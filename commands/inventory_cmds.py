"""
Inventory and equipment commands: CmdInventory, CmdWield, CmdUnwield, CmdFreehands, CmdWear, CmdRemove,
CmdStrip, CmdFrisk, CmdCheckAmmo, CmdReload, CmdUnload, and helpers _hands_required, _obj_in_hands,
_update_primary_wielded, _clear_hand_for_obj, _frisk_readout.
"""

from commands.base_cmds import Command
from evennia.utils import logger


def _hands_required(weapon_key):
    """Return 1 or 2 hands needed for this weapon key."""
    from world.combat import WEAPON_HANDS
    return WEAPON_HANDS.get(weapon_key, 1)


def _obj_in_hands(caller, obj):
    """True if obj is held in either hand (and still on caller)."""
    if not obj or getattr(obj, "location", None) != caller:
        return False
    left = getattr(caller.db, "left_hand_obj", None)
    right = getattr(caller.db, "right_hand_obj", None)
    return left is obj or right is obj


def _update_primary_wielded(caller):
    """Set wielded_obj and wielded from hands (right takes precedence for combat)."""
    right = getattr(caller.db, "right_hand_obj", None)
    left = getattr(caller.db, "left_hand_obj", None)
    primary = right if right and right.location == caller else (left if left and left.location == caller else None)
    caller.db.wielded_obj = primary
    if not primary:
        caller.db.wielded = None
        return
    try:
        from typeclasses.weapons import get_weapon_key
        caller.db.wielded = get_weapon_key(primary) or getattr(primary.db, "weapon_key", None)
    except Exception as e:
        logger.log_trace("inventory_cmds._update_primary_wielded: %s" % e)
        caller.db.wielded = getattr(primary.db, "weapon_key", None)


def _clear_hand_for_obj(caller, obj):
    """Clear the hand that holds obj and update primary wielded."""
    if getattr(caller.db, "left_hand_obj", None) is obj:
        caller.db.left_hand_obj = None
    if getattr(caller.db, "right_hand_obj", None) is obj:
        caller.db.right_hand_obj = None
    _update_primary_wielded(caller)


def _frisk_readout(caller, target):
    """One-time inventory readout for frisk/loot: show what target is carrying (excluding worn)."""
    from evennia.utils.utils import list_to_string
    from world.clothing import get_worn_items
    worn_objs = set(get_worn_items(target))
    contents = [o for o in target.contents if o != caller and o not in worn_objs]
    tname = target.get_display_name(caller)
    if not contents:
        caller.msg(f"You've checked {tname}. Nothing of interest on them.")
    else:
        names = [obj.get_display_name(caller) for obj in contents]
        caller.msg(f"You've checked {tname}. |wCarrying:|n " + list_to_string(names, endsep=" and ") + ".")


