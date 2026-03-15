"""
Numeric level system: skills 0-150 (1 raise = 1 point), stats same scale but 1 raise = 0.5 points.
Stats stored internally as 0-300 (2 stored = 1 displayed point); letter/formulas use stored value.
All 17 letters Q through A; XP cost increases with level (~1-1.5 year cap).
"""

# Class-level constants for configuration
LEVEL_LETTERS = "QPONMLKJIHGFEDCBA"
NUM_LEVEL_TIERS = len(LEVEL_LETTERS)
MAX_LEVEL = 150       # skills: 0-150, 1 raise = +1
MAX_STAT_LEVEL = 300  # stats: stored 0-300, 1 raise = +1 stored = +0.5 points (display as stored//2)

# Combat attack tiers: which moves unlock at which skill level (integer, not letter)
SKILL_LEVEL_TIER_1 = 60
SKILL_LEVEL_FOR_C = (14 * MAX_LEVEL) // NUM_LEVEL_TIERS  # 123 = first level in letter C

def level_to_letter(level, max_level=None):
    """
    Convert numeric level to grade letter. Uses all letters in LEVEL_LETTERS.
    max_level=150 for skills, 300 for stats (default 150).
    """
    max_level = MAX_LEVEL if max_level is None else max_level
    if level is None:
        return LEVEL_LETTERS[0]  # "Q"
    try:
        lv = int(level)
    except (TypeError, ValueError):
        return LEVEL_LETTERS[0]  # "Q"
    if lv >= max_level:
        return "A"
    if lv < 0:
        return LEVEL_LETTERS[0]  # "Q"
    # NUM_LEVEL_TIERS tiers: 0 -> Q, ..., max_level-1 -> last letter before A
    idx = (lv * NUM_LEVEL_TIERS) // max_level
    idx = min(NUM_LEVEL_TIERS - 1, idx)
    return LEVEL_LETTERS[idx]

def letter_to_level_range(letter, max_level=None):
    """
    Return (min_level, max_level) for a letter. For migration. max_level=150 skills, 300 stats.
    """
    max_level = MAX_LEVEL if max_level is None else max_level
    default_hi = max_level // NUM_LEVEL_TIERS - 1
    if not letter:
        return 0, default_hi
    ltr = str(letter).upper()
    if ltr == "A":
        return max_level, max_level
    if ltr in LEVEL_LETTERS:
        idx = LEVEL_LETTERS.index(ltr)
        lo = (idx * max_level) // NUM_LEVEL_TIERS
        hi = ((idx + 1) * max_level) // NUM_LEVEL_TIERS - 1
        return max(0, lo), min(max_level, hi)
    return 0, default_hi

def level_to_effective_grade(level, max_level=None):
    """
    Map level to 1-17 for formulas (max_hp, medical, etc). max_level=150 skills, 300 stats.
    """
    max_level = MAX_LEVEL if max_level is None else max_level
    if level is None:
        return 1
    try:
        lv = int(level)
    except (TypeError, ValueError):
        return 1
    if lv <= 0:
        return 1
    if lv >= max_level:
        return NUM_LEVEL_TIERS
    result = 1 + round(lv * (NUM_LEVEL_TIERS - 1) / max_level)
    return max(1, min(NUM_LEVEL_TIERS, result))

def xp_cost_for_next_level(current_level, max_level=None):
    """
    XP required to raise from current_level to current_level + 1.
    Steeper curve; higher XP gain compensates so full build fits in ~1.5 years.
    Skills: cost steps every 12 (1 at 0-11, 2 at 12-23, ... 12 at 132-149).
    Stats: cost steps every 30 (1 at 0-29, 2 at 30-59, ... 10 at 270-299).
    Design math: 1 skill to B (135) ~828 XP, to E (108) ~540 XP; 1 B + 5 E ~3528 XP.
    Stats (step 30): 1 B + 1 C + 2 D + 2 E + 1 M ~6721 XP; full build ~10250, cap 10500.
    """
    max_level = MAX_LEVEL if max_level is None else max_level
    if current_level is None:
        lv = 0
    else:
        try:
            lv = int(current_level)
        except (TypeError, ValueError):
            lv = 0
    if lv >= max_level:
        return None
    if max_level == MAX_STAT_LEVEL:
        return 1 + (lv // 30)   # stats: 0-29 cost 1, 30-59 cost 2, ... 270-299 cost 10
    return 1 + (lv // 12)       # skills: 0-11 cost 1, 12-23 cost 2, ...
