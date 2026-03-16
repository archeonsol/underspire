"""
Exits

Exits are connectors between Rooms. An exit always has a destination property
set and has a single command defined on itself with the same name as its key,
for allowing Characters to traverse the exit to its destination.

Movement is staggered for RP: "You begin walking north" then 3–4 seconds later the move completes.
"""

from evennia.utils import delay
from evennia.objects.objects import DefaultExit

from .objects import ObjectParent

try:
    from world.staggered_movement import WALK_DELAY, CRAWL_DELAY, _staggered_walk_callback
except ImportError:
    WALK_DELAY = 3.5
    CRAWL_DELAY = 7.0
    _staggered_walk_callback = None


class Exit(ObjectParent, DefaultExit):
    """
    Exits are connectors between rooms. Movement is staggered: you see "You begin walking X"
    then after a short delay you arrive (for RP). Exhausted characters crawl (slower; stamina cost already 0).
    """

    def at_traverse(self, traversing_object, destination):
        if not destination:
            super().at_traverse(traversing_object, destination)
            return
        # Flatlined (dying): no movement — lock all IC action
        try:
            from world.death import is_flatlined
            if is_flatlined(traversing_object):
                traversing_object.msg("|rYou are dying. There is nothing you can do.|n")
                return
        except ImportError:
            pass
        # In combat: must use flee to try to break away
        if getattr(traversing_object.db, "combat_target", None) is not None:
            traversing_object.msg("You're in combat! Use |wflee|n or |wflee <direction>|n to try to break away.")
            return
        # Voided characters cannot leave the void room
        if getattr(traversing_object.db, "voided", False):
            try:
                from evennia.server.models import ServerConfig
                void_id = ServerConfig.objects.conf("VOID_ROOM_ID", default=None)
                if void_id is not None and getattr(destination, "id", None) != int(void_id):
                    traversing_object.msg("|rYou cannot leave the void.|n")
                    return
            except Exception:
                pass
        try:
            from world.stamina import is_exhausted, spend_stamina, STAMINA_COST_WALK, STAMINA_COST_CRAWL
        except ImportError:
            is_exhausted = lambda _: False
            spend_stamina = lambda _, __: True
            STAMINA_COST_WALK = 1
            STAMINA_COST_CRAWL = 0
        exhausted = is_exhausted(traversing_object)
        # Characters missing a leg/foot can only crawl (dragging themselves).
        try:
            missing = set(getattr(getattr(traversing_object, "db", None), "missing_body_parts", []) or [])
        except Exception:
            missing = set()
        leg_lost = bool(missing.intersection({"left thigh", "right thigh", "left foot", "right foot"}))
        if leg_lost:
            exhausted = True
        # High intoxication: occasionally stagger into a random exit instead of intended one.
        stagger_direction = None
        try:
            drunk_level = int(getattr(getattr(traversing_object, "db", None), "drunk_level", 0) or 0)
        except Exception:
            drunk_level = 0
        if drunk_level >= 3:
            import random
            # 25% chance to misstep on each move.
            if random.random() < 0.25:
                exits_here = [o for o in (getattr(traversing_object.location, "contents", None) or []) if getattr(o, "destination", None)]
                if exits_here:
                    stagger_exit = random.choice(exits_here)
                    if getattr(stagger_exit, "destination", None):
                        destination = stagger_exit.destination
                        stagger_direction = (stagger_exit.key or "away").strip()
        # Drain hunger/thirst only when traversing scavenging tiles (wilderness/urban).
        try:
            from world.survival import apply_move_hunger_thirst
            apply_move_hunger_thirst(traversing_object, traversing_object.location, destination)
        except Exception:
            pass

        if exhausted:
            spend_stamina(traversing_object, STAMINA_COST_CRAWL)
            delay_secs = CRAWL_DELAY
            direction = stagger_direction or (self.key or "away").strip()
            traversing_object.msg(f"You crawl slowly {direction}.")
            room_msg = f"{traversing_object.get_display_name(traversing_object)} crawls slowly {direction}."
        else:
            spend_stamina(traversing_object, STAMINA_COST_WALK)
            delay_secs = WALK_DELAY
            direction = stagger_direction or (self.key or "away").strip()
            traversing_object.msg(f"You begin walking {direction}.")
            room_msg = f"{traversing_object.get_display_name(traversing_object)} begins walking {direction}."
        loc = traversing_object.location
        if loc:
            loc.msg_contents(room_msg, exclude=traversing_object)
        if _staggered_walk_callback:
            delay(delay_secs, _staggered_walk_callback, traversing_object.id, destination.id)
        else:
            traversing_object.move_to(destination)
            victim = getattr(getattr(traversing_object, "db", None), "grappling", None)
            if victim and hasattr(victim, "move_to"):
                victim.move_to(destination, quiet=True)
                destination.msg_contents(
                    "%s is dragged in by %s." % (victim.name, traversing_object.name),
                    exclude=(traversing_object, victim),
                )
        return
