"""
Matrix Mixins

Mixins providing shared functionality for Matrix-related classes.

NetworkedMixin - Provides Matrix connectivity for both objects and items
"""


class NetworkedMixin:
    """
    Mixin providing Matrix connectivity for physical devices.

    This mixin can be used with both Object and Item classes to provide
    networked device functionality. It handles connection tracking, relay
    lookup, and Matrix node creation.

    Classes using this mixin should call setup_networked_attrs() in their
    at_object_creation() method.
    """

    def setup_networked_attrs(self):
        """
        Initialize networked device attributes.

        Should be called in at_object_creation() after super().
        """
        self.db.connection_type = "wireless"
        self.db.device_type = "device"
        self.db.matrix_node = None
        self.db.security_level = 0
        self.db.has_storage = False
        self.db.has_controls = False

    def get_or_create_node(self):
        """
        Get this device's Matrix node, creating it if it doesn't exist.

        The node is a virtual room in the Matrix that represents this physical
        device. When someone dives into this device, they enter its node.

        Returns:
            MatrixNode: The Matrix room representing this device
        """
        if not self.db.matrix_node:
            from typeclasses.matrix.rooms import MatrixNode
            self.db.matrix_node = MatrixNode.create_for_device(self)
        return self.db.matrix_node

    def get_relay(self):
        """
        Determine which relay this device is connected through.

        Wireless devices connect through the relay covering their current location.
        Hardwired devices connect through specific ports.

        Returns:
            Relay: The relay this device connects through, or None if not connected
        """
        if self.db.connection_type == "wireless":
            # Wireless devices connect through room coverage
            from typeclasses.matrix.relays import RelayManager
            return RelayManager.get_relay_for_room(self.location)
        elif self.db.connection_type == "hardwired":
            # Hardwired devices connect through specific ports
            # TODO: Implement port-based relay lookup
            # For items, hardwired might mean slotted into a console
            pass
        return None

    def is_connected(self):
        """
        Check if this device is currently connected to the Matrix.

        A device is connected if it can find a relay (either through wireless
        coverage or hardwired connection).

        Returns:
            bool: True if device has an active connection to the Matrix
        """
        relay = self.get_relay()
        return relay is not None
