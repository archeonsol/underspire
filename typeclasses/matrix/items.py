"""
Matrix Items

Portable objects related to the Matrix system, both physical and virtual.

NetworkedItem - Portable physical devices with Matrix interfaces (handsets, tablets, etc.)
MatrixItem - Portable data objects in Matrix virtual space (files, credentials, keys, etc.)
Program - Executable programs run via 'exec' command in Matrix interface rooms
"""

from typeclasses.items import Item
from typeclasses.matrix.mixins import NetworkedMixin


class NetworkedItem(NetworkedMixin, Item):
    """
    Portable physical device with a Matrix interface.

    These items exist in meatspace and can be carried by characters.
    Examples: handsets, tablets, portable consoles, data chips (physical).

    Like NetworkedObject, each has an associated MatrixNode in cyberspace.
    Unlike NetworkedObject, these are portable items rather than fixed objects.

    Attributes:
        device_type (str): Type of device (handset, tablet, console, etc.)
        matrix_node (MatrixNode): The virtual room representing this device in the Matrix
        security_level (int): Security clearance required to access (0-10)
        has_storage (bool): Whether this device has file storage
        has_controls (bool): Whether this device has controllable functions
    """

    def at_object_creation(self):
        """Called when the device is first created."""
        super().at_object_creation()
        self.setup_networked_attrs()


class MatrixItem(Item):
    """
    Base class for portable data objects in Matrix virtual space.

    These items can be picked up and carried by avatars. Examples include
    data files, access credentials, encryption keys, stolen corporate data,
    programs, etc.

    Unlike MatrixObjects, these are meant to be portable and can be taken
    between Matrix locations.

    Attributes:
        data_type (str): Type of data (file, credential, key, program, etc.)
        data_size (int): Size of data in arbitrary units (affects carry capacity?)
        encryption_key (str): Encryption key ID/hash, or None if unencrypted
        value (int): Black market value or importance level
    """

    def at_object_creation(self):
        """Called when the item is first created."""
        super().at_object_creation()
        self.db.data_type = "file"
        self.db.data_size = 1
        self.db.encryption_key = None
        self.db.value = 0

    def at_get(self, getter, **kwargs):
        """
        Called when this item is picked up.

        For now, standard behavior. Future implementation could:
        - Trigger alerts when secured data is accessed
        - Check if getter has permission to access this data
        - Log the data theft
        """
        super().at_get(getter, **kwargs)

    def at_drop(self, dropper, **kwargs):
        """
        Called when this item is dropped.

        Standard behavior for now.
        """
        super().at_drop(dropper, **kwargs)


# Import program classes from programs package
from typeclasses.matrix.programs import (
    Program,
    SysInfoProgram,
    CmdExeProgram,
    CRUDProgram,
    SkeletonKeyProgram,
    ExfilProgram,
    InfilProgram,
    ICEpickProgram,
)

__all__ = [
    "NetworkedItem",
    "MatrixItem",
    "Program",
    "SysInfoProgram",
    "CmdExeProgram",
    "CRUDProgram",
    "SkeletonKeyProgram",
    "ExfilProgram",
    "InfilProgram",
    "ICEpickProgram",
]
