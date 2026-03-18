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
