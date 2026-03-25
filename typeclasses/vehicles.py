"""
Vehicles: drivable objects with an interior room (or open motorcycles). Enter/exit, start/stop engine,
drive / fly <dir>. Uses driving or piloting skill. Interior is a separate room for enclosed types;
when you drive the vehicle moves and exits put you at the vehicle's new location.

Each enclosed vehicle has exactly ONE persistent interior. Items dropped inside stay when you exit.
"""
import re

from evennia.contrib.base_systems.components import ComponentHolderMixin, ComponentProperty
from typeclasses.matrix.mixins.matrix_id import MatrixIdMixin
from typeclasses.mixins.enterable import EnterableMixin
from typeclasses.objects import Object
from evennia.utils.create import create_object
from evennia.utils.search import search_tag, search_object
from evennia.objects.objects import DefaultExit
from world.vehicle_components import DriveComponent, FuelComponent, WearComponent

# Tag used to find an interior by vehicle id (category = str(vehicle.id)).
VEHICLE_INTERIOR_TAG = "vehicle_interior"
VEHICLE_ACCESS_CAT = "vehicle_access"

from .rooms import Room  # noqa: E402

try:
    from world.vehicle_parts import (
        default_parts,
        default_part_types,
        get_cool_part_id,
        get_fuel_part_id,
        get_part_condition as _get_part_condition,
        get_part_ids,
        set_part_condition as _set_part_condition,
        damage_part as _damage_part,
        repair_part as _repair_part,
        can_start_engine,
        roll_stall_chance,
        drive_failure_modifier,
        drive_check_modifier,
        tires_ok_for_offroad,
        PART_DISPLAY_NAMES,
        condition_description as _condition_description,
        invalidate_perf_cache,
    )
except ImportError:
    default_parts = lambda v=None: {}
    default_part_types = lambda v=None: {}

    def get_part_ids(v):
        return []

    def get_fuel_part_id(v):
        return "fuel_pump"

    def get_cool_part_id(v):
        return "radiator"

    def tires_ok_for_offroad(v):
        return True

    _get_part_condition = lambda v, p: 100
    _set_part_condition = lambda v, p, x: None
    _damage_part = lambda v, p, a: 100
    _repair_part = lambda v, p, a: 100
    can_start_engine = lambda v: (True, "")
    roll_stall_chance = lambda v: False
    drive_failure_modifier = lambda v: 0.0
    drive_check_modifier = lambda v, m="normal": 0
    invalidate_perf_cache = lambda v: None
    PART_DISPLAY_NAMES = {}
    _condition_description = lambda c: "ok"


# Reuse room's default-welcome check for outside view
_DEFAULT_WELCOME_MARKER = "evennia.com"
_DEFAULT_PLACE_DESC = "A place. Nothing much to note."


def vehicle_label(vehicle):
    """Short display name for messages (vehicle_name attr or object key)."""
    if not vehicle:
        return "vehicle"
    return (getattr(vehicle.db, "vehicle_name", None) or getattr(vehicle, "key", None) or "vehicle").strip()


def _msg_all_vehicle_occupants(vehicle, message):
    """Send a message to everyone in/on the vehicle."""
    if not vehicle:
        return
    if getattr(vehicle.db, "vehicle_type", None) == "motorcycle":
        rider = getattr(vehicle.db, "rider", None)
        if rider:
            rider.msg(message)
        return
    if getattr(vehicle.db, "has_interior", True) and vehicle.db.interior:
        interior = vehicle.db.interior
        if interior:
            interior.msg_contents(message)


def relay_to_parked_vehicle_interiors(room, text):
    """
    Relay a plain-text exterior room message to occupants of any enclosed vehicles parked in `room`.

    Each cabin occupant receives the message prefixed with a windscreen/window intro line so it
    reads as something overheard or glimpsed from inside the vehicle.  Motorcycles are skipped
    because their riders are in the exterior room already and receive the message normally.

    Call this from Room.msg_contents (and from any per-viewer broadcast loop that bypasses
    msg_contents, e.g. at_say and _run_emote) so that cabin crew never miss exterior activity.
    """
    if not room or not text:
        return
    try:
        vehicles_here = [
            obj for obj in room.contents
            if hasattr(obj, "db")
            and getattr(obj.db, "has_interior", False)
            and getattr(obj.db, "vehicle_type", None) not in (None, "motorcycle")
            and getattr(obj.db, "interior", None)
        ]
    except Exception:
        return
    for vehicle in vehicles_here:
        interior = vehicle.db.interior
        if not interior:
            continue
        try:
            occupants = list(interior.contents_get(content_type="character"))
        except Exception:
            continue
        if not occupants:
            continue
        vt = getattr(vehicle.db, "vehicle_type", None) or "ground"
        if vt == "aerial":
            prefix = "|wThrough the closed windows you see:|n "
        else:
            prefix = "|wThrough the windscreen you see:|n "
        relayed = prefix + text
        for occ in occupants:
            try:
                occ.msg(relayed)
            except Exception:
                pass


def _room_allows_vehicle_tags(room) -> bool:
    if not room or not hasattr(room, "tags"):
        return False
    t = room.tags
    return (
        t.has("street", category=VEHICLE_ACCESS_CAT)
        or t.has("tunnel", category=VEHICLE_ACCESS_CAT)
        or t.has("aerial", category=VEHICLE_ACCESS_CAT)
        or t.has("offroad", category=VEHICLE_ACCESS_CAT)
    )


