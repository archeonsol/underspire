"""
Channel commands: subscribe/unsubscribe, xooc/xgame/xstaff, help reply, help, ooc name.
"""

from commands.base_cmds import Command


def _send_to_channel(caller, channel_alias, args, session, msg_func, no_channel_msg, no_send_msg, usage_msg):
    """Helper: resolve account, find channel by alias, check send, send message."""
    from evennia import search_channel
    from evennia.utils.utils import strip_unsafe_input
    account = getattr(caller, "account", caller)
    if not hasattr(account, "permissions"):
        msg_func("You must be logged in to use channels.")
        return
    channels = search_channel(channel_alias)
    if not channels:
        msg_func(no_channel_msg)
        return
    try:
        channel = channels[0]
    except (TypeError, IndexError):
        msg_func(no_channel_msg)
        return
    if not channel.access(account, "send"):
        msg_func(no_send_msg)
        return
    message = (args or "").strip()
    if not message:
        msg_func(usage_msg)
        return
    message = strip_unsafe_input(message, session)
    channel.msg(message, senders=account)


def _subscribe_channel(account, alias, msg_func):
    """Subscribe account to channel by alias (xooc, xgame, xstaff). Returns True on success."""
    from evennia import search_channel
    channels = search_channel(alias)
    if not channels:
        msg_func("No channel found matching '%s'." % alias)
        return False
    try:
        channel = channels[0]
    except (TypeError, IndexError):
        msg_func("No channel found matching '%s'." % alias)
        return False
    if not channel.access(account, "listen"):
        msg_func("You are not allowed to subscribe to that channel.")
        return False
    if channel.has_connection(account):
        msg_func("You are already subscribed to %s." % channel.key)
        return False
    if not channel.connect(account):
        msg_func("Could not subscribe to %s." % channel.key)
        return False
    msg_func("You are now subscribed to |w%s|n (%s). You can leave with |wchannelunsub %s|n." % (channel.key, alias, alias))
    return True


def _unsubscribe_channel(account, alias, msg_func):
    """Unsubscribe account from channel by alias. Returns True on success. Assist (xassist) cannot be left."""
    from evennia import search_channel
    channels = search_channel(alias)
    if not channels:
        msg_func("No channel found matching '%s'." % alias)
        return False
    try:
        channel = channels[0]
    except (TypeError, IndexError):
        msg_func("No channel found matching '%s'." % alias)
        return False
    if getattr(channel, "key", None) == "Assist":
        msg_func("You cannot leave the Assist channel (xassist); it is mandatory so staff can reach you.")
        return False
    if not channel.has_connection(account):
        msg_func("You are not subscribed to %s." % channel.key)
        return False
    channel.disconnect(account)
    msg_func("You left %s (%s)." % (channel.key, alias))
    return True


def _xhelp_staff_reply(caller, target_name, message, msg_func, session):
    """Send a private help reply from staff to one account. Returns True on success."""
    from evennia.utils.search import search_account
    from evennia.utils.utils import strip_unsafe_input
    if not target_name or not (message or "").strip():
        return False
    accounts = search_account(target_name, exact=False)
    if not accounts:
        msg_func("No account found matching '%s'." % target_name)
        return False
    try:
        account = accounts[0]
    except (TypeError, IndexError, AttributeError):
        msg_func("No account found matching '%s'." % target_name)
        return False
    message = strip_unsafe_input(message.strip(), session)
    account.msg("|m[Help reply from Staff]|n %s" % message)
    msg_func("You replied privately to |w%s|n: %s" % (account.key, message))
    return True


class CmdChannelSub(Command):
    """Subscribe to an OOC channel so you can send and receive. Usage: channelsub xooc"""
    key = "channelsub"
    aliases = ["chsub"]
    locks = "cmd:all()"
    help_category = "Channels"

    def func(self):
        account = getattr(self.caller, "account", self.caller)
        if not hasattr(account, "permissions"):
            self.msg("You must be logged in.")
            return
        alias = (self.args or "").strip().lower()
        if not alias:
            self.msg("Usage: channelsub <channel>   (e.g. channelsub xooc, channelsub xgame). Staff: channelsub xstaff")
            return
        _subscribe_channel(account, alias, self.msg)


