"""
Matrix Objects

Objects related to the Matrix system, both physical and virtual.

NetworkedObject - Physical meatspace devices with Matrix interfaces (cameras, consoles, hubs, etc.)
MatrixObject - Virtual objects that exist only in cyberspace (programs, data, beacons, etc.)
"""

from typeclasses.objects import Object
from .mixins import NetworkedMixin


class NetworkedObject(NetworkedMixin, Object):
    """
    Physical device in meatspace with a Matrix interface.

    These objects exist in the physical world but can be accessed through the Matrix.
    Examples: cameras, terminals, consoles, hubs, door locks.

    Each NetworkedObject has an associated MatrixNode that represents it in
    cyberspace. When someone dives into the device, they enter its node.

    Attributes:
        connection_type (str): "wireless" or "hardwired"
        device_type (str): Type of device (hub, camera, terminal, console, etc.)
        matrix_node (MatrixNode): The virtual room representing this device in the Matrix
        security_level (int): Security clearance required to access (0-10)
        has_storage (bool): Whether this device has file storage
        has_controls (bool): Whether this device has controllable functions
    """

    def at_object_creation(self):
        """Called when the device is first created."""
        super().at_object_creation()
        self.setup_networked_attrs()


class MatrixObject(Object):
    """
    Virtual object that exists only in cyberspace.

    These objects exist in Matrix nodes and can be carried by avatars diving the Matrix.
    Examples: programs, data files, beacons, ICE constructs, virtual items.

    Unlike NetworkedObject devices, these have no physical form in meatspace
    (or if they do, it's just a data chip that points to the virtual object).

    Attributes:
        object_type (str): Type of object (program, data, beacon, ice, etc.)
        security_level (int): Security level (0-10)
        is_portable (bool): Whether this object can be picked up and carried
    """

    def at_object_creation(self):
        """Called when the object is first created."""
        super().at_object_creation()
        self.db.object_type = "data"
        self.db.security_level = 0
        self.db.is_portable = True

    def at_object_receive(self, moved_obj, source_location, **kwargs):
        """
        Called when an object is moved into this object (if it's a container).

        Future implementation could:
        - Restrict what can be stored
        - Log access attempts
        - Trigger security alerts
        """
        super().at_object_receive(moved_obj, source_location, **kwargs)