def _can_vehicle_enter(vehicle, destination):
    """Check if a vehicle type is allowed in the destination room. Returns (allowed: bool, reason: str).

    Tags use category ``vehicle_access`` (e.g. ``street``, ``tunnel``, ``aerial``, ``offroad``).
    Street/tunnel are universal for ground/motorcycle. Offroad-only cells need off-road tire mods.
    Aerial vehicles may use street, aerial, or offroad surfaces (no tire check).
    """
    if not destination:
        return False, "There is nowhere to go."

    if destination.tags.has("no_vehicle", category=VEHICLE_ACCESS_CAT):
        return False, "You can't drive there."

    vehicle_type = getattr(vehicle.db, "vehicle_type", None) or "ground"
    has_street = destination.tags.has("street", category=VEHICLE_ACCESS_CAT)
    has_tunnel = destination.tags.has("tunnel", category=VEHICLE_ACCESS_CAT)
    has_offroad = destination.tags.has("offroad", category=VEHICLE_ACCESS_CAT)
    has_aerial = destination.tags.has("aerial", category=VEHICLE_ACCESS_CAT)

    if vehicle_type == "aerial":
        if has_aerial or has_street or has_offroad:
            return True, ""
        return False, "You can't fly there."

    if vehicle_type in ("ground", "motorcycle"):
        if has_street or has_tunnel:
            return True, ""
        if has_offroad and not (has_street or has_tunnel):
            try:
                if tires_ok_for_offroad(vehicle):
                    return True, ""
            except Exception:
                pass
            return (
                False,
                "This terrain needs off-road rated tires or mud treads — yours aren't up to it.",
            )
        return False, "You can't drive there — no road."

    return False, "Unknown vehicle type."


def _can_vehicle_be_placed_in_room(vehicle, room):
    """Vehicles may only be placed on valid vehicle-access tiles (e.g. drop, spawn)."""
    if not room:
        return False, "Nowhere to place it."
    return _can_vehicle_enter(vehicle, room)


