"""
Staggered movement: walking and driving take a few seconds before the move completes (for RP).
"""
from collections import deque

from evennia.utils import delay
from evennia.utils.search import search_object

# Seconds before the move actually happens (RP pacing)
WALK_DELAY = 5.5
# Crawling is always slower than walking. Two tiers: exhaustion vs leg injury.
CRAWL_DELAY_EXHAUSTED = 12.0   # 0 stamina — slow crawl
CRAWL_DELAY_LEG_TRAUMA = 22.0  # Missing leg or limb unsalvageable — drag/crawl; must exceed walk + exhausted crawl
# Backwards compatibility (older imports)
CRAWL_DELAY = CRAWL_DELAY_EXHAUSTED
DRIVE_DELAY = 3.5


def get_drive_delay(vehicle) -> float:
    """Return the effective drive delay for a vehicle, reduced by engine/turbine performance mods.

    Better engines/turbines raise top_speed above the base 100, which proportionally
    shortens the delay. Heavy armor lowers top_speed, lengthening it. Clamped so that
    even the fastest build cannot go below 1.5 s and stock vehicles always use DRIVE_DELAY.
    """
    try:
        from world.vehicle_parts import calculate_vehicle_performance

        perf = calculate_vehicle_performance(vehicle)
        top_speed = perf.get("top_speed", 100) or 100
        scaled = DRIVE_DELAY * (100.0 / top_speed)
        return max(1.5, min(scaled, DRIVE_DELAY))
    except Exception:
        return DRIVE_DELAY


# Pending staggered walk (set in Exit / sneak until move completes or is cancelled).
NDB_STAGGER_WALK_NORM = "_stagger_walk_direction_norm"
NDB_STAGGER_WALK_DISPLAY = "_stagger_walk_direction_display"
NDB_WALK_QUEUE = "_walk_queue"

KNOWN_COMPASS_DIRECTIONS = frozenset(
    {
        "north",
        "south",
        "east",
        "west",
        "northeast",
        "northwest",
        "southeast",
        "southwest",
        "up",
        "down",
    }
)

_DIR_NORMALIZE = {
    "n": "north",
    "north": "north",
    "s": "south",
    "south": "south",
    "e": "east",
    "east": "east",
    "w": "west",
    "west": "west",
    "ne": "northeast",
    "northeast": "northeast",
    "nw": "northwest",
    "northwest": "northwest",
    "se": "southeast",
    "southeast": "southeast",
    "sw": "southwest",
    "southwest": "southwest",
    "u": "up",
    "up": "up",
    "d": "down",
    "down": "down",
}


def normalize_move_direction(direction_str):
    """Canonical direction key for comparing pending vs new staggered moves."""
    if not direction_str:
        return None
    k = direction_str.strip().lower()
    return _DIR_NORMALIZE.get(k, k)


def is_valid_compass_token(token):
    n = normalize_move_direction(token)
    return bool(n and n in KNOWN_COMPASS_DIRECTIONS)


def stagger_walk_direction_conflict(character, new_norm):
    """
    Deprecated for Exit traversal: queuing replaces this. Kept for callers that
    still import the name (e.g. stealth sneak — see stealth_cmds).
    """
    return None


def is_staggered_walk_pending(character):
    ndb = getattr(character, "ndb", None)
    if ndb is None:
        return False
    return getattr(ndb, NDB_STAGGER_WALK_NORM, None) is not None


def _get_walk_queue(character):
    ndb = getattr(character, "ndb", None)
    if ndb is None:
        return None
    return getattr(ndb, NDB_WALK_QUEUE, None)


def append_walk_queue(character, norm):
    """Append a normalized direction to the post-move queue."""
    if not character or not norm:
        return
    ndb = getattr(character, "ndb", None)
    if ndb is None:
        return
    q = getattr(ndb, NDB_WALK_QUEUE, None)
    if q is None:
        q = deque()
        setattr(ndb, NDB_WALK_QUEUE, q)
    q.append(norm)


