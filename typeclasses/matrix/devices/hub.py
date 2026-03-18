"""
Hub Device - Personal Network Hub

A hub is a personal networked device that creates a customizable virtual space
in the Matrix. It serves as a home base for deckers and can be customized
via device commands.

Key features:
- Customizable description via cmd.exe describe command
- File storage for personal data
- ACL-controlled access
- Can add custom "details" (examinable features)
"""

from typeclasses.matrix.objects import NetworkedObject


class Hub(NetworkedObject):
    """
    Personal network hub device.

    Hubs create a private virtual space in the Matrix that can be customized.
    They have storage for personal files and can be decorated with custom
    descriptions and details.

    Device Commands (via cmd.exe):
        describe <text> - Set the hub's main description
        detail <key> <text> - Add an examinable detail
        remove_detail <key> - Remove an examinable detail
        list_details - Show all details
    """

    def at_object_creation(self):
        """Initialize the hub device."""
        super().at_object_creation()
        self.setup_networked_attrs()

        # Hub-specific attributes
        self.db.device_type = "hub"
        self.db.has_storage = True  # Hubs can store files
        self.db.has_controls = True  # Hubs have customization controls
        self.db.security_level = 1  # Low security by default (personal device)

        # Hub customization
        self.db.hub_desc = None  # Custom description for interface room
        self.db.hub_details = {}  # Custom examinable details {key: description}

        # Interface room description template
        self.db.interface_desc = (
            "A blank virtual space, waiting to be customized. "
            "This is your private network node - shape it as you see fit."
        )

        # Register device commands
        self.register_device_command(
            "describe",
            "handle_describe",
            help_text="Set hub description: describe <text>",
            requires_acl=True  # Only authorized users can customize
        )
        self.register_device_command(
            "detail",
            "handle_add_detail",
            help_text="Add examinable detail: detail <key> <description>",
            requires_acl=True
        )
        self.register_device_command(
            "remove_detail",
            "handle_remove_detail",
            help_text="Remove detail: remove_detail <key>",
            requires_acl=True
        )
        self.register_device_command(
            "list_details",
            "handle_list_details",
            help_text="List all custom details"
            # No restrictions - anyone can view
        )

        # Add owner to ACL by default
        if self.location and hasattr(self.location, 'pk'):
            # If placed in a character's inventory on creation
            from typeclasses.characters import Character
            if isinstance(self.location, Character):
                self.add_to_acl(self.location)

    def handle_describe(self, caller, *args):
        """
        Set the hub's interface room description.

        Usage: patch cmd.exe describe <text>

        Args:
            caller (MatrixAvatar): The avatar executing the command
            *args: Description text (joined with spaces)

        Returns:
            bool: True on success, False on failure
        """
        if not args:
            # Show current description
            current = self.db.hub_desc or self.db.interface_desc
            caller.msg(f"|c=== Current Hub Description ===|n")
            caller.msg(current)
            caller.msg("\nUsage: patch cmd.exe describe <new description>")
            return True

        # Check if caller is authorized (on ACL)
        if not self.check_acl(caller):
            caller.msg("|rAccess denied. You are not authorized to modify this hub.|n")
            return False

        # Set new description
        new_desc = ' '.join(args)
        self.db.hub_desc = new_desc

        # Update interface room if it exists
        interface_pk = getattr(self.db, 'interface_node', None)
        if interface_pk:
            try:
                from typeclasses.matrix.rooms import MatrixNode
                interface = MatrixNode.objects.get(pk=interface_pk)
                interface.db.desc = new_desc
                caller.msg("|gHub description updated!|n")
                caller.msg(f"New description: {new_desc}")
            except MatrixNode.DoesNotExist:
                # Interface doesn't exist yet, just save to db
                caller.msg("|gHub description saved. Will apply when interface is created.|n")
        else:
            caller.msg("|gHub description saved. Will apply when interface is created.|n")

        return True

    def handle_add_detail(self, caller, *args):
        """
        Add an examinable detail to the hub interface.

        Usage: patch cmd.exe detail <key> <description>

        Example: patch cmd.exe detail fountain A crystalline data fountain

        Args:
            caller (MatrixAvatar): The avatar executing the command
            *args: Detail key and description

        Returns:
            bool: True on success, False on failure
        """
        if len(args) < 2:
            caller.msg("Usage: patch cmd.exe detail <key> <description>")
            caller.msg("\nExample: patch cmd.exe detail fountain A crystalline data fountain")
            return False

        # Check authorization
        if not self.check_acl(caller):
            caller.msg("|rAccess denied. You are not authorized to modify this hub.|n")
            return False

        detail_key = args[0].lower()
        detail_desc = ' '.join(args[1:])

        # Initialize details if needed
        if not hasattr(self.db, 'hub_details'):
            self.db.hub_details = {}

        # Add detail
        self.db.hub_details[detail_key] = detail_desc

        # Update interface room if it exists
        interface_pk = getattr(self.db, 'interface_node', None)
        if interface_pk:
            try:
                from typeclasses.matrix.rooms import MatrixNode
                interface = MatrixNode.objects.get(pk=interface_pk)
                if not hasattr(interface.db, 'details'):
                    interface.db.details = {}
                interface.db.details[detail_key] = detail_desc
                caller.msg(f"|gDetail '{detail_key}' added to hub interface.|n")
            except MatrixNode.DoesNotExist:
                caller.msg(f"|gDetail '{detail_key}' saved. Will apply when interface is created.|n")
        else:
            caller.msg(f"|gDetail '{detail_key}' saved. Will apply when interface is created.|n")

        return True

    def handle_remove_detail(self, caller, *args):
        """
        Remove an examinable detail from the hub interface.

        Usage: patch cmd.exe remove_detail <key>

        Args:
            caller (MatrixAvatar): The avatar executing the command
            *args: Detail key to remove

        Returns:
            bool: True on success, False on failure
        """
        if not args:
            caller.msg("Usage: patch cmd.exe remove_detail <key>")
            return False

        # Check authorization
        if not self.check_acl(caller):
            caller.msg("|rAccess denied. You are not authorized to modify this hub.|n")
            return False

        detail_key = args[0].lower()

        # Check if detail exists
        if not hasattr(self.db, 'hub_details') or detail_key not in self.db.hub_details:
            caller.msg(f"|yDetail '{detail_key}' not found.|n")
            return False

        # Remove from saved details
        del self.db.hub_details[detail_key]

        # Remove from interface room if it exists
        interface_pk = getattr(self.db, 'interface_node', None)
        if interface_pk:
            try:
                from typeclasses.matrix.rooms import MatrixNode
                interface = MatrixNode.objects.get(pk=interface_pk)
                if hasattr(interface.db, 'details') and detail_key in interface.db.details:
                    del interface.db.details[detail_key]
                caller.msg(f"|gDetail '{detail_key}' removed from hub interface.|n")
            except MatrixNode.DoesNotExist:
                caller.msg(f"|gDetail '{detail_key}' removed.|n")
        else:
            caller.msg(f"|gDetail '{detail_key}' removed.|n")

        return True

    def handle_list_details(self, caller, *args):
        """
        List all custom details on the hub.

        Usage: patch cmd.exe list_details

        Args:
            caller (MatrixAvatar): The avatar executing the command
            *args: Unused

        Returns:
            bool: Always True
        """
        if not hasattr(self.db, 'hub_details') or not self.db.hub_details:
            caller.msg("This hub has no custom details.")
            caller.msg("\nAdd details with: patch cmd.exe detail <key> <description>")
            return True

        caller.msg("|c=== Hub Details ===|n")
        for key, desc in self.db.hub_details.items():
            caller.msg(f"|w{key}|n: {desc}")

        return True

    def at_post_puppet(self, **kwargs):
        """
        Called after a character is puppeted (not directly relevant for devices,
        but kept for potential future use).
        """
        pass

    def return_appearance(self, looker, **kwargs):
        """
        Customize how the hub appears when examined in meatspace.

        Args:
            looker: The object examining this hub
            **kwargs: Additional arguments

        Returns:
            str: Description of the hub
        """
        # Get base appearance
        text = super().return_appearance(looker, **kwargs)

        # Add connection status
        if self.is_connected():
            text += "\n|g[ONLINE]|n Connected to the Matrix."
        else:
            text += "\n|r[OFFLINE]|n Not connected to any network."

        # Add customization info if owner is looking
        if self.check_acl(looker):
            text += "\n|yThis is your hub. Jack in to customize it via cmd.exe.|n"

        return text
