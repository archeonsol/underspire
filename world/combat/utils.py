from __future__ import annotations

from evennia.utils.search import search_object

from world.theme_colors import COMBAT_COLORS as CC

_ACTIVE_ATTACKERS = {}
_ACTIVE_DEFENDERS = {}

# Combat log readability palette:
# - base line tint distinguishes combat traffic from normal room text
# - attacker/defender names are role-colored for quick parsing
COMBAT_BASE_COLOR = "|b"
COMBAT_ATTACKER_COLOR = CC["crit"]
COMBAT_DEFENDER_COLOR = "|Y"


def combat_display_name(char, viewer):
    """
    Viewer-relative combat names: vehicle label, then rp_features (mask, recog, sdesc) for others.
    When viewer is the character, returns object key (first-person lines use "You" in templates).
    """
    if char is None:
        return "Someone"
    try:
        from typeclasses.vehicles import Vehicle, vehicle_label as _vehicle_label

        if isinstance(char, Vehicle):
            return _vehicle_label(char)
    except ImportError:
        pass
    if viewer is None:
        return getattr(char, "name", None) or getattr(char, "key", None) or "Someone"
    if viewer != char:
        try:
            from world.rp_features import get_display_name_for_viewer

            out = get_display_name_for_viewer(char, viewer)
            if out:
                return out
        except Exception:
            pass
        if hasattr(char, "get_display_name"):
            out = char.get_display_name(viewer)
            if out:
                return out
        return getattr(char, "name", None) or getattr(char, "key", None) or "Someone"
    return getattr(char, "key", None) or getattr(char, "name", None) or "Someone"


def combat_role_name(char, viewer, role="neutral"):
    name = combat_display_name(char, viewer)
    if role == "attacker":
        return f"{COMBAT_ATTACKER_COLOR}{name}|n"
    if role == "defender":
        return f"{COMBAT_DEFENDER_COLOR}{name}|n"
    return name


def combat_role_name_attacker_party(attacker, viewer, role="attacker"):
    """
    Third-party combat lines: when this character is fighting with a vehicle-mounted weapon,
    show the vehicle (hull) as the aggressor, not the driver's sdesc.
    """
    if not attacker:
        return combat_role_name(attacker, viewer, role=role)
    try:
        from world.combat.vehicle_combat import get_attacker_vehicle_weapon_context

        ctx = get_attacker_vehicle_weapon_context(attacker)
        if ctx:
            return combat_role_name(ctx[0], viewer, role=role)
    except ImportError:
        pass
    return combat_role_name(attacker, viewer, role=role)


def relay_combat_room_msg(loc, attacker, defender, room_tpl, **extra_names):
    """
    After a per-viewer combat observer loop, relay the same message to occupants of any enclosed
    vehicles parked in `loc`.  Names are resolved against `None` (neutral third-person) so cabin
    crew see the same sdesc/label as an anonymous bystander would.

    `room_tpl` should be a format string with at least {attacker} and {defender} slots.
    Pass additional keyword args for any extra slots (e.g. effective_defender=, loc=).
    """
    if not loc:
        return
    try:
        from typeclasses.vehicles import relay_to_parked_vehicle_interiors
    except ImportError:
        return
    atk_n = combat_role_name_attacker_party(attacker, None, role="attacker")
    def_n = combat_role_name(defender, None, role="defender")
    fmt_kwargs = {"attacker": atk_n, "defender": def_n}
    fmt_kwargs.update(extra_names)
    try:
        msg = room_tpl.format(**fmt_kwargs)
    except (KeyError, IndexError):
        return
    relay_to_parked_vehicle_interiors(loc, combat_text(msg))


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


def get_combat_external_location(caller):
    """
    Room used for resolving attack targets (line of sight).
    When the caller is inside an enclosed vehicle cabin, targets are in the vehicle's exterior room.
    """
    if not caller:
        return None
    v = getattr(caller.db, "in_vehicle", None)
    if v and getattr(v, "location", None):
        return v.location
    return caller.location


def is_vehicle_interior_room(room):
    """True when this room is an enclosed vehicle cabin (not the outside street)."""
    if not room or not getattr(room, "db", None):
        return False
    return bool(getattr(room.db, "vehicle", None))


def melee_brawl_blocked_in_vehicle_cabin(caller, target):
    """
    No fist-fighting another person inside the same enclosed vehicle cabin.
    Attack from the cabin toward targets in the outside room (field of fire) is allowed.
    Returns a user-facing message if blocked, otherwise None.
    """
    if not caller or not target:
        return None
    cloc = getattr(caller, "location", None)
    if not is_vehicle_interior_room(cloc):
        return None
    try:
        from typeclasses.characters import Character
    except ImportError:
        return None
    if not isinstance(target, Character):
        return None
    if getattr(target, "location", None) != cloc:
        return None
    return (
        "You can't brawl with someone inside the cabin. "
        "Use |wattack <target>|n on someone outside, or the vehicle's mounted weapons."
    )


def melee_target_blocked_enclosed_cabin(caller, target, exterior_room):
    """
    Foot combat from the outside field-of-fire cannot target someone who only exists
    inside an enclosed vehicle cabin. Motorcycle riders are in the room and are allowed.
    Returns a user-facing message if blocked, otherwise None.
    """
    if not caller or not target or not exterior_room:
        return None
    try:
        from typeclasses.characters import Character
    except ImportError:
        return None
    if not isinstance(target, Character):
        return None
    iv = getattr(target.db, "in_vehicle", None)
    if not iv:
        return None
    try:
        from typeclasses.vehicles import Vehicle, vehicle_label as _vehicle_label
    except ImportError:
        return None
    if not isinstance(iv, Vehicle) or getattr(iv.db, "vehicle_destroyed", False):
        return None
    if getattr(iv.db, "vehicle_type", None) == "motorcycle":
        return None
    if not getattr(iv.db, "has_interior", True):
        return None
    if getattr(target, "location", None) == exterior_room:
        return None
    lab = _vehicle_label(iv)
    return (
        f"You can't reach them — they're inside {lab}. "
        f"Attack the vehicle: |wattack {lab}|n (or that vehicle's name)."
    )


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

