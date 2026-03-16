"""
Damage type system: slashing, impact, penetrating, magical.
Used by combat, medical trauma, and injury display. Weapon classes map to a damage type;
individual weapons can override via db.damage_type.
"""
# Canonical damage types (used for trauma multipliers, injury wording, future resistances)
DAMAGE_TYPES = ("slashing", "impact", "penetrating", "magical")

# Armor-only: environmental / non-physical (fire, radiation). Armor can protect vs these; combat may use later.
ARMOR_EXTRA_DAMAGE_TYPES = ("fire", "radiation")

# Weapon key (world.combat / world.skills / creature moves) -> damage type
WEAPON_KEY_TO_DAMAGE_TYPE = {
    "fists": "impact",
    "knife": "slashing",
    "long_blade": "slashing",
    "blunt": "impact",
    "sidearm": "penetrating",
    "longarm": "penetrating",
    "automatic": "penetrating",
    # Creature move weapon_key (for trauma)
    "claws": "slashing",
    "bite": "penetrating",
    "saw": "slashing",
    "gouge": "penetrating",
    "fire": "magical",
}

# Damage type -> injury type key (for INJURY_SEVERITY_WORDING, body part descriptions)
DAMAGE_TYPE_TO_INJURY_TYPE = {
    "slashing": "cut",
    "impact": "bruise",
    "penetrating": "gunshot",
    "magical": "arcane",
}

# -----------------------------------------------------------------------------
# Body part -> region (for damage type × region trauma tables)
# -----------------------------------------------------------------------------
BODY_PART_TO_REGION = {
    "head": "head",
    "face": "head",
    "neck": "neck",
    "torso": "torso",
    "back": "torso",
    "abdomen": "abdomen",
    "groin": "groin",
    "left shoulder": "arm",
    "right shoulder": "arm",
    "left arm": "arm",
    "right arm": "arm",
    "left hand": "hand",
    "right hand": "hand",
    "left thigh": "leg",
    "right thigh": "leg",
    "left foot": "foot",
    "right foot": "foot",
}

REGIONS = ("head", "neck", "torso", "abdomen", "groin", "arm", "hand", "leg", "foot")

# Trauma multipliers by (damage_type, region). Slashing: high bleed on neck/groin/head; impact: high fracture on limbs/torso/head; penetrating: high organ on core/neck.
# Fallback 1.0 for missing keys. Keys are damage_type -> region -> mult.
def _trauma_table(rows):
    """Build {damage_type: {region: mult}} from list of (damage_type, region, bleed, fracture, organ)."""
    bleed = {}
    fracture = {}
    organ = {}
    for dt, region, b, f, o in rows:
        bleed.setdefault(dt, {})[region] = b
        fracture.setdefault(dt, {})[region] = f
        organ.setdefault(dt, {})[region] = o
    return bleed, fracture, organ

_TRAUMA_ROWS = [
    # slashing: neck/groin/head = very high bleed; torso/limbs = moderate; hand/foot = low. Low fracture; organ on core/neck.
    ("slashing", "head", 1.65, 0.45, 0.55),
    ("slashing", "neck", 1.95, 0.35, 1.05),
    ("slashing", "torso", 1.35, 0.45, 0.95),
    ("slashing", "abdomen", 1.45, 0.40, 1.00),
    ("slashing", "groin", 1.90, 0.40, 0.90),
    ("slashing", "arm", 1.25, 0.40, 0.30),
    ("slashing", "hand", 0.60, 0.45, 0.15),
    ("slashing", "leg", 1.25, 0.40, 0.30),
    ("slashing", "foot", 0.60, 0.45, 0.15),
    # impact: fracture high on head/limbs/torso; organ on head/torso/abdomen; bleed low (internal/moderate).
    ("impact", "head", 0.70, 1.85, 1.45),
    ("impact", "neck", 0.60, 1.25, 0.95),
    ("impact", "torso", 0.50, 1.70, 1.35),
    ("impact", "abdomen", 0.60, 1.25, 1.45),
    ("impact", "groin", 0.55, 1.55, 1.05),
    ("impact", "arm", 0.50, 1.85, 0.50),
    ("impact", "hand", 0.60, 1.60, 0.30),
    ("impact", "leg", 0.50, 1.85, 0.50),
    ("impact", "foot", 0.55, 1.55, 0.30),
    # penetrating: organ high on core/neck/head; bleed moderate-high neck/groin/abdomen; fracture low, slightly higher on limbs.
    ("penetrating", "head", 1.05, 0.50, 1.35),
    ("penetrating", "neck", 1.60, 0.35, 1.50),
    ("penetrating", "torso", 1.25, 0.40, 1.45),
    ("penetrating", "abdomen", 1.35, 0.35, 1.55),
    ("penetrating", "groin", 1.50, 0.45, 1.25),
    ("penetrating", "arm", 1.15, 0.55, 0.65),
    ("penetrating", "hand", 0.85, 0.60, 0.25),
    ("penetrating", "leg", 1.15, 0.55, 0.65),
    ("penetrating", "foot", 0.85, 0.55, 0.25),
    # magical: placeholder flat
    ("magical", "head", 1.0, 1.0, 1.0),
    ("magical", "neck", 1.0, 1.0, 1.0),
    ("magical", "torso", 1.0, 1.0, 1.0),
    ("magical", "abdomen", 1.0, 1.0, 1.0),
    ("magical", "groin", 1.0, 1.0, 1.0),
    ("magical", "arm", 1.0, 1.0, 1.0),
    ("magical", "hand", 1.0, 1.0, 1.0),
    ("magical", "leg", 1.0, 1.0, 1.0),
    ("magical", "foot", 1.0, 1.0, 1.0),
]
TRAUMA_BLEED_MULT_BY_REGION, TRAUMA_FRACTURE_MULT_BY_REGION, TRAUMA_ORGAN_MULT_BY_REGION = _trauma_table(_TRAUMA_ROWS)


def get_trauma_multipliers(damage_type, body_part):
    """
    Return (bleed_mult, fracture_mult, organ_mult) for this damage type and body part.
    Uses body_part -> region mapping; fallback 1.0 for unknown region or damage type.
    """
    region = BODY_PART_TO_REGION.get(body_part, "torso")
    bleed = (TRAUMA_BLEED_MULT_BY_REGION.get(damage_type) or {}).get(region, 1.0)
    fracture = (TRAUMA_FRACTURE_MULT_BY_REGION.get(damage_type) or {}).get(region, 1.0)
    organ = (TRAUMA_ORGAN_MULT_BY_REGION.get(damage_type) or {}).get(region, 1.0)
    return bleed, fracture, organ


def get_damage_type(weapon_key, weapon_obj=None):
    """
    Resolve damage type for trauma and injury. Use weapon_obj.db.damage_type if set,
    otherwise WEAPON_KEY_TO_DAMAGE_TYPE[weapon_key]. Fallback to impact (unarmed).
    """
    if weapon_obj and getattr(weapon_obj.db, "damage_type", None):
        dt = weapon_obj.db.damage_type
        if dt in DAMAGE_TYPES:
            return dt
    return WEAPON_KEY_TO_DAMAGE_TYPE.get(weapon_key, "impact")
