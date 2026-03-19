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
        Called when object is first created.
        Matrix ID will be assigned lazily on first get_matrix_id() call.
        """
        super().at_object_creation()

    def at_object_delete(self):
        """
        Clean up Matrix ID when object is deleted.

        NOTE: ID recycling is disabled. Matrix IDs are permanent and never reused.
        This preserves historical references in logs, messages, and records.
        """
        # Recycling disabled - IDs remain in registry permanently
        # try:
        #     unregister_matrix_id(self)
        # except Exception:
        #     # Don't let registry errors prevent deletion
        #     pass
        return super().at_object_delete()

    def _should_have_matrix_id(self):
        """
        Check if this object should have a Matrix ID.

        Override in subclasses to control ID assignment criteria.
        Base implementation allows all objects to have IDs.

        Returns:
            bool: True if object should have Matrix ID, False otherwise
        """
        return True

    def get_matrix_id(self):
        """
        Get this object's Matrix ID.

        Lazily generates and assigns the ID on first access if not already assigned.
        Always checks registry as single source of truth.

        Returns:
            str or None: The Matrix ID with prefix (e.g., "^3K7MQ5"), or None if object shouldn't have one
        """
        # Don't assign IDs to objects without a database ID
        if not self.pk:
            return None

        # Check if this object should have a Matrix ID
        if not self._should_have_matrix_id():
            return None

        # Check registry for existing ID
        matrix_id = get_matrix_id(self)
        if matrix_id:
            return matrix_id

        # Generate and register new ID (lazy assignment)
        return register_matrix_id(self)
