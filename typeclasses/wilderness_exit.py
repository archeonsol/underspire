"""
Custom exit type for leaving the city into the wilderness and returning.

- OutsideToWildernessExit: attach to an 'outside' exit in your city gate room.
- InsideToCityExit: created automatically at wilderness (0,0) by ColonyWildernessProvider;
  sends players back to the city gate when they type 'inside' or 'in'.
"""

from evennia.objects.objects import DefaultExit


class OutsideToWildernessExit(DefaultExit):
    """
    Exit that leads from the city gate into the wilderness map.
    """

    def at_traverse(self, traversing_object, destination):
        from evennia.contrib.grid import wilderness
        from world.wilderness_map import CITY_GATE_COORD

        if not traversing_object:
            return

        ok = wilderness.enter_wilderness(traversing_object, coordinates=CITY_GATE_COORD, name="colony_wilds")
        if not ok:
            traversing_object.msg("|rThe gates refuse to open onto the wastes right now.|n")


class InsideToCityExit(DefaultExit):
    """
    Exit that appears only at wilderness (0,0). When traversed, moves the
    character to the city gate room (configured on ColonyWildernessProvider).
    """

    def at_traverse(self, traversing_object, destination):
        from world.wilderness_map import get_city_gate_room

        if not traversing_object or not traversing_object.location:
            return
        room = traversing_object.location
        wilderness_script = getattr(room, "wilderness", None)
        if not wilderness_script:
            traversing_object.msg("|rYou can't go inside from here.|n")
            return
        provider = getattr(wilderness_script, "mapprovider", None)
        gate = get_city_gate_room(provider) if provider else None
        if not gate:
            traversing_object.msg("|rThe way inside is not open.|n")
            return
        traversing_object.move_to(gate, quiet=False)

