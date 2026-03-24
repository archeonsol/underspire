"""
Matrix Menu System

EvMenu nodes for Matrix navigation and interaction.

Router Access Menu:
- Lists access points (rooms) connected to a router
- Shows devices in each access point
- Allows routing to device interfaces (creates ephemeral checkpoint/interface rooms)
"""

from evennia.utils.evmenu import EvMenu
from evennia.utils import logger, delay
from world.utils import get_networked_devices, get_router_access_points


def router_main_menu(caller, raw_string, **kwargs):
    """
    Main router interface menu.

    Provides options for routing, proxy management, and browsing access points.
    """
    router = kwargs.get("router")
    if not router:
        router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
    if not router:
        caller.msg("Error: No router found.")
        return None

    # Store router in menu for other nodes
    if hasattr(caller.ndb, '_evmenu'):
        caller.ndb._evmenu.router = router

    text = f"|c=== {router.key} Interface ===|n\n\n"
    text += f"Status: {router.get_status()}\n"

    # Check if caller has a proxy tunnel
    from typeclasses.matrix.avatars import MatrixAvatar
    has_proxy = False
    if isinstance(caller, MatrixAvatar):
        has_proxy = bool(caller.db.proxy_router)

    options = (
        {
            "key": ("a", "route", "access"),
            "desc": "Route to access point",
            "goto": ("route_to_access_point", {"router": router})
        },
        {
            "key": ("b", "browse"),
            "desc": "Browse APs (testing only)",
            "goto": ("browse_access_points", {"router": router})
        },
        {
            "key": ("e", "entry", "back", "previous"),
            "desc": "Route to proxy exit" if has_proxy else "Route to session origin",
            "goto": (_do_route_to_entry_point, {"router": router})
        },
        {
            "key": ("s", "status"),
            "desc": "View proxy status",
            "goto": ("view_proxy_status", {"router": router})
        },
        {
            "key": ("p", "proxy"),
            "desc": "Close proxy tunnel" if has_proxy else "Open proxy tunnel",
            "goto": (_close_proxy_tunnel, {"router": router}) if has_proxy else (_open_proxy_tunnel, {"router": router})
        },
        {
            "key": ("q", "quit", "exit"),
            "desc": "Exit",
            "goto": "router_exit"
        }
    )

    return text, options


def _process_access_point_input(caller, raw_string, **kwargs):
    """
    Process user input for AP Matrix ID.

    This is a goto-callable that validates the input and returns the next node.
    """
    router = kwargs.get("router")
    if not router:
        router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
    if not router:
        caller.msg("|rError: No router found.|n")
        return None

    ap_input = raw_string.strip() if raw_string else ""

    # Empty input - return to prompt
    if not ap_input:
        return ("route_to_access_point", {"router": router})

    # Strip ^ prefix if present
    if ap_input.startswith("^"):
        ap_input = ap_input[1:]

    # Normalize to uppercase
    ap_id = "^" + ap_input.upper()

    # Look up the AP by Matrix ID
    from world.matrix_ids import lookup_matrix_id
    room = lookup_matrix_id(ap_id)

    if not room:
        caller.msg(f"|rAccess point {ap_id} not found.|n")
        return ("route_to_access_point", {"router": router})

    if not hasattr(room, 'db'):
        caller.msg(f"|rInvalid access point.|n")
        return ("route_to_access_point", {"router": router})

    room_router_pk = getattr(room.db, 'network_router', None)
    if room_router_pk != router.pk:
        caller.msg(f"|rAccess point {ap_id} is not connected to this router.|n")
        return ("route_to_access_point", {"router": router})

    # Valid AP, show devices
    return ("access_point_devices", {"room": room, "router": router})


