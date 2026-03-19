"""
Character appearance pipeline: assembles per-body-part descriptions
from naked text, cyberware, injuries, medical treatment, and clothing.

Each layer can be extended independently. The pipeline order:
  1. Missing check — if part is missing, use existing stump text, skip layers 2-4
  2. Cyberware: lock replaces naked entirely; append adds after
  3. Untreated injury lines (from db.injuries via get_untreated_injuries_by_part)
  4. Treatment descriptors (bandage / splint / stabilized organ)
  5. Worn clothing (outermost non-see-thru wins, replaces all above)
"""

from world.body import BODY_PART_GROUPS, is_part_present
from world.medical import (
    BODY_PARTS,
    BODY_PART_BONES,
    BODY_PART_ORGANS,
    _pronoun_sub_poss,
    format_body_part_injuries,
    get_untreated_injuries_by_part,
)


# ── Treatment descriptors ────────────────────────────────────────────────

_LIMB_LIKE = frozenset((
    "left arm", "right arm", "left hand", "right hand",
    "left thigh", "right thigh", "left foot", "right foot",
    "left shoulder", "right shoulder",
))


def _bandaged_desc(part, poss):
    """One-line bandage descriptor for a body part; pronoun-aware (poss = their/his/her)."""
    if part in _LIMB_LIKE:
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
    if part in _LIMB_LIKE:
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


# ── Appearance pipeline ──────────────────────────────────────────────────

def get_effective_body_descriptions(character):
    """
    Return dict of body_part -> description string for look/appearance.

    Pipeline per part:
      1. Start with naked text (db.body_descriptions)
      2. If part is missing, keep stump text and skip cyberware/injury/treatment
      3. Cyberware lock replaces naked; cyberware append adds after
      4. Untreated injury lines
      5. Treatment descriptors (bandaged/splinted/organ-stabilized)
      6. Worn clothing overlay (outermost non-see-thru wins)
    """
    from world.clothing import get_worn_items
    from world.rpg.crafting import substitute_clothing_desc

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
        missing = not is_part_present(character, part)

        if not missing:
            # Layer 2: Cyberware — locked replaces user text entirely; appended adds.
            if part in locked:
                text = locked[part]
            else:
                part_appends = appended.get(part, {})
                if part_appends:
                    text = (text + " " + " ".join(part_appends.values())).strip()

            # Layer 3: Untreated injury lines
            part_injuries = untreated_by_part.get(part) or []
            if part_injuries:
                injury_line = format_body_part_injuries(character, part, part_injuries)
                if injury_line:
                    text = (text + " " + injury_line).strip()

            # Layer 4: Treatment descriptors
            if part in bandaged:
                text = (text + " " + _bandaged_desc(part, poss)).strip()
            part_bones = BODY_PART_BONES.get(part, [])
            if any(b in splinted_bones for b in part_bones):
                text = (text + " " + _splinted_desc(part, poss)).strip()
            part_organs = BODY_PART_ORGANS.get(part, [])
            if any(org in stabilized_organs for org in part_organs):
                text = (text + " " + _stabilized_organ_desc(part, poss)).strip()

        result[part] = text

    # Layer 5: Clothing overlay — outermost item wins for each covered part.
    worn = get_worn_items(character)
    for item in reversed(worn):
        covered = getattr(item.db, "covered_parts", None) or []
        # Only use worn_desc; do NOT fall back to db.desc (ground description).
        raw_desc = (getattr(item.db, "worn_desc", None) or "").strip()
        if not raw_desc:
            continue
        desc = substitute_clothing_desc(raw_desc, character)
        for part in covered:
            if part in result and not getattr(item.db, "see_thru", False):
                result[part] = desc
    return result


def format_body_appearance(parts_dict):
    """
    Merge body-part descriptions into three paragraphs (head/face, upper body, lower body).
    Identical descriptions within a region are shown once (first occurrence order) so a
    garment covering e.g. torso+shoulders doesn't repeat.
    """
    if not parts_dict:
        return ""
    paragraphs = []
    for group in BODY_PART_GROUPS:
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
