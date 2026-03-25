"""
Character appearance pipeline: assembles per-body-part descriptions
from naked text, cyberware, injuries, medical treatment, and clothing.

Each layer can be extended independently. The pipeline order:
  1. Missing check — if part is missing, use existing stump text, skip layers 2-4
  2. Cyberware: lock replaces naked entirely; append adds after
  3. Untreated injury lines (from db.injuries via get_untreated_injuries_by_part)
  4. Treatment descriptors (bandage / splint / stabilized organ)
  5. Worn clothing (outermost non-see-thru wins, replaces all above)

Skin tone and chrome colors are applied at render time (see world.skin_tones).
"""

from world.body import body_part_groups_for_character, get_character_body_parts, get_part_state, is_part_present
from world.medical import (
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
    if part in ("head", "face", "neck", "left eye", "right eye", "left ear", "right ear"):
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
    if part in ("face", "left eye", "right eye", "left ear", "right ear"):
        return f"{poss.capitalize()} face and sensory areas show stitches and signs of recent surgery."
    if part == "neck":
        return f"{poss.capitalize()} neck shows stitches and signs of recent surgery."
    if part == "groin":
        return f"{poss.capitalize()} pelvic region shows signs of recent surgery."
    if "shoulder" in part:
        return f"{poss.capitalize()} {part} area shows signs of recent surgery."
    return f"{poss.capitalize()} {part} shows signs of recent surgery."


def _treatment_segments(part, character, bandaged, splinted_bones, stabilized_organs, poss):
    """Return list of treatment descriptor strings for this part."""
    segs = []
    if part in bandaged:
        segs.append(_bandaged_desc(part, poss))
    part_bones = BODY_PART_BONES.get(part, [])
    if any(b in splinted_bones for b in part_bones):
        segs.append(_splinted_desc(part, poss))
    part_organs = BODY_PART_ORGANS.get(part, [])
    if any(org in stabilized_organs for org in part_organs):
        segs.append(_stabilized_organ_desc(part, poss))
    return segs


def _injury_segment(character, part, untreated_by_part):
    part_injuries = untreated_by_part.get(part) or []
    if not part_injuries:
        return ""
    injury_line = format_body_part_injuries(character, part, part_injuries)
    return (injury_line or "").strip()


def get_effective_body_descriptions(character):
    """
    Return dict of body_part -> description string for look/appearance.

    Pipeline per part:
      1. Start with naked text (db.body_descriptions)
      2. If part is missing, keep stump text and skip cyberware/injury/treatment
      3. Cyberware lock replaces naked; append adds after
      4. Untreated injury lines
      5. Treatment descriptors (bandaged/splinted/organ-stabilized)
      6. Worn clothing overlay (outermost non-see-thru wins) — not skin-toned
    """
    from world.clothing import get_worn_items
    from world.rpg.crafting import substitute_clothing_desc
    from world.skin_tones import (
        apply_skin_tone_to_bio_text,
        cyberware_by_typeclass_path,
        locking_cyberware_for_part,
        render_chrome_description,
    )

    raw_body = getattr(character.db, "body_descriptions", None) or {}
    untreated_by_part = get_untreated_injuries_by_part(character)
    bandaged = getattr(character.db, "bandaged_body_parts", None) or []
    splinted_bones = getattr(character.db, "splinted_bones", None) or []
    stabilized_organs = getattr(character.db, "stabilized_organs", None) or {}
    _, poss = _pronoun_sub_poss(character)
    locked = getattr(character.db, "locked_descriptions", None) or {}
    appended = getattr(character.db, "appended_descriptions", None) or {}

    result = {}

    for part in get_character_body_parts(character):
        missing = not is_part_present(character, part)
        base_naked = (raw_body.get(part) or "").strip()

        if missing:
            result[part] = base_naked
            continue

        injury_seg = _injury_segment(character, part, untreated_by_part)
        treat_segs = _treatment_segments(part, character, bandaged, splinted_bones, stabilized_organs, poss)

        if part in locked:
            cw = locking_cyberware_for_part(character, part)
            chrome_block = render_chrome_description(cw, part) if cw else ""
            if not chrome_block.strip():
                lt = (locked.get(part) or "").strip()
                from world.skin_tones import CHROME_DESC_COLOR
                if lt:
                    chrome_block = f"{CHROME_DESC_COLOR}{lt}|n"
            bio_bits = []
            if injury_seg:
                bio_bits.append(injury_seg)
            bio_bits.extend(treat_segs)
            bio_joined = " ".join(bio_bits).strip()
            if bio_joined:
                bio_colored = apply_skin_tone_to_bio_text(character, bio_joined, part=part)
                result[part] = f"{chrome_block} {bio_colored}".strip() if chrome_block else bio_colored
            else:
                result[part] = chrome_block
            continue

        part_appends = appended.get(part, {}) or {}
        chrome_fragments = []
        for path in part_appends:
            cw = cyberware_by_typeclass_path(character, path)
            if cw:
                frag = render_chrome_description(cw, part)
            else:
                from world.skin_tones import CHROME_DESC_COLOR
                txt = (part_appends.get(path) or "").strip()
                frag = f"{CHROME_DESC_COLOR}{txt}|n" if txt else ""
            if frag:
                chrome_fragments.append(frag)

        bio_bits = [base_naked] if base_naked else []
        if injury_seg:
            bio_bits.append(injury_seg)
        bio_bits.extend(treat_segs)
        bio_plain = " ".join(bio_bits).strip()

        if chrome_fragments:
            bio_colored = apply_skin_tone_to_bio_text(character, bio_plain, part=part) if bio_plain else ""
            chrome_joined = " ".join(chrome_fragments)
            if bio_colored:
                result[part] = f"{bio_colored} {chrome_joined}".strip()
            else:
                result[part] = chrome_joined
        else:
            result[part] = apply_skin_tone_to_bio_text(character, bio_plain, part=part) if bio_plain else ""

    # Layer 5: Clothing — replace covered parts with uncolored worn description
    worn = get_worn_items(character)
    for item in reversed(worn):
        covered = getattr(item.db, "covered_parts", None) or []
        raw_desc = (getattr(item.db, "worn_desc", None) or "").strip()
        if not raw_desc:
            continue
        desc = substitute_clothing_desc(raw_desc, character)
        for part in covered:
            if part in result and not getattr(item.db, "see_thru", False):
                result[part] = desc

    # Layer 6: Tattoos — permanent marks appended after clothing
    try:
        from world.cosmetics.tattoos import get_tattoo_display_for_part
        for part in list(result.keys()):
            tattoo_text = get_tattoo_display_for_part(character, part)
            if tattoo_text:
                existing = result[part]
                result[part] = (existing + " " + tattoo_text).strip() if existing else tattoo_text
    except Exception:
        pass

    # Layer 7: Makeup — temporary surface cosmetics appended last
    try:
        from world.cosmetics.makeup import get_makeup_display_for_part
        for part in list(result.keys()):
            makeup_text = get_makeup_display_for_part(character, part)
            if makeup_text:
                existing = result[part]
                result[part] = (existing + " " + makeup_text).strip() if existing else makeup_text
    except Exception:
        pass

    return result


def format_body_appearance(parts_dict, character=None):
    """
    Merge body-part descriptions into three paragraphs (head/face, upper body, lower body).
    Identical descriptions within a region are shown once (first occurrence order) so a
    garment covering e.g. torso+shoulders doesn't repeat.
    When character is set, race-specific display order applies (e.g. tail after abdomen).
    """
    if not parts_dict:
        return ""
    paragraphs = []
    groups = body_part_groups_for_character(character)
    for group in groups:
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
