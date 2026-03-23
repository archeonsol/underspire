"""Installable vehicle part items (swap / vendor loot)."""

from typeclasses.objects import Object


class VehiclePart(Object):
    """A vehicle part that can be installed via swap."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.fits_part_slot = getattr(self.db, "fits_part_slot", None) or ""
        self.db.part_type_id = getattr(self.db, "part_type_id", None) or ""
        self.db.part_condition = int(getattr(self.db, "part_condition", None) or 100)
        self.db.fits_vehicle_type = getattr(self.db, "fits_vehicle_type", None) or ""
