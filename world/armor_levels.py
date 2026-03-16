"""
Armor levels and layering: templates for placeholder/basic armor.
Used as a parent data source for spawning or defining actual armor later.
Lore: gutterpunk/arcanepunk — street salvage, ward-weave, and tiered rigs.

Armor levels (guideline):
  Level 1 — Street wear: one damage type (or environmental only). Trade-offs; more items than you can wear.
  Level 2 — Armor wear: multiple physical types, piercing first available. Full coverage possible.
  Level 3 — Medium: higher protection. Mix-and-match for full coverage.
  Level 4 — Heavy: superior protection. Full set possible; can mix with lower tiers.

Layers (wear order, 0 = innermost):
  0 = Jumpsuits (base; nothing under except underwear)
  1 = Pants, shirts, dresses, skirts, codpieces
  2 = Shades
  3 = Flak jackets, jackets
  4 = Trenchcoats, dusters
  5 = Helmet, boots, gloves
"""
from world.damage_types import DAMAGE_TYPES, ARMOR_EXTRA_DAMAGE_TYPES

# All damage types armor can protect against (physical + environmental)
ALL_ARMOR_DAMAGE_TYPES = DAMAGE_TYPES + ARMOR_EXTRA_DAMAGE_TYPES

# Layer constants (match typeclasses/armor.py and wear order)
ARMOR_LAYER_JUMPSUIT = 0
ARMOR_LAYER_PANTS_SHIRT = 1
ARMOR_LAYER_SHADES = 2
ARMOR_LAYER_JACKET = 3
ARMOR_LAYER_TRENCHCOAT = 4
ARMOR_LAYER_HELMET_BOOTS_GLOVES = 5

ARMOR_LEVEL_STREET = 1
ARMOR_LEVEL_ARMOR_WEAR = 2
ARMOR_LEVEL_MEDIUM = 3
ARMOR_LEVEL_HEAVY = 4


def _prot(slashing=0, impact=0, penetrating=0, magical=0, fire=0, radiation=0):
    """Build protection dict for template. Omitted types default to 0."""
    return {
        "slashing": slashing,
        "impact": impact,
        "penetrating": penetrating,
        "magical": magical,
        "fire": fire,
        "radiation": radiation,
    }


