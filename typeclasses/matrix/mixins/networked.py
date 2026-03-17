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
        self.db.device_type = "device"  # Override in subclasses (e.g., "camera", "terminal", "hub")
        self.db.matrix_node = None  # Cached reference to this device's Matrix node
        self.db.ephemeral_node = False  # Whether Matrix node is ephemeral (default: persistent)
        self.db.security_level = 0
        self.db.has_storage = False
        self.db.has_controls = False

    def get_or_create_node(self):
        """
        Get this device's Matrix node, creating it if it doesn't exist.

        DEPRECATED: Use get_or_create_cluster() for ephemeral device interfaces.
        This method is kept for backward compatibility with persistent nodes.

        The node is a virtual room in the Matrix that represents this physical
        device. When someone dives into this device, they enter its node.

        Returns:
            MatrixNode: The Matrix room representing this device
        """
        if not self.db.matrix_node:
            from typeclasses.matrix.rooms import MatrixNode
            self.db.matrix_node = MatrixNode.create_for_device(self)
        return self.db.matrix_node

    def get_or_create_cluster(self):
        """
        Get or create the ephemeral 2-room cluster for this device.

        Creates a vestibule (ICE room) and interface room on first access.
        Both rooms are ephemeral and will be cleaned up when empty.

        Returns:
            dict: {'vestibule': MatrixNode, 'interface': MatrixNode} or None on failure
        """
        from typeclasses.matrix.rooms import MatrixNode
        from evennia.utils.create import create_object

        # Check if cluster already exists
        vestibule_dbref = getattr(self.db, 'vestibule_node', None)
        interface_dbref = getattr(self.db, 'interface_node', None)

        vestibule = None
        interface = None

        # Try to load existing rooms
        if vestibule_dbref:
            try:
                vestibule = MatrixNode.objects.get(pk=vestibule_dbref)
            except MatrixNode.DoesNotExist:
                self.db.vestibule_node = None

        if interface_dbref:
            try:
                interface = MatrixNode.objects.get(pk=interface_dbref)
            except MatrixNode.DoesNotExist:
                self.db.interface_node = None

        # If both exist, return them
        if vestibule and interface:
            return {'vestibule': vestibule, 'interface': interface}

        # Clean up partial cluster
        if vestibule:
            vestibule.delete()
            self.db.vestibule_node = None
        if interface:
            interface.delete()
            self.db.interface_node = None

        # Create new cluster
        device_type = getattr(self.db, 'device_type', 'device')

        # Create vestibule
        vestibule = create_object(
            MatrixNode,
            key=f"{self.key} - Vestibule"
        )
        if not vestibule:
            return None

        vestibule.db.parent_object = self
        vestibule.db.is_vestibule = True
        vestibule.db.ephemeral = True
        vestibule.db.node_type = "device_vestibule"
        vestibule.db.desc = (
            "A stark virtual anteroom. Security protocols hum in the background, "
            "ready to spawn defensive ICE at the first sign of unauthorized access."
        )

        # Create interface room
        interface = create_object(
            MatrixNode,
            key=f"{self.key} - Interface"
        )
        if not interface:
            vestibule.delete()
            return None

        interface.db.parent_object = self
        interface.db.is_interface = True
        interface.db.ephemeral = True
        interface.db.node_type = "device_interface"

        # Set interface description based on device type
        if device_type == "hub":
            # Hub uses custom description or default
            hub_desc = getattr(self.db, 'hub_desc', None)
            if hub_desc:
                interface.db.desc = hub_desc
            else:
                interface.db.desc = (
                    "A blank virtual space, waiting to be customized. "
                    "This is your private network node - shape it as you see fit."
                )
            # Restore hub details if they exist
            hub_details = getattr(self.db, 'hub_details', None)
            if hub_details:
                for key, value in hub_details.items():
                    interface.db.details[key] = value
        else:
            # Generic device interface
            device_desc = getattr(self.db, 'interface_desc', None)
            if device_desc:
                interface.db.desc = device_desc
            else:
                interface.db.desc = (
                    f"A sterile virtual interface space. The {device_type}'s "
                    "systems are accessible here through command consoles."
                )

        # Create exits between rooms
        from evennia.utils.create import create_object
        from typeclasses.exits import Exit

        # Vestibule -> Interface (locked until ICE defeated or on ACL)
        exit_to_interface = create_object(
            Exit,
            key="interface",
            location=vestibule,
            destination=interface
        )
        # TODO: Add lock based on ICE/ACL status
        # exit_to_interface.locks.add("traverse:...")

        # Interface -> Vestibule (back exit)
        exit_to_vestibule = create_object(
            Exit,
            key="back",
            aliases=["vestibule"],
            location=interface,
            destination=vestibule
        )

        # Store references
        self.db.vestibule_node = vestibule.pk
        self.db.interface_node = interface.pk

        return {'vestibule': vestibule, 'interface': interface}

    def get_relay(self):
        """
        Determine which relay this device is connected through.

        Gets the relay from the room this device is located in.
        Rooms define network coverage via their network_router attribute (dbref).

        Returns:
            Router: The router this device connects through, or None if not connected
        """
        room = self.location
        if not room:
            return None

        # Get router dbref from room
        router_dbref = getattr(room.db, 'network_router', None)
        if not router_dbref:
            return None

        # Look up router by dbref
        from typeclasses.matrix.objects import Router
        try:
            return Router.objects.get(pk=router_dbref)
        except Router.DoesNotExist:
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
