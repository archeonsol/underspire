"""
Matrix Items

Portable objects related to the Matrix system, both physical and virtual.

NetworkedItem - Portable physical devices with Matrix interfaces (handsets, tablets, etc.)
MatrixItem - Portable data objects in Matrix virtual space (files, credentials, keys, etc.)
Program - Executable programs run via 'exec' command in Matrix interface rooms
"""

from typeclasses.items import Item
from typeclasses.matrix.mixins import NetworkedMixin


class NetworkedItem(NetworkedMixin, Item):
    """
    Portable physical device with a Matrix interface.

    These items exist in meatspace and can be carried by characters.
    Examples: handsets, tablets, portable consoles, data chips (physical).

    Like NetworkedObject, each has an associated MatrixNode in cyberspace.
    Unlike NetworkedObject, these are portable items rather than fixed objects.

    Attributes:
        device_type (str): Type of device (handset, tablet, console, etc.)
        matrix_node (MatrixNode): The virtual room representing this device in the Matrix
        security_level (int): Security clearance required to access (0-10)
        has_storage (bool): Whether this device has file storage
        has_controls (bool): Whether this device has controllable functions
    """

    def at_object_creation(self):
        """Called when the device is first created."""
        super().at_object_creation()
        self.setup_networked_attrs()


class MatrixItem(Item):
    """
    Base class for portable data objects in Matrix virtual space.

    These items can be picked up and carried by avatars. Examples include
    data files, access credentials, encryption keys, stolen corporate data,
    programs, etc.

    Unlike MatrixObjects, these are meant to be portable and can be taken
    between Matrix locations.

    Attributes:
        data_type (str): Type of data (file, credential, key, program, etc.)
        data_size (int): Size of data in arbitrary units (affects carry capacity?)
        encryption_key (str): Encryption key ID/hash, or None if unencrypted
        value (int): Black market value or importance level
    """

    def at_object_creation(self):
        """Called when the item is first created."""
        super().at_object_creation()
        self.db.data_type = "file"
        self.db.data_size = 1
        self.db.encryption_key = None
        self.db.value = 0

    def at_get(self, getter, **kwargs):
        """
        Called when this item is picked up.

        For now, standard behavior. Future implementation could:
        - Trigger alerts when secured data is accessed
        - Check if getter has permission to access this data
        - Log the data theft
        """
        super().at_get(getter, **kwargs)

    def at_drop(self, dropper, **kwargs):
        """
        Called when this item is dropped.

        Standard behavior for now.
        """
        super().at_drop(dropper, **kwargs)


class Program(MatrixItem):
    """
    Executable program that can be run in Matrix interface rooms.

    Programs are carried by avatars and executed via 'exec <program> [args]'.
    They interact with networked devices to perform operations like file
    manipulation, device control, information gathering, etc.

    Programs can degrade with use and eventually become unusable.

    Attributes:
        program_type (str): Type of program (utility, exploit, combat, etc.)
        max_uses (int): Maximum uses before degradation (None = unlimited)
        uses_remaining (int): Current remaining uses (None = unlimited)
        quality (int): Quality level 0-10 (affects capabilities)
        execute_handler (str): Name of method to call when executed
        requires_device (bool): Whether program needs a device interface to run
    """

    def at_object_creation(self):
        """Called when the program is first created."""
        super().at_object_creation()
        self.db.data_type = "program"
        self.db.program_type = "utility"
        self.db.max_uses = None  # None = unlimited uses
        self.db.uses_remaining = None
        self.db.quality = 1  # 0-10 scale
        self.db.execute_handler = None  # Method name to call
        self.db.requires_device = True  # Most programs need a device interface

    def can_execute(self):
        """
        Check if this program can be executed.

        Returns:
            bool: True if program is usable, False if degraded/broken
        """
        if self.db.uses_remaining is not None and self.db.uses_remaining <= 0:
            return False
        return True

    def degrade(self):
        """
        Degrade the program by one use.

        Returns:
            bool: True if program is still usable, False if now broken
        """
        if self.db.uses_remaining is not None:
            self.db.uses_remaining -= 1
            return self.db.uses_remaining > 0
        return True

    def execute(self, caller, device, *args):
        """
        Execute this program.

        This is the base implementation. Subclasses or handler methods
        should override this to provide specific functionality.

        Args:
            caller (MatrixAvatar): The avatar executing the program
            device (NetworkedObject): The device being targeted
            *args: Additional arguments passed to the program

        Returns:
            bool: True if execution succeeded, False otherwise
        """
        if not self.can_execute():
            caller.msg(f"|r{self.key} is corrupted and unusable.|n")
            return False

        # If a handler method is defined, call it
        if self.db.execute_handler:
            handler = getattr(self, self.db.execute_handler, None)
            if handler and callable(handler):
                result = handler(caller, device, *args)
                if result:
                    self.degrade()
                return result

        # Default behavior - show usage
        caller.msg(f"Program: {self.key}")
        if self.db.desc:
            caller.msg(self.db.desc)
        if self.db.uses_remaining is not None:
            caller.msg(f"Uses remaining: {self.db.uses_remaining}/{self.db.max_uses}")
        return True

    def get_display_name(self, looker, **kwargs):
        """Add use count to display name if applicable."""
        name = super().get_display_name(looker, **kwargs)
        if self.db.uses_remaining is not None:
            if self.db.uses_remaining <= 0:
                return f"{name} |r[CORRUPTED]|n"
            elif self.db.uses_remaining <= 2:
                return f"{name} |y[{self.db.uses_remaining} uses]|n"
        return name


