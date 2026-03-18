"""
General game utilities.

This module contains utility functions that are useful across multiple
parts of the game system.
"""



def get_containing_room(obj, max_depth=10):
    """
    Walk up an object's location chain to find the containing Room.

    In Evennia, objects can be nested inside other objects (like items
    in a character's inventory, or a character sitting in a vehicle).
    This function walks up the location chain until it finds an actual
    Room object.

    Args:
        obj: The object to find the containing room for
        max_depth (int): Maximum depth to traverse (prevents infinite loops)

    Returns:
        Room or None: The containing room, or None if not found

    Examples:
        >>> # Room itself
        >>> get_containing_room(room)  # => room
        >>>
        >>> # Item in character inventory
        >>> item.location  # => Character
        >>> get_containing_room(item)  # => Room (where character is)
        >>>
        >>> # Character in a room
        >>> character.location  # => Room
        >>> get_containing_room(character)  # => Room
        >>>
        >>> # Device in inventory
        >>> device.location  # => Character
        >>> get_containing_room(device)  # => Room
    """
    from typeclasses.rooms import Room

    if not obj:
        return None

    # If the object itself is already a room, return it
    if isinstance(obj, Room):
        return obj

    current_location = obj.location
    depth = 0

    while current_location and depth < max_depth:
        if isinstance(current_location, Room):
            return current_location
        current_location = current_location.location
        depth += 1

    return None


def room_has_network_coverage(room):
    """
    Check if a room has active Matrix network coverage.

    Args:
        room: The room object to check

    Returns:
        bool: True if the room has an active and online network router, False otherwise

    Examples:
        >>> room_has_network_coverage(my_room)
        True
        >>> room_has_network_coverage(None)
        False
    """
    if not room:
        return False

    router_dbref = getattr(room.db, 'network_router', None)
    if not router_dbref:
        return False

    # Verify the router exists and is online
    from typeclasses.matrix.objects import Router
    try:
        router = Router.objects.get(pk=router_dbref)
        return getattr(router.db, 'online', False)
    except Router.DoesNotExist:
        return False


def get_networked_devices(room):
    """
    Get all networked devices in a room (recursively searching contents).

    Args:
        room: The room object to search

    Returns:
        list: List of NetworkedMixin objects found in the room

    Examples:
        >>> devices = get_networked_devices(my_room)
        >>> len(devices)
        3
    """
    from typeclasses.matrix.mixins import NetworkedMixin

    devices = []

    def find_devices_recursive(container):
        """Recursively search container and inventory for networked devices."""
        for obj in container.contents:
            if isinstance(obj, NetworkedMixin):
                devices.append(obj)
            # Also search this object's contents (inventory, containers, etc.)
            if hasattr(obj, 'contents'):
                find_devices_recursive(obj)

    if room:
        find_devices_recursive(room)

    return devices


def get_router_access_points(router):
    """
    Get all rooms (access points) linked to a specific router.

    Args:
        router: The Router object

    Returns:
        list: List of Room objects linked to this router

    Examples:
        >>> aps = get_router_access_points(my_router)
        >>> len(aps)
        5
    """
    from typeclasses.rooms import Room

    if not router:
        return []

    linked_rooms = []
    for room in Room.objects.all():
        room_router_pk = getattr(room.db, 'network_router', None)
        if room_router_pk == router.pk:
            linked_rooms.append(room)

    return linked_rooms
