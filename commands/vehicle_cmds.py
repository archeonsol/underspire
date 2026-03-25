"""
Vehicle commands: enter, disembark, mount, drive, fly, lock, control, repair, etc.
"""

from collections import deque

from commands.base_cmds import Command

try:
    from typeclasses.vehicles import vehicle_label
except ImportError:

    def vehicle_label(vehicle):
        if not vehicle:
            return "vehicle"
        return (
            getattr(vehicle.db, "vehicle_name", None) or getattr(vehicle, "key", None) or "vehicle"
        ).strip()

try:
    from world.rp_features import msg_room_with_character_display
except ImportError:
    msg_room_with_character_display = None


def _broadcast_engine_start(vehicle, caller, loc):
    """Notify cabin (if interior) and outside room with vehicle-specific copy."""
    lab = vehicle_label(vehicle)
    vt = getattr(vehicle.db, "vehicle_type", None) or "ground"
    if vt == "motorcycle":
        msg = f"{lab}'s engine fires up with a sharp bark and settles into a throaty idle."
    else:
        msg = f"The engine on {lab} turns over and rumbles to life."
    if loc and getattr(getattr(loc, "db", None), "vehicle", None) == vehicle:
        loc.msg_contents(msg, exclude=caller)
        exterior = getattr(vehicle, "location", None)
        if exterior:
            exterior.msg_contents(msg)
    elif loc:
        loc.msg_contents(msg, exclude=caller)


def _broadcast_engine_stop(vehicle, caller, loc):
    lab = vehicle_label(vehicle)
    vt = getattr(vehicle.db, "vehicle_type", None) or "ground"
    if vt == "motorcycle":
        msg = f"{lab}'s engine cuts out with a final pop."
    else:
        msg = f"{lab}'s engine sputters and goes quiet."
    if loc and getattr(getattr(loc, "db", None), "vehicle", None) == vehicle:
        loc.msg_contents(msg, exclude=caller)
        exterior = getattr(vehicle, "location", None)
        if exterior:
            exterior.msg_contents(msg)
    elif loc:
        loc.msg_contents(msg, exclude=caller)


def _sync_stale_in_vehicle(caller):
    """Clear db.in_vehicle if we're not actually inside that vehicle's cabin."""
    iv = getattr(caller.db, "in_vehicle", None)
    if not iv:
        return
    try:
        interior = getattr(iv, "interior", None)
        loc = caller.location
        if not interior or loc != interior:
            caller.db.in_vehicle = None
    except Exception:
        caller.db.in_vehicle = None


def _get_vehicle_from_caller(caller):
    """Vehicle if caller is inside an interior, or mounted on a motorcycle."""
    _sync_stale_in_vehicle(caller)
    loc = caller.location
    if not loc:
        return getattr(caller.db, "mounted_on", None) or getattr(caller.db, "in_vehicle", None)
    v = getattr(loc.db, "vehicle", None)
    if v:
        return v
    iv = getattr(caller.db, "in_vehicle", None)
    if iv:
        return iv
    return getattr(caller.db, "mounted_on", None)


def _resolve_drive_vehicle(caller):
    """Vehicle the caller is driving or could drive (interior or mounted)."""
    bike = getattr(caller.db, "mounted_on", None)
    if bike:
        return bike
    loc = caller.location
    if not loc:
        return None
    return getattr(loc.db, "vehicle", None)


def _can_takeoff_from_room(vehicle):
    """Require a valid exterior room (ground street or aerial corridor)."""
    room = getattr(vehicle, "location", None)
    if not room:
        return False, "The vehicle is nowhere."
    return True, ""


def _broadcast_cabin_and_exterior(vehicle, caller, line):
    """Send the same line to everyone in the cabin (except caller) and the exterior room."""
    loc = caller.location
    ext = getattr(vehicle, "location", None)
    if loc and getattr(getattr(loc, "db", None), "vehicle", None) == vehicle:
        loc.msg_contents(line, exclude=caller)
    if ext:
        ext.msg_contents(line)



class CmdExitVehicle(Command):
    """
    Get out of an enclosed vehicle. You appear in the same room as the vehicle.
    """

    key = "disembark"
    aliases = []
    locks = "cmd:all()"
    help_category = "Vehicles"
    usage_typeclasses = ["typeclasses.vehicles.VehicleInterior"]
    usage_hint = "|wdisembark|n (to get out)"

    def func(self):
        caller = self.caller
        vehicle = _get_vehicle_from_caller(caller)
        if not vehicle:
            caller.msg("You're not in a vehicle.")
            return
        try:
            from typeclasses.vehicles import Motorcycle
        except ImportError:
            Motorcycle = None
        if Motorcycle and isinstance(vehicle, Motorcycle):
            caller.msg("You're on a motorcycle. Use |wdismount|n.")
            return
        dest = vehicle.location
        if not dest:
            caller.msg("The vehicle is nowhere. You can't exit.")
            return
        vlabel = vehicle_label(vehicle)
        if not caller.move_to(dest, quiet=True, move_type="teleport"):
            caller.msg("You couldn't get out of the vehicle.")
            return
        if getattr(vehicle.db, "driver", None) == caller:
            vehicle.db.driver = None
        caller.db.in_vehicle = None
        caller.msg(f"You open the door and climb out of {vlabel}.")
        if dest and msg_room_with_character_display:
            msg_room_with_character_display(
                dest,
                caller,
                lambda _v, display: f"{display} gets out of {vlabel}.",
                exclude=[caller],
            )
        elif dest:
            dest.msg_contents(f"{caller.key} gets out of {vlabel}.", exclude=caller)


