DRINK_WATER_FLASK = {
    "prototype_key": "DRINK_WATER_FLASK",
    "prototype_tags": ["survival", "drink"],
    "key": "flask of water",
    "typeclass": "typeclasses.items.Item",
    "attrs": [
        ("drinkable", True),
        ("thirst_restore", 30),
        (
            "desc",
            "A beaten metal flask sloshing with clean water. The sides are cold with condensation.",
        ),
    ],
}

DRINK_RECYCLED_WATER = {
    "prototype_key": "DRINK_RECYCLED_WATER",
    "prototype_tags": ["survival", "drink"],
    "key": "recycled water pouch",
    "typeclass": "typeclasses.items.Item",
    "attrs": [
        ("drinkable", True),
        ("thirst_restore", 20),
        (
            "desc",
            "A soft plastic pouch stamped with filtration warnings. The water inside tastes faintly of metal and bleach.",
        ),
    ],
}

DRINK_ELECTROLYTE = {
    "prototype_key": "DRINK_ELECTROLYTE",
    "prototype_tags": ["survival", "drink"],
    "key": "electrolyte drink",
    "typeclass": "typeclasses.items.Item",
    "attrs": [
        ("drinkable", True),
        ("thirst_restore", 25),
        (
            "desc",
            "A bright-colored electrolyte drink that smells of artificial citrus and salt.",
        ),
    ],
}

DRINK_HERBAL_TEA = {
    "prototype_key": "DRINK_HERBAL_TEA",
    "prototype_tags": ["survival", "drink"],
    "key": "cup of herbal tea",
    "typeclass": "typeclasses.items.Item",
    "attrs": [
        ("drinkable", True),
        ("thirst_restore", 22),
        (
            "desc",
            "A steaming cup of bitter herbal tea, the surface sheened with oils from crushed leaves.",
        ),
    ],
}

DRINK_SOUP_BROTH = {
    "prototype_key": "DRINK_SOUP_BROTH",
    "prototype_tags": ["survival", "drink"],
    "key": "cup of broth",
    "typeclass": "typeclasses.items.Item",
    "attrs": [
        ("drinkable", True),
        ("thirst_restore", 18),
        ("edible", True),
        ("hunger_restore", 8),
        (
            "desc",
            "A thin, salty broth in a chipped mug. It warms your hands and puts a little weight in your gut.",
        ),
    ],
}
