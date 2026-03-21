"""
Range-based combat commands.
"""

from commands.base_cmds import Command
from commands.combat_cmds import _combat_caller
from world.combat import _get_combat_target, _combat_display_name
from world.combat.utils import combat_msg, combat_role_name
from world.combat.range_system import (
    attempt_advance,
    attempt_retreat,
    get_combat_range,
    get_range_display_line,
    RANGE_LABELS,
    RANGE_DESCRIPTIONS,
)
from world.combat.cover import get_cover_status_text


def _emit_room(caller, opponent, msg_room):
    loc = getattr(caller, "location", None)
    if not loc or not msg_room or not hasattr(loc, "contents_get"):
        return
    for viewer in loc.contents_get(content_type="character"):
        if viewer in (caller, opponent):
            continue
        combat_msg(viewer, msg_room(viewer) if callable(msg_room) else msg_room)


class CmdAdvance(Command):
    key = "advance"
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = _combat_caller(self)
        if not getattr(caller, "db", None) or not hasattr(caller.db, "stats"):
            combat_msg(self.caller, "You must be in character to do that.")
            return
        opponent = _get_combat_target(caller)
        if not opponent:
            combat_msg(caller, "You're not in combat.")
            return
        if getattr(caller.db, "combat_positioning_attempted", False):
            combat_msg(
                caller,
                "|yYou've already used a positioning action this round. "
                "Wait until after your next combat turn.|n"
            )
            return
        caller.db.combat_skip_next_turn = True
        caller.db.combat_positioning_attempted = True
        _ok, _new_range, msg_you, msg_opp, msg_room = attempt_advance(caller, opponent)
        combat_msg(caller, msg_you)
        if msg_opp:
            mover_name = combat_role_name(caller, opponent, role="attacker")
            combat_msg(opponent, msg_opp.replace("{mover}", mover_name))
        _emit_room(caller, opponent, msg_room)
        combat_msg(caller, get_range_display_line(caller, opponent))


class CmdRetreat(Command):
    key = "retreat"
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = _combat_caller(self)
        if not getattr(caller, "db", None) or not hasattr(caller.db, "stats"):
            combat_msg(self.caller, "You must be in character to do that.")
            return
        opponent = _get_combat_target(caller)
        if not opponent:
            combat_msg(caller, "You're not in combat.")
            return
        if getattr(caller.db, "combat_positioning_attempted", False):
            combat_msg(
                caller,
                "|yYou've already used a positioning action this round. "
                "Wait until after your next combat turn.|n"
            )
            return
        caller.db.combat_skip_next_turn = True
        caller.db.combat_positioning_attempted = True
        _ok, _new_range, msg_you, msg_opp, msg_room = attempt_retreat(caller, opponent)
        combat_msg(caller, msg_you)
        if msg_opp:
            mover_name = combat_role_name(caller, opponent, role="attacker")
            combat_msg(opponent, msg_opp.replace("{mover}", mover_name))
        _emit_room(caller, opponent, msg_room)
        combat_msg(caller, get_range_display_line(caller, opponent))


class CmdRange(Command):
    key = "range"
    aliases = ["distance", "positioning"]
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = _combat_caller(self)
        if not getattr(caller, "db", None):
            combat_msg(self.caller, "You must be in character to do that.")
            return
        opponent = _get_combat_target(caller)
        if not opponent:
            combat_msg(caller, "You're not in combat. Range only applies during a fight.")
            return
        current = get_combat_range(caller, opponent)
        label = RANGE_LABELS.get(current, "unknown")
        desc = RANGE_DESCRIPTIONS.get(current, "")
        combat_msg(caller, f"|wCurrent range|n: {label} — {desc}")
        combat_msg(
            caller,
            f"|wCover|n: You are {get_cover_status_text(caller)}. "
            f"{_combat_display_name(opponent, caller)} is {get_cover_status_text(opponent)}."
        )
        combat_msg(caller, get_range_display_line(caller, opponent))
