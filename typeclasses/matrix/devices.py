"""
Matrix Devices

Physical devices connected to the Matrix. These are meatspace objects that have
virtual interfaces accessible through diving. Examples include cameras, servers,
terminals, kiosks, TVs, digital signs, door locks, etc.

MatrixDevice - Base class for any physical device connected to the Matrix
"""

from typeclasses.objects import Object


class MatrixDevice(Object):
    """
    Base class for physical devices connected to the Matrix.

    These are meatspace objects that exist in regular rooms but have virtual
    interfaces that can be accessed by diving. When an avatar dives into a
    MatrixDevice, a temporary MatrixDevice room is created representing the
    device's virtual interface.

    Attributes:
        device_type (str): Type of device (camera, terminal, kiosk, lock, etc.)
        security_level (int): Security level (0-10, 0=unsecured, 10=maximum)
        is_connected (bool): Whether device is connected to Matrix (False = air-gapped, requires physical proximity)
        virtual_interface (obj): Reference to active temporary interface room (if any)
        access_logs (list): Log of access attempts (for future implementation)
    """

    def at_object_creation(self):
        """Called when the device is first created."""
        super().at_object_creation()
        self.db.device_type = "generic"
        self.db.security_level = 0
        self.db.is_connected = True
        self.db.virtual_interface = None
        self.db.access_logs = []

    def generate_virtual_interface(self, **kwargs):
        """
        Generate a temporary virtual interface room for this device.

        Called when an avatar dives into this device. Creates a MatrixDevice room
        with appropriate description and controls for this device type.

        Args:
            **kwargs: Additional parameters for room creation

        Returns:
            MatrixDevice room instance, or None if creation fails
        """
        # Don't create duplicate interfaces
        if self.db.virtual_interface:
            # Check if it still exists
            if self.db.virtual_interface.pk:
                return self.db.virtual_interface
            else:
                # Stale reference, clear it
                self.db.virtual_interface = None

        # Import here to avoid circular dependency
        from typeclasses.rooms import MatrixDevice as MatrixDeviceRoom

        try:
            interface = MatrixDeviceRoom.create_for_device(self, **kwargs)
            self.db.virtual_interface = interface
            return interface
        except Exception as e:
            # Log error but don't crash
            print(f"Error creating virtual interface for {self.key}: {e}")
            return None

    def cleanup_virtual_interface(self):
        """
        Clean up the temporary virtual interface room.

        Called when no avatars remain in the device interface, or when
        the device is disconnected/destroyed.
        """
        interface = self.db.virtual_interface
        if not interface:
            return

        # Clear our reference first
        self.db.virtual_interface = None

        # Clean up the interface room if it exists
        if hasattr(interface, 'cleanup'):
            interface.cleanup()
        elif hasattr(interface, 'delete'):
            interface.delete()

    def at_dive(self, avatar, **kwargs):
        """
        Called when an avatar attempts to dive into this device.

        Args:
            avatar: The avatar object attempting to dive
            **kwargs: Additional parameters

        Returns:
            bool: True if dive succeeds, False otherwise
        """
        # Note: is_connected determines if device can be accessed remotely via Matrix
        # If False (air-gapped), avatar must be physically near the device
        # TODO: Add proximity check for air-gapped devices in future implementation
        # if not self.db.is_connected:
        #     # Check if avatar's meatspace body is near this device
        #     pass

        # TODO: Security checks for future implementation
        # if self.db.security_level > avatar.get_clearance_level():
        #     avatar.msg("Access denied: insufficient clearance.")
        #     return False

        # Generate or get existing interface
        interface = self.generate_virtual_interface()
        if not interface:
            if hasattr(avatar, 'msg'):
                avatar.msg("Error: Could not establish connection to device interface.")
            return False

        # Move avatar into the interface
        avatar.move_to(interface)

        # Log the access (for future implementation)
        # self.log_access(avatar)

        return True

    def at_disconnect(self):
        """
        Called when device is disconnected from Matrix.

        Cleans up virtual interface and notifies any avatars inside.
        """
        self.db.is_connected = False

        interface = self.db.virtual_interface
        if interface and hasattr(interface, 'contents'):
            # Notify and eject any avatars
            for obj in interface.contents:
                if hasattr(obj, 'force_disconnect'):
                    obj.msg("|rConnection lost: device disconnected from Matrix.|n")
                    obj.force_disconnect()

        # Clean up the interface
        self.cleanup_virtual_interface()

    def at_object_delete(self):
        """
        Called just before this device is deleted.

        Clean up any virtual interfaces.
        """
        self.cleanup_virtual_interface()
        return super().at_object_delete()

    def get_device_description(self, looker=None):
        """
        Get description text specific to this device's function.

        Override this in subclasses to provide device-specific descriptions
        in the virtual interface.

        Args:
            looker: Who is looking (for permission checks)

        Returns:
            str: Description for virtual interface
        """
        return f"A {self.db.device_type} interface."
