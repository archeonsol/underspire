"""
Matrix Rooms

Virtual locations within the Matrix. These rooms exist in virtual space and can only
be accessed by diving (via avatar objects). They form the navigable geography
of the city's cyberspace.

MatrixRoom - Base class for all virtual Matrix locations
MatrixNode - Persistent virtual locations (spines, corporate networks, shops, etc.)
MatrixDevice - Temporary rooms for simple device dives (cameras, locks, etc.)
"""

from typeclasses.rooms import Room
from typeclasses.exits import Exit


class MatrixRoom(Room):
    """
    Base class for virtual Matrix locations.

    These rooms exist in the Matrix's virtual space and can only be accessed
    by avatars (characters who are diving). The physical character remains
    in meatspace while their avatar navigates these virtual locations.

    Attributes:
        security_level (int): Security clearance required (0-10, 0=public, 10=maximum)
        is_temporary (bool): If True, room is dynamically created and should be cleaned up
        parent_device (obj): For temporary rooms, the physical device this represents
    """

    default_description = "A featureless virtual space, devoid of detail."

    # Matrix rooms have a different color scheme to distinguish from meatspace
    matrix_name_color = "|c"  # cyan for matrix locations

    def at_object_creation(self):
        """Called when the room is first created."""
        super().at_object_creation()
        self.db.security_level = 0
        self.db.is_temporary = False
        self.db.parent_device = None

    def get_display_header(self, looker, **kwargs):
        """Matrix room names use different coloring to distinguish from meatspace."""
        name = self.get_display_name(looker, **kwargs)
        extra = self.get_extra_display_name_info(looker, **kwargs) or ""
        return f"{self.matrix_name_color}{name}{extra}|n"

    def at_object_receive(self, moved_obj, source_location, **kwargs):
        """
        Called when an object enters this room.

        For now, just standard behavior. In the future this could:
        - Check security clearance
        - Alert ICE
        - Log access attempts
        """
        super().at_object_receive(moved_obj, source_location, **kwargs)

        # TODO: Security checks for future implementation
        # if self.db.security_level > 0:
        #     # Check if moved_obj has clearance
        #     pass

    def cleanup(self):
        """
        Clean up temporary rooms and their contents.

        Called when a temporary device interface room is no longer needed.
        Should destroy ICE and any dynamically created objects.
        """
        if not self.db.is_temporary:
            return

        # Destroy all contents (ICE, control objects, etc.)
        for obj in self.contents:
            # Don't delete avatars, just move them out
            if hasattr(obj, 'typeclass_path') and 'avatar' in obj.typeclass_path.lower():
                # Force disconnect the avatar
                if hasattr(obj, 'force_disconnect'):
                    obj.force_disconnect()
            else:
                obj.delete()

        # Delete the room itself
        self.delete()


class MatrixNode(MatrixRoom):
    """
    Persistent virtual location in the Matrix.

    These are the major locations in Matrix geography: district spines,
    corporate networks, virtual storefronts, media hubs, the Cortex, etc.
    They are permanent and persist across server restarts.

    Attributes:
        node_type (str): Type of node (spine, corporate, shop, media, etc.)
        district (str): Physical district this node serves (for spine nodes)
    """

    default_description = "A vast data space, humming with virtual activity."

    def at_object_creation(self):
        """Called when the node is first created."""
        super().at_object_creation()
        self.db.is_temporary = False  # Nodes are persistent
        self.db.node_type = "standard"
        self.db.district = None


class MatrixDevice(MatrixRoom):
    """
    Temporary virtual location representing a device's interface.

    These rooms are dynamically created when diving into cameras, locks,
    terminals, and other simple devices. They should be cleaned up when
    the dive ends.

    The appearance is minimal and functional, appropriate to the device type.
    """

    default_description = "A sterile control interface."

    def at_object_creation(self):
        """Called when the interface room is created."""
        super().at_object_creation()
        self.db.is_temporary = True
        self.db.security_level = 0  # Most simple devices have minimal security

    @classmethod
    def create_for_device(cls, device, **kwargs):
        """
        Factory method to create a temporary interface room for a device.

        Args:
            device: The physical device object this interface represents
            **kwargs: Additional room creation parameters

        Returns:
            MatrixDevice: The created temporary room
        """
        device_type = device.typename if hasattr(device, 'typename') else "device"
        room_name = f"Interface: {device.get_display_name(device)}"

        # Create the room
        room = cls.create(room_name, **kwargs)
        room.db.parent_device = device

        # Set description based on device type
        # TODO: Make this more sophisticated with device-specific descriptions
        room.db.desc = f"A sterile virtual space. {device_type.capitalize()} controls are present."

        return room


class MatrixExit(Exit):
    """
    Exit between Matrix virtual locations.

    These exits connect virtual rooms in the Matrix. They can have different
    behavior than physical exits, including security checks, routing through
    the Cortex, and access logging.

    Attributes:
        security_clearance (int): Clearance level required to traverse (0-10)
        requires_credentials (bool): If True, requires valid credentials to pass
        routes_through_cortex (bool): If True, logs routing through central hub
    """

    def at_object_creation(self):
        """Called when the exit is first created."""
        super().at_object_creation()
        self.db.security_clearance = 0
        self.db.requires_credentials = False
        self.db.routes_through_cortex = False

    def at_traverse(self, traversing_object, destination):
        """
        Called when someone attempts to traverse this exit.

        For now, behaves like normal exits but instantaneous (no walking delay).
        Future implementation will add:
        - Security clearance checks
        - Credential verification
        - Cortex routing and logging
        - ICE alerts on unauthorized access
        """
        if not destination:
            super().at_traverse(traversing_object, destination)
            return

        # TODO: Security checks for future implementation
        # if self.db.security_clearance > 0:
        #     # Check traversing_object has required clearance
        #     pass

        # Matrix navigation is instantaneous - no delay like physical movement
        direction = (self.key or "away").strip()
        traversing_object.msg(f"You navigate {direction}.")

        # Move immediately
        traversing_object.move_to(destination)