def extend_walk_queue(character, norms):
    """Append many normalized directions."""
    for n in norms or []:
        append_walk_queue(character, n)


def clear_walk_queue(character):
    ndb = getattr(character, "ndb", None)
    if ndb is None:
        return
    try:
        if hasattr(ndb, NDB_WALK_QUEUE):
            delattr(ndb, NDB_WALK_QUEUE)
    except Exception:
        pass


def set_stagger_walk_pending(character, norm, display):
    ndb = getattr(character, "ndb", None)
    if ndb is None:
        return
    setattr(ndb, NDB_STAGGER_WALK_NORM, norm)
    setattr(ndb, NDB_STAGGER_WALK_DISPLAY, display)


def clear_stagger_walk_pending(character):
    ndb = getattr(character, "ndb", None)
    if ndb is None:
        return
    for name in (NDB_STAGGER_WALK_NORM, NDB_STAGGER_WALK_DISPLAY):
        try:
            if hasattr(ndb, name):
                delattr(ndb, name)
        except Exception:
            pass


def has_walk_queue_or_pending(character):
    """True if a staggered walk is in progress or compass steps are queued (e.g. via |wgo|n)."""
    if not character:
        return False
    if is_staggered_walk_pending(character):
        return True
    q = _get_walk_queue(character)
    return bool(q and len(q) > 0)


def interrupt_staggered_walk(character, notify_msg=None):
    """
    Cancel pending staggered movement and clear the go-queue — same mechanism as |wstop walking|n.
    If notify_msg is set, it is sent only when something was actually interrupted.
    Returns True if there was a pending step or a non-empty queue.
    """
    if not character:
        return False
    active = has_walk_queue_or_pending(character)
    clear_stagger_walk_pending(character)
    clear_walk_queue(character)
    db = getattr(character, "db", None)
    if db is not None:
        db.cancel_walking = True
    if active and notify_msg and hasattr(character, "msg"):
        character.msg(notify_msg)
    return active


def find_exit_in_room(room, direction_norm):
    """Find an exit whose key/aliases normalize to direction_norm."""
    if not room or not direction_norm:
        return None, None
    try:
        from evennia.objects.objects import DefaultExit
    except ImportError:
        return None, None

    for obj in list(room.contents or []):
        if not isinstance(obj, DefaultExit):
            continue
        dest = getattr(obj, "destination", None)
        if not dest:
            continue
        key = (obj.key or "").strip().lower()
        if normalize_move_direction(key) == direction_norm:
            return obj, dest
        al = getattr(obj, "aliases", None)
        if al and hasattr(al, "all"):
            try:
                for a in al.all():
                    if normalize_move_direction(str(a).strip()) == direction_norm:
                        return obj, dest
            except Exception:
                pass
    return None, None


def seed_walk_queue_and_start_first(character, directions_norm_list):
    """
    directions_norm_list: e.g. ['west','west','west']. Schedules first step;
    remaining steps stay on the queue.
    """
    if not directions_norm_list:
        return False, "No directions."
    clear_walk_queue(character)
    first = directions_norm_list[0]
    rest = list(directions_norm_list[1:])
    if rest:
        extend_walk_queue(character, rest)
    ok, err = begin_staggered_walk_in_direction(character, first)
    if not ok:
        clear_walk_queue(character)
        return False, err or "You can't go that way."
    return True, ""


def begin_staggered_walk_in_direction(character, direction_norm):
    """
    Resolve exit from character.location for direction_norm, run precheck, schedule delay.
    Returns (ok, err_msg).
    """
    from typeclasses.exit_traversal import precheck_exit_traversal

    loc = character.location
    if not loc:
        return False, "You have nowhere to go."
    exit_obj, dest = find_exit_in_room(loc, direction_norm)
    if not exit_obj or not dest:
        return False, f"There is no exit {direction_norm}."
    ok, dest2, err, direction_str = precheck_exit_traversal(exit_obj, character, dest)
    if not ok:
        return False, err or "You can't go that way."
    direction = direction_str or (exit_obj.key or "away").strip()
    new_norm = normalize_move_direction(direction)
    begin_staggered_walk_segment(character, dest2, direction, new_norm, exit_obj=exit_obj)
    return True, ""