# ==============================================================================
# Example Program Implementations
# ==============================================================================


class SysInfoProgram(Program):
    """
    System information utility - displays device information.

    Usage: exec sysinfo.exe

    Does not require a device interface - can run anywhere to show info
    about the current location or targeted device.
    """

    def at_object_creation(self):
        """Initialize sysinfo program."""
        super().at_object_creation()
        self.key = "sysinfo.exe"
        self.db.program_type = "utility"
        self.db.requires_device = False  # Can run anywhere
        self.db.max_uses = None  # Unlimited uses
        self.db.desc = "System information utility. Displays device and network data."

    def execute(self, caller, device, *args):
        """Display system information."""
        if not self.can_execute():
            caller.msg(f"|r{self.key} is corrupted and unusable.|n")
            return False

        room = caller.location
        if not room:
            caller.msg("Error: Cannot determine location.")
            return False

        # Show room info
        caller.msg("|c=== System Information ===|n")
        caller.msg(f"Current Node: {room.key}")
        caller.msg(f"Node Type: {getattr(room.db, 'node_type', 'unknown')}")

        # If in a device interface, show device info
        parent_device = getattr(room.db, 'parent_object', None)
        if parent_device:
            caller.msg(f"\n|c=== Connected Device ===|n")
            caller.msg(f"Device Type: {getattr(parent_device.db, 'device_type', 'unknown')}")
            caller.msg(f"Security Level: {getattr(parent_device.db, 'security_level', 0)}")

            # Show ACL
            acl = getattr(parent_device.db, 'acl', [])
            if acl:
                caller.msg(f"ACL: {len(acl)} authorized user(s)")
            else:
                caller.msg("ACL: No access restrictions")

            # Show capabilities
            has_storage = getattr(parent_device.db, 'has_storage', False)
            has_controls = getattr(parent_device.db, 'has_controls', False)
            caller.msg(f"Storage: {'Yes' if has_storage else 'No'}")
            caller.msg(f"Controls: {'Yes' if has_controls else 'No'}")

            # Show available commands
            commands = getattr(parent_device.db, 'commands', [])
            if commands:
                caller.msg(f"\n|c=== Available Commands ===|n")
                for cmd in commands:
                    cmd_name = cmd.get('name', 'unknown')
                    cmd_help = cmd.get('help', '')
                    caller.msg(f"  {cmd_name} - {cmd_help}")

        return True


