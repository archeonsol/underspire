"""
Race registry: body part lists, armor slots, chargen hooks, description rules.

Race is structural (anatomy, fit, appearance), not a stat block.
Combat/medical hit locations still use world.medical.BODY_PARTS only.
"""

from __future__ import annotations

from world.medical import BODY_PARTS

# Default armor-coverable slots (before race extras). Same keys as baseline anatomy.
ARMOR_SLOTS = list(BODY_PARTS)

# Optional defaults for race-specific parts (future use).
RACE_DEFAULT_DESCRIPTIONS: dict[str, dict[str, str]] = {}

RACES = {
    "human": {
        "key": "human",
        "name": "Human",
        "body_parts": None,
        "extra_body_parts": [],
        "chargen_questions": [],
        "description_rules": {},
        "armor_slots": None,
        "extra_armor_slots": [],
    },
    "splicer": {
        "key": "splicer",
        "name": "Splicer",
        "body_parts": None,
        "extra_body_parts": ["tail"],
        "chargen_questions": ["node_splicer_animal"],
        "description_rules": {
            "tail": "always_visible",
        },
        "armor_slots": None,
        "extra_armor_slots": ["tail"],
    },
}


def get_race(key):
    """Look up a race by key (case-insensitive). Returns dict or None."""
    return RACES.get((key or "").strip().lower())


def get_race_body_parts(key):
    """
    Return the full list of body parts for a race.
    Combines the default body parts with any race-specific extras.
    """
    race = get_race(key)
    if not race:
        return list(BODY_PARTS)
    base = list(BODY_PARTS) if race["body_parts"] is None else list(race["body_parts"])
    extras = race.get("extra_body_parts") or []
    for part in extras:
        if part not in base:
            base.append(part)
    return base


def get_race_armor_slots(key):
    """
    Return the full list of armor-coverable slots for a race.
    """
    race = get_race(key)
    if not race:
        return list(ARMOR_SLOTS)
    base = list(ARMOR_SLOTS) if race["armor_slots"] is None else list(race["armor_slots"])
    extras = race.get("extra_armor_slots") or []
    for slot in extras:
        if slot not in base:
            base.append(slot)
    return base


def _compute_all_coverable_body_parts() -> frozenset[str]:
    """Union of BODY_PARTS and every race extra armor slot (for clothing/armor filtering)."""
    parts = set(BODY_PARTS)
    for race in RACES.values():
        if race.get("armor_slots") is not None:
            parts.update(race["armor_slots"])
        parts.update(race.get("extra_armor_slots") or [])
    return frozenset(parts)


ALL_COVERABLE_BODY_PARTS = _compute_all_coverable_body_parts()
