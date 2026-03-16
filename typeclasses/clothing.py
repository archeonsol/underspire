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
    - db.quality_adjective: from tailoring finalize; shown on look ("This garment seems to be X.").
    """
    def at_object_creation(self):
        super().at_object_creation()
        self.db.covered_parts = []
        if self.db.desc is None:
            self.db.desc = ""
        self.db.worn_desc = ""
        self.db.tease_message = ""
        # Quality from tailoring finalize roll: adjective (e.g. "fancy") and score (0-100) for outfit averaging
        if not hasattr(self.db, "quality_adjective"):
            self.db.quality_adjective = ""
        if not hasattr(self.db, "quality_score"):
            self.db.quality_score = None
        # Tailored clothing layering (0-5); default 1 unless tailoring sets otherwise.
        if not hasattr(self.db, "clothing_layer"):
            self.db.clothing_layer = 1
        # See-through clothing (jewelry, mesh, etc.): when True, does not replace body-part text.
        if not hasattr(self.db, "see_thru"):
            self.db.see_thru = False

    def get_display_desc(self, looker, **kwargs):
        """Main description plus quality line when set (from tailoring finalize)."""
        base = super().get_display_desc(looker, **kwargs) or ""
        adj = getattr(self.db, "quality_adjective", None) or ""
        if adj.strip():
            base = (base.rstrip() + "\n\nThis garment seems to be %s." % adj.strip()).strip()
        return base or ""

    def at_drop(self, dropper):
        """When dropped, stop counting as worn."""
        try:
            worn = dropper.db.worn or []
            if self in worn:
                dropper.db.worn = [o for o in worn if o != self]
        except Exception:
            pass

    def at_give(self, giver, receiver):
        """
        When given to someone else, require that it is not worn.

        If the giver is still wearing this item, cancel the transfer and keep it
        in the giver's inventory so state stays consistent.
        """
        try:
            worn = giver.db.worn or []
            if self in worn:
                # Move back to giver if Evennia already moved it.
                if self.location is not giver:
                    self.location = giver
                giver.msg(f"You must |wremove|n {self.get_display_name(giver)} before you can give it to someone.")
                if receiver and hasattr(receiver, "msg"):
                    receiver.msg(f"{giver.get_display_name(receiver)} is still wearing {self.get_display_name(receiver)} and cannot give it yet.")
        except Exception:
            # If anything goes wrong, better to leave the item with the giver than to allow a half-worn state.
            try:
                if self.location is not giver:
                    self.location = giver
            except Exception:
                pass
