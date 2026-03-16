"""
Matrix Items

Portable data objects within Matrix virtual space. These items can be picked up,
carried, and manipulated by avatars diving in the Matrix.

MatrixItem - Base class for all portable Matrix data objects (files, credentials, keys, etc.)
"""

from typeclasses.items import Item


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
        encrypted (bool): Whether this data is encrypted
        value (int): Black market value or importance level
    """

    def at_object_creation(self):
        """Called when the item is first created."""
        super().at_object_creation()
        self.db.data_type = "file"
        self.db.data_size = 1
        self.db.encrypted = False
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