class CmdExeProgram(Program):
    """
    Command execution interface - sends commands to devices.

    Usage: exec cmd.exe <command> [args]

    Requires device interface. Executes registered commands on the device.
    """

    def at_object_creation(self):
        """Initialize cmd.exe program."""
        super().at_object_creation()
        self.key = "cmd.exe"
        self.db.program_type = "utility"
        self.db.requires_device = True
        self.db.max_uses = None  # Unlimited uses
        self.db.desc = "Command execution interface. Sends commands to connected devices."

    def execute(self, caller, device, *args):
        """Execute a device command."""
        if not self.can_execute():
            caller.msg(f"|r{self.key} is corrupted and unusable.|n")
            return False

        if not device:
            caller.msg("Error: No device connected.")
            return False

        if not args:
            # Show device information (like examine)
            caller.msg(f"|c=== {device.key} Interface ===|n")
            caller.msg(f"Device Type: {getattr(device.db, 'device_type', 'unknown')}")
            caller.msg(f"Security Level: {getattr(device.db, 'security_level', 0)}")

            # Show capabilities
            has_storage = getattr(device.db, 'has_storage', False)
            has_controls = getattr(device.db, 'has_controls', False)
            caller.msg(f"Storage: {'Yes' if has_storage else 'No'}")
            caller.msg(f"Controls: {'Yes' if has_controls else 'No'}")

            caller.msg("\nUsage: exec cmd.exe <command> [args]")
            caller.msg("Available commands depend on the device type.")
            caller.msg("Try device-specific methods like 'describe', 'pan', 'jack_out', etc.")
            return True

        # Execute the command by calling the method on the device
        command_name = args[0]
        command_args = args[1:] if len(args) > 1 else []

        # Try to get the method from the device
        handler = getattr(device, command_name, None)

        if not handler or not callable(handler):
            caller.msg(f"|y{device.key} does not support command '{command_name}'|n")
            return False

        # Call the handler
        try:
            result = handler(caller, *command_args)
            return True
        except TypeError as e:
            caller.msg(f"|rError: Invalid arguments for '{command_name}'|n")
            caller.msg(f"Details: {e}")
            return False
        except Exception as e:
            caller.msg(f"|rError executing '{command_name}': {e}|n")
            return False


class CRUDProgram(Program):
    """
    File operations program - Create, Read, Update, Delete files on devices.

    Usage:
        exec CRUD.exe ls                    - List files
        exec CRUD.exe read <filename>       - Read file contents
        exec CRUD.exe write <filename> <contents> - Write/create file
        exec CRUD.exe delete <filename>     - Delete file

    Requires device interface with storage capability.
    Limited uses - degrades with each operation.
    """

    def at_object_creation(self):
        """Initialize CRUD program."""
        super().at_object_creation()
        self.key = "CRUD.exe"
        self.db.program_type = "utility"
        self.db.requires_device = True
        self.db.max_uses = 10  # Limited uses
        self.db.uses_remaining = 10
        self.db.quality = 1
        self.db.desc = "File operations utility. Limited use - degrades with each operation."

    def execute(self, caller, device, *args):
        """Perform file operations."""
        if not self.can_execute():
            caller.msg(f"|r{self.key} is corrupted and unusable. |y[DELETE]|n")
            return False

        if not device:
            caller.msg("Error: No device connected.")
            return False

        # Check if device has storage
        if not getattr(device.db, 'has_storage', False):
            caller.msg(f"{device.key} does not have file storage capability.")
            return False

        if not args:
            caller.msg("|c=== CRUD.exe File Operations ===|n")
            caller.msg("Usage:")
            caller.msg("  exec CRUD.exe ls")
            caller.msg("  exec CRUD.exe read <filename>")
            caller.msg("  exec CRUD.exe write <filename> <contents>")
            caller.msg("  exec CRUD.exe delete <filename>")
            return True

        operation = args[0].lower()

        # Initialize storage if not present
        if not hasattr(device.db, 'storage') or device.db.storage is None:
            device.db.storage = []

        if operation in ['ls', 'list', 'dir']:
            # List files
            files = device.db.storage
            if not files:
                caller.msg("No files on device.")
            else:
                caller.msg(f"|c=== Files on {device.key} ===|n")
                for f in files:
                    filename = f.get('filename', 'unknown')
                    filetype = f.get('filetype', 'unknown')
                    size = len(f.get('contents', ''))
                    caller.msg(f"  {filename} ({filetype}, {size} bytes)")
            self.degrade()
            if self.db.uses_remaining and self.db.uses_remaining > 0:
                caller.msg(f"|y[CRUD.exe: {self.db.uses_remaining} uses remaining]|n")
            return True

        elif operation in ['read', 'cat', 'view']:
            # Read file
            if len(args) < 2:
                caller.msg("Usage: exec CRUD.exe read <filename>")
                return False

            filename = args[1]
            file_obj = next((f for f in device.db.storage if f.get('filename') == filename), None)

            if not file_obj:
                caller.msg(f"File not found: {filename}")
                return False

            caller.msg(f"|c=== {filename} ===|n")
            caller.msg(file_obj.get('contents', '[empty]'))
            self.degrade()
            if self.db.uses_remaining and self.db.uses_remaining > 0:
                caller.msg(f"|y[CRUD.exe: {self.db.uses_remaining} uses remaining]|n")
            return True

        elif operation in ['write', 'create', 'edit']:
            # Write/create file
            if len(args) < 3:
                caller.msg("Usage: exec CRUD.exe write <filename> <contents>")
                return False

            filename = args[1]
            contents = ' '.join(args[2:])

            # Check if file exists
            file_obj = next((f for f in device.db.storage if f.get('filename') == filename), None)

            if file_obj:
                # Update existing
                file_obj['contents'] = contents
                caller.msg(f"File updated: {filename}")
            else:
                # Create new
                device.db.storage.append({
                    'filename': filename,
                    'filetype': 'text',
                    'contents': contents
                })
                caller.msg(f"File created: {filename}")

            self.degrade()
            if self.db.uses_remaining and self.db.uses_remaining > 0:
                caller.msg(f"|y[CRUD.exe: {self.db.uses_remaining} uses remaining]|n")
            return True

        elif operation in ['delete', 'rm', 'remove']:
            # Delete file
            if len(args) < 2:
                caller.msg("Usage: exec CRUD.exe delete <filename>")
                return False

            filename = args[1]
            file_obj = next((f for f in device.db.storage if f.get('filename') == filename), None)

            if not file_obj:
                caller.msg(f"File not found: {filename}")
                return False

            device.db.storage.remove(file_obj)
            caller.msg(f"File deleted: {filename}")
            self.degrade()
            if self.db.uses_remaining and self.db.uses_remaining > 0:
                caller.msg(f"|y[CRUD.exe: {self.db.uses_remaining} uses remaining]|n")
            return True

        else:
            caller.msg(f"Unknown operation: {operation}")
            caller.msg("Valid operations: ls, read, write, delete")
            return False


