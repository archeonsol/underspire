"""
Food system constants: social class tiers for bars and kitchenettes.

Tier levels determine which base ingredients a station can use.
A station at tier "guild" (level 2) can use ingredients at levels 0, 1, and 2,
but not "bourgeois" (3) or "elite" (4).

Builders set the tier on a station object:
    @set bar/social_tier = guild
"""

SOCIAL_TIERS = {
    "gutter": {
        "name": "Gutter",
        "desc": "Bottom of the Warrens. Scavenged, expired, questionable.",
        "level": 0,
    },
    "slum": {
        "name": "Slum Standard",
        "desc": "Warrens-grade. Mass-produced, functional, joyless.",
        "level": 1,
    },
    "guild": {
        "name": "Guild Canteen",
        "desc": "Works-level. Institutional but edible. Portions are measured.",
        "level": 2,
    },
    "bourgeois": {
        "name": "Terrace Quality",
        "desc": "Real ingredients. Actual flavor. The concept of 'cuisine' exists here.",
        "level": 3,
    },
    "elite": {
        "name": "Apex Grade",
        "desc": "Imported, synthesized, or grown in private gardens. Food as art and power.",
        "level": 4,
    },
}

# Ordered list for display purposes
TIER_ORDER = ["gutter", "slum", "guild", "bourgeois", "elite"]


def get_tier_level(tier_name: str) -> int:
    """Return the numeric level for a tier name. Defaults to slum (1) if unknown."""
    return SOCIAL_TIERS.get(tier_name, {}).get("level", 1)


def get_tier_name(tier_key: str) -> str:
    """Return the display name for a tier key."""
    return SOCIAL_TIERS.get(tier_key, {}).get("name", tier_key.title())
