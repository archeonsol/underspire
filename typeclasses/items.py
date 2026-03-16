# D:\moo\mootest\typeclasses\items.py
"""
Non-combat items (containers, keys, tools, etc.).
For combat weapons, use typeclasses.weapons.CombatWeapon instead.
"""
from evennia import DefaultObject
import re


class Item(DefaultObject):
    """
    Generic non-combat item. Use for keys, containers, quest objects, etc.
    """
    def at_object_creation(self):
        pass

    def get_display_name(self, looker, **kwargs):
        """
        Override default to hide the dbref (#id) when looking at items.

        Evennia's default often returns 'name(#id)' with color codes; we strip the '(#id)'
        suffix so players just see the item name.
        """
        base = super().get_display_name(looker, **kwargs)
        # Strip a trailing '(#number)' (with or without color codes before it).
        return re.sub(r"\(#\d+\)$", "", str(base))
