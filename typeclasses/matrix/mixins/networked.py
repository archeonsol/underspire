"""
Matrix Mixins

Mixins providing shared functionality for Matrix-related classes.

NetworkedMixin - Provides Matrix connectivity for both objects and items
"""


class NetworkedMixin:
    """
    Mixin providing Matrix connectivity for physical devices.

    This mixin can be used with both Object and Item classes to provide
    networked device functionality. It handles connection tracking, relay
    lookup, and Matrix node creation.

    Classes using this mixin should call setup_networked_attrs() in their
    at_object_creation() method.
    """

    def setup_networked_attrs(self):
        """
        Initialize networked device attributes.

        Should be called in at_object_creation() after super().
        """
        self.db.device_type = "device"  # Override in subclasses (e.g., "camera", "terminal", "hub")
        self.db.matrix_node = None  # Cached reference to this device's Matrix node
        self.db.ephemeral_node = False  # Whether Matrix node is ephemeral (default: persistent)
        self.db.security_level = 0
        self.db.has_storage = False
        self.db.has_controls = False
        self.db.acl = []  # Access Control List - list of character dbrefs with permission
        self.db.storage = []  # File storage (list of dicts with filename, filetype, contents)
        self.db.device_commands = {}  # Registered commands: {command_name: handler_function_name}
        self.db.interface_desc = None  # Custom description for device interface room

    def get_or_create_node(self):
        """
        Get this device's Matrix node, creating it if it doesn't exist.

        DEPRECATED: Use get_or_create_cluster() for ephemeral device interfaces.
        This method is kept for backward compatibility with persistent nodes.

        The node is a virtual room in the Matrix that represents this physical
        device. When someone dives into this device, they enter its node.

        Returns:
            MatrixNode: The Matrix room representing this device
        """
        if not self.db.matrix_node:
            from typeclasses.matrix.rooms import MatrixNode
            self.db.matrix_node = MatrixNode.create_for_device(self)
        return self.db.matrix_node

    def get_or_create_cluster(self):
        """
        Get or create the ephemeral 2-room cluster for this device.

        Creates a vestibule (ICE room) and interface room on first access.
        Both rooms are ephemeral and will be cleaned up when empty.

        Returns:
            dict: {'vestibule': MatrixNode, 'interface': MatrixNode} or None on failure
        """
        from typeclasses.matrix.rooms import MatrixNode
        from evennia.utils.create import create_object

        # Check if cluster already exists
        vestibule_dbref = getattr(self.db, 'vestibule_node', None)
        interface_dbref = getattr(self.db, 'interface_node', None)

        vestibule = None
        interface = None

        # Try to load existing rooms
        if vestibule_dbref:
            try:
                vestibule = MatrixNode.objects.get(pk=vestibule_dbref)
            except MatrixNode.DoesNotExist:
                self.db.vestibule_node = None

        if interface_dbref:
            try:
                interface = MatrixNode.objects.get(pk=interface_dbref)
            except MatrixNode.DoesNotExist:
                self.db.interface_node = None

        # If both exist, return them
        if vestibule and interface:
            return {'vestibule': vestibule, 'interface': interface}

        # Clean up partial cluster
        if vestibule:
            vestibule.delete()
            self.db.vestibule_node = None
        if interface:
            interface.delete()
            self.db.interface_node = None

        # Create new cluster
        device_type = getattr(self.db, 'device_type', 'device')

        # Create vestibule
        vestibule = create_object(
            MatrixNode,
            key=f"{self.key} - Vestibule"
        )
        if not vestibule:
            return None

        vestibule.db.parent_object = self
        vestibule.db.is_vestibule = True
        vestibule.db.ephemeral = True
        vestibule.db.node_type = "device_vestibule"
        vestibule.db.desc = (
            "A stark virtual anteroom. Security protocols hum in the background, "
            "ready to spawn defensive ICE at the first sign of unauthorized access."
        )

        # Create interface room
        interface = create_object(
            MatrixNode,
            key=f"{self.key} - Interface"
        )
        if not interface:
            vestibule.delete()
            return None

        interface.db.parent_object = self
        interface.db.is_interface = True
        interface.db.ephemeral = True
        interface.db.node_type = "device_interface"

        # Set interface description based on device type
        if device_type == "hub":
            # Hub uses custom description or default
            hub_desc = getattr(self.db, 'hub_desc', None)
            if hub_desc:
                interface.db.desc = hub_desc
            else:
                interface.db.desc = (
                    "A blank virtual space, waiting to be customized. "
                    "This is your private network node - shape it as you see fit."
                )
            # Restore hub details if they exist
            hub_details = getattr(self.db, 'hub_details', None)
            if hub_details:
                for key, value in hub_details.items():
                    interface.db.details[key] = value
        else:
            # Generic device interface
            device_desc = getattr(self.db, 'interface_desc', None)
            if device_desc:
                interface.db.desc = device_desc
            else:
                interface.db.desc = (
                    f"A sterile virtual interface space. The {device_type}'s "
                    "systems are accessible here through command consoles."
                )

        # Create exits between rooms
        from evennia.utils.create import create_object
        from typeclasses.matrix.exits import MatrixExit

        # Vestibule -> Interface (locked until ICE defeated or on ACL)
        exit_to_interface = create_object(
            MatrixExit,
            key="interface",
            location=vestibule,
            destination=interface
        )
        # TODO: Add lock based on ICE/ACL status
        # exit_to_interface.locks.add("traverse:...")

        # Interface -> Vestibule (back exit)
        exit_to_vestibule = create_object(
            MatrixExit,
            key="back",
            aliases=["vestibule"],
            location=interface,
            destination=vestibule
        )

        # Store references
        self.db.vestibule_node = vestibule.pk
        self.db.interface_node = interface.pk

        return {'vestibule': vestibule, 'interface': interface}

    def get_relay(self):
        """
        Determine which relay this device is connected through.

        Gets the relay from the room this device is located in.
        Rooms define network coverage via their network_router attribute (dbref).

        Returns:
            Router: The router this device connects through, or None if not connected
        """
        room = self.location
        if not room:
            return None

        # Get router dbref from room
        router_dbref = getattr(room.db, 'network_router', None)
        if not router_dbref:
            return None

        # Look up router by dbref
        from typeclasses.matrix.objects import Router
        try:
            return Router.objects.get(pk=router_dbref)
        except Router.DoesNotExist:
            return None

    def is_connected(self):
        """
        Check if this device is currently connected to the Matrix.

        A device is connected if it can find a relay (either through wireless
        coverage or hardwired connection).

        Returns:
            bool: True if device has an active connection to the Matrix
        """
        relay = self.get_relay()
        return relay is not None

    # =========================================================================
    # Program Interaction Framework
    # =========================================================================

    def register_device_command(self, command_name, handler_method_name, help_text=None,
                                matrix_only=False, physical_only=False, requires_acl=False,
                                auth_level=0, visibility_threshold=0):
        """
        Register a command that can be invoked via device interface menu.

        Device subclasses should call this in at_object_creation() to expose
        device-specific functionality to programs.

        Args:
            command_name (str): The command name (e.g., "describe", "pan", "jack_out")
            handler_method_name (str): Name of the method on this device to call
            help_text (str): Optional help text describing the command
            matrix_only (bool): If True, only accessible from Matrix (not physical access)
            physical_only (bool): If True, only accessible from physical access (not Matrix)
            requires_acl (bool): If True, requires caller to be on device ACL (level 1+)
            auth_level (int): Minimum authorization level required (0-10)
                             0: Public access (no ACL required, anyone can use)
                             1: Minimum entry - just gets you in the door
                             2-3: Low access - basic authenticated commands
                             4-6: Medium access - standard modification commands
                             7-9: High access - advanced commands, full control
                             10: Root/admin - all commands including ACL management
            visibility_threshold (int): Minimum skill level (0-150) to see this command in menu
                                       Uses 'hacking' skill for Matrix access, 'technology' for physical

        Example:
            # Basic command visible to all
            self.register_device_command("status", "handle_status",
                help_text="Show device status", auth_level=0)

            # Medium access command
            self.register_device_command("describe", "handle_describe",
                help_text="Set device description",
                requires_acl=True, auth_level=5)

            # Root-level command for ACL management
            self.register_device_command("grant_access", "handle_grant_access",
                help_text="Grant access to another user",
                requires_acl=True, auth_level=10)

            # Hidden exploit command for skilled hackers
            self.register_device_command("dump_logs", "handle_dump_logs",
                help_text="Extract security logs",
                matrix_only=True, visibility_threshold=75, auth_level=7)
        """
        if not hasattr(self.db, 'device_commands'):
            self.db.device_commands = {}

        self.db.device_commands[command_name] = {
            'handler': handler_method_name,
            'help': help_text or f"Execute {command_name} on this device",
            'matrix_only': matrix_only,
            'physical_only': physical_only,
            'requires_acl': requires_acl,
            'auth_level': auth_level,
            'visibility_threshold': visibility_threshold
        }

    def invoke_device_command(self, command_name, caller, from_matrix=False, *args):
        """
        Invoke a registered device command.

        Args:
            command_name (str): The command to invoke
            caller: The character/avatar invoking the command
            from_matrix (bool): True if accessed from Matrix, False if physical access
            *args: Arguments to pass to the command handler

        Returns:
            bool: True if command executed successfully, False otherwise
        """
        if not hasattr(self.db, 'device_commands'):
            self.db.device_commands = {}

        if command_name not in self.db.device_commands:
            caller.msg(f"|rUnknown command: {command_name}|n")
            return False

        cmd_data = self.db.device_commands[command_name]

        # Check access restrictions
        if cmd_data.get('matrix_only', False) and not from_matrix:
            caller.msg(f"|rCommand '{command_name}' requires Matrix access.|n")
            return False

        if cmd_data.get('physical_only', False) and from_matrix:
            caller.msg(f"|rCommand '{command_name}' requires physical access.|n")
            return False

        # Check authorization level
        required_auth_level = cmd_data.get('auth_level', 0)
        if required_auth_level > 0 or cmd_data.get('requires_acl', False):
            caller_level = self.get_acl_level(caller)
            # If requires_acl is set but auth_level is 0, default to level 1
            if cmd_data.get('requires_acl', False) and required_auth_level == 0:
                required_auth_level = 1

            if caller_level < required_auth_level:
                caller.msg(f"|rAccess denied. Command '{command_name}' requires authorization level {required_auth_level} (you have level {caller_level}).|n")
                return False

        handler_name = cmd_data['handler']
        handler = getattr(self, handler_name, None)

        if not handler or not callable(handler):
            caller.msg(f"|rCommand handler '{handler_name}' not found on device.|n")
            return False

        try:
            return handler(caller, *args)
        except Exception as e:
            caller.msg(f"|rCommand execution failed: {e}|n")
            return False

    def get_available_commands(self, caller=None, from_matrix=False):
        """
        Get a list of available device commands for a given caller.

        Filters commands based on access restrictions and skill thresholds.

        Args:
            caller: The character/avatar checking available commands
            from_matrix (bool): True if accessed from Matrix, False if physical access

        Returns:
            dict: Dictionary of {command_name: help_text} for visible/accessible commands
        """
        if not hasattr(self.db, 'device_commands'):
            return {}

        # If no caller, return all commands (for admin/debugging)
        if not caller:
            return {
                cmd: info['help']
                for cmd, info in self.db.device_commands.items()
            }

        # Determine caller's skill level
        if from_matrix:
            # For Matrix avatars, check operator's hacking skill
            from typeclasses.matrix.avatars import MatrixAvatar
            if isinstance(caller, MatrixAvatar):
                operator = caller.db.operator
                skill = operator.db.skills.get('hacking', 0) if operator else 0
            else:
                skill = 0
        else:
            # For physical access, check technology skill
            skill = caller.db.skills.get('technology', 0) if hasattr(caller, 'db') else 0

        available = {}
        for cmd_name, cmd_info in self.db.device_commands.items():
            # Check access mode restrictions
            if cmd_info.get('matrix_only', False) and not from_matrix:
                continue
            if cmd_info.get('physical_only', False) and from_matrix:
                continue

            # Check skill visibility threshold
            threshold = cmd_info.get('visibility_threshold', 0)
            if skill < threshold:
                continue

            available[cmd_name] = cmd_info['help']

        return available

    def check_acl(self, character, required_level=1):
        """
        Check if a character is authorized on this device's ACL.

        For MatrixAvatars, checks BOTH:
        - The physical operator (grants physical + Matrix access)
        - The avatar itself (grants Matrix-only access)

        This allows avatars to be granted access independently, enabling
        Matrix users to authorize other avatars without knowing their
        physical identities.

        Args:
            character: The character to check (Character or MatrixAvatar)
            required_level (int): Minimum authorization level required (1-10)

        Returns:
            int: Authorization level (0 if not authorized, 1-10 if authorized)
        """
        if not hasattr(self.db, 'acl') or not self.db.acl:
            return 0

        # Migrate old list-based ACL to dict-based ACL
        if isinstance(self.db.acl, list):
            old_acl = self.db.acl
            self.db.acl = {}
            for char_pk in old_acl:
                # Default old entries to level 5 (medium access)
                self.db.acl[char_pk] = 5

        # For MatrixAvatar, check BOTH operator AND avatar (return highest level)
        from typeclasses.matrix.avatars import MatrixAvatar
        if isinstance(character, MatrixAvatar):
            max_level = 0
            # Check if the physical operator is authorized
            operator = character.db.operator
            if operator and operator.pk in self.db.acl:
                max_level = max(max_level, self.db.acl[operator.pk])
            # Also check if the avatar itself is authorized (Matrix-only access)
            if character.pk in self.db.acl:
                max_level = max(max_level, self.db.acl[character.pk])
            return max_level

        # For regular characters, check their dbref
        return self.db.acl.get(character.pk, 0)

    def get_acl_level(self, character):
        """
        Get the authorization level for a character.

        Args:
            character: The character to check (Character or MatrixAvatar)

        Returns:
            int: Authorization level (0 if not authorized, 1-10 if authorized)
        """
        return self.check_acl(character, required_level=0)

    def add_to_acl(self, character, level=5):
        """
        Add a character to this device's Access Control List.

        For MatrixAvatars: Adds the AVATAR itself (not the operator).
        This grants Matrix-only access - the avatar can access from the Matrix
        but doesn't get physical access to the device.

        For Characters: Adds the physical character, granting both physical
        and Matrix access (when they jack in).

        Args:
            character: The character to add (Character or MatrixAvatar)
            level (int): Authorization level to grant (1-10, default 5)
                        1: Entry level - can access interface, basic viewing
                        2-3: Low access - basic authenticated commands
                        4-6: Medium access - standard commands, modifications
                        7-9: High access - advanced commands, full control
                        10: Root access - all commands, ACL management

        Returns:
            bool: True if added/updated, False on error
        """
        if not hasattr(self.db, 'acl'):
            self.db.acl = {}

        # Migrate old list-based ACL to dict-based ACL
        if isinstance(self.db.acl, list):
            old_acl = self.db.acl
            self.db.acl = {}
            for char_pk in old_acl:
                # Default old entries to level 5 (medium access)
                self.db.acl[char_pk] = 5

        # Clamp level to valid range
        level = max(1, min(10, level))

        # For MatrixAvatar, add the AVATAR itself (Matrix-only access)
        # For Character, add the character (physical + Matrix access)
        char_pk = character.pk

        # Add or update the entry
        self.db.acl[char_pk] = level
        return True

    def remove_from_acl(self, character):
        """
        Remove a character from this device's Access Control List.

        For MatrixAvatars: Removes the avatar itself.
        For Characters: Removes the physical character.

        Args:
            character: The character to remove (Character or MatrixAvatar)

        Returns:
            bool: True if removed, False if not on list
        """
        if not hasattr(self.db, 'acl') or not self.db.acl:
            return False

        # Migrate old list-based ACL to dict-based ACL
        if isinstance(self.db.acl, list):
            old_acl = self.db.acl
            self.db.acl = {}
            for char_pk in old_acl:
                # Default old entries to level 5 (medium access)
                self.db.acl[char_pk] = 5

        # Remove the character/avatar by its own pk
        char_pk = character.pk

        if char_pk not in self.db.acl:
            return False

        del self.db.acl[char_pk]
        return True

    def get_acl_names(self):
        """
        Get a list of character/avatar names on the ACL with type indicators and levels.

        Returns:
            list: List of formatted names showing type and authorization level:
                  "CharName (physical, level 10)" - Physical character with level
                  "AvatarName (matrix, level 5)" - Matrix avatar with level
                  "[Unknown #123]" - Deleted object
        """
        if not hasattr(self.db, 'acl') or not self.db.acl:
            return []

        # Migrate old list-based ACL to dict-based ACL
        if isinstance(self.db.acl, list):
            old_acl = self.db.acl
            self.db.acl = {}
            for char_pk in old_acl:
                # Default old entries to level 5 (medium access)
                self.db.acl[char_pk] = 5

        from evennia.objects.models import ObjectDB
        from typeclasses.matrix.avatars import MatrixAvatar

        names = []
        for char_pk, level in self.db.acl.items():
            try:
                obj = ObjectDB.objects.get(pk=char_pk)
                # Check if it's a MatrixAvatar
                if obj.typeclass_path and 'MatrixAvatar' in obj.typeclass_path:
                    names.append(f"{obj.key} (matrix, level {level})")
                else:
                    names.append(f"{obj.key} (physical, level {level})")
            except ObjectDB.DoesNotExist:
                names.append(f"[Unknown #{char_pk}, level {level}]")

        return names

    def add_file(self, filename, filetype, contents):
        """
        Add a file to this device's storage.

        Args:
            filename (str): Name of the file
            filetype (str): Type of file (text, data, binary, etc.)
            contents (str): File contents

        Returns:
            bool: True if added, False if storage not available or file exists
        """
        if not self.db.has_storage:
            return False

        if not hasattr(self.db, 'storage'):
            self.db.storage = []

        # Check if file already exists
        if any(f['filename'] == filename for f in self.db.storage):
            return False

        self.db.storage.append({
            'filename': filename,
            'filetype': filetype,
            'contents': contents
        })
        return True

    def get_file(self, filename):
        """
        Get a file from this device's storage.

        Args:
            filename (str): Name of the file to retrieve

        Returns:
            dict or None: File dict with filename, filetype, contents, or None if not found
        """
        if not self.db.has_storage:
            return None

        if not hasattr(self.db, 'storage'):
            self.db.storage = []

        for file in self.db.storage:
            if file['filename'] == filename:
                return file

        return None

    def update_file(self, filename, contents):
        """
        Update an existing file's contents.

        Args:
            filename (str): Name of the file to update
            contents (str): New contents

        Returns:
            bool: True if updated, False if file not found
        """
        if not self.db.has_storage:
            return False

        if not hasattr(self.db, 'storage'):
            self.db.storage = []

        for file in self.db.storage:
            if file['filename'] == filename:
                file['contents'] = contents
                return True

        return False

    def delete_file(self, filename):
        """
        Delete a file from this device's storage.

        Args:
            filename (str): Name of the file to delete

        Returns:
            bool: True if deleted, False if file not found
        """
        if not self.db.has_storage:
            return False

        if not hasattr(self.db, 'storage'):
            self.db.storage = []

        for i, file in enumerate(self.db.storage):
            if file['filename'] == filename:
                self.db.storage.pop(i)
                return True

        return False

    def list_files(self):
        """
        Get a list of all files on this device.

        Returns:
            list: List of file dicts with filename, filetype, contents
        """
        if not self.db.has_storage:
            return []

        if not hasattr(self.db, 'storage'):
            self.db.storage = []

        return list(self.db.storage)
