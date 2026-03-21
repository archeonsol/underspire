"""
Matrix Mixins

Mixins providing shared functionality for Matrix-related classes.

NetworkedMixin - Provides Matrix connectivity for both objects and items
"""

from world.utils import get_containing_room, room_has_network_coverage
from .matrix_id import MatrixIdMixin


class NetworkedMixin(MatrixIdMixin):
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
        self.db.acl = {}  # Access Control List - dict of {char_pk: level} with permission
        self.db.storage = []  # File storage (list of dicts with filename, filetype, contents)
        self.db.device_commands = {}  # Registered commands: {command_name: handler_function_name}
        self.db.interface_desc = None  # Custom description for device interface room

    def get_or_create_cluster(self):
        """
        Get or create the ephemeral 2-room cluster for this device.

        Creates a checkpoint (ICE room) and interface room on first access.
        Both rooms are ephemeral and will be cleaned up when empty.

        Returns:
            dict: {'checkpoint': MatrixNode, 'interface': MatrixNode} or None on failure
        """
        from typeclasses.matrix.rooms import MatrixNode
        from evennia.utils.create import create_object

        # Check if cluster already exists
        checkpoint_dbref = self.db.checkpoint_node
        interface_dbref = self.db.interface_node

        checkpoint = None
        interface = None

        # Try to load existing rooms
        if checkpoint_dbref:
            try:
                checkpoint = MatrixNode.objects.get(pk=checkpoint_dbref)
            except MatrixNode.DoesNotExist:
                self.db.checkpoint_node = None

        if interface_dbref:
            try:
                interface = MatrixNode.objects.get(pk=interface_dbref)
            except MatrixNode.DoesNotExist:
                self.db.interface_node = None

        # If both exist, return them
        if checkpoint and interface:
            return {'checkpoint': checkpoint, 'interface': interface}

        # Clean up partial cluster
        if checkpoint:
            checkpoint.delete()
            self.db.checkpoint_node = None
        if interface:
            interface.delete()
            self.db.interface_node = None

        # Create new cluster
        device_type = self.db.device_type or 'device'

        # Get Matrix ID for this device
        matrix_id = self.get_matrix_id()

        # Create checkpoint
        checkpoint = create_object(
            MatrixNode,
            key=f"{device_type} {matrix_id} :: Checkpoint"
        )
        if not checkpoint:
            return None

        checkpoint.db.parent_object = self
        checkpoint.db.is_checkpoint = True
        checkpoint.db.ephemeral = True
        checkpoint.db.node_type = "device_checkpoint"
        checkpoint.db.desc = (
            "A stark virtual checkpoint. Security protocols hum in the background, "
            "ready to spawn defensive ICE at the first sign of unauthorized access."
        )

        # Create interface room
        interface = create_object(
            MatrixNode,
            key=f"{device_type} {matrix_id} :: Interface"
        )
        if not interface:
            checkpoint.delete()
            return None

        interface.db.parent_object = self
        interface.db.is_interface = True
        interface.db.ephemeral = True
        interface.db.node_type = "device_interface"

        # Set interface description - devices override interface_desc to customize
        device_desc = self.db.interface_desc
        if device_desc:
            interface.db.desc = device_desc
        else:
            interface.db.desc = (
                f"A sterile virtual interface space. The {device_type}'s "
                "systems are accessible here through command consoles."
            )

        # Create exits between rooms
        from typeclasses.matrix.exits import MatrixExit

        # Checkpoint -> Interface (locked until ICE defeated or on ACL)
        exit_to_interface = create_object(
            MatrixExit,
            key="Interface",
            aliases=["in"],
            location=checkpoint,
            destination=interface
        )
        # TODO: Add lock based on ICE/ACL status
        # exit_to_interface.locks.add("traverse:...")

        # Interface -> Checkpoint (back exit)
        exit_to_checkpoint = create_object(
            MatrixExit,
            key="Checkpoint",
            aliases=["c"],
            location=interface,
            destination=checkpoint
        )

        # Store references
        self.db.checkpoint_node = checkpoint.pk
        self.db.interface_node = interface.pk

        return {'checkpoint': checkpoint, 'interface': interface}

    def get_relay(self):
        """
        Determine which relay this device is connected through.

        Gets the relay from the room this device is located in.
        Rooms define network coverage via their network_router attribute (dbref).

        Returns:
            Router: The router this device connects through, or None if not connected
        """
        room = get_containing_room(self)
        if not room or not room_has_network_coverage(room):
            return None

        # Get router from room
        router_dbref = room.db.network_router
        from typeclasses.matrix.objects import Router
        try:
            return Router.objects.get(pk=router_dbref)
        except Router.DoesNotExist:
            return None



    def has_network_coverage(self):
        """
        Check if this device currently has Matrix network coverage.

        A device has coverage if it can find a relay (either through wireless
        coverage or hardwired connection).

        Returns:
            bool: True if device has active network coverage
        """
        relay = self.get_relay()
        return relay is not None

    # =========================================================================
    # Program Interaction Framework
    # =========================================================================

    def register_device_command(self, command_name, handler_method_name, help_text=None,
                                matrix_only=False, physical_only=False,
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
                auth_level=5)

            # Root-level command for ACL management
            self.register_device_command("grant_access", "handle_grant_access",
                help_text="Grant access to another user",
                auth_level=10)

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
            bool or tuple: True/False for simple commands, or a (node_name, kwargs)
                          tuple if the handler wants to navigate the device menu to
                          another node instead of returning to main.
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
        if required_auth_level > 0:
            caller_level = self.get_acl_level(caller)

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
            from evennia.utils import logger
            logger.log_err(f"Device command '{command_name}' on {self} raised: {e}")
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

        # TODO: Implement skill-based visibility once skill checks are finalized.
        # Skill keys and check mechanics are not yet defined for Matrix/physical access.
        # Returning 150 (max) so all threshold-gated commands are visible during testing.
        skill = 150

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

        self._migrate_acl()

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

    def _migrate_acl(self):
        """
        Migrate old list-based ACL to dict-based ACL in-place.
        Old entries default to level 5 (medium access).
        Safe to call even if acl is already a dict or doesn't exist.
        """
        if not hasattr(self.db, 'acl'):
            return
        if isinstance(self.db.acl, dict):
            return
        old_acl = list(self.db.acl)
        self.db.acl = {}
        for char_pk in old_acl:
            self.db.acl[char_pk] = 5

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

        self._migrate_acl()

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

        self._migrate_acl()

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

        self._migrate_acl()

        from evennia.objects.models import ObjectDB
        from typeclasses.matrix.avatars import MatrixAvatar

        names = []
        for char_pk, level in self.db.acl.items():
            try:
                obj = ObjectDB.objects.get(pk=char_pk)
                if isinstance(obj.typeclass, MatrixAvatar):
                    names.append(f"{obj.key} (matrix, level {level})")
                else:
                    names.append(f"{obj.key} (physical, level {level})")
            except ObjectDB.DoesNotExist:
                names.append(f"<err> (<err>, level {level})")

        return names

    # =========================================================================
    # ACL Management Command Registration and Handlers
    # =========================================================================

    def register_acl_commands(self):
        """
        Register standard ACL management commands.

        Call this in at_object_creation() to add grant and revoke commands
        to the device. Requires level 10 for both commands.

        Note: ACL viewing is available through the main device menu.

        Example:
            def at_object_creation(self):
                super().at_object_creation()
                self.setup_networked_attrs()
                self.register_acl_commands()  # Add ACL management
        """
        self.register_device_command(
            "grant",
            "handle_grant_access",
            help_text="Grant access: grant <name> <level>",
            auth_level=10  # Root only
        )
        self.register_device_command(
            "revoke",
            "handle_revoke_access",
            help_text="Revoke access: revoke <name>",
            auth_level=10  # Root only
        )

    def handle_grant_access(self, caller, *args):
        """
        Grant access to another user.

        Usage (physical): patch cmd.exe grant <person in room> <level>
        Usage (Matrix): patch cmd.exe grant <avatar name> <level>

        Args:
            caller (Character or MatrixAvatar): The character executing the command
            *args: Target name and access level

        Returns:
            bool: True on success, False on failure
        """
        if len(args) < 2:
            caller.msg("Usage: patch cmd.exe grant <name> <level>")
            caller.msg("\nLevel 1-10:")
            caller.msg("  1: Entry (basic access)")
            caller.msg("  2-3: Low access")
            caller.msg("  4-6: Medium access")
            caller.msg("  7-9: High access")
            caller.msg("  10: Root (ACL management)")
            return False

        target_name = args[0]
        try:
            level = int(args[1])
        except ValueError:
            caller.msg("|rLevel must be a number between 1 and 10.|n")
            return False

        if level < 1 or level > 10:
            caller.msg("|rLevel must be between 1 and 10.|n")
            return False

        # Determine if we're in Matrix or physical context
        from typeclasses.matrix.avatars import MatrixAvatar
        from_matrix = isinstance(caller, MatrixAvatar)

        target = None

        if from_matrix:
            # In Matrix: search for avatar by name
            from evennia.utils.search import search_object
            avatars = search_object(target_name, typeclass="typeclasses.matrix.avatars.MatrixAvatar")
            if not avatars:
                caller.msg(f"|rNo avatar found with name '{target_name}'.|n")
                return False
            if len(avatars) > 1:
                caller.msg(f"|yMultiple avatars found. Using first match: {avatars[0].key}|n")
            target = avatars[0]
            caller.msg(f"|gGranting Matrix-only access to avatar '{target.key}' at level {level}.|n")
        else:
            # Physical: search for character in same room
            if not caller.location:
                caller.msg("|rYou must be in a location to grant physical access.|n")
                return False

            target = caller.search(target_name, location=caller.location)
            if not target:
                return False

            from typeclasses.characters import Character
            if not isinstance(target, Character):
                caller.msg("|rYou can only grant access to characters.|n")
                return False

            caller.msg(f"|gGranting physical + Matrix access to '{target.key}' at level {level}.|n")

        # Add to ACL
        self.add_to_acl(target, level=level)
        caller.msg(f"|gAccess granted successfully.|n")

        # Notify target if they're online
        if target.has_account:
            target.msg(f"|yYou have been granted level {level} access to {self.key}.|n")

        return True

    def handle_revoke_access(self, caller, *args):
        """
        Open interactive menu to revoke access from users.

        Usage:
            patch cmd.exe revoke - Open ACL management menu

        Args:
            caller (Character or MatrixAvatar): The character executing the command
            *args: Unused

        Returns:
            bool: True on success
        """
        return ("node_device_acl_list", {"device": self})

    def handle_view_acl(self, caller, *args):
        """
        View the access control list.

        Usage: patch cmd.exe acl

        Args:
            caller (Character or MatrixAvatar): The character executing the command
            *args: Unused

        Returns:
            bool: Always True
        """
        acl_names = self.get_acl_names()

        caller.msg(f"|c=== Access Control List for {self.key} ===|n")
        if not acl_names:
            caller.msg("\nNo access restrictions (public device).")
        else:
            caller.msg("\nAuthorized users:")
            for name in acl_names:
                caller.msg(f"  {name}")

        caller.msg("\n|yYour access level:|n " + str(self.get_acl_level(caller)))
        return True

    # =========================================================================
    # File Storage
    # =========================================================================

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
