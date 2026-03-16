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

from evennia import create_object
from evennia.contrib.grid import wilderness
from evennia.utils.search import search_object


# Coordinate where the city gate "outside" exit drops you.
CITY_GATE_COORD = (0, 0)

# Example: a town reached by going 19 east and 7 north from city gate.
TOWN_COORD = (19, 7)

# Map wilderness coordinates to permanent room paths or objects.
# Replace the string values with actual room paths (or room objects) in your world.
PERMANENT_COORDS = {
    # Example – town entry room; adjust to your actual room path.
    TOWN_COORD: "world.town.TownSquare",  # TODO: create this room and update this path
}


def get_city_gate_room(provider):
    """Resolve the city gate room from the provider's city_gate_room_path."""
    path = getattr(provider, "city_gate_room_path", None)
    if not path:
        return None
    if isinstance(path, int):
        results = search_object(path)
        return results[0] if results else None
    if isinstance(path, str) and path.startswith("#"):
        try:
            dbref = int(path.lstrip("#"))
            results = search_object(dbref)
            return results[0] if results else None
        except (ValueError, TypeError):
            pass
    if isinstance(path, str):
        # Path (dbref string already handled above)
        if path.startswith("world.") or "/" in path or path.count(".") >= 1:
            results = search_object(path)
            return results[0] if results else None
        # Treat as tag
        from evennia.utils.search import search_tag
        tagged = search_tag(path)
        for obj in (tagged or []):
            if hasattr(obj, "at_object_leave"):
                return obj
        return None
    return path if hasattr(path, "at_object_leave") else None


class ColonyWildernessRoom(wilderness.WildernessRoom):
    """
    Wilderness room that:
    - Uses a fixed name, 'The Harshlands'.
    - Hides coordinates from regular players.
    - Shows coordinates only to builders.
    - Avoids double (#dbref) in the header.
    """

    def get_display_name(self, looker, **kwargs):
        """
        Base, uncolored name for this room.
        """
        name = "The Harshlands"
        coords = self.coordinates
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

    def __init__(self, city_gate_room_path=None):
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
                    destination=room,
                    report_to=obj,
                )
        else:
            if inside_exit:
                inside_exit.delete()

        # 1) Hand off to permanent structures if this coord is special.
        if (x, y) in PERMANENT_COORDS:
            target = PERMANENT_COORDS[(x, y)]
            dest = None
            if isinstance(target, str):
                try:
                    found = search_object(target)
                    dest = found[0] if found else None
                except Exception:
                    dest = None
            else:
                dest = target if hasattr(target, "at_object_leave") else None
            if dest:
                obj.msg("|gYou leave the wastes behind and enter a settlement.|n")
                obj.move_to(dest, quiet=False)
                return

        # 2) Biome selection and description.
        # Grasslands near the city, harsher biomes further out.
        if abs(x) <= 20 and abs(y) <= 20:
            biome = "grasslands"
            desc = (
                "Patchy scrub and stubborn grasses cling to the broken earth. The wind carries "
                "the distant hum of the city behind you and the faint stink of burned ozone."
            )
        elif abs(x) <= 40 and abs(y) <= 40:
            biome = "ashlands"
            desc = (
                "A grey ashfall carpets the ground, muffling your steps. Charred stumps, twisted "
                "rebar and slag heaps jut from the waste like broken teeth."
            )
        elif abs(y) > 40:
            biome = "hills"
            desc = (
                "Low, rolling hills of cracked stone rise and fall underfoot. Rusted wreckage "
                "and half-buried concrete ribs jut from the slopes like old bones."
            )
        else:
            biome = "volcanic"
            desc = (
                "The ground here is dark and glassy, fissured with old lava flows. Heat shimmers "
                "from vents in the rock, and the air stinks of sulfur and scorched metal."
            )

        # Always set the room description for this coordinate.
        room.db.desc = desc

        # 3) Mark this tile as scavengable with biome-specific tags.
        try:
            # Clear old scavenge tags, then add new ones.
            if hasattr(room, "tags"):
                for tag in list(room.tags.all()):
                    t = str(tag).lower()
                    if t in ("wildscavenge", "urbanscavenge") or t.startswith("biome_") or t.startswith("scavenge_"):
                        room.tags.remove(tag)
                room.tags.add("wildscavenge")
                room.tags.add(f"biome_{biome}")
                room.tags.add(f"scavenge_{biome}")
        except Exception:
            pass

