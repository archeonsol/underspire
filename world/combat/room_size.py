"""
Room size combat modifiers. Each room is tagged with a size category.
Weapon classes receive bonuses or penalties based on the room size.
"""

from __future__ import annotations

import time

ROOM_SIZES = {
    "cqc": {
        "name": "Close Quarters",
        "desc": "Tight space. Corridors, small rooms, vehicle interiors, alleys.",
        "tag": "cqc",
    },
    "medium": {
        "name": "Medium Range",
        "desc": "Standard room. Streets, open rooms, intersections, tunnels.",
        "tag": "medium",
    },
    "open": {
        "name": "Open Ground",
        "desc": "Wide open space. Plazas, parks, large halls, air shafts.",
        "tag": "open",
    },
}

# Modifier applied to attack rolls. Positive = bonus, negative = penalty.
ROOM_SIZE_MODIFIERS = {
    ("cqc", "unarmed"): 8,
    ("cqc", "short_blades"): 10,
    ("cqc", "long_blades"): 4,
    ("cqc", "blunt_weaponry"): 6,
    ("cqc", "sidearms"): 2,
    ("cqc", "longarms"): -10,
    ("cqc", "automatics"): -6,
    ("medium", "unarmed"): 0,
    ("medium", "short_blades"): 0,
    ("medium", "long_blades"): 0,
    ("medium", "blunt_weaponry"): 0,
    ("medium", "sidearms"): 4,
    ("medium", "longarms"): 2,
    ("medium", "automatics"): 4,
    ("open", "unarmed"): -12,
    ("open", "short_blades"): -10,
    ("open", "long_blades"): -8,
    ("open", "blunt_weaponry"): -10,
    ("open", "sidearms"): 6,
    ("open", "longarms"): 12,
    ("open", "automatics"): 10,
}


def get_room_size(room):
    """Return the room size tag. Defaults to 'medium' if untagged."""
    if not room or not hasattr(room, "tags"):
        return "medium"
    for size_key in ROOM_SIZES:
        if room.tags.has(size_key, category="room_size"):
            return size_key
    return "medium"


def get_room_size_modifier(room, weapon_class: str) -> int:
    """Return the attack roll modifier for this weapon class in this room."""
    size = get_room_size(room)
    return int(ROOM_SIZE_MODIFIERS.get((size, weapon_class), 0))


def get_smoke_attack_penalty(room, weapon_key: str) -> int:
    """
    Thick smoke in the room penalizes ranged attacks.
    Set room.db.smoke_until = time.time() + duration when deploying smoke.
    """
    if not room or not getattr(room, "db", None):
        return 0
    until = float(getattr(room.db, "smoke_until", 0) or 0)
    if until <= time.time():
        return 0
    try:
        from world.ammo import is_ranged_weapon
    except ImportError:
        is_ranged_weapon = lambda k: k in ("sidearm", "longarm", "automatic")
    if is_ranged_weapon(weapon_key):
        return -15
    return 0
