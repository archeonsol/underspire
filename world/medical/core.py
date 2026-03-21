"""
Core medical primitives with no sibling imports.
"""
import time

TREATMENT_QUALITY_LABELS = {
    0: "untreated",
    1: "field",
    2: "clinical",
    3: "surgical",
}

ORGAN_MECHANICAL_EFFECTS = {
    "lungs": {"atk": -2, "def": -2, "stamina_recovery": -1},
    "heart": {"atk": -2, "def": -2, "bleed_resistance": -0.08},
    "brain": {"atk": -3, "def": -1},
    "spine_cord": {"atk": -1, "def": -3},
    "eyes": {"atk": -2, "def": -1},
    "liver": {"atk": -1, "def": -1},
    "kidneys": {"atk": -1, "def": -1},
}


def _ensure_medical_db(character):
    """
    Ensure medical attributes exist only.
    Intentionally does NOT run normalization/rebuild passes.
    """
    if character.db.organ_damage is None:
        character.db.organ_damage = {}
    if character.db.limb_damage is None:
        character.db.limb_damage = {}
    if character.db.fractures is None:
        character.db.fractures = []
    if character.db.bleeding_level is None:
        character.db.bleeding_level = 0
    if character.db.splinted_bones is None:
        character.db.splinted_bones = []
    if character.db.stabilized_organs is None:
        character.db.stabilized_organs = {}
    if character.db.bandaged_body_parts is None:
        character.db.bandaged_body_parts = []
    if character.db.injuries is None:
        character.db.injuries = []


def _injury_type_for_weapon(weapon_key, weapon_obj=None):
    if weapon_key == "surgery":
        return "surgery"
    from world.combat.damage_types import get_damage_type, DAMAGE_TYPE_TO_INJURY_TYPE
    return DAMAGE_TYPE_TO_INJURY_TYPE.get(get_damage_type(weapon_key, weapon_obj), "trauma")


def _cardiovascular_resistance(character, organ_damage=None):
    """
    Better endurance makes severe bleeding harder.
    Heart trauma lowers resistance (bleeds worsen).
    """
    try:
        from world.levels import level_to_effective_grade, letter_to_level_range, MAX_STAT_LEVEL
        end = (character.db.stats or {}).get("endurance", 0)
        if isinstance(end, str):
            lo, hi = letter_to_level_range(end.upper(), MAX_STAT_LEVEL)
            end = (lo + hi) // 2
        val = level_to_effective_grade(end if isinstance(end, int) else 0, MAX_STAT_LEVEL)
        base = 1.0 - (val - 5) * 0.02
    except Exception:
        base = 1.0
    od = organ_damage or (getattr(character.db, "organ_damage", None) or {})
    heart_sev = int(od.get("heart", 0) or 0)
    # Lower resistance => easier bleeding.
    return max(0.6, base - (0.08 * heart_sev))
