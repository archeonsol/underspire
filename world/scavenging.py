"""
Scavenging system: skill-based loot from tagged rooms (wildscavenge, urbanscavenge, or biome tags).

Roll flow:
- Uses the 'scavenging' skill (stats: intelligence + perception) with a luck bonus modifier.
- Only works in rooms tagged with one or more scavenging tags:
  - 'wildscavenge'  -> wild/outdoors-style loot (fallback)
  - 'urbanscavenge' -> urban/industrial loot
  - Biome-specific (wilderness_map): scavenge_grasslands, scavenge_harshlands, scavenge_hills,
    scavenge_ruined_settlement, scavenge_volcanic -> each has its own loot table.

Loot tiers (Escape-from-Tarkov style):
- grey   (tier 0): common junk
- green  (tier 1): useful scrap / low-grade consumables
- blue   (tier 2): valuable components
- purple (tier 3): rare prototypes
- yellow (tier 4): ultra-rare artifacts

We pick a rarity tier based on the final roll result. Higher rolls unlock higher tiers,
but upper tiers require both luck and skill.
"""

import random
import time

from evennia.utils.create import create_object


# Max scavenges per 24h by scavenging skill level (0-150). Server date resets at midnight UTC.
# (level_min_inclusive, max_per_day); first matching tier wins (order low to high).
SCAVENGE_DAILY_LIMIT_TIERS = [
    (0, 5),
    (20, 10),
    (40, 15),
    (60, 20),
    (80, 25),
    (100, 30),
    (120, 40),
    (150, 50),
]


def get_scavenge_daily_limit(skill_level):
    """Return max number of scavenges allowed per server day for this skill level (0-150)."""
    if skill_level is None or skill_level < 0:
        skill_level = 0
    limit = 3
    for level_min, max_per_day in SCAVENGE_DAILY_LIMIT_TIERS:
        if skill_level >= level_min:
            limit = max_per_day
    return limit


def get_server_date_key():
    """Return (year, month, day) for current server time (UTC) so 24h limit resets same for everyone."""
    t = time.gmtime()
    return (t.tm_year, t.tm_mon, t.tm_mday)


SCAVENGE_TAGS_WILD = {"wildscavenge"}
SCAVENGE_TAGS_URBAN = {"urbanscavenge"}
# Biome tags from wilderness_map (scavenge_<biome>) get their own loot tables
BIOME_SCAVENGE_TAGS = {
    "scavenge_grasslands",
    "scavenge_harshlands",
    "scavenge_hills",
    "scavenge_ruined_settlement",
    "scavenge_volcanic",
}


LOOT_BY_TIER_WILD = {
    "grey": [
        "|xCracked Filter Mask|n",
        "|xRust-Flaked Machete Blade|n",
        "|xBundle of Moldy Rations|n",
    ],
    "green": [
        "|gField-Dressed Medkit Shell|n",
        "|gPurified Water Cartridge|n",
        "|gReinforced Canvas Satchel|n",
    ],
    "blue": [
        "|cStabilized Mutagen Sample|n",
        "|cRefined Herb Distillate|n",
        "|cHardened Survival Harness|n",
    ],
    "purple": [
        "|mAncient Root Idol|n",
        "|mLiving Spore Phial|n",
        "|mWitcher’s Bone Charm|n",
    ],
    "yellow": [
        "|yRelic of the First Expedition|n",
        "|yHeart of the Pale Tree|n",
    ],
}


LOOT_BY_TIER_URBAN = {
    "grey": [
        "|xCracked Circuit Board|n",
        "|xBent Access Card|n",
        "|xFrayed Power Conduit|n",
    ],
    "green": [
        "|gFactory Ration Brick|n",
        "|gReusable Filter Cartridge|n",
        "|gSalvaged Medfoam Canister|n",
    ],
    "blue": [
        "|cEncrypted Data Shard|n",
        "|cRefined Chemical Solvent|n",
        "|cTuned Optics Module|n",
    ],
    "purple": [
        "|mPrototype Neural Jack|n",
        "|mAuthority Clearance Token|n",
        "|mStabilized Void Crystal|n",
    ],
    "yellow": [
        "|yInquisitorial Rosette|n",
        "|ySingularity Core Fragment|n",
    ],
}


