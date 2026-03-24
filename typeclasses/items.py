# D:\moo\mootest\typeclasses\items.py
"""
Non-combat items (containers, keys, tools, etc.).
For combat weapons, use typeclasses.weapons.CombatWeapon instead.
"""
from typeclasses.objects import Object
import re


class Item(Object):
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

    def _portion_narrative(self):
        """
        Narrative-only remaining-portion text for prepared food/drink items.
        Returns empty string for non-prepared items.
        """
        total = int(getattr(self.db, "portions_total", 0) or 0)
        left = int(getattr(self.db, "uses_remaining", 0) or 0)
        if total <= 0:
            return ""

        is_drink = bool(
            (getattr(self, "tags", None) and self.tags.has("drink"))
            or bool(getattr(self.db, "drinkable", False))
        )

        if left >= total:
            return "This drink hasn't been touched yet." if is_drink else "This has never been touched."

        ratio = left / float(total) if total else 0.0
        if left <= 1:
            return "Only a swallow remains." if is_drink else "Only a few bites remain."
        if ratio <= 0.25:
            return "There's just a little left in the glass." if is_drink else "There's just a little left."
        if ratio <= 0.50:
            return "There's about half left in the glass." if is_drink else "There's about half of it remaining."
        if ratio < 1.0:
            return "It's been sipped, but most of it remains." if is_drink else "This has been partially eaten."
        return ""

    def get_display_desc(self, looker, **kwargs):
        """
        Append narrative remaining-portion state for prepared station consumables.
        """
        base = super().get_display_desc(looker, **kwargs) or ""
        portion_line = self._portion_narrative()
        if not portion_line:
            return base
        if base.strip():
            return f"{base.rstrip()}\n{portion_line}"
        return portion_line