def route_to_access_point(caller, raw_string, **kwargs):
    """
    Prompt for AP Matrix ID and route to it.
    """
    router = kwargs.get("router")
    if not router:
        router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
    if not router:
        caller.msg("|rError: No router found.|n")
        return None

    text = f"|c=== Route to Access Point ===|n\n\n"
    text += "Enter the Matrix ID of the access point you wish to route to.\n"
    text += "Format: ^XXXXXX or XXXXXX\n"

    options = (
        {
            "key": "_default",
            "desc": None,
            "goto": (_process_access_point_input, {"router": router})
        },
        {
            "key": ("q", "back"),
            "desc": "Back to router menu",
            "goto": ("router_main_menu", {"router": router})
        }
    )

    return text, options


def browse_access_points(caller, raw_string, **kwargs):
    """
    Browse all access points connected to this router (testing only).
    """
    router = kwargs.get("router")
    if not router:
        router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
    if not router:
        caller.msg("|rError: No router found.|n")
        return None

    # Find all rooms linked to this router
    linked_rooms = get_router_access_points(router)

    # Sort rooms by key for consistent display
    linked_rooms.sort(key=lambda r: r.key)

    text = f"|c=== {router.key} - Browse APs (testing) ===|n\n\n"

    if not linked_rooms:
        text += "No access points connected to this router.\n"
        text += "(Use 'mlink' in meatspace rooms to connect them to this router)\n"
    else:
        text += f"Connected Access Points: {len(linked_rooms)}\n"

    options = []

    for i, room in enumerate(linked_rooms, 1):
        ap_name = room.key
        matrix_id = room.get_matrix_id() if hasattr(room, 'get_matrix_id') else "^UNKNOWN"

        options.append({
            "desc": f"{ap_name} |m({matrix_id})|n",
            "goto": ("access_point_devices", {"room": room, "router": router})
        })

    options.append({
        "key": ("q", "back"),
        "desc": "Back to router menu",
        "goto": ("router_main_menu", {"router": router})
    })

    return text, options


def access_point_devices(caller, raw_string, **kwargs):
    """
    Show all networked devices in a specific access point.

    Displays devices with their type and allows routing to their interface.
    """
    router = kwargs.get("router")
    room = kwargs.get("room")

    if not router:
        router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
    if not router or not room:
        caller.msg("|rError: Missing router or room data.|n")
        return None

    # Find all networked devices in this room (recursively check inventory)
    devices = get_networked_devices(room)

    # Sort devices by key
    devices.sort(key=lambda d: d.key)

    text = f"|c=== {room.key} - Devices ===|n\n\n"
    text += f"Access Point: |w{room.key}|n\n"
    text += f"Devices: {len(devices)}\n"

    if not devices:
        text += "\nNo networked devices found in this access point.\n"

    options = []

    for device in devices:
        device_type = getattr(device.db, 'device_type', 'unknown')
        matrix_id = device.get_matrix_id() if hasattr(device, 'get_matrix_id') else "^UNKNOWN"

        # Check security level if set
        security = getattr(device.db, 'security_level', 0)
        security_str = f" |r[SEC:{security}]|n" if security > 0 else ""

        display_name = f"{device_type} {matrix_id}"

        options.append({
            "desc": f"Route to {display_name}{security_str}",
            "goto": ("route_to_device", {"device": device, "router": router})
        })

    options.append({
        "key": ("q", "back"),
        "desc": "Back to router menu",
        "goto": ("router_main_menu", {"router": router})
    })

    return text, options


