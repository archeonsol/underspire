"""
Staggered movement: walking and driving take a few seconds before the move completes (for RP).
"""
from evennia.utils import delay
from evennia.utils.search import search_object

# Seconds before the move actually happens
WALK_DELAY = 3.5
CRAWL_DELAY = 7.0   # When exhausted (0 stamina), you crawl slowly
DRIVE_DELAY = 2.0


def _staggered_walk_callback(obj_id, dest_id):
    """Called after WALK_DELAY: perform the actual move. Drags grappled victim if mover is grappler."""
    try:
        objs = search_object("#%s" % obj_id)
        dests = search_object("#%s" % dest_id)
        if not objs or not dests:
            return
        obj, dest = objs[0], dests[0]
        if not obj or not dest or not hasattr(obj, "move_to"):
            return
        obj.move_to(dest)
        # If grappler: bring grappled victim along
        victim = getattr(getattr(obj, "db", None), "grappling", None)
        if victim and hasattr(victim, "move_to"):
            victim.move_to(dest, quiet=True)
            dest.msg_contents(
                "%s is dragged in by %s." % (victim.name, obj.name),
                exclude=(obj, victim),
            )
    except Exception as e:
        from evennia.utils import logger
        logger.log_trace("staggered_movement._staggered_walk_callback: %s" % e)


def _staggered_drive_callback(vehicle_id, dest_id, direction):
    """Called after DRIVE_DELAY: move the vehicle and show new outside view to everyone inside."""
    try:
        vehicles = search_object("#%s" % vehicle_id)
        dests = search_object("#%s" % dest_id)
        if not vehicles or not dests:
            return
        vehicle, dest = vehicles[0], dests[0]
        if not vehicle or not dest:
            return
        old_room = vehicle.location
        vehicle.move_to(dest, quiet=True)
        # Announce to old and new room
        if old_room:
            old_room.msg_contents(f"{vehicle.key} drives {direction}.")
        dest.msg_contents(f"{vehicle.key} arrives from {direction}.")
        # Send updated "outside" view to everyone inside the vehicle
        interior = getattr(vehicle, "interior", None)
        if interior and hasattr(interior, "get_outside_block"):
            for char in (interior.contents or []):
                if not char:
                    continue
                if hasattr(char, "msg") and hasattr(char, "account") and char.account:
                    block = interior.get_outside_block(char)
                    if block:
                        char.msg("\n|wYou arrive.|n\n" + block)
    except Exception as e:
        from evennia.utils import logger
        logger.log_trace("staggered_movement._staggered_drive_callback: %s" % e)
