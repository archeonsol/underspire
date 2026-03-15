"""
Vehicles: drivable objects with an interior room. Enter/exit, start/stop engine, drive <dir>.
Uses the driving skill for movement. Interior is a separate room; when you enter you go there,
when you drive the vehicle moves and exits put you at the vehicle's new location.
Vehicles have a parts system (engine, transmission, brakes, etc.) that can be damaged and repaired.
"""
from evennia import DefaultObject
from evennia.utils.create import create_object
from evennia.objects.objects import DefaultExit

from .rooms import Room  # noqa: E402

try:
    from world.vehicle_parts import (
        default_parts,
        default_part_types,
        get_part_condition as _get_part_condition,
        set_part_condition as _set_part_condition,
        damage_part as _damage_part,
        repair_part as _repair_part,
        can_start_engine,
        roll_stall_chance,
        drive_failure_modifier,
        VEHICLE_PART_IDS,
        PART_DISPLAY_NAMES,
        condition_description as _condition_description,
    )
except ImportError:
    default_parts = lambda: {}
    default_part_types = lambda: {}
    _get_part_condition = lambda v, p: 100
    _set_part_condition = lambda v, p, x: None
    _damage_part = lambda v, p, a: 100
    _repair_part = lambda v, p, a: 100
    can_start_engine = lambda v: (True, "")
    roll_stall_chance = lambda v: False
    drive_failure_modifier = lambda v: 0.0
    VEHICLE_PART_IDS = []
    PART_DISPLAY_NAMES = {}
    _condition_description = lambda c: "ok"


# Reuse room's default-welcome check for outside view
_DEFAULT_WELCOME_MARKER = "evennia.com"
_DEFAULT_PLACE_DESC = "A place. Nothing much to note."


class VehicleInterior(Room):
    """
    Room representing the inside of a vehicle. db.vehicle points to the Vehicle object.
    No location (rooms don't have one). Movement is via the drive command.
    """
    default_description = (
        "Worn upholstery, a faint smell of oil and old vinyl. The steering column and dash sit in front of you; "
        "through the windscreen you can see outside. Start the engine with |wstart|n, then |wdrive <direction>|n to move. "
        "|wexit|n to get out."
    )

    def _exterior_room(self):
        """The room where the vehicle is (the outside world)."""
        vehicle = self.db.vehicle
        return getattr(vehicle, "location", None) if vehicle else None

    def _exterior_exits(self):
        """List of exit names (e.g. ['south', 'east']) from the vehicle's current location."""
        room = self._exterior_room()
        if not room:
            return []
        return [
            (obj.key or "").strip() or "out"
            for obj in (room.contents or [])
            if isinstance(obj, DefaultExit) and getattr(obj, "destination", None)
        ]

    def _exterior_display_desc(self, room, looker, **kwargs):
        """Get the exterior room's description, with default substitution for stock welcome text."""
        if hasattr(room, "get_display_desc"):
            return room.get_display_desc(looker, **kwargs)
        raw = (room.db.desc or getattr(room, "default_description", "") or "").strip()
        if not raw or _DEFAULT_WELCOME_MARKER.lower() in raw.lower():
            return getattr(room, "default_description", _DEFAULT_PLACE_DESC) or _DEFAULT_PLACE_DESC
        return raw

    def _dashboard_block(self, vehicle):
        """Build an artistic dashboard line with colors (engine, fuel, temp, warnings)."""
        running = getattr(vehicle.db, "engine_running", False)
        try:
            from world.vehicle_parts import VEHICLE_PART_IDS, PART_DISPLAY_NAMES
            parts = getattr(vehicle.db, "vehicle_parts", None) or {}
            bad = [p for p in VEHICLE_PART_IDS if (parts.get(p, 100) or 100) < 50]
            warn = ", ".join(PART_DISPLAY_NAMES.get(p, p) for p in bad) if bad else None
        except ImportError:
            warn = None
        # x256: |025 dim blue, |500 red, |050 green, |550 yellow, |n reset
        engine_text = "|050 RUNNING|n" if running else "|x OFF|n"
        fuel_bar = "|050██████████|n" if not warn else "|550██████░░░░|n"
        temp_text = "|025 NORMAL|n" if not warn else "|550 CHECK|n"
        lines = [
            "|025┌─ DASHBOARD ───────────────────┐|n",
            f"|025│|n  ENGINE   {engine_text}     |025│|n",
            f"|025│|n  FUEL     |n {fuel_bar}   |025│|n",
            f"|025│|n  COOLANT  {temp_text}     |025│|n",
        ]
        if warn:
            lines.append(f"|025│|n  |550⚠ {warn[:24]:<24} |025│|n")
        lines.append("|025└───────────────────────────────┘|n")
        return "\n".join(lines)

    def get_display_desc(self, looker, **kwargs):
        vehicle = self.db.vehicle
        if vehicle:
            base = self.db.desc or self.default_description
            out = base
            out += "\n\n" + self._dashboard_block(vehicle)
            room = self._exterior_room()
            if room:
                room_name = room.get_display_name(looker, **kwargs) if hasattr(room, "get_display_name") else (room.key or "Unknown")
                exterior_desc = self._exterior_display_desc(room, looker, **kwargs)
                out += "\n\n|025─────────────────────────────────────|n"
                out += "\n|wOUTSIDE|n (through the windscreen): |w" + room_name + "|n"
                out += "\n|025─────────────────────────────────────|n\n"
                out += exterior_desc
            return out
        return self.db.desc or self.default_description

    def get_outside_block(self, looker, **kwargs):
        """Return only the 'outside' section (windscreen view + exits) for use after arriving."""
        vehicle = self.db.vehicle
        if not vehicle:
            return ""
        room = self._exterior_room()
        if not room:
            return ""
        room_name = room.get_display_name(looker, **kwargs) if hasattr(room, "get_display_name") else (room.key or "Unknown")
        exterior_desc = self._exterior_display_desc(room, looker, **kwargs)
        exit_names = self._exterior_exits()
        exits_str = ", ".join(exit_names) if exit_names else "no exits"
        block = "|025─────────────────────────────────────|n\n"
        block += "|wOUTSIDE|n (through the windscreen): |w" + room_name + "|n\n"
        block += "|025─────────────────────────────────────|n\n\n"
        block += exterior_desc
        block += "\n\n|wExits (drive):|n " + exits_str + "."
        return block

    def get_display_exits(self, looker, **kwargs):
        """Show the outside room's exits as driveable directions."""
        vehicle = self.db.vehicle
        if not vehicle:
            return ""
        exit_names = self._exterior_exits()
        if not exit_names:
            if vehicle.engine_running:
                return "\n|wDrive:|n No exits from this location. Use |wdrive <direction>|n when there are exits."
            return "\n|wDrive:|n Start the engine first, then |wdrive <direction>|n."
        exits_str = ", ".join(exit_names)
        if vehicle.engine_running:
            return f"\n|wExits (drive):|n {exits_str}.  Use |wdrive <direction>|n (e.g. |wdrive {exit_names[0]}|n)."
        return f"\n|wExits (drive):|n {exits_str}.  Start the engine first, then |wdrive <direction>|n."


