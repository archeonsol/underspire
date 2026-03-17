"""
Multi-puppet commands: add puppet to set, list puppets, run command as p1/p2/.../p9.

Commands in this module inherit from evennia's BaseCommand (not commands.base_cmds.Command)
on purpose: they run at Account level (e.g. addpuppet, p1, p2). Character flatline/dead
checks are not applied here; character-level commands use base_cmds.Command and at_pre_cmd.
"""

from evennia.commands.command import Command as BaseCommand
from evennia.utils import logger
from commands.media_cmds import _get_object_by_id


def _clear_multi_puppet_links_for_account(account):
    """Remove _multi_puppet_account_id and _multi_puppet_slot from all characters in account's multi_puppets."""
    ids = list(getattr(account.db, "multi_puppets", None) or [])
    for oid in ids:
        obj = _get_object_by_id(oid)
        if obj and hasattr(obj, "db"):
            if hasattr(obj.db, "_multi_puppet_account_id"):
                try:
                    del obj.db["_multi_puppet_account_id"]
                except Exception as e:
                    logger.log_trace("multipuppet_cmds._clear_multi_puppet_links_for_account _multi_puppet_account_id: %s" % e)
            if hasattr(obj.db, "_multi_puppet_slot"):
                try:
                    del obj.db["_multi_puppet_slot"]
                except Exception as e:
                    logger.log_trace("multipuppet_cmds._clear_multi_puppet_links_for_account _multi_puppet_slot: %s" % e)


def _set_multi_puppet_link(char, account_id, slot_1based):
    """Mark a character as being in an account's multi-puppet set at the given slot (1-based)."""
    if char and hasattr(char, "db"):
        char.db._multi_puppet_account_id = account_id
        char.db._multi_puppet_slot = slot_1based


def _multi_puppet_account(caller):
    """Return the Account for multi-puppet commands (caller may be Account or Character)."""
    if hasattr(caller, "account") and caller.account:
        return caller.account
    return caller


def _multi_puppet_list(account):
    """Return list of puppet dbrefs; ensure current session.puppet is in the list if we're puppeting."""
    ids = list(getattr(account.db, "multi_puppets", None) or [])
    session = getattr(account, "sessions", None)
    if session and hasattr(session, "get"):
        sess_list = session.get()
        if sess_list:
            sess = sess_list[0]
            puppet = getattr(sess, "puppet", None)
            if puppet and (not ids or ids[-1] != getattr(puppet, "id", None)):
                if not ids:
                    ids = [puppet.id]
                elif puppet.id not in ids:
                    ids = list(ids) + [puppet.id]
                account.db.multi_puppets = ids
    return ids


def _resolve_multi_puppet(account, index):
    """Return (Character or None, 0-based index). index 0 = first in list (p1)."""
    ids = _multi_puppet_list(account)
    if index < 0 or index >= len(ids):
        return None, index
    from evennia.utils.search import search_object
    try:
        ref = "#%s" % int(ids[index])
        result = search_object(ref)
        return (result[0] if result else None), index
    except (TypeError, ValueError):
        return None, index


