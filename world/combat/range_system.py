"""
Combat range system: positional distance between combatants.
"""

from __future__ import annotations

from collections.abc import Mapping

from world.combat.cover import (
    character_in_cover,
    force_leave_cover,
    get_cover_status_text,
    is_pinned_by_suppression,
)

RANGE_CLINCH = -1
RANGE_VERY_CLOSE = 0
RANGE_CLOSE = 1
RANGE_EXTENDED = 2
RANGE_RANGED = 3
RANGE_LONG = 4
RANGE_EXTREME = 5

RANGE_MIN = RANGE_CLINCH
RANGE_MAX = RANGE_EXTREME
DEFAULT_STARTING_RANGE = RANGE_EXTENDED

RANGE_LABELS = {
    RANGE_CLINCH: "clinch",
    RANGE_VERY_CLOSE: "very close",
    RANGE_CLOSE: "close",
    RANGE_EXTENDED: "extended",
    RANGE_RANGED: "ranged",
    RANGE_LONG: "long",
    RANGE_EXTREME: "extreme",
}

RANGE_DESCRIPTIONS = {
    RANGE_CLINCH: "grapple-locked",
    RANGE_VERY_CLOSE: "chest-to-chest pressure",
    RANGE_CLOSE: "within arm's reach",
    RANGE_EXTENDED: "a step outside immediate reach",
    RANGE_RANGED: "at practical firearm distance",
    RANGE_LONG: "at long distance",
    RANGE_EXTREME: "at extreme distance",
}

WEAPON_RANGE_PENALTY = {
    # Pattern per class: one optimal (0), one-step neighbors debuffed, two-step neighbors unusable.
    # Clinch is reserved for grapple state and is unusable for normal attacks.
    "fists": {
        RANGE_CLINCH: None,
        RANGE_VERY_CLOSE: 0,
        RANGE_CLOSE: -5,
        RANGE_EXTENDED: None,
        RANGE_RANGED: None,
        RANGE_LONG: None,
        RANGE_EXTREME: None,
    },
    "knife": {
        RANGE_CLINCH: None,
        RANGE_VERY_CLOSE: -4,
        RANGE_CLOSE: 0,
        RANGE_EXTENDED: -10,
        RANGE_RANGED: None,
        RANGE_LONG: None,
        RANGE_EXTREME: None,
    },
    "long_blade": {
        RANGE_CLINCH: None,
        RANGE_VERY_CLOSE: None,
        RANGE_CLOSE: -8,
        RANGE_EXTENDED: 0,
        RANGE_RANGED: -8,
        RANGE_LONG: None,
        RANGE_EXTREME: None,
    },
    "blunt": {
        RANGE_CLINCH: None,
        RANGE_VERY_CLOSE: None,
        RANGE_CLOSE: -6,
        RANGE_EXTENDED: 0,
        RANGE_RANGED: -10,
        RANGE_LONG: None,
        RANGE_EXTREME: None,
    },
    "sidearm": {
        RANGE_CLINCH: None,
        RANGE_VERY_CLOSE: None,
        RANGE_CLOSE: None,
        RANGE_EXTENDED: -8,
        RANGE_RANGED: 0,
        RANGE_LONG: -8,
        RANGE_EXTREME: None,
    },
    "longarm": {
        RANGE_CLINCH: None,
        RANGE_VERY_CLOSE: None,
        RANGE_CLOSE: None,
        RANGE_EXTENDED: None,
        RANGE_RANGED: -5,
        RANGE_LONG: 0,
        RANGE_EXTREME: -5,
    },
    "automatic": {
        RANGE_CLINCH: None,
        RANGE_VERY_CLOSE: None,
        RANGE_CLOSE: None,
        RANGE_EXTENDED: -8,
        RANGE_RANGED: 0,
        RANGE_LONG: -6,
        RANGE_EXTREME: None,
    },
    "claws": {
        RANGE_CLINCH: None,
        RANGE_VERY_CLOSE: -4,
        RANGE_CLOSE: 0,
        RANGE_EXTENDED: -10,
        RANGE_RANGED: None,
        RANGE_LONG: None,
        RANGE_EXTREME: None,
    },
    "bite": {
        RANGE_CLINCH: None,
        RANGE_VERY_CLOSE: -6,
        RANGE_CLOSE: 0,
        RANGE_EXTENDED: -12,
        RANGE_RANGED: None,
        RANGE_LONG: None,
        RANGE_EXTREME: None,
    },
    "saw": {
        RANGE_CLINCH: None,
        RANGE_VERY_CLOSE: -4,
        RANGE_CLOSE: 0,
        RANGE_EXTENDED: -8,
        RANGE_RANGED: None,
        RANGE_LONG: None,
        RANGE_EXTREME: None,
    },
    "gouge": {
        RANGE_CLINCH: None,
        RANGE_VERY_CLOSE: -4,
        RANGE_CLOSE: 0,
        RANGE_EXTENDED: -10,
        RANGE_RANGED: None,
        RANGE_LONG: None,
        RANGE_EXTREME: None,
    },
    "acid_spit": {
        RANGE_CLINCH: None,
        RANGE_VERY_CLOSE: None,
        RANGE_CLOSE: None,
        RANGE_EXTENDED: -6,
        RANGE_RANGED: 0,
        RANGE_LONG: -8,
        RANGE_EXTREME: None,
    },
    "frost_breath": {
        RANGE_CLINCH: None,
        RANGE_VERY_CLOSE: None,
        RANGE_CLOSE: -6,
        RANGE_EXTENDED: 0,
        RANGE_RANGED: -8,
        RANGE_LONG: None,
        RANGE_EXTREME: None,
    },
    "shock_lash": {
        RANGE_CLINCH: None,
        RANGE_VERY_CLOSE: None,
        RANGE_CLOSE: -4,
        RANGE_EXTENDED: 0,
        RANGE_RANGED: -8,
        RANGE_LONG: None,
        RANGE_EXTREME: None,
    },
    "void_rend": {
        RANGE_CLINCH: None,
        RANGE_VERY_CLOSE: None,
        RANGE_CLOSE: -4,
        RANGE_EXTENDED: 0,
        RANGE_RANGED: -6,
        RANGE_LONG: None,
        RANGE_EXTREME: None,
    },
    "void_pulse": {
        RANGE_CLINCH: None,
        RANGE_VERY_CLOSE: None,
        RANGE_CLOSE: None,
        RANGE_EXTENDED: -6,
        RANGE_RANGED: 0,
        RANGE_LONG: -8,
        RANGE_EXTREME: None,
    },
}