def _format_move_self_template(text, direction):
    """Optional {direction} in db.move_leave_self / move_arrive_self."""
    if not text:
        return ""
    s = str(text).strip()
    try:
        return s.format(direction=direction)
    except Exception:
        return s


def begin_staggered_walk_segment(traversing_object, destination, direction, new_norm, exit_obj=None):
    """
    Stamina, messages, delay — extracted from Exit.at_traverse (non-sneak).
    Caller must have passed precheck.
    exit_obj: optional Exit; db.move_leave_others / move_leave_self override default stagger lines.
    """
    try:
        from world.rpg.stamina import is_exhausted, spend_stamina, STAMINA_COST_WALK, STAMINA_COST_CRAWL
    except ImportError:
        is_exhausted = lambda _: False
        spend_stamina = lambda _, __: True
        STAMINA_COST_WALK = 1
        STAMINA_COST_CRAWL = 0
    exhausted = is_exhausted(traversing_object)
    try:
        missing = set(getattr(getattr(traversing_object, "db", None), "missing_body_parts", []) or [])
    except Exception:
        missing = set()
    leg_lost = bool(missing.intersection({"left thigh", "right thigh", "left foot", "right foot"}))
    try:
        from world.medical.limb_trauma import is_limb_destroyed

        if is_limb_destroyed(traversing_object, "left_leg") or is_limb_destroyed(traversing_object, "right_leg"):
            leg_lost = True
    except Exception:
        pass
    force_crawl = exhausted or leg_lost

    db = getattr(traversing_object, "db", None)
    if db is not None and hasattr(db, "cancel_walking"):
        try:
            del db.cancel_walking
        except Exception:
            db.cancel_walking = False

    custom_leave_self = None
    custom_leave_others = None
    if exit_obj is not None:
        try:
            custom_leave_self = getattr(exit_obj.db, "move_leave_self", None)
            custom_leave_others = getattr(exit_obj.db, "move_leave_others", None)
        except Exception:
            pass

    if force_crawl:
        spend_stamina(traversing_object, STAMINA_COST_CRAWL)
        delay_secs = CRAWL_DELAY_LEG_TRAUMA if leg_lost else CRAWL_DELAY_EXHAUSTED
        if custom_leave_self and str(custom_leave_self).strip():
            traversing_object.msg(_format_move_self_template(str(custom_leave_self).strip(), direction))
        elif leg_lost:
            traversing_object.msg(f"You drag yourself {direction}, barely moving.")
        else:
            traversing_object.msg(f"You crawl slowly {direction}.")
    else:
        spend_stamina(traversing_object, STAMINA_COST_WALK)
        delay_secs = WALK_DELAY
        if custom_leave_self and str(custom_leave_self).strip():
            traversing_object.msg(_format_move_self_template(str(custom_leave_self).strip(), direction))
        else:
            traversing_object.msg(f"You begin walking {direction}.")

    loc = traversing_object.location
    if loc:
        from world.rp_features import format_exit_move_line_for_viewer, get_move_display_for_viewer

        viewers = [c for c in loc.contents_get(content_type="character") if c is not traversing_object]
        if custom_leave_others and str(custom_leave_others).strip():
            action = str(custom_leave_others).strip()
            for viewer in viewers:
                line = format_exit_move_line_for_viewer(action, traversing_object, viewer)
                if line:
                    viewer.msg(line)
        else:
            for viewer in viewers:
                display = get_move_display_for_viewer(traversing_object, viewer)
                if force_crawl:
                    viewer.msg(
                        f"{display} drags along the ground {direction}."
                        if leg_lost
                        else f"{display} crawls slowly {direction}."
                    )
                else:
                    viewer.msg(f"{display} begins walking {direction}.")

    set_stagger_walk_pending(traversing_object, new_norm, direction)
    cb = _staggered_walk_callback
    if cb:
        delay(delay_secs, cb, traversing_object.id, destination.id)
    else:

        def _fallback_move():
            o, d = traversing_object, destination
            if not o or not d:
                return
            try:
                db = getattr(o, "db", None)
                if db is not None and getattr(db, "cancel_walking", False):
                    try:
                        del db.cancel_walking
                    except Exception:
                        db.cancel_walking = False
                    try:
                        if hasattr(o.ndb, "_stealth_move_sneak"):
                            del o.ndb._stealth_move_sneak
                    except Exception:
                        pass
                    return
                sneak = bool(getattr(o.ndb, "_stealth_move_sneak", False))
                o.move_to(d, quiet=sneak)
                victim = getattr(getattr(o, "db", None), "grappling", None)
                if victim and hasattr(victim, "move_to"):
                    victim.move_to(d, quiet=True, move_type="teleport")
                    if d and hasattr(d, "contents_get"):
                        for v in d.contents_get(content_type="character"):
                            if v in (o, victim):
                                continue
                            vname = victim.get_display_name(v) if hasattr(victim, "get_display_name") else victim.name
                            oname = o.get_display_name(v) if hasattr(o, "get_display_name") else o.name
                            v.msg("%s is dragged in by %s." % (vname, oname))
            finally:
                clear_stagger_walk_pending(o)
                _try_schedule_next_walk_from_queue(o)

        delay(delay_secs, _fallback_move)