class VehicleInterior(Room):
    """
    Room representing the inside of a vehicle. db.vehicle points to the Vehicle object.
    No location (rooms don't have one). Movement is via the drive command.
    """

    default_description = (
        "Worn upholstery, a faint smell of oil and old vinyl. The steering column and dash sit in front of you. "
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

    def _exterior_appearance_as_look(self, room, looker, **kwargs):
        """
        Full room readout as if `look` were used while standing in that room
        (header, desc, things, furniture, people, exits, footer).

        You are not in that room, so omit your own @lp line (no bogus 'You are standing here').
        """
        if not room:
            return ""
        # Strip include_looker before forwarding — it's our own flag and must not leak into
        # arbitrary object methods (e.g. OperatingTable.get_display_name) that don't accept it.
        kw = {k: v for k, v in kwargs.items() if k != "include_looker"}
        kw["include_looker"] = False
        try:
            if hasattr(room, "return_appearance"):
                snap = room.return_appearance(looker, **kw) or ""
            else:
                snap = self._exterior_display_desc(room, looker, **kwargs)
        except Exception:
            snap = self._exterior_display_desc(room, looker, **kwargs)
        return self._sanitize_exterior_snapshot(snap)

    @staticmethod
    def _sanitize_exterior_snapshot(text):
        """Remove bogus self-lines and OOC exit aliases (|w(n)|n) from the outside-room snapshot."""
        if not text:
            return ""
        out_lines = []
        for line in text.split("\n"):
            s = line.strip()
            if s in ("You are standing here.", "You are standing here"):
                continue
            if "here are exits to the" in line.lower():
                line = re.sub(r"\s*\|w\([^)]*\)\|n", "", line)
                line = re.sub(r"  +", " ", line)
            out_lines.append(line)
        return "\n".join(out_lines).strip()

    def _windows_intro_line(self, vehicle):
        vt = getattr(vehicle.db, "vehicle_type", None) or "ground"
        if vt == "aerial":
            return "|wYou see this through the closed windows:|n"
        return "|wYou see this through the windscreen:|n"

    @staticmethod
    def _hud_bar(pct, width=6):
        """Block bar 0–100; color by band (green / amber / red)."""
        pct = max(0, min(100, int(pct)))
        filled = max(0, min(width, round(width * pct / 100.0)))
        empty = width - filled
        if pct < 25:
            col = "|550"
        elif pct < 50:
            col = "|530"
        else:
            col = "|050"
        return f"{col}{'█' * filled}{'░' * empty}|n"

    def _vehicle_status_panel(self, vehicle):
        """
        Shared compact HUD for all vehicle types: power, class, mode, fuel/cool gauges, fault lamps.
        Three lines when healthy; adds one line for active fault codes only.
        """
        vt = getattr(vehicle.db, "vehicle_type", None) or "ground"
        running = getattr(vehicle.db, "engine_running", False)
        airborne = bool(getattr(vehicle.db, "airborne", False))
        parts = getattr(vehicle.db, "vehicle_parts", None) or {}

        bad = []
        try:
            bad = [p for p in get_part_ids(vehicle) if (parts.get(p, 100) or 100) < 50]
        except Exception:
            pass

        cap = float(getattr(vehicle.db, "fuel_capacity", 100) or 100)
        fl = float(getattr(vehicle.db, "fuel_level", cap) or 0)
        fuel_pct = int(round(100.0 * fl / max(cap, 1.0)))
        cool_v = parts.get(get_cool_part_id(vehicle), 100) or 100
        fuel_bar = self._hud_bar(fuel_pct)
        cool_bar = self._hud_bar(cool_v)

        pwr = "|050●RUN|n" if running else "|x○STB|n"
        if vt == "aerial":
            mode = "|050SKY|n" if airborne else "|025GND|n"
            kind = "|025AV|n"
        elif vt == "motorcycle":
            mode = "|025RIDE|n"
            kind = "|0252W|n"
        else:
            mode = "|025ROAD|n"
            kind = "|0254W|n"

        fault_bits = []
        for pid in bad[:6]:
            ab = PART_DISPLAY_NAMES.get(pid, pid)[:3].upper()
            fault_bits.append(f"|550●{ab}|n")

        top = "|025╭── |530◇|n |025 LINK ────────────────────────────────╮|n"
        row1 = (
            f"|025│|n {pwr} {kind} {mode}  "
            f"|xF|n{fuel_bar} |xC|n{cool_bar}"
        )
        bot = "|025╰──────────────────────────────────────────────╯|n"
        lines = [top]
        if fault_bits:
            lines.append(row1 + " |025│|n")
            lines.append(f"|025│|n |550⚠|n {' '.join(fault_bits)} |025│|n")
        else:
            lines.append(row1 + "  |025◇|n|xOK|n |025│|n")
        lines.append(bot)
        return "\n".join(lines)

    @staticmethod
    def _weapon_ammo_bar(current, capacity, width=8):
        """Ammo bar: green when full, amber below half, red when critical (≤10%)."""
        if capacity <= 0:
            return "|025∞∞∞∞∞∞∞∞|n"
        pct = max(0, min(100, int(round(100.0 * current / capacity))))
        filled = max(0, min(width, round(width * pct / 100.0)))
        empty = width - filled
        if pct <= 10:
            col = "|500"
        elif pct < 50:
            col = "|550"
        else:
            col = "|050"
        return f"{col}{'█' * filled}{'░' * empty}|n"

    def _weapon_panel_row(self, weapon, mount_id, vehicle):
        """Single weapon row — left-bordered, no right border."""
        if not weapon or not getattr(weapon, "db", None):
            return f"|025│|n  |025{mount_id}|n  |x(empty)|n"

        wname = (getattr(weapon.db, "weapon_name", None) or weapon.key or "weapon").strip()
        wkey = (getattr(weapon.db, "weapon_key", None) or "").strip()
        cap = int(getattr(weapon.db, "ammo_capacity", 0) or 0)
        cur = int(getattr(weapon.db, "ammo_current", 0) or 0)
        fr = int(getattr(weapon.db, "fire_rate", 1) or 1)

        if "cannon" in wkey or "cannon" in wname.lower():
            tag = "|530CAN|n"
        elif "rocket" in wkey or "missile" in wkey:
            tag = "|500RKT|n"
        elif "machinegun" in wkey or "minigun" in wkey or "mg" in wkey:
            tag = "|050MG |n"
        elif "laser" in wkey:
            tag = "|055LSR|n"
        elif "net" in wkey or "harpoon" in wkey:
            tag = "|025SPL|n"
        else:
            tag = "|025WPN|n"

        from world.combat.vehicle_combat import _get_mount_type
        mtype = _get_mount_type(vehicle, mount_id)
        if mtype == "fixed_forward":
            mlabel = "|025FWD|n"
        elif mtype == "turret":
            mlabel = "|025TUR|n"
        elif mtype == "rear":
            mlabel = "|025RER|n"
        else:
            mlabel = "|025MNT|n"

        wname_trunc = wname[:18]
        if cap > 0:
            ammo_bar = self._weapon_ammo_bar(cur, cap)
            fr_str = f"  |xROF×{fr}|n" if fr > 1 else ""
            return f"|025│|n  {mlabel} |w{wname_trunc}|n  {tag}  {ammo_bar}  |x{cur}/{cap}|n{fr_str}"
        else:
            return f"|025│|n  {mlabel} |w{wname_trunc}|n  {tag}  |025∞|n |xunlimited|n"

    def _driver_weapon_panel(self, vehicle):
        """Compact ammo panel for the driver — forward-mount weapons only."""
        mounts = getattr(vehicle.db, "weapon_mounts", None) or {}
        mount_types = getattr(vehicle.db, "weapon_mount_types", None) or {}
        fwd_mounts = [
            mid for mid in sorted(mounts.keys())
            if mount_types.get(mid, "fixed_forward") == "fixed_forward" and mounts.get(mid)
        ]
        if not fwd_mounts:
            return ""

        rows = ["|025╭── |530◈|n |025 WEAPONS|n"]
        for mid in fwd_mounts:
            rows.append(self._weapon_panel_row(mounts[mid], mid, vehicle))
        rows.append("|025╰─────────────────────────────────────────────|n")
        return "\n".join(rows)

    def _gunner_panel(self, vehicle, gunner):
        """Full gunner HUD: hull status strip + weapon rows."""
        mounts = getattr(vehicle.db, "weapon_mounts", None) or {}
        mount_types = getattr(vehicle.db, "weapon_mount_types", None) or {}
        gunner_mount = getattr(vehicle.db, "gunner_mount", None)

        gunner_mids = []
        if gunner_mount and gunner_mount in mounts:
            gunner_mids.append(gunner_mount)
        for mid in sorted(mounts.keys()):
            if mid not in gunner_mids and mount_types.get(mid, "fixed_forward") in ("turret", "rear", "underbelly"):
                gunner_mids.append(mid)

        running = getattr(vehicle.db, "engine_running", False)
        hp = int(getattr(vehicle.db, "vehicle_hp", 100) or 100)
        max_hp = int(getattr(vehicle.db, "vehicle_max_hp", 100) or 100)
        pwr = "|050●RUN|n" if running else "|x○STB|n"
        hull_bar = self._hud_bar(int(round(100.0 * hp / max(max_hp, 1))))

        rows = ["|025╭── |530◈|n |025 GUNNER|n"]
        rows.append(f"|025│|n  {pwr}  |xHULL|n {hull_bar}  |x{hp}/{max_hp}|n")

        if gunner_mids:
            rows.append("|025│|n")
            for mid in gunner_mids:
                marker = "|050► |n" if mid == gunner_mount else "  "
                # Strip the leading │ from _weapon_panel_row and re-add with marker
                wrow = self._weapon_panel_row(mounts.get(mid), mid, vehicle)
                inner = wrow[len("|025│|n"):]
                rows.append(f"|025│|n {marker}{inner}")
        else:
            rows.append("|025│|n  |xNo weapons on this station.|n")

        rows.append("|025╰─────────────────────────────────────────────|n")
        return "\n".join(rows)

    def _dashboard_block(self, vehicle, looker=None):
        """
        Return the appropriate dashboard panel(s) for the looker:
        - Gunner: gunner HUD (weapon status + hull strip)
        - Driver: base LINK panel + forward-weapon ammo panel if applicable
        - Passenger/none: base LINK panel only
        """
        base = self._vehicle_status_panel(vehicle)
        if looker is None:
            return base

        gunner = getattr(vehicle.db, "gunner", None)
        driver = getattr(vehicle.db, "driver", None)

        if looker is gunner:
            return self._gunner_panel(vehicle, looker)

        if looker is driver:
            weapon_panel = self._driver_weapon_panel(vehicle)
            if weapon_panel:
                return base + "\n" + weapon_panel
            return base

        return base

    def get_display_desc(self, looker, **kwargs):
        """
        Interior prose, then transition line, then full outside-room look (desc, things, people, exits).
        Dashboard and cabin contents are assembled in return_appearance so order matches: outside view,
        then LINK panel, then items inside the vehicle, then seating lines.
        """
        vehicle = self.db.vehicle
        if vehicle:
            base = self.db.desc or self.default_description
            room = self._exterior_room()
            parts = [base]
            if room:
                parts.append(self._windows_intro_line(vehicle))
                parts.append(self._exterior_appearance_as_look(room, looker, **kwargs))
            return "\n\n".join(p for p in parts if p)
        return self.db.desc or self.default_description

    def return_appearance(self, looker, **kwargs):
        """
        Same as Room, but after the main desc block (interior + windscreen view): LINK panel, then
        objects *inside* the cabin, then characters. No separate OOC drive exit line at the bottom —
        exits already appear in the outside snapshot.
        """
        header = self.get_display_header(looker, **kwargs)
        desc = self.get_display_desc(looker, **kwargs)
        things = self.get_display_things(looker, **kwargs)
        furniture = self.get_display_furniture(looker, **kwargs)
        characters = self.get_display_characters(looker, **kwargs)
        footer = self.get_display_footer(looker, **kwargs)
        vehicle = self.db.vehicle
        dashboard = self._dashboard_block(vehicle, looker=looker) if vehicle else ""

        if self._is_street_mode():
            ambient = ""
        else:
            ambient = self.get_display_ambient(looker, **kwargs)

        if self._is_street_mode():
            narrative = self.get_display_narrative_exits(looker, **kwargs)
            head = "\n".join([p for p in (header, desc) if p])
            parts = [head]
            if dashboard:
                parts.append(dashboard)
            if things:
                parts.append(things)
            if furniture:
                parts.append(furniture)
            tail = "\n".join([p for p in (characters, footer) if p])
            if tail:
                parts.append(tail)
            if narrative:
                parts.append(narrative)
            appearance = "\n\n".join([p for p in parts if p])
            return self.format_appearance(appearance, looker, **kwargs)

        exits = self.get_display_exits(looker, **kwargs)
        head = "\n".join([p for p in (header, desc) if p])
        parts = [head]
        if ambient:
            parts.append(ambient)
        if dashboard:
            parts.append(dashboard)
        if things:
            parts.append(things)

        if furniture:
            parts.append(furniture)

        tail = "\n".join([p for p in (characters, exits, footer) if p])
        if tail:
            if furniture:
                parts.append(tail)
            else:
                parts[-1] = "\n".join([parts[-1], tail]) if parts[-1] else tail

        appearance = "\n\n".join([p for p in parts if p])
        return self.format_appearance(appearance, looker, **kwargs)

    def get_outside_block(self, looker, **kwargs):
        """Windscreen section after a move: full outside room look (same as a normal `look` there)."""
        vehicle = self.db.vehicle
        if not vehicle:
            return ""
        room = self._exterior_room()
        if not room:
            return ""
        block = self._windows_intro_line(vehicle) + "\n\n"
        block += self._exterior_appearance_as_look(room, looker, **kwargs)
        return block

    def get_display_exits(self, looker, **kwargs):
        """Exits are shown inside the windscreen snapshot; no duplicate line here."""
        return ""

    def get_vehicle_interior_seat_line(self, char, looker, **kwargs):
        """
        One line for cab occupants: driver's seat vs passenger / back.
        Used by Room.get_display_characters when present.
        """
        vehicle = self.db.vehicle
        if not vehicle:
            return None
        from typeclasses.rooms import _ic_room_char_name

        chars = self.filter_visible(self.contents_get(content_type="character"), looker, **kwargs)
        try:
            from evennia.utils.utils import inherits_from

            chars = [c for c in chars if inherits_from(c, "evennia.objects.objects.DefaultCharacter")]
        except Exception:
            pass

        # Include the char being described even if filter_visible excluded them (e.g. the looker).
        all_present = set(chars) | {char}
        driver = getattr(vehicle.db, "driver", None)
        if driver is not None and driver not in all_present:
            driver = None
        gunner = getattr(vehicle.db, "gunner", None)
        if gunner is not None and gunner not in all_present:
            gunner = None
        gunner_mount = getattr(vehicle.db, "gunner_mount", None) or ""
        occupied = {c for c in (driver, gunner) if c}
        passengers = [c for c in chars if c not in occupied]
        try:
            passengers.sort(key=lambda x: getattr(x, "id", 0) or 0)
        except Exception:
            pass

        vt = getattr(vehicle.db, "vehicle_type", None) or "ground"
        pilot_word = "pilot" if vt == "aerial" else "driver"
        front_passenger = "the co-pilot seat" if vt == "aerial" else "the passenger seat"

        # Determine gunner station label from mount id
        if gunner_mount in ("m0", "m1"):
            gun_station = "the turret"
        elif gunner_mount == "m2":
            gun_station = "the rear gun"
        else:
            gun_station = "the gunner station"

        if char is driver:
            if char is looker:
                return f"You are sitting in the {pilot_word}'s seat."
            return f"{_ic_room_char_name(char, looker, **kwargs)} is sitting in the {pilot_word}'s seat."

        if char is gunner:
            if char is looker:
                return f"You are manning {gun_station}."
            return f"{_ic_room_char_name(char, looker, **kwargs)} is manning {gun_station}."

        if char not in passengers:
            return None
        idx = passengers.index(char)
        place = front_passenger if idx == 0 else "the back"
        if char is looker:
            return f"You are sitting in {place}."
        return f"{_ic_room_char_name(char, looker, **kwargs)} is sitting in {place}."


class Vehicle(ComponentHolderMixin, MatrixIdMixin, EnterableMixin, Object):
    """
    Base class for all vehicles. Subclassed by enclosed ground vehicles, motorcycles, and aerial vehicles.

    db.vehicle_type: ground | motorcycle | aerial
    db.has_interior: enclosed types True; motorcycles False

    Components (Evennia base_systems.components):
        vehicle.fuel  — FuelComponent (level, capacity, type, heat, overheat)
        vehicle.wear  — WearComponent (level, max)
        vehicle.drive — DriveComponent (driver, passengers, running, speed_class, skill)

    Backward-compatibility shims keep db.fuel_level, db.driver, db.engine_running etc.
    working so all existing call sites need no changes.
    """

    has_interior_default = True

    fuel  = ComponentProperty("fuel")
    wear  = ComponentProperty("wear")
    drive = ComponentProperty("drive")

    # ------------------------------------------------------------------
    # Fuel compatibility shims — existing code uses vehicle.db.fuel_level
    # ------------------------------------------------------------------

    @property
    def fuel_level(self):
        return self.fuel.level if self.fuel else self.db.fuel_level

    @fuel_level.setter
    def fuel_level(self, value):
        if self.fuel:
            self.fuel.level = float(value)
        self.db.fuel_level = float(value)

    @property
    def fuel_capacity(self):
        return self.fuel.capacity if self.fuel else self.db.fuel_capacity

    @fuel_capacity.setter
    def fuel_capacity(self, value):
        if self.fuel:
            self.fuel.capacity = float(value)
        self.db.fuel_capacity = float(value)

    @property
    def fuel_type(self):
        return self.fuel.type if self.fuel else self.db.fuel_type

    @fuel_type.setter
    def fuel_type(self, value):
        if self.fuel:
            self.fuel.type = str(value)
        self.db.fuel_type = str(value)

    # ------------------------------------------------------------------
    # Drive compatibility shims — existing code uses vehicle.db.driver etc.
    # ------------------------------------------------------------------

    @property
    def current_driver(self):
        return self.drive.driver if self.drive else self.db.driver

    @current_driver.setter
    def current_driver(self, value):
        if self.drive:
            self.drive.driver = value
        self.db.driver = value

    def at_object_creation(self):
        super().at_object_creation()
        self.db.vehicle_type = getattr(self.db, "vehicle_type", None) or "ground"
        self.db.engine_running = False
        self.db.interior = None
        self.db.has_interior = self.has_interior_default
        self.db.driver = None
        self.db.max_passengers = 4
        self.db.driving_skill = getattr(self.db, "driving_skill", None) or "driving"
        self.db.vehicle_name = getattr(self.db, "vehicle_name", None) or "vehicle"
        self.db.vehicle_parts = default_parts(self)
        self.db.vehicle_part_types = default_part_types(self)
        self.db.speed_class = getattr(self.db, "speed_class", None) or "normal"
        cap = float(getattr(self.db, "fuel_capacity", None) or 100)
        self.db.fuel_capacity = cap
        self.db.fuel_level = float(getattr(self.db, "fuel_level", None) if getattr(self.db, "fuel_level", None) is not None else cap)
        self.db.fuel_type = getattr(self.db, "fuel_type", None) or "standard"
        self.db.heat_level = float(getattr(self.db, "heat_level", None) or 0)
        self.db.overheat_threshold = float(getattr(self.db, "overheat_threshold", None) or 100)

        # --- Components: initialize with values already set above ---
        self.components.add(FuelComponent.create(
            self,
            level=self.db.fuel_level,
            capacity=self.db.fuel_capacity,
            type=self.db.fuel_type,
            heat=self.db.heat_level,
            overheat=self.db.overheat_threshold,
        ))
        self.components.add(WearComponent.default_create(self))
        self.components.add(DriveComponent.create(
            self,
            speed_class=self.db.speed_class,
            skill=self.db.driving_skill,
        ))
        self.db.security_tier = int(getattr(self.db, "security_tier", None) or 1)
        self.db.security_owner = getattr(self.db, "security_owner", None)
        self.db.security_authorizations = getattr(self.db, "security_authorizations", None) or {}
        self.db.security_locked = bool(getattr(self.db, "security_locked", True))
        self.db.security_hotwired = bool(getattr(self.db, "security_hotwired", False))
        self.db.security_alarm_active = bool(getattr(self.db, "security_alarm_active", False))
        self.db.security_alarm_until = float(getattr(self.db, "security_alarm_until", None) or 0)
        self.db.security_failed_attempts = int(getattr(self.db, "security_failed_attempts", None) or 0)
        self.db.security_lockout_until = float(getattr(self.db, "security_lockout_until", None) or 0)
        self.db.paint_color = getattr(self.db, "paint_color", None)
        self.db.paint_color_code = getattr(self.db, "paint_color_code", None) or ""
        self.db.paint_quality = getattr(self.db, "paint_quality", None)
        self.db.custom_desc_prefix = getattr(self.db, "custom_desc_prefix", None) or ""
        self.db.visual_mods = getattr(self.db, "visual_mods", None) or []
        self.db.autopilot_active = False
        self.db.autopilot_route = []
        self.db.autopilot_step = 0
        self.db.autopilot_destination = ""
        try:
            self.locks.add("get:false()")
        except Exception:
            pass
        self.db.vehicle_destroyed = bool(getattr(self.db, "vehicle_destroyed", False))
        self.db.weapon_mounts = getattr(self.db, "weapon_mounts", None) or {}
        self.db.gunner = getattr(self.db, "gunner", None)
        self.db.gunner_mount = getattr(self.db, "gunner_mount", None)
        self.db.tethered_to = getattr(self.db, "tethered_to", None)
        self.db.tethered_by = getattr(self.db, "tethered_by", None)
        try:
            from world.combat.vehicle_combat import VEHICLE_MOUNT_CONFIGS, init_vehicle_hp_for_type

            vt = getattr(self.db, "vehicle_type", None) or "ground"
            vcfg = VEHICLE_MOUNT_CONFIGS.get(vt, VEHICLE_MOUNT_CONFIGS["ground"])
            if getattr(self.db, "max_weapon_mounts", None) is None:
                self.db.max_weapon_mounts = vcfg["max_mounts"]
            init_vehicle_hp_for_type(self)
            if not getattr(self.db, "weapon_mount_types", None):
                meta = {}
                for i, mtype in enumerate(vcfg["mount_types"][: int(self.db.max_weapon_mounts or 2)]):
                    meta[f"m{i}"] = mtype
                self.db.weapon_mount_types = meta
        except Exception:
            if getattr(self.db, "vehicle_hp", None) is None:
                self.db.vehicle_hp = 100
            if getattr(self.db, "vehicle_max_hp", None) is None:
                self.db.vehicle_max_hp = 100
            if getattr(self.db, "max_weapon_mounts", None) is None:
                self.db.max_weapon_mounts = 2
        if getattr(self.db, "vehicle_armor", None) is None:
            self.db.vehicle_armor = 0
        try:
            from world.vehicle_parts import refresh_vehicle_armor

            refresh_vehicle_armor(self)
        except Exception:
            pass
        try:
            mid = self.get_matrix_id()
            if mid:
                self.db.matrix_id = mid
        except Exception:
            self.db.matrix_id = getattr(self.db, "matrix_id", None) or ""
        if self.has_interior_default:
            self._ensure_interior()

    def _recover_interior_from_id(self):
        rid = getattr(self.db, "interior_room_id", None)
        if not rid:
            return None
        try:
            res = search_object(f"#{rid}")
            if res:
                interior = res[0]
                if getattr(interior.db, "vehicle", None) in (self, None):
                    interior.db.vehicle = self
                    self.db.interior = interior
                    return interior
        except Exception:
            pass
        return None

    def _ensure_interior(self):
        """Return this vehicle's single persistent interior. Creates once per vehicle; never duplicates."""
        if not getattr(self.db, "has_interior", True):
            return None

        interior = self.db.interior
        if interior:
            try:
                if not interior.tags.has(VEHICLE_INTERIOR_TAG, category=str(self.id)):
                    interior.tags.add(VEHICLE_INTERIOR_TAG, category=str(self.id))
            except Exception:
                pass
            return interior

        recovered = self._recover_interior_from_id()
        if recovered:
            return recovered

        if not getattr(self.ndb, "_interior_tag_search_done", False):
            try:
                found = search_tag(VEHICLE_INTERIOR_TAG, category=str(self.id))
                self.ndb._interior_tag_search_done = True
                if found:
                    candidate = found[0]
                    if getattr(candidate.db, "vehicle", None) is self or getattr(candidate.db, "vehicle", None) == self:
                        self.db.interior = candidate
                        self.db.interior_room_id = candidate.id
                        return candidate
                    if getattr(candidate.db, "vehicle", None) is None:
                        candidate.db.vehicle = self
                        self.db.interior = candidate
                        self.db.interior_room_id = candidate.id
                        return candidate
            except Exception:
                self.ndb._interior_tag_search_done = True

        key = f"Inside the {self.key}"
        interior = create_object(
            "typeclasses.vehicles.VehicleInterior",
            key=key,
            location=None,
        )
        if interior:
            interior.db.vehicle = self
            interior.db.desc = None
            interior.tags.add(VEHICLE_INTERIOR_TAG, category=str(self.id))
            self.db.interior = interior
            self.db.interior_room_id = interior.id
        return self.db.interior

    @property
    def interior(self):
        if not getattr(self.db, "has_interior", True):
            return None
        return self._ensure_interior()

    def at_pre_get(self, getter, **kwargs):
        if getter and getter.check_permstring("Builder"):
            return super().at_pre_get(getter, **kwargs)
        interior = None
        if getattr(self.db, "has_interior", True):
            interior = self.db.interior or self._ensure_interior()
        if interior and hasattr(interior, "contents_get"):
            try:
                if interior.contents_get(content_type="character"):
                    getter.msg("Someone is inside. You can't pick this up.")
                    return False
            except Exception:
                pass
        return super().at_pre_get(getter, **kwargs)

    def at_pre_drop(self, dropper, **kwargs):
        loc = dropper.location if dropper else None
        if not loc:
            return super().at_pre_drop(dropper, **kwargs)
        ok, reason = _can_vehicle_be_placed_in_room(self, loc)
        if not ok:
            if dropper:
                dropper.msg(f"|r{reason}|n")
            return False
        return super().at_pre_drop(dropper, **kwargs)

    def at_after_move(self, source_location, **kwargs):
        try:
            super().at_after_move(source_location, **kwargs)
        except Exception:
            pass
        dest = self.location
        if not dest:
            return
        ok, _reason = _can_vehicle_be_placed_in_room(self, dest)
        if ok:
            return
        # Guard against recursive at_after_move when moving back to source.
        if source_location and dest != source_location:
            self.move_to(source_location, quiet=True)

    def return_appearance(self, looker, **kwargs):
        desc = self.db.desc or "A vehicle."
        pq = getattr(self.db, "paint_quality", None)
        pcolor = getattr(self.db, "paint_color", None)
        prefix = (getattr(self.db, "custom_desc_prefix", None) or "").strip()
        if pcolor and (pq is None or float(pq) > 20) and prefix:
            code = getattr(self.db, "paint_color_code", None) or ""
            header = f"{code}{prefix} {self.key}|n"
        else:
            header = self.get_display_name(looker)
        parts_out = [header, desc]
        plate = None
        try:
            plate = self.get_matrix_id()
        except Exception:
            plate = None
        if not plate:
            plate = getattr(self.db, "matrix_id", None) or ""
        elif getattr(self.db, "matrix_id", None) != plate:
            self.db.matrix_id = plate
        if plate:
            parts_out.append(f"|mPlate:|n {plate}")
        vm = getattr(self.db, "visual_mods", None) or []
        for entry in vm:
            if isinstance(entry, dict) and entry.get("desc"):
                parts_out.append(str(entry["desc"]))
        if getattr(self.db, "engine_running", False):
            parts_out.append("|yEngine running.|n")
        mounts = getattr(self.db, "weapon_mounts", None) or {}
        weapon_descs = []
        for _mid, wobj in mounts.items():
            if wobj and getattr(wobj, "db", None):
                addon = getattr(wobj.db, "desc_addon", None) or ""
                if addon:
                    weapon_descs.append(addon)
        if weapon_descs:
            parts_out.append("\n".join(weapon_descs))
        return "\n\n".join(p for p in parts_out if p)

    def damage_part(self, part_id, amount):
        try:
            from world.movement import tunnels as _tunnels

            if getattr(self.db, "autopilot_active", False):
                _tunnels.cancel_autopilot(self, reason="Vehicle took damage.")
        except Exception:
            pass
        return _damage_part(self, part_id, amount)

    def start_engine(self):
        ok, msg = can_start_engine(self)
        if not ok:
            return False, msg
        self.db.engine_running = True
        return True, None

    def stop_engine(self):
        self.db.engine_running = False
        try:
            from world.movement import tunnels as _tunnels

            if getattr(self.db, "autopilot_active", False):
                _tunnels.cancel_autopilot(self, reason="Engine stopped.")
        except Exception:
            pass
        try:
            from world.vehicle_parts import schedule_vehicle_cooldown

            schedule_vehicle_cooldown(self)
        except Exception:
            pass

    @property
    def engine_running(self):
        return bool(self.db.engine_running)

    @property
    def state_machine(self):
        """
        Return the VehicleStateMachine for this vehicle (created on first access).
        Stored in ndb._state_machine (non-persistent; recreated on reload).
        Use this to trigger validated state transitions:
            self.state_machine.start_engine()
            self.state_machine.engage_autopilot()
        """
        from world.vehicle_states import get_vehicle_fsm
        return get_vehicle_fsm(self)

    def get_part_condition(self, part_id):
        return _get_part_condition(self, part_id)

    def set_part_condition(self, part_id, value):
        _set_part_condition(self, part_id, value)

    def repair_part(self, part_id, amount):
        return _repair_part(self, part_id, amount)

    def drive_failure_modifier(self):
        return drive_failure_modifier(self)

    def get_drive_check_modifier(self, maneuver="normal"):
        return drive_check_modifier(self, maneuver)

    def roll_stall_chance(self):
        return roll_stall_chance(self)

    def at_enter(self, caller):
        """Handle a character entering this vehicle (called by CmdEnter)."""
        if getattr(caller.db, "in_vehicle", None) or getattr(caller.db, "mounted_on", None):
            caller.msg("You are already inside or on a vehicle. Exit or dismount first.")
            return
        if not getattr(self.db, "has_interior", True):
            caller.msg("That is not a vehicle you can enter.")
            return
        interior = self.interior
        if not interior:
            caller.msg("That is not a vehicle you can enter.")
            return
        try:
            from world.vehicles.vehicle_security import check_vehicle_permission
            if getattr(self.db, "security_locked", False) and not check_vehicle_permission(
                self, caller, "unlock"
            ):
                caller.msg(f"{getattr(self.db, 'vehicle_name', None) or self.key} is locked.")
                return
        except ImportError:
            pass
        if not caller.move_to(interior, quiet=True, move_type="teleport"):
            caller.msg("You couldn't get into the vehicle. (Try standing up if you are seated.)")
            return
        caller.db.in_vehicle = self
        if not getattr(self.db, "driver", None):
            self.db.driver = caller
        vlabel = getattr(self.db, "vehicle_name", None) or self.key
        caller.msg(f"You enter {vlabel}.")
        exterior = getattr(self, "location", None)
        try:
            from world.rp_features import msg_room_with_character_display as _mrwcd
        except ImportError:
            _mrwcd = None
        if exterior and _mrwcd:
            _mrwcd(exterior, caller, lambda _v, display: f"{display} enters the {vlabel}.")
        elif exterior:
            exterior.msg_contents(f"{caller.key} enters the {vlabel}.", exclude=caller)

    def get_exit(self, direction):
        """Find an exit from the vehicle's current room in the given direction (e.g. 'east', 'e')."""
        room = self.location
        if not room or not direction:
            return None
        d = direction.strip().lower()
        dir_aliases = {
            "n": "north",
            "s": "south",
            "e": "east",
            "w": "west",
            "ne": "northeast",
            "nw": "northwest",
            "se": "southeast",
            "sw": "southwest",
            "u": "up",
            "d": "down",
        }
        d = dir_aliases.get(d, d)
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


class Motorcycle(Vehicle):
    """
    Open vehicle — no interior. The rider remains in the room, mounted.
    """

    has_interior_default = False

    def at_object_creation(self):
        super().at_object_creation()
        self.db.vehicle_type = "motorcycle"
        self.db.has_interior = False
        self.db.interior = None
        self.db.max_passengers = getattr(self.db, "max_passengers", None) or 1
        self.db.rider = None
        self.db.speed_class = getattr(self.db, "speed_class", None) or "fast"
        if not self.attributes.has("has_pillion"):
            self.db.has_pillion = False

    @property
    def interior(self):
        return None

    def at_enter(self, caller):
        caller.msg("That's an open bike. Use |wmount <bike>|n.")


class AerialVehicle(Vehicle):
    """Flying vehicle; uses piloting; can use aerial corridors and shafts."""

    def at_object_creation(self):
        self.db.vehicle_type = "aerial"
        super().at_object_creation()
        self.db.has_interior = True
        self.db.driving_skill = "piloting"
        self.db.speed_class = getattr(self.db, "speed_class", None) or "fast"
        self.db.airborne = False
        self.db.altitude_z = None

    def stop_engine(self):
        was_air = bool(getattr(self.db, "airborne", False))
        loc = getattr(self, "location", None)
        super().stop_engine()
        self.db.airborne = False
        if was_air and loc and getattr(getattr(loc, "db", None), "is_air", False):
            _msg_all_vehicle_occupants(self, "|R[ENGINE] Power loss. Losing altitude.|n")
            try:
                from evennia.utils import delay
                from world.movement.falling import process_fall

                delay(1.0, process_fall, self.id, loc.id)
            except Exception:
                pass
