"""
Survival commands: CmdEat, CmdDrink, _is_edible, _is_drinkable.
"""

from commands.base_cmds import Command
from commands.inventory_cmds import _obj_in_hands, _clear_hand_for_obj


def _is_edible(obj):
    """True if object is food (tag 'food' or db.edible)."""
    if getattr(obj, "tags", None) and obj.tags.has("food"):
        return True
    return bool(getattr(obj.db, "edible", False))


def _is_drinkable(obj):
    """True if object is drink (tag 'drink' or db.drinkable)."""
    if getattr(obj, "tags", None) and obj.tags.has("drink"):
        return True
    return bool(getattr(obj.db, "drinkable", False))


class CmdEat(Command):
    """
    Eat something you're holding. You must wield (hold) the food first.

    Usage:
      eat [item]
    """
    key = "eat"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        left = getattr(caller.db, "left_hand_obj", None)
        right = getattr(caller.db, "right_hand_obj", None)
        if not args:
            obj = None
            if right and right.location == caller and _is_edible(right):
                obj = right
            elif left and left.location == caller and _is_edible(left):
                obj = left
            if not obj:
                caller.msg("You aren't holding anything to eat. Wield food first (e.g. wield ration, then eat).")
                return
        else:
            obj = caller.search(args, location=caller)
            if not obj:
                return
            if not _obj_in_hands(caller, obj):
                caller.msg("You need to hold that in your hands to eat it. Wield it first.")
                return
        if not _is_edible(obj):
            caller.msg("That isn't something you can eat.")
            return
        name = obj.get_display_name(caller) if hasattr(obj, "get_display_name") else obj.name
        caller.msg("You eat |w%s|n." % name)
        taste_msg = getattr(getattr(obj, "db", None), "taste_msg", None)
        caller.msg(taste_msg or "You taste it, but nothing stands out.")
        if hasattr(caller.location, "contents_get"):
            for v in caller.location.contents_get(content_type="character"):
                if v == caller:
                    continue
                v.msg("%s eats %s." % (caller.get_display_name(v) if hasattr(caller, "get_display_name") else caller.name, name))
        else:
            caller.location.msg_contents("%s eats %s." % (caller.name, name), exclude=caller)
        # Apply survival effects: hunger and nutrition.
        from world.rpg.survival import apply_food_effects
        apply_food_effects(caller, obj)
        # Consume: delete single-use or decrement uses
        if getattr(obj.db, "uses_remaining", None) is not None:
            u = (obj.db.uses_remaining or 0) - 1
            obj.db.uses_remaining = u
            if u <= 0:
                _clear_hand_for_obj(caller, obj)
                obj.delete()
        else:
            _clear_hand_for_obj(caller, obj)
            obj.delete()


class CmdDrink(Command):
    """
    Drink something you're holding. You must wield (hold) the drink first.

    Usage:
      drink [item]
    """
    key = "drink"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        left = getattr(caller.db, "left_hand_obj", None)
        right = getattr(caller.db, "right_hand_obj", None)
        if not args:
            obj = None
            if right and right.location == caller and _is_drinkable(right):
                obj = right
            elif left and left.location == caller and _is_drinkable(left):
                obj = left
            if not obj:
                caller.msg("You aren't holding anything to drink. Wield a drink first (e.g. wield canteen, then drink).")
                return
        else:
            obj = caller.search(args, location=caller)
            if not obj:
                return
            if not _obj_in_hands(caller, obj):
                caller.msg("You need to hold that in your hands to drink it. Wield it first.")
                return
        if not _is_drinkable(obj):
            caller.msg("That isn't something you can drink.")
            return
        name = obj.get_display_name(caller) if hasattr(obj, "get_display_name") else obj.name
        caller.msg("You drink |w%s|n." % name)
        taste_msg = getattr(getattr(obj, "db", None), "taste_msg", None)
        caller.msg(taste_msg or "You taste it, but nothing stands out.")
        if hasattr(caller.location, "contents_get"):
            for v in caller.location.contents_get(content_type="character"):
                if v == caller:
                    continue
                v.msg("%s drinks %s." % (caller.get_display_name(v) if hasattr(caller, "get_display_name") else caller.name, name))
        else:
            caller.location.msg_contents("%s drinks %s." % (caller.name, name), exclude=caller)
        # Apply survival effects: thirst and/or alcohol.
        from world.rpg.survival import apply_drink_effects
        apply_drink_effects(caller, obj)
        if getattr(obj.db, "uses_remaining", None) is not None:
            u = (obj.db.uses_remaining or 0) - 1
            obj.db.uses_remaining = u
            if u <= 0:
                _clear_hand_for_obj(caller, obj)
                obj.delete()
        else:
            _clear_hand_for_obj(caller, obj)
            obj.delete()
