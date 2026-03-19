"""
Character sheet-style commands available to all players.
"""

from commands.base_cmds import Command
from evennia.utils import logger
from evennia.utils.utils import inherits_from
from world.ui_utils import fade_rule


class CmdStats(Command):
    """
    Display your character sheet: stats, skills, XP, and shard fragment time.

    Usage:
      @stats
      @sheet
    """

    key = "@stats"
    aliases = ["@sheet", "@score"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.rpg.chargen import STAT_KEYS
        from world.skills import SKILL_KEYS, SKILL_DISPLAY_NAMES
        from world.levels import get_stat_grade, get_skill_grade
        from world.rpg.xp import _stat_level, _skill_level

        caller = self.caller
        data_source = caller

        # If caller is Account, use session puppet so @stats works while puppeted.
        if not getattr(caller.db, "stats", None) and getattr(self, "session", None):
            try:
                puppet = getattr(self.session, "puppet", None)
                if puppet:
                    caller = puppet
                    data_source = puppet
            except Exception as e:
                logger.log_trace("sheet_cmds.CmdStats session puppet fallback: %s" % e)

        # Matrix avatars should read stats from their controlling character.
        if inherits_from(caller, "typeclasses.matrix.avatars.MatrixAvatar"):
            controlling_char = (
                caller.get_controlling_character()
                if hasattr(caller, "get_controlling_character")
                else None
            )
            if not controlling_char:
                caller.msg("You are not connected to a physical body. Cannot view stats.")
                return
            data_source = controlling_char

        if not getattr(data_source, "db", None) or not hasattr(data_source.db, "stats"):
            caller.msg("Puppet a character to view your sheet.")
            return

        _db = data_source.db
        skills = _db.skills or {}
        bg = _db.background or "Unknown"
        display_name = data_source.name or "Unknown"
        xp = int(getattr(_db, "xp", 0) or 0)

        snapshot = getattr(_db, "clone_snapshot", None)
        fragmented_str = ""
        if snapshot and snapshot.get("fragmented_at"):
            try:
                from datetime import datetime

                ts = snapshot["fragmented_at"]
                dt = datetime.utcfromtimestamp(ts) if isinstance(ts, (int, float)) else ts
                fragmented_str = dt.strftime("%Y-%m-%d %H:%M") + " UTC"
            except Exception as e:
                logger.log_trace("sheet_cmds.CmdStats fragmented_at format: %s" % e)

        w = 50
        rule = fade_rule(w - 2, "─")
        edge = "|x├" + rule + "|n"

        output = "|x┌" + rule + "|n\n"
        output += "|x│|n |R■|n |wSOUL READOUT|n  |x—|n  " + display_name.ljust(18) + "\n"
        output += "|x│|n   |wOrigin|n " + (bg or "Unknown").ljust(w - 18) + "\n"
        output += edge + "\n"
        output += "|x│|n |wXP|n " + str(xp).ljust(w - 10) + "\n"
        if fragmented_str:
            output += "|x│|n |wLast fragmented|n " + fragmented_str.ljust(w - 21) + "\n"
        output += edge + "\n"
        output += "|x│|n |R CORE|n" + " ".ljust(w - 9) + "\n"

        base_stat_display = {}
        for key in STAT_KEYS:
            try:
                stored = int(_stat_level(data_source, key) or 0)
                base_stat_display[key] = max(0, min(150, stored // 2))
            except Exception:
                base_stat_display[key] = 0

        effective_stat_display = {}
        for key in STAT_KEYS:
            try:
                effective_stat_display[key] = int(
                    data_source.get_display_stat(key)
                    if hasattr(data_source, "get_display_stat")
                    else base_stat_display.get(key, 0)
                )
            except Exception:
                effective_stat_display[key] = base_stat_display.get(key, 0)

        for key in STAT_KEYS:
            stored = data_source.get_stat_level(key) if hasattr(data_source, "get_stat_level") else 0
            letter = get_stat_grade(stored)
            adj = (
                data_source.get_stat_grade_adjective(letter, key)
                if hasattr(data_source, "get_stat_grade_adjective")
                else letter
            )
            label = key.capitalize()
            delta = effective_stat_display.get(key, 0) - base_stat_display.get(key, 0)
            marker = " |g+|n" if delta > 0 else (" |r-|n" if delta < 0 else "")
            output += "|x│|n   |w{}|n  |R[{}]|n {}{}\n".format(label.ljust(12), letter, adj, marker)

        output += edge + "\n"
        output += "|x│|n |R IMPLANTS|n" + " ".ljust(w - 14) + "\n"

        base_skill_levels = {}
        for key in SKILL_KEYS:
            try:
                base_skill_levels[key] = int(_skill_level(data_source, key))
            except Exception:
                base_skill_levels[key] = int((skills.get(key, 0) or 0))

        effective_skill_levels = {}
        for key in SKILL_KEYS:
            try:
                effective_skill_levels[key] = int(
                    data_source.get_skill_level(key)
                    if hasattr(data_source, "get_skill_level")
                    else (skills.get(key, 0) or 0)
                )
            except Exception:
                effective_skill_levels[key] = base_skill_levels.get(key, int((skills.get(key, 0) or 0)))

        skill_label_width = 24
        for key in SKILL_KEYS:
            level = effective_skill_levels.get(key, 0)
            if not level:
                continue
            letter = get_skill_grade(level)
            adj = (
                data_source.get_skill_grade_adjective(letter)
                if hasattr(data_source, "get_skill_grade_adjective")
                else letter
            )
            label = SKILL_DISPLAY_NAMES.get(key, key.replace("_", " ").title())
            delta = level - base_skill_levels.get(key, 0)
            marker = " |g+|n" if delta > 0 else (" |r-|n" if delta < 0 else "")
            output += "|x│|n   |w{}|n  |R[{}]|n {}{}\n".format(label.ljust(skill_label_width), letter, adj, marker)

        output += "|x└" + rule + "|n\n"
        caller.msg(output)
