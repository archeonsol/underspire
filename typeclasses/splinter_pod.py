"""
Splinter pod: soul-shard backup for clone resurrection.
Enter the pod, run 'splinter me', then 'done' to leave.
Uses DefaultRoom for the interior so the room never adds cmdsets (character commands always apply).

Each pod has exactly ONE persistent interior (same instance every time). Items dropped inside
persist when leaving and re-entering. A second pod on the grid has its own separate interior.
Only one character may be inside a given pod at a time.
"""
from evennia import DefaultRoom, DefaultObject
from evennia.utils.create import create_object
from evennia.utils.search import search_tag

# Tag used to find an interior by pod id (category = str(pod.id)).
SPLINTER_POD_INTERIOR_TAG = "splinter_pod_interior"


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
    Interior of a splinter pod. One instance per pod (tag + category = pod id).
    Plain DefaultRoom so it never adds cmdsets; character's 'done' always works.
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
    """
    Splinter pod: enter to reach this pod's interior, splinter me, then done to leave.
    Each pod has one persistent interior (like a vehicle); one character at a time per pod.
    """
    def at_object_creation(self):
        self.db.desc = POD_DESC
        self.db.interior = None  # set in _ensure_interior
        # Pods are fixtures: cannot be picked up and do not support @sp for non-builders.
        self.db.immovable = True
        self.db.allow_setplace = False

    def _ensure_interior(self):
        """Return this pod's single persistent interior. Creates once per pod; never duplicates."""
        interior = self.db.interior
        if interior:
            try:
                if not interior.tags.has(SPLINTER_POD_INTERIOR_TAG, category=str(self.id)):
                    interior.tags.add(SPLINTER_POD_INTERIOR_TAG, category=str(self.id))
            except Exception:
                pass
            return interior
        try:
            found = search_tag(SPLINTER_POD_INTERIOR_TAG, category=str(self.id))
            if found:
                candidate = found[0]
                if getattr(candidate.db, "pod", None) is self or getattr(candidate.db, "pod", None) == self:
                    self.db.interior = candidate
                    return candidate
                if getattr(candidate.db, "pod", None) is None:
                    candidate.db.pod = self
                    self.db.interior = candidate
                    return candidate
        except Exception:
            pass
        interior = create_object(
            "typeclasses.splinter_pod.SplinterPodInterior",
            key="Splinter Pod Interior",
            location=None,
        )
        if interior:
            interior.db.pod = self
            interior.tags.add(SPLINTER_POD_INTERIOR_TAG, category=str(self.id))
            self.db.interior = interior
        return self.db.interior

    @property
    def interior(self):
        return self._ensure_interior()
