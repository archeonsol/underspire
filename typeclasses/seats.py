"""
Seating and lying-down objects: chairs, couches, beds, etc.
Characters use 'sit' / 'stand' and 'lie on' / 'get up'; room shows "X is sitting on Y" / "X is lying on Y".
Template typeclasses for customization (desc, key, etc.).
"""
from evennia.objects.objects import DefaultObject


class Seat(DefaultObject):
    """
    Template for sit-on objects: chair, couch, bench, etc.
    One sitter at a time; character.db.sitting_on = this object.
    Room shows "X is sitting on <key>". Grapple pulls them off and auto-succeeds.
    """
    def at_object_creation(self):
        super().at_object_creation()
        # Seats are moveable furniture (no get lock)

    def get_display_name(self, looker):
        return getattr(self.db, "desc", None) or self.key or "a seat"

    def get_sitter(self):
        """Return the character sitting here (db.sitting_on == self), or None."""
        loc = self.location
        if not loc:
            return None
        for char in loc.contents_get(content_type="character"):
            if getattr(char.db, "sitting_on", None) == self:
                return char
        return None


class Bed(DefaultObject):
    """
    Template for lie-on objects: bed, cot, sofa, etc.
    One occupant at a time; character.db.lying_on = this object.
    Room shows "X is lying on <key>". Grapple pulls them off and auto-succeeds.
    """
    def at_object_creation(self):
        super().at_object_creation()
        # Beds are moveable furniture (no get lock)

    def get_display_name(self, looker):
        return getattr(self.db, "desc", None) or self.key or "a bed"

    def get_occupant(self):
        """Return the character lying here (db.lying_on == self), or None."""
        loc = self.location
        if not loc:
            return None
        for char in loc.contents_get(content_type="character"):
            if getattr(char.db, "lying_on", None) == self:
                return char
        return None
