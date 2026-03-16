"""
Custom exit type for leaving the city into the wilderness and returning.

- OutsideToWildernessExit: attach to an 'outside' exit in your city gate room.
  Delayed move (10-12 s) with ambient messages; then enter wilderness.
- InsideToCityExit: created automatically at wilderness (0,0) by ColonyWildernessProvider;
  delayed move (same as outside) with ambient messages (guards, etc.), then to city gate.
"""

from evennia.objects.objects import DefaultExit
from evennia.utils import delay
from evennia.utils.search import search_object

# Delay (seconds) before actually entering the wilderness from the gate
OUTSIDE_TO_WILDS_DELAY = 11
# Delay (seconds) before actually entering the city from the wilderness (inside)
INSIDE_TO_CITY_DELAY = 11


def _outside_to_wilds_callback(obj_id, step):
    """Step 0 = second ambient message, 1 = third, 2 = enter wilderness."""
    objs = search_object("#%s" % obj_id)
    if not objs:
        return
    obj = objs[0]
    if not obj or not obj.location:
        return
    if step == 0:
        obj.msg("|xThe air changes. The safety of the gates falls behind.|n")
    elif step == 1:
        obj.msg("|xYou step out into the dangerous wilds.|n")
    elif step == 2:
        from evennia.contrib.grid import wilderness
        from world.wilderness_map import CITY_GATE_COORD
        old_loc = obj.location
        ok = wilderness.enter_wilderness(obj, coordinates=CITY_GATE_COORD, name="colony_wilds")
        if not ok:
            obj.msg("|rThe gates refuse to open onto the wastes right now.|n")
        else:
            if old_loc:
                old_loc.msg_contents(
                    "%s passes through the gate and is gone." % obj.get_display_name(old_loc),
                    exclude=obj,
                )
            # Auto-look so they see the wilderness room as soon as they step out
            if obj.location and hasattr(obj.location, "return_appearance"):
                obj.msg(obj.location.return_appearance(obj))


def _inside_to_city_callback(obj_id, gate_id, step):
    """Step 0 = second ambient message, 1 = third, 2 = move to city gate."""
    objs = search_object("#%s" % obj_id)
    gates = search_object("#%s" % gate_id)
    if not objs:
        return
    obj = objs[0]
    if not obj or not obj.location:
        return
    if step == 0:
        obj.msg("|xYou pass the threshold. The guards stare at you with suspicion as you step inside.|n")
    elif step == 1:
        obj.msg("|xThe hum of the undercity closes around you. You are inside.|n")
    elif step == 2:
        if not gates:
            obj.msg("|rThe way inside is not open.|n")
            return
        gate = gates[0]
        if not gate:
            obj.msg("|rThe way inside is not open.|n")
            return
        old_loc = obj.location
        obj.move_to(gate, quiet=False)
        if old_loc:
            old_loc.msg_contents(
                "%s passes through the gate toward the city." % obj.get_display_name(old_loc),
                exclude=obj,
            )
        if gate:
            gate.msg_contents(
                "%s arrives from the wilds, past the guards." % obj.get_display_name(gate),
                exclude=obj,
            )


class OutsideToWildernessExit(DefaultExit):
    """
    Exit that leads from the city gate into the wilderness map.
    Uses delayed movement (10-12 s) with 2-3 ambient messages before entering.
    """

    def at_traverse(self, traversing_object, destination):
        from evennia.contrib.grid import wilderness
        from world.wilderness_map import CITY_GATE_COORD

        if not traversing_object:
            return

        # Staggered exit: ambient messages then enter after OUTSIDE_TO_WILDS_DELAY
        traversing_object.msg("|xYou make for the gate. Beyond lies the waste.|n")
        loc = traversing_object.location
        if loc:
            loc.msg_contents(
                "%s heads for the gate, toward the wilds." % traversing_object.get_display_name(loc),
                exclude=traversing_object,
            )
        delay(4, _outside_to_wilds_callback, traversing_object.id, 0)
        delay(8, _outside_to_wilds_callback, traversing_object.id, 1)
        delay(OUTSIDE_TO_WILDS_DELAY, _outside_to_wilds_callback, traversing_object.id, 2)


class InsideToCityExit(DefaultExit):
    """
    Exit that appears only at wilderness (0,0). When traversed, uses delayed
    movement (same as going outside) with ambient messages, then moves to the
    city gate room.
    """

    def at_traverse(self, traversing_object, destination):
        from world.wilderness_map import get_city_gate_room

        if not traversing_object or not traversing_object.location:
            return
        room = traversing_object.location
        wilderness_script = getattr(room, "wilderness", None)
        provider = getattr(wilderness_script, "mapprovider", None) if wilderness_script else None
        gate = get_city_gate_room(provider) if provider else None
        if not gate:
            # Fallback: resolve city gate by tag so "inside" works even if provider/path wasn't set
            from evennia.utils.search import search_tag
            tagged = search_tag("city_gate")
            for obj in (tagged or []):
                if getattr(obj, "location", None) is None and hasattr(obj, "at_object_leave"):
                    gate = obj
                    break
        if not gate:
            traversing_object.msg("|rThe way inside is not open.|n")
            return

        # Staggered entry: ambient messages then move after INSIDE_TO_CITY_DELAY
        traversing_object.msg("|xYou make for the gate. The walls of the colony rise ahead.|n")
        if room:
            room.msg_contents(
                "%s heads for the gate, toward the city." % traversing_object.get_display_name(room),
                exclude=traversing_object,
            )
        delay(4, _inside_to_city_callback, traversing_object.id, gate.id, 0)
        delay(8, _inside_to_city_callback, traversing_object.id, gate.id, 1)
        delay(INSIDE_TO_CITY_DELAY, _inside_to_city_callback, traversing_object.id, gate.id, 2)

