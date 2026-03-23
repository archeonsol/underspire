"""
Shared vehicle movement: announcements, reverse directions, execute moves for drive/fly/autopilot.
"""
from __future__ import annotations

import time

from evennia.objects.objects import DefaultExit

from world.rp_features import msg_room_with_character_display

VEHICLE_ACCESS_CAT = "vehicle_access"


def _movement_maneuver(vehicle, destination, old_room, direction: str) -> str:
    """Classify maneuver for drive checks and fuel/wear multipliers."""
    if destination and hasattr(destination, "tags"):
        try:
            if destination.tags.has("offroad", category=VEHICLE_ACCESS_CAT):
                return "offroad"
        except Exception:
            pass
    ndb = getattr(vehicle, "ndb", None)
    prev = getattr(ndb, "drive_prev_direction", None) if ndb else None
    dnorm = normalize_direction(direction) or direction
    if prev and dnorm:
        pnorm = normalize_direction(prev) or prev
        if pnorm != dnorm:
            return "corner"
    return "normal"


def _after_vehicle_move_hook(vehicle, driver, destination, old_room, direction: str):
    from world.vehicle_parts import _vehicle_after_room_transition
    from world.combat.vehicle_combat import check_room_hazards

    if not vehicle or not destination:
        return
    check_room_hazards(vehicle, destination)
    maneuver = _movement_maneuver(vehicle, destination, old_room, direction)
    _vehicle_after_room_transition(vehicle, driver, destination, maneuver=maneuver, rooms=1)

_DIR_ALIASES = {
    "n": "north",
    "s": "south",
    "e": "east",
    "w": "west",
    "ne": "northeast",
    "nw": "northwest",
    "se": "southeast",
    "sw": "southwest",
    "u": "up",
    "d": "down",
}

_OPP = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "northeast": "southwest",
    "southwest": "northeast",
    "northwest": "southeast",
    "southeast": "northwest",
    "up": "down",
    "down": "up",
}


def normalize_direction(direction: str) -> str:
    if not direction:
        return ""
    d = direction.strip().lower()
    return _DIR_ALIASES.get(d, d)


def reverse_direction(direction: str) -> str:
    """Opposite compass direction for 'arrives from the …' messages."""
    d = normalize_direction(direction)
    return _OPP.get(d, d)


def _vehicle_display_name(vehicle) -> str:
    return getattr(vehicle.db, "vehicle_name", None) or vehicle.key


def execute_vehicle_move(
    vehicle,
    driver,
    destination,
    direction: str,
    *,
    is_vertical: bool = False,
    cabin_message: str | None = None,
    exterior_departure_message: str | None = None,
):
    """
    Move vehicle and occupants; announce to old room, new room, and interior (windscreen).
    driver may be None (e.g. delayed callback).
    If cabin_message is set (queued multi-step moves), cabin/rider see only that instead of a full outside look.
    If exterior_departure_message is set, old-room observers see that instead of generic departure lines.
    """
    from typeclasses.vehicles import AerialVehicle, Motorcycle, Vehicle

    if not vehicle or not destination:
        return

    old_room = vehicle.location
    direction = normalize_direction(direction) or (direction or "").strip().lower()
    vehicle_name = _vehicle_display_name(vehicle)
    rev = reverse_direction(direction)

    vtype = getattr(vehicle.db, "vehicle_type", None) or "ground"

    if isinstance(vehicle, Motorcycle) or vtype == "motorcycle":
        _move_motorcycle(
            vehicle,
            driver,
            destination,
            old_room,
            direction,
            vehicle_name,
            rev,
            cabin_message=cabin_message,
            exterior_departure_message=exterior_departure_message,
        )
        _after_vehicle_move_hook(vehicle, driver, destination, old_room, direction)
        return

    if isinstance(vehicle, AerialVehicle) or vtype == "aerial":
        _move_aerial(
            vehicle,
            driver,
            destination,
            old_room,
            direction,
            vehicle_name,
            rev,
            is_vertical=is_vertical,
            cabin_message=cabin_message,
            exterior_departure_message=exterior_departure_message,
        )
        _after_vehicle_move_hook(vehicle, driver, destination, old_room, direction)
        return

    if isinstance(vehicle, Vehicle) or vtype in ("ground", None):
        _move_enclosed_ground(
            vehicle,
            driver,
            destination,
            old_room,
            direction,
            vehicle_name,
            rev,
            cabin_message=cabin_message,
            exterior_departure_message=exterior_departure_message,
        )
        _after_vehicle_move_hook(vehicle, driver, destination, old_room, direction)
        return