class CmdMount(Command):
    """Mount a motorcycle. You stay in the room."""

    key = "mount"
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Mount what? Usage: mount <bike>")
            return
        target = caller.search(self.args.strip(), location=caller.location)
        if not target:
            return
        try:
            from typeclasses.vehicles import Motorcycle
        except ImportError:
            caller.msg("Vehicle system unavailable.")
            return
        if not isinstance(target, Motorcycle) and getattr(target.db, "vehicle_type", None) != "motorcycle":
            caller.msg("That's not a motorcycle.")
            return
        target.at_enter(caller)


class CmdDismount(Command):
    """Dismount a motorcycle."""

    key = "dismount"
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        from world.vehicle_mounts import force_dismount

        caller = self.caller
        bike = getattr(caller.db, "mounted_on", None)
        if not bike:
            caller.msg("You're not on a bike.")
            return
        force_dismount(caller, bike, reason="")


class CmdControlVehicle(Command):
    """Take the driver seat in an enclosed vehicle."""

    key = "control"
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        caller = self.caller
        vehicle = _get_vehicle_from_caller(caller)
        if not vehicle:
            caller.msg("You're not inside a vehicle.")
            return
        try:
            from typeclasses.vehicles import Motorcycle
        except ImportError:
            return
        if isinstance(vehicle, Motorcycle) or getattr(vehicle.db, "vehicle_type", None) == "motorcycle":
            caller.msg("Use |wmount|n / |wdismount|n for motorcycles.")
            return
        cur = getattr(vehicle.db, "driver", None)
        if cur == caller:
            caller.msg("You are already at the controls.")
            return
        if cur and cur != caller:
            caller.msg("Someone else is at the wheel.")
            return
        # Leave the gunner station if currently on the guns
        if getattr(vehicle.db, "gunner", None) == caller:
            vehicle.db.gunner = None
            vehicle.db.gunner_mount = None
        vehicle.db.driver = caller
        caller.msg("You take the controls.")


class CmdReleaseControls(Command):
    """Let go of the wheel so someone else can |wcontrol|n (enclosed vehicles)."""

    key = "release controls"
    aliases = ["uncontrol", "release wheel"]
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        caller = self.caller
        vehicle = _get_vehicle_from_caller(caller)
        if not vehicle:
            caller.msg("You're not inside a vehicle.")
            return
        try:
            from typeclasses.vehicles import Motorcycle
        except ImportError:
            return
        if isinstance(vehicle, Motorcycle) or getattr(vehicle.db, "vehicle_type", None) == "motorcycle":
            caller.msg("Use |wdismount|n.")
            return
        is_driver = getattr(vehicle.db, "driver", None) == caller
        is_gunner = getattr(vehicle.db, "gunner", None) == caller
        if not is_driver and not is_gunner:
            caller.msg("You're not at the controls or a weapon station.")
            return
        if is_driver:
            vehicle.db.driver = None
            caller.msg("You take your hands off the wheel. Someone else can |wcontrol|n.")
        else:
            vehicle.db.gunner = None
            vehicle.db.gunner_mount = None
            caller.msg("You step away from the weapon station.")


# Backward-compatible name for imports
CmdStopDriving = CmdReleaseControls


class CmdHaltVehicleMovement(Command):
    """
    Cancel a queued drive or fly route and any pending delayed move (same pacing as |wstop walking|n on foot).

    Usage:
      halt driving
    """

    key = "halt driving"
    aliases = ["stop driving", "cancel driving", "halt vehicle", "halt flying"]
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        from world.vehicle_movement import bump_drive_session, clear_drive_queue_state

        caller = self.caller
        vehicle = _resolve_drive_vehicle(caller)
        if not vehicle:
            caller.msg("You're not in or on a vehicle.")
            return
        try:
            from typeclasses.vehicles import Motorcycle, VehicleInterior
        except ImportError:
            return
        if isinstance(caller.location, VehicleInterior) and not (
            isinstance(vehicle, Motorcycle) or getattr(vehicle.db, "vehicle_type", None) == "motorcycle"
        ):
            if getattr(vehicle.db, "driver", None) != caller:
                caller.msg("You're not driving.")
                return
        elif getattr(vehicle.db, "driver", None) and vehicle.db.driver != caller:
            caller.msg("You're not driving.")
            return
        vdb = getattr(vehicle, "db", None)
        if vdb is not None:
            vdb.cancel_vehicle_move = True
        clear_drive_queue_state(vehicle)
        bump_drive_session(vehicle)
        caller.msg("You cut the maneuver short and cancel any queued legs.")


class CmdTakeoff(Command):
    """Lift off the ground in an aerial vehicle (required before |wfly|n)."""

    key = "takeoff"
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        try:
            from typeclasses.vehicles import AerialVehicle, VehicleInterior
        except ImportError:
            return

        caller = self.caller
        vehicle = _get_vehicle_from_caller(caller)
        if not vehicle:
            caller.msg("You're not in a vehicle.")
            return
        if getattr(vehicle.db, "vehicle_type", None) != "aerial" and not isinstance(vehicle, AerialVehicle):
            caller.msg("|wTakeoff|n only applies to an aircraft.")
            return
        if not isinstance(caller.location, VehicleInterior):
            caller.msg("You need to be inside the craft.")
            return
        if getattr(vehicle.db, "driver", None) != caller:
            caller.msg("You're not at the controls.")
            return
        if not vehicle.engine_running:
            caller.msg("Start the engines first.")
            return
        if getattr(vehicle.db, "airborne", False):
            caller.msg("You're already airborne.")
            return
        ok, err = _can_takeoff_from_room(vehicle)
        if not ok:
            caller.msg(err)
            return
        lab = vehicle_label(vehicle)
        vehicle.db.airborne = True
        caller.msg(f"You power up the vert thrusters and ease {lab} up off the ground.")
        _broadcast_cabin_and_exterior(vehicle, caller, f"{lab} lifts off, vertical thrusters kicking in.")


