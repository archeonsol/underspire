"""
Short description (sdesc) system: dynamic one-line blurb next to a character's name.

Shows in room look and when entering a room, e.g.:
  Test (a refined rangy man wearing a silk shirt and carrying a blade)

Built from: outfit prefix (if quality high) + build adjective (height+weight, gender-specific) + gender term + worn items + wielded weapon.
Updates automatically when they wear/wield/unwield (computed on the fly).
"""

# Outfit quality (averaged score 0-100) -> prefix before build adjective. Higher = more refined.
SDESC_OUTFIT_PREFIX = [
    (95, "elegant"),
    (90, "refined"),
    (80, "stylish"),
]

# Build adjectives: (height_category, weight_category) -> adjective, by gender.
# height: tall, average, short. weight: heavy, average, thin.
BUILD_ADJECTIVES_MALE = {
    "tall_heavy": "hulking",
    "tall_average": "rangy",
    "tall_thin": "lanky",
    "average_heavy": "burly",
    "average_average": "average",
    "average_thin": "wiry",
    "short_heavy": "stout",
    "short_average": "compact",
    "short_thin": "scrawny",
}

BUILD_ADJECTIVES_FEMALE = {
    "tall_heavy": "amazonian",
    "tall_average": "leggy",
    "tall_thin": "willowy",
    "average_heavy": "voluptuous",
    "average_average": "average",
    "average_thin": "lissome",
    "short_heavy": "plump",
    "short_average": "petite",
    "short_thin": "delicate",
}

BUILD_ADJECTIVES_NONBINARY = {
    "tall_heavy": "heavyset",
    "tall_average": "lofty",
    "tall_thin": "reedy",
    "average_heavy": "solid",
    "average_average": "average",
    "average_thin": "slender",
    "short_heavy": "chunky",
    "short_average": "diminutive",
    "short_thin": "slight",
}

# Customizable gender terms (sdesc customize / sdesc set <term>). Default is first in each list.
SDESC_GENDER_TERMS_MALE = [
    "man", "male", "guy", "dude", "bro", "bloke", "chap", "lad", "fella", "bastard",
    "hombre", "gent", "gentleman", "sir", "boy", "buck", "stud", "twink", "femboy", "faggot",
]
SDESC_GENDER_TERMS_FEMALE = [
    "woman", "female", "gal", "lady", "lass", "dame", "chica", "miss", "maiden",
    "girl", "madame", "queen", "vixen", "sister", "bitch",
]
SDESC_GENDER_TERMS_NB = [
    "person", "individual", "being", "figure", "soul", "entity", "denizen", "citizen",
    "punk", "urchin", "dweller", "fleshbag", "body", "mortal", "creature",
]

# weapon_key (combat) -> "carrying a X" for sdesc. Unarmed/fists not shown.
WEAPON_KEY_TO_SDESC = {
    "knife": "a blade",
    "short_blade": "a blade",
    "long_blade": "a blade",
    "blunt": "a blunt weapon",
    "sidearm": "a gun",
    "longarm": "a gun",
    "automatic": "a gun",
    "fists": None,
    "unarmed": None,
}


def _clothing_state(character):
    """
    Return 'naked', 'topless', or None.
    - naked: no clothing at all
    - topless: some clothing but no upper-body coverage
    """
    from world.clothing import get_worn_items, get_covered_parts_set, UPPER_BODY_PARTS
    worn = get_worn_items(character)
    if not worn:
        return "naked"
    covered = get_covered_parts_set(character)
    if not covered.intersection(set(UPPER_BODY_PARTS)):
        return "topless"
    return None


def get_outfit_prefix(character):
    """Return prefix word for sdesc if outfit quality is high enough, else ''."""
    from world.clothing import get_worn_items
    worn = get_worn_items(character)
    if not worn:
        return ""
    scores = []
    for item in worn:
        s = getattr(item.db, "quality_score", None)
        if s is not None:
            scores.append(int(s))
    if not scores:
        return ""
    avg = sum(scores) / len(scores)
    for min_score, prefix in reversed(SDESC_OUTFIT_PREFIX):
        if avg >= min_score:
            return prefix + " "
    return ""


def _gender_term(gender):
    """Default term from gender: 'man', 'woman', 'person' (first in each list)."""
    g = (gender or "").lower()
    if g in ("male", "m"):
        return SDESC_GENDER_TERMS_MALE[0]
    if g in ("female", "f"):
        return SDESC_GENDER_TERMS_FEMALE[0]
    return SDESC_GENDER_TERMS_NB[0]


def get_gender_terms_list(character):
    """Return the list of allowed terms for this character's gender."""
    gender = str(getattr(character.db, "gender", None) or getattr(character.db, "pronoun", None) or "nonbinary").strip().lower()
    if gender in ("male", "m"):
        return SDESC_GENDER_TERMS_MALE
    if gender in ("female", "f"):
        return SDESC_GENDER_TERMS_FEMALE
    return SDESC_GENDER_TERMS_NB


