"""
Prototypes

A prototype is a simple way to create individualized instances of a
given typeclass. It is dictionary with specific key names.

For example, you might have a Sword typeclass that implements everything a
Sword would need to do. The only difference between different individual Swords
would be their key, description and some Attributes. The Prototype system
allows to create a range of such Swords with only minor variations. Prototypes
can also inherit and combine together to form entire hierarchies (such as
giving all Sabres and all Broadswords some common properties). Note that bigger
variations, such as custom commands or functionality belong in a hierarchy of
typeclasses instead.

A prototype can either be a dictionary placed into a global variable in a
python module (a 'module-prototype') or stored in the database as a dict on a
special Script (a db-prototype). The former can be created just by adding dicts
to modules Evennia looks at for prototypes, the latter is easiest created
in-game via the `olc` command/menu.

Prototypes are read and used to create new objects with the `spawn` command
or directly via `evennia.spawn` or the full path `evennia.prototypes.spawner.spawn`.

A prototype dictionary have the following keywords:

Possible keywords are:
- `prototype_key` - the name of the prototype. This is required for db-prototypes,
  for module-prototypes, the global variable name of the dict is used instead
- `prototype_parent` - string pointing to parent prototype if any. Prototype inherits
  in a similar way as classes, with children overriding values in their parents.
- `key` - string, the main object identifier.
- `typeclass` - string, if not set, will use `settings.BASE_OBJECT_TYPECLASS`.
- `location` - this should be a valid object or #dbref.
- `home` - valid object or #dbref.
- `destination` - only valid for exits (object or #dbref).
- `permissions` - string or list of permission strings.
- `locks` - a lock-string to use for the spawned object.
- `aliases` - string or list of strings.
- `attrs` - Attributes, expressed as a list of tuples on the form `(attrname, value)`,
  `(attrname, value, category)`, or `(attrname, value, category, locks)`. If using one
   of the shorter forms, defaults are used for the rest.
- `tags` - Tags, as a list of tuples `(tag,)`, `(tag, category)` or `(tag, category, data)`.
-  Any other keywords are interpreted as Attributes with no category or lock.
   These will internally be added to `attrs` (equivalent to `(attrname, value)`.

See the `spawn` command and `evennia.prototypes.spawner.spawn` for more info.

"""

## example of module-based prototypes using
## the variable name as `prototype_key` and
## simple Attributes

# from random import randint
#
# GOBLIN = {
# "key": "goblin grunt",
# "health": lambda: randint(20,30),
# "resists": ["cold", "poison"],
# "attacks": ["fists"],
# "weaknesses": ["fire", "light"],
# "tags": = [("greenskin", "monster"), ("humanoid", "monster")]
# }
#
# GOBLIN_WIZARD = {
# "prototype_parent": "GOBLIN",
# "key": "goblin wizard",
# "spells": ["fire ball", "lighting bolt"]
# }
#
# GOBLIN_ARCHER = {
# "prototype_parent": "GOBLIN",
# "key": "goblin archer",
# "attacks": ["short bow"]
# }
#
# This is an example of a prototype without a prototype
# (nor key) of its own, so it should normally only be
# used as a mix-in, as in the example of the goblin
# archwizard below.
# ARCHWIZARD_MIXIN = {
# "attacks": ["archwizard staff"],
# "spells": ["greater fire ball", "greater lighting"]
# }
#
# GOBLIN_ARCHWIZARD = {
# "key": "goblin archwizard",
# "prototype_parent" : ("GOBLIN_WIZARD", "ARCHWIZARD_MIXIN")
# }


# Tailoring: bolts of material. Higher materials require more tailoring skill (see world.rpg.tailoring.BOLT_MATERIALS).
# Spawn with: spawn bolt of cloth | spawn bolt of silk | spawn bolt of satin | spawn bolt of velvet
BOLT_OF_CLOTH = {
    "key": "bolt of cloth",
    "typeclass": "typeclasses.bolt_of_cloth.BoltOfCloth",
    "attrs": [("material_type", "cloth")],
}

BOLT_OF_SILK = {
    "prototype_parent": "BOLT_OF_CLOTH",
    "key": "bolt of silk",
    "attrs": [("material_type", "silk")],
}

BOLT_OF_SATIN = {
    "prototype_parent": "BOLT_OF_CLOTH",
    "key": "bolt of satin",
    "attrs": [("material_type", "satin")],
}

BOLT_OF_VELVET = {
    "prototype_parent": "BOLT_OF_CLOTH",
    "key": "bolt of velvet",
    "attrs": [("material_type", "velvet")],
}


# ---------------------------------------------------------------------------
# Survival templates: food, drink, and alcohol
# Spawn with: spawnitem <prototype_key> (e.g. spawnitem FOOD_RATION_BRICK)
# ---------------------------------------------------------------------------

# Food items (edible, restore hunger; some nutritious for stamina regen buff)

FOOD_RATION_BRICK = {
    "prototype_key": "FOOD_RATION_BRICK",
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


# Non-alcoholic drinks (restore thirst; no alcohol_strength)

DRINK_WATER_FLASK = {
    "prototype_key": "DRINK_WATER_FLASK",
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


# Alcoholic drinks (no thirst restore; contribute alcohol_strength instead)

ALCO_BEER = {
    "prototype_key": "ALCO_BEER",
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


# ---------------------------------------------------------------------------
# Performance: instruments for composed performances (performance play ... with guitar)
# Spawn with: spawnitem GUITAR_WASTES
# ---------------------------------------------------------------------------

GUITAR_WASTES = {
    "prototype_key": "GUITAR_WASTES",
    "key": "wastes guitar",
    "typeclass": "typeclasses.items.Item",
    "tags": [("guitar", "performance_instrument")],
    "attrs": [
        (
            "desc",
            "A six-string put together from salvage: rust-scabbed body, re-purposed wiring for frets, "
            "and a neck that has seen more knocks than tunes. It still holds its pitch. In the right hands "
            "it can make the tunnels echo.",
        ),
    ],
}