_DEFAULT_RANGE_PENALTY = {
    RANGE_CLINCH: None,
    RANGE_VERY_CLOSE: None,
    RANGE_CLOSE: -8,
    RANGE_EXTENDED: 0,
    RANGE_RANGED: -8,
    RANGE_LONG: None,
    RANGE_EXTREME: None,
}

STAMINA_COST_ADVANCE = 6
STAMINA_COST_RETREAT = 4
FOOTWORK_SKILL = "footwork"
FOOTWORK_STATS = ["agility"]
RETREAT_BONUS = 4
RANGE_COMFORT_BONUS = 5


def _display_name(char, viewer):
    if char is None:
        return "Someone"
    if viewer is not None and hasattr(char, "get_display_name"):
        out = char.get_display_name(viewer)
        if out:
            return out
    return getattr(char, "name", None) or "Someone"


def _normalized_combat_ranges_map(raw):
    """
    opponent dbref (as str) -> range band (int). Accepts dict-like attrs from the DB
    where keys may be int, str, or '#12' style.
    """
    if raw is None or not isinstance(raw, Mapping):
        return {}
    out = {}
    for k, v in raw.items():
        key = str(k).strip().lstrip("#")
        try:
            oid = int(float(key))
        except (TypeError, ValueError):
            continue
        sk = str(oid)
        try:
            out[sk] = int(v)
        except (TypeError, ValueError):
            try:
                out[sk] = int(float(v))
            except (TypeError, ValueError):
                continue
    return out


def get_combat_range(a, b):
    if not a or not b:
        return DEFAULT_STARTING_RANGE
    aid = getattr(a, "id", None)
    bid = getattr(b, "id", None)
    if aid is None or bid is None:
        return DEFAULT_STARTING_RANGE
    for x, other in ((a, b), (b, a)):
        oid = getattr(other, "id", None)
        if oid is None or not getattr(x, "db", None):
            continue
        mp = _normalized_combat_ranges_map(getattr(x.db, "combat_ranges", None))
        sk = str(oid)
        if sk in mp:
            return mp[sk]
    return DEFAULT_STARTING_RANGE


def set_combat_range(a, b, value):
    value = max(RANGE_MIN, min(RANGE_MAX, int(value)))
    if not a or not b:
        return
    for x, other in ((a, b), (b, a)):
        if not getattr(x, "db", None):
            continue
        oid = getattr(other, "id", None)
        if oid is None:
            continue
        mp = _normalized_combat_ranges_map(getattr(x.db, "combat_ranges", None))
        mp[str(oid)] = value
        x.db.combat_ranges = dict(mp)