def route_to_device(caller, raw_string, **kwargs):
    """
    Route to a specific device's interface.

    Creates the device's ephemeral checkpoint and interface rooms,
    then teleports the caller to the checkpoint.
    """
    router = kwargs.get("router")
    device = kwargs.get("device")

    if not router:
        router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
    if not device:
        caller.msg("|rError: Device not found.|n")
        return None

    # Get or create the device's ephemeral cluster
    try:
        cluster = device.get_or_create_cluster()
    except Exception as e:
        logger.log_trace(f"matrix_menus.route_to_device get_or_create_cluster: {e}")
        caller.msg(f"|rConnection failed: Unable to establish interface.|n")
        caller.msg(f"Error: {e}")
        return None

    if not cluster:
        caller.msg(f"|rConnection failed: Device interface unavailable.|n")
        return None

    checkpoint = cluster.get('checkpoint')
    interface = cluster.get('interface')

    if not checkpoint or not interface:
        caller.msg(f"|rConnection failed: Incomplete interface cluster.|n")
        return None

    # Get router and access point info for link path
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

        # Move to checkpoint (let Evennia handle auto-look)
        caller.move_to(checkpoint)

        # Announce arrival
        checkpoint.msg_contents(
            f"{caller.key} materializes from the data stream.",
            exclude=[caller]
        )

    delay(0.8, _link_established)

    # Exit the menu
    return None


def _do_route_to_entry_point(caller, raw_string, **kwargs):
    """
    Goto-callable that routes back to the entry point router.

    Traces from avatar -> rig -> meatspace room -> entry router,
    then routes the avatar to that router.
    """
    from typeclasses.matrix.avatars import MatrixAvatar

    router = kwargs.get("router")
    if not router:
        router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None

    if not isinstance(caller, MatrixAvatar):
        caller.msg("|rError: Only Matrix avatars can route to entry points.|n")
        return "router_exit"

    # Get the rig this avatar is connected through
    rig = caller.db.entry_device
    if not rig:
        caller.msg("|rError: No entry device found. Cannot determine entry point.|n")
        return "router_exit"

    # Get the meatspace room the rig is in
    rig_room = rig.location
    if not rig_room:
        caller.msg("|rError: Entry device has no location.|n")
        return "router_exit"

    # Get the router that room is linked to
    entry_router_pk = getattr(rig_room.db, 'network_router', None)
    if not entry_router_pk:
        caller.msg("|rError: Entry location has no network router.|n")
        return "router_exit"

    # Load the entry router
    from typeclasses.matrix.objects import Router
    try:
        entry_router = Router.objects.get(pk=entry_router_pk)
    except Router.DoesNotExist:
        caller.msg("|rError: Entry router not found.|n")
        return "router_exit"

    # Check if we're already at the entry router's location
    if caller.location == entry_router.location:
        caller.msg("|yYou are already at your entry point router.|n")
        return "router_exit"

    # Route to the entry router with delays
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

        # Move to entry router's location (the room it's in)
        destination = entry_router.location
        if not destination:
            caller.msg("|rError: Entry router has no location.|n")
            return

        caller.move_to(destination)

        # Announce arrival
        destination.msg_contents(
            f"{caller.key} materializes from the data stream.",
            exclude=[caller]
        )

    delay(0.8, _routing)

    # Exit the menu after movement
    return None


def router_exit(caller, raw_string, **kwargs):
    """Exit the router access menu."""
    caller.msg("|cDisconnecting from router interface...|n")
    return None


def _open_proxy_tunnel(caller, raw_string, **kwargs):
    """
    Goto-callable to open a proxy tunnel at the current router.

    Cannot open if already have one open.
    """
    from typeclasses.matrix.avatars import MatrixAvatar

    router = kwargs.get("router")
    if not router:
        router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
    if not router:
        caller.msg("|rError: No router found.|n")
        return "router_main_menu"

    if not isinstance(caller, MatrixAvatar):
        caller.msg("|rError: Only Matrix avatars can open proxy tunnels.|n")
        return "router_main_menu"

    # Check if already has proxy
    if caller.db.proxy_router:
        caller.msg("|rYou already have a proxy tunnel open.|n")
        caller.msg("You must close your existing proxy before opening a new one.")
        return "router_main_menu"

    # Open the proxy tunnel
    caller.db.proxy_router = router.pk
    caller.msg(f"|gProxy tunnel opened at {router.key}.|n")
    caller.msg("Your session origin now routes through this proxy.")
    return "router_main_menu"


