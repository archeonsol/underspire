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
    Legacy: XP for one level. Prefer world.rpg.xp.xp_cost_for_stat_level / xp_cost_for_skill_level.
    """
    from world.rpg.xp import xp_cost_for_stat_level, xp_cost_for_skill_level
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


# ============================================================================
# Generic Skill Check Functions (Tunable for Game Balance)
# ============================================================================

def normalize_stat_for_check(stat_stored_value):
    """
    Convert stored stat value (0-300) to check scale (0-150).
    Stats are stored at 0-300 because they cost 2x to level, but for
    check math everything should be on the 0-150 scale.

    Args:
        stat_stored_value: Stat value from character.db (0-300 range)

    Returns:
        float: Normalized value on 0-150 scale

    Example:
        strength = character.db.strength or 0
        strength_check = normalize_stat_for_check(strength)
        success, margin = skill_check(strength_check, difficulty)
    """
    return (stat_stored_value or 0) / 2.0


def skill_check(
    skill_value,
    difficulty,
    min_prob=0.05,
    max_prob=0.95,
    curve_steepness=1.0,
    q_factor=1.0,
    **kwargs
):
    """
    Generic tunable skill check with difficulty.

    Args:
        skill_value: Character's skill level (0-150)
        difficulty: Task difficulty (0-150 scale)
        min_prob: Minimum success probability (floor), e.g., 0.05 = 5% minimum chance
        max_prob: Maximum success probability (ceiling), e.g., 0.95 = 95% maximum chance
        curve_steepness: How much skill differential matters (default 1.0)
                        - Higher values = skill matters more (steeper curve)
                        - Lower values = more flat/random (skill matters less)
        q_factor: Final roll variance (1.0=uniform, <1=more consistent, >1=more swingy)
        **kwargs: Reserved for future tuning parameters

    Returns:
        (success: bool, margin: float)
        - success: True if check succeeded
        - margin: Positive on success, negative on failure. Magnitude indicates degree.

    Example:
        success, margin = skill_check(75, 50)  # 75 skill vs 50 difficulty
        if success:
            if margin > 30:
                # Critical success
            elif margin > 15:
                # Strong success
            else:
                # Marginal success

    Tuning guide:
        - For "masters are reliable": curve_steepness=1.0-2.0, q_factor=0.8-1.0
        - For "more random/cinematic": curve_steepness=0.5, q_factor=1.2-1.5
        - min_prob/max_prob prevent impossible/guaranteed outcomes
    """
    import random

    # Clamp inputs to valid range
    skill_value = max(0, min(150, skill_value))
    difficulty = max(0, min(150, difficulty))

    # Calculate skill differential (-150 to +150)
    skill_diff = skill_value - difficulty

    # Convert differential to base probability
    # At equal skill (diff=0), base_prob = 0.5
    # At +150 diff, base_prob approaches max_prob
    # At -150 diff, base_prob approaches min_prob
    # curve_steepness controls how quickly probability changes with skill diff
    normalized_diff = (skill_diff / 150.0) * curve_steepness
    base_prob = 0.5 + (normalized_diff * 0.5)  # Maps -1 to +1 diff to 0-1 probability

    # Apply min/max caps
    clamped_prob = max(min_prob, min(max_prob, base_prob))

    # Apply q_factor variance to final roll
    # This adds "dice variance" while respecting the probability
    random_roll = random.random() ** (1.0 / q_factor)
    success = random_roll < clamped_prob

    # Calculate margin for degree of success/failure
    # Margin represents how far above/below the threshold we rolled
    threshold = clamped_prob
    margin_raw = random_roll - threshold  # Negative on failure, positive on success

    # Scale margin back to skill scale for interpretation
    # A margin of ±0.5 (full random range) maps to ±75 on skill scale
    final_margin = margin_raw * 150.0

    return success, final_margin


def contested_check(
    skill_a,
    skill_b,
    tie_threshold=5.0,
    curve_steepness=1.0,
    q_factor=1.0,
    **kwargs
):
    """
    Generic contested check between two opposing skills.

    Args:
        skill_a: Attacker/initiator skill level (0-150)
        skill_b: Defender/responder skill level (0-150)
        tie_threshold: Margin below which result is considered a tie (on 0-150 scale)
                      - Default 5.0 means if they're within 5 points, it's a tie
        curve_steepness: How much skill differential matters (default 1.0)
                        - Higher = skilled fighter almost always beats unskilled
                        - Lower = more upsets possible
        q_factor: Controls randomness (1.0=uniform, <1=more consistent, >1=more swingy)
        **kwargs: Reserved for future tuning parameters

    Returns:
        (winner: str, margin: float)
        - winner: 'a', 'b', or 'tie'
        - margin: Always positive, indicates how decisively winner won

    Example:
        winner, margin = contested_check(80, 60)  # 80 skill vs 60 skill
        if winner == 'a':
            if margin > 30:
                # Decisive victory for A
            elif margin > 10:
                # Clear victory for A
            else:
                # Narrow victory for A
        elif winner == 'tie':
            # Dead heat

    Tuning guide:
        - For "skill matters a lot": curve_steepness=1.5-2.0, q_factor=0.8
        - For "David vs Goliath possible": curve_steepness=0.5-0.7, q_factor=1.2
        - tie_threshold controls how often exact ties occur
    """
    import random

    # Clamp inputs to valid range
    skill_a = max(0, min(150, skill_a))
    skill_b = max(0, min(150, skill_b))

    # Normalize to 0-1 scale and apply curve steepness
    skill_a_norm = (skill_a / 150.0) ** curve_steepness
    skill_b_norm = (skill_b / 150.0) ** curve_steepness

    # Apply q_factor to random rolls
    rand_a = random.random() ** (1.0 / q_factor)
    rand_b = random.random() ** (1.0 / q_factor)

    # Calculate effective rolls
    roll_a = skill_a_norm * rand_a
    roll_b = skill_b_norm * rand_b

    # Calculate margin (always positive for return)
    raw_margin = roll_a - roll_b
    margin = abs(raw_margin) * 150.0  # Scale back to 0-150 for interpretation

    # Determine winner
    if margin < tie_threshold:
        return 'tie', margin
    elif raw_margin > 0:
        return 'a', margin
    else:
        return 'b', margin