class CmdLand(Command):
    """Settle back to the ground from airborne flight."""

    key = "land"
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        try:
            from typeclasses.vehicles import AerialVehicle, VehicleInterior
        except ImportError:
            return

        caller = self.caller
        vehicle = _get_vehicle_from_caller(caller)
        if not vehicle:
            caller.msg("You're not in a vehicle.")
            return
        if getattr(vehicle.db, "vehicle_type", None) != "aerial" and not isinstance(vehicle, AerialVehicle):
            caller.msg("|wLand|n only applies to an aircraft.")
            return
        if not isinstance(caller.location, VehicleInterior):
            caller.msg("You need to be inside the craft.")
            return
        if getattr(vehicle.db, "driver", None) != caller:
            caller.msg("You're not at the controls.")
            return
        if not getattr(vehicle.db, "airborne", False):
            caller.msg("You're not airborne. Use |wtakeoff|n first.")
            return
        if not vehicle.engine_running:
            caller.msg("The engines aren't running.")
            return
        lab = vehicle_label(vehicle)
        vehicle.db.airborne = False
        caller.msg(f"You power down the vert thrusters and ease {lab} down to the ground.")
        _broadcast_cabin_and_exterior(vehicle, caller, f"{lab} settles onto the ground, thrusters spooling down.")


class CmdStartEngine(Command):
    """Start the vehicle's engine."""

    key = "start"
    aliases = ["start engine", "ignition"]
    locks = "cmd:all()"
    help_category = "Vehicles"
    usage_hint = "|wstart|n (engine)"

    def func(self):
        caller = self.caller
        vehicle = _resolve_drive_vehicle(caller)
        if not vehicle:
            caller.msg("You're not in or on a vehicle.")
            return
        try:
            from typeclasses.vehicles import Motorcycle, VehicleInterior
        except ImportError:
            return
        loc = caller.location
        if isinstance(loc, VehicleInterior):
            if getattr(vehicle.db, "driver", None) != caller:
                caller.msg("You're not at the controls. Use |wcontrol|n to take the driver's seat.")
                return
        elif isinstance(vehicle, Motorcycle) or getattr(vehicle.db, "vehicle_type", None) == "motorcycle":
            if getattr(caller.db, "mounted_on", None) != vehicle:
                caller.msg("You need to be on the bike.")
                return
        else:
            caller.msg("You need to be inside the vehicle.")
            return
        if vehicle.engine_running:
            caller.msg("The engine is already running.")
            return
        try:
            from world.vehicles.vehicle_security import check_vehicle_permission

            if getattr(vehicle.db, "security_locked", False):
                caller.msg("The vehicle is locked.")
                return
            if not check_vehicle_permission(vehicle, caller, "start"):
                caller.msg("The ignition bioscan rejects you. Not authorized to start this vehicle.")
                return
        except ImportError:
            pass
        ok, err = vehicle.start_engine()
        if not ok:
            caller.msg(f"|r{err}|n")
            return
        lab = vehicle_label(vehicle)
        vt = getattr(vehicle.db, "vehicle_type", None) or "ground"
        if vt == "aerial":
            caller.msg(
                f"You pump the ignitor lever a few times and press the ignition switch. You hear the whine of "
                f"turbines spinning up as {lab} vibrates momentarily."
            )
            _broadcast_cabin_and_exterior(vehicle, caller, f"The turbines on {lab} spin up with a rising whine.")
        elif vt == "motorcycle":
            caller.msg(
                f"You thumb the starter. The engine catches with a raspy bark and settles into a throaty idle. "
                f"Use |wdrive|n to move, |whalt driving|n to cancel a queued route."
            )
            _broadcast_engine_start(vehicle, caller, loc)
        else:
            caller.msg(
                f"You twist the key in the ignition. The starter whines, the block turns over, and the engine "
                f"catches with a low rumble — the cab vibrates slightly at idle. Use |wdrive|n to move, "
                f"|whalt driving|n to cancel a queued route."
            )
            _broadcast_engine_start(vehicle, caller, loc)