# Placeholder armor templates. Keys are spawn keys; use create_armor_from_template(template_key).
# protection = per-type score (coin-flip per point). stacking_score counts toward MAX_ARMOR_STACKING_SCORE.
ARMOR_TEMPLATES = [
    # -------------------------------------------------------------------------
    # LEVEL 1 — STREET WEAR (one damage type or environmental; style, trade-offs)
    # -------------------------------------------------------------------------
    {
        "key": "street_slashing_shirt",
        "name": "Dregweave longsleeve",
        "level": ARMOR_LEVEL_STREET,
        "layer": ARMOR_LAYER_PANTS_SHIRT,
        "covered_parts": ["torso", "back", "left shoulder", "right shoulder", "left arm", "right arm"],
        "protection": _prot(slashing=2),
        "stacking_score": 2,
        "mobility_impact": 0,
        "desc": "A reinforced longsleeve from the Dregweave line. Good against blades; style first.",
        "worn_desc": "A reinforced Dregweave longsleeve covers $P torso and arms.",
    },
    {
        "key": "street_slashing_pants",
        "name": "Dregweave pants",
        "level": ARMOR_LEVEL_STREET,
        "layer": ARMOR_LAYER_PANTS_SHIRT,
        "covered_parts": ["groin", "left thigh", "right thigh"],
        "protection": _prot(slashing=2),
        "stacking_score": 2,
        "mobility_impact": 0,
        "desc": "Dregweave work pants. Slash-resistant weaves; cheap and common in the sprawl.",
        "worn_desc": "Dregweave pants cover $P legs and groin.",
    },
    {
        "key": "street_impact_vest",
        "name": "Nexus-thread vest",
        "level": ARMOR_LEVEL_STREET,
        "layer": ARMOR_LAYER_PANTS_SHIRT,
        "covered_parts": ["torso", "back", "abdomen"],
        "protection": _prot(impact=2),
        "stacking_score": 2,
        "mobility_impact": 0,
        "desc": "Nexus-thread padded vest. Takes the punch; doesn't stop blades or rounds.",
        "worn_desc": "A Nexus-thread vest covers $P chest and belly.",
    },
    {
        "key": "street_impact_cowl",
        "name": "Nexus-thread cowl",
        "level": ARMOR_LEVEL_STREET,
        "layer": ARMOR_LAYER_PANTS_SHIRT,
        "covered_parts": ["head", "face", "neck"],
        "protection": _prot(impact=2),
        "stacking_score": 2,
        "mobility_impact": 0,
        "desc": "Pulled-over cowl with Nexus padding. Impact only; no pierce or slash.",
        "worn_desc": "A Nexus-thread cowl wraps $P head and neck.",
    },
    {
        "key": "street_env_hood",
        "name": "Hazardweave hood",
        "level": ARMOR_LEVEL_STREET,
        "layer": ARMOR_LAYER_PANTS_SHIRT,
        "covered_parts": ["head", "face", "neck"],
        "protection": _prot(slashing=0, impact=0, penetrating=0, magical=1, fire=2, radiation=2),
        "stacking_score": 2,
        "mobility_impact": 0,
        "desc": "Hazardweave: minimal physical protection, but wards against fire and rad. Common in the hot zones.",
        "worn_desc": "A Hazardweave hood covers $P head and neck, faint ward-glow at the seams.",
    },
    {
        "key": "street_slashing_jacket",
        "name": "Dregweave jacket",
        "level": ARMOR_LEVEL_STREET,
        "layer": ARMOR_LAYER_JACKET,
        "covered_parts": ["torso", "back", "left shoulder", "right shoulder", "left arm", "right arm"],
        "protection": _prot(slashing=3),
        "stacking_score": 3,
        "mobility_impact": 0,
        "desc": "Dregweave jacket. Blade-resistant; no help against impact or rounds.",
        "worn_desc": "A Dregweave jacket covers $P upper body.",
    },
    {
        "key": "street_shades",
        "name": "Nexus shades",
        "level": ARMOR_LEVEL_STREET,
        "layer": ARMOR_LAYER_SHADES,
        "covered_parts": ["face"],
        "protection": _prot(impact=1),
        "stacking_score": 1,
        "mobility_impact": 0,
        "desc": "Reinforced Nexus lenses. Minor impact protection for the eyes.",
        "worn_desc": "Nexus shades cover $P eyes.",
    },
    # -------------------------------------------------------------------------
    # LEVEL 2 — ARMOR WEAR (multiple physical types; piercing first; full coverage possible)
    # -------------------------------------------------------------------------
    {
        "key": "armorwear_jumpsuit",
        "name": "Rig jumpsuit",
        "level": ARMOR_LEVEL_ARMOR_WEAR,
        "layer": ARMOR_LAYER_JUMPSUIT,
        "covered_parts": [
            "torso", "back", "abdomen", "groin",
            "left shoulder", "right shoulder", "left arm", "right arm",
            "left thigh", "right thigh",
        ],
        "protection": _prot(slashing=1, impact=1, penetrating=1),
        "stacking_score": 6,
        "mobility_impact": 1,
        "desc": "Armored rig jumpsuit. Base protection against all physical damage; layer other pieces for more.",
        "worn_desc": "A rig jumpsuit covers $P core and limbs with a dull armored weave.",
    },
    {
        "key": "armorwear_shirt",
        "name": "Protec shirt",
        "level": ARMOR_LEVEL_ARMOR_WEAR,
        "layer": ARMOR_LAYER_PANTS_SHIRT,
        "covered_parts": ["torso", "back", "abdomen", "left shoulder", "right shoulder", "left arm", "right arm"],
        "protection": _prot(slashing=2, impact=2, penetrating=1),
        "stacking_score": 3,
        "mobility_impact": 0,
        "desc": "Protec line shirt. Slash, impact, and light pierce; first real armor tier.",
        "worn_desc": "A Protec shirt covers $P torso and arms.",
    },
    {
        "key": "armorwear_pants",
        "name": "Protec pants",
        "level": ARMOR_LEVEL_ARMOR_WEAR,
        "layer": ARMOR_LAYER_PANTS_SHIRT,
        "covered_parts": ["groin", "left thigh", "right thigh"],
        "protection": _prot(slashing=2, impact=2, penetrating=1),
        "stacking_score": 3,
        "mobility_impact": 0,
        "desc": "Protec pants. Multi-type physical protection.",
        "worn_desc": "Protec pants cover $P legs and groin.",
    },
    {
        "key": "armorwear_jacket",
        "name": "Protec jacket",
        "level": ARMOR_LEVEL_ARMOR_WEAR,
        "layer": ARMOR_LAYER_JACKET,
        "covered_parts": ["torso", "back", "left shoulder", "right shoulder", "left arm", "right arm"],
        "protection": _prot(slashing=2, impact=2, penetrating=1),
        "stacking_score": 4,
        "mobility_impact": 1,
        "desc": "Protec jacket. Multi-damage coverage; standard armor wear.",
        "worn_desc": "A Protec jacket covers $P upper body.",
    },
    {
        "key": "armorwear_duster",
        "name": "Protec duster",
        "level": ARMOR_LEVEL_ARMOR_WEAR,
        "layer": ARMOR_LAYER_TRENCHCOAT,
        "covered_parts": ["torso", "back", "abdomen", "left shoulder", "right shoulder", "left arm", "right arm", "left thigh", "right thigh"],
        "protection": _prot(slashing=2, impact=2, penetrating=1),
        "stacking_score": 5,
        "mobility_impact": 1,
        "desc": "Protec duster. Full-coverage multi-type; heavy on the stacking budget.",
        "worn_desc": "A Protec duster hangs over $P frame.",
    },
    {
        "key": "armorwear_helmet",
        "name": "Protec helmet",
        "level": ARMOR_LEVEL_ARMOR_WEAR,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["head", "face"],
        "protection": _prot(slashing=2, impact=2, penetrating=1),
        "stacking_score": 3,
        "mobility_impact": 0,
        "desc": "Protec helmet. Protects head and face from slash, impact, and pierce.",
        "worn_desc": "A Protec helmet covers $P head and face.",
    },
    {
        "key": "armorwear_boots",
        "name": "Protec boots",
        "level": ARMOR_LEVEL_ARMOR_WEAR,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["left foot", "right foot"],
        "protection": _prot(slashing=2, impact=2, penetrating=1),
        "stacking_score": 2,
        "mobility_impact": 0,
        "desc": "Protec boots. Ankle and foot protection.",
        "worn_desc": "Protec boots cover $P feet.",
    },
    {
        "key": "armorwear_gloves",
        "name": "Skinweave gloves",
        "level": ARMOR_LEVEL_ARMOR_WEAR,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["left hand", "right hand"],
        "protection": _prot(slashing=1, impact=1, penetrating=1),
        "stacking_score": 1,
        "mobility_impact": 0,
        "desc": "Skinweave gloves. Light multi-type on the hands.",
        "worn_desc": "Skinweave gloves cover $P hands.",
    },
    {
        "key": "armorwear_shades",
        "name": "Protec shades",
        "level": ARMOR_LEVEL_ARMOR_WEAR,
        "layer": ARMOR_LAYER_SHADES,
        "covered_parts": ["face"],
        "protection": _prot(slashing=1, impact=1, penetrating=1),
        "stacking_score": 1,
        "mobility_impact": 0,
        "desc": "Protec lenses. Multi-type eye protection.",
        "worn_desc": "Protec shades cover $P eyes.",
    },
    # -------------------------------------------------------------------------
    # LEVEL 3 — MEDIUM (higher protection; mix-and-match for full coverage)
    # -------------------------------------------------------------------------
    {
        "key": "medium_jumpsuit",
        "name": "Third-Circle rig",
        "level": ARMOR_LEVEL_MEDIUM,
        "layer": ARMOR_LAYER_JUMPSUIT,
        "covered_parts": [
            "torso", "back", "abdomen", "groin",
            "left shoulder", "right shoulder", "left arm", "right arm",
            "left thigh", "right thigh",
        ],
        "protection": _prot(slashing=2, impact=2, penetrating=2),
        "stacking_score": 8,
        "mobility_impact": 2,
        "desc": "Third-Circle armored rig. Step up in protection; still needs mixing for full coverage.",
        "worn_desc": "A Third-Circle rig covers $P core and limbs.",
    },
    {
        "key": "medium_jacket",
        "name": "Third-Circle jacket",
        "level": ARMOR_LEVEL_MEDIUM,
        "layer": ARMOR_LAYER_JACKET,
        "covered_parts": ["torso", "back", "left shoulder", "right shoulder", "left arm", "right arm"],
        "protection": _prot(slashing=3, impact=3, penetrating=2),
        "stacking_score": 5,
        "mobility_impact": 1,
        "desc": "Third-Circle jacket. Noticeable physical and environmental resistance.",
        "worn_desc": "A Third-Circle jacket covers $P upper body.",
    },
    {
        "key": "medium_duster",
        "name": "Third-Circle duster",
        "level": ARMOR_LEVEL_MEDIUM,
        "layer": ARMOR_LAYER_TRENCHCOAT,
        "covered_parts": ["torso", "back", "abdomen", "left shoulder", "right shoulder", "left arm", "right arm", "left thigh", "right thigh"],
        "protection": _prot(slashing=3, impact=3, penetrating=2),
        "stacking_score": 6,
        "mobility_impact": 2,
        "desc": "Third-Circle duster. Heavy coverage; mix with rig or plates.",
        "worn_desc": "A Third-Circle duster hangs over $P frame.",
    },
    {
        "key": "medium_helmet",
        "name": "Third-Circle helmet",
        "level": ARMOR_LEVEL_MEDIUM,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["head", "face"],
        "protection": _prot(slashing=3, impact=3, penetrating=2),
        "stacking_score": 4,
        "mobility_impact": 0,
        "desc": "Third-Circle helmet. Solid head protection.",
        "worn_desc": "A Third-Circle helmet covers $P head and face.",
    },
    {
        "key": "medium_boots",
        "name": "Third-Circle boots",
        "level": ARMOR_LEVEL_MEDIUM,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["left foot", "right foot"],
        "protection": _prot(slashing=2, impact=2, penetrating=2),
        "stacking_score": 2,
        "mobility_impact": 0,
        "desc": "Third-Circle boots. Sturdy foot and ankle.",
        "worn_desc": "Third-Circle boots cover $P feet.",
    },
    {
        "key": "medium_gloves",
        "name": "Third-Circle gloves",
        "level": ARMOR_LEVEL_MEDIUM,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["left hand", "right hand"],
        "protection": _prot(slashing=2, impact=2, penetrating=2),
        "stacking_score": 2,
        "mobility_impact": 0,
        "desc": "Third-Circle gloves. Better hand protection.",
        "worn_desc": "Third-Circle gloves cover $P hands.",
    },
    # -------------------------------------------------------------------------
    # LEVEL 4 — HEAVY (superior; full set possible; can mix with lower tiers)
    # -------------------------------------------------------------------------
    {
        "key": "heavy_jumpsuit",
        "name": "Fifth-Circle rig",
        "level": ARMOR_LEVEL_HEAVY,
        "layer": ARMOR_LAYER_JUMPSUIT,
        "covered_parts": [
            "torso", "back", "abdomen", "groin",
            "left shoulder", "right shoulder", "left arm", "right arm",
            "left thigh", "right thigh",
        ],
        "protection": _prot(slashing=3, impact=3, penetrating=3),
        "stacking_score": 10,
        "mobility_impact": 3,
        "desc": "Fifth-Circle armored rig. Superior base protection; full set if you can find and afford the pieces.",
        "worn_desc": "A Fifth-Circle rig covers $P core and limbs with serious plate and weave.",
    },
    {
        "key": "heavy_jacket",
        "name": "Fifth-Circle jacket",
        "level": ARMOR_LEVEL_HEAVY,
        "layer": ARMOR_LAYER_JACKET,
        "covered_parts": ["torso", "back", "left shoulder", "right shoulder", "left arm", "right arm"],
        "protection": _prot(slashing=4, impact=4, penetrating=3),
        "stacking_score": 6,
        "mobility_impact": 2,
        "desc": "Fifth-Circle jacket. Top-tier physical and environmental protection.",
        "worn_desc": "A Fifth-Circle jacket covers $P upper body.",
    },
    {
        "key": "heavy_duster",
        "name": "Fifth-Circle duster",
        "level": ARMOR_LEVEL_HEAVY,
        "layer": ARMOR_LAYER_TRENCHCOAT,
        "covered_parts": ["torso", "back", "abdomen", "left shoulder", "right shoulder", "left arm", "right arm", "left thigh", "right thigh"],
        "protection": _prot(slashing=4, impact=4, penetrating=3),
        "stacking_score": 7,
        "mobility_impact": 2,
        "desc": "Fifth-Circle duster. Superior coverage; mix with lower tiers and still excel.",
        "worn_desc": "A Fifth-Circle duster hangs over $P frame.",
    },
    {
        "key": "heavy_helmet",
        "name": "Fifth-Circle helmet",
        "level": ARMOR_LEVEL_HEAVY,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["head", "face"],
        "protection": _prot(slashing=4, impact=4, penetrating=3),
        "stacking_score": 5,
        "mobility_impact": 0,
        "desc": "Fifth-Circle helmet. Best head protection the tiers offer.",
        "worn_desc": "A Fifth-Circle helmet covers $P head and face.",
    },
    {
        "key": "heavy_boots",
        "name": "Fifth-Circle boots",
        "level": ARMOR_LEVEL_HEAVY,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["left foot", "right foot"],
        "protection": _prot(slashing=3, impact=3, penetrating=3),
        "stacking_score": 3,
        "mobility_impact": 1,
        "desc": "Fifth-Circle boots. Heavy foot and ankle protection.",
        "worn_desc": "Fifth-Circle boots cover $P feet.",
    },
    {
        "key": "heavy_gloves",
        "name": "Fifth-Circle gloves",
        "level": ARMOR_LEVEL_HEAVY,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["left hand", "right hand"],
        "protection": _prot(slashing=3, impact=3, penetrating=3),
        "stacking_score": 3,
        "mobility_impact": 0,
        "desc": "Fifth-Circle gloves. Superior hand protection.",
        "worn_desc": "Fifth-Circle gloves cover $P hands.",
    },
]


def get_armor_template(key):
    """Return the template dict for template_key, or None."""
    for t in ARMOR_TEMPLATES:
        if t.get("key") == key:
            return t
    return None


def create_armor_from_template(template_key, location=None, quality=100):
    """
    Create an Armor object from a template key. Use for spawning placeholder/basic armor.
    Returns the created object or None.
    """
    template = get_armor_template(template_key)
    if not template:
        return None
    from evennia import create_object
    from typeclasses.armor import Armor
    obj = create_object(
        Armor,
        key=template["name"],
        location=location,
        nohome=True,
    )
    if not obj:
        return None
    obj.db.armor_layer = template["layer"]
    obj.db.covered_parts = list(template["covered_parts"])
    obj.db.protection = dict(template["protection"])
    obj.db.stacking_score = template["stacking_score"]
    obj.db.mobility_impact = template.get("mobility_impact", 0)
    obj.db.quality = max(0, min(100, int(quality)))
    if template.get("desc"):
        obj.db.desc = template["desc"]
    if template.get("worn_desc"):
        obj.db.worn_desc = template["worn_desc"]
    # Store level for reference (e.g. examine, balance)
    obj.db.armor_level = template.get("level", 1)
    return obj
