"""
Rune system data: definitions, incense mappings, color palette, and all
narrative / ambient message strings.

Runes are permanent spiritual modifications carved onto a character's
astral body during a sacred ceremony. They grant stat boosts that settle
over 24 hours and are erased by death or cloning.
"""

# ── Rune definitions ──────────────────────────────────────────────────────

# Each rune maps to a SPECIAL stat and a restricted color code.
# Color codes are the ONLY permitted colors for rune descriptions.
RUNES = {
    "thurisaz": {
        "stat": "strength",
        "incense": "dragons_blood",
        "incense_display": "Dragon's Blood",
        "color": "|500",
        "display": "Thurisaz",
        "flavor": "the rune of primal force and the thorn",
    },
    "ansuz": {
        "stat": "charisma",
        "incense": "benzoin",
        "incense_display": "Benzoin",
        "color": "|305",
        "display": "Ansuz",
        "flavor": "the rune of the divine voice and breath",
    },
    "raidho": {
        "stat": "agility",
        "incense": "peppermint",
        "incense_display": "Peppermint",
        "color": "|055",
        "display": "Raidho",
        "flavor": "the rune of the wheel and the journey",
    },
    "mannaz": {
        "stat": "intelligence",
        "incense": "frankincense",
        "incense_display": "Frankincense",
        "color": "|445",
        "display": "Mannaz",
        "flavor": "the rune of humanity and the awakened mind",
    },
    "nauthiz": {
        "stat": "endurance",
        "incense": "myrrh",
        "incense_display": "Myrrh",
        "color": "|503",
        "display": "Nauthiz",
        "flavor": "the rune of necessity and the need-fire",
    },
    "kenaz": {
        "stat": "perception",
        "incense": "sage",
        "incense_display": "Sage",
        "color": "|350",
        "display": "Kenaz",
        "flavor": "the rune of the torch and the opened eye",
    },
    "jera": {
        "stat": "luck",
        "incense": "cinnamon",
        "incense_display": "Cinnamon",
        "color": "|540",
        "display": "Jera",
        "flavor": "the rune of the harvest and the turning year",
    },
}

# Reverse lookup: incense_type -> rune key
INCENSE_TO_RUNE = {v["incense"]: k for k, v in RUNES.items()}

# Permitted color codes (one per rune). No other colors are allowed.
RUNE_COLOR_CODES = {k: v["color"] for k, v in RUNES.items()}

# Buff progression: (seconds_after_application, buff_value)
# Buff starts minimal and reaches full at 24h.
RUNE_BUFF_SCHEDULE = [
    (0,          2),   # immediate: partial
    (8 * 3600,   4),   # 8 hours: halfway
    (24 * 3600,  6),   # 24 hours: full settle
]

RUNE_FULL_BUFF_VALUE = 6

# ── Narrative messages (broadcast to room during ~60s ritual) ─────────────
# {carver} and {target} are character objects in msg_contents mapping — each
# viewer sees recog-aware names via get_display_name(looker=receiver).
# {rune} and {part} are plain strings (rune display name, body part key).

