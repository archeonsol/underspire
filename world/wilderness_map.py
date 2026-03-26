"""
Colony wilderness map provider.

Uses Evennia's wilderness contrib to provide a large overland area outside the city.

Key features:
- Coordinates are (x, y) integers around a city gate at (0, 0).
- Most tiles are auto-generated wilderness views with a base description.
- Specific coordinates can map into permanent, hand-built rooms (towns, ruins, etc.).
- At (0, 0) an "inside" exit returns players to the city gate.

Usage (once, from the Evennia shell or a startup hook):

    from evennia.contrib.grid import wilderness
    from world import wilderness_map as wmap
    provider = wmap.ColonyWildernessProvider(city_gate_room_path="#123")  # or path/tag
    wilderness.create_wilderness(name="colony_wilds", mapprovider=provider)

Set city_gate_room_path to the room's #dbref (e.g. "#123"), a search path, or a tag
like "city_gate" so the "inside" exit knows where to send players.

From your city gate room, create an exit with typeclass
typeclasses.wilderness_exit.OutsideToWildernessExit.
"""

import logging

from evennia import create_object
from evennia.contrib.grid import wilderness
from evennia.utils.search import search_object

logger = logging.getLogger("evennia")

# ---------------------------------------------------------------------------
# OpenSimplex noise for organic biome generation
# ---------------------------------------------------------------------------
try:
    from opensimplex import OpenSimplex as _OpenSimplex
    _OPENSIMPLEX_AVAILABLE = True
except ImportError:
    _OpenSimplex = None
    _OPENSIMPLEX_AVAILABLE = False

# Seed is loaded lazily on first use so ServerConfig is available.
_elev_gen = None
_moist_gen = None
_NOISE_SEED = None


def _get_noise_generators():
    """Return (elev_gen, moist_gen), initialising from ServerConfig on first call."""
    global _elev_gen, _moist_gen, _NOISE_SEED
    if _elev_gen is not None:
        return _elev_gen, _moist_gen
    if not _OPENSIMPLEX_AVAILABLE:
        return None, None
    try:
        from evennia.server.models import ServerConfig
        seed = ServerConfig.objects.conf("WILDERNESS_SEED", default=42)
        _NOISE_SEED = int(seed)
    except Exception:
        _NOISE_SEED = 42
    _elev_gen = _OpenSimplex(seed=_NOISE_SEED)
    _moist_gen = _OpenSimplex(seed=_NOISE_SEED + 1000)
    return _elev_gen, _moist_gen


# Whittaker-style biome lookup: [elev_band 0-2][moist_band 0-2]
# elev: 0=low, 1=mid, 2=high  |  moist: 0=dry, 1=moderate, 2=wet
_WHITTAKER_BIOME = [
    # low elevation
    ["harshlands",       "grasslands",         "grasslands"],
    # mid elevation
    ["harshlands",       "hills",              "hills"],
    # high elevation
    ["volcanic",         "ruined_settlement",  "hills"],
]


def _elev_band(v: float) -> int:
    """Map noise value -1..1 to elevation band 0-2."""
    if v < -0.2:
        return 0
    if v < 0.3:
        return 1
    return 2


def _moist_band(v: float) -> int:
    """Map noise value -1..1 to moisture band 0-2."""
    if v < -0.1:
        return 0
    if v < 0.3:
        return 1
    return 2


# Coordinate where the city gate "outside" exit drops you.
CITY_GATE_COORD = (0, 0)

# Example: a town reached by going 19 east and 7 north from city gate.
TOWN_COORD = (19, 7)

# Map wilderness coordinates to permanent rooms via dbref strings (e.g. "#123").
# Use the room's #dbref so lookups are exact and never match by name/path.
# Example: once you've built the town entry room and noted its dbref, set:
#   TOWN_COORD: "#123"
# Leave the value as None (or omit the entry) to skip that coord until the room exists.
PERMANENT_COORDS = {
    # TOWN_COORD: "#123",  # TODO: replace with actual dbref once the room is built
}


def get_city_gate_room(provider):
    """
    Resolve the city gate room from the provider's city_gate_room_path.

    Accepted values:
      - A dbref string like "#123"  (preferred)
      - An integer dbref
      - A tag string (no "#" prefix) — searches by tag, prefers rooms (location=None)
      - An already-resolved room object
    """
    path = getattr(provider, "city_gate_room_path", None)
    if not path:
        return None
    # Already a resolved object
    if not isinstance(path, (str, int)):
        return path if hasattr(path, "at_object_leave") else None
    # Integer dbref
    if isinstance(path, int):
        results = search_object(f"#{path}")
        return results[0] if results else None
    # Dbref string "#NNN"
    if path.startswith("#"):
        try:
            int(path.lstrip("#"))  # validate it's numeric
            results = search_object(path)
            return results[0] if results else None
        except (ValueError, TypeError):
            pass
    # Tag string — prefer rooms (location is None)
    from evennia.utils.search import search_tag
    tagged = search_tag(path)
    for obj in (tagged or []):
        if hasattr(obj, "at_object_leave") and getattr(obj, "location", None) is None:
            return obj
    for obj in (tagged or []):
        if hasattr(obj, "at_object_leave"):
            return obj
    return None


