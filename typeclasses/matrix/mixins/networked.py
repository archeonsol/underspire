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
        self.db.ephemeral_node = False  # Whether Matrix node is ephemeral (default: persistent)
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

        Gets the relay from the room this device is located in.
        Rooms define network coverage via their network_relay attribute.

        Returns:
            Router: The router this device connects through, or None if not connected
        """
        room = self.location
        if not room:
            return None

        # Get router key from room
        relay_key = getattr(room.db, 'network_router', None)
        if not relay_key:
            return None

        # Look up router by key
        from evennia.utils.search import search_object
        results = search_object(relay_key)
        return results[0] if results else None

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
