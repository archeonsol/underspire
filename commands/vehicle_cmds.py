"""
Vehicle commands: CmdEnterVehicle, CmdExitVehicle, CmdStartEngine, CmdStopEngine, CmdShutoffEngine,
CmdDrive, CmdVehicleStatus, CmdRepairPart, _get_vehicle_from_caller.
"""

from commands.base_cmds import Command


def _get_vehicle_from_caller(caller):
    """If caller is inside a vehicle interior, return the vehicle; else None."""
    loc = caller.location
    if not loc:
        return None
    return getattr(loc.db, "vehicle", None)


class CmdEnterVehicle(Command):
    """
    Enter (or ride) a vehicle. You are moved to its interior. Start the engine to drive.
    """
    key = "enter"
    aliases = ["ride", "board"]
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.vehicles.Vehicle"]
    usage_hint = "|wenter|n / |wride|n (to get in)"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Enter what? Usage: enter <vehicle>")
            return
        if _get_vehicle_from_caller(caller):
            caller.msg("You are already inside a vehicle. Exit first.")
            return
        vehicle = caller.search(self.args.strip(), location=caller.location)
        if not vehicle:
            return
        if not (hasattr(vehicle, "interior") and vehicle.interior):
            caller.msg("That is not a vehicle you can enter.")
            return
        caller.move_to(vehicle.interior)
        caller.db.in_vehicle = vehicle
        caller.msg(f"You enter {vehicle.key}. You're inside. Use |wstart|n to start the engine, |wdrive <direction>|n to move, |wexit|n to get out.")
        caller.location.msg_contents(f"{caller.key} enters.", exclude=caller)


class CmdExitVehicle(Command):
    """
    Get out of the vehicle. You appear in the same room as the vehicle.
    """
    key = "disembark"
    aliases = ["disembark"]
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.vehicles.VehicleInterior"]
    usage_hint = "|wexit|n (to get out)"

    def func(self):
        caller = self.caller
        vehicle = _get_vehicle_from_caller(caller)
        if not vehicle:
            caller.msg("You're not in a vehicle.")
            return
        dest = vehicle.location
        if not dest:
            caller.msg("The vehicle is nowhere. You can't exit.")
            return
        caller.db.in_vehicle = None
        caller.move_to(dest)
        caller.msg(f"You get out of {vehicle.key}.")
        dest.msg_contents(f"{caller.key} gets out of {vehicle.key}.", exclude=caller)


class CmdStartEngine(Command):
    """Start the vehicle's engine. Required to drive."""
    key = "start"
    aliases = ["start engine", "ignition"]
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.vehicles.VehicleInterior"]
    usage_hint = "|wstart|n (engine)"

    def func(self):
        caller = self.caller
        vehicle = _get_vehicle_from_caller(caller)
        if not vehicle:
            caller.msg("You're not inside a vehicle.")
            return
        if vehicle.engine_running:
            caller.msg("The engine is already running.")
            return
        ok, err = vehicle.start_engine()
        if not ok:
            caller.msg(f"|r{err}|n")
            return
        caller.msg("You start the engine. It's running. Use |wdrive <direction>|n to move.")
        caller.location.msg_contents("The engine starts.", exclude=caller)


class CmdStopEngine(Command):
    """Turn off the vehicle's engine."""
    key = "stop engine"
    aliases = ["stopengine", "kill engine", "turn off"]
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.vehicles.VehicleInterior"]
    usage_hint = "|wstop engine|n"

    def func(self):
        caller = self.caller
        vehicle = _get_vehicle_from_caller(caller)
        if not vehicle:
            caller.msg("You're not inside a vehicle.")
            return
        if not vehicle.engine_running:
            caller.msg("The engine is already off.")
            return
        vehicle.stop_engine()
        caller.msg("You turn off the engine.")
        caller.location.msg_contents("The engine stops.", exclude=caller)