def _get_biome_for_coords(x: int, y: int) -> str:
    """
    Return the biome string for (x, y) using OpenSimplex noise when available,
    falling back to distance-band logic.
    """
    elev_gen, moist_gen = _get_noise_generators()
    if elev_gen is not None and moist_gen is not None:
        try:
            elev = elev_gen.noise2(x * 0.04, y * 0.04)
            moist = moist_gen.noise2(x * 0.04 + 500, y * 0.04 + 500)
            return _WHITTAKER_BIOME[_elev_band(elev)][_moist_band(moist)]
        except Exception:
            pass
    # Distance-band fallback
    dist = max(abs(x), abs(y))
    if dist <= 20:
        return "grasslands"
    if dist <= 40:
        return "harshlands"
    if dist <= 60:
        return "hills"
    if dist <= 80:
        return "ruined_settlement"
    return "volcanic"


class ColonyWildernessRoom(wilderness.WildernessRoom):
    """
    Wilderness room that:
    - Uses a fixed name, 'The Harshlands'.
    - Hides coordinates from regular players.
    - Shows coordinates only to builders.
    - Avoids double (#dbref) in the header.
    - Accepts move_type/**kwargs in at_object_receive for Evennia move_to() compatibility.
    """

    def at_object_receive(self, obj, source_location, move_type="move", **kwargs):
        """Accept move_type and kwargs so @goto/teleport into wilderness doesn't break, and still run Room hooks."""
        super().at_object_receive(obj, source_location, move_type=move_type, **kwargs)

    def _biome_label_for_coords(self, coordinates):
        """Return a short label for the biome at these coordinates (for room header)."""
        if coordinates is None:
            return "The Harshlands"
        try:
            x, y = coordinates
            biome = _get_biome_for_coords(x, y)
            labels = {
                "grasslands": "Grasslands",
                "harshlands": "Harshlands",
                "hills": "Hills",
                "ruined_settlement": "Ruined Settlement",
                "volcanic": "Volcanic Wastes",
            }
            return labels.get(biome, "The Harshlands")
        except (TypeError, ValueError):
            return "The Harshlands"

    def get_display_name(self, looker, **kwargs):
        """
        Base, uncolored name for this room. Reflects the biome at this coordinate.
        """
        coords = self.coordinates
        name = self._biome_label_for_coords(coords)
        if looker and self.locks.check_lockstring(looker, "perm(Builder)"):
            if coords is not None:
                try:
                    x, y = coords
                    name += f" ({x}, {y})"
                except (TypeError, ValueError):
                    pass
        return name

    def get_display_header(self, looker, **kwargs):
        """
        Colored header line for room look.
        """
        name = self.get_display_name(looker, **kwargs)
        extra = self.get_extra_display_name_info(looker, **kwargs) or ""
        # Harsh amber-red color for wilderness rooms
        return f"|510{name}{extra}|n"