CARVE_NARRATIVE = [
    # (delay_seconds, message)
    (0,
     "|=mThe incense catches. A thin coil of smoke rises from the brazier, curling "
     "upward in a perfect helix before dispersing into the air.|n"),

    (5,
     "|=m{carver} closes their eyes and breathes slowly. The smoke thickens. "
     "Something in the room shifts — a pressure behind the eyes, a faint ringing "
     "in the ears that wasn't there before.|n"),

    (12,
     "|=m{carver} raises the athame. The blade catches no light. It seems instead "
     "to absorb it, drinking the shadows of the room into its edge.|n"),

    (18,
     "|=mThe air around {target} grows heavy. Their breath fogs despite the warmth "
     "of the room. The smoke from the incense bends toward them as if drawn.|n"),

    (24,
     "|=m{carver} begins to trace the shape of |w{rune}|n|=m in the air above "
     "{target}'s {part}. The athame leaves a faint luminous trail — not light "
     "exactly, but the memory of light.|n"),

    (31,
     "|=mThe athame descends. It does not touch skin. It passes through it.|n\n"
     "|=m{target} goes rigid. Their eyes roll back. The rune-trace glows white-hot "
     "where the blade moves, bloodless and absolute, engraving itself into something "
     "deeper than flesh.|n"),

    (38,
     "|=m{target}'s lips part. No sound comes out at first — then a low, sustained "
     "exhalation, almost a moan, as the symbol burns itself into their astral body. "
     "The pain is real. The wound is not.|n"),

    (44,
     "|=mThe shape of |w{rune}|n|=m begins to manifest on {target}'s {part}. "
     "It appears as if surfacing from beneath the skin — rising, not carved. "
     "The lines are perfect. Inhuman. No hand could have drawn them so.|n"),

    (50,
     "|=mA sound like distant thunder rolls through the room. The candles, if any "
     "burn here, gutter sideways. The incense smoke freezes in place for a single "
     "heartbeat, then collapses.|n"),

    (55,
     "|=m{target} shudders violently. Their hands grip whatever is nearest. "
     "The rune pulses once — twice — then settles into the skin like a coal "
     "cooling from white to red to dark.|n"),

    (60,
     "|=m{carver} lowers the athame. The room breathes again. "
     "The mark of |w{rune}|n|=m rests on {target}'s {part}, still faintly warm "
     "to the eye if not to the touch. The ritual is complete.|n"),
]

# ── Ambient settling messages (sent privately to the target) ──────────────
# Delivered at intervals over 24h as the rune 'settles in'.
# {rune} = display name, {stat} = stat name, {part} = body part.

SETTLE_MESSAGES = [
    # ~3 hours
    "|=mYour {part} aches with a deep, sourceless heat. The mark of |w{rune}|n|=m "
    "seems to breathe when you are not looking at it directly. You feel faintly "
    "watched — not by anything outside you.|n",

    # ~7 hours
    "|=mIn a quiet moment you catch yourself moving differently. Something in your "
    "body has begun to remember what the rune is teaching it. The change is not "
    "yet complete. It is only beginning.|n",

    # ~12 hours
    "|=mYou dream of a vast dark field under a sky with too many stars. A figure "
    "stands at the center, faceless, and points at your {part}. When you wake the "
    "mark of |w{rune}|n|=m is warm against your skin and your {stat} feels "
    "different — sharper, heavier, more present.|n",

    # ~18 hours
    "|=mThe rune |w{rune}|n|=m has stopped hurting. In its place is something "
    "like a second heartbeat, slow and deliberate, pulsing from your {part}. "
    "You are aware of it the way you are aware of your own breathing. "
    "It is becoming part of you.|n",

    # ~24 hours (full settle)
    "|=mThe mark of |w{rune}|n|=m has settled. You feel it now not as a wound "
    "or a foreign thing but as something that was always there, waiting to be "
    "named. The gift of {flavor} is fully yours. "
    "It will remain until death unmakes it.|n",
]

# Timing offsets in seconds for each settle message
SETTLE_OFFSETS = [
    3 * 3600,    # 3h
    7 * 3600,    # 7h
    12 * 3600,   # 12h
    18 * 3600,   # 18h
    24 * 3600,   # 24h (full settle, matches final RUNE_BUFF_SCHEDULE entry)
]

# ── Failure messages (ritual fails the skill roll) ────────────────────────

CARVE_FAIL_MESSAGES = [
    "|=mThe ritual unravels. The athame's light gutters and dies. {carver} lowers "
    "the blade, jaw tight. The incense smoke disperses without ceremony. "
    "The mark did not take.|n",

    "|=mSomething resists. The rune-trace fractures midway through its shape, "
    "the luminous lines collapsing inward. {carver} pulls back. "
    "The incense is spent. The ritual has failed.|n",

    "|=mThe connection breaks. {carver}'s hand trembles once and stills. "
    "The athame goes dark. Whatever presence filled the room recedes "
    "like a tide going out. The rune will not be carved today.|n",
]