class CmdStopEngine(Command):
    """Shut off the vehicle's engine from inside or while mounted."""

    key = "shutoff"
    aliases = ["stop engine", "stopengine", "kill engine", "turn off"]
    locks = "cmd:all()"
    help_category = "Vehicles"
    usage_hint = "|wshutoff|n"

    def func(self):
        caller = self.caller
        vehicle = _resolve_drive_vehicle(caller)
        if not vehicle:
            caller.msg("You're not in or on a vehicle.")
            return
        try:
            from typeclasses.vehicles import Motorcycle, VehicleInterior
        except ImportError:
            return
        loc = caller.location
        if isinstance(loc, VehicleInterior):
            if getattr(vehicle.db, "driver", None) != caller:
                caller.msg("You're not at the controls. Use |wcontrol|n to take the driver's seat.")
                return
        elif isinstance(vehicle, Motorcycle) or getattr(vehicle.db, "vehicle_type", None) == "motorcycle":
            if getattr(caller.db, "mounted_on", None) != vehicle:
                caller.msg("You need to be on the bike.")
                return
        else:
            caller.msg("You need to be inside the vehicle.")
            return
        if not vehicle.engine_running:
            caller.msg("The engine is already off.")
            return
        was_airborne = bool(getattr(vehicle.db, "airborne", False)) and getattr(
            vehicle.db, "vehicle_type", None
        ) == "aerial"
        lab = vehicle_label(vehicle)
        vt = getattr(vehicle.db, "vehicle_type", None) or "ground"
        vehicle.stop_engine()
        if vt == "aerial":
            caller.msg(f"You thumb the ignition panel and {lab} goes quiet.")
        elif vt == "motorcycle":
            caller.msg("You kill the engine. The frame goes still under you; only faint ticking remains.")
        else:
            caller.msg(
                "You twist the key back. The engine dies; the sudden quiet lets street noise and your own breathing "
                "fill the cab."
            )
        if was_airborne:
            caller.msg("|yThe craft settles as power cuts out.|n")
        _broadcast_engine_stop(vehicle, caller, loc)


class CmdShutoffEngine(Command):
    """
    Turn off a vehicle's engine from outside.
    Usage: shutoff exterior <vehicle>
    """

    key = "shutoff exterior"
    aliases = ["turn off engine outside", "kill engine outside", "reach in"]
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        caller = self.caller
        location = caller.location
        if not location:
            caller.msg("You are not in a room.")
            return
        if _get_vehicle_from_caller(caller):
            caller.msg("You're inside or on a vehicle. Use |wshutoff|n from here.")
            return
        arg = self.args.strip()
        if not arg:
            caller.msg("Usage: |wshutoff exterior <vehicle>|n")
            return
        vehicle = caller.search(arg, location=location)
        if not vehicle:
            return
        try:
            from typeclasses.vehicles import Vehicle
        except ImportError:
            return
        if not isinstance(vehicle, Vehicle):
            caller.msg("That isn't a vehicle.")
            return
        if not vehicle.engine_running:
            caller.msg("The engine is already off.")
            return
        vehicle.stop_engine()
        lab = vehicle_label(vehicle)
        vt = getattr(vehicle.db, "vehicle_type", None) or "ground"
        try:
            from typeclasses.vehicles import Motorcycle

            if isinstance(vehicle, Motorcycle):
                vt = "motorcycle"
        except ImportError:
            pass
        if vt == "motorcycle":
            caller.msg(
                f"You lean in and thumb the kill switch. The engine on {lab} cuts out with a final pop."
            )
        elif vt == "aerial":
            caller.msg(f"You slap the external cutoff. {lab}'s turbines spool down to silence.")
        else:
            caller.msg(f"You reach through the window and twist the key back. {lab}'s engine shudders and dies.")
        if msg_room_with_character_display:
            msg_room_with_character_display(
                location,
                caller,
                lambda _v, display: f"{display} turns off {lab}'s engine.",
                exclude=[caller],
            )
        else:
            location.msg_contents(f"{caller.key} turns off {lab}'s engine.", exclude=caller)


class CmdDrive(Command):
    """
    Drive a ground vehicle or motorcycle. One direction moves after a short delay;
    several directions form a queued route (brief cabin messages between legs, full view on a single leg).

    Usage:
      drive <direction> [<direction> ...]
    """

    key = "drive"
    locks = "cmd:all()"
    help_category = "Vehicles"
    usage_hint = "|wdrive <direction>|n"

    def func(self):
        from evennia.utils import delay
        from typeclasses.vehicles import _can_vehicle_enter
        from world.rpg.staggered_movement import DRIVE_DELAY, get_drive_delay
        from world.vehicle_movement import (
            bump_drive_session,
            clear_drive_queue_state,
            execute_vehicle_move,
            is_vehicle_drive_active,
            normalize_direction,
            set_drive_chain_active,
            staggered_drive_complete,
            vehicle_leg_roll_or_abort,
        )

        caller = self.caller
        vehicle = _resolve_drive_vehicle(caller)
        if not vehicle:
            caller.msg("You're not in or on a vehicle.")
            return
        if getattr(vehicle.db, "vehicle_type", None) == "aerial":
            caller.msg("This is an aircraft. Use |wfly <direction>|n.")
            return
        if getattr(vehicle.db, "driver", None) and vehicle.db.driver != caller:
            caller.msg("You're not driving.")
            return
        try:
            from world.vehicles.vehicle_security import check_vehicle_permission

            if not check_vehicle_permission(vehicle, caller, "drive"):
                caller.msg("The drive controls won't respond. You are not authorized to operate this vehicle.")
                return
        except ImportError:
            pass
        if not vehicle.engine_running:
            caller.msg("Start the engine first.")
            return
        try:
            from world.combat.vehicle_combat import vehicle_drive_movement_blocked

            _blocked = vehicle_drive_movement_blocked(vehicle)
            if _blocked:
                caller.msg(f"|r{_blocked}|n")
                return
        except Exception:
            pass
        try:
            import time

            if float(getattr(vehicle.db, "entangled_until", 0) or 0) > time.time():
                caller.msg("|yThe net tangles the wheels. Handling is compromised.|n")
        except Exception:
            pass
        if is_vehicle_drive_active(vehicle):
            caller.msg(
                "The vehicle is already in motion. Wait until you reach your destination "
                "or use |whalt driving|n / |whalt flying|n."
            )
            return
        parts = (self.args or "").strip().split()
        if not parts:
            caller.msg("Drive which way?")
            return
        directions = [normalize_direction(p) or p.strip().lower() for p in parts]
        for d in directions:
            if d in ("up", "down"):
                caller.msg("Ground vehicles can't go vertical. You need an AV for that.")
                return

        try:
            from world.movement import tunnels as _tunnels

            if getattr(vehicle.db, "autopilot_active", False):
                _tunnels.cancel_autopilot(vehicle, reason="Manual override.")
        except Exception:
            pass

        first_dir = directions[0]
        exit_obj = vehicle.get_exit(first_dir)
        if not exit_obj or not exit_obj.destination:
            caller.msg(f"No exit {first_dir} from here.")
            return
        dest = exit_obj.destination
        allowed, reason = _can_vehicle_enter(vehicle, dest)
        if not allowed:
            caller.msg(f"|r{reason}|n")
            return

        vdb = getattr(vehicle, "db", None)
        if vdb is not None and getattr(vdb, "cancel_vehicle_move", False):
            try:
                del vdb.cancel_vehicle_move
            except Exception:
                vdb.cancel_vehicle_move = False

        clear_drive_queue_state(vehicle)
        if len(directions) > 1:
            vehicle.ndb.drive_queue = deque(directions[1:])
            vehicle.ndb.drive_queue_multi_step = True
        else:
            vehicle.ndb.drive_queue_multi_step = False
        sid = bump_drive_session(vehicle)

        if delay and DRIVE_DELAY:
            set_drive_chain_active(vehicle)
            dir_display = normalize_direction(first_dir) or first_dir
            caller.msg(f"You begin driving {dir_display}.")
            delay(get_drive_delay(vehicle), staggered_drive_complete, vehicle.id, dest.id, first_dir, sid)
        else:
            if not vehicle_leg_roll_or_abort(vehicle, dest_room=dest):
                return
            execute_vehicle_move(vehicle, caller, dest, first_dir)


