"""AV vertical movement in aerial-tagged XYZ cells."""

from evennia.contrib.grid.xyzgrid.xyzroom import XYZRoom

from world.vehicle_movement import _after_vehicle_move_hook, vehicle_leg_roll_or_abort


def _find_vertical_destination(vehicle_room, direction):
    """Find the room above or below for AV flight."""
    if not vehicle_room:
        return None
    try:
        xyz = vehicle_room.xyz
        x, y, z = int(xyz[0]), int(xyz[1]), int(xyz[2])
    except Exception:
        return None

    target_z = z + 1 if direction == "up" else z - 1

    try:
        room = XYZRoom.objects.get_xyz(xyz=(x, y, target_z))
    except Exception:
        return None

    if room and room.tags.has("aerial", category="vehicle_access"):
        return room
    return None


def fly_vertical(vehicle, pilot, direction):
    """
    Move an AV up or down one Z level.
    Returns (success: bool, message: str).
    """
    direction = (direction or "").strip().lower()
    if direction not in ("up", "down"):
        return False, "Invalid vertical direction."

    current_room = vehicle.location
    dest = _find_vertical_destination(current_room, direction)
    if not dest:
        return False, f"Nothing to fly to {direction}. You're at the edge of the shaft."

    if not dest.tags.has("aerial", category="vehicle_access"):
        return False, "That space isn't rated for flight."

    if not vehicle_leg_roll_or_abort(vehicle, dest_room=dest):
        return False, ""

    old_room = vehicle.location
    vehicle_name = getattr(vehicle.db, "vehicle_name", None) or vehicle.key
    dir_word = "ascends" if direction == "up" else "descends"

    vehicle.move_to(dest, quiet=True)

    if old_room:
        old_room.msg_contents(f"{vehicle_name} {dir_word}.")
    dest.msg_contents(f"{vehicle_name} arrives from {'below' if direction == 'up' else 'above'}.")

    interior = getattr(vehicle, "interior", None)
    if interior:
        try:
            z_new = dest.xyz[2]
        except Exception:
            z_new = "?"
        interior.msg_contents(f"|xThe AV {dir_word}. Altitude: Z-{z_new}.|n")

    try:
        vehicle.db.altitude_z = dest.xyz[2]
    except Exception:
        vehicle.db.altitude_z = None

    _after_vehicle_move_hook(vehicle, pilot, dest, old_room, direction)

    return True, ""
