"""
Custom unloggedin commands (create account).

Overrides create to: fix "log with" -> "log in with" typo, and surface real
exceptions when account creation fails.
"""

import re
from django.conf import settings
from evennia.utils import class_from_module, logger

from evennia.commands.default.unloggedin import CmdUnconnectedCreate as DefaultCmdUnconnectedCreate


class CmdUnconnectedCreate(DefaultCmdUnconnectedCreate):
    """Create a new account; fix success-message typo and surface creation errors."""

    def func(self):
        session = self.caller
        args = self.args.strip()
        address = session.address
        Account = class_from_module(settings.BASE_ACCOUNT_TYPECLASS)

        parts = [part.strip() for part in re.split(r"\"", args) if part.strip()]
        if len(parts) == 1:
            parts = parts[0].split(None, 1)
        if len(parts) != 2:
            session.msg(
                "\n Usage (without <>): create <name> <password>"
                "\nIf <name> or <password> contains spaces, enclose it in double quotes."
            )
            return

        username, password = parts
        non_normalized_username = username
        username = Account.normalize_username(username)
        if non_normalized_username != username:
            session.msg(
                "Note: your username was normalized to strip spaces and remove characters "
                "that could be visually confusing."
            )

        answer = yield (
            f"You want to create an account '{username}' with password '{password}'."
            "\nIs this what you intended? [Y]/N?"
        )
        if answer.lower() in ("n", "no"):
            session.msg("Aborted. If your user name contains spaces, surround it by quotes.")
            return

        try:
            account, errors = Account.create(
                username=username, password=password, ip=address, session=session
            )
        except Exception as e:
            logger.log_trace()
            session.msg(
                "|rAccount creation failed.|n\n|y%s: %s|n" % (type(e).__name__, e)
            )
            return

        if account:
            string = "A new account '%s' was created. Welcome!"
            if " " in username:
                string += '\n\nYou can now log in with the command \'connect "%s" <your password>\'.'
            else:
                string += "\n\nYou can now log in with the command 'connect %s <your password>'."
            session.msg(string % (username, username))
        else:
            session.msg("|R%s|n" % "\n".join(errors))