class CmdAddPuppet(BaseCommand):
    """
    Add another character to your multi-puppet set without unpuppeting the current one.
    Your session will now control the new character (normal commands use them); use p1, p2, ...
    to run commands as the first, second, etc. puppet.
    Usage: @addpuppet <character>
    """
    key = "@addpuppet"
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        account = getattr(self.caller, "account", self.caller)
        if not hasattr(account, "db"):
            self.msg("No account.")
            return
        session = getattr(self, "session", None)
        if not session:
            self.msg("No session.")
            return
        if not self.args or not self.args.strip():
            self.msg("Usage: @addpuppet <character>")
            return
        # Resolve character: search from current puppet's location or globally.
        raw = self.args.strip()
        searcher = getattr(session, "puppet", None) or self.caller
        # Use quiet=True so we don't emit "Could not find" before our relaxed search succeeds.
        char = (
            searcher.search(raw, global_search=True, quiet=True)
            if hasattr(searcher, "search")
            else None
        )

        # If normal search failed, try a relaxed, room-local surname/partial match
        # similar to @puppet/@restore: match any word in the name, or substring.
        if not char and hasattr(searcher, "location"):
            loc = getattr(searcher, "location", None)
            if loc and hasattr(loc, "contents_get"):
                arg_low = raw.lower()
                relaxed = []
                for obj in loc.contents_get(content_type="character"):
                    # Only consider characters we can puppet.
                    if not obj.access(account, "puppet"):
                        continue
                    key_low = (getattr(obj, "key", "") or "").lower()
                    words = key_low.split()
                    if any(w.startswith(arg_low) for w in words) or arg_low in key_low:
                        relaxed.append(obj)
                if len(relaxed) == 1:
                    char = relaxed[0]
                elif len(relaxed) > 1:
                    names = [f"{o.name}(#{getattr(o, 'id', '?')})" for o in relaxed]
                    self.msg("Multiple matches for that name here: %s" % ", ".join(names))
                    return

        if not char:
            # Final fallback: global object search like before.
            from evennia.utils.search import search_object

            matches = search_object(raw)
            if isinstance(matches, list) and len(matches) == 1:
                char = matches[0]
            elif isinstance(matches, list) and len(matches) > 1:
                names = [f"{o.name}(#{getattr(o, 'id', '?')})" for o in matches]
                self.msg("Multiple global matches: %s" % ", ".join(names))
                return

        if not char:
            return
        from evennia.utils import make_iter
        char = make_iter(char)[0] if make_iter(char) else char
        if not hasattr(char, "location"):
            self.msg("That's not a character you can puppet.")
            return
        # Build multi_puppets: current puppet is always p1; newly added go to p2, p3, ... Do NOT call puppet_object.
        ids = list(getattr(account.db, "multi_puppets", None) or [])
        if not ids and getattr(session, "puppet", None):
            ids = [session.puppet.id]
            _set_multi_puppet_link(session.puppet, account.id, 1)
        if char.id in ids:
            self.msg("You already have that character in your puppet set.")
            return
        # Append: p1 = current (first in list), p2 = first added, p3 = second added, etc.
        ids.append(char.id)
        account.db.multi_puppets = ids
        for i, oid in enumerate(ids):
            obj = _get_object_by_id(oid)
            if obj:
                _set_multi_puppet_link(obj, account.id, i + 1)
        self.msg("You add |w%s|n to your puppet set. You remain controlling your current character (p1). Use |wp2|n to act as %s, |wp3|n for the next, etc." % (char.get_display_name(self.caller), char.get_display_name(self.caller)))


class CmdPuppetList(BaseCommand):
    """
    List your current multi-puppet set (p1, p2, ... and which character each slot is).
    Usage: @puppet/list
    """
    key = "@puppet/list"
    aliases = ["@puppetlist", "puppet list"]
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        account = getattr(self.caller, "account", self.caller)
        if not hasattr(account, "db"):
            self.msg("No account.")
            return
        session = getattr(self, "session", None)
        ids = _multi_puppet_list(account)
        if not ids:
            self.msg("You have no puppets in your set. Use |w@puppet|n to puppet a character, then |w@addpuppet <name>|n to add more.")
            return
        lines = []
        current = getattr(session, "puppet", None) if session else None
        for i, oid in enumerate(ids):
            obj = _get_object_by_id(oid)
            name = obj.get_display_name(self.caller) if obj else "#%s (gone)" % oid
            slot = i + 1
            mark = " |w(you)|n" if obj and obj == current else ""
            lines.append("  p%s: %s%s" % (slot, name, mark))
        self.msg("|wYour puppet set:|n\n%s" % "\n".join(lines))


class CmdPuppetSlot(BaseCommand):
    """
    Run a command as one of your multi-puppeted characters.
    Usage: p1 <command>   p2 <command>   ...   p9 <command>
    Example: p1 say Hello world   p2 go north
    """
    key = "p1"
    aliases = ["p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9"]
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        account = _multi_puppet_account(self.caller)
        session = getattr(self, "session", None)
        if not session:
            # Fallback: get session from account
            if hasattr(account, "sessions") and account.sessions.get():
                session = account.sessions.get()[0]
        if not session:
            self.msg("No session.")
            return
        # Parse slot from cmdstring: p1 -> 0, p2 -> 1, ...
        raw = (self.cmdstring or "").strip().lower()
        if raw.startswith("p") and len(raw) >= 2 and raw[1:].isdigit():
            index = int(raw[1:]) - 1
        else:
            index = 0
        char, _ = _resolve_multi_puppet(account, index)
        if not char:
            self.msg("You don't have a puppet in slot %s. Use |w@puppet|n and |w@addpuppet|n to build your set." % (index + 1))
            return
        sub_cmd = (self.args or "").strip()
        if not sub_cmd:
            self.msg("Usage: %s <command>   (e.g. %s say Hello)" % (self.cmdstring, self.cmdstring))
            return
        # Temporarily set session.puppet to this character so the command runs as them (cmdset merge uses session.puppet)
        old_puppet = getattr(session, "puppet", None)
        session.puppet = char
        try:
            d = char.execute_cmd(sub_cmd, session=session)
            if d is not None and hasattr(d, "addBoth"):
                def _restore(_):
                    session.puppet = old_puppet
                d.addBoth(_restore)
            else:
                session.puppet = old_puppet
        except Exception as e:
            session.puppet = old_puppet
            self.msg("|rError running command: %s|n" % e)
