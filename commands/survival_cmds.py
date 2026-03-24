"""
Survival commands: CmdEat, CmdDrink, _is_edible, _is_drinkable.
"""

from commands.base_cmds import Command
from commands.inventory_cmds import _obj_in_hands, _clear_hand_for_obj
from world.rpg.survival import apply_food_effects, apply_drink_effects


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


def _display_name(obj, looker):
    return obj.get_display_name(looker) if hasattr(obj, "get_display_name") else obj.name


def _resolve_held_consumable(caller, args, check_fn, empty_msg, wrong_type_msg):
    """
    Resolve which held object the caller wants to consume.

    Returns the object, or None if the command should abort (error already sent).
    """
    left = getattr(caller.db, "left_hand_obj", None)
    right = getattr(caller.db, "right_hand_obj", None)
    if not args:
        obj = None
        if right and right.location == caller and check_fn(right):
            obj = right
        elif left and left.location == caller and check_fn(left):
            obj = left
        if not obj:
            caller.msg(empty_msg)
            return None
    else:
        obj = caller.search(args, location=caller)
        if not obj:
            return None
        if not _obj_in_hands(caller, obj):
            caller.msg("You need to hold that in your hands to use it. Wield it first.")
            return None
    if not check_fn(obj):
        caller.msg(wrong_type_msg)
        return None
    return obj


def _broadcast_consume(caller, obj_name, verb):
    """Send a consume message to the room, guarding against None location."""
    if not caller.location:
        return
    caller_name = _display_name(caller, None)
    if hasattr(caller.location, "contents_get"):
        for viewer in caller.location.contents_get(content_type="character"):
            if viewer == caller:
                continue
            viewer.msg(f"{_display_name(caller, viewer)} {verb}s {obj_name}.")
    else:
        caller.location.msg_contents(f"{caller.name} {verb}s {obj_name}.", exclude=caller)


def _consume_object(caller, obj):
    """Decrement uses or delete the object, clearing the hand slot."""
    if getattr(obj.db, "uses_remaining", None) is not None:
        u = (obj.db.uses_remaining or 0) - 1
        obj.db.uses_remaining = u
        if u <= 0:
            _clear_hand_for_obj(caller, obj)
            obj.delete()
    else:
        _clear_hand_for_obj(caller, obj)
        obj.delete()


def _portion_value(total, portions_total, portions_left_before):
    """
    Return this-use share of a total effect, preserving exact totals over all portions.
    """
    try:
        total_f = float(total or 0)
        p_total = int(portions_total or 0)
        p_left = int(portions_left_before or 0)
    except Exception:
        return 0.0
    if total_f <= 0 or p_total <= 0 or p_left <= 0:
        return total_f
    consumed_before = p_total - p_left
    consumed_after = consumed_before + 1
    return (total_f * consumed_after / p_total) - (total_f * consumed_before / p_total)


def _apply_prepared_portion_effects(obj):
    """
    For prepared station items, scale this consume action to one of 5 portions.
    """
    portions_total = int(getattr(obj.db, "portions_total", 0) or 0)
    uses_left = int(getattr(obj.db, "uses_remaining", 0) or 0)
    if portions_total <= 0 or uses_left <= 0:
        return

    # Preserve original totals once, then overwrite per-use values each consume.
    if getattr(obj.db, "hunger_restore_total", None) is None:
        obj.db.hunger_restore_total = float(getattr(obj.db, "hunger_restore", 0) or 0)
    if getattr(obj.db, "thirst_restore_total", None) is None:
        obj.db.thirst_restore_total = float(getattr(obj.db, "thirst_restore", 0) or 0)
    if getattr(obj.db, "alcohol_strength_total", None) is None:
        obj.db.alcohol_strength_total = float(getattr(obj.db, "alcohol_strength", 0.0) or 0.0)

    h_total = float(getattr(obj.db, "hunger_restore_total", 0) or 0)
    t_total = float(getattr(obj.db, "thirst_restore_total", 0) or 0)
    a_total = float(getattr(obj.db, "alcohol_strength_total", 0.0) or 0.0)

    # hunger/thirst are int in survival effects; ceil avoids zero-effect micro-portions.
    from math import ceil
    h_share = _portion_value(h_total, portions_total, uses_left)
    t_share = _portion_value(t_total, portions_total, uses_left)
    a_share = _portion_value(a_total, portions_total, uses_left)

    if h_total > 0:
        obj.db.hunger_restore = max(1, int(ceil(h_share)))
    if t_total > 0:
        obj.db.thirst_restore = max(1, int(ceil(t_share)))
    if a_total > 0:
        obj.db.alcohol_strength = max(0.01, float(a_share))


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
        obj = _resolve_held_consumable(
            caller, args, _is_edible,
            empty_msg="You aren't holding anything to eat. Wield food first (e.g. wield ration, then eat).",
            wrong_type_msg="That isn't something you can eat.",
        )
        if not obj:
            return
        name = _display_name(obj, caller)
        caller.msg(f"You eat |w{name}|n.")
        taste_msg = getattr(getattr(obj, "db", None), "taste_msg", None)
        caller.msg(taste_msg or "You chew it down. Nothing remarkable about the taste.")
        _broadcast_consume(caller, name, "eat")
        _apply_prepared_portion_effects(obj)
        apply_food_effects(caller, obj)
        _consume_object(caller, obj)


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
        obj = _resolve_held_consumable(
            caller, args, _is_drinkable,
            empty_msg="You aren't holding anything to drink. Wield a drink first (e.g. wield canteen, then drink).",
            wrong_type_msg="That isn't something you can drink.",
        )
        if not obj:
            return
        name = _display_name(obj, caller)
        caller.msg(f"You drink |w{name}|n.")
        taste_msg = getattr(getattr(obj, "db", None), "taste_msg", None)
        caller.msg(taste_msg or "It goes down without much flavour.")
        _broadcast_consume(caller, name, "drink")
        _apply_prepared_portion_effects(obj)
        apply_drink_effects(caller, obj)
        _consume_object(caller, obj)