class Vehicle(DefaultObject):
    """
    A drivable vehicle with an interior. Place the vehicle in a room; when characters
    enter they go to the interior room. Drive <direction> moves the vehicle (and everyone
    inside stays in the interior; when they exit they appear at the vehicle's current location).
    """
    def at_object_creation(self):
        self.db.engine_running = False
        self.db.interior = None  # set in _ensure_interior
        self.db.driving_skill = "driving"
        self.db.vehicle_parts = default_parts()
        self.db.vehicle_part_types = default_part_types()
        self._ensure_interior()

    def _ensure_interior(self):
        """Create or return the interior room for this vehicle."""
        if self.db.interior:
            return self.db.interior
        key = f"Inside the {self.key}"
        interior = create_object(
            "typeclasses.vehicles.VehicleInterior",
            key=key,
            location=None,
        )
        if interior:
            interior.db.vehicle = self
            interior.db.desc = None  # use VehicleInterior.default_description (flavorful)
            self.db.interior = interior
        return self.db.interior

    @property
    def interior(self):
        return self._ensure_interior()

    def start_engine(self):
        ok, msg = can_start_engine(self)
        if not ok:
            return False, msg
        self.db.engine_running = True
        return True, None

    def stop_engine(self):
        self.db.engine_running = False

    @property
    def engine_running(self):
        return bool(self.db.engine_running)

    def get_part_condition(self, part_id):
        return _get_part_condition(self, part_id)

    def set_part_condition(self, part_id, value):
        _set_part_condition(self, part_id, value)

    def damage_part(self, part_id, amount):
        return _damage_part(self, part_id, amount)

    def repair_part(self, part_id, amount):
        return _repair_part(self, part_id, amount)

    def drive_failure_modifier(self):
        return drive_failure_modifier(self)

    def roll_stall_chance(self):
        return roll_stall_chance(self)

    def get_exit(self, direction):
        """Find an exit from the vehicle's current room in the given direction (e.g. 'east', 'e')."""
        room = self.location
        if not room or not direction:
            return None
        d = direction.strip().lower()
        dir_aliases = {
            "n": "north", "s": "south", "e": "east", "w": "west",
            "ne": "northeast", "nw": "northwest", "se": "southeast", "sw": "southwest",
            "u": "up", "d": "down",
        }
        d = dir_aliases.get(d, d)
        # All names that mean this direction (e.g. north -> north, n)
        d_names = {d}
        for short, long in dir_aliases.items():
            if long == d:
                d_names.add(short)
        for obj in (room.contents or []):
            if not isinstance(obj, DefaultExit) or not getattr(obj, "destination", None):
                continue
            key = (obj.key or "").strip().lower()
            raw_aliases = getattr(obj, "aliases", None)
            if isinstance(raw_aliases, str):
                exit_aliases = [a.strip().lower() for a in raw_aliases.split(",") if a.strip()]
            elif hasattr(raw_aliases, "all"):
                exit_aliases = [str(a).strip().lower() for a in raw_aliases.all() if str(a).strip()]
            else:
                exit_aliases = [str(a).strip().lower() for a in (raw_aliases or []) if str(a).strip()]
            if key in d_names or d in exit_aliases or any(a in d_names for a in exit_aliases):
                return obj
        return None
