"""
Grade adjectives: one per letter Q->A, keyed by grade letter.
Stats have custom adjectives per stat; skills share one set.
Letter of grade matches the adjective (same letter / starts with that letter).
"""

# Grade order worst (Q) to best (A)
GRADE_LETTERS = "QPONMLKJIHGFEDCBA"

# Per-stat adjectives: SPECIAL (Fallout). Every adjective unique across all stats.
# All dicts here are not mutated so safe as module-level constants.
STAT_GRADE_ADJECTIVES = {
    "strength": {
        "Q": "Quivering", "P": "Puny", "O": "Overmatched", "N": "Negligible",
        "M": "Meager", "L": "Low", "K": "Knackered", "J": "Jelly-like",
        "I": "Insubstantial", "H": "Humdrum", "G": "Growing", "F": "Formidable",
        "E": "Exceptional", "D": "Dominant", "C": "Commanding", "B": "Brutal", "A": "Almighty",
    },
    "perception": {
        "Q": "Querying", "P": "Poor", "O": "Oblivious", "N": "Narrow",
        "M": "Muddled", "L": "Lacking", "K": "Keen-ish", "J": "Judicious",
        "I": "Intuitive", "H": "Honed", "G": "Grounded", "F": "Focused",
        "E": "Exact", "D": "Detecting", "C": "Clear", "B": "Beholding", "A": "All-seeing",
    },
    "endurance": {
        "Q": "Quitting", "P": "Pathetic", "O": "Out of steam", "N": "Negated",
        "M": "Modest", "L": "Limping", "K": "Kaput", "J": "Jaded",
        "I": "Insufficient", "H": "Holding", "G": "Gritty", "F": "Fortified",
        "E": "Enduring", "D": "Durable", "C": "Conditioned", "B": "Bulletproof", "A": "Adamant",
    },
    "charisma": {
        "Q": "Quiet", "P": "Plain", "O": "Off-putting", "N": "Nothing special",
        "M": "Mild", "L": "Lackluster", "K": "Kind of there", "J": "Jovial",
        "I": "Interesting", "H": "Hypnotic", "G": "Genuine", "F": "Fascinating",
        "E": "Enchanting", "D": "Disarming", "C": "Compelling", "B": "Beguiling", "A": "Alluring",
    },
    "intelligence": {
        "Q": "Quizzical", "P": "Primitive", "O": "Obtuse", "N": "Naive",
        "M": "Middling", "L": "Limited", "K": "Know-nothing", "J": "Juvenile",
        "I": "Incomplete", "H": "Half-baked", "G": "Gifted", "F": "Farsighted",
        "E": "Erudite", "D": "Discerning", "C": "Cerebral", "B": "Brilliant", "A": "Astute",
    },
    "agility": {
        "Q": "Quavering", "P": "Plodding", "O": "Obstinate", "N": "Numb",
        "M": "Moderate", "L": "Leaden", "K": "Klutzy", "J": "Jittery",
        "I": "Inert", "H": "Hesitant", "G": "Graceful", "F": "Fleet",
        "E": "Effortless", "D": "Dynamic", "C": "Cat-like", "B": "Boundless", "A": "Acrobatic",
    },
    "luck": {
        "Q": "Quirkless", "P": "Penniless", "O": "Out of luck", "N": "Null",
        "M": "Mercurial", "L": "Lucky", "K": "Karmic", "J": "Jinxed",
        "I": "Inspired", "H": "Halcyon", "G": "Golden", "F": "Favored",
        "E": "Elect", "D": "Destined", "C": "Charmed", "B": "Blessed", "A": "Arcane",
    },
}

# Skills share one set (letter-matched). No overlap with any stat adjective.
SKILL_GRADE_ADJECTIVES = {
    "Q": "Questionable", "P": "Patchy", "O": "Out of depth", "N": "Novice",
    "M": "Marginal", "L": "Learned", "K": "Knackless", "J": "Junior",
    "I": "Inexperienced", "H": "Half-decent", "G": "Good", "F": "Functional",
    "E": "Expert", "D": "Disciplined", "C": "Capable", "B": "Badass", "A": "Apex",
}

# Use tuple of all valid stat keys for perf in lookup
_STAT_GRADE_DEFAULT = STAT_GRADE_ADJECTIVES["strength"]

def get_stat_grade_adjective(grade_letter, stat_key):
    """
    Return the adjective for this stat at this grade. Letter matches grade.
    If the stat key is not recognized, uses the 'strength' adjectives as fallback.
    """
    grade = str(grade_letter).upper() if grade_letter else "Q"
    # Use .get with constant fallback instead of re-evaluating default every call
    by_stat = STAT_GRADE_ADJECTIVES.get(stat_key, _STAT_GRADE_DEFAULT)
    return by_stat.get(grade, "Unknown")

def get_skill_grade_adjective(grade_letter):
    """
    Return the adjective for any skill at this grade. Letter matches grade.
    """
    grade = str(grade_letter).upper() if grade_letter else "Q"
    return SKILL_GRADE_ADJECTIVES.get(grade, "Unknown")
