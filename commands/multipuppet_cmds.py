"""
Multi-puppet commands: add puppet to set, list puppets, run command as p1/p2/.../p9.

Commands in this module inherit from evennia's BaseCommand (not commands.base_cmds.Command)
on purpose: they run at Account level (e.g. addpuppet, p1, p2). Character flatline/dead
checks are not applied here; character-level commands use base_cmds.Command and at_pre_cmd.
"""

from evennia.commands.command import Command as BaseCommand
from evennia.commands.default.account import CmdIC, CmdOOC
from evennia.utils import logger, search, utils
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


class StaffOnlyPuppet(CmdIC):
    """
    Puppet a character. Staff only (one character per account for players).

    This overrides Evennia's default `CmdIC` search behaviour to be a bit
    more forgiving for NPCs with multi-word names: when run by a Builder+,
    if the normal search does not find a match, we also accept partial
    matches on any word of a character's key in the current room
    (including surnames).
    """

    key = "@puppet"
    aliases = []
    locks = "cmd:perm(Builder)"

    def func(self):
        """
        Staff-only puppet command with relaxed surname/partial matching and
        integration with the multi-puppet system.
        """
        account = self.account
        session = self.session

        # Remember previous multi-puppet list so we can clear their links.
        old_ids = list(getattr(account.db, "multi_puppets", None) or [])

        new_character = None
        character_candidates = []

        args = (self.args or "").strip()

        if not args:
            # No argument: fall back to last puppet, like default CmdIC.
            character_candidates = [account.db._last_puppet] if account.db._last_puppet else []
            if not character_candidates:
                self.msg("Usage: @puppet <character>")
                return
        else:
            # --- First: use the same logic as Evennia's CmdIC.func ---
            playables = account.characters
            if playables:
                character_candidates.extend(
                    utils.make_iter(
                        account.search(
                            args,
                            candidates=playables,
                            search_object=True,
                            quiet=True,
                        )
                    )
                )

            if account.locks.check_lockstring(account, "perm(Builder)"):
                # Builder+ can puppet beyond their own characters.
                local_matches = []
                if session.puppet:
                    # Local search from current puppet, as in CmdIC.
                    local_matches = [
                        char
                        for char in session.puppet.search(args, quiet=True)
                        if char.access(account, "puppet")
                    ]
                    character_candidates = list(local_matches) or character_candidates

                    # --- Extra: surname/word-part matching in current room ---
                    if not local_matches:
                        loc = getattr(session.puppet, "location", None)
                        if loc and hasattr(loc, "contents_get"):
                            arg_low = args.lower()
                            relaxed = []
                            for obj in loc.contents_get(content_type="character"):
                                if not obj.access(account, "puppet"):
                                    continue
                                key_low = (obj.key or "").lower()
                                words = key_low.split()
                                if any(w.startswith(arg_low) for w in words) or arg_low in key_low:
                                    relaxed.append(obj)
                            if relaxed:
                                character_candidates = list(relaxed)

                # If we still have no candidates at all, fall back to the
                # global object search from CmdIC (keeps default behaviour).
                if not character_candidates:
                    character_candidates.extend(
                        [
                            char
                            for char in search.object_search(args)
                            if char.access(account, "puppet")
                        ]
                    )

        # --- Handle candidates (same semantics as CmdIC) ---
        if not character_candidates:
            self.msg("That is not a valid character choice.")
            return
        if len(character_candidates) > 1:
            self.msg(
                "Multiple targets with the same name:\n %s"
                % ", ".join("%s(#%s)" % (obj.key, obj.id) for obj in character_candidates)
            )
            return

        new_character = character_candidates[0]

        # --- Perform the actual puppeting (same as CmdIC) ---
        try:
            account.puppet_object(session, new_character)
            account.db._last_puppet = new_character
            logger.log_sec(
                f"Puppet Success: (Caller: {account}, Target: {new_character}, IP:"
                f" {self.session.address})."
            )
        except RuntimeError as exc:
            self.msg(f"|rYou cannot become |C{new_character.name}|n: {exc}")
            logger.log_sec(
                f"Puppet Failed: {account} -> {new_character} ({self.session.address}): {exc}"
            )
            return

        # --- Reset multi-puppet links so @puppet is always 'p1' ---
        for oid in old_ids:
            obj = _get_object_by_id(oid)
            if obj and hasattr(obj, "db"):
                for key in ("_multi_puppet_account_id", "_multi_puppet_slot"):
                    if hasattr(obj.db, key):
                        try:
                            del obj.db[key]
                        except Exception:
                            pass

        if getattr(self.session, "puppet", None):
            account.db.multi_puppets = [self.session.puppet.id]
            _set_multi_puppet_link(self.session.puppet, account.id, 1)


