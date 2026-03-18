"""
Matrix ID System

Generates and manages unique Base32 IDs for Matrix-connected entities.
All networked devices, avatars, and Matrix objects get a unique ^XXXXXX identifier.

IDs are 6-character Base32 strings (A-Z, 2-7), giving ~1 billion possible IDs.
IDs are recycled when objects are deleted to conserve the ID space.

The registry is stored on a persistent global script for easy access.
"""

import random
import string
from evennia import DefaultScript
from evennia.utils import search


# Base32 alphabet (excludes 0, 1, 8, 9 to avoid confusion with O, I, B, g)
BASE32_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
ID_LENGTH = 6
ID_PREFIX = "^"


def get_registry_script():
    """
    Get or create the global Matrix ID registry script.

    Returns:
        DefaultScript: The registry script with id_to_dbref and dbref_to_id mappings
    """
    script = search.search_script("matrix_id_registry")

    if not script:
        # Create the registry script
        script = DefaultScript.create(
            key="matrix_id_registry",
            persistent=True,
            desc="Global registry for Matrix ID system"
        )
        script.db.id_to_dbref = {}  # {"3K7MQ5": 123, ...}
        script.db.dbref_to_id = {}  # {123: "3K7MQ5", ...}
    else:
        script = script[0]

    # Ensure attributes exist
    if not hasattr(script.db, 'id_to_dbref'):
        script.db.id_to_dbref = {}
    if not hasattr(script.db, 'dbref_to_id'):
        script.db.dbref_to_id = {}

    return script


def generate_id(length=ID_LENGTH):
    """
    Generate a random Base32 ID string.

    Args:
        length (int): Length of the ID (default 6)

    Returns:
        str: Random Base32 string (e.g., "3K7MQ5")
    """
    return ''.join(random.choices(BASE32_CHARS, k=length))


def register_matrix_id(obj, max_attempts=100):
    """
    Register an object and assign it a unique Matrix ID.

    Args:
        obj: The object to register
        max_attempts (int): Maximum collision retry attempts

    Returns:
        str: The full Matrix ID with prefix (e.g., "^3K7MQ5")

    Raises:
        RuntimeError: If unable to generate unique ID after max_attempts
    """
    if not obj or not obj.pk:
        raise ValueError("Cannot register object without a database ID")

    registry = get_registry_script()
    dbref = obj.id

    # Check if already registered
    if dbref in registry.db.dbref_to_id:
        return ID_PREFIX + registry.db.dbref_to_id[dbref]

    # Generate unique ID
    for _ in range(max_attempts):
        matrix_id = generate_id()

        # Check for collision
        if matrix_id not in registry.db.id_to_dbref:
            # Register it
            registry.db.id_to_dbref[matrix_id] = dbref
            registry.db.dbref_to_id[dbref] = matrix_id
            return ID_PREFIX + matrix_id

    # Failed to generate unique ID
    raise RuntimeError(
        f"Failed to generate unique Matrix ID after {max_attempts} attempts. "
        f"ID space may be exhausted ({len(registry.db.id_to_dbref)} IDs registered)."
    )


def unregister_matrix_id(obj):
    """
    Remove an object from the Matrix ID registry.
    This frees up the ID to be reused.

    Args:
        obj: The object to unregister

    Returns:
        bool: True if unregistered, False if wasn't registered
    """
    if not obj or not obj.pk:
        return False

    registry = get_registry_script()
    dbref = obj.id

    # Check if registered
    if dbref not in registry.db.dbref_to_id:
        return False

    # Remove from both mappings
    matrix_id = registry.db.dbref_to_id[dbref]
    del registry.db.dbref_to_id[dbref]
    del registry.db.id_to_dbref[matrix_id]

    return True


def lookup_matrix_id(matrix_id):
    """
    Find an object by its Matrix ID.

    If the object has been deleted, automatically cleans up the registry entry
    and returns None (lazy cleanup).

    Args:
        matrix_id (str): The Matrix ID (with or without ^ prefix)

    Returns:
        Object or None: The object with this ID, or None if not found
    """
    # Strip prefix if present
    if matrix_id.startswith(ID_PREFIX):
        matrix_id = matrix_id[1:]

    # Normalize to uppercase
    matrix_id = matrix_id.upper()

    registry = get_registry_script()
    dbref = registry.db.id_to_dbref.get(matrix_id)

    if not dbref:
        return None

    # Look up object by dbref
    from evennia import search_object
    results = search_object(f"#{dbref}")

    if not results:
        # Object was deleted - clean up the registry (lazy cleanup)
        del registry.db.id_to_dbref[matrix_id]
        del registry.db.dbref_to_id[dbref]
        return None

    return results[0]


def get_matrix_id(obj):
    """
    Get the Matrix ID for an object.

    Args:
        obj: The object to look up

    Returns:
        str or None: The Matrix ID with prefix (e.g., "^3K7MQ5"), or None if not registered
    """
    if not obj or not obj.pk:
        return None

    registry = get_registry_script()
    dbref = obj.id

    matrix_id = registry.db.dbref_to_id.get(dbref)
    return ID_PREFIX + matrix_id if matrix_id else None


def get_registry_stats():
    """
    Get statistics about the Matrix ID registry.

    Returns:
        dict: Statistics including total_ids, capacity, usage_percent
    """
    registry = get_registry_script()
    total_ids = len(registry.db.id_to_dbref)
    capacity = 32 ** ID_LENGTH
    usage_percent = (total_ids / capacity) * 100

    return {
        'total_ids': total_ids,
        'capacity': capacity,
        'usage_percent': usage_percent,
        'id_length': ID_LENGTH,
        'prefix': ID_PREFIX
    }