def clear_combat_range(a, b):
    for x, y in ((a, b), (b, a)):
        if not x or not getattr(x, "db", None) or not y:
            continue
        oid = getattr(y, "id", None)
        if oid is None:
            continue
        mp = _normalized_combat_ranges_map(getattr(x.db, "combat_ranges", None))
        mp.pop(str(oid), None)
        x.db.combat_ranges = dict(mp)


def get_initial_range(attacker_weapon_key):
    profile = WEAPON_RANGE_PENALTY.get(attacker_weapon_key, _DEFAULT_RANGE_PENALTY)
    # Opening range favors the initial attacker: choose the best (lowest penalty)
    # legal range for the weapon they're currently using. On ties, keep distance
    # (extreme > long > ranged > extended > close > very_close > clinch)
    # as the opener's advantage on tied penalties.
    order = (
        RANGE_EXTREME,
        RANGE_LONG,
        RANGE_RANGED,
        RANGE_EXTENDED,
        RANGE_CLOSE,
        RANGE_VERY_CLOSE,
        RANGE_CLINCH,
    )
    best_range = DEFAULT_STARTING_RANGE
    best_penalty = None
    for r in order:
        pen = profile.get(r)
        if pen is None:
            continue
        pen_i = int(pen)
        if best_penalty is None or pen_i > best_penalty:
            best_penalty = pen_i
            best_range = r
    return best_range


def get_weapon_range_penalty(weapon_key, current_range):
    profile = WEAPON_RANGE_PENALTY.get(weapon_key, _DEFAULT_RANGE_PENALTY)
    return profile.get(current_range, None)


def can_attack_at_range(weapon_key, current_range):
    return get_weapon_range_penalty(weapon_key, current_range) is not None


def is_weapon_optimal(weapon_key, current_range):
    pen = get_weapon_range_penalty(weapon_key, current_range)
    return pen is not None and pen == 0


def get_weapon_optimal_ranges(weapon_key):
    profile = WEAPON_RANGE_PENALTY.get(weapon_key, _DEFAULT_RANGE_PENALTY)
    return [r for r in sorted(profile) if profile.get(r) == 0]


def get_range_status_text(weapon_key, current_range):
    pen = get_weapon_range_penalty(weapon_key, current_range)
    if pen is None:
        return "|rblocked|n"
    if pen == 0:
        return "|goptimal|n"
    return "|yawkward|n"


def _footwork_roll(character, modifier=0):
    if not hasattr(character, "roll_check"):
        return "Failure", 0
    return character.roll_check(FOOTWORK_STATS, FOOTWORK_SKILL, modifier=modifier)


def _comfort_bonus(weapon_key, current_range):
    return RANGE_COMFORT_BONUS if is_weapon_optimal(weapon_key, current_range) else 0


def _get_character_weapon_key(character):
    wielded_obj = getattr(character.db, "wielded_obj", None)
    if wielded_obj and getattr(wielded_obj, "location", None) == character:
        return getattr(character.db, "wielded", "fists") or "fists"
    from typeclasses.cyberware_catalog import RetractableClaws
    for cw in (getattr(character.db, "cyberware", None) or []):
        if isinstance(cw, RetractableClaws) and bool(getattr(cw.db, "claws_deployed", False)) and not bool(
            getattr(cw.db, "malfunctioning", False)
        ):
            return "claws"
    return "fists"


