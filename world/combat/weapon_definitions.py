"""
Weapon and combat definition data used by the combat system.

This module intentionally contains only static/mostly-static data structures so
that combat logic can evolve independently of flavor text and numbers.
"""

from __future__ import annotations

from world.theme_colors import COMBAT_COLORS as CC

# Hands required per weapon: 1 = one-handed, 2 = two-handed. Used for wield/unwield.
WEAPON_HANDS = {
    "fists": 1,
    "claws": 1,
    "knife": 1,
    "long_blade": 2,
    "blunt": 2,
    "sidearm": 1,
    "longarm": 2,
    "automatic": 2,
}


# "Ready" messages when combat is initiated: attacker sees weapon-specific line;
# defender and room see generic messages. Templates use {target} for the
# defender's name.
COMBAT_READY_ATTACKER_MSG = {
    "fists": "" + CC["miss"] + "You raise your fists, eyeing {target}.|n",
    "claws": "" + CC["miss"] + "You spread your hands, chrome claws poised, eyeing {target}.|n",
    "knife": "" + CC["miss"] + "You ready your blade, eyeing {target}.|n",
    "long_blade": "" + CC["miss"] + "You ready your blade, eyeing {target}.|n",
    "blunt": "" + CC["miss"] + "You heft your weapon, eyeing {target}.|n",
    "sidearm": "" + CC["miss"] + "You bring your sidearm up, eyeing {target}.|n",
    "longarm": "" + CC["miss"] + "You shoulder your weapon, eyeing {target}.|n",
    "automatic": "" + CC["miss"] + "You bring the weapon to bear, eyeing {target}.|n",
    # Vehicle crew using attack + mounted weapon (opening range bands are legacy UI only; room size rules combat).
    "vehicle_mount": "" + CC["miss"] + "You train the mount on {target}, hands on the controls.|n",
}


# Kept as a safe fallback if weapon tiers are missing or misconfigured.
WEAPON_DATA = {
    "fists": {
        1: {"name": "Jab", "damage": 5},
        2: {"name": "Cross", "damage": 8},
        3: {"name": "Hook", "damage": 12},
        4: {"name": "Uppercut", "damage": 15},
        5: {"name": "Kidney Punch", "damage": 10},
        6: {"name": "Headbutt", "damage": 20},
    },
    "claws": {
        1: {"name": "Rake", "damage": 9},
        2: {"name": "Talon Slash", "damage": 13},
        3: {"name": "Hooked Rip", "damage": 17},
        4: {"name": "Eviscerating Arc", "damage": 22},
        5: {"name": "Fingertip Feint", "damage": 11},
        6: {"name": "Tendon Shear", "damage": 19},
    },
    "knife": {
        1: {"name": "Slash", "damage": 12},
        2: {"name": "Stab", "damage": 18},
        3: {"name": "Gut-rip", "damage": 25},
        4: {"name": "Throat-slit", "damage": 35},
        5: {"name": "Pommel Strike", "damage": 8},
        6: {"name": "Arterial Nick", "damage": 22},
    },
    "long_blade": {
        1: {"name": "Cut", "damage": 14},
        2: {"name": "Thrust", "damage": 20},
        3: {"name": "Sweep", "damage": 18},
        4: {"name": "Overhead", "damage": 28},
        5: {"name": "Pommel Bash", "damage": 10},
        6: {"name": "Deep Strike", "damage": 32},
    },
    "blunt": {
        1: {"name": "Swing", "damage": 12},
        2: {"name": "Strike", "damage": 18},
        3: {"name": "Crush", "damage": 24},
        4: {"name": "Overhead Smash", "damage": 30},
        5: {"name": "Rib Shot", "damage": 16},
        6: {"name": "Skull Crack", "damage": 26},
    },
    "sidearm": {
        1: {"name": "Single Shot", "damage": 14},
        2: {"name": "Double Tap", "damage": 22},
        3: {"name": "Center Mass", "damage": 28},
        4: {"name": "Head Shot", "damage": 38},
        5: {"name": "Quick Draw", "damage": 18},
        6: {"name": "Controlled Pair", "damage": 26},
    },
    "longarm": {
        1: {"name": "Single Shot", "damage": 20},
        2: {"name": "Aimed Shot", "damage": 32},
        3: {"name": "Burst", "damage": 28},
        4: {"name": "Precision Hit", "damage": 42},
        5: {"name": "Hip Fire", "damage": 16},
        6: {"name": "Follow-through", "damage": 36},
    },
    "automatic": {
        1: {"name": "Short Burst", "damage": 18},
        2: {"name": "Sweep", "damage": 24},
        3: {"name": "Sustained Fire", "damage": 30},
        4: {"name": "Controlled Burst", "damage": 36},
        5: {"name": "Spray", "damage": 22},
        6: {"name": "Mag Dump", "damage": 44},
    },
}