class CmdFly(Command):
    """
    Fly an aerial vehicle (piloting). Horizontal routes can be queued like |wdrive|n
    (same delay between legs). Use |wfly up|n / |wfly down|n alone for vertical moves.

    Usage:
      fly <direction> [<direction> ...]
      fly up / fly down
    """

    key = "fly"
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        from evennia.utils import delay
        from typeclasses.vehicles import AerialVehicle, _can_vehicle_enter
        from world.rpg.staggered_movement import DRIVE_DELAY, get_drive_delay
        from world.movement.aerial import fly_vertical
        from world.vehicle_movement import (
            bump_drive_session,
            clear_drive_queue_state,
            execute_vehicle_move,
            is_vehicle_drive_active,
            normalize_direction,
            set_drive_chain_active,
            staggered_drive_complete,
            vehicle_leg_roll_or_abort,
        )

        caller = self.caller
        vehicle = _get_vehicle_from_caller(caller)
        if not vehicle:
            caller.msg("You're not in a vehicle.")
            return
        if getattr(vehicle.db, "vehicle_type", None) != "aerial" and not isinstance(vehicle, AerialVehicle):
            caller.msg("This isn't an aircraft. Use |wdrive <direction>|n.")
            return
        if getattr(vehicle.db, "driver", None) and vehicle.db.driver != caller:
            caller.msg("You're not at the controls.")
            return
        try:
            from world.vehicles.vehicle_security import check_vehicle_permission

            if not check_vehicle_permission(vehicle, caller, "drive"):
                caller.msg("The flight controls won't respond. You are not authorized.")
                return
        except ImportError:
            pass
        if not vehicle.engine_running:
            caller.msg("Start the engines first.")
            return
        if not getattr(vehicle.db, "airborne", False):
            caller.msg("You need to |wtakeoff|n before you can fly.")
            return
        try:
            from world.combat.vehicle_combat import vehicle_drive_movement_blocked

            _blocked = vehicle_drive_movement_blocked(vehicle)
            if _blocked:
                caller.msg(f"|r{_blocked}|n")
                return
        except Exception:
            pass
        try:
            import time

            if float(getattr(vehicle.db, "entangled_until", 0) or 0) > time.time():
                caller.msg("|yThe net tangles the wheels. Handling is compromised.|n")
        except Exception:
            pass
        if is_vehicle_drive_active(vehicle):
            caller.msg(
                "The vehicle is already in motion. Wait until you reach your destination "
                "or use |whalt driving|n / |whalt flying|n."
            )
            return
        parts = (self.args or "").strip().split()
        if not parts:
            caller.msg("Fly which way? Usage: fly <direction>, fly up, fly down")
            return

        try:
            from world.movement import tunnels as _tunnels

            if getattr(vehicle.db, "autopilot_active", False):
                _tunnels.cancel_autopilot(vehicle, reason="Manual override.")
        except Exception:
            pass

        if parts[0].lower() in ("up", "down"):
            if len(parts) > 1:
                caller.msg("Use |wfly up|n or |wfly down|n alone — not mixed with horizontal legs.")
                return
            direction = parts[0].lower()
            current_room = vehicle.location
            if not current_room or not current_room.tags.has("aerial", category="vehicle_access"):
                caller.msg(
                    f"You can't fly {direction} here. You need to be in an aerial corridor or shaft."
                )
                return
            ok, msg = fly_vertical(vehicle, caller, direction)
            if not ok:
                if msg:
                    caller.msg(f"|r{msg}|n")
            return

        directions = [normalize_direction(p) or p.strip().lower() for p in parts]
        for d in directions:
            if d in ("up", "down"):
                caller.msg("Use |wfly up|n / |wfly down|n separately from horizontal routes.")
                return

        first_dir = directions[0]
        exit_obj = vehicle.get_exit(first_dir)
        if not exit_obj or not exit_obj.destination:
            caller.msg(f"No route {first_dir} from here.")
            return
        dest = exit_obj.destination
        allowed, reason = _can_vehicle_enter(vehicle, dest)
        if not allowed:
            caller.msg(f"|r{reason}|n")
            return

        vdb = getattr(vehicle, "db", None)
        if vdb is not None and getattr(vdb, "cancel_vehicle_move", False):
            try:
                del vdb.cancel_vehicle_move
            except Exception:
                vdb.cancel_vehicle_move = False

        clear_drive_queue_state(vehicle)
        if len(directions) > 1:
            vehicle.ndb.drive_queue = deque(directions[1:])
            vehicle.ndb.drive_queue_multi_step = True
        else:
            vehicle.ndb.drive_queue_multi_step = False
        sid = bump_drive_session(vehicle)

        if delay and DRIVE_DELAY:
            set_drive_chain_active(vehicle)
            dir_display = normalize_direction(first_dir) or first_dir
            caller.msg(f"You vector {dir_display}.")
            delay(get_drive_delay(vehicle), staggered_drive_complete, vehicle.id, dest.id, first_dir, sid)
        else:
            if not vehicle_leg_roll_or_abort(vehicle, dest_room=dest):
                return
            execute_vehicle_move(vehicle, caller, dest, first_dir, is_vertical=False)


