"""
Corpse cyberware salvage command.
"""

from commands.base_cmds import Command, _command_character
from world.medical.salvage import has_scalpel, start_assessment_sequence


class CmdSalvage(Command):
    """
    Salvage installed chrome from a corpse.

    Usage:
      salvage <corpse>
    """

    key = "salvage"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller:
            self.caller.msg("You must be in character to do that.")
            return
        args = (self.args or "").strip()
        if not args:
            caller.msg("Salvage what? Usage: salvage <corpse>")
            return
        target = caller.search(args, location=caller.location)
        if not target:
            return
        try:
            from typeclasses.corpse import Corpse
            if not isinstance(target, Corpse):
                caller.msg("You can only salvage chrome from a corpse.")
                return
        except Exception:
            caller.msg("You can only salvage chrome from a corpse.")
            return

        if getattr(caller.db, "combat_target", None):
            caller.msg("You cannot do this while someone is trying to kill you.")
            return
        if getattr(caller.db, "salvage_in_progress", False) or getattr(caller.db, "salvage_assessing", False):
            caller.msg("You are already working a body.")
            return
        if not has_scalpel(caller):
            caller.msg("You need a scalpel for this work. A knife will destroy the interfaces.")
            return
        cyberware = list(getattr(target.db, "cyberware", None) or [])
        if not cyberware:
            caller.msg("There is no chrome on this body. Nothing worth taking.")
            return

        def _open_menu(op, corpse):
            from world.medical.salvage_menu import start_salvage_menu
            start_salvage_menu(op, corpse)

        ok, err = start_assessment_sequence(caller, target, on_complete=_open_menu)
        if not ok and err:
            caller.msg(err)
