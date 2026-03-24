"""
Matrix Exits

Connections between Matrix virtual locations.

MatrixExit - Connections between Matrix nodes with security features
"""

from typeclasses.exits import Exit


class MatrixExit(Exit):
    """
    Exit between Matrix virtual locations.

    These exits connect virtual nodes in the Matrix. They can have different
    behavior than physical exits, including security checks, routing through
    the network, and access logging.

    Attributes:
        security_clearance (int): Clearance level required to traverse (0-10)
        requires_credentials (bool): If True, requires valid credentials to pass
        is_routing (bool): If True, this is a dynamic routing connection (not a permanent exit)
    """

    def at_object_creation(self):
        """Called when the exit is first created."""
        super().at_object_creation()
        self.db.security_clearance = 0
        self.db.requires_credentials = False
        self.db.is_routing = False

    def at_traverse(self, traversing_object, destination):
        """
        Called when someone attempts to traverse this exit.

        Matrix navigation is fast but not instant - base 0.5 second delay,
        reducible with decking skill. Future implementation will add:
        - Security clearance checks
        - Credential verification
        - ICE alerts on unauthorized access
        - Routing logs
        """
        if not destination:
            super().at_traverse(traversing_object, destination)
            return

        # Matrix navigation delay - fast but not instant
        # Base delay: 1.0s, reduced by decking skill
        # TODO: When decking skill exists, reduce delay based on skill level
        base_delay = 1.0

        # Check if traversing object has decking skill
        skill_reduction = 0.0
        if hasattr(traversing_object, 'get_skill_level'):
            try:
                # Future: decking_skill = traversing_object.get_skill_level('decking')
                # skill_reduction = min(0.3, decking_skill / 500)  # Max 0.3s reduction
                pass
            except:
                pass

        move_delay = max(0.2, base_delay - skill_reduction)  # Minimum 0.2s delay

        direction = (self.key or "away").strip()
        traversing_object.msg(f"You navigate {direction}...")

        # Use utils.delay to add movement delay
        from evennia.utils import delay
        delay(move_delay, traversing_object.move_to, destination)