class StaffOnlyUnpuppet(CmdOOC):
    """
    Unpuppet / leave character. Staff only.

    Usage:
      @unpuppet              - fully unpuppet (legacy behaviour)
      @unpuppet all          - keep p1 puppeted, drop p2, p3, ... from multi-puppet set
      @unpuppet p2 p3 ...    - drop specific multi-puppet slots while keeping p1
    """

    key = "@unpuppet"
    aliases = []
    locks = "cmd:perm(Builder)"

    def func(self):
        """
        Staff unpuppet:
          - No args: unpuppet completely (current behaviour).
          - Args like 'p2 p3 p4': drop those multi-puppet slots only, keeping p1 puppeted.
        """
        args = (self.args or "").strip()

        # No arguments: full unpuppet + clear all multi-puppets (legacy behaviour).
        if not args:
            _clear_multi_puppet_links_for_account(self.account)
            super().func()
            if hasattr(self.account, "db"):
                self.account.db.multi_puppets = []
            return

        # Special case: "@unpuppet all" -> keep p1, drop all extra puppets (p2+).
        if args.lower() == "all":
            ids = _multi_puppet_list(self.account)
            if not ids:
                self.caller.msg("You have no puppets in your set.")
                return
            if len(ids) == 1:
                self.caller.msg("Only p1 is in your puppet set; nothing to unpuppet.")
                return
            keep_id = ids[0]
            removed_ids = ids[1:]
            removed_names = []
            for oid in removed_ids:
                obj = _get_object_by_id(oid)
                if obj and hasattr(obj, "db"):
                    removed_names.append(obj.get_display_name(self.caller))
                    for key in ("_multi_puppet_account_id", "_multi_puppet_slot"):
                        if hasattr(obj.db, key):
                            try:
                                delattr(obj.db, key) if False else obj.db.__delitem__(key)
                            except Exception:
                                pass
            if hasattr(self.account, "db"):
                self.account.db.multi_puppets = [keep_id]
            # Ensure p1 still has correct link.
            first = _get_object_by_id(keep_id)
            if first:
                _set_multi_puppet_link(first, self.account.id, 1)
            if removed_names:
                self.caller.msg("Unpuppeted: %s (p2+). You remain puppeting p1." % ", ".join(removed_names))
            else:
                self.caller.msg("Multi-puppet set trimmed; you remain puppeting p1.")
            return

        # With arguments: interpret as one or more p-slots (p2, p3, ...). Only drop those slots.
        tokens = args.split()
        indices_to_remove = set()
        wants_full_unpuppet = False
        for tok in tokens:
            tok = tok.lower()
            if tok.startswith("p") and tok[1:].isdigit():
                idx = int(tok[1:]) - 1  # p1 -> 0, p2 -> 1, ...
                if idx == 0:
                    # Asking to unpuppet p1 too – treat as full unpuppet.
                    wants_full_unpuppet = True
                elif idx > 0:
                    indices_to_remove.add(idx)

        if wants_full_unpuppet or not indices_to_remove:
            # Fall back to full unpuppet if p1 requested or nothing valid parsed.
            _clear_multi_puppet_links_for_account(self.account)
            super().func()
            if hasattr(self.account, "db"):
                self.account.db.multi_puppets = []
            return

        # Remove selected multi-puppet slots while keeping main puppet (p1) active.
        ids = _multi_puppet_list(self.account)
        if not ids:
            self.caller.msg("You have no puppets in your set.")
            return

        removed_names = []
        # Work from highest index down so list pops don't shift earlier indices.
        for idx in sorted(indices_to_remove, reverse=True):
            if 0 <= idx < len(ids):
                oid = ids[idx]
                obj = _get_object_by_id(oid)
                if obj and hasattr(obj, "db"):
                    removed_names.append(obj.get_display_name(self.caller))
                    for key in ("_multi_puppet_account_id", "_multi_puppet_slot"):
                        if hasattr(obj.db, key):
                            try:
                                del obj.db[key]
                            except Exception:
                                pass
                ids.pop(idx)

        # Re-number remaining slots and persist.
        if hasattr(self.account, "db"):
            self.account.db.multi_puppets = ids
        for slot, oid in enumerate(ids, start=1):
            obj = _get_object_by_id(oid)
            if obj:
                _set_multi_puppet_link(obj, self.account.id, slot)
        if removed_names:
            self.caller.msg("Unpuppeted: %s" % ", ".join(removed_names))


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
