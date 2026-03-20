from __future__ import annotations

from evennia.utils.search import search_object

_ACTIVE_ATTACKERS = {}
_ACTIVE_DEFENDERS = {}

# Combat log readability palette:
# - base line tint distinguishes combat traffic from normal room text
# - attacker/defender names are role-colored for quick parsing
COMBAT_BASE_COLOR = "|b"
COMBAT_ATTACKER_COLOR = "|R"
COMBAT_DEFENDER_COLOR = "|Y"


def combat_display_name(char, viewer):
    if char is None:
        return "Someone"
    if viewer is not None and hasattr(char, "get_display_name"):
        out = char.get_display_name(viewer)
        if out:
            return out
    return getattr(char, "name", None) or getattr(char, "key", None) or "Someone"


def combat_role_name(char, viewer, role="neutral"):
    name = combat_display_name(char, viewer)
    if role == "attacker":
        return f"{COMBAT_ATTACKER_COLOR}{name}|n"
    if role == "defender":
        return f"{COMBAT_DEFENDER_COLOR}{name}|n"
    return name


def combat_text(line):
    line = str(line or "")
    if not line:
        return line
    # Re-apply combat tint after any inline reset so mixed-color templates
    # still keep a consistent combat-channel base color.
    tinted = line.replace("|n", f"|n{COMBAT_BASE_COLOR}")
    return f"{COMBAT_BASE_COLOR}{tinted}|n"


def combat_msg(viewer, line):
    if viewer and hasattr(viewer, "msg"):
        viewer.msg(combat_text(line))


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
    _unregister_combat_pair(caller)
    if target is not None:
        _register_combat_pair(caller, target)


def _register_combat_pair(attacker, defender):
    if not attacker or not defender:
        return
    _ACTIVE_ATTACKERS[attacker.id] = defender.id
    defenders = _ACTIVE_DEFENDERS.get(defender.id)
    if defenders is None:
        defenders = set()
        _ACTIVE_DEFENDERS[defender.id] = defenders
    defenders.add(attacker.id)


def _unregister_combat_pair(attacker):
    if not attacker:
        return
    attacker_id = attacker.id
    old_defender_id = _ACTIVE_ATTACKERS.pop(attacker_id, None)
    if old_defender_id is None:
        return
    defenders = _ACTIVE_DEFENDERS.get(old_defender_id)
    if not defenders:
        return
    defenders.discard(attacker_id)
    if not defenders:
        _ACTIVE_DEFENDERS.pop(old_defender_id, None)


def remove_engagement(attacker):
    _unregister_combat_pair(attacker)


def unregister_as_attacker(attacker):
    """Drop this character from the active-attacker index only; does not clear db.combat_target."""
    _unregister_combat_pair(attacker)


def is_attacking_target(attacker, defender):
    """True if attacker is registered as actively engaging defender (outgoing attack schedule)."""
    if not attacker or not defender:
        return False
    return _ACTIVE_ATTACKERS.get(attacker.id) == defender.id


def add_engagement(attacker, defender):
    _register_combat_pair(attacker, defender)


def get_attackers_for(character):
    if not character:
        return set()
    return set(_ACTIVE_DEFENDERS.get(character.id, set()))


def clear_engagement_index():
    _ACTIVE_ATTACKERS.clear()
    _ACTIVE_DEFENDERS.clear()


def has_reciprocal_combat(attacker, defender):
    if not attacker or not defender:
        return False
    return get_combat_target(attacker) == defender and get_combat_target(defender) == attacker


def is_being_attacked(character, location=None):
    if not character or not hasattr(character, "location"):
        return False
    loc = location or getattr(character, "location", None)
    if not loc or not hasattr(loc, "contents_get"):
        return False
    attackers = get_attackers_for(character)
    if attackers:
        return True
    for other in loc.contents_get(content_type="character"):
        if other is character:
            continue
        if getattr(other.db, "combat_target", None) == character:
            _register_combat_pair(other, character)
            return True
    return False


def is_in_combat(character):
    return get_combat_target(character) is not None or is_being_attacked(character)

