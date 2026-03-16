"""
Matrix Nodes

Virtual locations within the Matrix. These nodes exist in virtual space and can only
be accessed by diving (via avatar objects). They form the navigable geography
of the city's cyberspace.

All Matrix nodes are persistent - device nodes exist as long as the device exists,
and spine nodes are permanent infrastructure.

MatrixNode - All virtual Matrix locations (spines, hubs, devices, public spaces)
MatrixExit - Connections between Matrix locations
"""

from typeclasses.rooms import Room
from typeclasses.exits import Exit


class MatrixNode(Room):
    """
    Virtual location in the Matrix.

    These represent all types of Matrix locations:
    - Spine nodes (relay rooms along the network backbone)
    - Hub nodes (private network spaces created by hub devices)
    - Device nodes (interface spaces for cameras, terminals, etc.)
    - Public spaces (the Cortex, shops, clubs)

    All nodes are persistent. Device nodes exist as long as their parent device
    exists. Spine nodes and public spaces are permanent infrastructure.

    Attributes:
        security_level (int): Security clearance required (0-10, 0=public, 10=maximum)
        parent_object (obj): The physical device/object this node represents (if any)
        node_type (str): Type of node (spine, hub, device, public, etc.)
        relay_key (str): Key of the relay this node is associated with (if any)
    """

    default_description = "A vast data space, humming with virtual activity."

    # Matrix nodes have a different color scheme to distinguish from meatspace
    matrix_name_color = "|c"  # cyan for matrix locations

    def at_object_creation(self):
        """Called when the node is first created."""
        super().at_object_creation()
        self.db.security_level = 0
        self.db.parent_object = None
        self.db.node_type = "standard"
        self.db.relay_key = None

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
