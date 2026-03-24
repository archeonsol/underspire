# Rune carving items: ritual athame and the seven incense types.
# Tags: |wrune|n (all), plus |wathame|n or |wincense|n for |wspawnitem list <tag>|n.

_RUNE = ["rune"]
_RUNE_ATHAME = ["rune", "athame"]
_RUNE_INCENSE = ["rune", "incense"]

# ── Ritual Athame ─────────────────────────────────────────────────────────

RITUAL_ATHAME = {
    "prototype_key": "RITUAL_ATHAME",
    "prototype_tags": _RUNE_ATHAME,
    "key": "ritual athame",
    "typeclass": "typeclasses.items.Item",
    "desc": (
        "A double-edged blade no longer than a hand's span, its steel so dark it "
        "seems to swallow light rather than reflect it. The handle is wrapped in "
        "cord that has been knotted in patterns no one has bothered to explain. "
        "It does not feel like a weapon. It feels like a key."
    ),
    "attrs": [
        ("is_athame", True),
    ],
    "tags": [("athame", "object_type")],
}

# ── Incense ───────────────────────────────────────────────────────────────

INCENSE_DRAGONS_BLOOD = {
    "prototype_key": "INCENSE_DRAGONS_BLOOD",
    "prototype_tags": _RUNE_INCENSE,
    "key": "stick of dragon's blood incense",
    "typeclass": "typeclasses.items.Item",
    "desc": (
        "A deep crimson incense stick, dense and resinous. Unlit, it smells of "
        "dried blood and something older — earth after rain, iron, the edge of "
        "a storm. It is used in rites of force and primal will."
    ),
    "attrs": [
        ("is_incense", True),
        ("incense_type", "dragons_blood"),
        ("is_lit", False),
    ],
    "tags": [("incense", "object_type")],
}

INCENSE_BENZOIN = {
    "prototype_key": "INCENSE_BENZOIN",
    "prototype_tags": _RUNE_INCENSE,
    "key": "stick of benzoin incense",
    "typeclass": "typeclasses.items.Item",
    "desc": (
        "A pale amber incense stick with a faintly vanilla-sweet scent that "
        "deepens into something almost medicinal when lit. Associated with the "
        "voice, the breath, and the power of persuasion."
    ),
    "attrs": [
        ("is_incense", True),
        ("incense_type", "benzoin"),
        ("is_lit", False),
    ],
    "tags": [("incense", "object_type")],
}

INCENSE_PEPPERMINT = {
    "prototype_key": "INCENSE_PEPPERMINT",
    "prototype_tags": _RUNE_INCENSE,
    "key": "stick of peppermint incense",
    "typeclass": "typeclasses.items.Item",
    "desc": (
        "A pale green incense stick that smells sharp and clean, like cold air "
        "moving fast. It is used in rites of motion, speed, and the road that "
        "never ends."
    ),
    "attrs": [
        ("is_incense", True),
        ("incense_type", "peppermint"),
        ("is_lit", False),
    ],
    "tags": [("incense", "object_type")],
}

INCENSE_FRANKINCENSE = {
    "prototype_key": "INCENSE_FRANKINCENSE",
    "prototype_tags": _RUNE_INCENSE,
    "key": "stick of frankincense incense",
    "typeclass": "typeclasses.items.Item",
    "desc": (
        "A golden-white incense stick with a resinous, cathedral scent — ancient "
        "and serious. It has been burned in sacred spaces for longer than anyone "
        "can remember. It is used in rites of the mind and the awakened self."
    ),
    "attrs": [
        ("is_incense", True),
        ("incense_type", "frankincense"),
        ("is_lit", False),
    ],
    "tags": [("incense", "object_type")],
}

INCENSE_MYRRH = {
    "prototype_key": "INCENSE_MYRRH",
    "prototype_tags": _RUNE_INCENSE,
    "key": "stick of myrrh incense",
    "typeclass": "typeclasses.items.Item",
    "desc": (
        "A dark brown incense stick, bitter and smoky, with an undertone of "
        "something almost medicinal. It is burned in rites of endurance, "
        "necessity, and the will to survive what cannot be avoided."
    ),
    "attrs": [
        ("is_incense", True),
        ("incense_type", "myrrh"),
        ("is_lit", False),
    ],
    "tags": [("incense", "object_type")],
}

INCENSE_SAGE = {
    "prototype_key": "INCENSE_SAGE",
    "prototype_tags": _RUNE_INCENSE,
    "key": "stick of sage incense",
    "typeclass": "typeclasses.items.Item",
    "desc": (
        "A grey-green incense stick, dry and herbal. When lit it smells of "
        "cleared spaces and opened eyes. It is used in rites of perception "
        "and the torch that reveals what hides in the dark."
    ),
    "attrs": [
        ("is_incense", True),
        ("incense_type", "sage"),
        ("is_lit", False),
    ],
    "tags": [("incense", "object_type")],
}

INCENSE_CINNAMON = {
    "prototype_key": "INCENSE_CINNAMON",
    "prototype_tags": _RUNE_INCENSE,
    "key": "stick of cinnamon incense",
    "typeclass": "typeclasses.items.Item",
    "desc": (
        "A warm reddish-brown incense stick with a spiced, almost sweet scent "
        "that carries a faint bite. It is burned in rites of fortune, the harvest, "
        "and the slow turning of good things toward those who wait."
    ),
    "attrs": [
        ("is_incense", True),
        ("incense_type", "cinnamon"),
        ("is_lit", False),
    ],
    "tags": [("incense", "object_type")],
}
