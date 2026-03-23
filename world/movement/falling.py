"""
Fall mechanics for air rooms and shaft traversal.
"""

from evennia.utils import delay, logger
from evennia.utils.search import search_object

# Defaults; AirRoom may override via db.fall_damage_per_z
FALL_DAMAGE_PER_Z = 5
FALL_DAMAGE_CAP = 200
ABSOLUTE_FLOOR_Z = 0


def process_fall(character_id, air_room_id):
    """
    Called when a character arrives in an air room. Find the next solid
    surface below and move them there, applying fall damage.
    """
    try:
        char_results = search_object(f"#{character_id}")
        room_results = search_object(f"#{air_room_id}")
        if not char_results or not room_results:
            return
        character = char_results[0]
        air_room = room_results[0]
    except Exception as e:
        logger.log_trace(f"process_fall lookup: {e}")
        return

    if character.location != air_room:
        return

    try:
        from typeclasses.vehicles import Vehicle

        if isinstance(character, Vehicle):
            _process_vehicle_fall(character, air_room)
            return
    except Exception as e:
        logger.log_trace(f"process_fall vehicle branch: {e}")

    if hasattr(character, "msg") and getattr(character.db, "flying", False):
        character.msg("|xYou hover in the open shaft.|n")
        return
    if hasattr(character, "msg") and getattr(character.db, "climbing", False):
        character.msg("|xYou cling to the shaft wall.|n")
        return

    dest = None
    z_fallen = 0

    if getattr(air_room.db, "fall_destination", None):
        dest_results = search_object(f"#{air_room.db.fall_destination}")
        if dest_results:
            dest = dest_results[0]
            xz = getattr(air_room, "xyz", None)
            dz = getattr(dest, "xyz", None)
            if xz and dz and len(xz) > 2 and len(dz) > 2:
                z_fallen = abs(int(xz[2]) - int(dz[2]))

    if not dest:
        dest, z_fallen = _find_surface_below(air_room)

    if not dest:
        if hasattr(character, "msg"):
            character.msg("|rYou fall into darkness. There is no bottom.|n")
        if hasattr(character, "db"):
            character.db.current_hp = 0
        try:
            from world.death import make_flatlined

            if hasattr(character, "sessions"):
                make_flatlined(character, attacker=None)
        except Exception:
            pass
        return

    per_z = int(getattr(air_room.db, "fall_damage_per_z", None) or FALL_DAMAGE_PER_Z)
    damage = min(FALL_DAMAGE_CAP, z_fallen * per_z)

    if hasattr(character, "msg"):
        character.msg("|rYou fall.|n")
        if z_fallen <= 2:
            character.msg("|rA short drop. You hit the ground hard.|n")
        elif z_fallen <= 5:
            character.msg("|rThe air rushes past. The impact drives the breath from your lungs.|n")
        else:
            character.msg("|rYou fall for what feels like forever. The impact is catastrophic.|n")

    if hasattr(air_room, "msg_contents") and air_room.contents_get(content_type="character"):
        air_room.msg_contents(
            "{name} plummets downward.",
            exclude=character,
            mapping={"name": character},
        )

    character.move_to(dest, quiet=True)

    if hasattr(dest, "msg_contents"):
        dest.msg_contents(
            "{name} crashes to the ground from above.",
            exclude=character,
            mapping={"name": character},
        )

    if damage > 0 and hasattr(character, "at_damage"):
        if hasattr(character, "msg"):
            character.msg(f"|rThe impact deals {damage} damage.|n")
        try:
            character.at_damage(None, damage, weapon_key="fall")
        except Exception as e:
            logger.log_trace(f"process_fall damage: {e}")

    if getattr(getattr(dest, "db", None), "is_air", False):
        delay(0.5, process_fall, character.id, dest.id)


def _find_surface_below(air_room):
    """
    Search downward for the first non-air room at the same X,Y.
    """
    from evennia.contrib.grid.xyzgrid.xyzroom import XYZRoom

    current_x, current_y, current_z = None, None, None
    try:
        xyz = air_room.xyz
        current_x, current_y, current_z = int(xyz[0]), int(xyz[1]), int(xyz[2])
    except Exception:
        return None, 0

    for check_z in range(current_z - 1, ABSOLUTE_FLOOR_Z - 1, -1):
        try:
            room = XYZRoom.objects.get_xyz(xyz=(current_x, current_y, check_z))
        except (XYZRoom.DoesNotExist, Exception):
            continue
        if room and not getattr(room.db, "is_air", False):
            return room, current_z - check_z

    return None, 0


def _process_vehicle_fall(vehicle, air_room):
    """Aerial vehicle loses lift: fall to next solid surface; damage parts."""
    dest = None
    z_fallen = 0

    if getattr(air_room.db, "fall_destination", None):
        dest_results = search_object(f"#{air_room.db.fall_destination}")
        if dest_results:
            dest = dest_results[0]
            xz = getattr(air_room, "xyz", None)
            dz = getattr(dest, "xyz", None)
            if xz and dz and len(xz) > 2 and len(dz) > 2:
                z_fallen = abs(int(xz[2]) - int(dz[2]))

    if not dest:
        dest, z_fallen = _find_surface_below(air_room)

    if not dest:
        return

    per_z = int(getattr(air_room.db, "fall_damage_per_z", None) or FALL_DAMAGE_PER_Z)
    damage = min(FALL_DAMAGE_CAP, z_fallen * per_z)

    if hasattr(air_room, "msg_contents"):
        air_room.msg_contents(
            f"{getattr(vehicle.db, 'vehicle_name', None) or vehicle.key} drops out of the sky."
        )

    vehicle.move_to(dest, quiet=True)

    if hasattr(dest, "msg_contents"):
        vname = getattr(vehicle.db, "vehicle_name", None) or vehicle.key
        dest.msg_contents(f"{vname} slams into the ground from above.")

    part_damage = max(5, min(40, damage // 4))
    try:
        from world.vehicle_parts import get_part_ids

        pids = get_part_ids(vehicle)[:5]
    except Exception:
        pids = ("engine", "suspension", "wiring")
    for part_id in pids:
        try:
            vehicle.damage_part(part_id, part_damage)
        except Exception:
            pass

    interior = getattr(vehicle, "interior", None)
    if interior:
        interior.msg_contents(
            f"|rIMPACT — the hull screams. Something vital just sheared.|n (|y~{damage} stress|n)"
        )

    if getattr(getattr(dest, "db", None), "is_air", False):
        delay(0.5, process_fall, vehicle.id, dest.id)
