"""
Station access control, ownership management, and validation helpers.

Access model:
  Bar:
    - Manager (db.manager_id): full control
    - Employees (db.employees list of character ids): can serve/prepare
    - Anyone: can view menu

  Kitchenette:
    - Owner (resolved via linked door or db.owner_id): full control
    - Trusted characters (trust category "feed"): can prepare
    - Anyone else: no access

Kitchenette ownership is auto-synced from the rentable door system.
"""

from __future__ import annotations


# ══════════════════════════════════════════════════════════════════════════════
#  Bar access helpers
# ══════════════════════════════════════════════════════════════════════════════

def is_bar_manager(character, station) -> bool:
    """True if character is the manager of this bar station."""
    manager_id = getattr(station.db, "manager_id", None)
    if not manager_id:
        return False
    return manager_id == getattr(character, "id", None)


def is_bar_employee(character, station) -> bool:
    """True if character is an employee (or manager) of this bar station."""
    if is_bar_manager(character, station):
        return True
    employees = list(getattr(station.db, "employees", None) or [])
    char_id = getattr(character, "id", None)
    return char_id in employees


def is_staff(character) -> bool:
    """True if character has Builder or higher permissions."""
    try:
        return character.locks.check_lockstring(character, "perm(Builder)")
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  Kitchenette ownership helpers
# ══════════════════════════════════════════════════════════════════════════════

def get_kitchenette_owner_id(station) -> int | None:
    """
    Return the owner's character id for a kitchenette.

    Checks db.linked_door_id first (auto-follows current tenant),
    then falls back to db.owner_id (manually set).
    """
    door_id = getattr(station.db, "linked_door_id", None)
    if door_id:
        try:
            from evennia.utils.search import search_object
            results = search_object(f"#{door_id}")
            if results:
                door = results[0]
                tenant_id = getattr(door.db, "rent_tenant_id", None)
                if tenant_id:
                    return tenant_id
        except Exception:
            pass
    return getattr(station.db, "owner_id", None)


def is_kitchenette_owner(character, station) -> bool:
    """True if character owns (or rents) this kitchenette."""
    owner_id = get_kitchenette_owner_id(station)
    if not owner_id:
        return False
    return owner_id == getattr(character, "id", None)


def is_kitchenette_trusted(character, station) -> bool:
    """
    True if character is trusted by the owner to use the kitchenette.
    Checks the trust system (category 'feed') if available.
    """
    if is_kitchenette_owner(character, station):
        return True
    owner_id = get_kitchenette_owner_id(station)
    if not owner_id:
        return False
    try:
        from evennia.utils.search import search_object
        results = search_object(f"#{owner_id}")
        if not results:
            return False
        owner = results[0]
        trusted = list(getattr(owner.db, "trusted_feed", None) or [])
        return getattr(character, "id", None) in trusted
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  General access check
# ══════════════════════════════════════════════════════════════════════════════

def can_use_station(character, station) -> tuple:
    """
    Check whether character may prepare items at this station.

    Returns:
        (allowed: bool, reason: str)
    """
    if is_staff(character):
        return True, ""

    station_type = getattr(station.db, "station_type", "kitchenette")

    if station_type == "bar":
        if is_bar_employee(character, station):
            return True, ""
        return False, "You're not an employee of this bar."

    elif station_type == "kitchenette":
        if is_kitchenette_owner(character, station):
            return True, ""
        if is_kitchenette_trusted(character, station):
            return True, ""
        owner_id = get_kitchenette_owner_id(station)
        if not owner_id:
            return False, "This kitchenette has no owner. It can't be used."
        return False, "This isn't your kitchenette."

    return False, "Unknown station type."


def can_manage_station(character, station) -> tuple:
    """
    Check whether character may manage recipes and settings on this station.

    Returns:
        (allowed: bool, reason: str)
    """
    if is_staff(character):
        return True, ""

    station_type = getattr(station.db, "station_type", "kitchenette")

    if station_type == "bar":
        if is_bar_manager(character, station):
            return True, ""
        return False, "Only the bar manager can do that."

    elif station_type == "kitchenette":
        if is_kitchenette_owner(character, station):
            return True, ""
        return False, "Only the kitchenette owner can do that."

    return False, "Unknown station type."


