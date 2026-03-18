"""
Ammunition typeclasses. Each ammo type is for one firearm class (sidearm, longarm, automatic).
Weapons are loaded via the reload command by matching db.ammo_type. Quantity stacks up to max_stack.
"""
from typeclasses.objects import Object
from world.ammo import (
    AMMO_TYPES,
    AMMO_TYPE_SIDEARM,
    AMMO_TYPE_LONGARM,
    AMMO_TYPE_AUTOMATIC,
    AMMO_TYPE_DISPLAY_NAMES,
)


# Max rounds per stack (expand later with weight, caliber, etc.)
DEFAULT_MAX_STACK = 50


class Ammo(Object):
    """
    Base ammunition. Set db.ammo_type to one of world.ammo.AMMO_TYPES.
    db.quantity = rounds in this stack; db.max_stack = stack size cap.
    Subclasses set ammo_type so builders can create "pistol rounds", "rifle rounds", etc.
    """
    def at_object_creation(self):
        self.db.ammo_type = AMMO_TYPE_SIDEARM
        self.db.quantity = 0
        self.db.max_stack = DEFAULT_MAX_STACK

    def get_display_name(self, looker, **kwargs):
        name = super().get_display_name(looker, **kwargs)
        qty = int(self.db.quantity or 0)
        if qty > 0:
            return f"{name} ({qty} rounds)"
        return name


class PistolAmmo(Ammo):
    """Pistol / sidearm ammunition. Use with sidearms."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.ammo_type = AMMO_TYPE_SIDEARM
        self.db.quantity = self.db.quantity or 12
        if not self.db.desc:
            self.db.desc = "A stack of pistol rounds for sidearms."


class RifleAmmo(Ammo):
    """Rifle / longarm ammunition. Use with rifles and shotguns."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.ammo_type = AMMO_TYPE_LONGARM
        self.db.quantity = self.db.quantity or 5
        if not self.db.desc:
            self.db.desc = "A stack of rifle rounds for longarms."


class AutomaticAmmo(Ammo):
    """Automatic weapon ammunition. Use with SMGs, assault rifles, LMGs."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.ammo_type = AMMO_TYPE_AUTOMATIC
        self.db.quantity = self.db.quantity or 30
        if not self.db.desc:
            self.db.desc = "A stack of rounds for automatic weapons."
