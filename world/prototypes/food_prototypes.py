FOOD_RATION_BRICK = {
    "prototype_key": "FOOD_RATION_BRICK",
    "prototype_tags": ["survival", "food"],
    "key": "ration brick",
    "typeclass": "typeclasses.items.Item",
    "attrs": [
        ("edible", True),
        ("hunger_restore", 25),
        ("is_nutritious", True),
        ("taste_msg", "You chew through dry, flavorless calories that cling to your teeth."),
        (
            "desc",
            "A dense brick of compressed calories: bland, chewy, and designed to keep you moving rather than happy.",
        ),
    ],
}

FOOD_DRY_MEAT = {
    "prototype_key": "FOOD_DRY_MEAT",
    "prototype_tags": ["survival", "food"],
    "key": "strip of dried meat",
    "typeclass": "typeclasses.items.Item",
    "attrs": [
        ("edible", True),
        ("hunger_restore", 20),
        ("is_nutritious", True),
        ("taste_msg", "Salt and smoke flood your mouth as the tough meat fights every bite."),
        (
            "desc",
            "Tough, salty meat dried hard against spoilage. It tugs at your teeth but sits heavy in your stomach.",
        ),
    ],
}

FOOD_CANNED_STEW = {
    "prototype_key": "FOOD_CANNED_STEW",
    "prototype_tags": ["survival", "food"],
    "key": "can of stew",
    "typeclass": "typeclasses.items.Item",
    "attrs": [
        ("edible", True),
        ("hunger_restore", 35),
        ("is_nutritious", True),
        ("taste_msg", "Grease and peppery broth spread warmth through your mouth and throat."),
        (
            "desc",
            "A battered tin of thick stew. The label is half-gone, but the smell promises fat, salt, and warmth.",
        ),
    ],
}

FOOD_MOLDY_BREAD = {
    "prototype_key": "FOOD_MOLDY_BREAD",
    "prototype_tags": ["survival", "food"],
    "key": "moldy ration loaf",
    "typeclass": "typeclasses.items.Item",
    "attrs": [
        ("edible", True),
        ("hunger_restore", 10),
        ("is_nutritious", False),
        ("taste_msg", "You taste mold and damp rot on your tongue."),
        (
            "desc",
            "A stale loaf speckled with grey-green mold. It'll quiet your stomach, but it's far from ideal.",
        ),
    ],
}

FOOD_NUT_BAR = {
    "prototype_key": "FOOD_NUT_BAR",
    "prototype_tags": ["survival", "food"],
    "key": "protein nut bar",
    "typeclass": "typeclasses.items.Item",
    "attrs": [
        ("edible", True),
        ("hunger_restore", 18),
        ("is_nutritious", True),
        ("taste_msg", "Sugary oil and crushed nuts coat your teeth in a sticky film."),
        (
            "desc",
            "A compact bar of pressed nuts, seeds, and synthetic binders. Sweet, oily, and surprisingly dense.",
        ),
    ],
}