def _move_enclosed_ground(
    vehicle,
    driver,
    destination,
    old_room,
    direction,
    vehicle_name,
    rev,
    *,
    cabin_message: str | None = None,
    exterior_departure_message: str | None = None,
):
    vehicle.move_to(destination, quiet=True)
    if old_room:
        if exterior_departure_message:
            old_room.msg_contents(exterior_departure_message)
        else:
            old_room.msg_contents(f"{vehicle_name} drives {direction}.")
    destination.msg_contents(f"{vehicle_name} arrives from the {rev}.")
    interior = getattr(vehicle, "interior", None)
    if interior and hasattr(interior, "get_outside_block"):
        try:
            chars = interior.contents_get(content_type="character") or []
        except Exception:
            chars = [c for c in interior.contents or [] if c]
        for char in chars:
            if hasattr(char, "msg"):
                if cabin_message:
                    char.msg(cabin_message)
                else:
                    block = interior.get_outside_block(char)
                    if block:
                        char.msg(f"|xYou arrive at {destination.key}.|n\n\n{block}")


def _move_motorcycle(
    vehicle,
    driver,
    destination,
    old_room,
    direction,
    vehicle_name,
    rev,
    *,
    cabin_message: str | None = None,
    exterior_departure_message: str | None = None,
):
    rider = getattr(vehicle.db, "rider", None)
    pillion = None
    if getattr(vehicle.db, "has_pillion", False) and old_room:
        try:
            for c in old_room.contents_get(content_type="character"):
                if c is rider:
                    continue
                if getattr(c.db, "mounted_on", None) == vehicle:
                    pillion = c
                    break
        except Exception:
            pillion = None

    vehicle.move_to(destination, quiet=True)
    for char in (rider, pillion):
        if char and char.location == old_room:
            # Not move/traverse — avoids FurnitureMixin try_auto_dismount (rider stays mounted).
            char.move_to(destination, quiet=True, move_type="teleport")

    if old_room:
        if exterior_departure_message:
            old_room.msg_contents(exterior_departure_message)
        else:
            msg_room_with_character_display(
                old_room,
                rider,
                lambda _v, display: f"{display} guns the throttle and roars {direction} on {vehicle_name}.",
            )
    exclude = [x for x in (rider, pillion) if x]
    msg_room_with_character_display(
        destination,
        rider,
        lambda _v, display: f"{display} roars in from the {rev} on {vehicle_name}.",
        exclude=exclude or None,
    )
    if rider:
        if cabin_message:
            rider.msg(cabin_message)
            if pillion:
                pillion.msg(cabin_message)
        else:
            rider.msg(f"You ride {direction}. You arrive at {destination.key}.")
        try:
            from world.combat.mounted_combat import set_biker_momentum

            set_biker_momentum(rider)
        except Exception:
            pass


def _move_aerial(
    vehicle,
    driver,
    destination,
    old_room,
    direction,
    vehicle_name,
    rev,
    *,
    is_vertical: bool,
    cabin_message: str | None = None,
    exterior_departure_message: str | None = None,
):
    old_is_air = bool(getattr(getattr(old_room, "db", None), "is_air", False))
    dest_is_air = bool(getattr(getattr(destination, "db", None), "is_air", False))

    vehicle.move_to(destination, quiet=True)

    if old_room:
        if exterior_departure_message:
            old_room.msg_contents(exterior_departure_message)
        elif old_is_air:
            old_room.msg_contents(f"The lights of {vehicle_name} recede {direction}.")
        else:
            old_room.msg_contents(f"{vehicle_name} lifts and banks {direction}.")

    if dest_is_air:
        if is_vertical:
            src = "below" if direction == "up" else "above"
        else:
            src = rev
        destination.msg_contents(
            f"Engine noise. The lights of {vehicle_name} appear from the {src}."
        )
    else:
        destination.msg_contents(f"{vehicle_name} descends and settles in from the {rev}.")

    interior = getattr(vehicle, "interior", None)
    if interior and hasattr(interior, "get_outside_block"):
        try:
            chars = interior.contents_get(content_type="character") or []
        except Exception:
            chars = [c for c in interior.contents or [] if c]
        for char in chars:
            if hasattr(char, "msg"):
                if cabin_message:
                    char.msg(cabin_message)
                else:
                    block = interior.get_outside_block(char)
                    if block:
                        char.msg(f"|xYou fly {direction}. The craft adjusts.|n\n\n{block}")


def bump_drive_session(vehicle):
    """Invalidate pending drive callbacks; call when starting a new drive chain or halting."""
    ndb = getattr(vehicle, "ndb", None)
    if ndb is None:
        return 0
    sid = int(getattr(ndb, "drive_session_id", 0) or 0) + 1
    ndb.drive_session_id = sid
    return sid


def clear_drive_chain_active(vehicle):
    ndb = getattr(vehicle, "ndb", None)
    if ndb is not None and hasattr(ndb, "drive_chain_active"):
        try:
            delattr(ndb, "drive_chain_active")
        except Exception:
            pass


