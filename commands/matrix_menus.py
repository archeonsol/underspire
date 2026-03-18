"""
Matrix Menu System

EvMenu nodes for Matrix navigation and interaction.

Router Access Menu:
- Lists access points (rooms) connected to a router
- Shows devices in each access point
- Allows routing to device interfaces (creates ephemeral vestibule/interface rooms)
"""

from evennia.utils.evmenu import EvMenu
from evennia.utils import logger
from typeclasses.matrix.mixins import NetworkedMixin


def router_access_points(caller, raw_string, **kwargs):
    """
    Main menu showing all access points connected to this router.

    An access point is a meatspace room that has been linked to this router
    via the 'mlink' command. Each AP can contain multiple networked devices.
    """
    router = kwargs.get("router")
    if not router:
        # Try to get from menu storage
        router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
    if not router:
        caller.msg("Error: No router found.")
        return None

    # Store router in menu for other nodes
    if hasattr(caller.ndb, '_evmenu'):
        caller.ndb._evmenu.router = router

    # Find all rooms linked to this router
    from evennia.objects.models import ObjectDB
    from typeclasses.rooms import Room

    linked_rooms = []
    for room in Room.objects.all():
        room_router_dbref = getattr(room.db, 'network_router', None)
        if room_router_dbref == router.pk:
            linked_rooms.append(room)

    if not linked_rooms:
        text = f"|c=== {router.key} Access Points ===|n\n\n"
        text += "No access points connected to this router.\n"
        text += "(Use 'mlink' in meatspace rooms to connect them to this router)\n"

        return text, None

    # Sort rooms by key for consistent display
    linked_rooms.sort(key=lambda r: r.key)

    text = f"|c=== {router.key} Access Points ===|n\n\n"
    text += f"Status: {router.get_status()}\n"
    text += f"Connected Access Points: {len(linked_rooms)}\n\n"

    options = []

    for i, room in enumerate(linked_rooms, 1):
        # Count networked devices in this room
        device_count = 0
        for obj in room.contents:
            if isinstance(obj, NetworkedMixin):
                device_count += 1

        ap_name = room.key
        text += f"  |w{i}|n. {ap_name} |x({device_count} device{'s' if device_count != 1 else ''})|n\n"

        options.append({
            "desc": f"Access {ap_name}",
            "goto": ("access_point_devices", {"room": room})
        })

    text += "\n|xe|n. Route to entry point"
    text += "\n|xq|n. Exit router interface"

    options.append({
        "key": ("e", "entry"),
        "desc": "Route to entry point",
        "goto": "route_to_entry_point"
    })

    options.append({
        "key": ("q", "quit", "exit", "back"),
        "desc": "Exit",
        "goto": "router_exit"
    })

    return text, options


def access_point_devices(caller, raw_string, **kwargs):
    """
    Show all networked devices in a specific access point.

    Displays devices with their type and allows routing to their interface.
    """
    # Get router from menu storage
    router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
    room = kwargs.get("room")

    if not router or not room:
        caller.msg("Error: Missing router or room data.")
        return "router_access_points"

    # Find all networked devices in this room
    devices = []
    for obj in room.contents:
        if isinstance(obj, NetworkedMixin):
            devices.append(obj)

    if not devices:
        text = f"|c=== {room.key} ===|n\n\n"
        text += "No networked devices found in this access point.\n\n"
        text += "|xb|n. Back to access points\n"

        return text, [{
            "key": ("b", "back"),
            "desc": "Back",
            "goto": "router_access_points"
        }]

    # Sort devices by key
    devices.sort(key=lambda d: d.key)

    text = f"|c=== {room.key} - Devices ===|n\n\n"
    text += f"Access Point: |w{room.key}|n\n"
    text += f"Devices: {len(devices)}\n\n"

    options = []

    for i, device in enumerate(devices, 1):
        device_type = getattr(device.db, 'device_type', 'unknown')
        device_name = device.key

        # Check security level if set
        security = getattr(device.db, 'security_level', 0)
        security_str = f" |r[SEC:{security}]|n" if security > 0 else ""

        text += f"  |w{i}|n. {device_name} |x({device_type}){security_str}|n\n"

        options.append({
            "desc": f"Route to {device_name}",
            "goto": ("route_to_device", {"device": device})
        })

    text += "\n|xb|n. Back to access points"

    options.append({
        "key": ("b", "back"),
        "desc": "Back",
        "goto": "router_access_points"
    })

    return text, options


