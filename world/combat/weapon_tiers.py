"""
Weapon tier definitions for the arcanepunk/gutterpunk setting.

TIERS
  T1–T2  Scavenger      Bone, salvaged debris, crude improvised weapons.
  T3–T4  Crafted        Guild-forged, proper materials, journeyman quality.
  T5–T6  Mechanical     Pneumatic, electrified, chemical augmentation.
  T7–T8  Gauss/Magnetic Military-restricted magnetic-accelerator weapons.
  T9–T10 Energy/Eldritch Inquisitorate and senior-military only. Restricted.

STRUCTURE
  Each entry is a dict:
    tier        int           1–10
    name        str           Display name
    weapon_key  str           Maps to world.combat.WEAPON_DATA + world.skills
    damage_type str           Default; individual weapon obj can override via db.damage_type
    desc        str           Look/examine description (MUD 'look' output)
    attacks     list[dict]    Each: {name, damage_min, damage_max, damage_type (optional override)}

  If an attack omits 'damage_type', it inherits the weapon's damage_type.
  'damage_type' on an attack can override for mixed-type weapons (e.g. shock wraps).

USAGE
  Reference this when creating weapon objects in the builder:
    weapon.db.weapon_key  = entry["weapon_key"]
    weapon.db.damage_type = entry["damage_type"]
    weapon.db.desc        = entry["desc"]
  Attacks feed into world.combat.WEAPON_DATA move tables.
"""