# Wilderness biome loot tables (used when room has scavenge_<biome> tag)
LOOT_BY_TIER_GRASSLANDS = {
    "grey": [
        "|xCracked Filter Mask|n",
        "|xRust-Flaked Machete Blade|n",
        "|xBundle of Moldy Rations|n",
    ],
    "green": [
        "|gField-Dressed Medkit Shell|n",
        "|gPurified Water Cartridge|n",
        "|gReinforced Canvas Satchel|n",
    ],
    "blue": [
        "|cStabilized Mutagen Sample|n",
        "|cRefined Herb Distillate|n",
        "|cHardened Survival Harness|n",
    ],
    "purple": [
        "|mAncient Root Idol|n",
        "|mLiving Spore Phial|n",
        "|mWitcher's Bone Charm|n",
    ],
    "yellow": [
        "|yRelic of the First Expedition|n",
        "|yHeart of the Pale Tree|n",
    ],
}

LOOT_BY_TIER_HARSHLANDS = {
    "grey": [
        "|xCharred Rebar Stub|n",
        "|xAsh-Caked Boot|n",
        "|xMelted Plastic Shard|n",
    ],
    "green": [
        "|gScorched Filter Housing|n",
        "|gSlag-Encased Wire Coil|n",
        "|gHeat-Warped Canteen|n",
    ],
    "blue": [
        "|cCondensed Ash Sample|n",
        "|cTempered Ceramic Plate|n",
        "|cSalvaged Burn Unit|n",
    ],
    "purple": [
        "|mFused Authority Badge|n",
        "|mStill-Warm Reactor Shard|n",
        "|mBlackened Data Crystal|n",
    ],
    "yellow": [
        "|yEmber of the Fall|n",
        "|yCore Fragment from the Breach|n",
    ],
}

LOOT_BY_TIER_HILLS = {
    "grey": [
        "|xCracked Stone Chunk|n",
        "|xRusted Girder Scrap|n",
        "|xBent Reinforcement Rod|n",
    ],
    "green": [
        "|gSturdy Cable Spool|n",
        "|gConcrete-Dusted Rations|n",
        "|gHeavy-Duty Clamp|n",
    ],
    "blue": [
        "|cPre-Collapse Bearing|n",
        "|cStable Alloy Strip|n",
        "|cRidge Survey Map|n",
    ],
    "purple": [
        "|mOld Watchtower Lens|n",
        "|mMiner's Luck Charm|n",
        "|mEncrypted Relay Chip|n",
    ],
    "yellow": [
        "|ySurveyor's Final Report|n",
        "|yVoid-Touched Ore Sample|n",
    ],
}

LOOT_BY_TIER_RUINED_SETTLEMENT = {
    "grey": [
        "|xBent Door Handle|n",
        "|xShattered Window Pane|n",
        "|xFrayed Curtain Scrap|n",
    ],
    "green": [
        "|gIntact Medicine Cabinet|n",
        "|gStash of Canned Goods|n",
        "|gSalvaged Lock Mechanism|n",
    ],
    "blue": [
        "|cHousehold Power Cell|n",
        "|cFamily Data Slate|n",
        "|cReinforced Strongbox|n",
    ],
    "purple": [
        "|mSettlement Ledger|n",
        "|mEmergency Beacon|n",
        "|mPreserved Ration Stock|n",
    ],
    "yellow": [
        "|yMayor's Seal|n",
        "|yLast Evacuation Order|n",
    ],
}

