"""
Matrix Nodes

Virtual locations within the Matrix. These nodes exist in virtual space and can only
be accessed by diving (via avatar objects). They form the navigable geography
of the city's cyberspace.

Nodes can be persistent (customizable spaces that survive between visits) or
ephemeral (template-based interfaces that are cleaned up when empty).

MatrixNode - All virtual Matrix locations (spines, hubs, devices, public spaces)
"""

from typeclasses.rooms import Room


class MatrixNode(Room):
    """
    Virtual location in the Matrix.

    These represent all types of Matrix locations:
    - Spine nodes (relay rooms along the network backbone)
    - Hub nodes (private network spaces created by hub devices)
    - Device nodes (interface spaces for cameras, terminals, etc.)
    - Public spaces (the Cortex, shops, clubs)

    Nodes can be persistent (customizable, survive between visits) or ephemeral
    (template-based, cleaned up when empty). Most nodes are persistent - spine nodes,
    public spaces, and complex devices. Simple devices (cameras, locks, stock handsets)
    use ephemeral nodes.

    Attributes:
        security_level (int): Security clearance required (0-10, 0=public, 10=maximum)
        parent_object (obj): The physical device/object this node represents (if any)
        node_type (str): Type of node (spine, hub, device, public, etc.)
        relay_key (str): Key of the relay this node is associated with (if any)
        ephemeral (bool): Whether this node is ephemeral (False = persistent, default)
    """

    default_description = "A vast data space, humming with virtual activity."

    # Matrix nodes have a different color scheme to distinguish from meatspace
    matrix_name_color = "|m"  # purple/magenta for matrix locations

    def at_object_creation(self):
        """Called when the node is first created."""
        super().at_object_creation()
        self.db.security_level = 0
        self.db.parent_object = None
        self.db.node_type = "standard"
        self.db.relay_key = None
        self.db.ephemeral = False  # Defaults to persistent (not ephemeral)

    def get_display_header(self, looker, **kwargs):
        """Matrix node names use different coloring to distinguish from meatspace."""
        name = self.get_display_name(looker, **kwargs)
        extra = self.get_extra_display_name_info(looker, **kwargs) or ""
        return f"{self.matrix_name_color}{name}{extra}|n"

    def at_object_receive(self, moved_obj, source_location, **kwargs):
        """
        Called when an object enters this node.

        Future implementation will add:
        - Security clearance checks
        - ICE alerts
        - Access logging
        """
        super().at_object_receive(moved_obj, source_location, **kwargs)

        # TODO: Security checks for future implementation
        # if self.db.security_level > 0:
        #     # Check if moved_obj has clearance
        #     # Alert ICE if unauthorized
        #     pass

    @classmethod
    def create_for_device(cls, device, **kwargs):
        """
        Factory method to create a Matrix node for a physical device.

        Works for any Matrix-connected device: hubs, cameras, terminals, handsets, etc.
        The node type and description are determined by the device's properties.

        Args:
            device: The physical device object this node represents
            **kwargs: Additional node creation parameters

        Returns:
            MatrixNode: The created node
        """
        device_type = getattr(device.db, 'device_type', 'device')
        node_name = f"Node: {device.get_display_name(device)}"

        # Create the node
        node = cls.create(node_name, **kwargs)
        node.db.parent_object = device
        node.db.node_type = device_type

        # Set description based on device type
        if device_type == "hub":
            node.db.desc = "A private network space. Basic security daemons patrol the perimeter."
        else:
            node.db.desc = f"A sterile virtual space. {device_type.capitalize()} controls shimmer in the void."

        return node
