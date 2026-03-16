"""
Damage type system: slashing, impact, penetrating, burn, freeze, arc, void.

Replaces 'magical' with four elemental/energy types appropriate to the arcanepunk setting:
  - burn      : thermal plasma, fire-energy weapons, meltdown effects
  - freeze    : cryo weapons, cold-containment cells
  - arc       : electrical discharge, shock weapons, gauss arc-bleed
  - void      : eldritch dissolution, Deep Accord Inquisitorial weapons

Damage type drives trauma multipliers, injury wording, and future resistance tables.
Individual weapons can override via db.damage_type.
Ranged gauss weapons still use 'penetrating' (physical kinetic); energy cells use burn/void.
"""

# ── Canonical combat damage types ───────────────────────────────────────────
DAMAGE_TYPES = (
    "slashing",
    "impact",
    "penetrating",
    "burn",
    "freeze",
    "arc",
    "void",
)

# Armour-only environmental types (fire→now 'burn' in DAMAGE_TYPES; radiation kept here)
ARMOR_EXTRA_DAMAGE_TYPES = ("radiation",)

# ── Weapon key → default damage type ────────────────────────────────────────
# Each weapon object may override via db.damage_type.
WEAPON_KEY_TO_DAMAGE_TYPE = {
    # Melee
    "fists":       "impact",
    "knife":       "slashing",
    "long_blade":  "slashing",
    "blunt":       "impact",
    # Ranged (kinetic)
    "sidearm":     "penetrating",
    "longarm":     "penetrating",
    "automatic":   "penetrating",
    # Creature moves
    "claws":       "slashing",
    "bite":        "penetrating",
    "saw":         "slashing",
    "gouge":       "penetrating",
    # Creature elemental moves
    "acid_spit":   "burn",
    "frost_breath":"freeze",
    "shock_lash":  "arc",
    # Eldritch / void-tainted creatures
    "void_rend":   "void",
    "void_pulse":  "void",
}

# ── Damage type → injury display key ────────────────────────────────────────
# Used by INJURY_SEVERITY_WORDING and body part trauma descriptions.
DAMAGE_TYPE_TO_INJURY_TYPE = {
    "slashing":    "cut",
    "impact":      "bruise",
    "penetrating": "gunshot",
    "burn":        "burn",
    "freeze":      "frostbite",
    "arc":         "electrocution",
    "void":        "dissolution",
}

# ── Body part → region ───────────────────────────────────────────────────────
BODY_PART_TO_REGION = {
    "head":           "head",
    "face":           "head",
    "neck":           "neck",
    "torso":          "torso",
    "back":           "torso",
    "abdomen":        "abdomen",
    "groin":          "groin",
    "left shoulder":  "arm",
    "right shoulder": "arm",
    "left arm":       "arm",
    "right arm":      "arm",
    "left hand":      "hand",
    "right hand":     "hand",
    "left thigh":     "leg",
    "right thigh":    "leg",
    "left foot":      "foot",
    "right foot":     "foot",
}

REGIONS = ("head", "neck", "torso", "abdomen", "groin", "arm", "hand", "leg", "foot")


# ── Trauma multiplier table ──────────────────────────────────────────────────
def _trauma_table(rows):
    """Build {damage_type: {region: mult}} from (damage_type, region, bleed, fracture, organ)."""
    bleed, fracture, organ = {}, {}, {}
    for dt, region, b, f, o in rows:
        bleed.setdefault(dt, {})[region] = b
        fracture.setdefault(dt, {})[region] = f
        organ.setdefault(dt, {})[region] = o
    return bleed, fracture, organ