LOOT_BY_TIER_VOLCANIC = {
    "grey": [
        "|xGlassy Slag Chunk|n",
        "|xSulfur-Crusted Rock|n",
        "|xBurned-Out Wiring|n",
    ],
    "green": [
        "|gHeat-Resistant Glove|n",
        "|gCondensation Trap|n",
        "|gStable Sulfur Cake|n",
    ],
    "blue": [
        "|cCrystallized Vent Sample|n",
        "|cRare Earth Concentrate|n",
        "|cHardened Obsidian Shard|n",
    ],
    "purple": [
        "|mMagma-Forged Alloy|n",
        "|mDeep Vent Crystal|n",
        "|mThermal Regulator|n",
    ],
    "yellow": [
        "|yHeart of the Caldera|n",
        "|yPrimordial Crystal|n",
    ],
}

BIOME_LOOT_TABLES = {
    "grasslands": LOOT_BY_TIER_GRASSLANDS,
    "harshlands": LOOT_BY_TIER_HARSHLANDS,
    "hills": LOOT_BY_TIER_HILLS,
    "ruined_settlement": LOOT_BY_TIER_RUINED_SETTLEMENT,
    "volcanic": LOOT_BY_TIER_VOLCANIC,
}

RARITY_ORDER = ["grey", "green", "blue", "purple", "yellow"]

# Chance (0.0-1.0) that a successful scavenge roll produces a T1 weapon or T1 armor instead of generic loot.
# When this triggers, we try weapon 50% / armor 50%. Only tier-1 (scavenger) weapons/armor from
# world.weapon_tiers and world.armor_levels.
SCAVENGE_WEAPON_ARMOR_CHANCE = 0.08

# weapon_key -> typeclass path for spawning T1 weapons (from world.weapon_tiers tier 1).
WEAPON_KEY_TYPECLASS = {
    "knife": "typeclasses.weapons.ShortBladeWeapon",
    "blunt": "typeclasses.weapons.BluntWeapon",
    "long_blade": "typeclasses.weapons.LongBladeWeapon",
    "sidearm": "typeclasses.weapons.SidearmWeapon",
    "longarm": "typeclasses.weapons.LongarmWeapon",
    "automatic": "typeclasses.weapons.AutomaticWeapon",
}


def _pick_loot_table(room):
    """
    Choose which loot table to use based on room tags.

    Biome-specific tags (scavenge_grasslands, scavenge_harshlands, etc.) take precedence
    so wilderness tiles get the right table. Then wildscavenge, then urbanscavenge.
    """
    tags = set(str(t).lower() for t in (room.tags.all() if hasattr(room, "tags") else []))
    # Biome tags from wilderness_map: one table per biome
    for tag in tags:
        if tag in BIOME_SCAVENGE_TAGS:
            biome = tag.replace("scavenge_", "")
            table = BIOME_LOOT_TABLES.get(biome)
            if table:
                return table, biome
    if SCAVENGE_TAGS_WILD & tags:
        return LOOT_BY_TIER_WILD, "wild"
    if SCAVENGE_TAGS_URBAN & tags:
        return LOOT_BY_TIER_URBAN, "urban"
    return None, None


def _determine_rarity(env, final_roll):
    """
    Map final_roll (from roll_check) to a rarity tier, with a chance of no loot.

    We bias slightly by environment:
    - Urban: slightly more forgiving (small bonus to effective roll)
    - Wild: slightly harsher (small penalty)

    Very low rolls fumble and produce no loot at all. High rolls mostly give blue,
    with occasional purple and extremely rare yellow (legendary) results.
    """
    # Fumbles: come up empty-handed on very low effective results.
    if final_roll <= 50:
        return None

    effective = final_roll
    if env == "urban":
        effective += 5  # urban clutter = more odds of finding something
    else:
        effective -= 5  # wild and all wilderness biomes are harsher for salvage

    # Make sure we don't go negative
    if effective < 0:
        effective = 0

    # Base bands: grey/green are the bulk of low/medium rolls.
    if effective <= 75:
        return "grey"
    if effective <= 100:
        return "green"

    # Above 100 effective, we are in the "good scavenger" range: mostly blue, sometimes purple,
    # and very rarely yellow. We use probabilities so yellows stay truly legendary even at
    # high skill.
    import random

    if effective <= 125:
        # Solid but not insane: mostly blue, small chance of purple.
        roll = random.random()
        if roll < 0.15:
            return "purple"
        return "blue"

    # Very high effective (125+): compute a "high" band for probability shaping.
    high = max(0, min(effective, 185) - 125)  # clamp to avoid unbounded growth
    # Yellow chance: starts at ~0.5% and caps at 3%.
    p_yellow = min(0.005 + high * 0.0004, 0.03)
    # Purple chance: starts at ~10% and grows toward ~30%.
    p_purple = min(0.10 + high * 0.0015, 0.30)
    roll = random.random()
    if roll < p_yellow:
        return "yellow"
    if roll < p_yellow + p_purple:
        return "purple"
    return "blue"


