"""
Matrix ID Mixin

Provides automatic Matrix ID assignment and management for objects.

Any object that should have a Matrix ID (networked devices, avatars, Matrix objects)
should inherit from this mixin. IDs are automatically assigned on creation and
cleaned up on deletion.
"""

from world.matrix_ids import register_matrix_id, unregister_matrix_id, get_matrix_id


class MatrixIdMixin:
    """
    Mixin that provides automatic Matrix ID management.

    Automatically registers the object and assigns a unique ^XXXXXX ID on creation.
    Cleans up the ID from the registry on deletion to allow recycling.

    Add this mixin to any class that needs a Matrix ID:
    - NetworkedMixin (physical devices)
    - MatrixAvatar (virtual personas)
    - MatrixObject (virtual objects)
    - MatrixItem (portable virtual items)

    Attributes:
        matrix_id (str): The object's Matrix ID (stored in db.matrix_id)
    """

    def at_object_creation(self):
        """
        Initialize matrix_id attribute (ID assigned lazily on first access).
        """
        super().at_object_creation()
        # Don't assign ID yet - will be generated on first get_matrix_id() call
        self.db.matrix_id = None

    def at_object_delete(self):
        """
        Clean up Matrix ID when object is deleted.
        This frees the ID for reuse.
        """
        unregister_matrix_id(self)
        return super().at_object_delete()

    def get_matrix_id(self):
        """
        Get this object's Matrix ID.

        Lazily generates and assigns the ID on first access if not already assigned.

        Returns:
            str: The Matrix ID with prefix (e.g., "^3K7MQ5")
        """
        # Check if already assigned
        if hasattr(self.db, 'matrix_id') and self.db.matrix_id:
            return self.db.matrix_id

        # Check registry (in case it was registered externally)
        matrix_id = get_matrix_id(self)
        if matrix_id:
            # Cache it
            self.db.matrix_id = matrix_id
            return matrix_id

        # Generate and register new ID (lazy assignment)
        try:
            self.db.matrix_id = register_matrix_id(self)
            return self.db.matrix_id
        except Exception as e:
            # Log error but don't crash
            from evennia.utils import logger
            logger.log_err(f"Failed to assign Matrix ID to {self}: {e}")
            return "^ERROR"
