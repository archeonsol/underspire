"""
Matrix Commands

Commands for interacting with the Matrix system.

CmdJackIn - Jack into the Matrix through a dive rig
CmdJackOut - Disconnect from the Matrix
"""

from evennia import Command
from typeclasses.matrix.devices import DiveRig
from typeclasses.matrix.avatars import JACKOUT_NORMAL


class CmdJackIn(Command):
    """
    Jack into the Matrix through a dive rig.

    Usage:
        jack in

    You must be sitting in a dive rig to use this command.
    Your consciousness will transfer to your Matrix avatar while your
    body remains vulnerable in meatspace.
    """

    key = "jack in"
    aliases = ["jackin"]
    locks = "cmd:all()"
    help_category = "Matrix"

    def func(self):
        caller = self.caller

        # Check if sitting on anything
        sitting_on = caller.db.sitting_on
        if not sitting_on:
            caller.msg("You must be sitting in a dive rig first.")
            return

        # Check if it's a dive rig
        if not isinstance(sitting_on, DiveRig):
            caller.msg("You can only jack in from a dive rig.")
            return

        # Attempt to jack in
        success = sitting_on.jack_in(caller)
        if not success:
            # Error messages are handled by jack_in()
            return


class CmdJackOut(Command):
    """
    Disconnect from the Matrix and return to your body.

    Usage:
        jack out

    Cleanly disconnects you from the Matrix. Your avatar will be marked
    as idle and cleaned up after a grace period.

    Note: Cannot jack out during combat or other restricted situations.
    """

    key = "jack out"
    aliases = ["jackout"]
    locks = "cmd:all()"
    help_category = "Matrix"

    def func(self):
        caller = self.caller

        # Check if caller is a Matrix avatar
        from typeclasses.matrix.avatars import MatrixAvatar
        if not isinstance(caller, MatrixAvatar):
            caller.msg("You are not jacked into the Matrix.")
            return

        # Check if we have a real character to return to
        real_character = caller.db.real_character
        if not real_character:
            caller.msg("Error: Cannot locate your physical body.")
            return

        # Check if we have an entry device
        entry_device = caller.db.entry_device
        if not entry_device:
            caller.msg("Error: Cannot locate your dive rig connection.")
            return

        # TODO: Check for combat or other restrictions
        # if caller.db.in_combat:
        #     caller.msg("You cannot jack out during combat!")
        #     return

        # Perform clean logout
        entry_device.jack_out_character(
            real_character,
            severity=JACKOUT_NORMAL,
            reason="Logging out"
        )
