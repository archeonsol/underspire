"""
Clothing system: dynamic coverage of body parts.
Clothing and armor define which body parts they cover; when worn, their
description replaces those parts in the character's look. Uncovered parts
use the character's normal body description.
"""
from world.medical import (
    BODY_PARTS,
    BODY_PART_BONES,
    BODY_PART_ORGANS,
    _pronoun_sub_poss,
    format_body_part_injuries,
    get_untreated_injuries_by_part,
)
from world.rpg.crafting import substitute_clothing_desc

# Class-level constants for body part groups (for merging look paragraphs)
_HEAD_FACE = ("head", "face", "left eye", "right eye", "neck")
_UPPER_BODY = (
    "left shoulder",
    "right shoulder",
    "left arm",
    "right arm",
    "left hand",
    "right hand",
    "torso",
    "back",
    "abdomen",
)
_LOWER_BODY = (
    "groin",
    "left thigh",
    "right thigh",
    "left foot",
    "right foot",
)
_BODY_PART_GROUPS = (_HEAD_FACE, _UPPER_BODY, _LOWER_BODY)

# For sdesc clothing state: upper body = shirt/torso coverage; if none covered → "topless"
UPPER_BODY_PARTS = _UPPER_BODY

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


def _bandaged_desc(part, poss):
    """One-line bandage descriptor for a body part; pronoun-aware (poss = their/his/her)."""
    limb_like = ("left arm", "right arm", "left hand", "right hand", "left thigh", "right thigh", "left foot", "right foot", "left shoulder", "right shoulder")
    if part in limb_like:
        return f"Bandages are wrapped around {poss} {part}."
    if part == "torso":
        return f"{poss.capitalize()} chest is bound with bandages."
    if part == "back":
        return f"{poss.capitalize()} back is bound with bandages."
    if part == "abdomen":
        return f"{poss.capitalize()} abdomen is wrapped and bound."
    if part in ("head", "face", "neck", "left eye", "right eye"):
        return f"{poss.capitalize()} {part} is bandaged."
    if part == "groin":
        return f"{poss.capitalize()} groin is bandaged."
    return f"Bandages cover {poss} {part}."


def _splinted_desc(part, poss):
    """One-line splint descriptor for a body part; pronoun-aware."""
    limb_like = ("left arm", "right arm", "left hand", "right hand", "left thigh", "right thigh", "left foot", "right foot", "left shoulder", "right shoulder")
    if part in limb_like:
        return f"{poss.capitalize()} {part} is splinted and bound."
    if part == "torso":
        return f"{poss.capitalize()} chest is bound and immobilized."
    if part == "back":
        return f"{poss.capitalize()} back is immobilized (spine supported)."
    if part == "abdomen":
        return f"{poss.capitalize()} ribs are bound; breathing is shallow."
    if part == "head":
        return f"{poss.capitalize()} head is braced (skull/neck)."
    if part == "face":
        return f"{poss.capitalize()} face or jaw is immobilized."
    if part == "neck":
        return f"{poss.capitalize()} neck is immobilized (c-spine)."
    if part == "groin":
        return f"{poss.capitalize()} pelvis is braced."
    return f"{poss.capitalize()} {part} is splinted."


def _stabilized_organ_desc(part, poss):
    """One-line descriptor when internal organ(s) on this body part have been treated (surgery/closure); pronoun-aware."""
    if part == "torso":
        return f"{poss.capitalize()} chest shows signs of recent surgery."
    if part == "back":
        return f"{poss.capitalize()} back and spinal area show stitches and signs of recent surgery."
    if part == "abdomen":
        return f"{poss.capitalize()} abdomen shows signs of recent surgery."
    if part == "head":
        return f"{poss.capitalize()} head shows signs of recent surgery."
    if part in ("face", "left eye", "right eye"):
        return f"{poss.capitalize()} face or eyes show stitches and signs of recent surgery."
    if part == "neck":
        return f"{poss.capitalize()} neck shows stitches and signs of recent surgery."
    if part == "groin":
        return f"{poss.capitalize()} pelvic region shows signs of recent surgery."
    if "shoulder" in part:
        return f"{poss.capitalize()} {part} area shows signs of recent surgery."
    return f"{poss.capitalize()} {part} shows signs of recent surgery."


