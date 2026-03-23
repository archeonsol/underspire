"""
Combat spacing: positional distance bands were removed in favor of room size + cover.
This module keeps stable imports and a single nominal "range" value for cover math only.
"""

from __future__ import annotations

from world.combat.cover import get_cover_status_text
from world.combat.utils import combat_display_name

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


def get_combat_range(a, b):
    """Nominal exchange distance (fixed). No per-pair tracking."""
    return DEFAULT_STARTING_RANGE


def set_combat_range(a, b, value):
    """Legacy no-op (positional range removed)."""
    return


def clear_combat_range(a, b):
    """Legacy no-op."""
    return


def get_weapon_range_penalty(weapon_key, current_range):
    """Positional penalties removed; room size applies elsewhere."""
    return 0


def get_attack_range_penalty(attacker, defender, weapon_key):
    return 0


def get_parry_range_penalty(defender, attacker):
    """Allow parry when melee-eligible; no range gate."""
    return 0


def get_range_status_text(weapon_key, current_range):
    return "|gexchange|n"


def can_attack_at_range(weapon_key, current_range):
    return True


def is_weapon_optimal(weapon_key, current_range):
    return True


def get_weapon_optimal_ranges(weapon_key):
    return [DEFAULT_STARTING_RANGE]


def get_range_display_line(attacker, defender):
    cov_you = get_cover_status_text(attacker)
    cov_them = get_cover_status_text(defender)
    return f"|wCover|n: You are {cov_you}. {combat_display_name(defender, attacker)} is {cov_them}."


def validate_grapple_range(grappler, target):
    return True, None
