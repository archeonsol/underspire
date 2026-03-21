"""
Door pairing, bioscan checks, and auto-close for faction-secured exits.
Used by typeclasses.exits.Exit and commands.door_cmds.
"""

from evennia.utils import delay
from evennia.utils.search import search_object

from world.rpg.factions import is_faction_member
from world.rpg.factions.membership import get_member_rank


def _resolve_door_pair_exit(exit_obj):
    """Return the paired exit object from exit.db.door_pair (dbref int or #id)."""
    ref = getattr(getattr(exit_obj, "db", None), "door_pair", None)
    if ref is None:
        return None
    if isinstance(ref, int):
        rid = ref
    else:
        s = str(ref).strip()
        if s.startswith("#"):
            s = s[1:]
        try:
            rid = int(s)
        except ValueError:
            return None
    res = search_object(f"#{rid}")
    return res[0] if res else None


def sync_door_pair(exit_obj, open_state):
    """Sync the paired exit to the same open/closed state."""
    pair = _resolve_door_pair_exit(exit_obj)
    if pair and getattr(pair.db, "door", None):
        pair.db.door_open = bool(open_state)


def auto_close_door(exit_id):
    """Callback: close door after timer. exit_id is database id."""
    res = search_object(f"#{exit_id}")
    if not res:
        return
    exit_obj = res[0]
    if not getattr(exit_obj.db, "door_open", False):
        return
    exit_obj.db.door_open = False
    sync_door_pair(exit_obj, False)
    door_name = getattr(exit_obj.db, "door_name", None) or "door"
    loc = exit_obj.location
    if loc and hasattr(loc, "msg_contents"):
        loc.msg_contents(f"The {door_name} closes automatically.")


def schedule_door_auto_close(exit_obj, seconds):
    """Schedule auto-close after seconds (0 = no schedule)."""
    sec = int(seconds or 0)
    if sec <= 0:
        return
    delay(sec, auto_close_door, exit_obj.id)


def schedule_bioscan_auto_close(exit_obj):
    sec = int(getattr(exit_obj.db, "bioscan_auto_close", None) or 8)
    schedule_door_auto_close(exit_obj, sec)


def has_key(character, key_tag):
    """True if character carries a key item with tag key_tag (category key)."""
    if not key_tag or not character:
        return False
    for obj in character.contents:
        if obj.tags.has(key_tag, category="key"):
            return True
    return False


def staff_bypass(character):
    try:
        acc = getattr(character, "account", None)
        if acc and (acc.permissions.check("Builder") or acc.permissions.check("Admin")):
            return True
    except Exception:
        pass
    return False


def run_bioscan(character, exit_obj):
    """
    Run bioscan verification. Returns (passed: bool, message: str).
    """
    if staff_bypass(character):
        return True, "Staff override accepted."

    scan_type = getattr(exit_obj.db, "bioscan_type", None) or "faction"

    if scan_type == "faction":
        faction_key = getattr(exit_obj.db, "bioscan_faction", None)
        if not faction_key:
            return False, "Bioscan misconfigured. No faction set."
        if is_faction_member(character, faction_key):
            return True, "Faction membership confirmed."
        return False, "Faction membership not detected."

    if scan_type == "rank":
        faction_key = getattr(exit_obj.db, "bioscan_faction", None)
        min_rank = int(getattr(exit_obj.db, "bioscan_rank", None) or 1)
        if not faction_key:
            return False, "Bioscan misconfigured."
        rank = get_member_rank(character, faction_key)
        if rank >= min_rank:
            return True, "Rank clearance confirmed."
        if rank > 0:
            return False, "Insufficient rank clearance."
        return False, "Faction membership not detected."

    if scan_type == "whitelist":
        whitelist = getattr(exit_obj.db, "bioscan_whitelist", None) or []
        cid = getattr(character, "id", None)
        dbref = getattr(character, "dbref", None)
        if cid in whitelist or dbref in whitelist:
            return True, "Identity confirmed."
        return False, "Identity not on access list."

    if scan_type == "custom":
        return False, "Custom bioscan not implemented."

    return False, "Unknown bioscan type."