class CmdWield(Command):
    """
    Wield a weapon from your inventory. One-handed uses one hand, two-handed uses both.

    Usage:
      wield <weapon>
    """
    key = "wield"
    locks = "cmd:all()"
    help_category = "Combat"
    usage_typeclasses = ["typeclasses.weapons.CombatWeapon"]
    usage_hint = "|wwield <weapon>|n (e.g. wield katana)"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("What do you want to wield? Usage: wield <weapon>")
            return
        # Retractable claws lock out manual hand use while deployed.
        for cw in (getattr(caller.db, "cyberware", None) or []):
            if type(cw).__name__ == "RetractableClaws" and bool(getattr(cw.db, "claws_deployed", False)) and not bool(getattr(cw.db, "malfunctioning", False)):
                caller.msg("Your deployed claws prevent you from holding items. Retract them first.")
                return

        try:
            from world.medical.limb_trauma import is_hand_usable
            use_left = is_hand_usable(caller, "left")
            use_right = is_hand_usable(caller, "right")
        except Exception:
            use_left = use_right = True
        if not use_left and not use_right:
            caller.msg("Your arms are ruined. You can't hold anything until you get chrome.")
            return

        target = caller.search(self.args.strip(), location=caller)
        if not target:
            return

        # Try to resolve a combat weapon key if this is a weapon; if not, it's still holdable,
        # but will not be treated as a combat weapon by the combat system.
        try:
            from typeclasses.weapons import get_weapon_key
            weapon_key = get_weapon_key(target)
        except Exception as e:
            logger.log_trace("inventory_cmds.CmdWield get_weapon_key: %s" % e)
            weapon_key = getattr(target.db, "weapon_key", None)
        if weapon_key and not getattr(target.db, "weapon_key", None):
            target.db.weapon_key = weapon_key  # persist
        hands_needed = _hands_required(weapon_key) if weapon_key else 1
        left = getattr(caller.db, "left_hand_obj", None)
        right = getattr(caller.db, "right_hand_obj", None)
        if hands_needed == 2:
            if not (use_left and use_right):
                caller.msg("You need two working arms to wield that. Your limb won't cooperate.")
                return
            if left or right:
                caller.msg("You need both hands free to wield that. Unwield or drop what you're holding first.")
                return
        else:
            if left and right:
                caller.msg("You have no free hand. Unwield or drop something first.")
                return
        try:
            from world.ammo import is_ranged_weapon, WEAPON_AMMO_TYPE, DEFAULT_AMMO_CAPACITY
            if is_ranged_weapon(weapon_key) and not getattr(target.db, "ammo_type", None):
                target.db.ammo_type = WEAPON_AMMO_TYPE.get(weapon_key)
                target.db.ammo_capacity = DEFAULT_AMMO_CAPACITY.get(weapon_key, 0)
                target.db.ammo_current = int(getattr(target.db, "ammo_current", 0) or 0)
        except Exception as e:
            logger.log_trace("inventory_cmds.CmdWield ammo init: %s" % e)
        if hands_needed == 2:
            caller.db.left_hand_obj = target
            caller.db.right_hand_obj = target
        else:
            if not right and use_right:
                caller.db.right_hand_obj = target
            elif not left and use_left:
                caller.db.left_hand_obj = target
            else:
                caller.msg("You have no free usable hand.")
                return
        _update_primary_wielded(caller)
        if getattr(caller.db, "combat_target", None) is not None:
            caller.db.combat_skip_next_turn = True
        item_name_self = target.get_display_name(caller) if hasattr(target, "get_display_name") else target.name
        caller.msg(f"You hold |w{item_name_self}|n in your hands.")
        if caller.location and hasattr(caller.location, "contents_get"):
            for viewer in caller.location.contents_get(content_type="character"):
                if viewer == caller:
                    continue
                vcaller = caller.get_display_name(viewer) if hasattr(caller, "get_display_name") else caller.name
                vitem = target.get_display_name(viewer) if hasattr(target, "get_display_name") else target.name
                viewer.msg(f"{vcaller} holds {vitem} in their hands.")


class CmdUnwield(Command):
    """
    Stop wielding the current weapon and put it back in your inventory.

    Usage:
      unwield
      unwield <weapon>
    """
    key = "unwield"
    locks = "cmd:all()"
    help_category = "Combat"
    usage_hint = "|wunwield|n or |wunwield <weapon>|n"

    def func(self):
        caller = self.caller
        left = getattr(caller.db, "left_hand_obj", None)
        right = getattr(caller.db, "right_hand_obj", None)
        if not self.args.strip():
            # Unwield primary (right hand, or left if no right)
            target = right if right and right.location == caller else (left if left and left.location == caller else None)
            if not target:
                caller.msg("You aren't wielding anything.")
                return
        else:
            target = caller.search(self.args.strip(), location=caller)
            if not target:
                return
            if target is not left and target is not right:
                caller.msg(f"You aren't wielding {target.name}.")
                return
        # Clear only the hand that holds this item
        if getattr(caller.db, "left_hand_obj", None) is target:
            caller.db.left_hand_obj = None
        if getattr(caller.db, "right_hand_obj", None) is target:
            caller.db.right_hand_obj = None
        _update_primary_wielded(caller)
        if getattr(caller.db, "combat_target", None) is not None:
            caller.db.combat_skip_next_turn = True
        item_name_self = target.get_display_name(caller) if hasattr(target, "get_display_name") else target.name
        caller.msg(f"You put away |w{item_name_self}|n.")
        if caller.location and hasattr(caller.location, "contents_get"):
            for viewer in caller.location.contents_get(content_type="character"):
                if viewer == caller:
                    continue
                vcaller = caller.get_display_name(viewer) if hasattr(caller, "get_display_name") else caller.name
                vitem = target.get_display_name(viewer) if hasattr(target, "get_display_name") else target.name
                viewer.msg(f"{vcaller} puts away {vitem}.")


