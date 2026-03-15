"""
Ammunition types and mapping to firearm classes. Ranged weapons use these
to require and consume ammo in combat. Expand later with calibers, damage mods, etc.
"""
# Weapon keys that use ammo (must match world.combat.WEAPON_DATA and typeclasses.weapons)
RANGED_WEAPON_KEYS = ("sidearm", "longarm", "automatic")

# Ammo type identifiers (used in db.ammo_type on weapons and ammo objects)
AMMO_TYPE_SIDEARM = "sidearm"
AMMO_TYPE_LONGARM = "longarm"
AMMO_TYPE_AUTOMATIC = "automatic"
AMMO_TYPES = (AMMO_TYPE_SIDEARM, AMMO_TYPE_LONGARM, AMMO_TYPE_AUTOMATIC)

# Which ammo type each weapon key accepts
WEAPON_AMMO_TYPE = {
    "sidearm": AMMO_TYPE_SIDEARM,
    "longarm": AMMO_TYPE_LONGARM,
    "automatic": AMMO_TYPE_AUTOMATIC,
}

# Default magazine capacity per weapon key (overridable per object)
DEFAULT_AMMO_CAPACITY = {
    "sidearm": 12,
    "longarm": 5,
    "automatic": 30,
}

# Display names for ammo types (UI / reload messages)
AMMO_TYPE_DISPLAY_NAMES = {
    AMMO_TYPE_SIDEARM: "pistol",
    AMMO_TYPE_LONGARM: "rifle",
    AMMO_TYPE_AUTOMATIC: "automatic",
}

# Typeclass path to create ammo/magazine when unloading (so you get an item back)
AMMO_TYPE_TYPECLASS = {
    AMMO_TYPE_SIDEARM: "typeclasses.ammo.PistolAmmo",
    AMMO_TYPE_LONGARM: "typeclasses.ammo.RifleAmmo",
    AMMO_TYPE_AUTOMATIC: "typeclasses.ammo.AutomaticAmmo",
}

# Default key for ejected magazine item by ammo type
AMMO_TYPE_MAGAZINE_KEY = {
    AMMO_TYPE_SIDEARM: "pistol magazine",
    AMMO_TYPE_LONGARM: "rifle magazine",
    AMMO_TYPE_AUTOMATIC: "automatic magazine",
}


def is_ranged_weapon(weapon_key):
    """True if this weapon_key uses ammunition."""
    return weapon_key in RANGED_WEAPON_KEYS


def get_ammo_capacity_for_weapon_key(weapon_key):
    """Default capacity for a weapon key; 0 if not ranged."""
    return DEFAULT_AMMO_CAPACITY.get(weapon_key, 0)
