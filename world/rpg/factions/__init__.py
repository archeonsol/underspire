"""
Central faction registry. All faction definitions live here.
Every system that checks faction membership imports from this module.

Future NPC integration points (for AI / behavior scripts):
- NPC sees a faction member attacked → check if attacker is enemy faction → join fight
- NPC receives "follow" command → check if commander is same faction and sufficient rank
- NPC guards a door → check visitor's faction tag before allowing passage
- NPC vendor → check buyer's faction before selling restricted goods (see is_faction_member, get_member_rank)
"""

FACTIONS = {
    "IMP": {
        "key": "IMP",
        "name": "The Imperium Guard",
        "short_name": "Guard",
        "description": "The colony's law enforcement arm. They carry the Authority's mandate and the weapons to enforce it.",
        "color": "|y",
        "tag": "faction_imp",
        "tag_category": "faction",
        "ranks": "imperium_ranks",
        "default_rank": 1,
        "hq_room_tag": "imp_hq",
        "terminal_prototype": "terminal_imp",
    },
    "INQ": {
        "key": "INQ",
        "name": "The Inquisitorate",
        "short_name": "Inquisition",
        "description": "The Deep Accord's enforcement arm. They hunt heresy, guard doctrine, and answer to no temporal authority.",
        "color": "|r",
        "tag": "faction_inq",
        "tag_category": "faction",
        "ranks": "inquisitorate_ranks",
        "default_rank": 1,
        "hq_room_tag": "inq_hq",
        "terminal_prototype": "terminal_inq",
    },
    "LIMELIGHT": {
        "key": "LIMELIGHT",
        "name": "The Limelight Guild",
        "short_name": "Limelight",
        "description": "Entertainment monopoly. TV, gambling, pleasure, spectacle. They own what you do when you're not working.",
        "color": "|m",
        "tag": "faction_limelight",
        "tag_category": "faction",
        "ranks": "guild_ranks",
        "default_rank": 1,
        "hq_room_tag": "limelight_hq",
        "terminal_prototype": "terminal_limelight",
    },
    "MYTHOS": {
        "key": "MYTHOS",
        "name": "The Mythos Guild",
        "short_name": "Mythos",
        "description": "Cybernetics and biological engineering. If it goes in a body or replaces one, Mythos built it.",
        "color": "|c",
        "tag": "faction_mythos",
        "tag_category": "faction",
        "ranks": "guild_ranks",
        "default_rank": 1,
        "hq_room_tag": "mythos_hq",
        "terminal_prototype": "terminal_mythos",
    },
    "VULCANI": {
        "key": "VULCANI",
        "name": "The Vulcani Guild",
        "short_name": "Vulcani",
        "description": "Arms and armor. Every weapon in the colony that isn't scrap-forged was manufactured or licensed by Vulcani.",
        "color": "|R",
        "tag": "faction_vulcani",
        "tag_category": "faction",
        "ranks": "guild_ranks",
        "default_rank": 1,
        "hq_room_tag": "vulcani_hq",
        "terminal_prototype": "terminal_vulcani",
    },
    "SEPULCHRE": {
        "key": "SEPULCHRE",
        "name": "The Sepulchre Guild",
        "short_name": "Sepulchre",
        "description": "Keepers of doctrine, controllers of cloning. Vatican meets mortuary. They own your soul's backup.",
        "color": "|x",
        "tag": "faction_sepulchre",
        "tag_category": "faction",
        "ranks": "guild_ranks",
        "default_rank": 1,
        "hq_room_tag": "sepulchre_hq",
        "terminal_prototype": "terminal_sepulchre",
    },
    "GUILD5": {
        "key": "GUILD5",
        "name": "Guild Five (Logistics)",
        "short_name": "Guild Five",
        "description": "Transport and logistics. Placeholder — rename when finalized.",
        "color": "|w",
        "tag": "faction_guild5",
        "tag_category": "faction",
        "ranks": "guild_ranks",
        "default_rank": 1,
        "hq_room_tag": "guild5_hq",
        "terminal_prototype": "terminal_guild5",
    },
    "GUILD6": {
        "key": "GUILD6",
        "name": "Guild Six (Infrastructure)",
        "short_name": "Guild Six",
        "description": "Construction and infrastructure. Placeholder — rename when finalized.",
        "color": "|w",
        "tag": "faction_guild6",
        "tag_category": "faction",
        "ranks": "guild_ranks",
        "default_rank": 1,
        "hq_room_tag": "guild6_hq",
        "terminal_prototype": "terminal_guild6",
    },
    "BURN": {
        "key": "BURN",
        "name": "The Cinders",
        "short_name": "Cinders",
        "description": "The Burn quarter's metalworking gang. They control scrap, forge-work, and crude weapons.",
        "color": "|R",
        "tag": "faction_burn",
        "tag_category": "faction",
        "ranks": "gang_ranks",
        "default_rank": 1,
        "hq_room_tag": "burn_hq",
        "terminal_prototype": "terminal_burn",
    },
    "SINK": {
        "key": "SINK",
        "name": "The Mycelium",
        "short_name": "Mycelium",
        "description": "The Sink quarter's bioworks gang. They control food, water, and organic compounds.",
        "color": "|g",
        "tag": "faction_sink",
        "tag_category": "faction",
        "ranks": "gang_ranks",
        "default_rank": 1,
        "hq_room_tag": "sink_hq",
        "terminal_prototype": "terminal_sink",
    },
    "RACK": {
        "key": "RACK",
        "name": "The Signal",
        "short_name": "Signal",
        "description": "The Rack quarter's information gang. They control data, Matrix access, and illegal tech.",
        "color": "|c",
        "tag": "faction_rack",
        "tag_category": "faction",
        "ranks": "gang_ranks",
        "default_rank": 1,
        "hq_room_tag": "rack_hq",
        "terminal_prototype": "terminal_rack",
    },
    "PIT": {
        "key": "PIT",
        "name": "The House",
        "short_name": "House",
        "description": "The Pit quarter's vice gang. They control gambling, fighting, pleasure, and the underground economy.",
        "color": "|m",
        "tag": "faction_pit",
        "tag_category": "faction",
        "ranks": "gang_ranks",
        "default_rank": 1,
        "hq_room_tag": "pit_hq",
        "terminal_prototype": "terminal_pit",
    },
}


def get_faction(key):
    """Look up a faction by abbreviation key (case-insensitive). Returns dict or None."""
    return FACTIONS.get((key or "").strip().upper())


def get_faction_by_tag(tag):
    """Look up a faction by its Evennia tag string. Returns dict or None."""
    for fdata in FACTIONS.values():
        if fdata["tag"] == tag:
            return fdata
    return None


def get_all_faction_keys():
    """Return list of all faction abbreviation keys."""
    return list(FACTIONS.keys())


def get_character_factions(character):
    """
    Return list of faction dicts for all factions the character belongs to.
    Checks Evennia tags in the 'faction' category.
    """
    if not character or not hasattr(character, "tags"):
        return []
    factions = []
    for fdata in FACTIONS.values():
        if character.tags.has(fdata["tag"], category=fdata["tag_category"]):
            factions.append(fdata)
    return factions


def is_faction_member(character, faction_key):
    """Check if character is a member of the given faction. Returns bool."""
    fdata = get_faction(faction_key)
    if not fdata or not character or not hasattr(character, "tags"):
        return False
    return character.tags.has(fdata["tag"], category=fdata["tag_category"])
