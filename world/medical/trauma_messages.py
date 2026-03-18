"""
Trauma messaging (combat hit aftermath).

This module contains *only* narrative strings used to describe trauma triggered
by hits (organ damage, fractures, bleeding). It is intentionally separated from
the medical simulation logic so writers can iterate on tone/voice safely.

Keys are "combat message profile ids" as produced by
`world.combat.combat_messages.get_message_profile_id`, for example:

- "knife"
- "long_blade"
- "long_blade::executioners_blade"

Placeholders:
- {loc}: hit location string (e.g. "torso", "left arm", "head")

Values:
TRAUMA_MESSAGE_PROFILES[profile_id][kind][damage_type] = (attacker_line, defender_line)

Where:
- kind is "organ" or "fracture"
- damage_type is one of: "slashing", "impact", "penetrating", "burn", "freeze", "arc", "void"

Any missing entry falls back to the generic damage-type messaging in
`world.medical.get_brutal_hit_flavor`.
"""

from __future__ import annotations

# Expand this over time. Keep it writer-friendly: short, punchy, one line per kind.
TRAUMA_MESSAGE_PROFILES: dict[str, dict[str, dict[str, tuple[str, str]]]] = {
    # --- Baseline weapon-key profiles (placeholders; tweak freely) ---
    "fists": {
        "organ": {
            "impact": (
                "|r(PLACEHOLDER fists/organ/impact) You drove the shock through their {loc}.|n",
                "|r(PLACEHOLDER fists/organ/impact) Something inside your {loc} lurched and tore.|n",
            ),
        },
        "fracture": {
            "impact": (
                "|y(PLACEHOLDER fists/fracture/impact) Knuckles and bone at their {loc}.|n",
                "|y(PLACEHOLDER fists/fracture/impact) Something in your {loc} gives with a sickening pop.|n",
            ),
        },
    },
    "knife": {
        "organ": {
            "slashing": (
                "|r(PLACEHOLDER knife/organ/slashing) Your blade finds something vital at their {loc}.|n",
                "|r(PLACEHOLDER knife/organ/slashing) Something inside your {loc} tears open.|n",
            ),
            "penetrating": (
                "|r(PLACEHOLDER knife/organ/penetrating) You drove steel deep into their {loc}.|n",
                "|r(PLACEHOLDER knife/organ/penetrating) A hard, wrong pressure blooms inside your {loc}.|n",
            ),
        },
        "fracture": {
            "slashing": (
                "|y(PLACEHOLDER knife/fracture/slashing) The knife scrapes bone at their {loc}.|n",
                "|y(PLACEHOLDER knife/fracture/slashing) Steel grates against bone in your {loc}.|n",
            ),
        },
    },
    "long_blade": {
        "organ": {
            "slashing": (
                "|r(PLACEHOLDER long_blade/organ/slashing) The cut opens them deep at the {loc}.|n",
                "|r(PLACEHOLDER long_blade/organ/slashing) Something inside your {loc} is suddenly loose and wrong.|n",
            ),
        },
        "fracture": {
            "slashing": (
                "|y(PLACEHOLDER long_blade/fracture/slashing) Edge meets bone at their {loc}.|n",
                "|y(PLACEHOLDER long_blade/fracture/slashing) The edge hits bone in your {loc}.|n",
            ),
        },
    },
    "blunt": {
        "organ": {
            "impact": (
                "|r(PLACEHOLDER blunt/organ/impact) The impact caves something in at their {loc}.|n",
                "|r(PLACEHOLDER blunt/organ/impact) Your {loc} feels crushed from the inside.|n",
            ),
        },
        "fracture": {
            "impact": (
                "|y(PLACEHOLDER blunt/fracture/impact) A sharp crack from their {loc}.|n",
                "|y(PLACEHOLDER blunt/fracture/impact) A sharp crack from your {loc}.|n",
            ),
        },
    },
    "sidearm": {
        "organ": {
            "penetrating": (
                "|r(PLACEHOLDER sidearm/organ/penetrating) Your shot punches into their {loc} and keeps going.|n",
                "|r(PLACEHOLDER sidearm/organ/penetrating) The bullet hits your {loc} and something inside fails.|n",
            ),
        },
        "fracture": {},
    },
    "longarm": {
        "organ": {
            "penetrating": (
                "|r(PLACEHOLDER longarm/organ/penetrating) The round drives deep into their {loc}.|n",
                "|r(PLACEHOLDER longarm/organ/penetrating) Your {loc} seizes around the wound. Something vital is wrong.|n",
            ),
        },
        "fracture": {},
    },
    "automatic": {
        "organ": {
            "penetrating": (
                "|r(PLACEHOLDER automatic/organ/penetrating) One of the rounds finds something vital in their {loc}.|n",
                "|r(PLACEHOLDER automatic/organ/penetrating) A shot in your {loc} goes deep. You can feel it.|n",
            ),
        },
        "fracture": {},
    },
    # --- Executioner's Blade trauma profiles ---
    "long_blade::executioners_blade": {
        "organ": {
            "slashing": (
                "|rThe executioner's edge splits {loc} wide open: something dark and vital spills out, steaming in the air. The wound doesn't close; it gapes like a second mouth.|n",
                "|rThe headsman's blade lays your {loc} open to the root. You feel organs shift and slide against each other in ways they were never meant to. Something essential just stopped working.|n",
            ),
        },
        "fracture": {
            "slashing": (
                "|yThe executioner's blade hits bone at their {loc} and keeps going: not a clean break but a splintering, grinding crunch as the heavy edge chews through.|n",
                "|yThe headsman's edge catches bone in your {loc} and you hear it before you feel it — a wet, crunching snap that travels up your whole skeleton. The limb bends where it shouldn't.|n",
            ),
        },
    },
}