class CmdEvaluateVehicle(Command):
    """Mechanic evaluation of a vehicle (class-specific parts)."""

    key = "evaluate"
    aliases = []
    locks = "cmd:all()"
    help_category = "Vehicles"
    usage_hint = "|wevaluate <vehicle>|n"

    def func(self):
        caller = self.caller
        loc = caller.location
        arg = (self.args or "").strip()
        if not arg:
            caller.msg("Usage: |wevaluate <vehicle>|n")
            return
        if not loc:
            caller.msg("You are not anywhere.")
            return
        try:
            from evennia.utils import delay
            from typeclasses.vehicles import Vehicle, VehicleInterior
            from world.vehicle_parts import (
                EVALUATE_FLAVOR_MESSAGES,
                EVALUATE_MECHANICS_MIN_LEVEL,
                _vehicle_evaluate_flavor_callback,
                _vehicle_evaluate_final_callback,
                get_vehicle_type,
            )
        except ImportError:
            caller.msg("Vehicle system is not available.")
            return

        candidates = [o for o in (loc.contents or []) if isinstance(o, Vehicle)]
        if isinstance(loc, VehicleInterior):
            v = getattr(loc.db, "vehicle", None)
            if v and v not in candidates:
                candidates.append(v)
        if candidates:
            vehicle = caller.search(arg, candidates=candidates)
        else:
            vehicle = caller.search(arg, location=loc)
        if not vehicle:
            return
        if not isinstance(vehicle, Vehicle):
            caller.msg("That's not a vehicle.")
            return
        level = getattr(caller, "get_skill_level", lambda s: 0)("mechanical_engineering")
        if level < EVALUATE_MECHANICS_MIN_LEVEL:
            caller.msg("You don't know enough about mechanics to evaluate the vehicle properly.")
            return
        vt = get_vehicle_type(vehicle)
        flavor = EVALUATE_FLAVOR_MESSAGES.get(vt) or EVALUATE_FLAVOR_MESSAGES["ground"]
        caller.msg("You walk around the vehicle and begin a proper evaluation.")
        for i, (_part_id, message) in enumerate(flavor):
            delay(2 * (i + 1), _vehicle_evaluate_flavor_callback, caller.id, message)
        # Last flavor line is at 2 * len(flavor) s; final readout must run after that (was EVALUATE_DURATION_SECONDS=18).
        delay(2 * len(flavor) + 1, _vehicle_evaluate_final_callback, caller.id, vehicle.id)


