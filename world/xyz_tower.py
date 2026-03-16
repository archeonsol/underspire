"""
Example XYZGrid map module for a small 3D structure (tower/shaft).

This is a thin wrapper over Evennia's contrib.grid.xyzgrid example, intended as
your starting point for a fully 3D map. You can expand, rename, or replace this
module with your own map data while keeping the XYZGrid mechanics.

Usage (from shell or CLI):

    evennia xyzgrid init
    evennia xyzgrid add world.xyz_tower
    evennia xyzgrid spawn

Then link into the grid with a normal exit from a city/wilderness room.
"""

from evennia.contrib.grid.xyzgrid import xymap, xyzgrid


# Minimal single Z-layer map: "tower" at zcoord "tower0".
# Use symbols and LEGEND to define walls/rooms/exits if you expand this.

MAP_TOWER_0 = {
    "zcoord": "tower0",
    "map": [
        "#####",
        "#...#",
        "#.@.#",
        "#...#",
        "#####",
    ],
    "legend": {
        "#": "wall",
        ".": "floor",
        "@": "start",
    },
}


def get_maps():
    """
    XYZGrid loader hook: returns iterable of map data dicts.

    The xyzgrid contrib will call this when you 'add world.xyz_tower'.
    """
    return [MAP_TOWER_0]

