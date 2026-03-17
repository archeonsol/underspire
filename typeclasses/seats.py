"""
Seating and lying-down objects: chairs, couches, beds, etc.
Characters use 'sit' / 'stand' and 'lie on' / 'get up'; room shows "X is sitting on Y" / "X is lying on Y".
Template typeclasses for customization (desc, key, etc.).
"""
from evennia.objects.objects import DefaultObject


class Seat(DefaultObject):
    """
    Template for sit-on objects: chair, couch, bench, etc.
    Multiple people can sit (capacity); character.db.sitting_on = this object.
    Room shows "X is sitting on <key>". Grapple pulls them off and auto-succeeds.

    Attributes:
        capacity (int): How many people can sit at once (default 1)
        room_pose (str): How this appears in room look (e.g. "here" for "A chair is here.")
        seating_empty_msg (str): Template for empty seat display
        seating_occupied_msg (str): Template for occupied seat display
    """
    def at_object_creation(self):
        super().at_object_creation()
        # Seats are moveable furniture (no get lock)
        self.db.capacity = 1  # chairs = 1, couches/benches = 2-4
        self.db.room_pose = "here"  # Shows as "A chair is here."

        # Default room-look templates; builders can override these per-object:
        #   self.db.seating_empty_msg = "The {obj} is empty."
        #   self.db.seating_occupied_msg = "{name} is sitting on the {obj}."
        if getattr(self.db, "seating_empty_msg", None) is None:
            self.db.seating_empty_msg = "The {obj} is empty."
        if getattr(self.db, "seating_occupied_msg", None) is None:
            self.db.seating_occupied_msg = "{name} is sitting on the {obj}."

    def get_display_name(self, looker, **kwargs):
        """Return custom name or key."""
        return self.key or "a seat"

    def get_sitters(self):
        """Return list of characters sitting here (db.sitting_on == self)."""
        loc = self.location
        if not loc:
            return []
        sitters = []
        for char in loc.contents_get(content_type="character"):
            if getattr(char.db, "sitting_on", None) == self:
                sitters.append(char)
        return sitters

    def get_sitter(self):
        """Return first character sitting here, or None. For backwards compatibility."""
        sitters = self.get_sitters()
        return sitters[0] if sitters else None

    def get_occupants(self):
        """Return all people using this seat (sitting). Override in subclasses for other uses."""
        return self.get_sitters()

    def get_used_capacity(self):
        """Calculate how many capacity slots are currently used (sitting = 1 slot each)."""
        return len(self.get_sitters())

    def has_room(self, posture="sitting"):
        """
        Check if there's room for another person.

        Args:
            posture (str): "sitting" (1 slot) or "lying" (3 slots)

        Returns:
            bool: True if there's room
        """
        capacity = self.db.capacity or 1
        used = self.get_used_capacity()
        slots_needed = 3 if posture == "lying" else 1
        return (used + slots_needed) <= capacity

    def get_empty_template(self):
        """
        Return the format template for an empty seat.
        Placeholders:
          {obj}  – the seat's display name for the viewer
          {name} – unused for empty, but available for consistency
        """
        return getattr(self.db, "seating_empty_msg", None) or "The {obj} is empty."

    def get_occupied_template(self):
        """
        Return the format template for an occupied seat.
        Placeholders:
          {name} – seated character's display name
          {obj}  – the seat's display name for the viewer
        """
        return getattr(self.db, "seating_occupied_msg", None) or "{name} is sitting on the {obj}."


class Bed(Seat):
    """
    Template for lie-on AND sit-on objects: bed, cot, sofa, etc.
    Inherits sitting from Seat, adds lying functionality.
    Can be sat on OR lain on; character.db.sitting_on or db.lying_on = this object.
    Room shows "X is sitting/lying on <key>". Grapple pulls them off and auto-succeeds.

    Lying provides faster stamina recovery than sitting.

    Attributes:
        capacity (int): How many people can use at once (default 1 for single bed, 2+ for larger)
        room_pose (str): How this appears in room look (e.g. "against the wall")
        seating_empty_msg (str): Template for empty bed display
        sitting_template (str): Template when someone is sitting on bed
        lying_template (str): Template when someone is lying on bed
    """
    def at_object_creation(self):
        super().at_object_creation()
        self.db.room_pose = "against the wall"  # Override default seat pose

        # Default templates for beds
        if getattr(self.db, "seating_empty_msg", None) is None:
            self.db.seating_empty_msg = "The {obj} is empty."
        if getattr(self.db, "sitting_template", None) is None:
            self.db.sitting_template = "{name} is sitting on the {obj}."
        if getattr(self.db, "lying_template", None) is None:
            self.db.lying_template = "{name} is lying on the {obj}."

    def get_display_name(self, looker, **kwargs):
        """Return custom name or key."""
        return self.key or "a bed"

    def get_occupants(self):
        """Return list of characters using this bed (sitting OR lying)."""
        loc = self.location
        if not loc:
            return []
        occupants = []
        for char in loc.contents_get(content_type="character"):
            if getattr(char.db, "sitting_on", None) == self:
                occupants.append(char)
            elif getattr(char.db, "lying_on", None) == self:
                occupants.append(char)
        return occupants

    def get_used_capacity(self):
        """Calculate how many capacity slots are currently used (sitting = 1, lying = 3)."""
        loc = self.location
        if not loc:
            return 0
        used = 0
        for char in loc.contents_get(content_type="character"):
            if getattr(char.db, "lying_on", None) == self:
                used += 3  # lying takes 3 slots
            elif getattr(char.db, "sitting_on", None) == self:
                used += 1  # sitting takes 1 slot
        return used

    def get_occupant(self):
        """Return first occupant, or None. For backwards compatibility."""
        occupants = self.get_occupants()
        return occupants[0] if occupants else None

    def get_template_for_posture(self, posture):
        """
        Get the appropriate template for the given posture.

        Args:
            posture (str): "sitting" or "lying"

        Returns:
            str: Template string with {name} and {obj} placeholders
        """
        if posture == "lying":
            return getattr(self.db, "lying_template", None) or "{name} is lying on the {obj}."
        else:
            return getattr(self.db, "sitting_template", None) or "{name} is sitting on the {obj}."
