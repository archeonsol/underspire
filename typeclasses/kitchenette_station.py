"""
Kitchenette station typeclass.

A private kitchen. Serves food and non-alcoholic drinks.
No register, no payment. Ownership tied to apartment rental.

Attributes:
    db.station_type     str   "kitchenette"
    db.social_tier      str   tier based on apartment level
    db.owner_id         int   dbref of the owner (auto-set from rent tenant)
    db.recipes          list  recipe dicts
    db.station_name     str   "kitchenette"
    db.linked_door_id   int   dbref of the rentable door that controls ownership
"""

from evennia.objects.objects import DefaultObject


class KitchenetteStation(DefaultObject):
    """
    A private kitchen counter.

    Serves food and non-alcoholic drinks only. Alcohol is not permitted.
    Ownership is auto-assigned when the apartment is rented, and cleared
    when the tenant vacates.

    If db.linked_door_id is set, ownership follows whoever currently holds
    the rental on that door — no manual sync needed.

    Set up by builders:
        @create kitchenette:typeclasses.kitchenette_station.KitchenetteStation
        @set kitchenette/social_tier = guild
        @set kitchenette/linked_door_id = <dbref of the rentable exit>
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.station_type = "kitchenette"
        self.db.social_tier = "slum"
        self.db.owner_id = None
        self.db.recipes = []
        self.db.station_name = "kitchenette"
        self.db.linked_door_id = None
        self.db.room_pose = "is stocked and ready"
        self.locks.add("get:perm(Builder) or perm(Admin);drop:perm(Builder) or perm(Admin);give:false()")

    def at_pre_get(self, getter, **kwargs):
        """Kitchenettes are fixed fixtures and cannot be picked up."""
        try:
            if getter and (getter.check_permstring("Builder") or getter.check_permstring("Admin")):
                return True
        except Exception:
            pass
        if getter:
            getter.msg("That fixture is bolted in place.")
        return False

    def at_pre_move(self, destination, **kwargs):
        """
        Prevent normal in-world movement of kitchenette fixtures.
        Allow explicit builder/admin repositioning if needed.
        """
        if kwargs.get("move_type") == "teleport":
            return True
        mover = kwargs.get("caller") or kwargs.get("mover")
        if mover and (mover.check_permstring("Builder") or mover.check_permstring("Admin")):
            return True
        return False

    def get_room_appearance(self, looker, **kwargs):
        """
        Return the one-line room look entry for this fixture.
        Builders can customize with @set kitchenette/room_pose = <text>.
        """
        from typeclasses.rooms import ROOM_DESC_OBJECT_NAME_COLOR
        name = self.get_display_name(looker, **kwargs)
        pose = (getattr(self.db, "room_pose", None) or "is stocked and ready").strip().rstrip(".")
        return f"The {ROOM_DESC_OBJECT_NAME_COLOR}{name}|n {pose}."

    def get_owner_id(self) -> int | None:
        """
        Return the current owner's character id.
        Checks the linked door's tenant first, then falls back to db.owner_id.
        """
        from world.food.stations import get_kitchenette_owner_id
        return get_kitchenette_owner_id(self)