class ColonyWildernessProvider(wilderness.WildernessMapProvider):
    """
    Map provider for the overland wilderness.

    - is_valid_coordinates: which (x, y) coords are part of this wilderness.
    - at_prepare_room: how the WildernessRoom should present itself at a given coord,
      and when to hand off into permanent structures. At (0,0) adds an "inside" exit.
    """

    room_typeclass = ColonyWildernessRoom

    def __init__(self, city_gate_room_path="#222"):
        """
        Args:
            city_gate_room_path: #dbref (e.g. "#123"), search path, or tag like "city_gate"
                for the room where "inside" from (0,0) sends players.
        """
        self.city_gate_room_path = city_gate_room_path

    def is_valid_coordinates(self, wilderness_script, coordinates):
        """
        Define the overall extent of the wilderness map.

        For now we allow a big square around the city (e.g. -100..100).
        """
        x, y = coordinates
        return -100 <= x <= 100 and -100 <= y <= 100

    def at_prepare_room(self, coordinates, obj, room):
        """
        Called whenever a WildernessRoom is used to show a position.

        This is where we:
        - At (0,0) add an "inside" exit back to the city gate; remove it elsewhere.
        - Redirect into permanent rooms (towns, ruins) for special coords.
        - Set a base wilderness description and scavenge tags for generic tiles.
        """
        x, y = coordinates

        # 0) At (0,0) add "inside" exit; elsewhere remove it so recycled rooms don't show it.
        inside_exit = next((e for e in room.exits if e.key == "inside"), None)
        if coordinates == (0, 0):
            if not inside_exit and self.city_gate_room_path:
                create_object(
                    typeclass="typeclasses.wilderness_exit.InsideToCityExit",
                    key="inside",
                    aliases=["in"],
                    location=room,
                    # destination is resolved dynamically in InsideToCityExit.at_traverse;
                    # set to None here so the exit doesn't falsely point back at the wilderness room.
                    destination=None,
                    report_to=obj,
                )
        else:
            if inside_exit:
                inside_exit.delete()

        # 1) Hand off to permanent structures if this coord is special.
        # PERMANENT_COORDS values must be dbref strings ("#NNN") or room objects.
        if (x, y) in PERMANENT_COORDS:
            target = PERMANENT_COORDS[(x, y)]
            dest = None
            if target is None:
                pass  # entry reserved but room not built yet
            elif isinstance(target, str) and target.startswith("#"):
                try:
                    found = search_object(target)
                    dest = found[0] if found else None
                except Exception:
                    dest = None
            elif not isinstance(target, str):
                dest = target if hasattr(target, "at_object_leave") else None
            if dest:
                obj.msg("|gYou leave the wastes behind and enter a settlement.|n")
                obj.move_to(dest, quiet=False)
                return

        # 2) Biome selection and description (uses OpenSimplex noise when available).
        biome = _get_biome_for_coords(x, y)
        _BIOME_DESCS = {
            "grasslands": (
                "Patchy scrub and stubborn grasses cling to the broken earth. The wind carries "
                "the distant hum of the city behind you and the faint stink of burned ozone."
            ),
            "harshlands": (
                "A grey ashfall carpets the ground, muffling your steps. Charred stumps, twisted "
                "rebar and slag heaps jut from the waste like broken teeth."
            ),
            "hills": (
                "Low, rolling hills of cracked stone rise and fall underfoot. Rusted wreckage "
                "and half-buried concrete ribs jut from the slopes like old bones."
            ),
            "ruined_settlement": (
                "The skeleton of an old settlement: collapsed walls, buckled frames and rubble. "
                "Weeds and rust claim what's left. Nothing here has answered in a long time."
            ),
            "volcanic": (
                "The ground here is dark and glassy, fissured with old lava flows. Heat shimmers "
                "from vents in the rock, and the air stinks of sulfur and scorched metal."
            ),
        }
        desc = _BIOME_DESCS.get(biome, _BIOME_DESCS["harshlands"])

        # Always set the room description for this coordinate.
        room.db.desc = desc

        # 3) Mark this tile as scavengable with biome-specific tags.
        try:
            # Clear old scavenge tags, then add new ones.
            if hasattr(room, "tags"):
                for tag in list(room.tags.all()):
                    t = str(tag).lower()
                    if t in ("wildscavenge", "urbanscavenge") or t.startswith("biome_") or t.startswith("scavenge_"):
                        room.tags.remove(t)  # pass the string key, not the tag object
                room.tags.add("wildscavenge")
                room.tags.add(f"biome_{biome}")
                room.tags.add(f"scavenge_{biome}")
        except Exception:
            pass

        # Register biome with the wilderness graph for region queries and routing.
        try:
            from world.wilderness_graph import set_coord_biome
            set_coord_biome(coords, biome)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# APScheduler job registration
# ---------------------------------------------------------------------------

def _refresh_wilderness_scavenge_density():
    """
    Invalidate the wilderness graph cache so biome regions are recalculated
    on next access. Also clears stale scavenge density caches if any exist.
    Runs daily at 06:00 UTC via APScheduler.
    """
    try:
        from world.wilderness_graph import invalidate_wilderness_graph
        invalidate_wilderness_graph()
    except Exception as exc:
        logger.error("[wilderness_density_refresh] failed: %s", exc, exc_info=True)


def register_wilderness_jobs(sched):
    """
    Register wilderness APScheduler jobs.
    Called by world/scheduler.py register_all_jobs().

    Args:
        sched: A running APScheduler BackgroundScheduler instance.
    """
    sched.add_job(
        _refresh_wilderness_scavenge_density,
        trigger="cron",
        hour=6,
        minute=0,
        id="wilderness_scavenge_density_refresh",
        replace_existing=True,
    )

