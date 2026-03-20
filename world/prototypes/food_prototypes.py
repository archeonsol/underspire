FOOD_RATION_BRICK = {
    "prototype_key": "FOOD_RATION_BRICK",
    "prototype_tags": ["survival", "food"],
    "key": "ration brick",
    "typeclass": "typeclasses.items.Item",
    "attrs": [
        ("edible", True),
        ("hunger_restore", 25),
        ("is_nutritious", True),
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
        (
            "desc",
            "A compact bar of pressed nuts, seeds, and synthetic binders. Sweet, oily, and surprisingly dense.",
        ),
    ],
}
