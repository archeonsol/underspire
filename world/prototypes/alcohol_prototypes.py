ALCO_BEER = {
    "prototype_key": "ALCO_BEER",
    "prototype_tags": ["survival", "alcohol"],
    "key": "bottle of beer",
    "typeclass": "typeclasses.items.Item",
    "attrs": [
        ("drinkable", True),
        ("thirst_restore", 0),
        ("alcohol_strength", 6.0),
        (
            "desc",
            "A brown glass bottle filled with flat, tunnel-brewed beer. Bitter, sour, and deceptively strong.",
        ),
    ],
}

ALCO_SPIRITS = {
    "prototype_key": "ALCO_SPIRITS",
    "prototype_tags": ["survival", "alcohol"],
    "key": "flask of spirits",
    "typeclass": "typeclasses.items.Item",
    "attrs": [
        ("drinkable", True),
        ("thirst_restore", 0),
        ("alcohol_strength", 12.0),
        (
            "desc",
            "A small metal flask that smells sharply of distilled grain and industrial alcohol.",
        ),
    ],
}

ALCO_MOONSHINE = {
    "prototype_key": "ALCO_MOONSHINE",
    "prototype_tags": ["survival", "alcohol"],
    "key": "jar of moonshine",
    "typeclass": "typeclasses.items.Item",
    "attrs": [
        ("drinkable", True),
        ("thirst_restore", 0),
        ("alcohol_strength", 18.0),
        (
            "desc",
            "A cloudy jar of bootleg shine. The fumes alone make your eyes water; this will hit hard and fast.",
        ),
    ],
}

ALCO_MUTAGENIC_BREW = {
    "prototype_key": "ALCO_MUTAGENIC_BREW",
    "prototype_tags": ["survival", "alcohol"],
    "key": "mutagenic brew",
    "typeclass": "typeclasses.items.Item",
    "attrs": [
        ("drinkable", True),
        ("thirst_restore", 0),
        ("alcohol_strength", 25.0),
        (
            "desc",
            "A viscous, faintly luminescent liquor in a sealed vial. It smells of mushrooms, ozone, and bad ideas.",
        ),
    ],
}