# ══════════════════════════════════════════════════════════════════════════════
#  Base ingredient validation
# ══════════════════════════════════════════════════════════════════════════════

def _validate_base_for_station(station, base_key: str) -> tuple:
    """
    Check if a base ingredient is allowed on this station type.

    Bar: alcohol only.
    Kitchenette: food and non-alcoholic drinks only.

    Returns:
        (allowed: bool, reason: str)
    """
    from world.food.ingredients import get_base
    base = get_base(base_key)
    if not base:
        return False, "Unknown ingredient."

    station_type = getattr(station.db, "station_type", "kitchenette")
    category = base.get("category", "food")

    if station_type == "bar":
        if category != "alcohol":
            return False, "This bar only serves alcoholic drinks."
    elif station_type == "kitchenette":
        if category == "alcohol":
            return False, "This kitchenette doesn't serve alcohol. Use a bar."

    return True, ""


# ══════════════════════════════════════════════════════════════════════════════
#  Kitchenette ownership sync (called from rentable_doors.py hooks)
# ══════════════════════════════════════════════════════════════════════════════

def _get_rooms_behind_exit(exit_obj) -> list:
    """
    Return a list of rooms accessible behind a rentable exit.
    Walks the destination room and any rooms reachable from it
    that are not themselves behind another rentable door.
    """
    dest = getattr(exit_obj, "destination", None)
    if not dest:
        return []

    visited = set()
    to_visit = [dest]
    rooms = []

    while to_visit:
        room = to_visit.pop()
        if room.id in visited:
            continue
        visited.add(room.id)
        rooms.append(room)

        # Walk exits from this room to find connected private rooms
        for ex in room.exits:
            next_dest = getattr(ex, "destination", None)
            if not next_dest or next_dest.id in visited:
                continue
            # Don't cross into other rentable doors
            if getattr(ex.db, "rentable", False):
                continue
            to_visit.append(next_dest)

    return rooms


def sync_kitchenette_ownership(character, exit_obj):
    """
    After a character rents an apartment, set the owner on any kitchenette
    objects found in the rooms behind the exit.

    Called from world.rpg.rentable_doors.do_rent after successful rent.
    """
    try:
        rooms = _get_rooms_behind_exit(exit_obj)
        for room in rooms:
            for obj in room.contents:
                if getattr(obj.db, "station_type", None) == "kitchenette":
                    obj.db.owner_id = character.id
    except Exception:
        pass


def clear_kitchenette_ownership(exit_obj):
    """
    After a tenant vacates, clear the owner on any kitchenette objects
    found in the rooms behind the exit.

    Called from world.rpg.rentable_doors.do_vacate.
    """
    try:
        rooms = _get_rooms_behind_exit(exit_obj)
        for room in rooms:
            for obj in room.contents:
                if getattr(obj.db, "station_type", None) == "kitchenette":
                    obj.db.owner_id = None
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  Find station helper
# ══════════════════════════════════════════════════════════════════════════════

def find_station_in_room(caller, arg: str, station_type: str = None):
    """
    Find a bar or kitchenette station in the caller's current room.

    Args:
        caller:       The character searching.
        arg:          Name or partial name of the station.
        station_type: If given, only match stations of this type ("bar"/"kitchenette").

    Returns:
        The station object, or None if not found (error already sent to caller).
    """
    if not caller.location:
        caller.msg("You aren't anywhere.")
        return None

    candidates = []
    for obj in caller.location.contents:
        stype = getattr(obj.db, "station_type", None)
        if not stype:
            continue
        if station_type and stype != station_type:
            continue
        candidates.append(obj)

    if not candidates:
        if station_type:
            caller.msg(f"There is no {station_type} here.")
        else:
            caller.msg("There is no bar or kitchenette here.")
        return None

    if not arg:
        if len(candidates) == 1:
            return candidates[0]
        names = ", ".join(obj.key for obj in candidates)
        caller.msg(f"Which station? ({names})")
        return None

    arg_lower = arg.lower()
    matches = [obj for obj in candidates if arg_lower in obj.key.lower()]
    if not matches:
        caller.msg(f"No station called '{arg}' here.")
        return None
    if len(matches) > 1:
        names = ", ".join(obj.key for obj in matches)
        caller.msg(f"Which station? ({names})")
        return None
    return matches[0]
