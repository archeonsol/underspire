"""
Staggered movement: walking and driving take a few seconds before the move completes (for RP).
"""
from evennia.utils import delay
from evennia.utils.search import search_object

# Seconds before the move actually happens (RP pacing)
WALK_DELAY = 3.5
# Crawling is always slower than walking. Two tiers: exhaustion vs leg injury.
CRAWL_DELAY_EXHAUSTED = 8.5   # 0 stamina — slow crawl
CRAWL_DELAY_LEG_TRAUMA = 16.0  # Missing leg or limb unsalvageable — drag/crawl; must exceed walk + exhausted crawl
# Backwards compatibility (older imports)
CRAWL_DELAY = CRAWL_DELAY_EXHAUSTED
DRIVE_DELAY = 2.0


def _staggered_walk_callback(obj_id, dest_id):
    """Called after WALK_DELAY: perform the actual move. Drags grappled victim if mover is grappler.

    Movement can be cancelled between issuing the walk command and the delay elapsing
    by setting `db.cancel_walking` on the character (see `commands.base_cmds.CmdStopWalking`).
    """
    try:
        objs = search_object("#%s" % obj_id)
        dests = search_object("#%s" % dest_id)
        if not objs or not dests:
            return
        obj, dest = objs[0], dests[0]
        if not obj or not dest or not hasattr(obj, "move_to"):
            return
        # If character has requested to stop walking, abort the delayed move.
        db = getattr(obj, "db", None)
        if db is not None and getattr(db, "cancel_walking", False):
            try:
                del db.cancel_walking
            except Exception:
                # Fallback: ensure the flag is false if it couldn't be deleted cleanly.
                db.cancel_walking = False
            return
        obj.move_to(dest)
        # If grappler: bring grappled victim along
        victim = getattr(getattr(obj, "db", None), "grappling", None)
        if victim and hasattr(victim, "move_to"):
            # Pass move_type to trigger forced removal handling in at_pre_move
            victim.move_to(dest, quiet=True, move_type="teleport")
            if dest and hasattr(dest, "contents_get"):
                for v in dest.contents_get(content_type="character"):
                    if v in (obj, victim):
                        continue
                    vname = victim.get_display_name(v) if hasattr(victim, "get_display_name") else victim.name
                    oname = obj.get_display_name(v) if hasattr(obj, "get_display_name") else obj.name
                    v.msg("%s is dragged in by %s." % (vname, oname))
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