class SkeletonKeyProgram(Program):
    """
    ACL manipulation program - adds/removes users from device access control lists.

    Usage:
        exec Skeleton.key list              - Show current ACL
        exec Skeleton.key add <name>        - Add user to ACL
        exec Skeleton.key remove <name>     - Remove user from ACL

    Requires device interface. Illegal software - high black market value.
    Limited uses.
    """

    def at_object_creation(self):
        """Initialize Skeleton.key program."""
        super().at_object_creation()
        self.key = "Skeleton.key"
        self.db.program_type = "exploit"
        self.db.requires_device = True
        self.db.max_uses = 5  # Very limited uses
        self.db.uses_remaining = 5
        self.db.quality = 3
        self.db.value = 500  # High black market value
        self.db.desc = "ACL manipulation utility. Highly illegal. Limited uses."

    def execute(self, caller, device, *args):
        """Manipulate device ACL."""
        if not self.can_execute():
            caller.msg(f"|r{self.key} is corrupted and unusable. |y[DELETE]|n")
            return False

        if not device:
            caller.msg("Error: No device connected.")
            return False

        # Initialize ACL if not present
        if not hasattr(device.db, 'acl') or device.db.acl is None:
            device.db.acl = []

        if not args:
            caller.msg("|c=== Skeleton.key ACL Editor ===|n")
            caller.msg("Usage:")
            caller.msg("  exec Skeleton.key list")
            caller.msg("  exec Skeleton.key add <character_name>")
            caller.msg("  exec Skeleton.key remove <character_name>")
            return True

        operation = args[0].lower()

        if operation in ['list', 'show', 'ls']:
            # Show ACL
            if not device.db.acl:
                caller.msg(f"{device.key} has no ACL restrictions.")
            else:
                caller.msg(f"|c=== ACL for {device.key} ===|n")
                # TODO: Convert dbrefs to names
                for dbref in device.db.acl:
                    caller.msg(f"  User #{dbref}")
            return True

        elif operation in ['add', 'grant']:
            # Add to ACL
            if len(args) < 2:
                caller.msg("Usage: exec Skeleton.key add <character_name>")
                return False

            # TODO: Look up character by name and get dbref
            # For now, just acknowledge
            char_name = args[1]
            caller.msg(f"|yAdding {char_name} to ACL...|n")
            caller.msg("|r[Not yet implemented - character lookup pending]|n")
            # device.db.acl.append(character.pk)
            self.degrade()
            if self.db.uses_remaining and self.db.uses_remaining > 0:
                caller.msg(f"|y[Skeleton.key: {self.db.uses_remaining} uses remaining]|n")
            return True

        elif operation in ['remove', 'revoke', 'rm']:
            # Remove from ACL
            if len(args) < 2:
                caller.msg("Usage: exec Skeleton.key remove <character_name>")
                return False

            # TODO: Look up character and remove from ACL
            char_name = args[1]
            caller.msg(f"|yRemoving {char_name} from ACL...|n")
            caller.msg("|r[Not yet implemented - character lookup pending]|n")
            self.degrade()
            if self.db.uses_remaining and self.db.uses_remaining > 0:
                caller.msg(f"|y[Skeleton.key: {self.db.uses_remaining} uses remaining]|n")
            return True

        else:
            caller.msg(f"Unknown operation: {operation}")
            caller.msg("Valid operations: list, add, remove")
            return False