def attempt_advance(mover, opponent):
    if not mover or not opponent:
        return False, 0, "You cannot do that.", "", None
    current = get_combat_range(mover, opponent)
    if is_pinned_by_suppression(mover):
        return False, current, "|rYou're pinned by suppressing fire. You can't move.|n", "", None
    if current <= RANGE_VERY_CLOSE:
        return False, current, "You can't close any further without committing to a grapple.", "", None
    try:
        from world.rpg.stamina import is_exhausted, spend_stamina
        if is_exhausted(mover):
            return False, current, "You're too exhausted to move.", "", None
        spend_stamina(mover, STAMINA_COST_ADVANCE)
    except ImportError:
        pass
    opp_weapon = _get_character_weapon_key(opponent)
    opp_bonus = _comfort_bonus(opp_weapon, current)
    _, mover_val = _footwork_roll(mover, modifier=0)
    _, opp_val = _footwork_roll(opponent, modifier=opp_bonus + RETREAT_BONUS)
    target_range = current - 1
    range_label = RANGE_LABELS.get(target_range, "closer")
    current_label = RANGE_LABELS.get(current, "current distance")
    if mover_val > opp_val:
        set_combat_range(mover, opponent, target_range)
        if target_range <= RANGE_CLINCH and character_in_cover(mover):
            force_leave_cover(mover, reason_msg="|yYou leave cover as you close to clinch range.|n")

        def msg_room(viewer):
            return f"{_display_name(mover, viewer)} closes distance on {_display_name(opponent, viewer)}. They're at {range_label} range now."

        return True, target_range, f"|gYou push forward to {range_label} range.|n", f"|y{{mover}} closes on you. {range_label.capitalize()} range.|n", msg_room

    def msg_room(viewer):
        return f"{_display_name(mover, viewer)} tries to close on {_display_name(opponent, viewer)} but {_display_name(opponent, viewer)} keeps the distance."

    return False, current, f"|rYou try to close but they keep you at {current_label} range.|n", f"|g{{mover}} tries to close on you. You keep them at bay.|n", msg_room


def attempt_retreat(mover, opponent):
    if not mover or not opponent:
        return False, 0, "You cannot do that.", "", None
    current = get_combat_range(mover, opponent)
    if is_pinned_by_suppression(mover):
        return False, current, "|rYou're pinned by suppressing fire. You can't move.|n", "", None
    if current >= RANGE_MAX:
        return False, current, "You're already as far as you can get without fleeing.", "", None
    try:
        from world.rpg.stamina import is_exhausted, spend_stamina
        if is_exhausted(mover):
            return False, current, "You're too exhausted to move.", "", None
        spend_stamina(mover, STAMINA_COST_RETREAT)
    except ImportError:
        pass
    opp_weapon = _get_character_weapon_key(opponent)
    opp_bonus = _comfort_bonus(opp_weapon, current)
    _, mover_val = _footwork_roll(mover, modifier=RETREAT_BONUS)
    _, opp_val = _footwork_roll(opponent, modifier=opp_bonus)
    target_range = current + 1
    range_label = RANGE_LABELS.get(target_range, "further")
    current_label = RANGE_LABELS.get(current, "current distance")
    if mover_val > opp_val:
        set_combat_range(mover, opponent, target_range)

        def msg_room(viewer):
            return f"{_display_name(mover, viewer)} backs away from {_display_name(opponent, viewer)}. They're at {range_label} range now."

        return True, target_range, f"|gYou pull back to {range_label} range.|n", f"|y{{mover}} pulls away from you. {range_label.capitalize()} range.|n", msg_room

    def msg_room(viewer):
        return f"{_display_name(mover, viewer)} tries to back away but {_display_name(opponent, viewer)} stays on them."

    return False, current, f"|rYou try to pull back but they stay on you. Still at {current_label} range.|n", f"|g{{mover}} tries to break away. You stay on them.|n", msg_room


def validate_grapple_range(grappler, target):
    current = get_combat_range(grappler, target)
    if current in (RANGE_CLINCH, RANGE_CLOSE):
        return True, None
    label = RANGE_LABELS.get(current, "this distance")
    return False, f"You're too far away to grapple. You need to advance to close range first. (Currently at {label} range.)"


def get_attack_range_penalty(attacker, defender, weapon_key):
    current = get_combat_range(attacker, defender)
    return get_weapon_range_penalty(weapon_key, current)


def get_parry_range_penalty(defender, attacker):
    current = get_combat_range(defender, attacker)
    weapon_key = _get_character_weapon_key(defender)
    pen = get_weapon_range_penalty(weapon_key, current)
    if pen is None:
        return None
    return pen


def get_range_display_line(attacker, defender):
    current = get_combat_range(attacker, defender)
    label = RANGE_LABELS.get(current, "?")
    atk_weapon = _get_character_weapon_key(attacker)
    def_weapon = _get_character_weapon_key(defender)
    atk_status = get_range_status_text(atk_weapon, current)
    def_status = get_range_status_text(def_weapon, current)
    cov_you = get_cover_status_text(attacker)
    cov_them = get_cover_status_text(defender)
    return (
        f"|wRange|n: {label} | You: {atk_status}, {cov_you} | Them: {def_status}, {cov_them}"
    )


def on_combat_start(attacker, defender, attacker_weapon_key):
    initial = get_initial_range(attacker_weapon_key)
    set_combat_range(attacker, defender, initial)


def on_combat_end(a, b):
    clear_combat_range(a, b)

