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
    matrix_name_color = "|415"  # purple/magenta for matrix locations

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
        ephemeral_tag = " |y[Ephemeral]|n" if self.db.ephemeral else ""
        return f"{self.matrix_name_color}{name}{extra}{ephemeral_tag}|n"

    def at_pre_object_receive(self, moved_obj, source_location, **kwargs):
        """
        Called before an object enters this node. Returning False blocks the move.

        Prevents dropping items in ephemeral device nodes.

        Future implementation will add:
        - Security clearance checks
        - ICE alerts
        - Access logging
        """
        # Prevent dropping items in ephemeral nodes
        if self.db.ephemeral:
            # Allow characters/avatars to enter
            if moved_obj.has_account:
                return super().at_pre_object_receive(moved_obj, source_location, **kwargs)

            # Prevent items from being dropped
            if source_location and source_location.has_account:
                # It's being dropped by a character/avatar
                source_location.msg(
                    "You cannot drop items in ephemeral device nodes. "
                    "Use programs like infil.exe to save data to device storage."
                )
                return False

        return super().at_pre_object_receive(moved_obj, source_location, **kwargs)