class ICEpickProgram(Program):
    """
    Combat utility program for fighting ICE in the Matrix.

    Usage: exec ICEpick.exe <target>

    Does not require device interface - combat utility usable anywhere.
    Provides bonus damage or special attacks against ICE.
    """

    def at_object_creation(self):
        """Initialize ICEpick program."""
        super().at_object_creation()
        self.key = "ICEpick.exe"
        self.db.program_type = "combat"
        self.db.requires_device = False  # Can use anywhere
        self.db.max_uses = 20  # Limited uses in combat
        self.db.uses_remaining = 20
        self.db.quality = 2
        self.db.desc = "ICE combat utility. Provides offensive capabilities against security programs."

    def execute(self, caller, device, *args):
        """Use ICEpick in combat."""
        if not self.can_execute():
            caller.msg(f"|r{self.key} is corrupted and unusable. |y[DELETE]|n")
            return False

        if not args:
            caller.msg("|c=== ICEpick.exe Combat Utility ===|n")
            caller.msg("Usage: exec ICEpick.exe <target>")
            caller.msg("\nProvides offensive capabilities against ICE and security programs.")
            caller.msg("Must be used during combat.")
            return True

        target_name = ' '.join(args)

        # TODO: Implement combat system integration
        caller.msg(f"|yExecuting ICEpick attack on {target_name}...|n")
        caller.msg("|r[Not yet implemented - combat system pending]|n")

        # This would integrate with the combat system when implemented
        self.degrade()
        if self.db.uses_remaining and self.db.uses_remaining > 0:
            caller.msg(f"|y[ICEpick.exe: {self.db.uses_remaining} uses remaining]|n")
        return True


class ExfilProgram(Program):
    """
    Data exfiltration program - extracts files from device storage to portable data items.

    Usage:
        exec exfil.exe <filename>

    Converts a file from device storage into a physical MatrixItem that can be
    carried in your inventory. This allows you to steal data from corporate
    datastores and carry it out of the Matrix.

    Requires device interface with storage capability.
    Limited uses - highly illegal software.
    """

    def at_object_creation(self):
        """Initialize exfil.exe program."""
        super().at_object_creation()
        self.key = "exfil.exe"
        self.db.program_type = "exploit"
        self.db.requires_device = True
        self.db.max_uses = 8  # Limited uses
        self.db.uses_remaining = 8
        self.db.quality = 2
        self.db.value = 300  # Illegal software, moderate value
        self.db.desc = "Data exfiltration utility. Converts device files to portable data items. Illegal."

    def execute(self, caller, device, *args):
        """Extract file to portable data item."""
        if not self.can_execute():
            caller.msg(f"|r{self.key} is corrupted and unusable. |y[DELETE]|n")
            return False

        if not device:
            caller.msg("Error: No device connected.")
            return False

        # Check if device has storage
        if not getattr(device.db, 'has_storage', False):
            caller.msg(f"{device.key} does not have file storage capability.")
            return False

        if not args:
            caller.msg("|c=== exfil.exe Data Exfiltration ===|n")
            caller.msg("Usage: exec exfil.exe <filename>")
            caller.msg("\nExtracts a file from device storage and converts it to a")
            caller.msg("portable data item in your inventory.")
            return True

        filename = args[0]

        # Initialize storage if not present
        if not hasattr(device.db, 'storage') or device.db.storage is None:
            device.db.storage = []

        # Find the file
        file_obj = next((f for f in device.db.storage if f.get('filename') == filename), None)

        if not file_obj:
            caller.msg(f"File not found: {filename}")
            return False

        # Create a MatrixItem with the file data
        from evennia.utils.create import create_object

        data_item = create_object(
            MatrixItem,
            key=f"data chip: {filename}",
            location=caller
        )

        if not data_item:
            caller.msg("|rError creating data item.|n")
            return False

        # Store file data in the item
        data_item.db.data_type = "file_chip"
        data_item.db.file_data = {
            'filename': file_obj.get('filename'),
            'filetype': file_obj.get('filetype', 'unknown'),
            'contents': file_obj.get('contents', '')
        }
        data_item.db.data_size = len(file_obj.get('contents', ''))
        data_item.db.desc = f"A data chip containing '{filename}' ({data_item.db.data_size} bytes)."

        caller.msg(f"|gExfiltration successful!|n")
        caller.msg(f"File '{filename}' converted to portable data chip.")

        self.degrade()
        if self.db.uses_remaining and self.db.uses_remaining > 0:
            caller.msg(f"|y[exfil.exe: {self.db.uses_remaining} uses remaining]|n")

        return True


