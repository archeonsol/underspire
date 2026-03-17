from __future__ import annotations

from evennia.utils.search import search_object


def combat_display_name(char, viewer):
    if char is None:
        return "Someone"
    if viewer is not None and hasattr(char, "get_display_name"):
        out = char.get_display_name(viewer)
        if out:
            return out
    return getattr(char, "name", None) or getattr(char, "key", None) or "Someone"


def get_object_by_id(dbref):
    """Return the typeclassed Object for this dbref (int). Used by ticker callbacks."""
    if dbref is None:
        return None
    from evennia.utils import logger

    try:
        ref = f"#{int(dbref)}"
        result = search_object(ref)
        if result:
            return result[0]
    except Exception as e:
        logger.log_trace("combat.get_object_by_id(#%s): %s" % (dbref, e))
    return None


def resolve_combat_objects(attacker, defender, kwargs):
    """Resolve attacker/defender from ids (ticker callbacks pass ids as kwargs or as positional ints)."""
    attacker_id = kwargs.get("attacker_id")
    defender_id = kwargs.get("defender_id")
    if isinstance(attacker, int):
        attacker_id = attacker
        attacker = None
    if isinstance(defender, int):
        defender_id = defender
        defender = None
    if attacker_id is None and defender_id is None:
        return attacker, defender
    if attacker is None and attacker_id is not None:
        attacker = get_object_by_id(attacker_id)
    if defender is None and defender_id is not None:
        defender = get_object_by_id(defender_id)
    return attacker, defender


def get_combat_target(caller):
    return getattr(caller.db, "combat_target", None)


def set_combat_target(caller, target):
    caller.db.combat_target = target


def is_being_attacked(character, location=None):
    if not character or not hasattr(character, "location"):
        return False
    loc = location or getattr(character, "location", None)
    if not loc or not hasattr(loc, "contents_get"):
        return False
    for other in loc.contents_get(content_type="character"):
        if other is character:
            continue
        if getattr(other.db, "combat_target", None) == character:
            return True
    return False


def is_in_combat(character):
    return get_combat_target(character) is not None or is_being_attacked(character)