class CmdRepairPart(Command):
    """Repair a vehicle part (garage + tools + mechanical engineering)."""

    key = "repair"
    aliases = ["repair part", "fix vehicle"]
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        from evennia.utils import delay

        caller = self.caller
        loc = caller.location
        if not loc:
            caller.msg("You are not in a room.")
            return
        args = self.args.strip().split()
        if len(args) < 2:
            caller.msg("Usage: |wrepair <vehicle> <part>|n")
            return
        try:
            from typeclasses.vehicles import Vehicle
            from world.vehicle_parts import (
                REPAIR_CAPS,
                REPAIR_FLAVOR,
                calculate_repair_duration,
                get_part_display_name,
                get_part_ids,
                is_garage_room,
                _repair_tool_tag_from_inventory,
            )
            from world.skills import SKILL_STATS
            from world.vehicles.vehicle_security import check_vehicle_permission
        except ImportError:
            caller.msg("Vehicle or skill system not available.")
            return
        if not is_garage_room(loc):
            caller.msg("You need a proper shop. Find a |wgarage|n.")
            return
        vehicle_name, part_id = args[0], args[1].lower().replace(" ", "_")
        vehicle = caller.search(vehicle_name, location=loc)
        if not vehicle or not isinstance(vehicle, Vehicle):
            caller.msg("No such vehicle here.")
            return
        if not check_vehicle_permission(vehicle, caller, "modify"):
            caller.msg("The maintenance interlock won't disengage. Not authorized.")
            return
        valid = get_part_ids(vehicle)
        if part_id not in valid:
            caller.msg(f"Unknown part for this vehicle. Valid: {', '.join(valid)}")
            return
        current = vehicle.get_part_condition(part_id)
        if current >= 100:
            caller.msg(f"The {get_part_display_name(part_id)} is already in good shape.")
            return
        tool_tag = _repair_tool_tag_from_inventory(caller)
        if not tool_tag:
            caller.msg("You need a toolkit (basic, mechanic, or master) in your inventory.")
            return
        cap = REPAIR_CAPS.get(tool_tag, 50)
        if current >= cap:
            caller.msg(f"Your {tool_tag.replace('_', ' ')} can't improve this part further. Use better tools.")
            return
        stats = SKILL_STATS.get("mechanical_engineering", ["intelligence", "strength"])
        level, _ = caller.roll_check(stats, "mechanical_engineering", difficulty=15)
        repair_amount = 0
        if level == "Critical Success":
            repair_amount = 25
        elif level == "Full Success":
            repair_amount = 15
        elif level == "Marginal Success":
            repair_amount = 5
        if repair_amount <= 0:
            caller.msg("You work on it but don't manage to improve the condition.")
            return
        new_target = min(cap, current + repair_amount)
        add_amt = new_target - current
        dur = calculate_repair_duration(vehicle, part_id, tool_tag)
        part_name = get_part_display_name(part_id)
        flavor = REPAIR_FLAVOR.get(part_id) or REPAIR_FLAVOR["default"]
        caller.msg(f"You set up for a ~{dur}s job on {vehicle_label(vehicle)}'s {part_name}.")

        def _finish(caller_id, vid, pid, amount):
            from evennia.utils.search import search_object

            from world.vehicle_parts import get_part_display_name

            cr = search_object(f"#{caller_id}")
            vr = search_object(f"#{vid}")
            if not cr or not vr:
                return
            c, v = cr[0], vr[0]
            nc = v.repair_part(pid, amount)
            c.msg(f"You finish. The {get_part_display_name(pid)} is now |w{nc}%|n.")

        delay(dur, _finish, caller.id, vehicle.id, part_id, add_amt)
        for i, line in enumerate(flavor[:3]):
            delay(1 + i * 2, _repair_flavor_msg, caller.id, line)


def _repair_flavor_msg(caller_id, message):
    from evennia.utils.search import search_object

    try:
        o = search_object(f"#{caller_id}")
        if o:
            o[0].msg(f"|x{message}|n")
    except Exception:
        pass


class CmdRefuel(Command):
    key = "refuel"
    aliases = ["fuel", "gas up"]
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        from evennia.utils import delay

        caller = self.caller
        loc = caller.location
        if not loc:
            return
        args = (self.args or "").strip().split()
        if not args:
            caller.msg("Usage: refuel <vehicle> | refuel <vehicle> with <can>")
            return
        try:
            from typeclasses.vehicles import Vehicle
            from world.vehicle_parts import is_fuel_station_room
        except ImportError:
            return
        with_can = False
        if len(args) >= 3 and args[1].lower() == "with":
            veh_name, with_can = " ".join(args[:1]), True
            can_query = " ".join(args[2:])
        else:
            veh_name = " ".join(args)
            can_query = None
        vehicle = caller.search(veh_name, location=loc)
        if not vehicle or not isinstance(vehicle, Vehicle):
            return
        cap = float(getattr(vehicle.db, "fuel_capacity", 100) or 100)
        cur = float(getattr(vehicle.db, "fuel_level", 0) or 0)
        if cur >= cap - 0.01:
            caller.msg("The tank is already full.")
            return
        if with_can:
            can_obj = caller.search(can_query, location=caller)
            if not can_obj:
                return
            amt = float(getattr(can_obj.db, "fuel_amount", 0) or 0)
            if amt <= 0:
                caller.msg("That container is empty.")
                return
            need = cap - cur
            take = min(need, amt)
            vehicle.db.fuel_level = cur + take
            can_obj.db.fuel_amount = amt - take
            if can_obj.db.fuel_amount <= 0:
                can_obj.delete()
            caller.msg(f"You top up the tank from the can (+{take:.1f}).")
            return
        if not is_fuel_station_room(loc):
            caller.msg("You need to be at a fuel station or use a fuel can (|wrefuel <v> with <can>|n).")
            return

        def _done(cid, vid):
            from evennia.utils.search import search_object

            from world.vehicle_parts import invalidate_perf_cache

            c = search_object(f"#{cid}")
            v = search_object(f"#{vid}")
            if not c or not v:
                return
            veh = v[0]
            cap2 = float(getattr(veh.db, "fuel_capacity", 100) or 100)
            veh.db.fuel_level = cap2
            invalidate_perf_cache(veh)
            c[0].msg("|gTank filled.|n")

        caller.msg("You start refueling (10s)...")
        delay(10, _done, caller.id, vehicle.id)