def get_gender_term(character):
    """Return the sdesc gender term: custom (sdesc_gender_term) if set and valid or staff-approved, else default for gender."""
    custom = getattr(character.db, "sdesc_gender_term", None)
    if custom:
        custom = str(custom).strip().lower()
        allowed = get_gender_terms_list(character)
        if custom in [t.lower() for t in allowed]:
            return custom
        # Staff-approved custom term (one word, set via pending approval)
        if getattr(character.db, "sdesc_gender_term_custom", False) and custom:
            return custom
    return _gender_term(getattr(character.db, "gender", None) or getattr(character.db, "pronoun", None))


def _article_for(word):
    """Return 'a' or 'an' for the given word (e.g. adjective before man/woman/person)."""
    if not word:
        return "a"
    w = str(word).strip().lower()
    if not w:
        return "a"
    # Words that take 'an': vowel sound at start
    an_words = ("average", "amazonian", "elegant", "eastern", "honorable", "honest", "individual", "entity")
    if w in an_words or w.startswith(("a", "e", "i", "o", "u")):
        return "an"
    return "a"


def _build_adjective(character):
    """Return build adjective from height_category + weight_category + gender (e.g. 'rangy', 'petite')."""
    height = str(getattr(character.db, "height_category", None) or "average").strip().lower()
    weight = str(getattr(character.db, "weight_category", None) or "average").strip().lower()
    gender = str(getattr(character.db, "gender", None) or getattr(character.db, "pronoun", None) or "nonbinary").strip().lower()
    if height not in ("short", "average", "tall"):
        height = "average"
    if weight not in ("heavy", "average", "thin"):
        weight = "average"
    key = height + "_" + weight
    if gender in ("male", "m"):
        table = BUILD_ADJECTIVES_MALE
    elif gender in ("female", "f"):
        table = BUILD_ADJECTIVES_FEMALE
    else:
        table = BUILD_ADJECTIVES_NONBINARY
    return table.get(key, "average")


def _wielded_carry_phrase(character):
    """'carrying a blade' or 'carrying a gun' or '' if nothing / unarmed."""
    wielded_key = getattr(character.db, "wielded", None) or getattr(character.db, "wielded_obj", None)
    if wielded_key and hasattr(wielded_key, "db"):
        from typeclasses.weapons import get_weapon_key
        wielded_key = get_weapon_key(wielded_key)
    if not wielded_key:
        return ""
    carry = WEAPON_KEY_TO_SDESC.get(wielded_key)
    if not carry:
        return ""
    return "carrying " + carry


def _worn_phrase(character, looker=None):
    """
    Return a single, most-striking worn item for sdesc, rather than a full list.

    Priority:
      - Any worn Armor piece (outermost armor_layer, highest quality_score).
      - Otherwise, the highest-quality tailored Clothing (by quality_score).
      - Fallback to the last worn item if no quality scores are set.
    """
    from world.clothing import get_worn_items
    from typeclasses.armor import Armor
    from typeclasses.clothing import Clothing

    worn = get_worn_items(character)
    if not worn:
        return ""

    armor_items = [w for w in worn if isinstance(w, Armor)]
    clothing_items = [w for w in worn if isinstance(w, Clothing) and not isinstance(w, Armor)]

    best = None
    if armor_items:
        # Pick armor with highest layer, then highest quality_score.
        def _armor_key(it):
            layer = int(getattr(getattr(it, "db", None), "armor_layer", 0) or 0)
            qs = getattr(getattr(it, "db", None), "quality_score", None)
            qs_val = int(qs) if qs is not None else 0
            return (layer, qs_val)
        best = sorted(armor_items, key=_armor_key)[-1]
    elif clothing_items:
        # Pick clothing with highest quality_score.
        def _cloth_key(it):
            qs = getattr(getattr(it, "db", None), "quality_score", None)
            return int(qs) if qs is not None else 0
        best = sorted(clothing_items, key=_cloth_key)[-1]
    else:
        best = worn[-1]

    if not best:
        return ""
    name = best.get_display_name(looker) if hasattr(best, "get_display_name") else getattr(best, "key", str(best))
    if not name:
        return ""
    return "wearing a " + name


def get_short_desc(character, looker=None):
    """
    Build the dynamic short description: [article] + prefix + build adjective + [naked|topless]? + gender + wearing + carrying.

    Example: "a refined rangy man wearing a silk shirt and carrying a blade"
    Naked: "an average naked man"
    Topless: "a tall topless woman wearing a pair of jeans"
    """
    if not character:
        return ""
    prefix = get_outfit_prefix(character)
    adjective = _build_adjective(character)
    gender = get_gender_term(character)
    state = _clothing_state(character)
    worn = _worn_phrase(character, looker)
    carry = _wielded_carry_phrase(character)

    article = _article_for(adjective)
    body = article + " " + prefix + adjective
    if state == "naked":
        body += " naked " + gender
    elif state == "topless":
        body += " topless " + gender
    else:
        body += " " + gender
    parts = [body]
    if worn and state != "naked":
        parts.append(worn)
    if carry:
        parts.append(carry)
    return " ".join(parts)
