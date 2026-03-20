"""
Armor prototypes generated from world.armor_levels.ARMOR_TEMPLATES.

Spawning sets db.armor_template so Armor.at_object_creation applies the same stats as
create_armor_from_template (via _apply_armor_template_defaults).
"""
from world.armor_levels import ARMOR_TEMPLATES

PROTOTYPE_LIST = []
for _t in ARMOR_TEMPLATES:
    tk = _t["key"]
    PROTOTYPE_LIST.append(
        {
            "prototype_key": tk.upper(),
            "prototype_tags": ["combat", "armor"],
            "key": _t["name"],
            "typeclass": "typeclasses.armor.Armor",
            "attrs": [
                ("armor_template", tk),
                ("quality", 100),
            ],
        }
    )
