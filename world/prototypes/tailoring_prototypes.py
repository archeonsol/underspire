# Tailoring: bolts of material (world.rpg.tailoring.BOLT_MATERIALS).

BOLT_OF_CLOTH = {
    "prototype_tags": ["tailoring"],
    "key": "bolt of cloth",
    "typeclass": "typeclasses.bolt_of_cloth.BoltOfCloth",
    "attrs": [("material_type", "cloth")],
}

BOLT_OF_SILK = {
    "prototype_parent": "BOLT_OF_CLOTH",
    "prototype_tags": ["tailoring"],
    "key": "bolt of silk",
    "attrs": [("material_type", "silk")],
}

BOLT_OF_SATIN = {
    "prototype_parent": "BOLT_OF_CLOTH",
    "prototype_tags": ["tailoring"],
    "key": "bolt of satin",
    "attrs": [("material_type", "satin")],
}

BOLT_OF_VELVET = {
    "prototype_parent": "BOLT_OF_CLOTH",
    "prototype_tags": ["tailoring"],
    "key": "bolt of velvet",
    "attrs": [("material_type", "velvet")],
}
