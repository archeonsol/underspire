"""
Tunnel autopilot: drives a vehicle through a tagged tunnel network with delays.

Tunnel rooms use tags only (see module docstring in repo / builder docs):
- vehicle_access: tunnel (and usually street at endpoints)
- tunnel_network: e.g. tunnel_slums_guild — links all segments
- tunnel_endpoint: slum_exit, guild_exit, etc. — marks each end
"""

from collections import deque

from evennia.utils import delay
from evennia.utils.search import search_object, search_tag
from evennia.objects.objects import DefaultExit

from world.vehicle_movement import _after_vehicle_move_hook, execute_vehicle_move

# Maps a sector name to the endpoint tag to reach when autopiloting TO that sector.
SECTOR_TO_ENDPOINT = {
    "slums": "slum_exit",
    "guild": "guild_exit",
    "bourgeois": "bourgeois_exit",
    "elite": "elite_exit",
}

# Reverse: endpoint tag → sector name (for display / validation)
ENDPOINT_TO_SECTOR = {v: k for k, v in SECTOR_TO_ENDPOINT.items()}

AUTOPILOT_STEP_DELAY = {
    "slow": 6,
    "normal": 4,
    "fast": 2,
}


def _get_tunnel_network(room):
    """Return the tunnel network tag for this room, or None."""
    if not room or not hasattr(room, "tags"):
        return None
    try:
        tags = room.tags.get(category="tunnel_network", return_list=True) or []
    except TypeError:
        tags = []
    return tags[0] if tags else None


def _get_tunnel_endpoints(network_tag):
    """
    Find endpoint rooms in a tunnel network.
    Returns dict: {endpoint_tag: room_obj, ...}
    """
    if not network_tag:
        return {}
    try:
        all_rooms = search_tag(network_tag, category="tunnel_network") or []
    except Exception:
        all_rooms = []
    endpoints = {}
    for room in all_rooms:
        try:
            ep_tags = room.tags.get(category="tunnel_endpoint", return_list=True) or []
        except TypeError:
            ep_tags = []
        for tag in ep_tags:
            if tag in ENDPOINT_TO_SECTOR:
                endpoints[tag] = room
    return endpoints


def _get_valid_destinations(room):
    """
    From this room, what sectors can you autopilot to?
    Returns a list of sector name strings, or empty list if not in a tunnel or no valid hop.
    """
    network = _get_tunnel_network(room)
    if not network:
        return []

    endpoints = _get_tunnel_endpoints(network)
    if not endpoints:
        return []

    try:
        current_ep_tags = room.tags.get(category="tunnel_endpoint", return_list=True) or []
    except TypeError:
        current_ep_tags = []

    destinations = []
    for ep_tag, ep_room in endpoints.items():
        sector = ENDPOINT_TO_SECTOR.get(ep_tag)
        if not sector:
            continue
        if ep_tag in current_ep_tags:
            continue
        destinations.append(sector)
    return destinations


def _find_tunnel_route(start_room, destination_sector):
    """
    BFS from start_room to the endpoint room for destination_sector.
    Only traverses rooms in the same tunnel network.
    Returns a list of room objects (the path, excluding start), or None.
    """
    if not start_room:
        return None

    network = _get_tunnel_network(start_room)
    if not network:
        return None

    dest_sector = (destination_sector or "").strip().lower()
    target_ep_tag = SECTOR_TO_ENDPOINT.get(dest_sector)
    if not target_ep_tag:
        return None

    endpoints = _get_tunnel_endpoints(network)
    target_room = endpoints.get(target_ep_tag)
    if not target_room:
        return None

    visited = {start_room.id}
    queue = deque([(start_room, [])])

    while queue:
        current, path = queue.popleft()

        for obj in current.contents:
            if not isinstance(obj, DefaultExit) or not getattr(obj, "destination", None):
                continue
            dest = obj.destination
            if dest.id in visited:
                continue

            visited.add(dest.id)
            new_path = path + [dest]

            if dest.id == target_room.id:
                return new_path

            dest_network = _get_tunnel_network(dest)
            if dest_network != network:
                continue

            queue.append((dest, new_path))

    return None


def cancel_autopilot(vehicle, reason=""):
    """Stop autopilot. Vehicle remains where it is."""
    if not vehicle:
        return
    vehicle.db.autopilot_active = False
    vehicle.db.autopilot_route = []
    vehicle.db.autopilot_step = 0
    vehicle.db.autopilot_destination = ""
    msg = "|y[AUTOPILOT] Disengaged."
    if reason:
        msg += f" {reason}"
    msg += "|n"
    _msg_all_vehicle_occupants(vehicle, msg)