class CmdFreehands(Command):
    """
    Put away whatever you're holding in your hands (unwield / free hands).
    Usage: fh   or   freehands
    """
    key = "fh"
    aliases = ["freehands"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        left = getattr(caller.db, "left_hand_obj", None)
        right = getattr(caller.db, "right_hand_obj", None)
        if (not left or left.location != caller) and (not right or right.location != caller):
            caller.msg("Your hands are already free.")
            return
        names = []
        if left and left.location == caller:
            names.append(left)
        if right and right.location == caller and right is not left:
            names.append(right)
        caller.db.left_hand_obj = None
        caller.db.right_hand_obj = None
        _update_primary_wielded(caller)
        if getattr(caller.db, "combat_target", None) is not None:
            caller.db.combat_skip_next_turn = True
        # Build name list for self
        self_names = [
            (obj.get_display_name(caller) if hasattr(obj, "get_display_name") else obj.name)
            for obj in names
        ]
        caller.msg(f"You put away {' and '.join('|w' + n + '|n' for n in self_names)}.")
        # Echo to observers
        if caller.location and hasattr(caller.location, "contents_get"):
            for viewer in caller.location.contents_get(content_type="character"):
                if viewer == caller:
                    continue
                vcaller = caller.get_display_name(viewer) if hasattr(caller, "get_display_name") else caller.name
                vnames = [
                    (obj.get_display_name(viewer) if hasattr(obj, "get_display_name") else obj.name)
                    for obj in names
                ]
                viewer.msg(f"{vcaller} puts away {' and '.join(vnames)}.")


class CmdInventory(Command):
    """
    Show what you're holding in your hands and your inventory.
    Usage: inventory   or   inv   or   i
    """
    key = "inventory"
    aliases = ["inv", "i"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        left = getattr(caller.db, "left_hand_obj", None)
        right = getattr(caller.db, "right_hand_obj", None)
        hand_parts = []
        if right and right.location == caller:
            hand_parts.append(f"{right.get_display_name(caller) if hasattr(right, 'get_display_name') else right.name} (right)")
        if left and left.location == caller and left is not right:
            hand_parts.append(f"{left.get_display_name(caller) if hasattr(left, 'get_display_name') else left.name} (left)")
        if hand_parts:
            hands_line = "|wHolding in hands:|n " + ", ".join(hand_parts)
        else:
            hands_line = "|wHolding in hands:|n Your hands are free."
        items = [o for o in caller.contents if o]
        if not items:
            caller.msg(hands_line + "\n\n|wYou are carrying:|n Nothing.")
            return
        from evennia.utils import utils
        from evennia.utils.ansi import raw as raw_ansi
        try:
            from world.clothing import get_worn_items
            worn_set = set(get_worn_items(caller))
        except Exception as e:
            logger.log_trace("inventory_cmds.CmdInventory get_worn_items: %s" % e)
            worn_set = set()
        lines = [hands_line, ""]
        table = self.styled_table(border="header")
        wielded_set = {left, right} if left or right else set()
        for key, desc, obj_list in utils.group_objects_by_key_and_desc(items, caller=caller):
            if wielded_set and obj_list and any(o in wielded_set for o in obj_list):
                key = f"{key} |y(wielded)|n"
            elif worn_set and obj_list and any(o in worn_set for o in obj_list):
                key = f"{key} |y(worn)|n"
            table.add_row(
                f"|C{key}|n",
                "{}|n".format(utils.crop(raw_ansi(desc or ""), width=50) or ""),
            )
        lines.append(f"|wYou are carrying:\n{table}")
        caller.msg("\n".join(lines))


class CmdReload(Command):
    """
    Load ammunition into a ranged weapon. Wield the weapon, have matching ammo in inventory.

    Usage:
      reload              - load wielded weapon from ammo in inventory
      reload <weapon>     - load specified weapon (must be in inventory)
    """
    key = "reload"
    locks = "cmd:all()"
    help_category = "Combat"
    usage_typeclasses = ["typeclasses.weapons.CombatWeapon", "typeclasses.ammo.Ammo"]
    usage_hint = "|wreload|n (ranged weapon when wielded; ammo from inventory)"

    def func(self):
        caller = self.caller
        weapon = None
        if self.args.strip():
            weapon = caller.search(self.args.strip(), location=caller)
            if not weapon:
                return
        else:
            weapon = getattr(caller.db, "wielded_obj", None)
            if weapon and weapon.location != caller:
                weapon = None
            if not weapon:
                caller.msg("Wield a ranged weapon first, or specify one: |wreload <weapon>|n.")
                return

        from world.ammo import is_ranged_weapon, AMMO_TYPES, AMMO_TYPE_DISPLAY_NAMES
        weapon_key = getattr(weapon.db, "weapon_key", None)
        if not weapon_key or not is_ranged_weapon(weapon_key):
            caller.msg(f"{weapon.name} doesn't use ammunition.")
            return

        ammo_type = getattr(weapon.db, "ammo_type", None)
        if not ammo_type or ammo_type not in AMMO_TYPES:
            caller.msg(f"{weapon.name} has no ammo type set.")
            return

        capacity = int(getattr(weapon.db, "ammo_capacity", 0) or 0)
        current = int(getattr(weapon.db, "ammo_current", 0) or 0)
        need = capacity - current
        if need <= 0:
            caller.msg(f"{weapon.name} is already fully loaded ({current}/{capacity}).")
            return

        # Find matching ammo in caller's inventory
        ammo_candidates = [obj for obj in caller.contents if getattr(obj.db, "ammo_type", None) == ammo_type and (int(getattr(obj.db, "quantity", 0) or 0) > 0)]
        if not ammo_candidates:
            type_name = AMMO_TYPE_DISPLAY_NAMES.get(ammo_type, ammo_type)
            caller.msg(f"You have no {type_name} ammo in your inventory.")
            return

        # Use first stack with quantity
        ammo_stack = ammo_candidates[0]
        take = min(need, int(ammo_stack.db.quantity or 0))
        if take <= 0:
            caller.msg("That ammo stack is empty.")
            return

        weapon.db.ammo_current = current + take
        ammo_stack.db.quantity = int(ammo_stack.db.quantity or 0) - take
        type_name = AMMO_TYPE_DISPLAY_NAMES.get(ammo_type, ammo_type)
        caller.msg(f"You load {take} round(s) into |w{weapon.name}|n. ({current + take}/{capacity})")
        if ammo_stack.db.quantity <= 0:
            ammo_stack.delete()


class CmdUnload(Command):
    """
    Eject the magazine from a ranged weapon and get it back as an item.

    Usage:
      unload              - eject mag from wielded weapon
      unload <weapon>     - eject mag from specified weapon (in inventory)
    """
    key = "unload"
    aliases = ["eject", "eject mag"]
    locks = "cmd:all()"
    help_category = "Combat"
    usage_typeclasses = ["typeclasses.weapons.CombatWeapon"]
    usage_hint = "|wunload|n (when wielded, ranged only)"

    def func(self):
        caller = self.caller
        weapon = None
        if self.args.strip():
            weapon = caller.search(self.args.strip(), location=caller)
            if not weapon:
                return
        else:
            weapon = getattr(caller.db, "wielded_obj", None)
            if weapon and weapon.location != caller:
                weapon = None
            if not weapon:
                caller.msg("Wield a ranged weapon first, or specify one: |wunload <weapon>|n.")
                return

        from world.ammo import (
            is_ranged_weapon, AMMO_TYPES, AMMO_TYPE_TYPECLASS, AMMO_TYPE_MAGAZINE_KEY,
        )
        weapon_key = getattr(weapon.db, "weapon_key", None)
        if not weapon_key or not is_ranged_weapon(weapon_key):
            caller.msg(f"{weapon.name} doesn't use magazines.")
            return

        ammo_type = getattr(weapon.db, "ammo_type", None)
        if not ammo_type or ammo_type not in AMMO_TYPES:
            caller.msg(f"{weapon.name} has no ammo type set.")
            return

        current = int(getattr(weapon.db, "ammo_current", 0) or 0)
        if current <= 0:
            caller.msg(f"{weapon.name} is already empty. Nothing to eject.")
            return

        typeclass_path = AMMO_TYPE_TYPECLASS.get(ammo_type)
        if not typeclass_path:
            caller.msg("Cannot create magazine for that ammo type.")
            return

        from evennia.utils.create import create_object
        key = AMMO_TYPE_MAGAZINE_KEY.get(ammo_type, "magazine")
        try:
            mag = create_object(typeclass_path, key=key, location=caller)
            mag.db.quantity = current
            weapon.db.ammo_current = 0
            caller.msg(f"You eject the magazine from |w{weapon.name}|n. You have |w{mag.name}|n ({current} rounds) in hand.")
        except Exception as e:
            caller.msg(f"|rCould not eject magazine: {e}|n")


class CmdCheckAmmo(Command):
    """
    Check how many rounds are left in a ranged weapon's magazine (without unloading).

    Usage:
      check ammo              - check wielded weapon
      check ammo <weapon>     - check specified weapon
      ammo
      mag
    """
    key = "check ammo"
    aliases = ["ammo", "mag", "check mag", "rounds"]
    locks = "cmd:all()"
    help_category = "Combat"
    usage_typeclasses = ["typeclasses.weapons.CombatWeapon"]
    usage_hint = "|wcheck ammo|n (when wielded, ranged only)"

    def func(self):
        caller = self.caller
        weapon = None
        args = self.args.strip() if self.args else ""
        if args:
            weapon = caller.search(args, location=caller)
            if not weapon:
                return
        else:
            weapon = getattr(caller.db, "wielded_obj", None)
            if weapon and weapon.location != caller:
                weapon = None
            if not weapon:
                caller.msg("Wield a ranged weapon first, or specify one: |wcheck ammo <weapon>|n.")
                return

        from world.ammo import is_ranged_weapon
        weapon_key = getattr(weapon.db, "weapon_key", None)
        if not weapon_key or not is_ranged_weapon(weapon_key):
            caller.msg(f"{weapon.name} doesn't use ammunition.")
            return

        capacity = int(getattr(weapon.db, "ammo_capacity", 0) or 0)
        current = int(getattr(weapon.db, "ammo_current", 0) or 0)
        caller.msg(f"You thumb the magazine on |w{weapon.name}|n: |w{current}|n round(s) left." + (f" (capacity {capacity})" if capacity else "") + ".")


class CmdWear(Command):
    """
    Wear a piece of clothing or armor from your inventory.

    Usage:
      wear <clothing>
    """
    key = "wear"
    aliases = ["put on", "don"]
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.clothing.Clothing"]
    usage_hint = "|wwear|n"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Wear what?")
            return
        target = caller.search(self.args, location=caller)
        if not target:
            return
        covered = getattr(target.db, "covered_parts", None)
        if not covered:
            caller.msg(f"{target.get_display_name(caller)} isn't something you can wear.")
            return
        race_fit = getattr(target.db, "race_fit", None)
        character_race = (getattr(caller.db, "race", None) or "human").lower()
        if race_fit == "human_only" and character_race == "splicer":
            caller.msg("This garment doesn't accommodate your tail.")
            return
        if race_fit == "splicer_only" and character_race != "splicer":
            caller.msg("This garment is cut for a Splicer's frame.")
            return
        worn = caller.db.worn or []
        if target in worn:
            caller.msg(f"You're already wearing {target.get_display_name(caller)}.")
            return

        # Armor stacking and layering; clothing vs armor conflicts
        from world.armor import (
            MAX_ARMOR_STACKING_SCORE,
            get_worn_armor_stack_total,
            check_layer_warning,
            _is_armor,
        )
        from world.clothing import get_worn_items, infer_clothing_layer
        from typeclasses.armor import Armor
        from typeclasses.clothing import Clothing

        is_armor = _is_armor(target)
        if is_armor:
            current_stack = get_worn_armor_stack_total(caller)
            add_score = target.get_stacking_score()
            if current_stack >= MAX_ARMOR_STACKING_SCORE:
                caller.msg("You cannot wear any more armor.")
                return
            if current_stack + add_score > MAX_ARMOR_STACKING_SCORE:
                caller.msg(
                    "That would exceed your armor limit. You may be able to wear a smaller piece of armor instead."
                )
                return

        # Existing worn items (clothing + armor)
        worn_items = get_worn_items(caller)

        # Assign clothing_layer for tailored clothing if not already set
        if isinstance(target, Clothing) and not isinstance(target, Armor):
            layer = getattr(target.db, "clothing_layer", None)
            if layer is None:
                target.db.clothing_layer = infer_clothing_layer(target.key or target.get_display_name(caller))

            # Enforce that inner layers (e.g. bra) cannot be worn over outer layers on same parts
            layer = int(getattr(target.db, "clothing_layer", 1) or 1)
            target_parts = set(getattr(target.db, "covered_parts", None) or [])
            for item in worn_items:
                if not isinstance(item, Clothing):
                    continue
                other_parts = set(getattr(item.db, "covered_parts", None) or [])
                if not (target_parts and other_parts and target_parts.intersection(other_parts)):
                    continue
                other_layer = int(getattr(item.db, "clothing_layer", 1) or 1)
                # If trying to wear a lower-layer item over a higher-layer garment, block.
                if layer < other_layer:
                    caller.msg(
                        "That belongs under %s. You can't wear it on top." % item.get_display_name(caller)
                    )
                    return
                # Prevent multiple garments on the same layer for overlapping parts (mutual exclusivity).
                if layer == other_layer:
                    caller.msg(
                        "You're already wearing %s on that part of your body." % item.get_display_name(caller)
                    )
                    return

            # Prevent tailored boots/jackets that conflict directly with armor on same parts.
            for item in worn_items:
                if not isinstance(item, Armor):
                    continue
                armor_parts = set(getattr(item.db, "covered_parts", None) or [])
                if not (target_parts and armor_parts and target_parts.intersection(armor_parts)):
                    continue
                armor_layer = int(getattr(item.db, "armor_layer", 0) or 0)
                # Rough mapping: armor layer 3 ~ jackets; 5 ~ boots/outer extremities.
                if (layer >= 3 and armor_layer >= 3) or (layer == 5 and armor_layer == 5):
                    caller.msg(
                        "You can't layer that over or under your %s. Pick one." % item.get_display_name(caller)
                    )
                    return

        # Armor layering warning (armor vs armor); keep as non-blocking guidance.
        warn, higher = check_layer_warning(caller, target)
        if warn and higher:
            caller.msg("The item must be worn under %s." % higher.get_display_name(caller))

        caller.db.worn = worn + [target]
        item_name = target.get_display_name(caller) if hasattr(target, "get_display_name") else target.name
        caller.msg(f"You put on {item_name}.")
        if caller.location and hasattr(caller.location, "contents_get"):
            for viewer in caller.location.contents_get(content_type="character"):
                if viewer == caller:
                    continue
                vcaller = caller.get_display_name(viewer) if hasattr(caller, "get_display_name") else caller.name
                vitem = target.get_display_name(viewer) if hasattr(target, "get_display_name") else target.name
                viewer.msg(f"{vcaller} puts on {vitem}.")


class CmdRemove(Command):
    """
    Remove a piece of clothing you're wearing.

    Usage:
      remove <clothing>
    """
    key = "remove"
    aliases = ["take off", "doff"]
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.clothing.Clothing"]
    usage_hint = "|wremove|n"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Remove what?")
            return
        target = caller.search(self.args, location=caller)
        if not target:
            return
        worn = caller.db.worn or []
        if target not in worn:
            caller.msg(f"You aren't wearing {target.get_display_name(caller)}.")
            return
        caller.db.worn = [o for o in worn if o != target]
        item_name = target.get_display_name(caller) if hasattr(target, "get_display_name") else target.name
        caller.msg(f"You remove {item_name}.")
        if caller.location and hasattr(caller.location, "contents_get"):
            for viewer in caller.location.contents_get(content_type="character"):
                if viewer == caller:
                    continue
                vcaller = caller.get_display_name(viewer) if hasattr(caller, "get_display_name") else caller.name
                vitem = target.get_display_name(viewer) if hasattr(target, "get_display_name") else target.name
                viewer.msg(f"{vcaller} removes {vitem}.")


class CmdToggleClothing(Command):
    """
    Toggle a two-state garment you're wearing (zip/unzip, hood up/down, etc.).

    Usage:
      toggle <clothing>

    This works for any clothing item configured with two states (state_a and state_b
    on the garment's db). The garment defines what each state does to coverage,
    description, and any emote text.
    """

    key = "toggle"
    aliases = ["adjust"]
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.clothing.Clothing"]
    usage_hint = "|wtoggle|n"

    def func(self):
        caller = self.caller
        if not self.args or not self.args.strip():
            caller.msg("Toggle what?")
            return

        target = caller.search(self.args.strip(), location=caller)
        if not target:
            return

        from typeclasses.clothing import Clothing

        if not isinstance(target, Clothing):
            caller.msg(f"{target.get_display_name(caller)} isn't something you can adjust that way.")
            return

        worn = caller.db.worn or []
        if target not in worn:
            caller.msg(f"You're not wearing {target.get_display_name(caller)}.")
            return

        if not target.has_two_states():
            caller.msg(f"{target.get_display_name(caller)} doesn't have an alternate state to toggle.")
            return

        # Remember which state we were in before toggling; this determines which
        # toggle emote config to use (source state → emote).
        old_key = getattr(target.db, "state", None) or "a"

        new_key, _cfg = target.toggle_state()
        if not new_key:
            caller.msg("Nothing seems to happen.")
            return

        # Optional per-state toggle emote text, pulled from the *source* state config:
        # - When toggling A → B, use state A's toggleemote-*.
        # - When toggling B → A, use state B's toggleemote-*.
        cfg = target.get_state_config(old_key)
        you_emote = cfg.get("toggle_emote_you") if cfg else None

        item_name_you = target.get_display_name(caller) if hasattr(target, "get_display_name") else target.name
        if you_emote:
            from world.rpg.crafting import substitute_clothing_desc

            caller.msg(substitute_clothing_desc(you_emote, caller, item=target))
        else:
            caller.msg(f"You adjust {item_name_you}.")

        if caller.location and hasattr(caller.location, "contents_get"):
            for viewer in caller.location.contents_get(content_type="character"):
                if viewer == caller:
                    continue
                vcaller = caller.get_display_name(viewer) if hasattr(caller, "get_display_name") else caller.name
                vitem = target.get_display_name(viewer) if hasattr(target, "get_display_name") else target.name
                if you_emote:
                    from world.rpg.crafting import substitute_clothing_desc

                    viewer.msg(substitute_clothing_desc(you_emote, caller, item=target))
                else:
                    viewer.msg(f"{vcaller} adjusts {vitem}.")


class CmdStrip(Command):
    """
    Take off a worn item from yourself or from another (living or corpse).
    The item is moved to your inventory.

    Usage:
      strip <item>              - take off something you're wearing
      strip <item> from <target> - take off something worn by another or a corpse
    """
    key = "strip"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not self.args or not self.args.strip():
            caller.msg("Strip what? Usage: strip <item> [from <target>]")
            return
        args = self.args.strip()
        if " from " in args:
            item_spec, _, target_spec = args.partition(" from ")
            item_spec = item_spec.strip()
            target_spec = target_spec.strip()
            if not item_spec or not target_spec:
                caller.msg("Usage: strip <item> from <target>")
                return
            target = caller.search(target_spec, location=caller.location)
            if not target:
                return
            if target != caller:
                try:
                    from world.death import is_character_logged_off, character_logged_off_long_enough
                    if is_character_logged_off(target):
                        if not character_logged_off_long_enough(target):
                            caller.msg("They haven't been asleep long enough.")
                            return
                except ImportError as e:
                    logger.log_trace("inventory_cmds.CmdStrip is_character_logged_off: %s" % e)
        else:
            item_spec = args
            target = caller
        worn = list(target.db.worn or [])
        if not worn:
            if target is caller:
                caller.msg("You aren't wearing anything to strip.")
            else:
                caller.msg(f"{target.get_display_name(caller)} isn't wearing anything you can strip.")
            return
        item = caller.search(item_spec, candidates=worn)
        if not item:
            if target is caller:
                caller.msg(f"You aren't wearing '{item_spec}'.")
            else:
                caller.msg(f"{target.get_display_name(caller)} isn't wearing '{item_spec}'.")
            return
        target.db.worn = [o for o in worn if o != item]
        item.move_to(caller)
        iname = item.get_display_name(caller) if hasattr(item, "get_display_name") else item.name
        tname = target.get_display_name(caller) if hasattr(target, "get_display_name") else target.key
        if target is caller:
            caller.msg(f"You strip {iname} and take it.")
            caller.location.msg_contents(
                f"{caller.get_display_name(caller)} strips {iname}.",
                exclude=caller,
            )
        else:
            caller.msg(f"You strip {iname} from {tname} and take it.")
            caller.location.msg_contents(
                f"{caller.get_display_name(caller)} strips {iname} from {tname}.",
                exclude=caller,
            )


class CmdFrisk(Command):
    """
    Get a one-time readout of what someone is carrying (alive or sleeping).
    You must run the command again to see their inventory again.

    Usage:
      frisk <character>
    """
    key = "frisk"
    aliases = ["patdown"]  # "check" reserved for diagnose (medical check)
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not self.args or not self.args.strip():
            caller.msg("Frisk who? Usage: frisk <character>")
            return
        from typeclasses.corpse import Corpse
        from evennia import DefaultCharacter
        target = caller.search(self.args.strip(), location=caller.location)
        if not target:
            return
        if isinstance(target, Corpse):
            caller.msg("That's a corpse. Use |wloot|n to search the body.")
            return
        if not isinstance(target, DefaultCharacter):
            caller.msg("You can only frisk characters.")
            return
        if target == caller:
            caller.msg("You know what you're carrying.")
            return
        tname = target.get_display_name(caller)
        caller.msg("You run your hands over %s's pockets and belongings." % tname)
        caller.location.msg_contents(
            "%s frisks %s." % (caller.get_display_name(caller), tname),
            exclude=caller,
        )
        _frisk_readout(caller, target)
