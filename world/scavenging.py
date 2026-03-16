"""
Scavenging system: skill-based loot from tagged rooms (wildscavenge, urbanscavenge).

Roll flow:
- Uses the 'scavenging' skill (stats: intelligence + perception) with a luck bonus modifier.
- Only works in rooms tagged with one or more scavenging tags:
  - 'wildscavenge'  -> wild/outdoors-style loot
  - 'urbanscavenge' -> urban/industrial loot

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

from evennia.utils.create import create_object


SCAVENGE_TAGS_WILD = {"wildscavenge"}
SCAVENGE_TAGS_URBAN = {"urbanscavenge"}


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


RARITY_ORDER = ["grey", "green", "blue", "purple", "yellow"]


def _pick_loot_table(room):
    """
    Choose which loot table to use based on room tags.

    Prefers wildscavenge over urbanscavenge if both are present.
    """
    tags = set(room.tags.all()) if hasattr(room, "tags") else set()
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
    elif env == "wild":
        effective -= 5  # wilderness is harsher for salvage

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


def _pick_weapon_template(env, rarity):
    """
    Placeholder for scavenged weapon templates.

    Once weapon tiers are defined, this should return a tuple
    (typeclass_path, key) for a low-grade weapon appropriate to the
    environment and rarity band (usually grey/green/blue only).

    For now it always returns (None, None) so scavenging only produces
    generic loot Items. This is a framework hook to plug real weapon
    templates into later.
    """
    # Example future structure (not yet populated):
    # WEAPON_TEMPLATES = {
    #     "urban": {
    #         "grey": [("typeclasses.weapons.Sidearm", "Rusty Sidearm"), ...],
    #         "green": [...],
    #         "blue": [...],
    #     },
    #     "wild": {
    #         "grey": [("typeclasses.weapons.Machete", "Chipped Machete"), ...],
    #     },
    # }
    # For now, no weapon templates are available.
    return None, None


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

    # Decide if this roll should produce a (future) weapon template or a generic loot item.
    # Weapons will generally be low-grade when we start tiering them; for now this hook
    # always falls back to generic loot until weapon templates are defined.
    table, env = _pick_loot_table(room)
    weapon_typeclass, weapon_key = _pick_weapon_template(env, rarity)

    try:
        if weapon_typeclass:
            # Future path: low-grade weapon from a scavenging tier.
            obj = create_object(weapon_typeclass, key=weapon_key or name, location=caller)
        else:
            # Current path: generic scavenged item.
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

