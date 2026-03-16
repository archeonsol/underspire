"""
Matrix Objects

Tangible objects within Matrix virtual space. These objects exist in Matrix rooms
and can be interacted with by avatars, but are not portable items.

MatrixObject - Base class for all tangible Matrix objects (terminals, ICE, decorations, etc.)
"""

from typeclasses.objects import Object


class MatrixObject(Object):
    """
    Base class for tangible objects in Matrix virtual space.

    These objects exist in Matrix rooms and can be interacted with but are
    generally not portable. Examples include control terminals, security
    systems, decorative virtual architecture, ICE programs, etc.

    Unlike MatrixItems, these objects are typically fixtures of the virtual
    environment.

    Attributes:
        security_level (int): Security level of this object (0-10)
        is_interactive (bool): Whether avatars can interact with this object
        device_type (str): Type of device/object (terminal, ice, decoration, etc.)
    """

    def at_object_creation(self):
        """Called when the object is first created."""
        super().at_object_creation()
        self.db.security_level = 0
        self.db.is_interactive = True
        self.db.device_type = "generic"

    def at_object_receive(self, moved_obj, source_location, **kwargs):
        """
        Called when an object is moved into this object (if it's a container).

        For now, standard behavior. Future implementation could:
        - Restrict what can be stored in Matrix objects
        - Log access to secured containers
        - Trigger alerts
        """
        super().at_object_receive(moved_obj, source_location, **kwargs)
