"""
world/armor_levels.py
─────────────────────────────────────────────────────────────────────────────
Armor tier definitions and spawn templates for the arcanepunk/gutterpunk setting.

THE WORLD ABOVE AND THE WORLD BELOW
  The sun-scorched surface is uninhabitable. Humanity survives in tunnelled
  cities under the governance of the Deep Accord — part religion, part
  machine-cult, entirely totalitarian. Armor reflects this strata: scavengers
  stitch together whatever the tunnels offer; guilds sell manufactured weaves
  to those who can afford them; the Accord's enforcers and military wear
  proper plating; and the Inquisitorate moves in void-iron that protects
  against its own weapons.

TIERS
  Level 1  Scavenger       Bone, hide, rubber, salvaged scrap. One or two damage types.
  Level 2  Guild Civilian  Manufactured weave lines (Dregweave, Nexus-thread, Ironweave).
                           Multi-physical, light penetrating, some environmental.
  Level 3  Enforcer Grade  Ashplate / Wardwoven — ward-issued enforcer kit.
                           Solid physical, minor burn/arc protection.
  Level 4  Medium Military Third-Circle Rig — Undercourt Military standard issue.
                           Meaningful energy resistance begins here.
  Level 5  Heavy Military  Fifth-Circle Rig and Ironhollow Plate — restricted to
                           military officers and senior enforcers. Solid energy coverage.
  Level 6  Inquisitorate   Deep Accord void-iron. Only piece that meaningfully
                           resists the Inquisitorate's own void/plasma weapons.

PROTECTION SYSTEM
  protection[damage_type] = N  →  each point is a coin-flip: 50% chance to block 1 damage.
  Expected reduction = N/2. Quality scales linearly (100 quality = full value).
  Against T-rated weapons:
    T1–T2 (avg 8): L1 prot 2 blocks ~1.  L3 prot 4 blocks ~2.
    T3–T6 (avg 10–15): L2–L3 relevant; L4 comfortable.
    T7–T8 (avg 19–27): L4–L5 required for meaningful reduction.
    T9 (avg 35): L5 energy prot (4) blocks ~2. L6 (7) blocks ~3.5.
    T10 (avg 44): Only L6 void prot (8) provides real resistance.

LAYERS
  0 = Jumpsuit / base underlayer
  1 = Pants, shirts, tunic
  2 = Shades
  3 = Jacket
  4 = Trenchcoat / duster
  5 = Helmet / boots / gloves

STACKING SCORE
  MAX_ARMOR_STACKING_SCORE is enforced by the wear system.
  L1 pieces: 1–2  (light scraps; can stack many)
  L2 pieces: 2–4  (manufactured; standard civilian load)
  L3 pieces: 3–6  (plated; enforcer-weight)
  L4 pieces: 4–8  (military medium)
  L5 pieces: 6–11 (military heavy; eats stacking budget fast)
  L6 pieces: 9–14 (inquisitorate; few pieces cover everything)
"""

from world.damage_types import DAMAGE_TYPES, ARMOR_EXTRA_DAMAGE_TYPES

ALL_ARMOR_DAMAGE_TYPES = DAMAGE_TYPES + ARMOR_EXTRA_DAMAGE_TYPES

# Layer constants (match typeclasses/armor.py)
ARMOR_LAYER_JUMPSUIT            = 0
ARMOR_LAYER_PANTS_SHIRT         = 1
ARMOR_LAYER_SHADES              = 2
ARMOR_LAYER_JACKET              = 3
ARMOR_LAYER_TRENCHCOAT          = 4
ARMOR_LAYER_HELMET_BOOTS_GLOVES = 5

# Tier level constants
ARMOR_LEVEL_SCAVENGER  = 1
ARMOR_LEVEL_CIVILIAN   = 2
ARMOR_LEVEL_ENFORCER   = 3
ARMOR_LEVEL_MILITARY   = 4
ARMOR_LEVEL_HEAVY      = 5
ARMOR_LEVEL_INQUISITOR = 6