def set_drive_chain_active(vehicle):
    ndb = getattr(vehicle, "ndb", None)
    if ndb is not None:
        ndb.drive_chain_active = True


def is_vehicle_drive_active(vehicle):
    """True if a drive/fly chain is in progress (delayed leg or queued legs)."""
    ndb = getattr(vehicle, "ndb", None)
    if not ndb:
        return False
    if getattr(ndb, "drive_chain_active", False):
        return True
    q = getattr(ndb, "drive_queue", None)
    return bool(q and len(q) > 0)


def clear_drive_queue_state(vehicle):
    """Clear queued segments and multi-step flags (not session id)."""
    ndb = getattr(vehicle, "ndb", None)
    if ndb is None:
        return
    for attr in ("drive_queue", "drive_queue_multi_step", "drive_prev_direction"):
        try:
            if hasattr(ndb, attr):
                delattr(ndb, attr)
        except Exception:
            pass
    clear_drive_chain_active(vehicle)


def _vehicle_leg_roll(vehicle, dest_room=None):
    """
    Per-room driving / piloting check for staggered moves.
    Returns (True, None) or (False, 'skill' | 'stall').
    """
    driver = getattr(vehicle.db, "driver", None)
    if not driver:
        return False, "skill"
    roll_check = getattr(driver, "roll_check", None)
    if not callable(roll_check):
        return False, "skill"
    try:
        from world.skills import SKILL_STATS

        vtype = getattr(vehicle.db, "vehicle_type", None) or "ground"
        if vtype == "aerial":
            skill = "piloting"
        else:
            skill = getattr(vehicle.db, "driving_skill", None) or "driving"
        stats = SKILL_STATS.get(skill, ["perception", "agility"])
        maneuver = "normal"
        if dest_room and hasattr(dest_room, "tags"):
            try:
                if dest_room.tags.has("offroad", category=VEHICLE_ACCESS_CAT):
                    maneuver = "offroad"
            except Exception:
                pass
        get_mod = getattr(vehicle, "get_drive_check_modifier", None)
        if callable(get_mod):
            mod = int(get_mod(maneuver))
        else:
            from world.vehicle_parts import drive_failure_modifier

            mod = -int(drive_failure_modifier(vehicle))
        ent_pen = 0
        ent = float(getattr(vehicle.db, "entangled_until", 0) or 0)
        if ent > time.time():
            ent_pen = -15
        level, _ = roll_check(stats, skill, modifier=mod + ent_pen)
        if level == "Failure":
            return False, "skill"
        if getattr(vehicle, "roll_stall_chance", lambda: False)():
            return False, "stall"
    except Exception:
        return False, "skill"
    return True, None


def vehicle_leg_fail_outcome(vehicle, reason: str):
    """Kill engine, clear drive queue, notify driver / cabin / room; AV in shaft may fall."""
    from evennia.utils import delay

    from world.movement.falling import process_fall

    clear_drive_queue_state(vehicle)
    vehicle.stop_engine()
    driver = getattr(vehicle.db, "driver", None)
    vtype = getattr(vehicle.db, "vehicle_type", None) or "ground"
    loc = vehicle.location

    if reason == "skill":
        if vtype == "aerial":
            dmsg = (
                "|rYou buffet the slipstream — the AV slews, thrusters screaming as you haul back. "
                "Power cuts to idle.|n"
            )
            rmsg = "The aircraft shudders and slews in the air before losing way."
        elif vtype == "motorcycle":
            dmsg = "|rThe front lifts in a bunnyhop; you chop the throttle and skid to a stop.|n"
            rmsg = "The bike hops and slews, rider wrestling it to a stop."
        else:
            dmsg = (
                "|rThe wheels hop — you miss the shift and the drivetrain bites wrong. "
                "You fight it to a stop.|n"
            )
            rmsg = "The vehicle bounces and slews, fighting for grip before it stops."
    else:
        if vtype == "aerial":
            dmsg = "|rThe engines cut out. You're losing way.|n"
            rmsg = "Engine noise cuts out — the craft wallows."
        elif vtype == "motorcycle":
            dmsg = "|rThe engine sputters and dies under you.|n"
            rmsg = "The bike's engine cuts out."
        else:
            dmsg = "|rThe engine sputters and dies.|n"
            rmsg = "The engine sputters and stalls."

    if driver and hasattr(driver, "msg"):
        driver.msg(dmsg)

    interior = getattr(vehicle, "interior", None)
    if interior and hasattr(interior, "msg_contents"):
        interior.msg_contents(
            "|ySomething goes wrong — the vehicle lurches to a halt.|n", exclude=driver
        )

    if loc and hasattr(loc, "msg_contents"):
        try:
            loc.msg_contents(rmsg, exclude=driver)
        except Exception:
            pass

    if vtype == "aerial" and loc and getattr(getattr(loc, "db", None), "is_air", False):
        try:
            vehicle.db.airborne = False
        except Exception:
            pass
        delay(0.5, process_fall, vehicle.id, loc.id)