class CmdChannelUnsub(Command):
    """Leave an OOC channel. Usage: channelunsub xooc"""
    key = "channelunsub"
    aliases = ["chunsub"]
    locks = "cmd:all()"
    help_category = "Channels"

    def func(self):
        account = getattr(self.caller, "account", self.caller)
        if not hasattr(account, "permissions"):
            self.msg("You must be logged in.")
            return
        alias = (self.args or "").strip().lower()
        if not alias:
            self.msg("Usage: channelunsub <channel>   (e.g. channelunsub xooc)")
            return
        _unsubscribe_channel(account, alias, self.msg)


class CmdXooc(Command):
    """Send a message to OOC-Chat (xooc). Use @oocname to set the name others see."""
    key = "xooc"
    locks = "cmd:all()"
    help_category = "Channels"

    def func(self):
        _send_to_channel(
            self.caller, "xooc", self.args, self.session, self.msg,
            "OOC-Chat channel is not available.",
            "You are not allowed to send to OOC-Chat.",
            "Usage: xooc <message>",
        )


class CmdXgame(Command):
    """Send a message to Game-Help (xgame)."""
    key = "xgame"
    locks = "cmd:all()"
    help_category = "Channels"

    def func(self):
        _send_to_channel(
            self.caller, "xgame", self.args, self.session, self.msg,
            "Game-Help channel is not available.",
            "You are not allowed to send to Game-Help.",
            "Usage: xgame <message>",
        )


class CmdXstaff(Command):
    """Send a message to the Staff channel (staff only)."""
    key = "xstaff"
    locks = "cmd:perm(Builder)"
    help_category = "Channels"

    def func(self):
        _send_to_channel(
            self.caller, "xstaff", self.args, self.session, self.msg,
            "Staff channel is not available.",
            "You are not allowed to send to the Staff channel.",
            "Usage: xstaff <message>",
        )


class CmdHelpReply(Command):
    """Staff only: send a private reply to one player on the Assist channel. Usage: xassistreply <account> <message>"""
    key = "xassistreply"
    locks = "cmd:perm(Builder)"
    help_category = "Channels"

    def func(self):
        caller = getattr(self.caller, "account", self.caller)
        raw = (self.args or "").strip()
        parts = raw.split(None, 1)
        if len(parts) < 2:
            self.msg("Usage: xassistreply <account> <message>   (e.g. xassistreply skythia Hello.)")
            return
        _xhelp_staff_reply(caller, parts[0], parts[1], self.msg, self.session)


class CmdHelp(Command):
    """
    Send to the Assist channel (you only see your own; staff see all).
    Staff reply privately with: xassistreply <account> <message>
    """
    key = "xassist"
    aliases = []
    locks = "cmd:all()"
    help_category = "Channels"

    def func(self):
        from evennia import search_channel
        from evennia.utils.utils import strip_unsafe_input
        caller = getattr(self.caller, "account", self.caller)
        if not hasattr(caller, "permissions"):
            self.msg("You must be logged in to use the Help channel.")
            return
        raw = (self.args or "").strip()
        channels = search_channel("xassist") or search_channel("Assist")
        if not channels:
            self.msg("Assist channel is not available.")
            return
        channel = channels[0]
        if not channel.access(caller, "send"):
            self.msg("You are not allowed to send to the Assist channel.")
            return
        if not raw:
            self.msg("Usage: xassist <message>   (Staff reply privately: xassistreply <account> <message>)")
            return
        message = strip_unsafe_input(raw, self.session)
        channel.msg(message, senders=caller)


class CmdOocName(Command):
    """
    Set the name shown when you speak on OOC-Chat (xooc). If unset, your account name is used.
    Usage:
      @oocname [name]
    With no args, show current OOC name. With a name, set it.
    """
    key = "@oocname"
    aliases = ["oocname"]
    locks = "cmd:all()"
    help_category = "Channels"

    def func(self):
        caller = getattr(self.caller, "account", self.caller)
        if not hasattr(caller, "db"):
            self.msg("No account.")
            return
        if not self.args or not self.args.strip():
            current = getattr(caller.db, "ooc_display_name", None) or caller.key
            self.msg("Your OOC display name is: |w%s|n. Set it with |w@oocname <name>|n." % current)
            return
        name = self.args.strip()[:64]
        caller.db.ooc_display_name = name
        self.msg("OOC display name set to |w%s|n. You will appear as this on OOC-Chat (xooc)." % name)
