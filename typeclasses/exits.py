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
    from world.rpg.staggered_movement import (
        WALK_DELAY,
        CRAWL_DELAY_EXHAUSTED,
        CRAWL_DELAY_LEG_TRAUMA,
        _staggered_walk_callback,
    )
except ImportError:
    WALK_DELAY = 3.5
    CRAWL_DELAY_EXHAUSTED = 8.5
    CRAWL_DELAY_LEG_TRAUMA = 16.0
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
        # Sitting/lying: must stand/get up first (check before any messages)
        if getattr(traversing_object.db, "sitting_on", None):
            traversing_object.msg("You need to stand up first.")
            return
        if getattr(traversing_object.db, "lying_on", None) or getattr(traversing_object.db, "lying_on_table", None):
            traversing_object.msg("You need to get up first.")
            return
        # Grappled: cannot walk away while someone has them locked in grasp.
        grappled_by = getattr(traversing_object.db, "grappled_by", None)
        if grappled_by:
            # get_display_name() is viewer-aware; show the grappler name from the victim's perspective if available.
            grappler_name = (
                grappled_by.get_display_name(traversing_object)
                if hasattr(grappled_by, "get_display_name")
                else getattr(grappled_by, "key", "someone")
            )
            traversing_object.msg(f"You're locked in {grappler_name}'s grasp. Use |wresist|n to break free.")
            return
        # Flatlined (dying): no movement — lock all IC action
        try:
            from world.death import is_flatlined
            if is_flatlined(traversing_object):
                traversing_object.msg("|rYou are dying. There is nothing you can do.|n")
                return
        except ImportError:
            pass
        # In combat (attacking or being attacked): must use flee to try to break away
        try:
            from world.combat import is_in_combat
            if is_in_combat(traversing_object):
                traversing_object.msg("You're in combat! Use |wflee|n or |wflee <direction>|n to try to break away.")
                return
        except ImportError:
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

        # Doors and faction-locked exits (before stamina / staggered move)
        try:
            from world.rpg.factions import is_faction_member
            from world.rpg.factions.membership import get_member_rank
            from world.rpg.factions.doors import staff_bypass as _faction_staff

            if _faction_staff(traversing_object):
                pass
            else:
                door = getattr(self.db, "door", None)
                if door and not getattr(self.db, "door_open", False):
                    dname = getattr(self.db, "door_name", None) or "door"
                    if getattr(self.db, "door_locked", None):
                        traversing_object.msg(f"The {dname} is locked.")
                    elif getattr(self.db, "bioscan", None):
                        dk = (self.key or "that way").strip()
                        traversing_object.msg(
                            f"The {dname} requires bioscan verification. Use: verify {dk}"
                        )
                    else:
                        traversing_object.msg(f"The {dname} is closed.")
                    return

                fk = getattr(self.db, "faction_required", None)
                if fk:
                    min_r = int(getattr(self.db, "faction_required_rank", None) or 1)
                    if not is_faction_member(traversing_object, fk):
                        traversing_object.msg("|rAccess denied. Wrong faction clearance.|n")
                        return
                    if get_member_rank(traversing_object, fk) < min_r:
                        traversing_object.msg("|rAccess denied. Insufficient rank.|n")
                        return
        except Exception:
            pass

        try:
            from world.rpg.stamina import is_exhausted, spend_stamina, STAMINA_COST_WALK, STAMINA_COST_CRAWL
        except ImportError:
            is_exhausted = lambda _: False
            spend_stamina = lambda _, __: True
            STAMINA_COST_WALK = 1
            STAMINA_COST_CRAWL = 0
        exhausted = is_exhausted(traversing_object)
        # Characters missing a leg/foot, or with an unsalvageable leg, must crawl (drag).
        try:
            missing = set(getattr(getattr(traversing_object, "db", None), "missing_body_parts", []) or [])
        except Exception:
            missing = set()
        leg_lost = bool(missing.intersection({"left thigh", "right thigh", "left foot", "right foot"}))
        try:
            from world.medical.limb_trauma import is_limb_destroyed
            if is_limb_destroyed(traversing_object, "left_leg") or is_limb_destroyed(traversing_object, "right_leg"):
                leg_lost = True
        except Exception:
            pass
        force_crawl = exhausted or leg_lost
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
            from world.rpg.survival import apply_move_hunger_thirst
            apply_move_hunger_thirst(traversing_object, traversing_object.location, destination)
        except Exception:
            pass

        # Starting a new move clears any previous "stop walking" request so
        # that fresh walks work normally.
        db = getattr(traversing_object, "db", None)
        if db is not None and hasattr(db, "cancel_walking"):
            try:
                del db.cancel_walking
            except Exception:
                db.cancel_walking = False

        if force_crawl:
            spend_stamina(traversing_object, STAMINA_COST_CRAWL)
            delay_secs = CRAWL_DELAY_LEG_TRAUMA if leg_lost else CRAWL_DELAY_EXHAUSTED
            direction = stagger_direction or (self.key or "away").strip()
            if leg_lost:
                traversing_object.msg(f"You drag yourself {direction}, barely moving.")
            else:
                traversing_object.msg(f"You crawl slowly {direction}.")
        else:
            spend_stamina(traversing_object, STAMINA_COST_WALK)
            delay_secs = WALK_DELAY
            direction = stagger_direction or (self.key or "away").strip()
            traversing_object.msg(f"You begin walking {direction}.")

        # Announce staggered move to others in the room with recog-aware names.
        loc = traversing_object.location
        if loc:
            from world.rp_features import get_move_display_for_viewer
            viewers = [c for c in loc.contents_get(content_type="character") if c is not traversing_object]
            for viewer in viewers:
                display = get_move_display_for_viewer(traversing_object, viewer)
                if force_crawl:
                    viewer.msg(
                        f"{display} drags along the ground {direction}."
                        if leg_lost
                        else f"{display} crawls slowly {direction}."
                    )
                else:
                    viewer.msg(f"{display} begins walking {direction}.")
        cb = _staggered_walk_callback
        if cb:
            delay(delay_secs, cb, traversing_object.id, destination.id)
        else:
            # Never move instantly — same delay as normal stagger (fixes missing callback = teleport bug).
            def _fallback_move():
                o, d = traversing_object, destination
                if not o or not d:
                    return
                db = getattr(o, "db", None)
                if db is not None and getattr(db, "cancel_walking", False):
                    try:
                        del db.cancel_walking
                    except Exception:
                        db.cancel_walking = False
                    return
                o.move_to(d)
                victim = getattr(getattr(o, "db", None), "grappling", None)
                if victim and hasattr(victim, "move_to"):
                    victim.move_to(d, quiet=True)
                    if d and hasattr(d, "contents_get"):
                        for v in d.contents_get(content_type="character"):
                            if v in (o, victim):
                                continue
                            vname = victim.get_display_name(v) if hasattr(victim, "get_display_name") else victim.name
                            oname = o.get_display_name(v) if hasattr(o, "get_display_name") else o.name
                            v.msg("%s is dragged in by %s." % (vname, oname))

            delay(delay_secs, _fallback_move)
        return
