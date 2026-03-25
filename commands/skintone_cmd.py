"""@skintone — choose skin tone once (xterm256 palette)."""

from evennia.commands.command import Command

from world.skin_tones import (
    SKIN_TONES,
    format_skintone_display,
    resolve_skin_tone_key,
    set_character_skin_tone,
)


class CmdSkintone(Command):
    """
    Set or view your skin tone (biological; colors IC name and body descriptions).

    Usage:
      @skintone           - show palette (grouped) and current tone
      @skintone <name>   - set tone once (e.g. @skintone warm brown)
    """

    key = "@skintone"
    aliases = ["skintone"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not hasattr(caller, "db"):
            return
        args = (self.args or "").strip()
        if not args:
            caller.msg(format_skintone_display(caller))
            return
        if getattr(caller.db, "skin_tone_set", False):
            caller.msg(
                "Your skin tone is already set. It can only be changed through in-character means."
            )
            return
        key = resolve_skin_tone_key(args)
        if not key:
            caller.msg("That tone is not available. Use @skintone to see the options.")
            return
        err = set_character_skin_tone(caller, key)
        if err:
            caller.msg(err)
            return
        meta = SKIN_TONES[key]  # key is guaranteed valid after resolve_skin_tone_key
        preview = meta.get("preview", key)
        caller.msg(
            f"You chose {preview} as your skin tone. This will be reflected in how others see you."
        )