class CmdSwapVehiclePart(Command):
    key = "swap"
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        caller = self.caller
        loc = caller.location
        if not loc:
            return
        parts = (self.args or "").strip().split()
        if len(parts) < 3:
            caller.msg("Usage: swap <vehicle> <part_slot> <type_id>")
            return
        try:
            from typeclasses.vehicles import Vehicle
            from world.vehicle_parts import (
                SWAP_DIFFICULTY,
                get_part_display_name,
                get_part_ids,
                is_garage_room,
                set_part_type_id,
            )
            from world.vehicles.vehicle_security import check_vehicle_permission
        except ImportError:
            return
        if not is_garage_room(loc):
            caller.msg("You need a |wgarage|n to swap parts.")
            return
        vname, slot, type_id = parts[0], parts[1].lower(), parts[2].lower()
        vehicle = caller.search(vname, location=loc)
        if not vehicle or not isinstance(vehicle, Vehicle):
            return
        if not check_vehicle_permission(vehicle, caller, "modify"):
            caller.msg("Not authorized to modify this vehicle.")
            return
        if slot not in get_part_ids(vehicle):
            caller.msg("Invalid part slot.")
            return
        diff = SWAP_DIFFICULTY.get(slot, 25)
        from world.skills import SKILL_STATS

        stats = SKILL_STATS.get("mechanical_engineering", ["intelligence", "strength"])
        tier, _ = caller.roll_check(stats, "mechanical_engineering", difficulty=diff)
        if tier not in ("Critical Success", "Full Success", "Marginal Success"):
            caller.msg("Installation fails.")
            return
        if not set_part_type_id(vehicle, slot, type_id):
            caller.msg("That part type doesn't exist for this slot.")
            return
        qual = 100 if tier == "Critical Success" else (90 if tier == "Full Success" else 75)
        vehicle.set_part_condition(slot, qual)
        caller.msg(f"You install {type_id} on the {get_part_display_name(slot)} (condition ~{qual}%).")


class CmdPaintVehicle(Command):
    key = "paint"
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        caller = self.caller
        loc = caller.location
        if not loc:
            return
        try:
            from typeclasses.vehicles import Vehicle
            from world.vehicle_parts import PAINT_COLORS, is_garage_room
            from world.skills import SKILL_STATS
            from world.vehicles.vehicle_security import check_vehicle_permission
        except ImportError:
            return
        if not is_garage_room(loc):
            caller.msg("You need a |wgarage|n to paint.")
            return
        args = (self.args or "").strip().split()
        if len(args) < 2:
            caller.msg("Usage: paint <vehicle> <color_key>")
            return
        vehicle = caller.search(args[0], location=loc)
        if not vehicle or not isinstance(vehicle, Vehicle):
            return
        if not check_vehicle_permission(vehicle, caller, "modify"):
            caller.msg("Not authorized.")
            return
        ckey = args[1].lower()
        data = PAINT_COLORS.get(ckey)
        if not data:
            caller.msg(f"Unknown color. Try: {', '.join(PAINT_COLORS.keys())}")
            return
        has_can = any(getattr(o.db, "paint_can_color", None) == ckey for o in caller.contents)
        if not has_can:
            caller.msg("You need a matching paint can in inventory.")
            return
        stats = SKILL_STATS.get("mechanical_engineering", ["intelligence", "strength"])
        tier, _ = caller.roll_check(stats, "mechanical_engineering", difficulty=20)
        pq = 100 if tier == "Critical Success" else (80 if tier == "Full Success" else (50 if tier == "Marginal Success" else 0))
        if pq <= 0:
            caller.msg("The job goes wrong.")
            return
        vehicle.db.paint_color = ckey
        vehicle.db.paint_color_code = data["code"]
        vehicle.db.custom_desc_prefix = data["desc_prefix"]
        vehicle.db.paint_quality = float(pq)
        for o in list(caller.contents):
            if getattr(o.db, "paint_can_color", None) == ckey:
                o.delete()
                break
        caller.msg(f"You lay down {data['name']}. Quality ~{pq}%.")


class CmdCustomizeVehicle(Command):
    key = "customize"
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        caller = self.caller
        loc = caller.location
        if not loc:
            return
        try:
            from typeclasses.vehicles import Vehicle
            from world.vehicle_parts import is_garage_room
            from world.vehicles.vehicle_security import check_vehicle_permission
        except ImportError:
            return
        if not is_garage_room(loc):
            caller.msg("You need a |wgarage|n.")
            return
        raw = (self.args or "").strip()
        if not raw:
            caller.msg("Usage: customize <vehicle> add decal <text> | customize <vehicle> list | customize <vehicle> remove <n>")
            return
        toks = raw.split(None, 2)
        vehicle = caller.search(toks[0], location=loc)
        if not vehicle or not isinstance(vehicle, Vehicle):
            return
        if not check_vehicle_permission(vehicle, caller, "modify"):
            caller.msg("Not authorized.")
            return
        if len(toks) >= 2 and toks[1].lower() == "list":
            vm = getattr(vehicle.db, "visual_mods", None) or []
            if not vm:
                caller.msg("No visual mods.")
                return
            for i, e in enumerate(vm, 1):
                caller.msg(f"  {i}. {e.get('desc', '')}")
            return
        if len(toks) >= 2 and toks[1].lower() == "remove":
            try:
                n = int(toks[2].strip())
            except (ValueError, IndexError):
                caller.msg("Usage: customize <vehicle> remove <number>")
                return
            vm = list(getattr(vehicle.db, "visual_mods", None) or [])
            if 1 <= n <= len(vm):
                vm.pop(n - 1)
                vehicle.db.visual_mods = vm
                caller.msg("Removed.")
            else:
                caller.msg("Invalid index.")
            return
        if len(toks) >= 3 and toks[1].lower() == "add":
            rest = toks[2].split(None, 1)
            if len(rest) < 2:
                caller.msg("Usage: customize <vehicle> add decal <description>")
                return
            kind, desc = rest[0].lower(), rest[1].strip()
            vm = list(getattr(vehicle.db, "visual_mods", None) or [])
            vm.append({"type": kind, "desc": desc, "applied_by": caller.key})
            vehicle.db.visual_mods = vm
            caller.msg("Visual mod added.")
            return
        caller.msg("See help customize.")
