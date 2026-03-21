"""
Body part registry and body state queries.

Single source of truth for:
  - Display groupings (head/face, upper body, lower body)
  - Per-character body state inspection (missing, chrome, augmented, biological)
  - Effective anatomy queries (organs/bones accounting for chrome replacements)

Anatomical data (BODY_PARTS, organs, bones) lives in world.medical and is
re-exported here for convenience. All query functions are pure — they take
a character (or any object with the right db attributes) and return data.
"""

from world.medical import (
    BODY_PARTS,
    BODY_PARTS_HEAD_TO_FEET,
    BODY_PART_ALIASES,
    BODY_PART_BONES,
    BODY_PART_ORGANS,
)
from world.races import get_race_body_parts

# Re-export so consumers can import everything body-related from one place.
__all__ = [
    "BODY_PARTS",
    "BODY_PARTS_HEAD_TO_FEET",
    "BODY_PART_ALIASES",
    "BODY_PART_BONES",
    "BODY_PART_ORGANS",
    "HEAD_FACE",
    "UPPER_BODY",
    "LOWER_BODY",
    "BODY_PART_GROUPS",
    "UPPER_BODY_PARTS",
    "get_character_body_parts",
    "preview_body_parts_for_cyberware_install",
    "commit_adds_body_parts",
    "cleanup_adds_body_parts_on_remove",
    "body_part_groups_for_character",
    "is_part_present",
    "is_part_chrome",
    "is_part_augmented",
    "get_part_state",
    "get_effective_organs",
    "get_effective_bones",
    "get_chrome_parts",
    "get_missing_parts",
    "get_cyberware_for_part",
]


def get_character_body_parts(character):
    """
    Return the full body part list for this character: race anatomy plus any
    character-specific parts from cyberware (db.extra_body_parts).
    """
    if character is None:
        from world.medical import BODY_PARTS as _BP

        return list(_BP)
    race = getattr(getattr(character, "db", None), "race", None) or "human"
    parts = list(get_race_body_parts(race))
    seen = set(parts)
    for part in getattr(getattr(character, "db", None), "extra_body_parts", None) or []:
        if part not in seen:
            parts.append(part)
            seen.add(part)
    return parts


def preview_body_parts_for_cyberware_install(character, cyberware_obj):
    """
    Union of current anatomy and adds_body_parts on the installing object.
    Used to validate body_mods before committing extra_body_parts.
    """
    preview = set(get_character_body_parts(character))
    for part in getattr(cyberware_obj, "adds_body_parts", None) or []:
        preview.add(part)
    return preview


def commit_adds_body_parts(character, cyberware_obj):
    """
    Append race-missing parts from adds_body_parts to db.extra_body_parts.
    No-op for parts already present from race or extras.
    """
    adds = list(getattr(cyberware_obj, "adds_body_parts", None) or [])
    if not adds:
        return
    race = getattr(getattr(character, "db", None), "race", None) or "human"
    race_parts = set(get_race_body_parts(race))
    extras = list(getattr(character.db, "extra_body_parts", None) or [])
    changed = False
    for part in adds:
        if part in race_parts:
            continue
        if part not in extras:
            extras.append(part)
            changed = True
    if changed:
        character.db.extra_body_parts = extras


def cleanup_adds_body_parts_on_remove(character, removed_cyberware_obj, remaining_installed):
    """
    After uninstall: if no other installed cyberware still adds a part, remove it
    from extra_body_parts and drop body_descriptions for that part.
    """
    adds = list(getattr(removed_cyberware_obj, "adds_body_parts", None) or [])
    if not adds:
        return
    for part in adds:
        other_adds = any(
            part in (getattr(cw, "adds_body_parts", None) or [])
            for cw in remaining_installed
        )
        if other_adds:
            continue
        extras = list(getattr(character.db, "extra_body_parts", None) or [])
        if part in extras:
            extras.remove(part)
            character.db.extra_body_parts = extras
        descs = dict(getattr(character.db, "body_descriptions", None) or {})
        if part in descs:
            del descs[part]
            character.db.body_descriptions = descs

# ── Display groupings (canonical, defined once) ──────────────────────────
HEAD_FACE = ("head", "face", "left eye", "right eye", "left ear", "right ear", "neck")
UPPER_BODY = (
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
LOWER_BODY = ("groin", "left thigh", "right thigh", "left foot", "right foot")
BODY_PART_GROUPS = (HEAD_FACE, UPPER_BODY, LOWER_BODY)

# Alias used by sdesc to detect naked/topless state.
UPPER_BODY_PARTS = UPPER_BODY


def body_part_groups_for_character(character):
    """
    Display groups for look/appearance: tail is shown immediately after abdomen when present.
    """
    if not character:
        return BODY_PART_GROUPS
    parts = get_character_body_parts(character)
    if "tail" not in parts:
        return BODY_PART_GROUPS
    up = list(UPPER_BODY)
    if "abdomen" in up:
        up.insert(up.index("abdomen") + 1, "tail")
    else:
        up.append("tail")
    return (HEAD_FACE, tuple(up), LOWER_BODY)


# ── State queries ────────────────────────────────────────────────────────

def is_part_present(character, part):
    """True if this body part has not been severed."""
    missing = getattr(character.db, "missing_body_parts", None) or []
    return part not in missing


def is_part_chrome(character, part):
    """
    True if installed cyberware fully replaces this body part (lock mode).
    A locked part has no biological tissue — no organs, no bones.
    """
    locked = getattr(character.db, "locked_descriptions", None) or {}
    return part in locked


def is_part_augmented(character, part):
    """
    True if installed cyberware appends to this body part without replacing it.
    The part is still biological but has chrome additions (subdermal plating, etc.).
    """
    appended = getattr(character.db, "appended_descriptions", None) or {}
    return bool(appended.get(part))


def get_part_state(character, part):
    """
    Return a string summarising this body part's state:
    "missing", "chrome", "augmented", or "biological".

    Precedence: missing > chrome > augmented > biological.
    """
    if not is_part_present(character, part):
        return "missing"
    if is_part_chrome(character, part):
        return "chrome"
    if is_part_augmented(character, part):
        return "augmented"
    return "biological"


def get_effective_organs(character, part):
    """
    Return list of organ keys for this body part, accounting for chrome.
    A fully chrome (locked) part has no biological organs.
    A missing part has no organs.
    An augmented part still has its organs (chrome is additive).
    """
    state = get_part_state(character, part)
    if state in ("missing", "chrome"):
        return []
    return list(BODY_PART_ORGANS.get(part, []))


def get_effective_bones(character, part):
    """
    Return list of bone keys for this body part, accounting for chrome.
    Same rules as organs: chrome/missing parts have no biological bones.
    """
    state = get_part_state(character, part)
    if state in ("missing", "chrome"):
        return []
    return list(BODY_PART_BONES.get(part, []))


def get_chrome_parts(character):
    """Return set of body part keys that are fully replaced by cyberware."""
    locked = getattr(character.db, "locked_descriptions", None) or {}
    return set(locked.keys())


def get_missing_parts(character):
    """Return set of body part keys that have been severed."""
    return set(getattr(character.db, "missing_body_parts", None) or [])


def get_cyberware_for_part(character, part):
    """
    Return list of installed cyberware objects that affect this body part
    (either lock or append mode). Useful for damage routing, EMP effects,
    and armor contribution queries.
    """
    result = []
    for cw in (getattr(character.db, "cyberware", None) or []):
        mods = getattr(cw, "body_mods", None) or {}
        if part in mods:
            result.append(cw)
    return result