def route_to_device(caller, raw_string, **kwargs):
    """
    Route to a specific device's interface.

    Creates the device's ephemeral vestibule and interface rooms,
    then teleports the caller to the vestibule.
    """
    # Get router from menu storage
    router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
    device = kwargs.get("device")

    if not device:
        caller.msg("Error: Device not found.")
        return "router_access_points"

    from evennia.utils import delay

    # Get or create the device's ephemeral cluster
    try:
        cluster = device.get_or_create_cluster()
    except Exception as e:
        logger.log_trace(f"matrix_menus._route_to_device get_or_create_cluster: {e}")
        caller.msg(f"|rConnection failed: Unable to establish interface.|n")
        caller.msg(f"Error: {e}")
        return None

    if not cluster:
        caller.msg(f"|rConnection failed: Device interface unavailable.|n")
        return None

    vestibule = cluster.get('vestibule')
    interface = cluster.get('interface')

    if not vestibule or not interface:
        caller.msg(f"|rConnection failed: Incomplete interface cluster.|n")
        return None

    # Get router and access point info for link path
    router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
    router_name = router.key if router else "unknown"
    access_point_name = device.location.key if device.location else "unknown"
    link_path = f"link://{router_name}/{access_point_name}/{device.key}"

    # Progressive connection messages with delays
    caller.msg(f"|cResolving spanning tree...|n")

    def _link_established():
        caller.msg(f"|gLink established.|n")
        delay(0.8, _route_to_device)

    def _route_to_device():
        caller.msg(f"|cRouting to |w{link_path}|c...|n")
        delay(0.8, _do_move)

    def _do_move():
        # Announce departure to current room
        if caller.location:
            caller.location.msg_contents(
                f"{caller.key} disappears in a flicker of data.",
                exclude=[caller]
            )

        # Move to vestibule (let Evennia handle auto-look)
        caller.move_to(vestibule)

        # Announce arrival
        vestibule.msg_contents(
            f"{caller.key} materializes from the data stream.",
            exclude=[caller]
        )

    delay(0.8, _link_established)

    # Exit the menu
    return None


def route_to_entry_point(caller, raw_string, **kwargs):
    """
    Route back to the entry point router.

    Traces from avatar -> rig -> meatspace room -> entry router,
    then routes the avatar to that router.
    """
    from typeclasses.matrix.avatars import MatrixAvatar

    if not isinstance(caller, MatrixAvatar):
        caller.msg("|rError: Only Matrix avatars can route to entry points.|n")
        return "router_access_points"

    # Get the rig this avatar is connected through
    rig = caller.db.entry_device
    if not rig:
        caller.msg("|rError: No entry device found. Cannot determine entry point.|n")
        return "router_access_points"

    # Get the meatspace room the rig is in
    rig_room = rig.location
    if not rig_room:
        caller.msg("|rError: Entry device has no location.|n")
        return "router_access_points"

    # Get the router that room is linked to
    entry_router_pk = getattr(rig_room.db, 'network_router', None)
    if not entry_router_pk:
        caller.msg("|rError: Entry location has no network router.|n")
        return "router_access_points"

    # Load the entry router
    from typeclasses.matrix.objects import Router
    try:
        entry_router = Router.objects.get(pk=entry_router_pk)
    except Router.DoesNotExist:
        caller.msg("|rError: Entry router not found.|n")
        return "router_access_points"

    # Check if we're already at the entry router
    if caller.location == entry_router:
        caller.msg("|yYou are already at your entry point router.|n")
        return "router_access_points"

    # Route to the entry router with delays
    from evennia.utils import delay

    caller.msg(f"|cResolving route to entry point...|n")

    def _routing():
        caller.msg(f"|cRouting to |w{entry_router.key}|c...|n")
        delay(0.8, _do_move)

    def _do_move():
        # Announce departure
        if caller.location:
            caller.location.msg_contents(
                f"{caller.key} disappears in a flicker of data.",
                exclude=[caller]
            )

        # Move to entry router
        caller.move_to(entry_router)

        # Announce arrival
        entry_router.msg_contents(
            f"{caller.key} materializes from the data stream.",
            exclude=[caller]
        )

    delay(0.8, _routing)

    # Exit the menu
    return None


def router_exit(caller, raw_string, **kwargs):
    """Exit the router access menu."""
    caller.msg("|cDisconnecting from router interface...|n")
    return None


# Helper function to get all rooms linked to a router
def get_linked_rooms(router):
    """
    Get all rooms linked to a specific router.

    Args:
        router: The Router object

    Returns:
        list: List of Room objects linked to this router
    """
    from evennia.objects.models import ObjectDB
    from typeclasses.rooms import Room

    linked_rooms = []
    for room in Room.objects.all():
        room_router_dbref = getattr(room.db, 'network_router', None)
        if room_router_dbref == router.pk:
            linked_rooms.append(room)

    return linked_rooms


# Helper function to get all networked devices in a room
def get_networked_devices(room):
    """
    Get all networked devices in a room.

    Args:
        room: The Room object

    Returns:
        list: List of NetworkedMixin objects in the room
    """
    devices = []
    for obj in room.contents:
        if isinstance(obj, NetworkedMixin):
            devices.append(obj)

    return devices
