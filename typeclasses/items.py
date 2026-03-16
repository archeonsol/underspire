# D:\moo\mootest\typeclasses\items.py
"""
Non-combat items (containers, keys, tools, etc.).
For combat weapons, use typeclasses.weapons.CombatWeapon instead.
"""
from evennia import DefaultObject


class Item(DefaultObject):
    """
    Generic non-combat item. Use for keys, containers, quest objects, etc.
    """
    def at_object_creation(self):
        pass


# Re-export matrix item types for convenience
from .matrix.items import MatrixItem