_TRAUMA_ROWS = [
    # ── slashing: high bleed neck/groin/head; low fracture; organ on core/neck ──
    ("slashing", "head",    1.65, 0.45, 0.55),
    ("slashing", "neck",    1.95, 0.35, 1.05),
    ("slashing", "torso",   1.35, 0.45, 0.95),
    ("slashing", "abdomen", 1.45, 0.40, 1.00),
    ("slashing", "groin",   1.90, 0.40, 0.90),
    ("slashing", "arm",     1.25, 0.40, 0.30),
    ("slashing", "hand",    0.60, 0.45, 0.15),
    ("slashing", "leg",     1.25, 0.40, 0.30),
    ("slashing", "foot",    0.60, 0.45, 0.15),

    # ── impact: high fracture on head/limbs/torso; organ on head/torso; low bleed ──
    ("impact", "head",    0.70, 1.85, 1.45),
    ("impact", "neck",    0.60, 1.25, 0.95),
    ("impact", "torso",   0.50, 1.70, 1.35),
    ("impact", "abdomen", 0.60, 1.25, 1.45),
    ("impact", "groin",   0.55, 1.55, 1.05),
    ("impact", "arm",     0.50, 1.85, 0.50),
    ("impact", "hand",    0.60, 1.60, 0.30),
    ("impact", "leg",     0.50, 1.85, 0.50),
    ("impact", "foot",    0.55, 1.55, 0.30),

    # ── penetrating: high organ on core/neck/head; bleed neck/groin/abdomen ──
    ("penetrating", "head",    1.05, 0.50, 1.35),
    ("penetrating", "neck",    1.60, 0.35, 1.50),
    ("penetrating", "torso",   1.25, 0.40, 1.45),
    ("penetrating", "abdomen", 1.35, 0.35, 1.55),
    ("penetrating", "groin",   1.50, 0.45, 1.25),
    ("penetrating", "arm",     1.15, 0.55, 0.65),
    ("penetrating", "hand",    0.85, 0.60, 0.25),
    ("penetrating", "leg",     1.15, 0.55, 0.65),
    ("penetrating", "foot",    0.85, 0.55, 0.25),

    # ── burn: cauterises (low bleed); very high organ; moderate fracture (bone-crack) ──
    ("burn", "head",    0.35, 0.90, 1.60),
    ("burn", "neck",    0.30, 0.70, 1.75),
    ("burn", "torso",   0.35, 0.80, 1.65),
    ("burn", "abdomen", 0.40, 0.75, 1.70),
    ("burn", "groin",   0.35, 0.85, 1.50),
    ("burn", "arm",     0.40, 1.05, 0.80),
    ("burn", "hand",    0.45, 1.10, 0.45),
    ("burn", "leg",     0.40, 1.05, 0.80),
    ("burn", "foot",    0.45, 1.10, 0.40),

    # ── freeze: near-zero bleed (frozen solid); very high fracture (brittle tissue); moderate organ ──
    ("freeze", "head",    0.15, 2.10, 1.10),
    ("freeze", "neck",    0.20, 1.80, 0.90),
    ("freeze", "torso",   0.20, 1.95, 1.00),
    ("freeze", "abdomen", 0.25, 1.70, 1.05),
    ("freeze", "groin",   0.20, 1.85, 0.85),
    ("freeze", "arm",     0.20, 2.20, 0.55),
    ("freeze", "hand",    0.15, 2.30, 0.30),
    ("freeze", "leg",     0.20, 2.20, 0.55),
    ("freeze", "foot",    0.15, 2.25, 0.35),

    # ── arc: low bleed (cauterised nerves); low fracture; very high organ (cardiac/neural) ──
    ("arc", "head",    0.55, 0.45, 2.10),
    ("arc", "neck",    0.65, 0.40, 2.00),
    ("arc", "torso",   0.50, 0.50, 1.90),
    ("arc", "abdomen", 0.60, 0.45, 1.80),
    ("arc", "groin",   0.55, 0.50, 1.70),
    ("arc", "arm",     0.65, 0.55, 1.10),
    ("arc", "hand",    0.55, 0.60, 0.75),
    ("arc", "leg",     0.65, 0.55, 1.10),
    ("arc", "foot",    0.50, 0.60, 0.70),

    # ── void: wounds that don't bleed right (moderate bleed, delayed); low fracture; very high organ ──
    # Dissolution unmakes tissue from within — organ damage is highest of all types.
    ("void", "head",    0.80, 0.40, 2.20),
    ("void", "neck",    0.90, 0.35, 2.15),
    ("void", "torso",   0.85, 0.40, 2.10),
    ("void", "abdomen", 0.95, 0.35, 2.20),
    ("void", "groin",   0.90, 0.40, 1.95),
    ("void", "arm",     0.75, 0.45, 1.30),
    ("void", "hand",    0.60, 0.50, 0.90),
    ("void", "leg",     0.75, 0.45, 1.30),
    ("void", "foot",    0.60, 0.50, 0.85),
]

(
    TRAUMA_BLEED_MULT_BY_REGION,
    TRAUMA_FRACTURE_MULT_BY_REGION,
    TRAUMA_ORGAN_MULT_BY_REGION,
) = _trauma_table(_TRAUMA_ROWS)


def get_trauma_multipliers(damage_type, body_part):
    """
    Return (bleed_mult, fracture_mult, organ_mult) for this damage type and body part.
    Falls back to region 'torso' for unknown body parts, 1.0 for unknown damage type.
    """
    region = BODY_PART_TO_REGION.get(body_part, "torso")
    bleed    = (TRAUMA_BLEED_MULT_BY_REGION.get(damage_type)    or {}).get(region, 1.0)
    fracture = (TRAUMA_FRACTURE_MULT_BY_REGION.get(damage_type) or {}).get(region, 1.0)
    organ    = (TRAUMA_ORGAN_MULT_BY_REGION.get(damage_type)    or {}).get(region, 1.0)
    return bleed, fracture, organ


def get_damage_type(weapon_key, weapon_obj=None):
    """
    Resolve damage type for trauma and injury.
    Uses weapon_obj.db.damage_type if set and valid, else WEAPON_KEY_TO_DAMAGE_TYPE.
    Fallback: 'impact'.
    """
    if weapon_obj and getattr(weapon_obj.db, "damage_type", None):
        dt = weapon_obj.db.damage_type
        if dt in DAMAGE_TYPES:
            return dt
    return WEAPON_KEY_TO_DAMAGE_TYPE.get(weapon_key, "impact")
