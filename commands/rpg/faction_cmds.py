"""
Staff faction administration (bypasses terminal permission checks).
"""

from commands.base_cmds import Command
from evennia.utils.search import search_object


class CmdFaction(Command):
    """
    Staff faction management.

    Usage:
        @faction list
        @faction info <faction_key>
        @faction enlist <character> = <faction_key>
        @faction discharge <character> = <faction_key>
        @faction promote <character> = <faction_key>
        @faction demote <character> = <faction_key>
        @faction setrank <character> = <faction_key> <rank#>
        @faction roster <faction_key>
        @faction log <character>
    """

    key = "@faction"
    aliases = ["faction"]
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        from world.rpg.factions import get_faction, get_all_faction_keys
        from world.rpg.factions.membership import (
            enlist,
            discharge,
            promote,
            demote,
            set_rank,
            get_faction_roster,
        )
        from world.rpg.factions.ranks import get_rank_name

        raw = (self.args or "").strip()
        if not raw:
            self.caller.msg("Usage: @faction list | info <key> | enlist <char> = <key> | ...")
            return

        parts = raw.split(None, 1)
        sub = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "list":
            keys = get_all_faction_keys()
            self.caller.msg("Factions: " + ", ".join(keys))
            return

        if sub == "info":
            key = rest.strip().upper()
            fd = get_faction(key)
            if not fd:
                self.caller.msg("Unknown faction.")
                return
            self.caller.msg(
                f"{fd['name']} ({fd['key']}) — tag {fd['tag']}, ranks: {fd['ranks']}, "
                f"terminal prototype: {fd.get('terminal_prototype', '')}"
            )
            return

        if sub == "roster":
            key = rest.strip().upper()
            fd = get_faction(key)
            if not fd:
                self.caller.msg("Unknown faction.")
                return
            roster = get_faction_roster(key)
            lines = [f"{c.key} — rank {r} ({get_rank_name(fd['ranks'], r)})" for c, r in roster[:80]]
            self.caller.msg("\n".join(lines) if lines else "No members.")
            return

        if sub == "log":
            target = self._resolve_char(rest.strip())
            if not target:
                return
            log = target.db.faction_log or []
            if not log:
                self.caller.msg("No faction log entries.")
                return
            for entry in log[-25:]:
                self.caller.msg(
                    f"{entry.get('faction')} / {entry.get('event')}: {entry.get('details', '')}"
                )
            return

        if sub in ("enlist", "discharge", "promote", "demote", "setrank"):
            self._mutate(sub, rest)
            return

        self.caller.msg("Unknown subcommand. Try @faction list.")

    def _resolve_char(self, name):
        if not name:
            self.caller.msg("Specify a character name or #dbref.")
            return None
        name = name.strip()
        if name.startswith("#"):
            o = search_object(name)
            if not o:
                self.caller.msg("No object found.")
                return None
            return o[0]
        r = self.caller.search(name, global_search=True)
        return r

    def _parse_eq(self, rest):
        """Parse 'charname = FACTION' or 'charname = FACTION 3' for setrank."""
        if "=" not in rest:
            return None, None, None
        left, right = rest.split("=", 1)
        left = left.strip()
        right = right.strip()
        toks = right.split()
        if not toks:
            return left, None, None
        fac = toks[0].upper()
        rank = None
        if len(toks) > 1:
            try:
                rank = int(toks[1])
            except ValueError:
                pass
        return left, fac, rank

    def _mutate(self, sub, rest):
        from world.rpg.factions import get_faction
        from world.rpg.factions.membership import enlist, discharge, promote, demote, set_rank

        char_name, fac_key, rank_num = self._parse_eq(rest)
        if not char_name or not fac_key:
            self.caller.msg("Usage: @faction <cmd> <character> = <faction_key> [rank]")
            return
        target = self._resolve_char(char_name)
        if not target:
            self.caller.msg("Character not found.")
            return
        fd = get_faction(fac_key)
        if not fd:
            self.caller.msg("Unknown faction.")
            return

        if sub == "enlist":
            ok, msg = enlist(target, fd["key"], enlisted_by=self.caller.key)
        elif sub == "discharge":
            ok, msg = discharge(target, fd["key"], discharged_by=self.caller.key)
        elif sub == "promote":
            ok, msg = promote(target, fd["key"], promoted_by=self.caller.key)
        elif sub == "demote":
            ok, msg = demote(target, fd["key"], demoted_by=self.caller.key)
        elif sub == "setrank":
            if rank_num is None:
                self.caller.msg("Usage: @faction setrank <char> = <faction_key> <rank#>")
                return
            ok, msg = set_rank(target, fd["key"], rank_num, set_by=self.caller.key)
        else:
            return

        self.caller.msg(msg if ok else f"|r{msg}|n")
