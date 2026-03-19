"""
Handset Device - Personal Communication Device

A handset is a personal networked device (phone) that provides access to
Matrix communication features like calls, texts, and social media.

The handset authenticates using the holder's Matrix ID (chip implant) and
provides access to their Matrix account settings.

Key features:
- View account info (Matrix ID, alias)
- Set/change Matrix alias
- Future: calls, texts, contacts, camera, social media
"""

from typeclasses.matrix.items import NetworkedItem
from world.matrix_accounts import get_account, set_alias, get_alias, has_alias


class Handset(NetworkedItem):
    """
    Personal communication device (phone).

    Basic handsets authenticate using the holder's Matrix chip ID.
    Future jailbroken devices can have independent IDs.

    Device Commands (physical only):
        account - View your Matrix account info
        set_alias - Set your Matrix alias (@handle)
    """

    def at_object_creation(self):
        """Initialize the handset device."""
        super().at_object_creation()
        self.setup_networked_attrs()

        # Handset-specific attributes
        self.db.device_type = "handset"
        self.db.has_storage = True  # Store contacts, messages
        self.db.has_controls = False  # No customization like hubs
        self.db.security_level = 0  # Personal device, low security
        self.db.is_jailbroken = False  # Future feature

        # Register device commands
        self.register_device_command(
            "account",
            "handle_account_info",
            help_text="View your Matrix account information",
            auth_level=0
        )
        self.register_device_command(
            "set_alias",
            "handle_set_alias",
            help_text="Set your Matrix alias: set_alias @name",
            auth_level=0,
            physical_only=True
        )

    def get_authenticated_user(self):
        """
        Get the character currently authenticated on this handset.

        For basic handsets, this is whoever is holding/wearing it.
        Future jailbroken devices may have separate authentication.

        Returns:
            Character or None: The authenticated user
        """
        # For now, handset authenticates whoever is holding it
        if hasattr(self, 'location'):
            from typeclasses.characters import Character
            if isinstance(self.location, Character):
                return self.location
        return None

    def _get_user_from_caller(self, caller):
        """
        Get the actual user character from a caller.

        For physical access, caller is the character directly.
        For Matrix access, caller might be an avatar - get the operator.

        Args:
            caller: The caller (Character or MatrixAvatar)

        Returns:
            Character or None: The user character
        """
        from typeclasses.characters import Character
        if isinstance(caller, Character):
            return caller

        # Check if it's a Matrix avatar with an operator
        if hasattr(caller, 'db') and hasattr(caller.db, 'operator'):
            return caller.db.operator

        return None

    def handle_account_info(self, caller, *args):
        """
        Display the user's Matrix account information.

        Shows:
        - Matrix ID (chip ID)
        - Current alias (if set)
        - Future: account creation date, reputation, etc.

        Authenticates via whoever is holding the handset (works from Matrix or physical).

        Args:
            caller: The character/avatar using the command

        Returns:
            bool: Always True
        """
        # Always authenticate via who's holding the device
        user = self.get_authenticated_user()
        if not user:
            caller.msg("|rHandset authentication failed. Nobody is holding this device.|n")
            return False

        # Get account data
        account = get_account(user)
        matrix_id = account.get('matrix_id') or 'Not assigned'
        alias = account.get('alias') or '|x(not set)|n'

        # Build display
        caller.msg("|c" + "=" * 50 + "|n")
        caller.msg("|c=== Matrix Account Information ===|n")
        caller.msg("|c" + "=" * 50 + "|n")
        caller.msg(f"\n|wMatrix ID:|n {matrix_id}")

        # Display alias with @ prefix (UI decoration)
        if account.get('alias'):
            caller.msg(f"|wAlias:|n @{alias}")
        else:
            caller.msg(f"|wAlias:|n |x(not set)|n")
            caller.msg("\n|yYou haven't set an alias yet.|n")
            caller.msg("Set one with: |wset_alias @yourname|n")

        if account.get('created'):
            caller.msg(f"\n|xAccount created: {account['created']}|n")

        caller.msg("|c" + "=" * 50 + "|n")

        return True

    def handle_set_alias(self, caller, *args):
        """
        Set the user's Matrix alias.

        Usage: set_alias @newname

        The alias must:
        - Start with @
        - Be 2-10 characters
        - Contain only letters, numbers, underscore
        - Be unique (not taken by another user)

        Args:
            caller: The character using the command
            *args: The desired alias

        Returns:
            bool: True on success, False on failure
        """
        user = self._get_user_from_caller(caller)
        if not user:
            caller.msg("|rHandset authentication failed.|n")
            return False

        if not args:
            # Show current alias and usage
            current_alias = get_alias(user)
            if current_alias:
                caller.msg(f"Your current alias is: |w@{current_alias}|n")
            else:
                caller.msg("You don't have an alias set yet.")

            caller.msg("\n|wUsage:|n set_alias @yourname")
            caller.msg("\nAlias must be 2-10 characters and contain only letters, numbers, and underscores.")
            caller.msg("Example: set_alias @runner")
            return False

        # Get the desired alias
        new_alias = args[0].strip()

        # Attempt to set it
        success, message = set_alias(user, new_alias)

        if success:
            caller.msg(f"|g{message}|n")
        else:
            caller.msg(f"|r{message}|n")

        return success

    def return_appearance(self, looker, **kwargs):
        """
        Customize how the handset appears when examined.

        Args:
            looker: The object examining this handset
            **kwargs: Additional arguments

        Returns:
            str: Description of the handset
        """
        # Get base appearance
        text = super().return_appearance(looker, **kwargs)

        # Show authentication status if holder is looking
        user = self.get_authenticated_user()
        if user and user == looker:
            matrix_id = user.get_matrix_id() if hasattr(user, 'get_matrix_id') else None
            if matrix_id:
                text += f"\n|gAuthenticated to your Matrix chip: {matrix_id}|n"

            # Show alias if set (with @ prefix for display)
            alias = get_alias(user)
            if alias:
                text += f"\n|wMatrix alias: @{alias}|n"

        # Show network status
        if self.has_network_coverage():
            text += "\n|g[ONLINE]|n Connected to Matrix network."
        else:
            text += "\n|r[OFFLINE]|n No network coverage."

        return text
