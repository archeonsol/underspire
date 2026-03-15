"""
Splinter pod: soul-shard backup for clone resurrection.
Enter the pod, run 'splinter me', then 'done' to leave.
Uses DefaultRoom for the interior so the room never adds cmdsets (character commands always apply).
"""
from evennia import DefaultRoom, DefaultObject
from evennia.utils.create import create_object


# Interior: brutal, esoteric, not-a-place
INTERIOR_DESC = (
    "This is |rnot a room|n. It is the |xinside of something that eats|n. "
    "Rusted ribs curve over you. |RNodes|n pulse in no rhythm that has a name. "
    "The walls are |xcables and glass|n — something between pipe and |rvein|n. "
    "A single couch: straps, buckles, a |Rcrown of needles|n where your head goes. "
    "The air tastes of |xozone and copper|n. Something |rhums|n in your teeth.\n\n"
    "When you are ready, say |wsplinter me|n. There is no going back whole."
)

# Exterior
POD_DESC = (
    "A heavy capsule of dull metal and |Rfiligree|n. Cold. Something inside |rhums|n. "
    "You can |wenter pod|n."
)


class SplinterPodInterior(DefaultRoom):
    """
    Interior of a splinter pod. Plain DefaultRoom so it never adds cmdsets;
    character's 'done' always works. We clear any persisted cmdset
    so old DB state cannot override the character set.
    """
    def at_object_creation(self):
        self.db.desc = INTERIOR_DESC

    def at_init(self):
        # Ensure this room never contributes a replacing cmdset (fix old pod interiors).
        # Use list form so handler loads empty default; clear in-memory stack.
        self.cmdset_storage = [""]
        self.cmdset.remove_default()
        # Keep desc in sync with current INTERIOR_DESC (e.g. after "To leave" text changes).
        self.db.desc = INTERIOR_DESC

    def get_extra_display_name_info(self, looker=None, **kwargs):
        return ""


class SplinterPod(DefaultObject):
    """Splinter pod: enter to reach interior, splinter me, then done to leave."""
    def at_object_creation(self):
        self.db.desc = POD_DESC
        interior = create_object(
            "typeclasses.splinter_pod.SplinterPodInterior",
            key="Splinter Pod Interior",
            location=None,
        )
        if interior:
            self.db.interior = interior
            interior.db.pod = self