def get_effective_body_descriptions(character):
    """
    Return dict of body_part -> description string for look/appearance.
    For each body part: if a worn item covers it, use that item's description;
    otherwise use body_descriptions[part] + wound lines (untreated only) + treated descs (bandaged/splinted/organ-stabilized).
    Treated descs are shown whenever the part has any treatment state; they disappear when that treatment no longer applies.
    Topmost (last worn) item wins for each part.
    """
    result = {}
    raw_body = getattr(character.db, "body_descriptions", None) or {}
    untreated_by_part = get_untreated_injuries_by_part(character)
    bandaged = getattr(character.db, "bandaged_body_parts", None) or []
    splinted_bones = getattr(character.db, "splinted_bones", None) or []
    stabilized_organs = getattr(character.db, "stabilized_organs", None) or {}
    _, poss = _pronoun_sub_poss(character)
    locked = getattr(character.db, "locked_descriptions", None) or {}
    appended = getattr(character.db, "appended_descriptions", None) or {}
    for part in BODY_PARTS:
        text = (raw_body.get(part) or "").strip()
        # Cyberware layers: locked replaces user text entirely; appended adds to it.
        if part in locked:
            text = locked[part]
        else:
            part_appends = appended.get(part, {})
            if part_appends:
                text = (text + " " + " ".join(part_appends.values())).strip()
        # Wound lines: only for untreated injuries on this part
        part_injuries = untreated_by_part.get(part) or []
        if part_injuries:
            injury_line = format_body_part_injuries(character, part, part_injuries)
            if injury_line:
                text = (text + " " + injury_line).strip()
        # Treated descs: show when this part has any treatment (bandaged, splinted, or organ-stabilized)
        if part in bandaged:
            text = (text + " " + _bandaged_desc(part, poss)).strip()
        part_bones = BODY_PART_BONES.get(part, [])
        if any(b in splinted_bones for b in part_bones):
            text = (text + " " + _splinted_desc(part, poss)).strip()
        part_organs = BODY_PART_ORGANS.get(part, [])
        if any(org in stabilized_organs for org in part_organs):
            text = (text + " " + _stabilized_organ_desc(part, poss)).strip()
        result[part] = text

    worn = get_worn_items(character)
    # Topmost item for each part should win, so iterate in reversed order.
    # Items marked see_thru do not replace underlying body/clothing text.
    for item in reversed(worn):
        covered = getattr(item.db, "covered_parts", None) or []
        # Use worn_desc for body parts; fall back to main desc if worn_desc not set
        raw_desc = (getattr(item.db, "worn_desc", None) or getattr(item.db, "desc", None) or "").strip()
        if not raw_desc:
            continue
        desc = substitute_clothing_desc(raw_desc, character)
        for part in covered:
            if part in result and not getattr(item.db, "see_thru", False):
                result[part] = desc
    return result


def _body_part_groups():
    """
    (head_face, upper_body, lower_body) for merging look paragraphs.
    These are now class-level constants; this function is kept for backward compatibility.
    """
    return _BODY_PART_GROUPS


def format_body_appearance_from_parts(parts_dict):
    """
    Merge body-part descriptions into three paragraphs (head/face, upper, lower).
    parts_dict: body_part key -> description string. Used by Character and Corpse for look.
    """
    if not parts_dict:
        return ""
    head_face, upper_body, lower_body = _BODY_PART_GROUPS
    paragraphs = []
    for group in (head_face, upper_body, lower_body):
        # Using set to preserve order and uniqueness efficiently
        seen = set()
        bits = []
        for p in group:
            desc = (parts_dict.get(p) or "").strip()
            if desc and desc not in seen:
                bits.append(desc)
                seen.add(desc)
        if bits:
            paragraphs.append(" ".join(bits))
    return "\n\n".join(paragraphs) if paragraphs else ""