def start_autopilot(vehicle, driver, destination_sector):
    """
    Begin autopilot toward a sector endpoint. Works from any room in the tunnel.
    Returns (success: bool, message: str).
    """
    if not getattr(vehicle.db, "engine_running", False):
        return False, "Engine must be running."

    if getattr(vehicle.db, "vehicle_type", None) == "aerial":
        return False, "AVs don't use tunnels. Fly through the shaft."

    current_room = vehicle.location
    if not current_room:
        return False, "Vehicle is nowhere."

    network = _get_tunnel_network(current_room)
    if not network:
        return False, "You're not in a tunnel. Drive to a tunnel entrance first."

    destination_sector = (destination_sector or "").strip().lower()

    valid = _get_valid_destinations(current_room)
    if not valid:
        return False, "You're at an endpoint. Drive out of the tunnel."

    if destination_sector not in valid:
        valid_str = " or ".join(f"|w{v}|n" for v in valid)
        return False, f"This tunnel connects to {valid_str}. Pick one of those."

    route = _find_tunnel_route(current_room, destination_sector)
    if not route:
        return False, f"No route to {destination_sector}. The tunnel may be blocked."

    if getattr(vehicle.db, "autopilot_active", False):
        cancel_autopilot(vehicle, reason="Rerouting.")

    vehicle.db.autopilot_active = True
    vehicle.db.autopilot_route = [r.id for r in route]
    vehicle.db.autopilot_step = 0
    vehicle.db.autopilot_driver = getattr(driver, "id", None)
    vehicle.db.autopilot_destination = destination_sector

    speed = vehicle.db.speed_class or "normal"
    step_delay = AUTOPILOT_STEP_DELAY.get(speed, 4)

    if driver:
        driver.msg(
            f"|g[AUTOPILOT] Engaged. Heading to {destination_sector}: {len(route)} segments. "
            f"ETA ~{len(route) * step_delay}s.|n"
        )
    _msg_vehicle_occupants(vehicle, driver, "|x[AUTOPILOT] Route set. Hold on.|n")

    delay(step_delay, _autopilot_step, vehicle.id)

    return True, ""


def _autopilot_step(vehicle_id):
    """Execute one step of the autopilot route."""
    results = search_object(f"#{vehicle_id}")
    if not results:
        return
    vehicle = results[0]

    from typeclasses.vehicles import Motorcycle, _can_vehicle_enter

    if not getattr(vehicle.db, "autopilot_active", False):
        return

    if not getattr(vehicle.db, "engine_running", False):
        cancel_autopilot(vehicle, reason="Engine died.")
        return

    route_ids = vehicle.db.autopilot_route or []
    step = int(getattr(vehicle.db, "autopilot_step", 0) or 0)

    if step >= len(route_ids):
        _complete_autopilot(vehicle)
        return

    next_id = route_ids[step]
    next_results = search_object(f"#{next_id}")
    if not next_results:
        cancel_autopilot(vehicle, reason="Route blocked.")
        return
    next_room = next_results[0]

    allowed, reason = _can_vehicle_enter(vehicle, next_room)
    if not allowed:
        cancel_autopilot(vehicle, reason=f"Route blocked: {reason}")
        return

    current_room = vehicle.location
    if not current_room:
        cancel_autopilot(vehicle, reason="Vehicle is nowhere.")
        return

    exit_obj = None
    for obj in current_room.contents:
        if isinstance(obj, DefaultExit) and getattr(obj, "destination", None) == next_room:
            exit_obj = obj
            break

    if not exit_obj:
        cancel_autopilot(vehicle, reason="No exit to next segment.")
        return

    old_room = vehicle.location
    direction = (exit_obj.key or "forward").strip()

    if isinstance(vehicle, Motorcycle) or getattr(vehicle.db, "vehicle_type", None) == "motorcycle":
        vehicle.move_to(next_room, quiet=True)
        rider = getattr(vehicle.db, "rider", None)
        if rider and rider.location == old_room:
            rider.move_to(next_room, quiet=True, move_type="teleport")
        pillion = None
        if getattr(vehicle.db, "has_pillion", False) and old_room:
            try:
                for c in old_room.contents_get(content_type="character"):
                    if c is rider:
                        continue
                    if getattr(c.db, "mounted_on", None) == vehicle:
                        pillion = c
                        break
            except Exception:
                pillion = None
        if pillion and pillion.location == old_room:
            pillion.move_to(next_room, quiet=True, move_type="teleport")
        vname = getattr(vehicle.db, "vehicle_name", None) or vehicle.key
        if old_room:
            old_room.msg_contents(f"{vname} drives {direction}.")
        next_room.msg_contents(f"{vname} arrives through the tunnel.")
        _after_vehicle_move_hook(vehicle, None, next_room, old_room, direction)
    else:
        execute_vehicle_move(vehicle, None, next_room, direction)

    _msg_all_vehicle_occupants(vehicle, f"|x[AUTOPILOT] Segment {step + 1}/{len(route_ids)}.|n")

    vehicle.db.autopilot_step = step + 1

    speed = vehicle.db.speed_class or "normal"
    step_delay = AUTOPILOT_STEP_DELAY.get(speed, 4)
    delay(step_delay, _autopilot_step, vehicle.id)


def _complete_autopilot(vehicle):
    vehicle.db.autopilot_active = False
    vehicle.db.autopilot_route = []
    vehicle.db.autopilot_step = 0
    _msg_all_vehicle_occupants(vehicle, "|g[AUTOPILOT] Destination reached. Disengaging.|n")


def _msg_all_vehicle_occupants(vehicle, message):
    """Send a message to everyone in/on the vehicle."""
    if getattr(vehicle.db, "vehicle_type", None) == "motorcycle":
        rider = getattr(vehicle.db, "rider", None)
        if rider:
            rider.msg(message)
        return
    if getattr(vehicle.db, "has_interior", True) and vehicle.db.interior:
        interior = vehicle.db.interior
        if interior:
            interior.msg_contents(message)


def _msg_vehicle_occupants(vehicle, exclude, message):
    """Send to occupants except the excluded character."""
    if getattr(vehicle.db, "vehicle_type", None) == "motorcycle":
        rider = getattr(vehicle.db, "rider", None)
        if rider and rider != exclude:
            rider.msg(message)
        return
    if getattr(vehicle.db, "has_interior", True) and vehicle.db.interior:
        interior = vehicle.db.interior
        if interior:
            interior.msg_contents(message, exclude=exclude)


# Public names for commands / tools
get_tunnel_network = _get_tunnel_network
get_tunnel_endpoints = _get_tunnel_endpoints
get_valid_destinations = _get_valid_destinations
