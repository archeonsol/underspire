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

        Matrix navigation is instantaneous (no walking delay).
        Future implementation will add:
        - Security clearance checks
        - Credential verification
        - ICE alerts on unauthorized access
        - Routing logs
        """
        if not destination:
            super().at_traverse(traversing_object, destination)
            return

        # TODO: Security checks for future implementation
        # if self.db.security_clearance > 0:
        #     # Check traversing_object has required clearance
        #     # Alert ICE if unauthorized
        #     pass

        # Matrix navigation is instantaneous - no delay like physical movement
        direction = (self.key or "away").strip()
        traversing_object.msg(f"You navigate {direction}.")

        # Move immediately
        traversing_object.move_to(destination)
