"""
Numeric level system: skills 0-150, stats 0-300 (stored).
21-letter grade scale U (worst) to A (best). Thresholds and XP curve data in world.constants.
"""
from world.constants import SKILL_GRADE_THRESHOLDS as _SKILL_GRADE_DICT, STAT_GRADE_THRESHOLDS as _STAT_GRADE_DICT

MAX_LEVEL = 150       # skills: 0-150
MAX_STAT_LEVEL = 300  # stats: stored 0-300

# 21 letters, worst to best (canonical scale)
LEVEL_LETTERS = "UTSRQPONMLKJIHGFEDCBA"
NUM_LEVEL_TIERS = len(LEVEL_LETTERS)

# Re-export for callers that expect the dict from constants
SKILL_GRADE_THRESHOLDS = _SKILL_GRADE_DICT
STAT_GRADE_THRESHOLDS = _STAT_GRADE_DICT

# Bounds for letter_to_level_range: (level, letter) ascending by level
def _bounds_from_threshold_dict(threshold_dict):
    return [(0, "U")] + [(thresh, letter) for letter, thresh in sorted(threshold_dict.items(), key=lambda x: x[1])]

STAT_LETTER_BOUNDS = _bounds_from_threshold_dict(_STAT_GRADE_DICT)
SKILL_LETTER_BOUNDS = _bounds_from_threshold_dict(_SKILL_GRADE_DICT)
_STAT_KEYS = [thresh for _letter, thresh in sorted(_STAT_GRADE_DICT.items(), key=lambda x: x[1])]
_SKILL_KEYS = [thresh for _letter, thresh in sorted(_SKILL_GRADE_DICT.items(), key=lambda x: x[1])]

# Combat / skill tier breakpoints (integer levels)
SKILL_LEVEL_TIER_1 = 60
SKILL_LEVEL_FOR_C = 123  # first level in letter C (from milestone 123)


def _letter_for_level(level, bounds, max_level):
    """Return letter for level using (min_level, letter) bounds. Level < 0 -> first letter; >= max -> last letter."""
    if level is None or level < 0:
        return bounds[0][1]
    level = int(level)
    if level >= max_level:
        return bounds[-1][1]
    letter = bounds[0][1]
    for min_lv, ltr in bounds:
        if level >= min_lv:
            letter = ltr
        else:
            break
    return letter


def get_grade(level, threshold_dict):
    """
    Universal grade lookup: iterate threshold dict from highest to lowest, return letter when level >= threshold.
    threshold_dict: letter -> minimum level (e.g. {"A": 141, "B": 132, ..., "U": 1}).
    """
    if level is None or level < 0:
        return "U"
    level = int(level)
    for letter, thresh in sorted(threshold_dict.items(), key=lambda x: -x[1]):
        if level >= thresh:
            return letter
    return "U"


def get_skill_grade(level):
    """Return letter grade for skill level (0-150)."""
    return get_grade(level, SKILL_GRADE_THRESHOLDS)


def get_stat_grade(stored_level):
    """Return letter grade for stat stored level (0-300)."""
    return get_grade(stored_level, STAT_GRADE_THRESHOLDS)


def level_to_letter(level, max_level=None):
    """
    Convert numeric level to grade letter (U through A). Uses canonical milestone boundaries.
    max_level=150 for skills, 300 for stats (default 150).
    """
    max_level = MAX_LEVEL if max_level is None else max_level
    if max_level == MAX_STAT_LEVEL:
        return get_stat_grade(level)
    return get_skill_grade(level)


def letter_to_level_range(letter, max_level=None):
    """
    Return (min_level, max_level) for a letter. For migration/lookup.
    U = 0-11 (stats) or 0-5 (skills), A = 282-300 or 141-150.
    """
    max_level = MAX_LEVEL if max_level is None else max_level
    ltr = str(letter).upper() if letter else "U"
    if ltr not in LEVEL_LETTERS:
        return 0, max_level
    if max_level == MAX_STAT_LEVEL:
        bounds = STAT_LETTER_BOUNDS
    else:
        bounds = SKILL_LETTER_BOUNDS
    lo, hi = 0, max_level
    found = False
    for lv, b in bounds:
        if b == ltr:
            if not found:
                lo = lv
                found = True
        elif found:
            hi = lv - 1
            break
    return max(0, lo), min(max_level, hi)


def level_to_effective_grade(level, max_level=None):
    """
    Map level to 1-21 for formulas (max_hp, etc). U=1, A=21.
    """
    max_level = MAX_LEVEL if max_level is None else max_level
    if level is None or level < 0:
        return 1
    try:
        lv = int(level)
    except (TypeError, ValueError):
        return 1
    letter = level_to_letter(lv, max_level)
    grade = LEVEL_LETTERS.index(letter) + 1
    return max(1, min(NUM_LEVEL_TIERS, grade))


def xp_cost_for_next_level(current_level, max_level=None):
    """
    Legacy: XP for one level. Prefer world.xp.xp_cost_for_stat_level / xp_cost_for_skill_level.
    """
    from world.xp import xp_cost_for_stat_level, xp_cost_for_skill_level
    max_level = MAX_LEVEL if max_level is None else max_level
    try:
        lv = int(current_level or 0)
    except (TypeError, ValueError):
        lv = 0
    if lv >= max_level:
        return None
    if max_level == MAX_STAT_LEVEL:
        cost = xp_cost_for_stat_level(lv)
    else:
        cost = xp_cost_for_skill_level(lv)
    return int(cost) if cost is not None and cost == int(cost) else cost
