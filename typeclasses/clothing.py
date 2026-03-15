"""
Clothing typeclass: wearable items that cover specific body parts.
Set covered_parts to a list of keys from world.medical.BODY_PARTS.
When worn, the item's description replaces those body parts in the character's look.
"""
from typeclasses.items import Item
from world.medical import BODY_PARTS


class Clothing(Item):
    """
    Wearable clothing. Covers the body parts listed in db.covered_parts.
    - db.desc: main description (when you look at the item in room/inventory).
    - db.worn_desc: description that replaces covered body parts when someone looks at the wearer.
      If unset, body-part text falls back to db.desc. Supports $N, $P, $S for wearer.
    """
    def at_object_creation(self):
        super().at_object_creation()
        self.db.covered_parts = []
        if self.db.desc is None:
            self.db.desc = ""
        # Worn description (replaces body parts on look). If empty, main desc is used.
        self.db.worn_desc = ""
        self.db.tease_message = ""

    def at_drop(self, dropper):
        """When dropped, stop counting as worn."""
        try:
            worn = dropper.db.worn or []
            if self in worn:
                dropper.db.worn = [o for o in worn if o != self]
        except Exception:
            pass