def _prot(
    slashing=0, impact=0, penetrating=0,
    burn=0, freeze=0, arc=0, void=0,
    radiation=0,
):
    """Build a protection dict. Omitted damage types default to 0."""
    return {
        "slashing":    slashing,
        "impact":      impact,
        "penetrating": penetrating,
        "burn":        burn,
        "freeze":      freeze,
        "arc":         arc,
        "void":        void,
        "radiation":   radiation,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ARMOR TEMPLATES
# Keys: spawn key. Use create_armor_from_template(key) to instantiate.
# ─────────────────────────────────────────────────────────────────────────────
ARMOR_TEMPLATES = [

    # =========================================================================
    # LEVEL 1 — SCAVENGER
    # Bone, hide, salvaged rubber and pipe-insulation. Single or dual physical
    # types only. No penetrating, no energy protection. Made from whatever
    # didn't kill you when you took it.
    # =========================================================================

    {
        "key": "scav_tunnelbone_wrap",
        "name": "Tunnelbone wrap",
        "level": ARMOR_LEVEL_SCAVENGER,
        "layer": ARMOR_LAYER_PANTS_SHIRT,
        "covered_parts": [
            "torso", "back", "abdomen",
            "left shoulder", "right shoulder", "left arm", "right arm",
        ],
        "protection": _prot(slashing=2, impact=1),
        "stacking_score": 2,
        "mobility_impact": 0,
        "desc": (
            "Salvaged bone plates — ribs and scapulae from surface creatures, "
            "mostly — lashed to a canvas backing with sinew and wire. The plates "
            "click softly when you move. Some have been carved with ward-marks by "
            "previous owners. It will not stop a bullet. It will stop a knife, once "
            "or twice, before a plate cracks and has to be replaced. The smell "
            "washes out eventually."
        ),
        "worn_desc": "Tunnelbone plates rattle faintly across $P torso and arms.",
    },
    {
        "key": "scav_scrapleather_pants",
        "name": "Scrapleather pants",
        "level": ARMOR_LEVEL_SCAVENGER,
        "layer": ARMOR_LAYER_PANTS_SHIRT,
        "covered_parts": ["groin", "left thigh", "right thigh"],
        "protection": _prot(slashing=2, impact=1),
        "stacking_score": 1,
        "mobility_impact": 0,
        "desc": (
            "Heavy pants stitched from multiple hides — tunnel-dog, possibly, or "
            "something larger that did not survive the encounter. The seams are "
            "uneven and the color is inconsistent but the leather is thick. "
            "Slash-resistant in the way that something thick and dead usually is. "
            "The belt loops have been reinforced with wire."
        ),
        "worn_desc": "Scrapleather pants cover $P legs and groin, thick hide creaking with movement.",
    },
    {
        "key": "scav_hide_hood",
        "name": "Tunnel-hide hood",
        "level": ARMOR_LEVEL_SCAVENGER,
        "layer": ARMOR_LAYER_PANTS_SHIRT,
        "covered_parts": ["head", "face", "neck"],
        "protection": _prot(impact=2),
        "stacking_score": 1,
        "mobility_impact": 0,
        "desc": (
            "A close-fitting hood constructed from heavily tanned hide, "
            "double-layered at the crown and temples. It will absorb a club "
            "blow without breaking your skull. It will not absorb a blade. "
            "The inside is lined with softer, thinner leather; someone cared "
            "enough to do that, which is more than can be said for most "
            "tunnel-made gear."
        ),
        "worn_desc": "A tunnel-hide hood is drawn over $P head and face.",
    },
    {
        "key": "scav_riveted_jacket",
        "name": "Riveted leather jacket",
        "level": ARMOR_LEVEL_SCAVENGER,
        "layer": ARMOR_LAYER_JACKET,
        "covered_parts": [
            "torso", "back",
            "left shoulder", "right shoulder", "left arm", "right arm",
        ],
        "protection": _prot(slashing=3, impact=1),
        "stacking_score": 2,
        "mobility_impact": 0,
        "desc": (
            "A jacket of thick, stiffened hide with iron rivets punched "
            "through at close intervals along the shoulders, chest, and "
            "forearms. The rivets are uneven and some are loose. The hide "
            "itself is multiple layers at the chest, treated with something "
            "that has left it almost rigid. It stops blades. It does not stop "
            "much else, but blades are what most people are carrying."
        ),
        "worn_desc": "A riveted leather jacket covers $P upper body, iron studs glinting dully.",
    },
    {
        "key": "scav_rubber_stompers",
        "name": "Rubber-sole stompers",
        "level": ARMOR_LEVEL_SCAVENGER,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["left foot", "right foot"],
        "protection": _prot(impact=2),
        "stacking_score": 1,
        "mobility_impact": 0,
        "desc": (
            "Heavy boots assembled from salvaged rubber — pipe insulation, "
            "machinery gaskets, industrial sheet stock — layered and heat-"
            "bonded into thick soles, with canvas upper sections tied on "
            "with cord. Ugly and imprecise. They absorb stomps and drops and "
            "the occasions when someone tries to break your feet, which in "
            "the tunnels is a more common problem than it ought to be."
        ),
        "worn_desc": "Thick rubber-sole stompers cover $P feet, leaving heavy prints.",
    },

    # =========================================================================
    # LEVEL 2 — GUILD CIVILIAN
    # Three product lines available in ward markets:
    #   Dregweave  — slash-resistant bonded weave (street/traveller)
    #   Nexus-thread — impact-dampening gel-padded fabric (common/utility)
    #   Ironweave  — multi-type guild-licensed composite (expensive civilian)
    # Light penetrating protection first appears here (Ironweave line).
    # Environmental protection (burn/radiation) available on Hazardweave.
    # =========================================================================

    {
        "key": "civ_dregweave_longsleeve",
        "name": "Dregweave longsleeve",
        "level": ARMOR_LEVEL_CIVILIAN,
        "layer": ARMOR_LAYER_PANTS_SHIRT,
        "covered_parts": [
            "torso", "back",
            "left shoulder", "right shoulder", "left arm", "right arm",
        ],
        "protection": _prot(slashing=2, impact=1),
        "stacking_score": 2,
        "mobility_impact": 0,
        "desc": (
            "A close-fitting longsleeve from the Dregweave line — one of "
            "the more popular guild garments in the mid-wards. The weave "
            "is a proprietary bonded fiber that resists cutting without adding "
            "visible bulk, which is why enforcers hate that civilians can buy "
            "it. It looks like a normal shirt. The label inside gives it away, "
            "for anyone who knows what to look for."
        ),
        "worn_desc": "A Dregweave longsleeve covers $P torso and arms, unremarkable to look at.",
    },
    {
        "key": "civ_dregweave_pants",
        "name": "Dregweave work pants",
        "level": ARMOR_LEVEL_CIVILIAN,
        "layer": ARMOR_LAYER_PANTS_SHIRT,
        "covered_parts": ["groin", "left thigh", "right thigh"],
        "protection": _prot(slashing=2, impact=1),
        "stacking_score": 2,
        "mobility_impact": 0,
        "desc": (
            "Dregweave trousers cut in a working pattern — wide enough to "
            "move in, reinforced at the knees and inner thigh. The slash-"
            "resistance is built into the weave, not added on, so they "
            "don't feel armored. They feel like good trousers. That's the "
            "whole appeal. Sold at three of the four licensed outfitters "
            "in the market quarter."
        ),
        "worn_desc": "Dregweave work pants cover $P legs and groin.",
    },
    {
        "key": "civ_nexus_vest",
        "name": "Nexus-thread vest",
        "level": ARMOR_LEVEL_CIVILIAN,
        "layer": ARMOR_LAYER_PANTS_SHIRT,
        "covered_parts": ["torso", "back", "abdomen"],
        "protection": _prot(impact=2, slashing=1),
        "stacking_score": 2,
        "mobility_impact": 0,
        "desc": (
            "A padded vest using Nexus-thread gel-cell padding sewn into "
            "the lining. The padding distributes impact across a wider area "
            "before it reaches you. A blow that would bruise through a "
            "normal shirt becomes more of an inconvenience. It does nothing "
            "for blades, not really — but in the wards where the primary "
            "threat is getting beaten rather than cut, it's enough. The "
            "exterior is offered in several neutral colors."
        ),
        "worn_desc": "A Nexus-thread vest covers $P chest and belly, slightly puffed at the panels.",
    },
    {
        "key": "civ_nexus_cowl",
        "name": "Nexus-thread cowl",
        "level": ARMOR_LEVEL_CIVILIAN,
        "layer": ARMOR_LAYER_PANTS_SHIRT,
        "covered_parts": ["head", "face", "neck"],
        "protection": _prot(impact=2, slashing=1),
        "stacking_score": 2,
        "mobility_impact": 0,
        "desc": (
            "A pull-over cowl of heavy Nexus-thread fabric, padded at the "
            "crown and temples. It looks vaguely ceremonial — a common "
            "enough silhouette in the deep wards where religious head "
            "coverings are the norm. Nobody questions a cowl. The gel-"
            "padding at the temples will prevent most casual skull-cracking."
        ),
        "worn_desc": "A Nexus-thread cowl is drawn over $P head and neck.",
    },
    {
        "key": "civ_dregweave_jacket",
        "name": "Dregweave street jacket",
        "level": ARMOR_LEVEL_CIVILIAN,
        "layer": ARMOR_LAYER_JACKET,
        "covered_parts": [
            "torso", "back",
            "left shoulder", "right shoulder", "left arm", "right arm",
        ],
        "protection": _prot(slashing=3, impact=1),
        "stacking_score": 3,
        "mobility_impact": 0,
        "desc": (
            "The flagship outer garment of the Dregweave line: a structured "
            "jacket with reinforced bonded-fiber panels at the chest, back, "
            "and upper arms, over a softer Dregweave body. It looks like "
            "exactly the sort of jacket a guild worker who wants to come "
            "home at the end of the day would wear. Which is exactly what "
            "it is sold to, and exactly what it does."
        ),
        "worn_desc": "A Dregweave street jacket covers $P upper body.",
    },
    {
        "key": "civ_hazardweave_hood",
        "name": "Hazardweave hood",
        "level": ARMOR_LEVEL_CIVILIAN,
        "layer": ARMOR_LAYER_PANTS_SHIRT,
        "covered_parts": ["head", "face", "neck"],
        "protection": _prot(burn=2, radiation=2),
        "stacking_score": 2,
        "mobility_impact": 0,
        "desc": (
            "A specialist hood of Hazardweave — a licensed environmental "
            "fabric developed for workers in the heat zones near geothermal "
            "vents and irradiated tunnel sections. The weave has negligible "
            "physical protection but the thermal and radiation barrier is "
            "genuine. A faint ward-glow pulses at the seams under dim light; "
            "whether this is functional or cosmetic is a matter of some debate "
            "in guild circles."
        ),
        "worn_desc": "A Hazardweave hood covers $P head and neck, ward-seams faintly luminous.",
    },
    {
        "key": "civ_nexus_shades",
        "name": "Nexus shades",
        "level": ARMOR_LEVEL_CIVILIAN,
        "layer": ARMOR_LAYER_SHADES,
        "covered_parts": ["face"],
        "protection": _prot(impact=1, slashing=1),
        "stacking_score": 1,
        "mobility_impact": 0,
        "desc": (
            "Reinforced Nexus lens shades — a popular accessory in the tunnel "
            "wards both for the impact-rated lenses and because they read as "
            "something other than armor. The frames are polished alloy; the "
            "lenses are thick Nexus composite that stops a thrown object or "
            "a careless blade at the face. Available in tinted and clear. "
            "Most people choose tinted."
        ),
        "worn_desc": "Nexus shades cover $P eyes.",
    },
    {
        "key": "civ_ironweave_gloves",
        "name": "Ironweave work gloves",
        "level": ARMOR_LEVEL_CIVILIAN,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["left hand", "right hand"],
        "protection": _prot(slashing=2, impact=1, penetrating=1),
        "stacking_score": 1,
        "mobility_impact": 0,
        "desc": (
            "Ironweave composite gloves from the guild's multi-type civilian "
            "line — the most expensive item in the L2 range and the most "
            "technically accomplished. The Ironweave construction layers "
            "cut-resistant mesh, impact gel, and a light penetrating plate "
            "at the back of the hand. Looks like a heavy work glove. "
            "Costs three times as much."
        ),
        "worn_desc": "Ironweave work gloves cover $P hands.",
    },
    {
        "key": "civ_ironweave_jumpsuit",
        "name": "Ironweave rig suit",
        "level": ARMOR_LEVEL_CIVILIAN,
        "layer": ARMOR_LAYER_JUMPSUIT,
        "covered_parts": [
            "torso", "back", "abdomen", "groin",
            "left shoulder", "right shoulder", "left arm", "right arm",
            "left thigh", "right thigh",
        ],
        "protection": _prot(slashing=1, impact=1, penetrating=1),
        "stacking_score": 5,
        "mobility_impact": 1,
        "desc": (
            "The Ironweave rig suit is the civilian market's best answer to "
            "the question 'how much protection can you fit under normal "
            "clothing.' The answer is: not much, but some, and evenly "
            "distributed. The suit covers nearly the full body in a thin, "
            "laminated Ironweave composite that provides light protection "
            "against all three physical damage types. It was designed for "
            "guild inspectors who work near armed disputes and can't wear "
            "armor. Many people who can wear armor wear it anyway, underneath."
        ),
        "worn_desc": "An Ironweave rig suit covers $P body in a close, slightly stiff underlayer.",
    },

    # =========================================================================
    # LEVEL 3 — ENFORCER GRADE (Ashplate / Wardwoven)
    # Standard issue for licensed ward enforcer companies and junior military.
    # Two product lines:
    #   Wardwoven  — flexible armored fabric; covers softly; worn as base/shirt
    #   Ashplate   — hard composite plating; outer layers; better protection
    # Minor burn and arc protection appears here — enforcers carry arc batons
    # and deal with industrial fire hazards.
    # =========================================================================

    {
        "key": "enf_wardwoven_jumpsuit",
        "name": "Wardwoven under-rig",
        "level": ARMOR_LEVEL_ENFORCER,
        "layer": ARMOR_LAYER_JUMPSUIT,
        "covered_parts": [
            "torso", "back", "abdomen", "groin",
            "left shoulder", "right shoulder", "left arm", "right arm",
            "left thigh", "right thigh",
        ],
        "protection": _prot(slashing=2, impact=2, penetrating=2),
        "stacking_score": 6,
        "mobility_impact": 1,
        "desc": (
            "The Wardwoven under-rig is the base layer of the standard "
            "enforcer kit — a full-body armored suit worn beneath the "
            "outer Ashplate pieces. The Wardwoven fabric is a bonded "
            "composite that provides meaningful protection against all "
            "three physical types without the weight of hard plating. "
            "The enforcer ward-seal is printed inside the collar; most "
            "of these have been defaced, which tells you where this one "
            "came from. It still works fine."
        ),
        "worn_desc": "A Wardwoven under-rig covers $P body in a close armored underlayer.",
    },
    {
        "key": "enf_ashplate_shirt",
        "name": "Ashplate body armour",
        "level": ARMOR_LEVEL_ENFORCER,
        "layer": ARMOR_LAYER_PANTS_SHIRT,
        "covered_parts": [
            "torso", "back", "abdomen",
            "left shoulder", "right shoulder",
        ],
        "protection": _prot(slashing=3, impact=3, penetrating=2, burn=1),
        "stacking_score": 4,
        "mobility_impact": 1,
        "desc": (
            "Ashplate composite chest and back plating with shoulder "
            "cops — the standard torso piece of the enforcer armor "
            "system. The Ashplate material is a compressed ceramic-"
            "polymer composite in a matte grey-black finish. The "
            "ceramic component offers minor heat resistance, useful "
            "in the hot-zones and when dealing with arc-weapon users. "
            "The ward authority serial has been ground off the left "
            "pauldron. The grinding is recent."
        ),
        "worn_desc": "Ashplate body armour covers $P chest, back, and shoulders in grey-black composite.",
    },
    {
        "key": "enf_ashplate_pants",
        "name": "Ashplate leg armour",
        "level": ARMOR_LEVEL_ENFORCER,
        "layer": ARMOR_LAYER_PANTS_SHIRT,
        "covered_parts": ["groin", "left thigh", "right thigh"],
        "protection": _prot(slashing=3, impact=3, penetrating=2),
        "stacking_score": 3,
        "mobility_impact": 1,
        "desc": (
            "Ashplate composite leg guards worn over the Wardwoven under-rig: "
            "two articulated thigh plates with a groin panel connecting them. "
            "The articulation is functional — you can run, crouch, and climb "
            "without removing them. The original quick-release buckles are "
            "still present and properly calibrated. Someone has taken care "
            "of these."
        ),
        "worn_desc": "Ashplate leg armour covers $P thighs and groin in articulated grey-black plating.",
    },
    {
        "key": "enf_ashplate_jacket",
        "name": "Ashplate combat jacket",
        "level": ARMOR_LEVEL_ENFORCER,
        "layer": ARMOR_LAYER_JACKET,
        "covered_parts": [
            "torso", "back",
            "left shoulder", "right shoulder", "left arm", "right arm",
        ],
        "protection": _prot(slashing=3, impact=3, penetrating=2, burn=1, arc=1),
        "stacking_score": 5,
        "mobility_impact": 1,
        "desc": (
            "A structured combat jacket with integrated Ashplate composite "
            "panels across the chest, back, shoulders, and forearms, over "
            "a Wardwoven base. The arc-insulated lining in the forearms "
            "is designed to protect against the occupational hazard of "
            "having your own baton overload near your arm. The arm-panels "
            "are strapped rather than sewn, so they can be replaced when "
            "damaged without replacing the whole jacket. Several have been."
        ),
        "worn_desc": "An Ashplate combat jacket covers $P upper body in layered composite and weave.",
    },
    {
        "key": "enf_ashplate_duster",
        "name": "Ashplate patrol duster",
        "level": ARMOR_LEVEL_ENFORCER,
        "layer": ARMOR_LAYER_TRENCHCOAT,
        "covered_parts": [
            "torso", "back", "abdomen",
            "left shoulder", "right shoulder", "left arm", "right arm",
            "left thigh", "right thigh",
        ],
        "protection": _prot(slashing=3, impact=3, penetrating=2),
        "stacking_score": 6,
        "mobility_impact": 2,
        "desc": (
            "The long-form outer layer of enforcer kit: an Ashplate duster "
            "that covers the full torso and upper legs. The length is "
            "deliberate — it covers weapons holstered at the thigh and "
            "makes the wearer's exact loadout difficult to read from a "
            "distance. The composite runs in articulated strips rather "
            "than solid plates, allowing the swing and drape of a coat "
            "with better protection than one suggests. It is heavier than "
            "it looks."
        ),
        "worn_desc": "An Ashplate patrol duster hangs over $P frame in grey-black articulated panels.",
    },
    {
        "key": "enf_ashplate_helmet",
        "name": "Ashplate patrol helmet",
        "level": ARMOR_LEVEL_ENFORCER,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["head", "face"],
        "protection": _prot(slashing=3, impact=3, penetrating=2, arc=1),
        "stacking_score": 4,
        "mobility_impact": 0,
        "desc": (
            "Standard-issue enforcer helmet: full Ashplate composite shell "
            "with a visor of arc-insulated Nexus glass. The visor is rated "
            "for direct arc-baton contact, which enforcer companies apparently "
            "found worth specifying. The helmet carries a worn ward-authority "
            "serial on the right side of the shell; someone has scratched "
            "through it but not deeply enough. The padding inside is intact "
            "and comfortable."
        ),
        "worn_desc": "An Ashplate patrol helmet covers $P head and face, visor dark.",
    },
    {
        "key": "enf_ashplate_boots",
        "name": "Ashplate patrol boots",
        "level": ARMOR_LEVEL_ENFORCER,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["left foot", "right foot"],
        "protection": _prot(slashing=2, impact=3, penetrating=2),
        "stacking_score": 3,
        "mobility_impact": 0,
        "desc": (
            "Heavy patrol boots with Ashplate composite toe-caps and ankle "
            "guards over a thick rubber sole. The toe-cap is reinforced for "
            "use as an impact weapon when necessary, which the design manual "
            "does not state but the reinforcement implies. The sole's arc-"
            "insulation is a holdover from the ward authority specification. "
            "The lacing system is metal-eyelet and has never failed at a "
            "bad moment, which is the most important quality a boot can have."
        ),
        "worn_desc": "Ashplate patrol boots cover $P feet, toe-caps dull grey composite.",
    },
    {
        "key": "enf_wardwoven_gloves",
        "name": "Wardwoven combat gloves",
        "level": ARMOR_LEVEL_ENFORCER,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["left hand", "right hand"],
        "protection": _prot(slashing=2, impact=2, penetrating=1, arc=1),
        "stacking_score": 2,
        "mobility_impact": 0,
        "desc": (
            "Wardwoven composite gloves with hard knuckle-guards of Ashplate "
            "ceramic and arc-insulated palm lining. The arc insulation was "
            "added to the enforcer specification after a number of incidents "
            "involving operators and their own arc-weapons. The knuckle "
            "guards double as impact weapons; this was also apparently "
            "unintentional in the design and has since been left in."
        ),
        "worn_desc": "Wardwoven combat gloves cover $P hands, knuckle-guards prominent.",
    },

    # =========================================================================
    # LEVEL 4 — MEDIUM MILITARY (Third-Circle Rig)
    # Undercourt Military standard issue. The 'Third Circle' designation
    # refers to the third circle of the Deep Accord's ecclesiastical rank
    # structure — military is civil, but the Accord blessed the manufacture.
    # Meaningful energy resistance begins here.
    # Restricted: civilian possession requires military license.
    # =========================================================================

    {
        "key": "mil_thirdcircle_rig",
        "name": "Third-Circle under-rig",
        "level": ARMOR_LEVEL_MILITARY,
        "layer": ARMOR_LAYER_JUMPSUIT,
        "covered_parts": [
            "torso", "back", "abdomen", "groin",
            "left shoulder", "right shoulder", "left arm", "right arm",
            "left thigh", "right thigh",
        ],
        "protection": _prot(slashing=3, impact=3, penetrating=3, burn=1, arc=1),
        "stacking_score": 7,
        "mobility_impact": 2,
        "desc": (
            "The base layer of the Undercourt Military standard issue kit. "
            "The Third-Circle rig is a full-body laminated weave with integrated "
            "plate inserts at the torso, thighs, and shoulders — heavier than "
            "any civilian equivalent and noticeably more protective. The thermal "
            "and arc lining reflects the military's awareness that they may face "
            "their own energy weapons turned against them. The Accord sigil "
            "is embossed inside the left hip panel. Unauthorized civilian "
            "possession requires explanation."
        ),
        "worn_desc": "A Third-Circle under-rig covers $P body in dense military laminate.",
    },
    {
        "key": "mil_thirdcircle_jacket",
        "name": "Third-Circle combat jacket",
        "level": ARMOR_LEVEL_MILITARY,
        "layer": ARMOR_LAYER_JACKET,
        "covered_parts": [
            "torso", "back",
            "left shoulder", "right shoulder", "left arm", "right arm",
        ],
        "protection": _prot(slashing=4, impact=4, penetrating=3, burn=2, arc=2),
        "stacking_score": 6,
        "mobility_impact": 2,
        "desc": (
            "The outer plate jacket of the Third-Circle kit: hard laminate "
            "panels over a Wardwoven base, with expanded arc and thermal "
            "insulation in the chest and shoulder panels. The protection "
            "ratings here are the first where a wearer begins to feel "
            "meaningfully resistant rather than merely better-protected. "
            "The military serial has been removed from this one — cleanly, "
            "with a proper tool rather than force. Whoever did it knew "
            "what they were doing."
        ),
        "worn_desc": "A Third-Circle combat jacket covers $P upper body in hard military laminate.",
    },
    {
        "key": "mil_thirdcircle_duster",
        "name": "Third-Circle field duster",
        "level": ARMOR_LEVEL_MILITARY,
        "layer": ARMOR_LAYER_TRENCHCOAT,
        "covered_parts": [
            "torso", "back", "abdomen",
            "left shoulder", "right shoulder", "left arm", "right arm",
            "left thigh", "right thigh",
        ],
        "protection": _prot(slashing=4, impact=4, penetrating=3, burn=1, arc=1),
        "stacking_score": 7,
        "mobility_impact": 2,
        "desc": (
            "A military-issue field duster combining articulated plate with "
            "thermal/arc-lined Wardwoven underlayer — full-coverage outer armor "
            "that the Undercourt Military issues to field units expecting extended "
            "engagement. The length covers thigh holsters and the articulation "
            "is better than its predecessor enforcer equivalent. Heavier than "
            "a civilian duster but the weight distributes well when properly "
            "fitted. The Accord mark is stamped into the inner collar. "
            "Someone has been wearing this for a while."
        ),
        "worn_desc": "A Third-Circle field duster hangs over $P frame in heavy military plate.",
    },
    {
        "key": "mil_thirdcircle_helmet",
        "name": "Third-Circle combat helmet",
        "level": ARMOR_LEVEL_MILITARY,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["head", "face"],
        "protection": _prot(slashing=4, impact=4, penetrating=3, burn=2, arc=2, freeze=1),
        "stacking_score": 5,
        "mobility_impact": 0,
        "desc": (
            "The military combat helmet of the Third-Circle kit: a full-"
            "coverage shell of hard laminate with a visor rated for plasma "
            "splash, arc discharge, and standard ballistic. The inner lining "
            "has cryo-resilience built in after the Coldfront engagement "
            "where a number of Undercourt soldiers experienced helmet failures "
            "in freeze-weapon contact. The Accord sigil is pressed into the "
            "brow; it cannot be removed without destroying the shell integrity."
        ),
        "worn_desc": "A Third-Circle combat helmet covers $P head and face, visor bearing the Accord sigil.",
    },
    {
        "key": "mil_thirdcircle_boots",
        "name": "Third-Circle field boots",
        "level": ARMOR_LEVEL_MILITARY,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["left foot", "right foot"],
        "protection": _prot(slashing=3, impact=3, penetrating=3, burn=1),
        "stacking_score": 3,
        "mobility_impact": 1,
        "desc": (
            "Military-issue field boots with a full hard-laminate shell and "
            "thermal-lined sole. The thermal lining was added after tunnel-"
            "floor heat damage incidents in the deep-ward operations. The "
            "toe-cap is integrated into the shell rather than added on, "
            "which means it does not come off when you use it as an impact "
            "weapon — which the specification now officially accounts for."
        ),
        "worn_desc": "Third-Circle field boots cover $P feet in solid military laminate.",
    },
    {
        "key": "mil_thirdcircle_gloves",
        "name": "Third-Circle gauntlets",
        "level": ARMOR_LEVEL_MILITARY,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["left hand", "right hand"],
        "protection": _prot(slashing=3, impact=3, penetrating=3, arc=2),
        "stacking_score": 3,
        "mobility_impact": 0,
        "desc": (
            "Hard-laminate gauntlets with an articulated back-of-hand plate, "
            "reinforced knuckle bar, and an arc-insulated palm with extended "
            "wrist protection. The arc insulation is rated to full arc-weapon "
            "contact, which distinguishes them from the enforcer equivalent. "
            "They are heavy enough that sustained fine motor work is difficult, "
            "which the military evidently decided was an acceptable trade-off. "
            "They were not wrong."
        ),
        "worn_desc": "Third-Circle gauntlets cover $P hands in hard-laminate plate and arc lining.",
    },

    # =========================================================================
    # LEVEL 5 — HEAVY MILITARY / RESTRICTED
    # Two lines:
    #   Fifth-Circle Rig  — Undercourt Military senior/officer issue.
    #                       Superior physical; solid energy resistance.
    #                       Restricted to officer corps and above.
    #   Ironhollow Plate  — Guild-manufactured heavy armor sold exclusively
    #                       to the military and Inquisitorate under contract.
    #                       Higher physical ceiling; specialized energy plating.
    # =========================================================================

    {
        "key": "hvy_fifthcircle_rig",
        "name": "Fifth-Circle under-rig",
        "level": ARMOR_LEVEL_HEAVY,
        "layer": ARMOR_LAYER_JUMPSUIT,
        "covered_parts": [
            "torso", "back", "abdomen", "groin",
            "left shoulder", "right shoulder", "left arm", "right arm",
            "left thigh", "right thigh",
        ],
        "protection": _prot(slashing=5, impact=5, penetrating=5, burn=2, arc=2, freeze=1),
        "stacking_score": 9,
        "mobility_impact": 3,
        "desc": (
            "The Fifth-Circle under-rig is the officer-grade base layer: "
            "a full-body composite of military-grade void-weave laminate "
            "over a sealed thermal/arc underlayer. The protection level is "
            "a significant step up from Third-Circle, and the weight reflects "
            "this honestly. Wearing the full Fifth-Circle kit is a statement "
            "of intent. The Accord sigil is embossed at the sternum in "
            "raised void-iron, which cannot be removed, defaced, or concealed. "
            "Possession of this garment with an active sigil is self-evidently "
            "authorized. Possession with a tampered sigil is not."
        ),
        "worn_desc": "A Fifth-Circle under-rig covers $P body in heavy officer-grade laminate, void-iron sigil at the sternum.",
    },
    {
        "key": "hvy_fifthcircle_jacket",
        "name": "Fifth-Circle plate jacket",
        "level": ARMOR_LEVEL_HEAVY,
        "layer": ARMOR_LAYER_JACKET,
        "covered_parts": [
            "torso", "back",
            "left shoulder", "right shoulder", "left arm", "right arm",
        ],
        "protection": _prot(slashing=6, impact=6, penetrating=5, burn=3, arc=3, freeze=2),
        "stacking_score": 8,
        "mobility_impact": 3,
        "desc": (
            "The outer plate jacket of Fifth-Circle officer kit: hard void-"
            "weave panels over dense Wardwoven underlayer, with expanded energy "
            "insulation in the chest and shoulder pauldrons. The shoulder "
            "pauldrons extend to cover the upper bicep. The crest-mount on "
            "the right shoulder accepts a rank insignia; this one is vacant. "
            "The joints are articulated with micro-tension springs that aid "
            "the arm movement under the weight — a small quality-of-life "
            "addition that costs more than the rest of the jacket."
        ),
        "worn_desc": "A Fifth-Circle plate jacket covers $P upper body in heavy void-weave military plate.",
    },
    {
        "key": "hvy_fifthcircle_duster",
        "name": "Fifth-Circle command duster",
        "level": ARMOR_LEVEL_HEAVY,
        "layer": ARMOR_LAYER_TRENCHCOAT,
        "covered_parts": [
            "torso", "back", "abdomen",
            "left shoulder", "right shoulder", "left arm", "right arm",
            "left thigh", "right thigh",
        ],
        "protection": _prot(slashing=6, impact=6, penetrating=5, burn=2, arc=3, freeze=1, void=1),
        "stacking_score": 9,
        "mobility_impact": 3,
        "desc": (
            "The command duster of the Fifth-Circle kit — worn by officers "
            "who operate in field command roles and need full-coverage plate "
            "with the visual authority of a long coat. The void-weave panels "
            "run from shoulder to mid-shin in articulated sections. The trace "
            "void protection is not rated for Inquisitorial weapons; it "
            "exists to protect against ambient void contamination in deep-"
            "tunnel operations. The Accord sigil appears at both cuffs. "
            "The drape, despite the weight, is almost elegant."
        ),
        "worn_desc": "A Fifth-Circle command duster hangs over $P frame in articulated void-weave plate.",
    },
    {
        "key": "hvy_fifthcircle_helmet",
        "name": "Fifth-Circle command helmet",
        "level": ARMOR_LEVEL_HEAVY,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["head", "face"],
        "protection": _prot(slashing=6, impact=6, penetrating=5, burn=3, arc=3, freeze=2, void=1),
        "stacking_score": 6,
        "mobility_impact": 0,
        "desc": (
            "The Fifth-Circle command helmet is the most protective head armor "
            "available outside the Inquisitorate. The shell is void-weave laminate "
            "over a sealed energy-insulation core; the visor is multi-layer "
            "plasma-rated with arc discharge and freeze protection. The single "
            "point of void protection is a concession to deployment near "
            "Inquisitorial operations — not rated for direct contact, but enough "
            "for splash exposure. The Accord sigil is fused into the brow plate. "
            "It is visible at thirty meters."
        ),
        "worn_desc": "A Fifth-Circle command helmet covers $P head and face, Accord sigil prominent at the brow.",
    },
    {
        "key": "hvy_fifthcircle_boots",
        "name": "Fifth-Circle sabatons",
        "level": ARMOR_LEVEL_HEAVY,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["left foot", "right foot"],
        "protection": _prot(slashing=5, impact=5, penetrating=4, burn=2, arc=2),
        "stacking_score": 4,
        "mobility_impact": 1,
        "desc": (
            "Articulated void-weave sabatons in military pattern — more plating "
            "than boot, with an armored sole and articulated toe-and-ankle shell "
            "that allows near-full range of motion despite the coverage. They "
            "are louder than enforcer boots but quieter than they look, which is "
            "something. The thermal sole liner handles direct contact with hot "
            "tunnel floors and minor plasma splash without degradation."
        ),
        "worn_desc": "Fifth-Circle sabatons cover $P feet in articulated void-weave plating.",
    },
    {
        "key": "hvy_fifthcircle_gloves",
        "name": "Fifth-Circle heavy gauntlets",
        "level": ARMOR_LEVEL_HEAVY,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["left hand", "right hand"],
        "protection": _prot(slashing=5, impact=5, penetrating=4, arc=3, burn=2),
        "stacking_score": 4,
        "mobility_impact": 0,
        "desc": (
            "Heavy void-weave gauntlets with a full-articulated plate back, "
            "reinforced knuckle bar, and arc-insulated palm extending to "
            "mid-forearm. The arc rating is sufficient for direct baton "
            "contact and incidental gauss field exposure. The articulation "
            "is tight enough that fine motor work — shooting, blade use — "
            "is entirely possible with practice. The practice required is "
            "significant."
        ),
        "worn_desc": "Fifth-Circle heavy gauntlets cover $P hands in articulated void-weave plate.",
    },
    {
        "key": "hvy_ironhollow_jacket",
        "name": "Ironhollow heavy plate jacket",
        "level": ARMOR_LEVEL_HEAVY,
        "layer": ARMOR_LAYER_JACKET,
        "covered_parts": [
            "torso", "back",
            "left shoulder", "right shoulder", "left arm", "right arm",
        ],
        "protection": _prot(slashing=7, impact=6, penetrating=6, burn=4, arc=4, freeze=3),
        "stacking_score": 11,
        "mobility_impact": 4,
        "desc": (
            "The Ironhollow Smithy's contribution to the heavy military market: "
            "a bespoke plate jacket forged from Ironhollow's proprietary alloy "
            "and sold exclusively under contract to the military and "
            "Inquisitorate. The physical protection is the highest of any "
            "non-Inquisitorial item, and the energy insulation exceeds the "
            "Fifth-Circle equivalent. The trade-off is weight — this jacket "
            "weighs more than the full Third-Circle kit combined. Every Ironhollow "
            "Smithy mark is individually registered. This one's registration "
            "has been filed off and the filing has been polished to look "
            "original. Whoever did it was very good."
        ),
        "worn_desc": "An Ironhollow heavy plate jacket covers $P upper body in dense, proprietary alloy plate.",
    },

    # =========================================================================
    # LEVEL 6 — INQUISITORATE (Deep Accord Void-Iron)
    # Forged in void-iron and blessed under the Third Pronouncement of the
    # Deep Accord. The only armor that offers meaningful protection against
    # Inquisitorial weapons — void dissolution, plasma, and arc discharge.
    # Cannot be purchased, sold, or transferred. Each piece is bound to its
    # wearer by an inscription ritual. Possession by unauthorized individuals
    # is grounds for the Inquisitorate's immediate and personal interest.
    # =========================================================================

    {
        "key": "inq_accord_cerecloth_rig",
        "name": "Accord cerecloth under-rig",
        "level": ARMOR_LEVEL_INQUISITOR,
        "layer": ARMOR_LAYER_JUMPSUIT,
        "covered_parts": [
            "torso", "back", "abdomen", "groin",
            "left shoulder", "right shoulder", "left arm", "right arm",
            "left thigh", "right thigh",
        ],
        "protection": _prot(
            slashing=7, impact=7, penetrating=7,
            burn=5, arc=5, freeze=4, void=5, radiation=3
        ),
        "stacking_score": 12,
        "mobility_impact": 3,
        "desc": (
            "The base layer of Inquisitorial armor: a full-body underlayer "
            "of Accord cerecloth — void-iron thread woven into a sealed "
            "composite that protects against dissolution at the molecular "
            "level. The cerecloth was consecrated under the Third Pronouncement "
            "and the rites are woven into the fabric itself, not merely spoken "
            "over it. The void protection is not incidental — it exists because "
            "Inquisitors operate in conditions their weapons create and must "
            "not be dissolved by their own work. The material absorbs ambient "
            "light faintly and is warm to the touch regardless of temperature. "
            "There is a name written inside the collar in a script that reads "
            "differently to each person who looks at it."
        ),
        "worn_desc": "An Accord cerecloth under-rig covers $P body in void-iron weave that seems to absorb the surrounding light.",
    },
    {
        "key": "inq_accord_plate_jacket",
        "name": "Accord plate mantle",
        "level": ARMOR_LEVEL_INQUISITOR,
        "layer": ARMOR_LAYER_JACKET,
        "covered_parts": [
            "torso", "back",
            "left shoulder", "right shoulder", "left arm", "right arm",
        ],
        "protection": _prot(
            slashing=9, impact=9, penetrating=8,
            burn=7, arc=7, freeze=5, void=7
        ),
        "stacking_score": 13,
        "mobility_impact": 3,
        "desc": (
            "The outer plate mantle of Inquisitorial armor: solid void-iron "
            "plate panels over the cerecloth underlayer, each inscribed with "
            "the Rites of Preservation on its inner face. The inscriptions "
            "cannot be seen when the mantle is worn; they are not meant to be "
            "seen. They are meant to function. The physical protection reaches "
            "a level most weapons cannot meaningfully overcome; the energy "
            "insulation was designed by engineers who had seen what their own "
            "plasma weapons do to unprotected tissue and decided they had a "
            "professional interest in not experiencing the same. The shoulder "
            "pauldrons extend to the elbow in the traditional Inquisitorial "
            "long-cape form."
        ),
        "worn_desc": "An Accord plate mantle covers $P upper body in void-iron inscribed with rites invisible to all but the wearer.",
    },
    {
        "key": "inq_accord_mantle_duster",
        "name": "Accord ceremonial duster",
        "level": ARMOR_LEVEL_INQUISITOR,
        "layer": ARMOR_LAYER_TRENCHCOAT,
        "covered_parts": [
            "torso", "back", "abdomen",
            "left shoulder", "right shoulder", "left arm", "right arm",
            "left thigh", "right thigh",
        ],
        "protection": _prot(
            slashing=8, impact=8, penetrating=7,
            burn=6, arc=6, freeze=5, void=6, radiation=3
        ),
        "stacking_score": 14,
        "mobility_impact": 3,
        "desc": (
            "The ceremonial outer duster of the Inquisitorate — worn for "
            "formal proceedings and operational deployment alike, because "
            "the Inquisitorate makes no meaningful distinction between the "
            "two. The duster is void-iron plate in articulated full-length "
            "panels, the outer face etched with the Accord seal from collar "
            "to hem. In full operation dress it hangs open; when sealed, it "
            "covers everything to the ankle. The material does not crease. "
            "Observers universally report finding it difficult to remember "
            "exactly what the wearer looked like after the Inquisitor left "
            "the room."
        ),
        "worn_desc": "An Accord ceremonial duster falls over $P frame in void-iron plate etched with the full Accord seal.",
    },
    {
        "key": "inq_accord_helm",
        "name": "Accord judgment helm",
        "level": ARMOR_LEVEL_INQUISITOR,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["head", "face"],
        "protection": _prot(
            slashing=9, impact=9, penetrating=8,
            burn=7, arc=7, freeze=5, void=8
        ),
        "stacking_score": 12,
        "mobility_impact": 0,
        "desc": (
            "The Accord judgment helm: a full-coverage void-iron shell whose "
            "visor is a single piece of fused void-crystal — opaque from the "
            "outside, perfectly clear from within. The void-crystal absorbs "
            "dissolution energy; the shell absorbs everything else. The "
            "inscriptions on the inner surface are the Rites of Clear Sight "
            "and the Third Pronouncement in full. The helm has a presence "
            "beyond its physical mass — standing near a fully helmed Inquisitor "
            "in a tunnel, bystanders report the air feels different. Thinner. "
            "More deliberate."
        ),
        "worn_desc": "An Accord judgment helm covers $P head and face, void-crystal visor reflecting nothing.",
    },
    {
        "key": "inq_accord_sabatons",
        "name": "Accord sabatons",
        "level": ARMOR_LEVEL_INQUISITOR,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["left foot", "right foot"],
        "protection": _prot(
            slashing=7, impact=7, penetrating=6,
            burn=5, arc=5, freeze=3, void=4, radiation=2
        ),
        "stacking_score": 10,
        "mobility_impact": 1,
        "desc": (
            "Void-iron sabatons in Inquisitorial pattern — fully enclosed "
            "foot armor with articulated toe-sections and an engraved sole "
            "bearing the Accord's mark of passage. The mark means whatever "
            "the Accord decides it means; current consensus is that it "
            "means the ground the Inquisitor walks on has been assessed "
            "and found acceptable, which is a way of saying the Inquisitor's "
            "presence has been authorized everywhere. The steps they produce "
            "are quieter than void-iron should allow."
        ),
        "worn_desc": "Accord sabatons cover $P feet in void-iron, each step quieter than the material warrants.",
    },
    {
        "key": "inq_accord_gauntlets",
        "name": "Accord judgment gauntlets",
        "level": ARMOR_LEVEL_INQUISITOR,
        "layer": ARMOR_LAYER_HELMET_BOOTS_GLOVES,
        "covered_parts": ["left hand", "right hand"],
        "protection": _prot(
            slashing=7, impact=7, penetrating=7,
            burn=6, arc=7, freeze=4, void=5
        ),
        "stacking_score": 11,
        "mobility_impact": 0,
        "desc": (
            "The gauntlets of the Accord: void-iron plate with full articulation "
            "and arc-insulation that is rated to receive the Inquisitor's own "
            "Judgment Gauntlet discharge without resistance loss. The palms are "
            "smooth void-iron; the back-of-hand bears the Rites of Reaching. "
            "Despite the full plate coverage, the articulation is precise enough "
            "for fine work — inscription, ritual, the operation of weapons. "
            "This is not an accident. The design process was thorough. "
            "The gauntlets fit only the registered Inquisitor. Everyone else "
            "who has tried to put them on has regretted it."
        ),
        "worn_desc": "Accord judgment gauntlets cover $P hands in void-iron, the Rites of Reaching etched into the backs.",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_armor_template(key):
    """Return the template dict for key, or None."""
    for t in ARMOR_TEMPLATES:
        if t.get("key") == key:
            return t
    return None


def get_templates_by_level(level):
    """Return all templates at a given armor level, sorted by stacking_score."""
    return sorted(
        [t for t in ARMOR_TEMPLATES if t.get("level") == level],
        key=lambda t: t.get("stacking_score", 0),
    )


def find_armor_template(identifier):
    """
    Find an armor template by spawn key or display name. Case-insensitive on name.
    Returns the template dict or None.
    """
    if not identifier:
        return None
    ident = str(identifier).strip()
    ident_lower = ident.lower()
    for t in ARMOR_TEMPLATES:
        if t.get("key") == ident:
            return t
        name = str(t.get("name", "")).strip().lower()
        if name == ident_lower:
            return t
    return None


def create_armor_from_template(template_key, location=None, quality=100):
    """
    Spawn an Armor object from a template key.
    Returns the created Armor object or None if template not found.
    """
    template = get_armor_template(template_key)
    if not template:
        return None
    from evennia import create_object
    from typeclasses.armor import Armor
    obj = create_object(Armor, key=template["name"], location=location, nohome=True)
    if not obj:
        return None
    obj.db.armor_layer    = template["layer"]
    obj.db.covered_parts  = list(template["covered_parts"])
    obj.db.protection     = dict(template["protection"])
    obj.db.stacking_score = template["stacking_score"]
    obj.db.mobility_impact = template.get("mobility_impact", 0)
    obj.db.quality        = max(0, min(100, int(quality)))
    obj.db.armor_level    = template.get("level", 1)
    obj.db.armor_template = template.get("key")
    if template.get("desc"):
        obj.db.desc = template["desc"]
    if template.get("worn_desc"):
        obj.db.worn_desc = template["worn_desc"]
    return obj