class InfilProgram(Program):
    """
    Data infiltration program - uploads portable data items to device storage.

    Usage:
        exec infil.exe <data_item_name>

    Converts a MatrixItem (data chip) in your inventory into a file on the
    device's storage. Useful for planting false data, uploading malware,
    or transferring stolen files between systems.

    Requires device interface with storage capability.
    Limited uses.
    """

    def at_object_creation(self):
        """Initialize infil.exe program."""
        super().at_object_creation()
        self.key = "infil.exe"
        self.db.program_type = "utility"
        self.db.requires_device = True
        self.db.max_uses = 10  # More uses than exfil (uploading is easier)
        self.db.uses_remaining = 10
        self.db.quality = 2
        self.db.value = 150
        self.db.desc = "Data infiltration utility. Uploads data items to device storage."

    def execute(self, caller, device, *args):
        """Upload data item to device storage."""
        if not self.can_execute():
            caller.msg(f"|r{self.key} is corrupted and unusable. |y[DELETE]|n")
            return False

        if not device:
            caller.msg("Error: No device connected.")
            return False

        # Check if device has storage
        if not getattr(device.db, 'has_storage', False):
            caller.msg(f"{device.key} does not have file storage capability.")
            return False

        if not args:
            caller.msg("|c=== infil.exe Data Infiltration ===|n")
            caller.msg("Usage: exec infil.exe <data_item_name>")
            caller.msg("\nUploads a data item from your inventory to device storage.")

            # Show available data items
            data_items = [obj for obj in caller.contents
                         if isinstance(obj, MatrixItem) and obj.db.data_type == "file_chip"]
            if data_items:
                caller.msg("\nAvailable data items:")
                for item in data_items:
                    caller.msg(f"  {item.key}")
            else:
                caller.msg("\nYou have no data items to upload.")

            return True

        item_name = ' '.join(args)

        # Find the data item in inventory
        data_item = None
        for obj in caller.contents:
            if isinstance(obj, MatrixItem) and obj.key.lower() == item_name.lower():
                data_item = obj
                break

        if not data_item:
            caller.msg(f"You don't have a data item called '{item_name}'.")
            return False

        # Check if it's a file chip
        if data_item.db.data_type != "file_chip":
            caller.msg(f"{data_item.key} is not a file data chip.")
            return False

        # Get file data from the item
        file_data = getattr(data_item.db, 'file_data', None)
        if not file_data:
            caller.msg(f"{data_item.key} contains no file data.")
            return False

        # Initialize storage if not present
        if not hasattr(device.db, 'storage') or device.db.storage is None:
            device.db.storage = []

        # Check if file already exists
        filename = file_data.get('filename', 'unknown')
        existing = next((f for f in device.db.storage if f.get('filename') == filename), None)

        if existing:
            caller.msg(f"|yWarning: File '{filename}' already exists. Overwriting.|n")
            device.db.storage.remove(existing)

        # Upload the file
        device.db.storage.append({
            'filename': file_data.get('filename'),
            'filetype': file_data.get('filetype', 'unknown'),
            'contents': file_data.get('contents', '')
        })

        caller.msg(f"|gInfiltration successful!|n")
        caller.msg(f"File '{filename}' uploaded to device storage.")
        caller.msg(f"|yData item '{data_item.key}' consumed.|n")

        # Delete the data item (it's been uploaded)
        data_item.delete()

        self.degrade()
        if self.db.uses_remaining and self.db.uses_remaining > 0:
            caller.msg(f"|y[infil.exe: {self.db.uses_remaining} uses remaining]|n")

        return True