class CmdShutoffEngine(Command):
    """
    Turn off a vehicle's engine from outside (e.g. you're in the room, not inside the vehicle).
    Usage: shutoff <vehicle>   or   turn off <vehicle>
    """
    key = "shutoff"
    aliases = ["turn off engine", "kill engine outside"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        location = caller.location
        if not location:
            caller.msg("You are not in a room.")
            return
        if _get_vehicle_from_caller(caller):
            caller.msg("You're inside a vehicle. Use |wstop engine|n to turn it off from here.")
            return
        arg = self.args.strip()
        if not arg:
            caller.msg("Usage: |wshutoff <vehicle>|n (e.g. shutoff sedan)")
            return
        vehicle = caller.search(arg, location=location)
        if not vehicle:
            return
        try:
            from typeclasses.vehicles import Vehicle
            if not isinstance(vehicle, Vehicle):
                caller.msg("That isn't a vehicle.")
                return
        except ImportError:
            caller.msg("That isn't a vehicle.")
            return
        if not vehicle.engine_running:
            caller.msg("The engine is already off.")
            return
        vehicle.stop_engine()
        caller.msg(f"You reach in and turn off {vehicle.key}'s engine.")
        location.msg_contents(f"{caller.key} turns off {vehicle.key}'s engine.", exclude=caller)


class CmdDrive(Command):
    """
    Drive the vehicle in a direction. Engine must be running. Uses driving skill.
    Usage: drive <direction>   e.g. drive east, drive n
    """
    key = "drive"
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.vehicles.VehicleInterior"]
    usage_hint = "|wdrive <direction>|n (e.g. drive east)"

    def func(self):
        caller = self.caller
        vehicle = _get_vehicle_from_caller(caller)
        if not vehicle:
            caller.msg("You're not inside a vehicle.")
            return
        if not vehicle.engine_running:
            caller.msg("Start the engine first.")
            return
        direction = self.args.strip() if self.args else ""
        if not direction:
            caller.msg("Drive which way? Usage: drive <direction>  (e.g. drive east)")
            return
        exit_obj = vehicle.get_exit(direction)
        if not exit_obj or not exit_obj.destination:
            caller.msg(f"There is no exit {direction} from here.")
            return
        dest = exit_obj.destination
        # Driving skill check; vehicle parts add failure modifier
        from world.skills import SKILL_STATS, DEFENSE_SKILL
        skill = getattr(vehicle.db, "driving_skill", "driving")
        stats = SKILL_STATS.get(skill, ["perception", "agility"])
        mod = getattr(vehicle, "drive_failure_modifier", lambda: 0)()
        level, roll_value = caller.roll_check(stats, skill, modifier=-mod)
        if level == "Failure":
            caller.msg("You fumble the controls. The vehicle doesn't move.")
            return
        # Optional stall check (damaged engine/fuel/electrical)
        if getattr(vehicle, "roll_stall_chance", lambda: False)():
            vehicle.stop_engine()
            caller.msg("|rThe engine sputters and dies. You coast to a stop.|n")
            caller.location.msg_contents("The engine sputters and stalls.", exclude=caller)
            return
        # Staggered drive: message first, then move after delay; passengers see new outside on arrival
        try:
            from evennia.utils import delay
            from world.staggered_movement import DRIVE_DELAY, _staggered_drive_callback
        except ImportError:
            delay = None
            _staggered_drive_callback = None
        if delay and _staggered_drive_callback:
            caller.msg(f"You begin driving {direction}.")
            caller.location.msg_contents(f"{caller.key} begins driving {direction}.", exclude=caller)
            delay(DRIVE_DELAY, _staggered_drive_callback, vehicle.id, dest.id, direction)
        else:
            old_room = vehicle.location
            vehicle.move_to(dest, quiet=True)
            caller.msg(f"You drive {direction}. You arrive at {dest.key}.")
            caller.location.msg_contents(f"The vehicle drives {direction}. You arrive at {dest.key}.", exclude=caller)
            if old_room:
                old_room.msg_contents(f"{vehicle.key} drives {direction}.")
            dest.msg_contents(f"{vehicle.key} arrives from {direction}.")


class CmdVehicleStatus(Command):
    """
    Perform a mechanic-style inspection of a vehicle over 15–20 seconds. You check each part in turn
    with RP messages, then see the full condition and part types. Requires mechanical_engineering skill.
    Usage: vehicle status [vehicle]   or   inspect vehicle [vehicle]
    """
    key = "vehicle status"
    aliases = ["vehiclestatus", "inspect vehicle", "vstatus"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        loc = caller.location
        arg = self.args.strip()
        vehicle = None
        try:
            from evennia.utils import delay
            from typeclasses.vehicles import Vehicle
            from world.vehicle_parts import (
                INSPECT_DURATION_SECONDS,
                INSPECT_MECHANICS_MIN_LEVEL,
                INSPECT_FLAVOR_MESSAGES,
                _vehicle_inspect_flavor_callback,
                _vehicle_inspect_final_callback,
                default_part_types,
            )
        except ImportError as e:
            caller.msg("Vehicle system is not available.")
            return
        vehicle = _get_vehicle_from_caller(caller)
        if not vehicle and loc:
            if arg:
                vehicle = caller.search(arg, location=loc)
            if not vehicle and loc.contents:
                for obj in loc.contents:
                    if isinstance(obj, Vehicle):
                        vehicle = obj
                        break
        if not vehicle or not isinstance(vehicle, Vehicle):
            caller.msg("Inspect which vehicle? Usage: |wvehicle status [vehicle]|n (or use from inside one).")
            return
        # Gate behind mechanics skill
        level = getattr(caller, "get_skill_level", lambda s: 0)("mechanical_engineering")
        if level < INSPECT_MECHANICS_MIN_LEVEL:
            caller.msg("You don't know enough about mechanics to inspect the vehicle properly. Train |wmechanical_engineering|n.")
            return
        # Ensure part types exist on vehicle (older vehicles may not have them)
        if not getattr(vehicle.db, "vehicle_part_types", None):
            vehicle.db.vehicle_part_types = default_part_types()
        # Start timed inspection
        caller.msg("You walk around the vehicle and begin a proper inspection.")
        for i, (part_id, message) in enumerate(INSPECT_FLAVOR_MESSAGES):
            delay(2 * (i + 1), _vehicle_inspect_flavor_callback, caller.id, message)
        delay(INSPECT_DURATION_SECONDS, _vehicle_inspect_final_callback, caller.id, vehicle.id)


class CmdRepairPart(Command):
    """
    Repair a vehicle part using mechanical engineering. You must be next to the vehicle (same room).
    Usage: repair <vehicle> <part>   e.g. repair sedan engine
    """
    key = "repair"
    aliases = ["repair part", "fix vehicle"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        loc = caller.location
        args = self.args.strip().split()
        if len(args) < 2:
            caller.msg("Usage: |wrepair <vehicle> <part>|n (e.g. repair sedan engine). Parts: engine, transmission, brakes, suspension, tires, battery, fuel_system, cooling_system, electrical")
            return
        try:
            from typeclasses.vehicles import Vehicle
            from world.vehicle_parts import VEHICLE_PART_IDS, PART_DISPLAY_NAMES
            from world.skills import SKILL_STATS
        except ImportError as e:
            caller.msg("Vehicle or skill system not available.")
            return
        vehicle_name, part_id = args[0], args[1].lower().replace(" ", "_")
        vehicle = caller.search(vehicle_name, location=loc)
        if not vehicle or not isinstance(vehicle, Vehicle):
            caller.msg("No such vehicle here.")
            return
        if part_id not in VEHICLE_PART_IDS:
            caller.msg(f"Unknown part. Valid: {', '.join(VEHICLE_PART_IDS)}")
            return
        current = vehicle.get_part_condition(part_id)
        if current >= 100:
            caller.msg(f"The {PART_DISPLAY_NAMES.get(part_id, part_id)} is already in good shape.")
            return
        stats = SKILL_STATS.get("mechanical_engineering", ["intelligence", "strength"])
        level, _ = caller.roll_check(stats, "mechanical_engineering")
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
        new_cond = vehicle.repair_part(part_id, repair_amount)
        part_name = PART_DISPLAY_NAMES.get(part_id, part_id)
        caller.msg(f"You repair the {part_name}. Condition now |w{new_cond}%|n (was {current}%).")
        loc.msg_contents(f"{caller.key} works on {vehicle.key}'s {part_name}.", exclude=caller)
