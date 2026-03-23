"""
Maps combat weapon_key strings to room-size modifier classes (SKILL_STATS-style names).
"""

from __future__ import annotations

# Keys match ROOM_SIZE_MODIFIERS second element (unarmed, short_blades, …)
WEAPON_KEY_TO_WEAPON_CLASS: dict[str, str] = {
    "fists": "unarmed",
    "unarmed": "unarmed",
    "claws": "unarmed",
    "knife": "short_blades",
    "short_blade": "short_blades",
    "long_blade": "long_blades",
    "blunt": "blunt_weaponry",
    "sidearm": "sidearms",
    "longarm": "longarms",
    "automatic": "automatics",
    "bite": "unarmed",
    "saw": "short_blades",
    "gouge": "short_blades",
    "acid_spit": "sidearms",
    "frost_breath": "longarms",
    "shock_lash": "blunt_weaponry",
    "void_rend": "long_blades",
    "void_pulse": "longarms",
}


def get_weapon_class_for_room_mod(weapon_key: str) -> str:
    return WEAPON_KEY_TO_WEAPON_CLASS.get(weapon_key, "unarmed")
