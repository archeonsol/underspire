"""
Matrix Commands

Commands for interacting with the Matrix system.

CmdJackIn - Jack into the Matrix through a dive rig
CmdJackOut - Disconnect from the Matrix
CmdExec - Execute a program in a Matrix interface room
CmdRoute - Navigate router networks to connected devices
"""

from evennia import Command
from typeclasses.matrix.devices import DiveRig
from typeclasses.matrix.avatars import JACKOUT_NORMAL
from typeclasses.matrix.objects import Router, NetworkedObject


class CmdJackIn(Command):
    """
    Jack into the Matrix through a dive rig.

    Usage:
        jack in

    You must be sitting in a dive rig to use this command.
    Your consciousness will transfer to your Matrix avatar while your
    body remains vulnerable in meatspace.
    """

    key = "jack in"
    aliases = ["jackin"]
    locks = "cmd:all()"
    help_category = "Matrix"

    def func(self):
        caller = self.caller

        # Check if sitting on anything
        sitting_on = caller.db.sitting_on
        if not sitting_on:
            caller.msg("You must be sitting in a dive rig first.")
            return

        # Check if it's a dive rig
        if not isinstance(sitting_on, DiveRig):
            caller.msg("You can only jack in from a dive rig.")
            return

        # Attempt to jack in
        success = sitting_on.jack_in(caller)
        if not success:
            # Error messages are handled by jack_in()
            return


class CmdJackOut(Command):
    """
    Disconnect from the Matrix and return to your body.

    Usage:
        jack out

    Cleanly disconnects you from the Matrix and returns you to your body.

    Note: Cannot jack out during combat or other restricted situations.
    """

    key = "jack out"
    aliases = ["jackout"]
    locks = "cmd:all()"
    help_category = "Matrix"

    def func(self):
        caller = self.caller

        # Check if caller is a Matrix avatar
        from typeclasses.matrix.avatars import MatrixAvatar
        if not isinstance(caller, MatrixAvatar):
            caller.msg("You are not jacked into the Matrix.")
            return

        # Check if we have an entry device (the rig)
        entry_device = caller.db.entry_device
        if not entry_device:
            caller.msg("Error: Cannot locate your dive rig connection.")
            return

        # Get character from rig's active connection
        conn = entry_device.db.active_connection
        if not conn:
            caller.msg("Error: No active connection found.")
            return

        character = conn.get('character')
        if not character:
            caller.msg("Error: Cannot locate your physical body.")
            return

        # TODO: Check for combat or other restrictions
        # if caller.db.in_combat:
        #     caller.msg("You cannot jack out during combat!")
        #     return

        # Perform clean logout via the rig
        entry_device.disconnect(
            character,
            severity=JACKOUT_NORMAL,
            reason="Logging out"
        )


class CmdExec(Command):
    """
    Execute a program in a Matrix interface room.

    Usage:
        exec <program> [arguments]

    Runs an executable program from your inventory, targeting the device
    whose interface room you are currently in. Different programs provide
    different capabilities:

    Examples:
        exec sysinfo.exe           - Display device information
        exec cmd.exe describe A sleek virtual lounge
        exec CRUD.exe ls           - List files on device
        exec CRUD.exe read passwords.txt

    Programs may have limited uses and degrade with each execution.
    """

    key = "exec"
    aliases = ["execute", "run"]
    locks = "cmd:all()"
    help_category = "Matrix"

    def func(self):
        caller = self.caller

        # Check if caller is a Matrix avatar
        from typeclasses.matrix.avatars import MatrixAvatar
        if not isinstance(caller, MatrixAvatar):
            caller.msg("You must be in the Matrix to execute programs.")
            return

        # Parse arguments
        if not self.args:
            caller.msg("Usage: exec <program> [arguments]")
            return

        args = self.args.split()
        program_name = args[0]
        program_args = args[1:] if len(args) > 1 else []

        # Find the program in inventory
        from typeclasses.matrix.items import Program
        programs = [obj for obj in caller.contents if isinstance(obj, Program)]

        # Match by key (case-insensitive)
        program = None
        for prog in programs:
            if prog.key.lower() == program_name.lower():
                program = prog
                break

        if not program:
            caller.msg(f"You don't have a program called '{program_name}'.")
            caller.msg(f"Your programs: {', '.join([p.key for p in programs]) if programs else 'none'}")
            return

        # Check if program requires a device interface
        parent_device = None
        if program.db.requires_device:
            room = caller.location
            if not room:
                caller.msg("You are nowhere. This shouldn't happen.")
                return

            # Check if room has a parent device
            parent_device = getattr(room.db, 'parent_object', None)
            if not parent_device:
                caller.msg(f"{program.key} requires a device interface to run.")
                return

        # Execute the program (device may be None for utility programs)
        program.execute(caller, parent_device, *program_args)