def vehicle_leg_roll_or_abort(vehicle, dest_room=None) -> bool:
    """For instant (no-delay) drive/fly: run leg roll; on fail apply outcome and return False."""
    ok, kind = _vehicle_leg_roll(vehicle, dest_room=dest_room)
    if ok:
        return True
    vehicle_leg_fail_outcome(vehicle, kind or "skill")
    return False


def staggered_drive_complete(
    vehicle_id: int, dest_id: int, direction: str, session_id: int | None = None
):
    """Called from delayed drive/fly callback after DRIVE_DELAY; may chain further segments."""
    from evennia.utils import delay
    from evennia.utils.search import search_object

    from typeclasses.vehicles import _can_vehicle_enter
    from world.movement.vehicle_queue_flavor import (
        queued_finish_exterior_line,
        queued_finish_interior_line,
        queued_segment_exterior_line,
        queued_segment_interior_line,
    )
    from world.rpg.staggered_movement import DRIVE_DELAY, get_drive_delay

    vres = search_object(f"#{vehicle_id}")
    dres = search_object(f"#{dest_id}")
    if not vres or not dres:
        return
    vehicle, dest = vres[0], dres[0]

    ndb = getattr(vehicle, "ndb", None)
    if ndb is not None and session_id is not None:
        if session_id != int(getattr(ndb, "drive_session_id", 0) or 0):
            return

    vdb = getattr(vehicle, "db", None)
    if vdb is not None and getattr(vdb, "cancel_vehicle_move", False):
        try:
            del vdb.cancel_vehicle_move
        except Exception:
            vdb.cancel_vehicle_move = False
        clear_drive_queue_state(vehicle)
        return

    if not getattr(vehicle.db, "engine_running", False):
        clear_drive_queue_state(vehicle)
        return

    if not vehicle.location or vehicle.location == dest:
        return
    ok, _reason = _can_vehicle_enter(vehicle, dest)
    if not ok:
        clear_drive_queue_state(vehicle)
        return

    roll_ok, fail_kind = _vehicle_leg_roll(vehicle, dest_room=dest)
    if not roll_ok:
        vehicle_leg_fail_outcome(vehicle, fail_kind or "skill")
        return

    q = getattr(ndb, "drive_queue", None) if ndb else None
    remaining_after = len(q) if q else 0
    multi = bool(getattr(ndb, "drive_queue_multi_step", False)) if ndb else False
    vtype = getattr(vehicle.db, "vehicle_type", None) or "ground"
    dir_norm = normalize_direction(direction) or direction
    prev = getattr(ndb, "drive_prev_direction", None) if ndb else None
    vehicle_name = _vehicle_display_name(vehicle)

    cabin_message = None
    exterior_msg = None
    if multi:
        if remaining_after > 0:
            cabin_message = queued_segment_interior_line(vtype, prev, dir_norm)
            exterior_msg = queued_segment_exterior_line(vehicle_name, vtype, prev, dir_norm)
        else:
            cabin_message = queued_finish_interior_line(vtype, dir_norm)
            exterior_msg = queued_finish_exterior_line(vehicle_name, vtype, dir_norm)

    execute_vehicle_move(
        vehicle,
        None,
        dest,
        direction,
        cabin_message=cabin_message,
        exterior_departure_message=exterior_msg,
    )

    if ndb is not None:
        ndb.drive_prev_direction = dir_norm

    q = getattr(ndb, "drive_queue", None) if ndb else None
    if not q or len(q) == 0:
        if ndb is not None:
            try:
                if hasattr(ndb, "drive_queue_multi_step"):
                    delattr(ndb, "drive_queue_multi_step")
            except Exception:
                pass
        clear_drive_chain_active(vehicle)
        return

    try:
        next_dir = q.popleft()
    except (IndexError, TypeError):
        clear_drive_queue_state(vehicle)
        return

    exit_obj = vehicle.get_exit(next_dir)
    if not exit_obj or not exit_obj.destination:
        clear_drive_queue_state(vehicle)
        drv = getattr(vehicle.db, "driver", None)
        if drv and hasattr(drv, "msg"):
            drv.msg(f"You can't continue — no exit {next_dir} from here.")
        return
    next_dest = exit_obj.destination
    ok2, reason2 = _can_vehicle_enter(vehicle, next_dest)
    if not ok2:
        clear_drive_queue_state(vehicle)
        drv = getattr(vehicle.db, "driver", None)
        if drv and hasattr(drv, "msg"):
            drv.msg(f"|r{reason2}|n")
        return

    delay(
        get_drive_delay(vehicle),
        staggered_drive_complete,
        vehicle.id,
        next_dest.id,
        next_dir,
        session_id,
    )