def _try_schedule_next_walk_from_queue(character):
    """After a move, run the next queued compass step if any."""
    db = getattr(character, "db", None)
    if db is not None and getattr(db, "cancel_walking", False):
        clear_walk_queue(character)
        return
    q = _get_walk_queue(character)
    if not q or len(q) == 0:
        return
    try:
        next_norm = q.popleft()
    except (IndexError, TypeError):
        return
    if len(q) == 0:
        clear_walk_queue(character)
    ok, err = begin_staggered_walk_in_direction(character, next_norm)
    if not ok:
        if err:
            character.msg(err)
        clear_walk_queue(character)


def _staggered_walk_callback(obj_id, dest_id):
    """Called after WALK_DELAY: perform the actual move. Drags grappled victim if mover is grappler.

    Movement can be cancelled between issuing the walk command and the delay elapsing
    by setting `db.cancel_walking` on the character (see `commands.base_cmds.CmdStopWalking`,
    `interrupt_staggered_walk`, combat initiation in `world.combat.tickers`, damage, or grapple attempts).
    """
    try:
        objs = search_object("#%s" % obj_id)
        dests = search_object("#%s" % dest_id)
        if not objs or not dests:
            return
        obj, dest = objs[0], dests[0]
        if not obj or not dest or not hasattr(obj, "move_to"):
            return
        try:
            # If character has requested to stop walking, abort the delayed move.
            db = getattr(obj, "db", None)
            if db is not None and getattr(db, "cancel_walking", False):
                try:
                    del db.cancel_walking
                except Exception:
                    # Fallback: ensure the flag is false if it couldn't be deleted cleanly.
                    db.cancel_walking = False
                try:
                    if hasattr(obj.ndb, "_stealth_move_sneak"):
                        del obj.ndb._stealth_move_sneak
                except Exception:
                    pass
                clear_walk_queue(obj)
                return
            sneak = bool(getattr(obj.ndb, "_stealth_move_sneak", False))
            obj.move_to(dest, quiet=sneak)
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
        finally:
            clear_stagger_walk_pending(obj)
            _try_schedule_next_walk_from_queue(obj)
    except Exception as e:
        from evennia.utils import logger

        logger.log_trace("staggered_movement._staggered_walk_callback: %s" % e)


def _staggered_drive_callback(vehicle_id, dest_id, direction):
    """Called after DRIVE_DELAY: move the vehicle and show new outside view to everyone inside."""
    try:
        from world.vehicle_movement import staggered_drive_complete

        staggered_drive_complete(vehicle_id, dest_id, direction)
    except Exception as e:
        from evennia.utils import logger

        logger.log_trace("staggered_movement._staggered_drive_callback: %s" % e)