def _pick_t1_weapon():
    """
    Return (typeclass_path, template_name) for a random T1 weapon from world.weapon_tiers, or (None, None).
    Only tier-1 (scavenger) weapons; no fists.
    """
    try:
        from world.weapon_tiers import WEAPON_TIERS, get_weapon_tier
    except ImportError:
        return None, None
    candidates = []
    for weapon_key, typeclass_path in WEAPON_KEY_TYPECLASS.items():
        entry = get_weapon_tier(weapon_key, 1)
        if entry and entry.get("name"):
            candidates.append((typeclass_path, entry["name"]))
    if not candidates:
        return None, None
    return random.choice(candidates)


def _pick_t1_armor_template_key():
    """
    Return a random T1 (level 1 / scavenger) armor template key from world.armor_levels, or None.
    """
    try:
        from world.armor_levels import get_templates_by_level
        # ARMOR_LEVEL_SCAVENGER = 1 typically
        templates = get_templates_by_level(1)
        if not templates:
            return None
        t = random.choice(templates)
        return t.get("key")
    except ImportError:
        return None


def _pick_loot_item(room, final_roll):
    """
    Given a room and a roll result, pick a specific loot item name and rarity.
    """
    table, env = _pick_loot_table(room)
    if not table:
        return None, None
    rarity = _determine_rarity(env, final_roll)
    if not rarity:
        # Fumble/empty-handed for this roll.
        return None, None
    # Legendary (yellow) items only appear in rooms explicitly tagged for it.
    if rarity == "yellow":
        tags = set(room.tags.all()) if hasattr(room, "tags") else set()
        if "scavengelegendary" not in tags:
            # Downgrade to purple tier if available; otherwise treat as no loot.
            rarity = "purple"
            if rarity not in table or not table.get(rarity):
                return None, None
    items = table.get(rarity) or table.get("grey")
    if not items:
        return None, None
    name = random.choice(items)
    return rarity, name


def perform_scavenge(caller, room, final_roll):
    """
    Create a scavenged item based on the given roll.

    The item is placed directly into the caller's inventory (on the character)
    so it doesn't need to be picked up from the room.

    Returns the created object or None.
    """
    rarity, name = _pick_loot_item(room, final_roll)
    if not name:
        return None

    obj = None
    # Rarely: try for a T1 weapon or T1 armor (green/blue only; grey stays generic loot).
    if rarity in ("green", "blue") and random.random() < SCAVENGE_WEAPON_ARMOR_CHANCE:
        if random.random() < 0.5:
            typeclass_path, template_name = _pick_t1_weapon()
            if typeclass_path and template_name:
                try:
                    obj = create_object(typeclass_path, key=template_name, location=caller)
                except Exception:
                    obj = None
        else:
            armor_key = _pick_t1_armor_template_key()
            if armor_key:
                try:
                    from world.armor_levels import create_armor_from_template
                    obj = create_armor_from_template(armor_key, location=caller)
                except Exception:
                    obj = None

    if obj is None:
        try:
            obj = create_object("typeclasses.items.Item", key=name, location=caller)
        except Exception:
            return None

    try:
        obj.db.rarity = rarity
        if hasattr(obj, "tags"):
            obj.tags.add(f"scavenge_{rarity}")
    except Exception:
        pass

    return obj

