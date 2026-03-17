"""
Furniture interaction mixin: sitting, lying, movement blocking.

Provides db.sitting_on, db.lying_on, db.lying_on_table attributes and
at_pre_move() hook that blocks normal movement when seated/lying and
handles forced removal notifications.
"""


class FurnitureMixin:
    """Furniture interaction: sitting, lying, movement restrictions."""

    def at_pre_move(self, destination, **kwargs):
        """
        Called just before starting to move this object to destination.
        If this returns False, the move is cancelled.

        Block normal movement when sitting/lying (must stand first).
        Allow forced movement (teleport, grapple drag, etc) but notify furniture
        and clear state automatically.
        """
        move_type = kwargs.get("move_type", "move")

        # Check if sitting/lying
        is_seated = self.db.sitting_on is not None
        is_lying = self.db.lying_on is not None or self.db.lying_on_table is not None

        # Block normal movement (walking through exits)
        if (is_seated or is_lying) and move_type in ("move", "traverse"):
            if is_seated:
                self.msg("You need to stand up first.")
            else:
                self.msg("You need to get up first.")
            return False

        # For forced movement (teleport, grapple, etc), notify furniture and clear state
        if is_seated:
            sitting_on = self.db.sitting_on
            # Notify furniture of forced removal (e.g., dive rig jack-out)
            if sitting_on and hasattr(sitting_on, "handle_forced_removal"):
                sitting_on.handle_forced_removal(self)
            del self.db.sitting_on

        if self.db.lying_on:
            del self.db.lying_on
        if self.db.lying_on_table:
            del self.db.lying_on_table

        return True
