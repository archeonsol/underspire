"""
Device Interface Menu

EvMenu-based interface for interacting with networked devices.
Can be accessed from meatspace (via 'operate' command) or from Matrix (via 'patch cmd.exe').
"""

from evennia import EvMenu
from evennia.utils.evtable import EvTable


def device_main_menu(caller, raw_string, **kwargs):
    """
    Main menu for device interaction.

    Shows device info and available commands.
    """
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    if not device:
        return "node_error", kwargs

    # Build menu text
    text = f"|c=== {device.key} Interface ===|n\n\n"
    text += f"Device Type: {getattr(device.db, 'device_type', 'unknown')}\n"
    text += f"Security Level: {getattr(device.db, 'security_level', 0)}\n"

    # Show capabilities
    has_storage = getattr(device.db, 'has_storage', False)
    has_controls = getattr(device.db, 'has_controls', False)
    text += f"Storage: {'Yes' if has_storage else 'No'}\n"
    text += f"Controls: {'Yes' if has_controls else 'No'}\n"

    # Check ACL authorization
    is_authorized = device.check_acl(caller)
    if is_authorized:
        text += "\n|gYou are authorized on this device's ACL.|n\n"
    else:
        text += "\n|yYou are NOT authorized on this device's ACL.|n\n"

    # Build options dict
    options = []

    # Get available commands from device (filtered by skill and access)
    available_commands = device.get_available_commands(caller, from_matrix)
    if available_commands:
        text += "\n|wAvailable Commands:|n\n"
        for i, (cmd_name, cmd_help) in enumerate(available_commands.items(), 1):
            text += f"  {i}. |y{cmd_name}|n - {cmd_help}\n"
            options.append({
                "key": str(i),
                "desc": cmd_name,
                "goto": ("node_execute_command", {"device": device, "command": cmd_name, "from_matrix": from_matrix})
            })

    # Storage browsing if available
    if has_storage:
        options.append({
            "key": "f",
            "desc": "Browse files",
            "goto": ("node_browse_files", {"device": device, "from_matrix": from_matrix})
        })

    # ACL management if authorized or via exploit
    options.append({
        "key": "a",
        "desc": "View ACL",
        "goto": ("node_view_acl", {"device": device, "from_matrix": from_matrix})
    })

    options.append({
        "key": "q",
        "desc": "Exit interface",
        "goto": "node_exit"
    })

    return text, options


def node_execute_command(caller, raw_string, **kwargs):
    """
    Execute a device command, prompting for arguments if needed.
    """
    device = kwargs.get("device")
    command = kwargs.get("command")
    from_matrix = kwargs.get("from_matrix", False)

    if not device or not command:
        return "node_error", kwargs

    text = f"|c=== Execute: {command} ===|n\n\n"
    text += "Enter command arguments (or 'back' to cancel):\n"

    options = {
        "key": "_default",
        "goto": ("node_process_command", {"device": device, "command": command, "from_matrix": from_matrix})
    }

    return text, options


def node_process_command(caller, raw_string, **kwargs):
    """
    Process the command with provided arguments.
    """
    device = kwargs.get("device")
    command = kwargs.get("command")
    from_matrix = kwargs.get("from_matrix", False)

    if not device or not command:
        return "node_error", kwargs

    if raw_string.strip().lower() == "back":
        return "device_main_menu", {"device": device, "from_matrix": from_matrix}

    # Parse arguments
    args = raw_string.strip().split() if raw_string.strip() else []

    # Execute the command via device framework
    success = device.invoke_device_command(command, caller, from_matrix, *args)

    text = "\n|gCommand executed.|n\n" if success else "\n|rCommand failed.|n\n"
    text += "\nPress any key to return to main menu."

    options = {
        "key": "_default",
        "goto": ("device_main_menu", {"device": device, "from_matrix": from_matrix})
    }

    return text, options


def node_browse_files(caller, raw_string, **kwargs):
    """
    Browse files on device storage.
    """
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)

    if not device or not device.db.has_storage:
        return "node_error", kwargs

    files = device.list_files()

    text = f"|c=== Files on {device.key} ===|n\n\n"

    if not files:
        text += "No files on device.\n\n"
    else:
        # Create table
        table = EvTable("Filename", "Type", "Size", border="cells")
        for f in files:
            filename = f.get('filename', 'unknown')
            filetype = f.get('filetype', 'unknown')
            size = len(f.get('contents', ''))
            table.add_row(filename, filetype, f"{size} bytes")
        text += str(table) + "\n\n"

    options = [
        {
            "key": "r",
            "desc": "Read a file",
            "goto": ("node_read_file_prompt", {"device": device, "from_matrix": from_matrix})
        },
        {
            "key": "b",
            "desc": "Back to main menu",
            "goto": ("device_main_menu", {"device": device, "from_matrix": from_matrix})
        }
    ]

    return text, options


def node_read_file_prompt(caller, raw_string, **kwargs):
    """
    Prompt for filename to read.
    """
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)

    text = "|c=== Read File ===|n\n\n"
    text += "Enter filename to read (or 'back' to cancel):\n"

    options = {
        "key": "_default",
        "goto": ("node_read_file", {"device": device, "from_matrix": from_matrix})
    }

    return text, options


def node_read_file(caller, raw_string, **kwargs):
    """
    Read and display a file.
    """
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)

    if raw_string.strip().lower() == "back":
        return _browse_files(caller, "", **kwargs)

    filename = raw_string.strip()
    file_obj = device.get_file(filename)

    if not file_obj:
        text = f"|rFile not found: {filename}|n\n\n"
        text += "Press any key to return to file browser."
    else:
        text = f"|c=== {filename} ===|n\n\n"
        text += file_obj.get('contents', '[empty]')
        text += "\n\nPress any key to return to file browser."

    options = {
        "key": "_default",
        "goto": ("node_browse_files", {"device": device, "from_matrix": from_matrix})
    }

    return text, options


def node_view_acl(caller, raw_string, **kwargs):
    """
    View device ACL.
    """
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)

    acl_names = device.get_acl_names()

    text = f"|c=== ACL for {device.key} ===|n\n\n"

    if not acl_names:
        text += "No access restrictions (public device).\n\n"
    else:
        text += "Authorized users:\n"
        for name in acl_names:
            text += f"  - {name}\n"
        text += "\n"

    options = [
        {
            "key": "b",
            "desc": "Back to main menu",
            "goto": ("device_main_menu", {"device": device, "from_matrix": from_matrix})
        }
    ]

    return text, options


def node_error(caller, raw_string, **kwargs):
    """Error state - device not found or invalid."""
    text = "|rError: Device interface unavailable.|n\n"
    return text, {"key": "_default", "goto": "node_exit"}


def node_exit(caller, raw_string, **kwargs):
    """Exit the menu."""
    caller.msg("Disconnecting from device interface.")
    return None, None


def start_device_menu(caller, device, from_matrix=False):
    """
    Start the device interface menu.

    Args:
        caller: The character/avatar accessing the device
        device: The networked device being accessed
        from_matrix: True if accessed via cmd.exe in Matrix, False if from meatspace
    """
    if not device:
        caller.msg("|rError: No device specified.|n")
        return

    # Store context
    menu_data = {
        "device": device,
        "from_matrix": from_matrix
    }

    from typeclasses.matrix.menu_formatters import get_matrix_formatters
    EvMenu(
        caller,
        "typeclasses.matrix.device_menu",
        startnode="device_main_menu",
        startnode_input=("", menu_data),
        cmd_on_exit=None,
        persistent=False,
        **get_matrix_formatters(),
        **menu_data
    )
