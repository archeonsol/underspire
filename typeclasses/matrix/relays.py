"""
Matrix Relays

Infrastructure classes for handling network routing and connectivity.
Relays are not physical objects or rooms - they're pure logic that tracks
what's connected to each network segment.

Relay - Handles connection routing for a network segment
RelayManager - Singleton for managing all relays in the game
"""


class Relay:
    """
    Network routing infrastructure for a segment of the Matrix.

    Relays handle the connection logic between meatspace and the Matrix.
    Each relay has wireless coverage over certain physical rooms and connects
    to a specific Matrix room (spine node). They track all connected devices
    and provide routing information.

    This is not an in-game object - it's pure infrastructure.

    Attributes:
        key (str): Unique identifier for this relay (e.g. "spine-b-relay-2")
        matrix_room (MatrixNode): The virtual room in the Matrix this relay connects to
        coverage_rooms (list): Physical room objects covered by this relay's wireless
        hardwired_ports (dict): Mapping of port identifiers to room objects
    """

    def __init__(self, key, matrix_room=None):
        """
        Initialize a new relay.

        Args:
            key (str): Unique identifier for this relay
            matrix_room (MatrixNode): The Matrix room this relay connects to
        """
        self.key = key
        self.matrix_room = matrix_room
        self.coverage_rooms = []
        self.hardwired_ports = {}  # port_id: room_obj

    def add_coverage(self, room):
        """
        Add a physical room to this relay's wireless coverage area.

        Args:
            room: Room object to add to coverage
        """
        if room not in self.coverage_rooms:
            self.coverage_rooms.append(room)

    def remove_coverage(self, room):
        """
        Remove a physical room from this relay's wireless coverage.

        Args:
            room: Room object to remove from coverage
        """
        if room in self.coverage_rooms:
            self.coverage_rooms.remove(room)

    def add_hardwired_port(self, port_id, room):
        """
        Add a hardwired connection port.

        Args:
            port_id (str): Identifier for the port (e.g. "port-42-building-z")
            room: Room object where the port is located
        """
        self.hardwired_ports[port_id] = room

    def get_connected_devices(self):
        """
        Get all Matrix-connected devices accessible through this relay.

        Returns:
            list: All MatrixConnected objects in coverage or hardwired to this relay
        """
        devices = []

        # Wireless devices in coverage
        for room in self.coverage_rooms:
            for obj in room.contents:
                if hasattr(obj, 'db') and hasattr(obj.db, 'connection_type'):
                    if obj.db.connection_type == "wireless":
                        devices.append(obj)

        # Hardwired devices at ports
        for room in self.hardwired_ports.values():
            for obj in room.contents:
                if hasattr(obj, 'db') and hasattr(obj.db, 'connection_type'):
                    if obj.db.connection_type == "hardwired":
                        devices.append(obj)

        return devices

    def get_connected_hubs(self):
        """
        Get all hubs connected to this relay.

        Returns:
            list: All hub objects connected through this relay
        """
        # TODO: Implement hub tracking
        # Hubs will be special MatrixConnected objects
        return []

    def is_room_in_coverage(self, room):
        """
        Check if a physical room is covered by this relay's wireless.

        Args:
            room: Room object to check

        Returns:
            bool: True if room is in coverage area
        """
        return room in self.coverage_rooms

    def has_hardwired_port(self, port_id):
        """
        Check if a specific hardwired port exists on this relay.

        Args:
            port_id (str): Port identifier to check

        Returns:
            bool: True if port exists
        """
        return port_id in self.hardwired_ports

    def __str__(self):
        return f"Relay({self.key})"

    def __repr__(self):
        return f"<Relay '{self.key}' covering {len(self.coverage_rooms)} rooms>"
        """


class RelayManager:
    """
    Singleton manager for all relays in the game.

    Provides lookup and management functions for the relay infrastructure.
    Relays should be created and registered with this manager during world setup.
    """

    _instance = None
    _relays = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RelayManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    def register_relay(cls, relay):
        """
        Register a relay with the manager.

        Args:
            relay (Relay): Relay instance to register
        """
        cls._relays[relay.key] = relay

    @classmethod
    def get_relay(cls, key):
        """
        Get a relay by its key.

        Args:
            key (str): Relay identifier

        Returns:
            Relay: The relay object, or None if not found
        """
        return cls._relays.get(key)

    @classmethod
    def get_relay_for_room(cls, room):
        """
        Find which relay covers a given physical room.

        Args:
            room: Room object to check

        Returns:
            Relay: The relay covering this room, or None if no coverage
        """
        for relay in cls._relays.values():
            if relay.is_room_in_coverage(room):
                return relay
        return None

    @classmethod
    def get_relay_for_port(cls, port_id):
        """
        Find which relay has a specific hardwired port.

        Args:
            port_id (str): Port identifier

        Returns:
            Relay: The relay with this port, or None if not found
        """
        for relay in cls._relays.values():
            if relay.has_hardwired_port(port_id):
                return relay
        return None

    @classmethod
    def list_all_relays(cls):
        """
        Get all registered relays.

        Returns:
            list: All Relay objects
        """
        return list(cls._relays.values())

    @classmethod
    def clear_all(cls):
        """Clear all registered relays. Mainly for testing."""
        cls._relays = {}
