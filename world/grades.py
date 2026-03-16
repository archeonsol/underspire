"""
Grade adjectives: one per letter U->A (21 letters), keyed by grade letter.
Stats have custom adjectives per stat; skills share one set.
Letter of grade matches the adjective (same letter / starts with that letter).
"""

# Grade order worst (U) to best (A) — 21 letters, canonical scale
GRADE_LETTERS = "UTSRQPONMLKJIHGFEDCBA"

# Per-stat adjectives: 21 letters U through A. Every adjective unique across all stats.
STAT_GRADE_ADJECTIVES = {
    "strength": {
        "U": "Unsound", "T": "Tender", "S": "Spindly", "R": "Rickety",
        "Q": "Quivering", "P": "Powerless", "O": "Obsolete", "N": "Negligible",
        "M": "Meager", "L": "Limp", "K": "Knackered", "J": "Juicer",
        "I": "Inured", "H": "Hale", "G": "Great", "F": "Formidable",
        "E": "Exceptional", "D": "Destroyer", "C": "Concentrated", "B": "Booster", "A": "Almighty",
    },
    "perception": {
        "U": "Unperceiving", "T": "Typhlotic", "S": "Susceptive", "R": "Reckless",
        "Q": "Querying", "P": "Poor", "O": "Oblivious", "N": "Narrow",
        "M": "Muddled", "L": "Lacking", "K": "Keen", "J": "Judicious",
        "I": "Intuitive", "H": "Honed", "G": "Grounded", "F": "Focused",
        "E": "Exacting", "D": "Detective", "C": "Clairvoyant", "B": "Beholder", "A": "Astute",
    },
    "endurance": {
        "U": "Unfit", "T": "Tired", "S": "Spent", "R": "Ragged",
        "Q": "Queasy", "P": "Pathetic", "O": "Otiose", "N": "Nonathletic",
        "M": "Milling", "L": "Lethargic", "K": "Kaput", "J": "Jock",
        "I": "Invigorated", "H": "Hardy", "G": "Gritty", "F": "Fortified",
        "E": "Enduring", "D": "Durable", "C": "Conditioned", "B": "Bulletproof", "A": "Adamant",
    },
    "charisma": {
        "U": "Ugly", "T": "Terrible", "S": "Sour", "R": "Rancid",
        "Q": "Quarantined", "P": "Pariah", "O": "Odious", "N": "Nebulous",
        "M": "Miserable", "L": "Lackluster", "K": "Knave", "J": "Jovial",
        "I": "Interesting", "H": "Honorable", "G": "Gracious", "F": "Fabulous",
        "E": "Engaging", "D": "Dignified", "C": "Charming", "B": "Beautiful", "A": "Arresting",
    },
        "intelligence": {
        "U": "Unintelligent", "T": "Thick", "S": "Shallow", "R": "Rote",
        "Q": "Quizzical", "P": "Primitive", "O": "Obtuse", "N": "Naive",
        "M": "Middling", "L": "Lummox", "K": "Knowing", "J": "Jaded",
        "I": "Informed", "H": "Headful", "G": "Gifted", "F": "Foresighted",
        "E": "Erudite", "D": "Discerning", "C": "Cerebral", "B": "Brilliant", "A": "Astute",
    },
    "agility": {
        "U": "Unsteady", "T": "Tense", "S": "Stiff", "R": "Rigid",
        "Q": "Quiescent", "P": "Plodding", "O": "Obstinate", "N": "Numb",
        "M": "Moderate", "L": "Leaden", "K": "Kinetic", "J": "Jittery",
        "I": "Imminent", "H": "Hasted", "G": "Graceful", "F": "Fleet",
        "E": "Expedient", "D": "Dizzying", "C": "Celeritous", "B": "Blazing", "A": "Acrobatic",
    },
    "luck": {
        "U": "Unlucky", "T": "Troubled", "S": "Scorned", "R": "Random",
        "Q": "Quirkless", "P": "Plagued", "O": "Ominous", "N": "Nullified",
        "M": "Mercurial", "L": "Level", "K": "Karmic", "J": "Jaunty",
        "I": "Inspired", "H": "Halcyon", "G": "Golden", "F": "Favored",
        "E": "Eminent", "D": "Destined", "C": "Charmed", "B": "Blessed", "A": "Arcane",
    },
}

# Skills: 21 letters U through A
SKILL_GRADE_ADJECTIVES = {
    "U": "Untrained", "T": "Trial", "S": "Shaky", "R": "Rote",
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
    grade = str(grade_letter).upper() if grade_letter else "U"
    # Use .get with constant fallback instead of re-evaluating default every call
    by_stat = STAT_GRADE_ADJECTIVES.get(stat_key, _STAT_GRADE_DEFAULT)
    return by_stat.get(grade, "Unknown")

def get_skill_grade_adjective(grade_letter):
    """
    Return the adjective for any skill at this grade. Letter matches grade.
    """
    grade = str(grade_letter).upper() if grade_letter else "U"
    return SKILL_GRADE_ADJECTIVES.get(grade, "Unknown")
