r"""
Evennia settings file.

The available options are found in the default settings file found
here:

https://www.evennia.com/docs/latest/Setup/Settings-Default.html

Remember:

Don't copy more from the default file than you actually intend to
change; this will make sure that you don't overload upstream updates
unnecessarily.

When changing a setting requiring a file system path (like
path/to/actual/file.py), use GAME_DIR and EVENNIA_DIR to reference
your game folder and the Evennia library folders respectively. Python
paths (path.to.module) should be given relative to the game's root
folder (typeclasses.foo) whereas paths within the Evennia library
needs to be given explicitly (evennia.foo).

If you want to share your game dir, including its settings, you can
put secret game- or server-specific settings in secret_settings.py.

"""

# Use the defaults from Evennia unless explicitly overridden
from evennia.settings_default import *

######################################################################
# Evennia base server config
######################################################################

# This is the name of your game. Make it catchy!
SERVERNAME = "UNDERSPIRE"

# Command set for Characters (must be the game's CharacterCmdSet so stats/heal etc. are available).
CMDSET_CHARACTER = "commands.default_cmdsets.CharacterCmdSet"

# One character per account. No auto-puppet: login shows main menu (select character or create).
# Account stays separate; after "go light" they have no character and must create from the menu.
AUTO_CREATE_CHARACTER_WITH_ACCOUNT = True

# Room dbref (int) or None. If set, @ooc moves the character here; @ic returns them. Tag "ooc_room" used as fallback.
OOC_ROOM_ID = None
AUTO_PUPPET_ON_LOGIN = False
MULTISESSION_MODE = 2
MAX_NR_CHARACTERS = 1

# Prefer Argon2 for password hashing (requires: pip install argon2-cffi).
# Existing PBKDF2 hashes still work; new/changed passwords use Argon2.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

######################################################################
# Combat roll tuning (System 2 logistic combat)
######################################################################
#
# All values are optional; omit this block to use defaults in world.combat.rolls.
#
# - w_skill / w_stats: relative contribution to rating.
# - k: steepness of S-curve on (attacker_rating - defender_rating).
# - min_p/max_p: floors/ceilings for hit probability.
# - quality_sigma: how swingy the 1-100 quality output is.
#
COMBAT_ROLLS = {
    # Rating model:
    # - "multiplicative" uses: R = c_mul * stat_eff * (1 + alpha*(skill/150)) + mods
    # - stat_eff can be raw stat sum or a diminishing-returns transform (dr_mode)
    "rating_model": "additive",

    # Diminishing returns on stats before rating (Option D)
    # "log" compresses very high stat sums so stacking has less runaway impact.
    "dr_mode": "log",
    "dr_scale": 150.0,

    # Multiplicative coefficients (Option B)
    # Scale rating down so typical values land ~0-150 for readability in debug.
    "c_mul": 0.5,
    "alpha": 1.0,

    # (Additive-only weights; unused in multiplicative mode)
    "w_skill": 1.0,
    "w_stats": 1.0,

    # Steeper curve: bigger advantage -> more reliable hits/defenses.
    # If we scale ratings down, we scale k up to preserve curve behavior.
    "k": 0.04,
    "min_p": 0.05,
    "max_p": 0.95,
    # Slightly less swingy quality -> more decisive outcomes.
    # Sigma is in "rating delta units" too; scale it with the rating.
    "quality_sigma": 7.0,
    "parry_bias": 0.0,
    "dodge_bias": 0.0,
    "body_shield_bias": -0.5,
}

# Optional: print combat roll debug to staff (Builder+) in the room.
# This is very spammy; keep it False outside of tuning sessions.
COMBAT_DEBUG_ROLLS = False

######################################################################
# Module-based object prototypes (Evennia)
######################################################################
PROTOTYPE_MODULES = [
    "world.prototypes.tailoring_prototypes",
    "world.prototypes.weapon_prototypes",
    "world.prototypes.food_prototypes",
    "world.prototypes.drink_prototypes",
    "world.prototypes.alcohol_prototypes",
    "world.prototypes.performance_prototypes",
    "world.prototypes.medical_prototypes",
    "world.prototypes.alchemy_prototypes",
    "world.prototypes.cyberware_prototypes",
    "world.prototypes.armor_prototypes",
    "world.prototypes.faction_prototypes",
    "world.prototypes.vehicle_prototypes",
    "world.prototypes.rune_prototypes",
    "evennia.contrib.grid.xyzgrid.prototypes",
]

######################################################################
# Custom Django apps
######################################################################

INSTALLED_APPS += ["world"]

######################################################################
# Settings given in secret_settings.py override those in this file.
######################################################################
try:
    from server.conf.secret_settings import *
except ImportError:
    print("secret_settings.py file not found or failed to import.")

# Launcher: `evennia xyzgrid init|add|spawn` (see Evennia xyzgrid contrib README).
EXTRA_LAUNCHER_COMMANDS = dict(EXTRA_LAUNCHER_COMMANDS)
EXTRA_LAUNCHER_COMMANDS["xyzgrid"] = "evennia.contrib.grid.xyzgrid.launchcmd.xyzcommand"
# mygame/server/conf/settings.py
