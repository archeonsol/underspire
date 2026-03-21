"""
Faction registry terminals and door exit prototypes.
Spawn terminals with e.g. |wspawnitem terminal_imp|n (after loading prototypes).
"""

from world.rpg.factions import FACTIONS

_FTAG = ["faction", "terminal"]

_TERMINAL_DESC = {
    "IMP": (
        "A wall-mounted terminal bearing the Imperium Guard insignia. The screen glows amber. "
        "A card reader slot sits beneath the display."
    ),
    "INQ": (
        "A narrow black terminal with a red-lit scanner strip. The Inquisitorate seal is etched "
        "into the casing; the display shows only approved doctrine."
    ),
    "LIMELIGHT": (
        "A garish terminal wrapped in neon trim. The Limelight logo pulses softly; slot machines "
        "and crowd noise seem encoded in its hum."
    ),
    "MYTHOS": (
        "A sterile white terminal with biometric pads and a soft blue display. Mythos certification "
        "marks line the frame."
    ),
    "VULCANI": (
        "A heavy armored terminal stamped with the Vulcani forge-mark. The screen flickers like heat haze."
    ),
    "SEPULCHRE": (
        "A dark stone-faced terminal with funerary script. The screen is dim; incense seems ground into the seams."
    ),
    "GUILD5": "A logistics terminal: routing codes scroll idle on a dusty screen.",
    "GUILD6": "An infrastructure terminal: structural diagrams flicker on scratched glass.",
    "BURN": (
        "A battered terminal bolted to a structural beam. The screen flickers. The casing is scorched. "
        "Someone has scratched the Cinders' mark into the metal above it."
    ),
    "SINK": (
        "A moisture-stained terminal overgrown with cabling like roots. The Mycelium sigil is acid-etched nearby."
    ),
    "RACK": (
        "A terminal covered in aftermarket jacks and illegal decals. The Signal's glyph strobes when idle."
    ),
    "PIT": (
        "A velvet-framed terminal that smells of smoke and synth-spice. The House mark glows faintly violet."
    ),
}


def _terminal_entry(fk):
    fd = FACTIONS[fk]
    desc = _TERMINAL_DESC.get(fk, f"A {fd['short_name']} registry terminal.")
    return {
        "prototype_key": fd["terminal_prototype"],
        "prototype_tags": _FTAG,
        "key": f"{fd['short_name']} Registry Terminal",
        "typeclass": "typeclasses.rpg.faction_terminal.RegistryTerminal",
        "desc": desc,
        "attrs": [
            ("faction_key", fk),
            ("terminal_name", f"{fd['short_name']} Registry"),
        ],
        "tags": [("faction_terminal", "object_type")],
    }


TERMINAL_PROTOTYPES = [_terminal_entry(fk) for fk in FACTIONS]

EXIT_DOOR_BASIC = {
    "prototype_key": "exit_door",
    "prototype_tags": ["exit", "door"],
    "key": "door",
    "typeclass": "typeclasses.exits.Exit",
    "attrs": [
        ("door", True),
        ("door_open", False),
        ("door_name", "door"),
        ("door_locked", False),
        ("door_auto_close", 0),
    ],
}

EXIT_DOOR_BIOSCAN_FACTION = {
    "prototype_key": "exit_bioscan_faction",
    "prototype_tags": ["exit", "door", "bioscan"],
    "key": "bioscan door",
    "typeclass": "typeclasses.exits.Exit",
    "attrs": [
        ("door", True),
        ("door_open", False),
        ("door_name", "bioscan door"),
        ("door_locked", False),
        ("bioscan", True),
        ("bioscan_type", "faction"),
        ("bioscan_faction", ""),
        ("bioscan_rank", 1),
        ("bioscan_auto_close", 8),
        (
            "bioscan_message_pass",
            "Bioscan accepted. Identity confirmed. The door opens.",
        ),
        ("bioscan_message_fail", "Bioscan rejected. Identity not recognized."),
        ("bioscan_sound_fail", True),
    ],
}

EXIT_DOOR_BIOSCAN_RANK = {
    "prototype_key": "exit_bioscan_rank",
    "prototype_tags": ["exit", "door", "bioscan"],
    "key": "secured door",
    "typeclass": "typeclasses.exits.Exit",
    "attrs": [
        ("door", True),
        ("door_open", False),
        ("door_name", "secured door"),
        ("door_locked", False),
        ("bioscan", True),
        ("bioscan_type", "rank"),
        ("bioscan_faction", ""),
        ("bioscan_rank", 3),
        ("bioscan_auto_close", 8),
        ("bioscan_message_pass", "Clearance confirmed. Access granted."),
        ("bioscan_message_fail", "Insufficient clearance. This area is restricted."),
        ("bioscan_sound_fail", True),
    ],
}

for _tp in TERMINAL_PROTOTYPES:
    globals()[_tp["prototype_key"]] = _tp