class CmdRoute(Command):
    """
    Navigate the router network to connected devices and locations.

    Usage:
        route              - Show usage help
        route list         - List all connected cells (locations)
        route list <cell>  - List devices in a specific cell
        route connect <device> - Connect to a device's interface

    The router acts as a network hub, showing all devices connected through
    it across different physical locations (cells). You can navigate to any
    device's Matrix interface from the router console.

    Examples:
        route list
        route list Downtown Sector Alpha
        route connect Hub #1247
        route connect camera
    """

    key = "route"
    locks = "cmd:all()"
    help_category = "Matrix"

    def func(self):
        caller = self.caller

        # Check if caller is a Matrix avatar
        from typeclasses.matrix.avatars import MatrixAvatar
        if not isinstance(caller, MatrixAvatar):
            caller.msg("You must be in the Matrix to use the router.")
            return

        # Check if there's a router in the room
        room = caller.location
        if not room:
            caller.msg("You are nowhere. This shouldn't happen.")
            return

        router = None
        for obj in room.contents:
            if isinstance(obj, Router):
                router = obj
                break

        if not router:
            caller.msg("There is no router here.")
            return

        # Parse arguments
        if not self.args.strip():
            # Show usage
            caller.msg("|c=== Router Console ===|n")
            caller.msg(f"Connected to: {router.key}")
            caller.msg(f"Status: {router.get_status()}\n")
            caller.msg("Usage:")
            caller.msg("  route list             - Show connected cells")
            caller.msg("  route list <cell>      - Show devices in cell")
            caller.msg("  route connect <device> - Connect to device")
            return

        args = self.args.strip().split(None, 1)
        subcommand = args[0].lower()

        if subcommand == "list":
            # List cells or devices in a cell
            if len(args) == 1:
                # List all cells
                self.list_cells(caller, router)
            else:
                # List devices in specific cell
                cell_name = args[1]
                self.list_devices_in_cell(caller, router, cell_name)

        elif subcommand == "connect":
            # Connect to a device
            if len(args) < 2:
                caller.msg("Usage: route connect <device>")
                return
            device_name = args[1]
            self.connect_to_device(caller, router, device_name)

        else:
            caller.msg(f"Unknown subcommand: {subcommand}")
            caller.msg("Valid subcommands: list, connect")

    def list_cells(self, caller, router):
        """List all cells (locations) connected to this router."""
        from evennia.utils.search import search_object

        cells = {}  # cell_name -> [devices]

        # Find all rooms that reference this router
        # For now, search all rooms and check their network_router attribute
        # TODO: Optimize by maintaining linked_rooms on router
        from typeclasses.rooms import Room
        all_rooms = Room.objects.all()

        for room in all_rooms:
            router_dbref = getattr(room.db, 'network_router', None)
            if router_dbref == router.pk:
                cell_name = getattr(room.db, 'cell_name', room.key)

                # Get devices in this room
                devices = [obj for obj in room.contents if isinstance(obj, NetworkedObject)]

                if devices:
                    if cell_name not in cells:
                        cells[cell_name] = []
                    cells[cell_name].extend(devices)

        if not cells:
            caller.msg("|c=== Router Network ===|n")
            caller.msg("No cells connected to this router.")
            return

        caller.msg("|c=== Router Network ===|n")
        caller.msg(f"Connected Cells:\n")
        for cell_name, devices in sorted(cells.items()):
            caller.msg(f"  {cell_name} ({len(devices)} device{'s' if len(devices) != 1 else ''})")

        caller.msg("\nUse 'route list <cell>' to see devices in a cell.")

    def list_devices_in_cell(self, caller, router, cell_name):
        """List all devices in a specific cell."""
        from typeclasses.rooms import Room
        all_rooms = Room.objects.all()

        # Find devices in matching cell
        devices = []
        actual_cell_name = None

        for room in all_rooms:
            router_dbref = getattr(room.db, 'network_router', None)
            if router_dbref == router.pk:
                room_cell_name = getattr(room.db, 'cell_name', room.key)

                # Match cell name (case-insensitive partial match)
                if cell_name.lower() in room_cell_name.lower():
                    actual_cell_name = room_cell_name
                    room_devices = [obj for obj in room.contents if isinstance(obj, NetworkedObject)]
                    devices.extend(room_devices)

        if not devices:
            caller.msg(f"No devices found in cell matching '{cell_name}'.")
            return

        caller.msg(f"|c=== {actual_cell_name} ===|n")
        caller.msg(f"{len(devices)} device{'s' if len(devices) != 1 else ''}:\n")

        for i, device in enumerate(devices, 1):
            device_type = getattr(device.db, 'device_type', 'unknown')
            security = getattr(device.db, 'security_level', 0)
            caller.msg(f"  {i}. {device.key} ({device_type}, security: {security})")

        caller.msg("\nUse 'route connect <device>' to connect to a device.")

    def connect_to_device(self, caller, router, device_name):
        """Connect caller to a device's vestibule."""
        from typeclasses.rooms import Room
        from evennia.utils.search import search_object

        # Find the device
        all_rooms = Room.objects.all()
        found_device = None

        for room in all_rooms:
            router_dbref = getattr(room.db, 'network_router', None)
            if router_dbref == router.pk:
                for obj in room.contents:
                    if isinstance(obj, NetworkedObject):
                        # Match device name (case-insensitive partial match)
                        if device_name.lower() in obj.key.lower():
                            found_device = obj
                            break
                if found_device:
                    break

        if not found_device:
            caller.msg(f"Device '{device_name}' not found on this network.")
            return

        # Get or create the device cluster
        cluster = found_device.get_or_create_cluster()
        if not cluster:
            caller.msg(f"|rError: Could not establish connection to {found_device.key}.|n")
            return

        vestibule = cluster.get('vestibule')
        if not vestibule:
            caller.msg(f"|rError: Device interface unavailable.|n")
            return

        # Move to vestibule
        caller.msg(f"|cEstablishing connection to {found_device.key}...|n")
        caller.move_to(vestibule, quiet=True)
        caller.execute_cmd("look")
