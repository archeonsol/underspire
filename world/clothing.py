"""
Clothing system: dynamic coverage of body parts.
Clothing and armor define which body parts they cover; worn items,
layering, and coverage queries live here. The appearance pipeline
(assembling body descriptions from all systems) lives in world.appearance.
"""
from world.medical import BODY_PARTS
from world.body import UPPER_BODY as UPPER_BODY_PARTS  # re-export for sdesc

# ---------------------------------------------------------------------------
# Tailored clothing layering keywords
# ---------------------------------------------------------------------------

_LAYER_KEYWORDS = {
    0: [
        "bikini", "panties", "underwear", "bra", "thong", "boxers", "g-string", "gstring",
        "sock", "stockings",
    ],
    # 1: default layer (everything else)
    2: ["blindfold", "glasses", "vest"],
    3: ["jacket", "waistcoat"],
    4: [
        "tailcoat", "coat", "labcoat", "topcoat", "overcoat", "longcoat", "greatcoat",
        "browncoat", "trenchcoat", "watchcoat", "trench", "robe", "habit", "muumuu",
        "hawaiian", "bolero", "apron", "scrubs", "bathrobe", "armband", "obi", "duster",
    ],
    5: [
        "tie", "boots", "cane", "umbrella", "blindfold", "habit", "shawl", "scarf",
        "armband", "necktie", "cummerbund", "belt", "veil", "parka", "balaclava",
        "bandana", "bandanna", "sticker", "badge",
    ],
}


def infer_clothing_layer(name: str) -> int:
    """
    Infer clothing layer (0-5) from the garment name using configured keywords.

    Default is layer 1 if no keyword matches.
    """
    if not name:
        return 1
    lower = str(name).lower()
    for layer, words in _LAYER_KEYWORDS.items():
        for w in words:
            if w in lower:
                return layer
    return 1


def get_covered_parts_set(character):
    """
    Return a set of body part keys covered by any worn clothing/armor.
    Used by sdesc to determine naked vs topless vs normally dressed.
    """
    worn = get_worn_items(character)
    covered = set()
    for item in worn:
        parts = getattr(item.db, "covered_parts", None) or []
        covered.update(p for p in parts if p in BODY_PARTS)
    return covered


def get_worn_items(character):
    """
    Return a list of objects currently worn by the character.
    Order: first = bottom layer, last = top layer (outermost).
    Uses character.db.worn (list of dbrefs or objects).
    """
    if not character:
        return []
    worn = character.db.worn
    if not worn:
        return []
    from evennia.utils.search import search_object
    out = []
    for ref in worn:
        if hasattr(ref, "db"):
            out.append(ref)
        else:
            try:
                ob = search_object(ref)
                # Only append if object exists, and location check does not error
                if ob and getattr(ob[0], "location", None) == character:
                    out.append(ob[0])
            except Exception as e:
                # Log the error to prevent silent swallowing
                from evennia.utils import logger
                logger.log_trace(f"get_worn_items: Error searching for worn ref '{ref}': {e}")
    return out



# Backward compatibility re-exports — appearance pipeline moved to world.appearance
from world.appearance import (  # noqa: F401
    get_effective_body_descriptions,
    format_body_appearance as format_body_appearance_from_parts,
)
