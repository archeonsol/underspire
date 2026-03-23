"""
Cover combat commands: cover, leave cover, peek, suppress.
"""

from __future__ import annotations

from commands.base_cmds import Command
from commands.combat_cmds import _combat_caller
from world.combat import _get_combat_target, _combat_display_name
from world.combat.utils import combat_msg, combat_role_name
from world.combat.cover import (
    try_take_cover,
    clear_cover_state,
    get_cover_status_text,
    set_suppressed,
)
from world.skills import WEAPON_KEY_TO_SKILL


def _emit_room(caller, opponent, text):
    loc = getattr(caller, "location", None)
    if not loc or not hasattr(loc, "contents_get"):
        return
    for viewer in loc.contents_get(content_type="character"):
        if viewer == caller or (opponent and viewer == opponent):
            continue
        if callable(text):
            combat_msg(viewer, text(viewer))
        else:
            combat_msg(viewer, text)


class CmdCover(Command):
    key = "cover"
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = _combat_caller(self)
        if not getattr(caller, "db", None) or not hasattr(caller.db, "stats"):
            combat_msg(self.caller, "You must be in character to do that.")
            return
        opponent = _get_combat_target(caller)
        if opponent and getattr(caller.db, "combat_positioning_attempted", False):
            combat_msg(
                caller,
                "|yYou've already used a positioning action this round. "
                "Wait until after your next combat turn.|n"
            )
            return
        if getattr(caller.db, "grappled_by", None) or getattr(caller.db, "grappling", None):
            combat_msg(caller, "You're locked in a grapple.")
            return
        if opponent:
            caller.db.combat_skip_next_turn = True
            caller.db.combat_positioning_attempted = True
        success, info, _quality = try_take_cover(caller, difficulty=10)
        if not success:
            combat_msg(caller, f"|r{info}|n")
            return
        flavor = info
        combat_msg(caller, f"|gYou dive behind {flavor}.|n")
        if opponent:
            caller_name = combat_role_name(caller, opponent, role="attacker")
            combat_msg(opponent, f"|y{caller_name} ducks behind {flavor}.|n")
        _emit_room(caller, opponent, lambda v: f"{_combat_display_name(caller, v)} takes cover behind {flavor}.")


class CmdLeaveCover(Command):
    key = "leave cover"
    aliases = ["expose"]
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = _combat_caller(self)
        if not getattr(caller, "db", None):
            combat_msg(self.caller, "You must be in character to do that.")
            return
        if not getattr(caller.db, "in_cover", False):
            combat_msg(caller, "You're already exposed.")
            return
        opponent = _get_combat_target(caller)
        if opponent:
            caller.db.combat_skip_next_turn = True
        clear_cover_state(caller, reset_pose=True)
        combat_msg(caller, "|yYou leave cover and expose yourself.|n")
        _emit_room(caller, opponent, lambda v: f"{_combat_display_name(caller, v)} leaves cover.")


class CmdPeek(Command):
    key = "peek"
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = _combat_caller(self)
        if not getattr(caller.db, "in_cover", False):
            combat_msg(caller, "You're not in cover.")
            return
        loc = getattr(caller, "location", None)
        if not loc or not hasattr(loc, "contents_get"):
            combat_msg(caller, "No one is visible.")
            return
        combat_msg(caller, "|wVisible targets:|n")
        for target in loc.contents_get(content_type="character"):
            if target == caller:
                continue
            combat_msg(caller, f" - {_combat_display_name(target, caller)}: {get_cover_status_text(target)}")


class CmdSuppress(Command):
    key = "suppress"
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = _combat_caller(self)
        if not getattr(caller, "db", None) or not hasattr(caller.db, "stats"):
            combat_msg(self.caller, "You must be in character to do that.")
            return
        target = caller.search((self.args or "").strip(), location=caller.location)
        if not target:
            return
        wielded_obj = getattr(caller.db, "wielded_obj", None)
        weapon_key = getattr(caller.db, "wielded", "fists") if wielded_obj and getattr(wielded_obj, "location", None) == caller else "fists"
        if weapon_key != "automatic":
            combat_msg(caller, "You need an automatic weapon to lay down suppressing fire.")
            return
        if wielded_obj and hasattr(wielded_obj, "db"):
            ammo = int(wielded_obj.db.ammo_current or 0)
            if ammo < 2:
                combat_msg(caller, "Not enough ammo to suppress.")
                return
            wielded_obj.db.ammo_current = ammo - 2
        caller.db.combat_skip_next_turn = True
        atk_skill = WEAPON_KEY_TO_SKILL.get(weapon_key, "automatics")
        _a, atk_val = caller.roll_check(["agility", "perception"], atk_skill, modifier=0)
        # No explicit willpower stat in this codebase; endurance is used as resistance proxy.
        _t, tgt_val = target.roll_check(["endurance"], "evasion", modifier=0)
        success = int(atk_val or 0) > int(tgt_val or 0)
        combat_msg(caller, f"|rYou lay down fire on {_combat_display_name(target, caller)}'s position.|n")
        if success:
            set_suppressed(target)
            if getattr(target.db, "in_cover", False):
                combat_msg(target, "|rRounds tear into your cover. You flinch.|n")
            else:
                combat_msg(target, "|rRounds crack past you. You hit the ground. You're pinned.|n")
        else:
            combat_msg(target, "|yFire hits near you but you hold position.|n")
        _emit_room(
            caller,
            target,
            lambda v: f"{_combat_display_name(caller, v)} opens up on {_combat_display_name(target, v)}'s position, suppressing fire.",
        )
