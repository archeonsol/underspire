"""
Account

The Account represents the game "account" and each login has only one
Account object. An Account is what chats on default channels but has no
other in-game-world existence. Rather the Account puppets Objects (such
as Characters) in order to actually participate in the game world.


Guest

Guest accounts are simple low-level accounts that are created/deleted
on the fly and allows users to test the game without the commitment
of a full registration. Guest accounts are deactivated by default; to
activate them, add the following line to your settings file:

    GUEST_ENABLED = True

You will also need to modify the connection screen to reflect the
possibility to connect with a guest account. The setting file accepts
several more options for customizing the Guest account system.

"""

from evennia.accounts.accounts import DefaultAccount, DefaultGuest


def _auto_subscribe_help_channel(account):
    """Subscribe account to Assist (xassist) only. Mandatory so staff can reach them; players only see their own messages and staff's private replies."""
    try:
        from evennia import search_channel
        channels = search_channel("xassist")
        if not channels:
            return
        channel = channels[0] if isinstance(channels, list) else channels
        if not channel.access(account, "listen") or channel.has_connection(account):
            return
        channel.connect(account)
    except Exception:
        pass


class Account(DefaultAccount):
    """
    An Account is the actual OOC player entity. It doesn't exist in the game,
    but puppets characters.

    This is the base Typeclass for all Accounts. Accounts represent
    the person playing the game and tracks account info, password
    etc. They are OOC entities without presence in-game. An Account
    can connect to a Character Object in order to "enter" the
    game.

    Account Typeclass API:

    * Available properties (only available on initiated typeclass objects)

     - key (string) - name of account
     - name (string)- wrapper for user.username
     - aliases (list of strings) - aliases to the object. Will be saved to
            database as AliasDB entries but returned as strings.
     - dbref (int, read-only) - unique #id-number. Also "id" can be used.
     - date_created (string) - time stamp of object creation
     - permissions (list of strings) - list of permission strings
     - user (User, read-only) - django User authorization object
     - obj (Object) - game object controlled by account. 'character' can also
                     be used.
     - is_superuser (bool, read-only) - if the connected user is a superuser

    * Handlers

     - locks - lock-handler: use locks.add() to add new lock strings
     - db - attribute-handler: store/retrieve database attributes on this
                              self.db.myattr=val, val=self.db.myattr
     - ndb - non-persistent attribute handler: same as db but does not
                                  create a database entry when storing data
     - scripts - script-handler. Add new scripts to object with scripts.add()
     - cmdset - cmdset-handler. Use cmdset.add() to add new cmdsets to object
     - nicks - nick-handler. New nicks with nicks.add().
     - sessions - session-handler. Use session.get() to see all sessions connected, if any
     - options - option-handler. Defaults are taken from settings.OPTIONS_ACCOUNT_DEFAULT
     - characters - handler for listing the account's playable characters

    * Helper methods (check autodocs for full updated listing)

     - msg(text=None, from_obj=None, session=None, options=None, **kwargs)
     - execute_cmd(raw_string)
     - search(searchdata, return_puppet=False, search_object=False, typeclass=None,
                      nofound_string=None, multimatch_string=None, use_nicks=True,
                      quiet=False, **kwargs)
     - is_typeclass(typeclass, exact=False)
     - swap_typeclass(new_typeclass, clean_attributes=False, no_default=True)
     - access(accessing_obj, access_type='read', default=False, no_superuser_bypass=False, **kwargs)
     - check_permstring(permstring)
     - get_cmdsets(caller, current, **kwargs)
     - get_cmdset_providers()
     - uses_screenreader(session=None)
     - get_display_name(looker, **kwargs)
     - get_extra_display_name_info(looker, **kwargs)
     - disconnect_session_from_account()
     - puppet_object(session, obj)
     - unpuppet_object(session)
     - unpuppet_all()
     - get_puppet(session)
     - get_all_puppets()
     - is_banned(**kwargs)
     - get_username_validators(validator_config=settings.AUTH_USERNAME_VALIDATORS)
     - authenticate(username, password, ip="", **kwargs)
     - normalize_username(username)
     - validate_username(username)
     - validate_password(password, account=None)
     - set_password(password, **kwargs)
     - get_character_slots()
     - get_available_character_slots()
     - create_character(*args, **kwargs)
     - create(*args, **kwargs)
     - delete(*args, **kwargs)
     - channel_msg(message, channel, senders=None, **kwargs)
     - idle_time()
     - connection_time()

    * Hook methods

     basetype_setup()
     at_account_creation()

     > note that the following hooks are also found on Objects and are
       usually handled on the character level:

     - at_init()
     - at_first_save()
     - at_access()
     - at_cmdset_get(**kwargs)
     - at_password_change(**kwargs)
     - at_first_login()
     - at_pre_login()
     - at_post_login(session=None)
     - at_failed_login(session, **kwargs)
     - at_disconnect(reason=None, **kwargs)
     - at_post_disconnect(**kwargs)
     - at_message_receive()
     - at_message_send()
     - at_server_reload()
     - at_server_shutdown()
     - at_look(target=None, session=None, **kwargs)
     - at_post_create_character(character, **kwargs)
     - at_post_add_character(char)
     - at_post_remove_character(char)
     - at_pre_channel_msg(message, channel, senders=None, **kwargs)
     - at_post_chnnel_msg(message, channel, senders=None, **kwargs)

    """

    @property
    def has_spirit_puppet(self):
        """True if any session is puppeting a Spirit (death lobby). Used so go light / go shard appear on Account cmdset."""
        try:
            for sess in (self.sessions.get() or []):
                p = getattr(sess, "puppet", None)
                if p and type(p).__name__ == "Spirit":
                    return True
        except Exception:
            pass
        return False

    @property
    def account_has_clone(self):
        """True if corpse has a shard or account has clone_snapshot_backup. Used by CmdGoShard lock when on Account cmdset."""
        corpse = getattr(self.db, "dead_character_corpse", None)
        if corpse and getattr(corpse, "db", None) and getattr(corpse.db, "clone_snapshot", None):
            return True
        return bool(getattr(self.db, "clone_snapshot_backup", None))

    def at_post_login(self, session=None, **kwargs):
        """
        After login: first-time with one unfinished character -> puppet straight into
        chargen. If there is exactly one finished character, auto-puppet into it
        and skip the Soul Registry menu. Otherwise show the Soul Registry.
        """
        protocol_flags = self.attributes.get("_saved_protocol_flags", {})
        if session and protocol_flags:
            session.update_flags(**protocol_flags)
        if session:
            session.msg(logged_in={})
        self._send_to_connect_channel("|G{key} connected|n".format(key=self.key))

        # Mandatory subscribe to Help (xhelp) so staff can reply; players only see their own messages and staff's private xhelp/Name replies
        _auto_subscribe_help_channel(self)

        # Character selection logic:
        # - If exactly one character and it still needs chargen -> auto-puppet into chargen.
        # - If exactly one finished character -> auto-puppet into it and skip Soul Registry.
        # - Otherwise (0 or multiple) -> show the Soul Registry menu.
        chars = list(self.characters.all()) if hasattr(self, "characters") else []
        if session and len(chars) == 1:
            char = chars[0]
            try:
                # Needs chargen: go straight into chargen on first login.
                if getattr(char.db, "needs_chargen", False):
                    char.db._suppress_become_message = True  # no "You become X" before chargen
                    self.puppet_object(session, char)
                    return  # chargen runs in Character.at_post_puppet
                # Finished character: just puppet into the world.
                char.db._suppress_become_message = True
                self.puppet_object(session, char)
                return
            except Exception:
                pass

        from world.main_menu import start_main_menu
        start_main_menu(self)

    def get_cmdsets(self, caller, current, **kwargs):
        """Return cmdsets for merger. Never return None for current so the merger never hits 'NoneType' no_objs."""
        cur = self.cmdset.current
        stack = list(self.cmdset.cmdset_stack)
        if cur is None:
            from evennia.commands.cmdset import CmdSet
            cur = CmdSet()
        return cur, stack

    def at_look(self, target=None, session=None, **kwargs):
        """OOC look: suppress the default 'Account X (you are Out-of-Character)' block entirely.
        The Soul Registry menu is the only UI we show at account level."""
        return ""

    def at_pre_channel_msg(self, message, channel, senders=None, **kwargs):
        """
        - Help channel: non-staff only see their own messages; staff see all.
        - OOC-Chat: use account's ooc_display_name (set with @oocname) instead of character/key.
        """
        chan_key = getattr(channel, "key", None) or ""
        # Assist: one-way to staff — players only see messages they sent
        if chan_key == "Assist" and senders:
            if self not in senders and not self.permissions.check("Builder"):
                return None  # abort receive for this recipient
        # OOC-Chat: show account OOC display name, not character name
        if chan_key == "OOC-Chat" and senders:
            sender_string = ", ".join(
                (getattr(s, "db", None) and getattr(s.db, "ooc_display_name", None)) or getattr(s, "key", str(s))
                for s in senders
            )
            message_lstrip = message.lstrip()
            if message_lstrip.startswith((":", ";")):
                spacing = "" if message_lstrip[1:].startswith((":", "'", ",")) else " "
                message = f"{sender_string}{spacing}{message_lstrip[1:]}"
            else:
                message = f"{sender_string}: {message}"
            if not kwargs.get("no_prefix") and not kwargs.get("emit"):
                message = channel.channel_prefix() + message
            return message
        return super().at_pre_channel_msg(message, channel, senders=senders, **kwargs)


class Guest(DefaultGuest):
    """
    This class is used for guest logins. Unlike Accounts, Guests and their
    characters are deleted after disconnection.
    """

    pass