# ─────────────────────────────────────────────────────────────────────────────
# UNARMED  (weapon_key: "fists")
# damage_type default: impact
# ─────────────────────────────────────────────────────────────────────────────
UNARMED = [
    {
        "tier": 1,
        "name": "Knuckle Wraps",
        "weapon_key": "fists",
        "damage_type": "impact",
        "desc": (
            "Strips of toughened hide wound tight around the knuckles, "
            "stiffened with salvaged wire. They offer little protection but "
            "keep your hands from shredding on the first punch. Blood has "
            "dried into the weave and never quite washed out."
        ),
        "attacks": [
            {"name": "Jab",          "damage_min": 2, "damage_max": 5},
            {"name": "Haymaker",     "damage_min": 3, "damage_max": 7},
            {"name": "Headbutt",     "damage_min": 2, "damage_max": 5},
            {"name": "Knee Strike",  "damage_min": 3, "damage_max": 6},
            {"name": "Stomp",        "damage_min": 2, "damage_max": 5},
        ],
    },
    {
        "tier": 2,
        "name": "Bone Knuckles",
        "weapon_key": "fists",
        "damage_type": "impact",
        "desc": (
            "A knuckleduster carved from a large femur — likely human, though "
            "nobody asks. The bone has been ground smooth at the grip and left "
            "rough where it meets flesh. It hits with a hollow, satisfying crack "
            "and leaves a bruise shaped like something that used to be a person."
        ),
        "attacks": [
            {"name": "Bonecrusher",     "damage_min": 3, "damage_max": 7},
            {"name": "Overhand Smash",  "damage_min": 4, "damage_max": 8},
            {"name": "Face Rake",       "damage_min": 3, "damage_max": 7},
            {"name": "Gut Punch",       "damage_min": 3, "damage_max": 8},
            {"name": "Hammer Fist",     "damage_min": 4, "damage_max": 8},
        ],
    },
    {
        "tier": 3,
        "name": "Spiked Knuckles",
        "weapon_key": "fists",
        "damage_type": "impact",
        "desc": (
            "Iron knuckles with crude spikes welded to the striking face — "
            "scavenged from god knows what, ground to uneven points on tunnel "
            "stone. Some are sharp, some are blunt, all of them hurt. The grip "
            "is wound with leather to keep from cutting the wielder's own hand, "
            "which is a more recent modification than the spikes."
        ),
        "attacks": [
            {"name": "Spike Jab",      "damage_min": 4, "damage_max": 8},
            {"name": "Raking Backhand","damage_min": 4, "damage_max": 9},
            {"name": "Headbutt",       "damage_min": 3, "damage_max": 7},
            {"name": "Gut Hook",       "damage_min": 5, "damage_max": 9},
            {"name": "Sucker Punch",   "damage_min": 3, "damage_max": 8},
            {"name": "Ground Pound",   "damage_min": 5, "damage_max": 10},
        ],
    },
    {
        "tier": 4,
        "name": "Iron Knuckles",
        "weapon_key": "fists",
        "damage_type": "impact",
        "desc": (
            "Properly forged iron knuckles from a guild smithy — a luxury for "
            "a tunnel-dweller, and you can feel the craftsmanship in the weight. "
            "Tempered twice and polished to a dull sheen. They've been used, "
            "but maintained. Wearing them feels like an upgrade to your entire "
            "right hand."
        ),
        "attacks": [
            {"name": "Iron Jab",    "damage_min": 5,  "damage_max": 10},
            {"name": "Cross",       "damage_min": 6,  "damage_max": 11},
            {"name": "Haymaker",    "damage_min": 7,  "damage_max": 13},
            {"name": "Body Blow",   "damage_min": 5,  "damage_max": 10},
            {"name": "Headbutt",    "damage_min": 5,  "damage_max": 10},
            {"name": "Uppercut",    "damage_min": 7,  "damage_max": 13},
        ],
    },
    {
        "tier": 5,
        "name": "Shock Wraps",
        "weapon_key": "fists",
        "damage_type": "arc",
        "desc": (
            "Canvas fighting wraps threaded with fine copper filaments, connected "
            "to a compact charge-pack strapped at the wrist. Each strike delivers "
            "a sharp current — enough to make a man's teeth click and his legs "
            "unreliable. The pack hums at a frequency that sets bystanders on edge. "
            "Popular in the lower wards where guns are too loud to be profitable."
        ),
        "attacks": [
            {"name": "Charged Jab",     "damage_min": 6,  "damage_max": 11},
            {"name": "Static Cross",    "damage_min": 7,  "damage_max": 12},
            {"name": "Arc Headbutt",    "damage_min": 5,  "damage_max": 10},
            {"name": "Grounding Kick",  "damage_min": 6,  "damage_max": 11},
            {"name": "Voltage Strike",  "damage_min": 8,  "damage_max": 14, "damage_type": "arc"},
            {"name": "Overload Punch",  "damage_min": 9,  "damage_max": 16, "damage_type": "arc"},
        ],
    },
    {
        "tier": 6,
        "name": "Pneumatic Gauntlets",
        "weapon_key": "fists",
        "damage_type": "impact",
        "desc": (
            "Heavy gauntlets fitted with compressed-air cylinders along the "
            "forearm, venting forward on impact. The punch lands normal — then "
            "the piston fires a half-second later, adding a second blow within "
            "the first. The hiss of venting air echoes in tunnels. The canisters "
            "last roughly a hundred full discharges before needing a refill."
        ),
        "attacks": [
            {"name": "Piston Jab",      "damage_min": 8,  "damage_max": 14},
            {"name": "Double-Strike",   "damage_min": 9,  "damage_max": 16},
            {"name": "Hammer Blow",     "damage_min": 10, "damage_max": 17},
            {"name": "Gut Burst",       "damage_min": 9,  "damage_max": 15},
            {"name": "Piston Uppercut", "damage_min": 11, "damage_max": 18},
            {"name": "Overpressure",    "damage_min": 13, "damage_max": 21},
        ],
    },
    {
        "tier": 7,
        "name": "Shock-Spiked Gauntlets",
        "weapon_key": "fists",
        "damage_type": "arc",
        "desc": (
            "Military-forged iron gauntlets with hollow spikes that discharge "
            "stored electrical current on penetration. The arc fires blue-white "
            "when it discharges, and the smell of scorched meat lingers. These "
            "were not made for civilians — the Undercourt Armory seal is stamped "
            "inside the wrist guard, though most of these have been filed off."
        ),
        "attacks": [
            {"name": "Arc Spike",       "damage_min": 11, "damage_max": 18, "damage_type": "arc"},
            {"name": "Charged Rend",    "damage_min": 11, "damage_max": 18},
            {"name": "Grounding Slam",  "damage_min": 12, "damage_max": 20, "damage_type": "arc"},
            {"name": "Voltage Cross",   "damage_min": 13, "damage_max": 20, "damage_type": "arc"},
            {"name": "Thunderstrike",   "damage_min": 15, "damage_max": 23, "damage_type": "arc"},
            {"name": "Seizure Blow",    "damage_min": 14, "damage_max": 22, "damage_type": "arc"},
        ],
    },
    {
        "tier": 8,
        "name": "Gauss Knuckles",
        "weapon_key": "fists",
        "damage_type": "impact",
        "desc": (
            "Knuckles backed by a magnetic accelerator sleeve that fires the fist "
            "forward with electromagnetic force at the moment of contact. The punch "
            "arrives before the wind it displaces. The sleeve glows faint indigo "
            "along the coils when active. Restricted to Undercourt Military Officer "
            "Corps; unauthorized possession is a capital offense in most wards."
        ),
        "attacks": [
            {"name": "Magnetic Jab",      "damage_min": 15, "damage_max": 24},
            {"name": "Rail Punch",        "damage_min": 17, "damage_max": 27},
            {"name": "Accelerated Cross", "damage_min": 16, "damage_max": 26},
            {"name": "Gauss Uppercut",    "damage_min": 19, "damage_max": 30},
            {"name": "Magnetic Slam",     "damage_min": 18, "damage_max": 28},
            {"name": "Coil Overcharge",   "damage_min": 21, "damage_max": 33},
        ],
    },
    {
        "tier": 9,
        "name": "Void-Touched Wraps",
        "weapon_key": "fists",
        "damage_type": "void",
        "desc": (
            "Black wrappings soaked in void-resin harvested from the deep fissures "
            "where eldritch contamination pools thickest. Contact with the material "
            "leaves faint sigils burned into flesh — not wounds exactly, but something "
            "worse. Those struck report seeing the dark between stars for days afterward. "
            "The wrappings smell faintly of nothing, which is more disturbing than any smell."
        ),
        "attacks": [
            {"name": "Void Touch",          "damage_min": 20, "damage_max": 31, "damage_type": "void"},
            {"name": "Sigil Strike",        "damage_min": 21, "damage_max": 33, "damage_type": "void"},
            {"name": "Soul Crush",          "damage_min": 22, "damage_max": 35, "damage_type": "void"},
            {"name": "Resonance Blow",      "damage_min": 20, "damage_max": 32, "damage_type": "void"},
            {"name": "Eldritch Rend",       "damage_min": 24, "damage_max": 37, "damage_type": "void"},
            {"name": "Annihilating Strike", "damage_min": 27, "damage_max": 42, "damage_type": "void"},
        ],
    },
    {
        "tier": 10,
        "name": "Inquisitor's Judgment Gauntlets",
        "weapon_key": "fists",
        "damage_type": "burn",
        "desc": (
            "The gauntlets of a fully-invested Inquisitor of the Deep Accord, wrought "
            "from void-iron and fitted with plasma containment cells in each knuckle. "
            "When activated, the fists blaze with contained thermal fire that leaves "
            "no conventional burn — it unmakes. The sigils etched into the plating are "
            "the names of heresies no longer spoken. Their use requires no authorization; "
            "the bearer is the authorization."
        ),
        "attacks": [
            {"name": "Judgment Blow",      "damage_min": 28, "damage_max": 44, "damage_type": "burn"},
            {"name": "Plasma Strike",      "damage_min": 30, "damage_max": 46, "damage_type": "burn"},
            {"name": "Immolating Fist",    "damage_min": 31, "damage_max": 48, "damage_type": "burn"},
            {"name": "Void Annihilation",  "damage_min": 33, "damage_max": 51, "damage_type": "void"},
            {"name": "Condemnation",       "damage_min": 35, "damage_max": 54, "damage_type": "void"},
            {"name": "Absolute Verdict",   "damage_min": 38, "damage_max": 58, "damage_type": "void"},
        ],
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# BLUNT  (weapon_key: "blunt")
# damage_type default: impact
# ─────────────────────────────────────────────────────────────────────────────
BLUNT = [
    {
        "tier": 1,
        "name": "Knuckle-Bone Club",
        "weapon_key": "blunt",
        "damage_type": "impact",
        "desc": (
            "A large bone — femur or tibia, you don't ask — with smaller knuckle-bones "
            "lashed to the striking end with sinew. Crude, heavy, and it smells, but it "
            "will cave in a skull just as well as anything forged. The lashing has been "
            "re-tied so many times the original sinew is buried somewhere in the middle."
        ),
        "attacks": [
            {"name": "Overhead Smash",   "damage_min": 3, "damage_max": 7},
            {"name": "Backhanded Swing", "damage_min": 3, "damage_max": 6},
            {"name": "Skull Crack",      "damage_min": 4, "damage_max": 8},
            {"name": "Gut Bash",         "damage_min": 3, "damage_max": 7},
            {"name": "Ground Pound",     "damage_min": 4, "damage_max": 8},
        ],
    },
    {
        "tier": 2,
        "name": "Scrap Iron Bar",
        "weapon_key": "blunt",
        "damage_type": "impact",
        "desc": (
            "A length of rebar torn from a collapsed tunnel section, bent roughly "
            "straight and wrapped at one end with salvaged rubber for a grip. Heavy, "
            "unbalanced, and unrefined — but iron is iron, and this is heavy enough "
            "to matter. The rust-stains that won't scrub off are not all rust."
        ),
        "attacks": [
            {"name": "Bar Swing",      "damage_min": 4, "damage_max": 8},
            {"name": "Rebar Jab",      "damage_min": 4, "damage_max": 7},
            {"name": "Overhand Bash",  "damage_min": 5, "damage_max": 9},
            {"name": "Body Strike",    "damage_min": 4, "damage_max": 8},
            {"name": "Leg Sweep",      "damage_min": 3, "damage_max": 7},
            {"name": "Skull Cracker",  "damage_min": 5, "damage_max": 10},
        ],
    },
    {
        "tier": 3,
        "name": "Bound Cudgel",
        "weapon_key": "blunt",
        "damage_type": "impact",
        "desc": (
            "A solid length of dense hardwood, likely salvaged from a structural "
            "beam, wound at intervals with iron wire to prevent splitting. The head "
            "is weighted with a cluster of chain links for extra striking mass. "
            "It is not elegant, but whoever made it put real care into making it last. "
            "It has lasted."
        ),
        "attacks": [
            {"name": "Cudgel Swing",      "damage_min": 5, "damage_max": 10},
            {"name": "Chain-Wrap Strike", "damage_min": 6, "damage_max": 11},
            {"name": "Overhand Smash",    "damage_min": 7, "damage_max": 12},
            {"name": "Shield Breaker",    "damage_min": 6, "damage_max": 11},
            {"name": "Staggering Blow",   "damage_min": 7, "damage_max": 12},
            {"name": "Temple Strike",     "damage_min": 8, "damage_max": 13},
        ],
    },
    {
        "tier": 4,
        "name": "Ironhollow Warhammer",
        "weapon_key": "blunt",
        "damage_type": "impact",
        "desc": (
            "A guild-forged warhammer with a flanged head and an ash haft, properly "
            "weighted and balanced. The head is stamped with the guild-mark of the "
            "Ironhollow Smithy — a name worth something in the middle wards. No "
            "ornamentation, no flourish. Just mass, leverage, and intent. Someone "
            "has oiled the haft recently."
        ),
        "attacks": [
            {"name": "Hammer Blow",       "damage_min": 7,  "damage_max": 13},
            {"name": "Flanged Strike",    "damage_min": 7,  "damage_max": 14},
            {"name": "Crushing Overhead", "damage_min": 9,  "damage_max": 15},
            {"name": "Backswing",         "damage_min": 7,  "damage_max": 12},
            {"name": "Leg Break",         "damage_min": 8,  "damage_max": 14},
            {"name": "Skull Shatter",     "damage_min": 10, "damage_max": 17},
        ],
    },
    {
        "tier": 5,
        "name": "Morningstar",
        "weapon_key": "blunt",
        "damage_type": "impact",
        "desc": (
            "A heavy iron ball studded with sharpened flanges, on a short chain "
            "attached to a hardwood haft. Guild-made, recently restamped. The chain "
            "clacks against the flanges when it moves — oddly musical before a fight. "
            "The flanges have been sharpened recently enough that they still gleam "
            "at the tips."
        ),
        "attacks": [
            {"name": "Chain Swing",    "damage_min": 8,  "damage_max": 14},
            {"name": "Spike Rake",     "damage_min": 8,  "damage_max": 15},
            {"name": "Overhead Lash",  "damage_min": 9,  "damage_max": 16},
            {"name": "Flange Strike",  "damage_min": 9,  "damage_max": 15},
            {"name": "Wraparound",     "damage_min": 10, "damage_max": 16},
            {"name": "Skull Mash",     "damage_min": 11, "damage_max": 18},
        ],
    },
    {
        "tier": 6,
        "name": "Enforcer's Arc Baton",
        "weapon_key": "blunt",
        "damage_type": "arc",
        "desc": (
            "A reinforced steel baton with an insulated rubber grip and an exposed "
            "contact head wired to a capacitor pack at the belt. The head crackles "
            "blue when active; the hum it emits is enough to make bystanders "
            "uncomfortable. Standard issue for enforcer companies in the upper wards. "
            "There is a lot to infer from where you found this one."
        ),
        "attacks": [
            {"name": "Shock Jab",         "damage_min": 9,  "damage_max": 15, "damage_type": "arc"},
            {"name": "Capacitor Swing",   "damage_min": 10, "damage_max": 16, "damage_type": "arc"},
            {"name": "Charge Discharge",  "damage_min": 11, "damage_max": 18, "damage_type": "arc"},
            {"name": "Body Arc",          "damage_min": 10, "damage_max": 17, "damage_type": "arc"},
            {"name": "Overload Strike",   "damage_min": 13, "damage_max": 20, "damage_type": "arc"},
            {"name": "Grounding Bash",    "damage_min": 13, "damage_max": 21, "damage_type": "arc"},
        ],
    },
    {
        "tier": 7,
        "name": "Pneumatic Maul",
        "weapon_key": "blunt",
        "damage_type": "impact",
        "desc": (
            "A heavy maul head fitted with a pneumatic compression cylinder in the "
            "haft. On the downswing, the cylinder vents, adding a hammer-blow of "
            "compressed air at the exact moment of contact. The result is a strike "
            "that hits twice: once with iron, once with force. Requires an air "
            "canister that lasts roughly a hundred full swings. The canister vents "
            "with a percussive crack that echoes beautifully in tunnels."
        ),
        "attacks": [
            {"name": "Pneumatic Overhead", "damage_min": 12, "damage_max": 20},
            {"name": "Vent Slam",          "damage_min": 13, "damage_max": 21},
            {"name": "Air-Burst Strike",   "damage_min": 14, "damage_max": 22},
            {"name": "Compression Bash",   "damage_min": 13, "damage_max": 20},
            {"name": "Piston Overhead",    "damage_min": 15, "damage_max": 24},
            {"name": "Overpressure Maul",  "damage_min": 17, "damage_max": 27},
        ],
    },
    {
        "tier": 8,
        "name": "Gauss Hammer",
        "weapon_key": "blunt",
        "damage_type": "impact",
        "desc": (
            "A military-issue warhammer whose head is wrapped in superconductor coils "
            "that charge on the backswing and release on contact with concentrated "
            "magnetic force, multiplying the wielder's own strength many times over. "
            "The head is heavier than it looks, the coils warm to the touch after "
            "sustained use, and the impact sound is a deep, bone-shaking crack that "
            "carries down a tunnel for a very long way."
        ),
        "attacks": [
            {"name": "Magnetic Swing",      "damage_min": 17, "damage_max": 27},
            {"name": "Coil Slam",           "damage_min": 18, "damage_max": 29},
            {"name": "Electromagnetic Crush","damage_min": 19, "damage_max": 30},
            {"name": "Rail Overhead",       "damage_min": 20, "damage_max": 32},
            {"name": "Magnetic Shockwave",  "damage_min": 21, "damage_max": 33},
            {"name": "Coil Overcharge",     "damage_min": 24, "damage_max": 37},
        ],
    },
    {
        "tier": 9,
        "name": "Arc Mace",
        "weapon_key": "blunt",
        "damage_type": "arc",
        "desc": (
            "A heavy iron mace enclosed in an arc-discharge cage of crackling "
            "copper-gilt lattice, connected to a military-grade capacitor spine "
            "running the length of the haft. Each swing trails a crescent of blue "
            "lightning. The cage channels the discharge into the target on contact, "
            "cooking tissue through armor. It is a weapon of authorized violence, "
            "and the authorization is engraved on the ricasso."
        ),
        "attacks": [
            {"name": "Arc Swing",        "damage_min": 21, "damage_max": 33, "damage_type": "arc"},
            {"name": "Lightning Strike", "damage_min": 22, "damage_max": 35, "damage_type": "arc"},
            {"name": "Chain Lightning",  "damage_min": 20, "damage_max": 33, "damage_type": "arc"},
            {"name": "Thunder Smash",    "damage_min": 24, "damage_max": 37, "damage_type": "arc"},
            {"name": "Capacitor Burst",  "damage_min": 25, "damage_max": 40, "damage_type": "arc"},
            {"name": "Arc Shatter",      "damage_min": 28, "damage_max": 44, "damage_type": "arc"},
        ],
    },
    {
        "tier": 10,
        "name": "The Condemner",
        "weapon_key": "blunt",
        "damage_type": "void",
        "desc": (
            "The ceremonial-yet-functional mace of an Inquisitor of the Deep Accord, "
            "forged from void-iron and inlaid with burning sigils of containment. "
            "The head pulses with a dark light that is not light — and things struck "
            "by it do not simply break. They come apart at the root, as though the "
            "material bonds themselves have been judged and found wanting. Its name "
            "is carved into the haft in the old script. It is a name that means "
            "exactly what it says."
        ),
        "attacks": [
            {"name": "Judgment Swing",     "damage_min": 27, "damage_max": 43, "damage_type": "void"},
            {"name": "Sigil Detonation",   "damage_min": 29, "damage_max": 46, "damage_type": "void"},
            {"name": "Immolating Bash",    "damage_min": 28, "damage_max": 44, "damage_type": "burn"},
            {"name": "Void Fracture",      "damage_min": 31, "damage_max": 49, "damage_type": "void"},
            {"name": "Condemnation",       "damage_min": 33, "damage_max": 52, "damage_type": "void"},
            {"name": "Absolute Dissolution","damage_min": 37, "damage_max": 58, "damage_type": "void"},
        ],
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# SHORT BLADES  (weapon_key: "knife")
# damage_type default: slashing
# ─────────────────────────────────────────────────────────────────────────────
SHORT_BLADE = [
    {
        "tier": 1,
        "name": "Glass Shard",
        "weapon_key": "knife",
        "damage_type": "slashing",
        "desc": (
            "A thick shard of reinforced tunnel glass, one edge wrapped in salvaged "
            "rubber to protect the hand. It is not a knife — it is desperation with "
            "an edge. The wrap is coming loose at one end, and the unprotected tip "
            "will cut the wielder almost as readily as an enemy."
        ),
        "attacks": [
            {"name": "Quick Slash",     "damage_min": 2, "damage_max": 5},
            {"name": "Jagged Cut",      "damage_min": 3, "damage_max": 6},
            {"name": "Stab",            "damage_min": 2, "damage_max": 5},
            {"name": "Raking Slash",    "damage_min": 3, "damage_max": 6},
            {"name": "Desperate Thrust","damage_min": 2, "damage_max": 6},
        ],
    },
    {
        "tier": 2,
        "name": "Shiv",
        "weapon_key": "knife",
        "damage_type": "slashing",
        "desc": (
            "A handmade shiv fashioned from a snapped screwdriver shaft and a "
            "handle of wound electrical tape. The blade is ground to a ragged point "
            "on tunnel stone. Unimpressive to look at — which is entirely the point. "
            "Half the wards have one of these hidden somewhere. Some people have several."
        ),
        "attacks": [
            {"name": "Quick Stab",       "damage_min": 3, "damage_max": 6},
            {"name": "Slash",            "damage_min": 3, "damage_max": 7},
            {"name": "Gut Thrust",       "damage_min": 4, "damage_max": 8},
            {"name": "Desperate Cut",    "damage_min": 3, "damage_max": 7},
            {"name": "Backhanded Slash", "damage_min": 3, "damage_max": 7},
            {"name": "Throat Cut",       "damage_min": 5, "damage_max": 9},
        ],
    },
    {
        "tier": 3,
        "name": "Scrap Knife",
        "weapon_key": "knife",
        "damage_type": "slashing",
        "desc": (
            "A proper knife by gutter standards: a blade cut from thick tunnel-grade "
            "steel plate and given a simple handle of carved bone, riveted through. "
            "The edge holds reasonably well and has been whetted recently — you can "
            "tell by the way it catches the light at the bevel. It is functional, "
            "which in the tunnels is rarer than it ought to be."
        ),
        "attacks": [
            {"name": "Quick Slash",      "damage_min": 4, "damage_max": 8},
            {"name": "Low Stab",         "damage_min": 5, "damage_max": 9},
            {"name": "Gut Rake",         "damage_min": 5, "damage_max": 9},
            {"name": "Throat Slash",     "damage_min": 5, "damage_max": 10},
            {"name": "Parry & Riposte",  "damage_min": 4, "damage_max": 9},
            {"name": "Downward Stab",    "damage_min": 6, "damage_max": 11},
        ],
    },
    {
        "tier": 4,
        "name": "Iron Dirk",
        "weapon_key": "knife",
        "damage_type": "slashing",
        "desc": (
            "A guild-forged double-edged iron dirk with a simple crossguard and a "
            "wrapped bone grip. The blade is well-proportioned — long enough to "
            "matter, short enough to conceal. The crossguard is stamped with the "
            "maker's mark and dented from use, but the steel is clean and holds "
            "an edge."
        ),
        "attacks": [
            {"name": "Thrust",           "damage_min": 6,  "damage_max": 11},
            {"name": "Crossguard Slash", "damage_min": 6,  "damage_max": 12},
            {"name": "Low Cut",          "damage_min": 5,  "damage_max": 10},
            {"name": "Double-Edge Rake", "damage_min": 7,  "damage_max": 12},
            {"name": "Body Stab",        "damage_min": 7,  "damage_max": 13},
            {"name": "Gut Thrust",       "damage_min": 8,  "damage_max": 14},
        ],
    },
    {
        "tier": 5,
        "name": "Serrated Hunter's Knife",
        "weapon_key": "knife",
        "damage_type": "slashing",
        "desc": (
            "A hunting knife with a partially serrated spine and a full-tang blade "
            "of high-carbon guild steel. The serrations are designed to catch on the "
            "draw, tearing what they have already cut. The handle is wrapped in leather "
            "taken from a surface creature. There is a small fuller that carries blood "
            "away from the edge. This is a tool that knows exactly what it is."
        ),
        "attacks": [
            {"name": "Clean Slash",    "damage_min": 7,  "damage_max": 13},
            {"name": "Serrated Draw",  "damage_min": 8,  "damage_max": 14},
            {"name": "Gut Stab",       "damage_min": 8,  "damage_max": 14},
            {"name": "Rib Rake",       "damage_min": 7,  "damage_max": 13},
            {"name": "Throat Cut",     "damage_min": 9,  "damage_max": 15},
            {"name": "Ripping Slash",  "damage_min": 9,  "damage_max": 16},
        ],
    },
    {
        "tier": 6,
        "name": "Venomous Splicer",
        "weapon_key": "knife",
        "damage_type": "slashing",
        "desc": (
            "A compact double-bladed punch dagger fitted with a reservoir in the "
            "grip that feeds cultivated paralytic venom from subterranean creatures "
            "through hollow channels in the blade. The venom weeps from fine holes "
            "along the edge. The reservoir holds enough for roughly a dozen cuts. "
            "The blade smells faintly sweet, which is the last pleasant thing "
            "about it."
        ),
        "attacks": [
            {"name": "Venom Jab",      "damage_min": 8,  "damage_max": 14},
            {"name": "Paralytic Rake", "damage_min": 9,  "damage_max": 15},
            {"name": "Hollow Strike",  "damage_min": 9,  "damage_max": 15},
            {"name": "Toxin Thrust",   "damage_min": 9,  "damage_max": 16},
            {"name": "Bleeding Slash", "damage_min": 10, "damage_max": 17},
            {"name": "Venom Flood",    "damage_min": 11, "damage_max": 18},
        ],
    },
    {
        "tier": 7,
        "name": "Pneumatic Punch Dagger",
        "weapon_key": "knife",
        "damage_type": "penetrating",
        "desc": (
            "A forearm-mounted blade with a compressed-air cylinder that fires "
            "it forward on contact, driving it roughly two inches deeper than "
            "the wielder's own strike. The cylinder vents with a sharp hiss on "
            "each thrust. Canister change required every forty strikes. Leaves "
            "wounds that surgeons wince at and that describe a very specific "
            "and regrettable decision."
        ),
        "attacks": [
            {"name": "Pneumatic Thrust",   "damage_min": 12, "damage_max": 19},
            {"name": "Vent Stab",          "damage_min": 12, "damage_max": 20},
            {"name": "Air-Driven Rend",    "damage_min": 13, "damage_max": 21},
            {"name": "Deep Punch",         "damage_min": 12, "damage_max": 20},
            {"name": "Compression Stab",   "damage_min": 14, "damage_max": 23},
            {"name": "Overpressure Thrust","damage_min": 16, "damage_max": 25},
        ],
    },
    {
        "tier": 8,
        "name": "Gauss Stiletto",
        "weapon_key": "knife",
        "damage_type": "penetrating",
        "desc": (
            "A military-issue stiletto with a long needle blade riding a linear "
            "magnetic accelerator sleeve built into the handle. At the press of a "
            "thumb stud, the blade fires forward with electromagnetic force before "
            "retracting on a spring — effective range roughly eight inches beyond "
            "the hand. At close range it punches through light armor with "
            "contemptuous ease. The Undercourt Armory mark has not been removed "
            "from this one."
        ),
        "attacks": [
            {"name": "Magnetic Thrust",  "damage_min": 17, "damage_max": 26},
            {"name": "Rail Stab",        "damage_min": 18, "damage_max": 28},
            {"name": "Accelerated Rend", "damage_min": 17, "damage_max": 27},
            {"name": "Gauss Penetration","damage_min": 19, "damage_max": 30},
            {"name": "Deep Drive",       "damage_min": 20, "damage_max": 32},
            {"name": "Mag-Overcharge",   "damage_min": 22, "damage_max": 35},
        ],
    },
    {
        "tier": 9,
        "name": "Arc Fang",
        "weapon_key": "knife",
        "damage_type": "arc",
        "desc": (
            "A military-restricted shock knife with a blade of polarized copper-alloy "
            "lattice and an arc-discharge emitter embedded in the crossguard. The "
            "blade does not cut — it conducts. Contact delivers a focused arc that "
            "stops hearts and fries nerves depending on placement. The blade glows "
            "ice-blue when active and hums at a frequency just below conscious hearing. "
            "Your teeth know it's there."
        ),
        "attacks": [
            {"name": "Arc Slash",        "damage_min": 22, "damage_max": 34, "damage_type": "arc"},
            {"name": "Discharge Stab",   "damage_min": 23, "damage_max": 36, "damage_type": "arc"},
            {"name": "Nerve Slash",      "damage_min": 21, "damage_max": 34, "damage_type": "arc"},
            {"name": "Shorting Rake",    "damage_min": 23, "damage_max": 36, "damage_type": "arc"},
            {"name": "Capacitor Release","damage_min": 25, "damage_max": 40, "damage_type": "arc"},
            {"name": "Heart-Stop",       "damage_min": 27, "damage_max": 43, "damage_type": "arc"},
        ],
    },
    {
        "tier": 10,
        "name": "Inquisitor's Fang",
        "weapon_key": "knife",
        "damage_type": "void",
        "desc": (
            "One of a pair of ritual daggers granted upon full Inquisitor "
            "investiture, forged in void-iron and inscribed with the rites of "
            "the First Pronouncement. The blade absorbs light rather than "
            "reflecting it. A cut from the Fang does not bleed immediately — "
            "the wound seals at first. Then something inside begins to come "
            "undone. Medical staff who have treated Fang wounds do not describe "
            "the experience willingly."
        ),
        "attacks": [
            {"name": "Void Slash",          "damage_min": 26, "damage_max": 41, "damage_type": "void"},
            {"name": "Consuming Thrust",    "damage_min": 27, "damage_max": 43, "damage_type": "void"},
            {"name": "Soul-Cut",            "damage_min": 28, "damage_max": 44, "damage_type": "void"},
            {"name": "Unmaking Slash",      "damage_min": 27, "damage_max": 43, "damage_type": "void"},
            {"name": "Rite of Ending",      "damage_min": 30, "damage_max": 48, "damage_type": "void"},
            {"name": "First Pronouncement", "damage_min": 34, "damage_max": 53, "damage_type": "void"},
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# LONG BLADES  (weapon_key: "long_blade")
# damage_type default: slashing
# ─────────────────────────────────────────────────────────────────────────────
LONG_BLADE = [
    {
        "tier": 1,
        "name": "Scrap Machete",
        "weapon_key": "long_blade",
        "damage_type": "slashing",
        "desc": (
            "A wide blade roughly cut from a sheet of salvaged tunnel iron, its "
            "edge hammered sharp on stone. It looks exactly like what it is: not "
            "a weapon by design but by necessity. The handle is wrapped in pipe "
            "insulation and secured with wire. It will rust if you let it, and "
            "you should not let it."
        ),
        "attacks": [
            {"name": "Chop",           "damage_min": 3, "damage_max": 7},
            {"name": "Backhanded Slash","damage_min": 3, "damage_max": 7},
            {"name": "Wide Sweep",     "damage_min": 4, "damage_max": 8},
            {"name": "Overhead Hack",  "damage_min": 4, "damage_max": 9},
            {"name": "Low Cut",        "damage_min": 3, "damage_max": 7},
        ],
    },
    {
        "tier": 2,
        "name": "Bone Cleaver",
        "weapon_key": "long_blade",
        "damage_type": "slashing",
        "desc": (
            "A large blade fashioned from the thick, flat bones of a surface "
            "creature — a deep-spine, from the size of the plates. The bone has "
            "been carved and ground to hold a rough edge. It is unwieldy and "
            "slightly curved in the wrong direction, but heavy enough that none "
            "of that matters much in a close tunnel."
        ),
        "attacks": [
            {"name": "Cleave",          "damage_min": 4, "damage_max": 9},
            {"name": "Bone Sweep",      "damage_min": 4, "damage_max": 9},
            {"name": "Overhead Chop",   "damage_min": 5, "damage_max": 10},
            {"name": "Raking Slash",    "damage_min": 4, "damage_max": 9},
            {"name": "Desperate Swing", "damage_min": 4, "damage_max": 8},
            {"name": "Boning Thrust",   "damage_min": 5, "damage_max": 10},
        ],
    },
    {
        "tier": 3,
        "name": "Tunnel Shortsword",
        "weapon_key": "long_blade",
        "damage_type": "slashing",
        "desc": (
            "A straightforward short sword hammered from salvaged iron and "
            "competently ground to an edge. The guard is a simple crosspiece; "
            "the grip is wrapped leather. It is not beautiful. It is functional, "
            "which is everything in the tunnels. The blade has a slight taper "
            "that suggests someone who knew what a sword was supposed to do."
        ),
        "attacks": [
            {"name": "Slash",            "damage_min": 5, "damage_max": 11},
            {"name": "Thrust",           "damage_min": 5, "damage_max": 11},
            {"name": "Crossguard Strike","damage_min": 5, "damage_max": 10},
            {"name": "Low Sweep",        "damage_min": 5, "damage_max": 11},
            {"name": "Rising Cut",       "damage_min": 6, "damage_max": 12},
            {"name": "Overhead Slash",   "damage_min": 7, "damage_max": 13},
        ],
    },
    {
        "tier": 4,
        "name": "Guild Broadsword",
        "weapon_key": "long_blade",
        "damage_type": "slashing",
        "desc": (
            "A properly forged broadsword bearing the stamp of a licensed guild "
            "smithy — a mark worth something. The blade is wide enough for a "
            "proper defensive guard and balanced enough that a skilled fighter "
            "can use it quickly. The fuller runs two-thirds of the length, and "
            "the crossguard curves slightly forward. The grip has been replaced "
            "more than once."
        ),
        "attacks": [
            {"name": "Cleaving Slash",  "damage_min": 7,  "damage_max": 13},
            {"name": "Thrust",          "damage_min": 7,  "damage_max": 13},
            {"name": "Bind & Slash",    "damage_min": 8,  "damage_max": 14},
            {"name": "Half-Sword",      "damage_min": 7,  "damage_max": 13},
            {"name": "Rising Cut",      "damage_min": 8,  "damage_max": 14},
            {"name": "Heavy Overhead",  "damage_min": 9,  "damage_max": 16},
        ],
    },
    {
        "tier": 5,
        "name": "Executioner's Blade",
        "weapon_key": "long_blade",
        "damage_type": "slashing",
        "desc": (
            "A weapon designed for judicial beheadings but more than serviceable "
            "in combat: heavy, single-edged, with a reinforced spine and a "
            "forward-weighted tip built for cleaving force. This one has seen "
            "use beyond ceremony. The blade is clean, the edge freshly honed, "
            "and the grip replaced more recently than the steel. The pommel is "
            "engraved with a scale of justice, half-scratched off."
        ),
        "attacks": [
            {"name": "Executioner's Slash", "damage_min": 9,  "damage_max": 16},
            {"name": "Forward-Weight Cleave","damage_min": 10, "damage_max": 17},
            {"name": "Spine Strike",        "damage_min": 8,  "damage_max": 15},
            {"name": "Half-Blade Rend",     "damage_min": 9,  "damage_max": 16},
            {"name": "Sweeping Behead",     "damage_min": 11, "damage_max": 18},
            {"name": "Final Verdict",       "damage_min": 12, "damage_max": 19},
        ],
    },
    {
        "tier": 6,
        "name": "Electro-Saber",
        "weapon_key": "long_blade",
        "damage_type": "arc",
        "desc": (
            "A saber blade with an insulated spine and an exposed cutting edge "
            "connected to an arc induction coil running through the guard. The "
            "edge carries a persistent electrical current — not lethal on its own, "
            "but every cut conducts. The blade hums faintly in a quiet corridor. "
            "The guard displays the ward-seal of a licensed enforcer company. "
            "The seal has not deterred previous owners from acquiring it."
        ),
        "attacks": [
            {"name": "Arc Slash",       "damage_min": 10, "damage_max": 17, "damage_type": "arc"},
            {"name": "Conducting Cut",  "damage_min": 10, "damage_max": 16, "damage_type": "arc"},
            {"name": "Saber Thrust",    "damage_min": 9,  "damage_max": 15},
            {"name": "Live-Edge Sweep", "damage_min": 11, "damage_max": 18, "damage_type": "arc"},
            {"name": "Charged Cleave",  "damage_min": 12, "damage_max": 19, "damage_type": "arc"},
            {"name": "Discharge Slash", "damage_min": 13, "damage_max": 21, "damage_type": "arc"},
        ],
    },
    {
        "tier": 7,
        "name": "Resonance Blade",
        "weapon_key": "long_blade",
        "damage_type": "slashing",
        "desc": (
            "A vibroblade whose edge oscillates at a frequency engineered to "
            "disrupt molecular bonds — in practice, it passes through materials "
            "that would stop ordinary steel. The hilt contains the resonance "
            "generator, which produces a subsonic pitch that registers more as "
            "a feeling in the chest than a sound. Military-grade, with an officer's "
            "registration number engraved on the ricasso. Someone filed it down "
            "but not deep enough."
        ),
        "attacks": [
            {"name": "Resonance Slash",    "damage_min": 13, "damage_max": 21},
            {"name": "Vibro-Thrust",       "damage_min": 14, "damage_max": 22},
            {"name": "Frequency Sweep",    "damage_min": 13, "damage_max": 21},
            {"name": "Deep-Cut",           "damage_min": 14, "damage_max": 23},
            {"name": "Harmonic Cleave",    "damage_min": 15, "damage_max": 24},
            {"name": "Resonance Overload", "damage_min": 17, "damage_max": 28},
        ],
    },
    {
        "tier": 8,
        "name": "Gauss Sword",
        "weapon_key": "long_blade",
        "damage_type": "slashing",
        "desc": (
            "A long blade forged from a steel-magnetic composite, riding an "
            "electromagnetic accelerator in the hilt that amplifies every swing "
            "with focused magnetic force. The edge carries a charge that repels "
            "the blade from impacts in a way that preserves the steel. Not a "
            "weapon for civilians — the hilt bears the sigil of the Undercourt "
            "Military Armory in a place that cannot be filed without destroying "
            "the accelerator housing."
        ),
        "attacks": [
            {"name": "Magnetic Slash",       "damage_min": 18, "damage_max": 28},
            {"name": "Rail-Edge Cut",        "damage_min": 19, "damage_max": 30},
            {"name": "Accelerated Thrust",   "damage_min": 18, "damage_max": 29},
            {"name": "Gauss Sweep",          "damage_min": 20, "damage_max": 32},
            {"name": "Magnetic Cleave",      "damage_min": 21, "damage_max": 34},
            {"name": "Electromagnetic Surge","damage_min": 24, "damage_max": 38},
        ],
    },
    {
        "tier": 9,
        "name": "Plasma Saber",
        "weapon_key": "long_blade",
        "damage_type": "burn",
        "desc": (
            "A crucible-forged hilt containing a focused plasma containment cell "
            "that projects a blade of magnetically-confined plasma at saber length. "
            "The 'blade' is achingly bright in tunnel light and makes the air "
            "shimmer with thermal distortion. It cuts through armor the way light "
            "moves through shadow — without acknowledging it. Restricted to senior "
            "military and Inquisitorial adjuncts. Looking directly at it in darkness "
            "is inadvisable."
        ),
        "attacks": [
            {"name": "Plasma Slash",    "damage_min": 23, "damage_max": 36, "damage_type": "burn"},
            {"name": "Thermal Cut",     "damage_min": 24, "damage_max": 37, "damage_type": "burn"},
            {"name": "Core-Burn",       "damage_min": 24, "damage_max": 38, "damage_type": "burn"},
            {"name": "Plasma Thrust",   "damage_min": 23, "damage_max": 37, "damage_type": "burn"},
            {"name": "Fusion Sweep",    "damage_min": 26, "damage_max": 42, "damage_type": "burn"},
            {"name": "Meltdown Strike", "damage_min": 29, "damage_max": 46, "damage_type": "burn"},
        ],
    },
    {
        "tier": 10,
        "name": "Inquisitor's Judgment Blade",
        "weapon_key": "long_blade",
        "damage_type": "void",
        "desc": (
            "The primary weapon of a fully-invested Inquisitor: a long sword of "
            "void-iron whose blade absorbs ambient light and reflects nothing. "
            "The inscribed rites of the Accord run from forte to tip in a script "
            "that uninitiated observers cannot look at directly for long. Wounds "
            "from the Judgment Blade do not close naturally. They are not wounds, "
            "strictly speaking. They are corrections."
        ),
        "attacks": [
            {"name": "Pronouncement Slash","damage_min": 27, "damage_max": 43, "damage_type": "void"},
            {"name": "Void Thrust",        "damage_min": 28, "damage_max": 45, "damage_type": "void"},
            {"name": "Rite of Severance",  "damage_min": 29, "damage_max": 46, "damage_type": "void"},
            {"name": "Soul Cleave",        "damage_min": 30, "damage_max": 48, "damage_type": "void"},
            {"name": "Consuming Sweep",    "damage_min": 31, "damage_max": 50, "damage_type": "void"},
            {"name": "Final Judgment",     "damage_min": 36, "damage_max": 56, "damage_type": "void"},
        ],
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# SIDEARMS  (weapon_key: "sidearm")
# damage_type default: penetrating
# ─────────────────────────────────────────────────────────────────────────────
SIDEARM = [
    {
        "tier": 1,
        "name": "Zip Gun",
        "weapon_key": "sidearm",
        "damage_type": "penetrating",
        "desc": (
            "A single-shot improvised firearm: a pipe barrel, a nail-and-spring "
            "firing mechanism, and a handle of bound wood scraps. It fires a "
            "single round loaded directly into the barrel by hand and must be "
            "reloaded the same way after every shot. Loud, inaccurate, and "
            "just as likely to misfire as to discharge — but it fires, and in "
            "the tunnels that is all that is asked of it."
        ),
        "attacks": [
            {"name": "Point-Blank Shot",   "damage_min": 5,  "damage_max": 9},
            {"name": "Lucky Shot",         "damage_min": 4,  "damage_max": 8},
            {"name": "Desperation Fire",   "damage_min": 4,  "damage_max": 9},
            {"name": "Jammed Discharge",   "damage_min": 3,  "damage_max": 7},
            {"name": "Wild Shot",          "damage_min": 3,  "damage_max": 8},
        ],
    },
    {
        "tier": 2,
        "name": "Powder Flintlock",
        "weapon_key": "sidearm",
        "damage_type": "penetrating",
        "desc": (
            "A black-powder flintlock pistol rebuilt from salvaged components, "
            "firing ball shot from a brass barrel. The lock mechanism is replaced "
            "and re-fitted; the grip repaired with a dowel. It fires once per "
            "loading with a satisfying crack and a cloud of grey smoke that ends "
            "any ambiguity about your position. Reloading takes around thirty "
            "seconds, which is a lifetime underground."
        ),
        "attacks": [
            {"name": "Flintlock Shot",       "damage_min": 5,  "damage_max": 10},
            {"name": "Point-Blank Discharge","damage_min": 7,  "damage_max": 12},
            {"name": "Deliberate Aim",       "damage_min": 6,  "damage_max": 11},
            {"name": "Wild Shot",            "damage_min": 4,  "damage_max": 9},
            {"name": "Powder Burst",         "damage_min": 6,  "damage_max": 11},
        ],
    },
    {
        "tier": 3,
        "name": "Percussion Revolver",
        "weapon_key": "sidearm",
        "damage_type": "penetrating",
        "desc": (
            "A six-chamber percussion revolver, hand-loaded with powder and ball. "
            "The cylinder rotates smoothly and the hammer falls clean. Slow to "
            "reload — powder into each chamber, ball and patch, tamp — but it "
            "fires six times before you have to stop. The barrel is engraved "
            "with a serpent eating its own tail. Someone cared about this once, "
            "and maybe still does."
        ),
        "attacks": [
            {"name": "Revolver Shot",   "damage_min": 6,  "damage_max": 11},
            {"name": "Fan the Hammer",  "damage_min": 5,  "damage_max": 10},
            {"name": "Aimed Shot",      "damage_min": 8,  "damage_max": 13},
            {"name": "Point-Blank",     "damage_min": 7,  "damage_max": 12},
            {"name": "Double Action",   "damage_min": 6,  "damage_max": 11},
            {"name": "Desperation Fire","damage_min": 5,  "damage_max": 10},
        ],
    },
    {
        "tier": 4,
        "name": "Break-Action Pistol",
        "weapon_key": "sidearm",
        "damage_type": "penetrating",
        "desc": (
            "A compact break-action double-barrel pistol chambered for metallic "
            "cartridges. The two barrels fire independently or together. Reloading "
            "is quick by primitive standards: break, eject, load, snap shut. The "
            "grip bears a carved guild-mark for licensed manufacture, and the "
            "barrels are blued to a deep, even finish that hasn't chipped."
        ),
        "attacks": [
            {"name": "Double-Barrel Shot","damage_min": 7,  "damage_max": 14},
            {"name": "Single-Barrel Aim", "damage_min": 8,  "damage_max": 14},
            {"name": "Hip Shot",          "damage_min": 6,  "damage_max": 12},
            {"name": "Deliberate Aim",    "damage_min": 9,  "damage_max": 15},
            {"name": "Point Blank",       "damage_min": 8,  "damage_max": 14},
            {"name": "Both Barrels",      "damage_min": 10, "damage_max": 17},
        ],
    },
    {
        "tier": 5,
        "name": "Heavy Revolver",
        "weapon_key": "sidearm",
        "damage_type": "penetrating",
        "desc": (
            "A large-frame double-action revolver with a six-inch barrel and a "
            "six-round cylinder loaded with proper centrefire cartridges. Heavy "
            "in the hand — weighted to manage recoil rather than reduce it. The "
            "blued finish is intact but worn at the grip from use. It is a reliable, "
            "honest weapon that does exactly what it claims. A lot of people have "
            "died surprised by that."
        ),
        "attacks": [
            {"name": "Heavy Shot",     "damage_min": 9,  "damage_max": 15},
            {"name": "Aimed Fire",     "damage_min": 11, "damage_max": 17},
            {"name": "Fan the Hammer", "damage_min": 8,  "damage_max": 14},
            {"name": "Point Blank",    "damage_min": 10, "damage_max": 16},
            {"name": "Execution Shot", "damage_min": 12, "damage_max": 19},
            {"name": "Double Action",  "damage_min": 9,  "damage_max": 15},
        ],
    },
    {
        "tier": 6,
        "name": "Ward Enforcer Pistol",
        "weapon_key": "sidearm",
        "damage_type": "penetrating",
        "desc": (
            "A double-action semi-automatic pistol with a fifteen-round magazine "
            "and a polymer grip, mass-produced for ward enforcer companies and "
            "stamped with the relevant ward-authority serial. The action is clean, "
            "the safety ambidextrous, and the rail under the barrel suggests it "
            "was designed for accessories. There are a great many of these "
            "in the tunnels. Not all of them are in enforcer hands."
        ),
        "attacks": [
            {"name": "Semi-Auto Shot",   "damage_min": 10, "damage_max": 16},
            {"name": "Double Tap",       "damage_min": 9,  "damage_max": 15},
            {"name": "Aimed Shot",       "damage_min": 12, "damage_max": 18},
            {"name": "Hip Fire",         "damage_min": 9,  "damage_max": 15},
            {"name": "Point Blank",      "damage_min": 11, "damage_max": 17},
            {"name": "Suppression Shot", "damage_min": 9,  "damage_max": 15},
        ],
    },
    {
        "tier": 7,
        "name": "Pneumatic Sidearm",
        "weapon_key": "sidearm",
        "damage_type": "penetrating",
        "desc": (
            "A pneumatic pistol using compressed-gas propulsion in place of "
            "chemical propellant: virtually silent, no muzzle flash, and capable "
            "of sustained fire without combustion. The magazine holds gas-propelled "
            "ferrous slugs that travel near-subsonically. The trade-off is range — "
            "optimal inside fifty meters, which is more than most tunnel engagements "
            "ever need. Popular with hunters, assassins, and anyone who objects to "
            "the echo."
        ),
        "attacks": [
            {"name": "Silent Shot",      "damage_min": 11, "damage_max": 18},
            {"name": "Pneumatic Burst",  "damage_min": 11, "damage_max": 18},
            {"name": "Suppressed Aim",   "damage_min": 13, "damage_max": 20},
            {"name": "Gas-Drive",        "damage_min": 12, "damage_max": 19},
            {"name": "Point Blank",      "damage_min": 13, "damage_max": 20},
            {"name": "Overcharge Shot",  "damage_min": 15, "damage_max": 23},
        ],
    },
    {
        "tier": 8,
        "name": "Gauss Sidearm",
        "weapon_key": "sidearm",
        "damage_type": "penetrating",
        "desc": (
            "The standard sidearm of the Undercourt Military Officer Corps — a "
            "magnetic-accelerator pistol firing steel-core flechettes to supersonic "
            "velocity via a linear coil array in the barrel. No combustion, negligible "
            "recoil, and a muzzle signature that reads as a very soft crack. The coil "
            "housing glows faint indigo under sustained fire. Unauthorized possession "
            "is an automatic capital offense in all wards."
        ),
        "attacks": [
            {"name": "Gauss Shot",          "damage_min": 16, "damage_max": 25},
            {"name": "Rail-Accelerated Aim","damage_min": 18, "damage_max": 28},
            {"name": "Magnetic Burst",      "damage_min": 16, "damage_max": 26},
            {"name": "Point Blank Rail",    "damage_min": 18, "damage_max": 28},
            {"name": "Coil Overcharge",     "damage_min": 20, "damage_max": 32},
            {"name": "Magnetic Suppression","damage_min": 16, "damage_max": 26},
        ],
    },
    {
        "tier": 9,
        "name": "Plasma Sidearm",
        "weapon_key": "sidearm",
        "damage_type": "burn",
        "desc": (
            "A compact plasma projector in pistol configuration, firing coherent "
            "bolts of magnetically-confined plasma at effective ranges up to forty "
            "meters. The barrel glows hot after six shots and requires passive "
            "cooling before further use. The energy cell is good for eighteen shots "
            "before replacement. Restricted to senior military officers and "
            "Inquisitorial adjuncts. The targeting system is present but unnecessary; "
            "at this range, you do not need it."
        ),
        "attacks": [
            {"name": "Plasma Bolt",      "damage_min": 22, "damage_max": 34, "damage_type": "burn"},
            {"name": "Focused Plasma",   "damage_min": 24, "damage_max": 37, "damage_type": "burn"},
            {"name": "Thermal Burst",    "damage_min": 23, "damage_max": 36, "damage_type": "burn"},
            {"name": "Plasma Aim",       "damage_min": 25, "damage_max": 39, "damage_type": "burn"},
            {"name": "Overload Shot",    "damage_min": 27, "damage_max": 43, "damage_type": "burn"},
            {"name": "Plasma Execution", "damage_min": 30, "damage_max": 47, "damage_type": "burn"},
        ],
    },
    {
        "tier": 10,
        "name": "Inquisitor's Condemnation",
        "weapon_key": "sidearm",
        "damage_type": "void",
        "desc": (
            "The ritual sidearm of the Deep Accord Inquisitorate, wrought from "
            "void-iron and carrying a void-crystal energy cell that fires contained "
            "packets of eldritch dissolution. The barrel inscription reads the Rites "
            "of Passage and glows with an inner dark that brightens on discharge. "
            "What it fires is not, strictly speaking, a projectile. The wound it "
            "makes is not, strictly speaking, a wound. The target selection system "
            "has never been calibrated — it selects correctly regardless."
        ),
        "attacks": [
            {"name": "Void Bolt",        "damage_min": 28, "damage_max": 43, "damage_type": "void"},
            {"name": "Dissolution Shot", "damage_min": 29, "damage_max": 46, "damage_type": "void"},
            {"name": "Rite of Passage",  "damage_min": 30, "damage_max": 48, "damage_type": "void"},
            {"name": "Consuming Fire",   "damage_min": 30, "damage_max": 47, "damage_type": "void"},
            {"name": "Condemnation",     "damage_min": 33, "damage_max": 52, "damage_type": "void"},
            {"name": "Absolute Judgment","damage_min": 37, "damage_max": 58, "damage_type": "void"},
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# LONGARMS  (weapon_key: "longarm")
# damage_type default: penetrating
# ─────────────────────────────────────────────────────────────────────────────
LONGARM = [
    {
        "tier": 1,
        "name": "Pipe Musket",
        "weapon_key": "longarm",
        "damage_type": "penetrating",
        "desc": (
            "A muzzle-loading longarm fashioned from a length of reinforced pipe "
            "with a makeshift flintlock mechanism and a carved wooden stock. It "
            "fires a single ball and produces an enormous cloud of black smoke. "
            "Accurate to roughly twenty meters. A danger to its user past two "
            "hundred. Some people use them anyway."
        ),
        "attacks": [
            {"name": "Musket Shot",       "damage_min": 5,  "damage_max": 11},
            {"name": "Point Blank",       "damage_min": 7,  "damage_max": 13},
            {"name": "Aimed Fire",        "damage_min": 8,  "damage_max": 14},
            {"name": "Desperation Shot",  "damage_min": 5,  "damage_max": 10},
            {"name": "Stock Bash",        "damage_min": 4,  "damage_max": 8,  "damage_type": "impact"},
        ],
    },
    {
        "tier": 2,
        "name": "Percussion Long Gun",
        "weapon_key": "longarm",
        "damage_type": "penetrating",
        "desc": (
            "A long-barreled percussion firearm, disassembled from ruins and "
            "carefully rebuilt. The hexagonal barrel is original; the stock has "
            "been replaced in pine. The hammer falls clean. Single-shot, but the "
            "barrel length gives it real range — someone has etched rough distance "
            "markings along the side in faint scratches."
        ),
        "attacks": [
            {"name": "Long Shot",          "damage_min": 6,  "damage_max": 12},
            {"name": "Aimed Fire",         "damage_min": 8,  "damage_max": 14},
            {"name": "Point Blank",        "damage_min": 7,  "damage_max": 13},
            {"name": "Percussion Shot",    "damage_min": 6,  "damage_max": 12},
            {"name": "Stock Bash",         "damage_min": 4,  "damage_max": 9,  "damage_type": "impact"},
            {"name": "Desperate Discharge","damage_min": 5,  "damage_max": 11},
        ],
    },
    {
        "tier": 3,
        "name": "Lever-Action Carbine",
        "weapon_key": "longarm",
        "damage_type": "penetrating",
        "desc": (
            "A lever-action carbine of pre-Event manufacture, refurbished and "
            "re-chambered for modern metallic cartridge. The loading tube holds "
            "seven rounds and the action is smooth as old steel. Someone has "
            "maintained this weapon with genuine care — the wood is oiled, the "
            "metal is clean, the action is fast. It has been loved and it shows."
        ),
        "attacks": [
            {"name": "Lever Shot",     "damage_min": 7,  "damage_max": 13},
            {"name": "Aimed Fire",     "damage_min": 9,  "damage_max": 15},
            {"name": "Rapid Lever",    "damage_min": 7,  "damage_max": 13},
            {"name": "Point Blank",    "damage_min": 8,  "damage_max": 14},
            {"name": "Body Shot",      "damage_min": 8,  "damage_max": 14},
            {"name": "Headshot",       "damage_min": 10, "damage_max": 17},
        ],
    },
    {
        "tier": 4,
        "name": "Bolt-Action Marksman Rifle",
        "weapon_key": "longarm",
        "damage_type": "penetrating",
        "desc": (
            "A bolt-action rifle with a long barrel and simple iron sights, "
            "guild-made from quality steel. Five rounds in an internal magazine. "
            "The bolt throws cleanly and the trigger breaks crisply. Accurate to "
            "three hundred meters in a straight tunnel — more range than most "
            "underground engagements offer, which means it is always accurate enough."
        ),
        "attacks": [
            {"name": "Bolt Shot",       "damage_min": 9,  "damage_max": 16},
            {"name": "Aimed Shot",      "damage_min": 11, "damage_max": 18},
            {"name": "Chambered Fire",  "damage_min": 9,  "damage_max": 16},
            {"name": "Body Shot",       "damage_min": 10, "damage_max": 17},
            {"name": "Precision Aim",   "damage_min": 13, "damage_max": 20},
            {"name": "Headshot",        "damage_min": 14, "damage_max": 22},
        ],
    },
    {
        "tier": 5,
        "name": "Semi-Auto Combat Rifle",
        "weapon_key": "longarm",
        "damage_type": "penetrating",
        "desc": (
            "A gas-operated semi-automatic combat rifle with a twenty-round "
            "detachable box magazine and a folding stock. Not elegant, not "
            "particularly accurate past two hundred meters, but fast, reliable, "
            "and the default longarm of every serious fighting group in the "
            "middle wards. Stamped with an enforcer-company serial, scratched "
            "over with something else. The bayonet lug has been used."
        ),
        "attacks": [
            {"name": "Semi-Auto Shot",   "damage_min": 10, "damage_max": 17},
            {"name": "Double Tap",       "damage_min": 9,  "damage_max": 16},
            {"name": "Aimed Shot",       "damage_min": 12, "damage_max": 19},
            {"name": "Suppression Shot", "damage_min": 9,  "damage_max": 16},
            {"name": "Point Blank",      "damage_min": 11, "damage_max": 18},
            {"name": "Headshot",         "damage_min": 13, "damage_max": 21},
        ],
    },
    {
        "tier": 6,
        "name": "Pneumatic Longarm",
        "weapon_key": "longarm",
        "damage_type": "penetrating",
        "desc": (
            "A pneumatic longarm fed by a pressurized tank worn at the back, "
            "firing heavy ferrous darts in near-total silence. In a tunnel, "
            "silence is worth more than velocity. The darts tumble on entry "
            "and make ragged wounds. The tank lasts for fifty shots. Popular "
            "with hunters, infiltrators, and anyone who has learned the hard "
            "way what echoes in confined stone passages do to your plans."
        ),
        "attacks": [
            {"name": "Silent Shot",      "damage_min": 11, "damage_max": 19},
            {"name": "Aimed Dart",       "damage_min": 13, "damage_max": 21},
            {"name": "Double Pump",      "damage_min": 11, "damage_max": 18},
            {"name": "Suppression Fire", "damage_min": 10, "damage_max": 17},
            {"name": "Body Shot",        "damage_min": 12, "damage_max": 20},
            {"name": "Headshot",         "damage_min": 14, "damage_max": 23},
        ],
    },
    {
        "tier": 7,
        "name": "Combat Shotgun",
        "weapon_key": "longarm",
        "damage_type": "penetrating",
        "desc": (
            "A military-pattern pump-action shotgun with pistol grip, extended "
            "tube, and heat shield — an eight-shell capacity and a variety of "
            "specialist tunnel-warfare rounds. In an enclosed space it is, simply, "
            "the most immediately violent personal weapon available. The ward "
            "authority has official views on civilian ownership. They are widely "
            "and comprehensively ignored."
        ),
        "attacks": [
            {"name": "Buckshot Blast", "damage_min": 13, "damage_max": 22},
            {"name": "Slug Shot",      "damage_min": 13, "damage_max": 21},
            {"name": "Pump Fire",      "damage_min": 11, "damage_max": 19},
            {"name": "Close Blast",    "damage_min": 14, "damage_max": 23},
            {"name": "Point Blank",    "damage_min": 16, "damage_max": 25},
            {"name": "Gut Shot",       "damage_min": 13, "damage_max": 22},
        ],
    },
    {
        "tier": 8,
        "name": "Gauss Battle Rifle",
        "weapon_key": "longarm",
        "damage_type": "penetrating",
        "desc": (
            "The standard longarm of Undercourt Military line infantry — a "
            "magnetic-accelerator battle rifle firing steel-core flechettes at "
            "twelve hundred meters per second. No muzzle blast, negligible sound "
            "signature, near-zero recoil. The coils along the barrel glow faint "
            "orange under sustained fire. Effective at ranges that make the user "
            "effectively invisible underground. Unauthorized possession is an "
            "automatic death sentence."
        ),
        "attacks": [
            {"name": "Gauss Shot",          "damage_min": 19, "damage_max": 30},
            {"name": "Rail-Aimed Fire",     "damage_min": 21, "damage_max": 33},
            {"name": "Magnetic Suppression","damage_min": 18, "damage_max": 29},
            {"name": "Point Blank Rail",    "damage_min": 20, "damage_max": 32},
            {"name": "Coil Burst",          "damage_min": 22, "damage_max": 35},
            {"name": "Overcharge Shot",     "damage_min": 25, "damage_max": 39},
        ],
    },
    {
        "tier": 9,
        "name": "Plasma Rifle",
        "weapon_key": "longarm",
        "damage_type": "burn",
        "desc": (
            "A shoulder-fired plasma projector issuing coherent plasma bolts at "
            "effective ranges up to one hundred and fifty meters. The barrel "
            "glows cherry-red after three shots and must be vented before a "
            "fourth. The energy cell holds twelve shots; swap time is thirty "
            "seconds. The bolt burns through light armor and wall sections alike. "
            "Reserved for senior officers and Inquisitorial enforcement details. "
            "There is a reason it is not issued more widely."
        ),
        "attacks": [
            {"name": "Plasma Bolt",     "damage_min": 24, "damage_max": 38, "damage_type": "burn"},
            {"name": "Focused Plasma",  "damage_min": 26, "damage_max": 41, "damage_type": "burn"},
            {"name": "Thermal Burst",   "damage_min": 25, "damage_max": 39, "damage_type": "burn"},
            {"name": "Charged Bolt",    "damage_min": 27, "damage_max": 43, "damage_type": "burn"},
            {"name": "Meltdown Shot",   "damage_min": 29, "damage_max": 46, "damage_type": "burn"},
            {"name": "Execution Plasma","damage_min": 32, "damage_max": 50, "damage_type": "burn"},
        ],
    },
    {
        "tier": 10,
        "name": "The Pronouncement",
        "weapon_key": "longarm",
        "damage_type": "void",
        "desc": (
            "The Inquisitor's longarm — a void-cannon in the form of a ceremonial "
            "rifle of the Deep Accord. It fires a packet of contained void-energy "
            "that unmakes a target from the outside inward, beginning with the "
            "physical and proceeding to whatever comes after. Those struck but not "
            "killed have difficulty remembering who they were before the shot. "
            "Designated targets do not typically survive. The barrel inscription "
            "reads: 'Let the Accord be written in them.'"
        ),
        "attacks": [
            {"name": "Void Bolt",            "damage_min": 30, "damage_max": 47, "damage_type": "void"},
            {"name": "Dissolution Shot",     "damage_min": 31, "damage_max": 49, "damage_type": "void"},
            {"name": "Rite of Unmaking",     "damage_min": 32, "damage_max": 51, "damage_type": "void"},
            {"name": "Consuming Burst",      "damage_min": 33, "damage_max": 53, "damage_type": "void"},
            {"name": "Judgment Pronouncement","damage_min": 36, "damage_max": 57, "damage_type": "void"},
            {"name": "Final Accord",         "damage_min": 40, "damage_max": 63, "damage_type": "void"},
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# AUTOMATIC WEAPONS  (weapon_key: "automatic")
# damage_type default: penetrating
# ─────────────────────────────────────────────────────────────────────────────
AUTOMATIC = [
    {
        "tier": 1,
        "name": "Pipe Scatter",
        "weapon_key": "automatic",
        "damage_type": "penetrating",
        "desc": (
            "Four pipe barrels bound together and fired by a single trigger — "
            "all four at once, in an uncontrolled spread. 'Automatic' is too "
            "dignified a word for it. 'Explosive handshake' is closer. One use "
            "per loading. The barrels must cool before you can handle them, and "
            "they will burn you if you are impatient, which you will be."
        ),
        "attacks": [
            {"name": "Scatter Blast",    "damage_min": 5,  "damage_max": 11},
            {"name": "Point Blank",      "damage_min": 7,  "damage_max": 13},
            {"name": "Desperate Volley", "damage_min": 5,  "damage_max": 11},
            {"name": "Wild Fire",        "damage_min": 4,  "damage_max": 10},
            {"name": "Full Discharge",   "damage_min": 8,  "damage_max": 14},
        ],
    },
    {
        "tier": 2,
        "name": "Powder Pepperbox",
        "weapon_key": "automatic",
        "damage_type": "penetrating",
        "desc": (
            "A six-barrel pepperbox revolver firing black-powder charges in "
            "sequence. Each trigger pull rotates the cylinder and drops the "
            "hammer on the next chamber. Slow by modern standards, but it fires "
            "six times before you must reload — and after the third shot the "
            "smoke is thick enough to fight through, which cuts both ways."
        ),
        "attacks": [
            {"name": "Pepperbox Volley","damage_min": 6,  "damage_max": 12},
            {"name": "Rapid Fire",      "damage_min": 5,  "damage_max": 11},
            {"name": "Percussion Shot", "damage_min": 6,  "damage_max": 12},
            {"name": "Point Blank",     "damage_min": 7,  "damage_max": 13},
            {"name": "Hammer Volley",   "damage_min": 7,  "damage_max": 13},
            {"name": "Smoke Burst",     "damage_min": 5,  "damage_max": 11},
        ],
    },
    {
        "tier": 3,
        "name": "Drum Carbine",
        "weapon_key": "automatic",
        "damage_type": "penetrating",
        "desc": (
            "A lever-action carbine fitted with an oversized drum magazine "
            "holding thirty rounds of metallic cartridge. The lever is shortened "
            "for faster cycling; not a true automatic, but a practiced shooter "
            "can fire it faster than the eye tracks. The drum adds considerable "
            "weight and a grinding sound that carries well in tunnels. It is "
            "loud in ways that a drum carbine perhaps should not be."
        ),
        "attacks": [
            {"name": "Drum Shot",    "damage_min": 7,  "damage_max": 13},
            {"name": "Rapid Lever",  "damage_min": 6,  "damage_max": 12},
            {"name": "Spray Fire",   "damage_min": 6,  "damage_max": 12},
            {"name": "Aimed Shot",   "damage_min": 9,  "damage_max": 15},
            {"name": "Point Blank",  "damage_min": 8,  "damage_max": 14},
            {"name": "Drum Burst",   "damage_min": 8,  "damage_max": 14},
        ],
    },
    {
        "tier": 4,
        "name": "Converted Auto-Carbine",
        "weapon_key": "automatic",
        "damage_type": "penetrating",
        "desc": (
            "A semi-automatic combat carbine with the disconnector removed and "
            "the sear modified to fire fully automatic. The modification is crude "
            "but functional, and also illegal in every ward that bothers to say so. "
            "The rate of fire burns through a twenty-round magazine in roughly three "
            "seconds, which feels like plenty until it abruptly isn't."
        ),
        "attacks": [
            {"name": "Auto Burst",    "damage_min": 8,  "damage_max": 14},
            {"name": "Spray Fire",    "damage_min": 7,  "damage_max": 13},
            {"name": "Aimed Burst",   "damage_min": 9,  "damage_max": 15},
            {"name": "Point Blank",   "damage_min": 10, "damage_max": 16},
            {"name": "Suppression",   "damage_min": 7,  "damage_max": 13},
            {"name": "Panic Fire",    "damage_min": 7,  "damage_max": 14},
        ],
    },
    {
        "tier": 5,
        "name": "Military SMG",
        "weapon_key": "automatic",
        "damage_type": "penetrating",
        "desc": (
            "A military-specification submachine gun with a folding stock, "
            "double-magazine feed, and a cyclic rate of eight hundred rounds "
            "per minute. Built explicitly for tunnel warfare: short, compact, "
            "controllable in a corridor, and completely merciless at close "
            "range. The finish is worn from use, not neglect. This is "
            "a working weapon that has been worked."
        ),
        "attacks": [
            {"name": "SMG Burst",      "damage_min": 9,  "damage_max": 15},
            {"name": "Full Auto",      "damage_min": 8,  "damage_max": 14},
            {"name": "Aimed Burst",    "damage_min": 11, "damage_max": 17},
            {"name": "Suppression",    "damage_min": 8,  "damage_max": 14},
            {"name": "Point Blank",    "damage_min": 11, "damage_max": 17},
            {"name": "Double Mag",     "damage_min": 9,  "damage_max": 16},
        ],
    },
    {
        "tier": 6,
        "name": "Assault Rifle",
        "weapon_key": "automatic",
        "damage_type": "penetrating",
        "desc": (
            "A military-pattern assault rifle on a rotating bolt, firing semi "
            "or full auto from a thirty-round detachable magazine. The gas block "
            "is vented for reliability in tunnel dust and humidity. Heavy, loud, "
            "and utterly dependable. The bayonet lug is present and has clearly "
            "been used for its intended purpose at some point. The selector has "
            "three positions; two of them are used."
        ),
        "attacks": [
            {"name": "Assault Burst",  "damage_min": 10, "damage_max": 17},
            {"name": "Full Auto",      "damage_min": 9,  "damage_max": 16},
            {"name": "Aimed Shot",     "damage_min": 12, "damage_max": 19},
            {"name": "Suppressive",    "damage_min": 9,  "damage_max": 16},
            {"name": "Point Blank",    "damage_min": 11, "damage_max": 18},
            {"name": "Headshot",       "damage_min": 13, "damage_max": 21},
        ],
    },
    {
        "tier": 7,
        "name": "Pneumatic Automatic",
        "weapon_key": "automatic",
        "damage_type": "penetrating",
        "desc": (
            "A military pneumatic automatic weapon fed from a pressurized "
            "backpack tank, firing ferrous darts at six hundred rounds per "
            "minute in near-complete silence. Used for tunnel ambushes, "
            "assassination operations, and anywhere the sound signature of "
            "a conventional automatic would be catastrophic. The darts tumble "
            "on entry. The silence is the worst thing about it."
        ),
        "attacks": [
            {"name": "Silent Burst",     "damage_min": 12, "damage_max": 20},
            {"name": "Full Auto",        "damage_min": 11, "damage_max": 18},
            {"name": "Suppression Volley","damage_min": 11, "damage_max": 18},
            {"name": "Aimed Burst",      "damage_min": 14, "damage_max": 22},
            {"name": "Dart Storm",       "damage_min": 12, "damage_max": 20},
            {"name": "Overcharge",       "damage_min": 15, "damage_max": 24},
        ],
    },
    {
        "tier": 8,
        "name": "Gauss Automatic Rifle",
        "weapon_key": "automatic",
        "damage_type": "penetrating",
        "desc": (
            "The standard automatic longarm of Undercourt Military assault "
            "formations — a magnetic-accelerator rifle firing steel-core "
            "flechettes in cyclic bursts of four at near-zero sound signature. "
            "Overheating is the primary operational limitation; the coils sustain "
            "roughly fifteen full bursts before forced cooldown. Unauthorized "
            "possession is a capital offense. There is no civilian version."
        ),
        "attacks": [
            {"name": "Gauss Burst",       "damage_min": 19, "damage_max": 29},
            {"name": "Rail Auto",         "damage_min": 18, "damage_max": 28},
            {"name": "Magnetic Suppression","damage_min": 17, "damage_max": 27},
            {"name": "Gauss Full Auto",   "damage_min": 17, "damage_max": 28},
            {"name": "Coil Burst",        "damage_min": 21, "damage_max": 33},
            {"name": "Overcharge Auto",   "damage_min": 23, "damage_max": 37},
        ],
    },
    {
        "tier": 9,
        "name": "Plasma Automatic",
        "weapon_key": "automatic",
        "damage_type": "burn",
        "desc": (
            "A shoulder-mounted plasma automatic projecting rapid-fire plasma "
            "bolts from a contained plasma magazine — approximately two bolts per "
            "second, slow by conventional standards, but each bolt burns through "
            "cover and personnel alike. The barrel section glows white-hot under "
            "sustained fire and poses a hazard to the operator if cooling is "
            "neglected. Authorized for Inquisitorial enforcement operations only. "
            "This has been used for Inquisitorial enforcement operations."
        ),
        "attacks": [
            {"name": "Plasma Burst",     "damage_min": 23, "damage_max": 37, "damage_type": "burn"},
            {"name": "Thermal Volley",   "damage_min": 22, "damage_max": 35, "damage_type": "burn"},
            {"name": "Plasma Suppression","damage_min": 21, "damage_max": 33, "damage_type": "burn"},
            {"name": "Full Plasma Auto", "damage_min": 22, "damage_max": 36, "damage_type": "burn"},
            {"name": "Fusion Burst",     "damage_min": 26, "damage_max": 42, "damage_type": "burn"},
            {"name": "Meltdown Volley",  "damage_min": 29, "damage_max": 46, "damage_type": "burn"},
        ],
    },
    {
        "tier": 10,
        "name": "The Storm Accord",
        "weapon_key": "automatic",
        "damage_type": "void",
        "desc": (
            "The heaviest weapon in the Inquisitorial arsenal — a void-energy "
            "automatic projector that fires sequential packets of dissolution at "
            "high cyclic rate. Each bolt unmakes matter in transit. There is no "
            "meaningful cover; the Storm Accord does not interact with barriers "
            "by design. Every panel bears an inscription from the High Accord. "
            "Its use requires authorization from at least two ranking Inquisitors. "
            "It has been authorized fourteen times. You are looking at why."
        ),
        "attacks": [
            {"name": "Void Burst",         "damage_min": 29, "damage_max": 45, "damage_type": "void"},
            {"name": "Dissolution Volley", "damage_min": 28, "damage_max": 44, "damage_type": "void"},
            {"name": "Storm of Unmaking",  "damage_min": 27, "damage_max": 43, "damage_type": "void"},
            {"name": "Accord Suppression", "damage_min": 26, "damage_max": 42, "damage_type": "void"},
            {"name": "Consuming Auto",     "damage_min": 30, "damage_max": 48, "damage_type": "void"},
            {"name": "Absolute Storm",     "damage_min": 34, "damage_max": 54, "damage_type": "void"},
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Master registry — keyed by weapon_key for easy lookup
# ─────────────────────────────────────────────────────────────────────────────
WEAPON_TIERS = {
    "fists":      UNARMED,
    "blunt":      BLUNT,
    "knife":      SHORT_BLADE,
    "long_blade": LONG_BLADE,
    "sidearm":    SIDEARM,
    "longarm":    LONGARM,
    "automatic":  AUTOMATIC,
}


def get_weapon_tier(weapon_key, tier):
    """Return the weapon definition dict for weapon_key at the given tier, or None."""
    return next(
        (w for w in WEAPON_TIERS.get(weapon_key, []) if w["tier"] == tier),
        None,
    )


def get_weapons_for_key(weapon_key):
    """Return all weapon definitions for a given weapon_key, sorted by tier."""
    return sorted(WEAPON_TIERS.get(weapon_key, []), key=lambda w: w["tier"])


def find_weapon_template(weapon_key, template_name):
    """
    Find a specific template dict by weapon_key and template display name.
    Case-insensitive match on the 'name' field. Returns (entry, tier) or (None, None).
    """
    if not weapon_key or not template_name:
        return None, None
    templates = WEAPON_TIERS.get(weapon_key, [])
    name_lower = str(template_name).strip().lower()
    for entry in templates:
        if str(entry.get("name", "")).strip().lower() == name_lower:
            return entry, entry.get("tier")
    return None, None