def _close_proxy_tunnel(caller, raw_string, **kwargs):
    """
    Goto-callable to close the proxy tunnel.

    Can only close from session origin router or the proxy router itself.
    """
    from typeclasses.matrix.avatars import MatrixAvatar

    router = kwargs.get("router")
    if not router:
        router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None
    if not router:
        caller.msg("|rError: No router found.|n")
        return "router_main_menu"

    if not isinstance(caller, MatrixAvatar):
        caller.msg("|rError: Only Matrix avatars can close proxy tunnels.|n")
        return "router_main_menu"

    # Check if has proxy
    if not caller.db.proxy_router:
        caller.msg("|rYou don't have a proxy tunnel open.|n")
        return "router_main_menu"

    # Get session origin router (from rig's room)
    rig = caller.db.entry_device
    if not rig or not hasattr(rig, 'location'):
        caller.msg("|rError: Cannot determine session origin.|n")
        return "router_main_menu"

    rig_room = rig.location
    if not rig_room:
        caller.msg("|rError: Cannot determine session origin.|n")
        return "router_main_menu"

    session_origin_router_pk = getattr(rig_room.db, 'network_router', None)
    proxy_router_pk = caller.db.proxy_router

    # Check if at session origin or proxy router
    if router.pk != session_origin_router_pk and router.pk != proxy_router_pk:
        caller.msg("|rYou can only close your proxy tunnel from your session origin router or the proxy router itself.|n")
        return "router_main_menu"

    # Close the proxy tunnel
    caller.db.proxy_router = None
    caller.msg(f"|gProxy tunnel closed.|n")
    caller.msg("Your session origin now routes directly to your entry point.")
    return "router_main_menu"


def view_proxy_status(caller, raw_string, **kwargs):
    """
    Display current proxy tunnel status.
    """
    from typeclasses.matrix.avatars import MatrixAvatar

    router = kwargs.get("router")
    if not router:
        router = caller.ndb._evmenu.router if hasattr(caller.ndb, '_evmenu') else None

    text = f"|c=== Proxy Tunnel Status ===|n\n\n"

    if not isinstance(caller, MatrixAvatar):
        text += "|rError: Only Matrix avatars can have proxy tunnels.|n\n"
    elif not caller.db.proxy_router:
        text += "Status: |xNo proxy tunnel active|n\n\n"
        text += "You can open a proxy tunnel at any router to mask your session origin.\n"
    else:
        # Get proxy router info
        try:
            from typeclasses.matrix.objects import Router
            proxy_router = Router.objects.get(pk=caller.db.proxy_router)
            online_status = "|g[ONLINE]|n" if getattr(proxy_router.db, 'online', False) else "|r[OFFLINE]|n"
            text += f"Status: |gProxy tunnel active|n\n\n"
            text += f"Proxy Router: {proxy_router.key} {online_status}\n"
            text += f"Proxy Location: {proxy_router.location.key if proxy_router.location else 'Unknown'}\n\n"
            text += "Your session origin now routes through this proxy.\n"
        except Exception:
            from evennia.utils import logger
            logger.log_trace("matrix_menus: failed to look up proxy router")
            text += "Status: |yProxy tunnel active (router not found)|n\n\n"
            text += "Warning: Proxy router no longer exists.\n\n"

    # Get session origin info
    if isinstance(caller, MatrixAvatar):
        rig = caller.db.entry_device
        if rig and hasattr(rig, 'location') and rig.location:
            rig_room = rig.location
            session_router_pk = getattr(rig_room.db, 'network_router', None)
            if session_router_pk:
                try:
                    from typeclasses.matrix.objects import Router
                    session_router = Router.objects.get(pk=session_router_pk)
                    text += f"Session Origin Router: {session_router.key}\n"
                except Exception:
                    pass

    options = (
        {
            "key": ("q", "back"),
            "desc": "Back to router menu",
            "goto": ("router_main_menu", {"router": router})
        },
    )

    return text, options
