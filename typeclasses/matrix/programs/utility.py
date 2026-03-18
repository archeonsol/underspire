"""
Utility Programs

General-purpose programs for information gathering and device interaction.
"""

from typeclasses.matrix.programs.base import Program


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
            acl_names = parent_device.get_acl_names()
            if acl_names:
                caller.msg(f"ACL: {len(acl_names)} authorized user(s)")
            else:
                caller.msg("ACL: No access restrictions")

            # Show capabilities
            has_storage = getattr(parent_device.db, 'has_storage', False)
            has_controls = getattr(parent_device.db, 'has_controls', False)
            caller.msg(f"Storage: {'Yes' if has_storage else 'No'}")
            caller.msg(f"Controls: {'Yes' if has_controls else 'No'}")

            # Show available commands
            available_commands = parent_device.get_available_commands()
            if available_commands:
                caller.msg(f"\n|c=== Available Commands ===|n")
                for cmd_name, cmd_help in available_commands.items():
                    caller.msg(f"  {cmd_name} - {cmd_help}")

        return True


class CmdExeProgram(Program):
    """
    Command execution interface - opens interactive menu to control devices.

    Usage: patch cmd.exe

    Opens an EvMenu interface for interacting with the connected device.
    Can run anywhere but requires a device interface to be useful.
    """

    def at_object_creation(self):
        """Initialize cmd.exe program."""
        super().at_object_creation()
        self.key = "cmd.exe"
        self.db.program_type = "utility"
        self.db.requires_device = False  # Can run anywhere, checks for device in execute
        self.db.max_uses = None  # Unlimited uses
        self.db.desc = "Command execution interface. Opens interactive menu for device control."

    def execute(self, caller, device, *args):
        """Launch device control menu."""
        if not self.can_execute():
            caller.msg(f"|r{self.key} is corrupted and unusable.|n")
            return False

        if not device:
            caller.msg("Error: No device connected. You must be in a device interface room.")
            return False

        # Launch the device menu
        from typeclasses.matrix.device_menu import start_device_menu
        start_device_menu(caller, device, from_matrix=True)

        return True


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
        self.db.requires_device = False  # Can run anywhere, checks for device in execute
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
        if not device.db.has_storage:
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

        if operation in ['ls', 'list', 'dir']:
            # List files
            files = device.list_files()
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
            file_obj = device.get_file(filename)

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

            # Try to update existing file first
            if device.update_file(filename, contents):
                caller.msg(f"File updated: {filename}")
            else:
                # Create new file
                if device.add_file(filename, 'text', contents):
                    caller.msg(f"File created: {filename}")
                else:
                    caller.msg(f"|rFailed to create file: {filename}|n")
                    return False

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

            if device.delete_file(filename):
                caller.msg(f"File deleted: {filename}")
            else:
                caller.msg(f"File not found: {filename}")
                return False

            self.degrade()
            if self.db.uses_remaining and self.db.uses_remaining > 0:
                caller.msg(f"|y[CRUD.exe: {self.db.uses_remaining} uses remaining]|n")
            return True

        else:
            caller.msg(f"Unknown operation: {operation}")
            caller.msg("Valid operations: ls, read, write, delete")
            return False
