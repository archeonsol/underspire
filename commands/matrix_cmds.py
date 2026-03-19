"""
Matrix Commands

Commands for interacting with the Matrix system.

CmdJackIn - Jack into the Matrix through a dive rig
CmdJackOut - Disconnect from the Matrix
CmdExec - Execute a program in a Matrix interface room
CmdRoute - Navigate router networks to connected devices via menu
"""

from evennia import Command
from evennia.utils.evmenu import EvMenu
from typeclasses.matrix.devices import DiveRig
from typeclasses.matrix.avatars import JACKOUT_NORMAL
from typeclasses.matrix.objects import Router, NetworkedObject

# Admin lock for builder/admin commands
ADMIN_LOCK = "cmd:perm(Builder) or perm(Admin)"


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


class CmdPatch(Command):
    """
    Patch a program into a Matrix node.

    Usage:
        patch <program> [arguments]

    Runs an executable program from your inventory, patching it into the
    current node. Different programs provide different capabilities:

    Examples:
        patch sysinfo.exe           - Display device information
        patch cmd.exe               - Open device control menu
        patch CRUD.exe ls           - List files on device
        patch CRUD.exe read passwords.txt

    Programs may have limited uses and degrade with each execution.
    """

    key = "patch"
    aliases = []
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
            caller.msg("Usage: patch <program> [arguments]")
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

        # Get device from room if in an interface
        room = caller.location
        if not room:
            caller.msg("You are nowhere. This shouldn't happen.")
            return

        parent_device = getattr(room.db, 'parent_object', None)

        # Execute the program (device may be None - program decides if it needs one)
        program.execute(caller, parent_device, *program_args)


class CmdRoute(Command):
    """
    Navigate the router network to connected devices via menu.

    Usage:
        route via <router>
        route back

    route via <router> - Opens an interactive menu showing all access points (rooms)
                         connected to the specified router. You can browse devices
                         in each access point and connect to their Matrix interface.

    route back - Exit a device interface and return to the router that device is
                 currently connected to. Works from checkpoint or interface rooms.

    Examples:
        route via Cortex Router
        route via downtown_router
        route back
    """

    key = "route"
    locks = "cmd:all()"
    help_category = "Matrix"

    def func(self):
        caller = self.caller

        # Check if caller is a Matrix avatar
        from typeclasses.matrix.avatars import MatrixAvatar
        if not isinstance(caller, MatrixAvatar):
            caller.msg("You must be in the Matrix to use routers.")
            return

        if not self.args.strip():
            caller.msg("Usage: route via <router> | route back")
            return

        # Parse command
        args = self.args.strip().lower()

        # Handle "route back" - exit device interface
        if args in ("back", "exit", "return"):
            self.route_back(caller)
            return

        # Parse "via <router>" syntax
        if args.startswith("via "):
            router_name = args[4:].strip()
        else:
            router_name = args

        if not router_name:
            caller.msg("Usage: route via <router> | route back")
            return

        # Search for router in current location
        router = caller.search(router_name, location=caller.location)

        if not isinstance(router, Router):
            caller.msg("That is not a router.")
            return

        # Check if router is online
        if not router.db.online:
            caller.msg(f"{router.key} is offline. No connection available.")
            return

        # Start the router access menu
        from typeclasses.matrix.menu_formatters import get_matrix_formatters
        EvMenu(
            caller,
            "commands.matrix_menus",
            startnode="router_main_menu",
            startnode_input=("", {"router": router}),
            cmdset_mergetype="Union",
            cmd_on_exit=None,  # Suppress auto-look on menu exit
            **get_matrix_formatters()
        )

    def route_back(self, caller):
        """
        Exit a device interface and return to the router.

        Traces: interface/checkpoint → parent_object → location → router
        """
        room = caller.location
        if not room:
            caller.msg("You are nowhere.")
            return

        # Check if we're in a device interface or checkpoint
        parent_device = getattr(room.db, 'parent_object', None)
        if not parent_device:
            caller.msg("You are not in a device interface. Use this command from within a device's checkpoint or interface room.")
            return

        # Get the device's current physical location
        device_location = parent_device.location
        if not device_location:
            caller.msg("|rError: Device has no physical location. Connection lost.|n")
            return

        # Get the router for this location
        router_dbref = getattr(device_location.db, 'network_router', None)
        if not router_dbref:
            caller.msg("|rError: Device's location has no router connection.|n")
            # Trigger emergency disconnect
            from typeclasses.matrix.avatars import MatrixAvatar
            if isinstance(caller, MatrixAvatar):
                rig = getattr(caller.db, 'rig', None)
                if rig and hasattr(rig, 'disconnect'):
                    operator = getattr(caller.db, 'operator', None)
                    if operator:
                        from typeclasses.matrix.devices.dive_rig import JACKOUT_EMERGENCY
                        rig.disconnect(operator, severity=JACKOUT_EMERGENCY, reason="Network connection lost")
            return

        # Load the router
        try:
            router = Router.objects.get(pk=router_dbref)
        except Router.DoesNotExist:
            caller.msg("|rError: Router no longer exists.|n")
            # Trigger emergency disconnect
            from typeclasses.matrix.avatars import MatrixAvatar
            if isinstance(caller, MatrixAvatar):
                rig = getattr(caller.db, 'rig', None)
                if rig and hasattr(rig, 'disconnect'):
                    operator = getattr(caller.db, 'operator', None)
                    if operator:
                        from typeclasses.matrix.devices.dive_rig import JACKOUT_EMERGENCY
                        rig.disconnect(operator, severity=JACKOUT_EMERGENCY, reason="Router connection lost")
            return

        # Check if router is online
        if not router.db.online:
            caller.msg(f"|rConnection lost: {router.key} is offline.|n")
            # Trigger emergency disconnect
            from typeclasses.matrix.avatars import MatrixAvatar
            if isinstance(caller, MatrixAvatar):
                rig = getattr(caller.db, 'rig', None)
                if rig and hasattr(rig, 'disconnect'):
                    operator = getattr(caller.db, 'operator', None)
                    if operator:
                        from typeclasses.matrix.devices.dive_rig import JACKOUT_EMERGENCY
                        rig.disconnect(operator, severity=JACKOUT_EMERGENCY, reason="Router offline")
            return

        # Get router's location
        router_location = router.location
        if not router_location:
            caller.msg("|rError: Router has no physical location.|n")
            return

        # Show closing message
        caller.msg(f"|gConnection closed. Returned to {router.key}.|n")

        # Announce departure to current room
        room.msg_contents(
            f"{caller.key} disconnects and fades into the data stream.",
            exclude=[caller]
        )

        # Delay 1 second before moving
        from evennia.utils import delay

        def _do_move():
            # Move to router's location (let Evennia handle auto-look)
            caller.move_to(router_location)

            # Announce arrival
            router_location.msg_contents(
                f"{caller.key} materializes from a device connection.",
                exclude=[caller]
            )

        delay(1.0, _do_move)


class CmdMacl(Command):
    """
    Manage Access Control Lists on networked devices.

    Usage:
        macl <device>                         - List ACL entries
        macl/grant <device> = <name>,<level>  - Grant access (level 1-10)
        macl/revoke <device> = <name>         - Revoke access
        macl/clear <device>                   - Clear entire ACL

    Access Levels:
        1   - Entry (basic interface access)
        2-3 - Low access (basic commands)
        4-6 - Medium access (modify device, customize)
        7-9 - High access (advanced commands)
        10  - Root (full control, ACL management)

    Examples:
        macl hub
            View all users who have access to the hub and their levels.

        macl/grant hub = Alice,10
            Grant Alice level 10 (root) access - she can do everything.

        macl/grant hub = Cyph3r,5
            Grant avatar Cyph3r level 5 (medium) access - Matrix-only.

        macl/revoke hub = Bob
            Remove Bob from the ACL - he loses all access.

        macl/clear hub
            Remove everyone from the ACL - reset to public device.

    Notes:
        - Use character names for physical access (they must be in same room)
        - Use avatar names for Matrix-only access (searched globally)
        - Characters on ACL get both physical and Matrix access
        - Avatars on ACL only get Matrix access
    """

    key = "macl"
    switch_options = ("grant", "revoke", "clear")
    locks = ADMIN_LOCK
    help_category = "Building"

    def parse(self):
        """Parse switches from raw_string."""
        super().parse()

        raw = self.raw_string or ""
        self.switches = []

        # Find switches in format: macl/grant/revoke args
        parts = raw.split(None, 1)
        if parts:
            cmd_part = parts[0]
            segments = cmd_part.split('/')
            if len(segments) > 1:
                self.switches = segments[1:]

            if len(parts) > 1:
                self.args = parts[1]
            else:
                self.args = ""

    def func(self):
        caller = self.caller

        if not self.args.strip():
            caller.msg("Usage: macl <device>  or  macl/grant <device> = <name>,<level>")
            return

        # Parse device name (everything before '=' or the whole arg)
        if "=" in self.args:
            device_name = self.args.split("=")[0].strip()
        else:
            device_name = self.args.strip()

        # Search for device
        device = caller.search(device_name)
        if not device:
            return

        # Check if it's a networked device
        from typeclasses.matrix.mixins import NetworkedMixin
        if not isinstance(device, NetworkedMixin):
            caller.msg(f"{device.get_display_name(caller)} is not a networked device.")
            return

        # Handle switches
        if "grant" in self.switches:
            self._handle_grant(caller, device)
        elif "revoke" in self.switches:
            self._handle_revoke(caller, device)
        elif "clear" in self.switches:
            self._handle_clear(caller, device)
        else:
            # Default: list ACL
            self._handle_list(caller, device)

    def _handle_list(self, caller, device):
        """List all ACL entries with interactive menu."""
        # Start EvMenu for ACL management
        from typeclasses.matrix.menu_formatters import get_matrix_formatters
        EvMenu(
            caller,
            "commands.matrix_cmds",
            startnode="node_acl_list",
            startnode_input=("", {"device": device}),
            cmd_on_exit=None,
            **get_matrix_formatters()
        )

    def _handle_grant(self, caller, device):
        """Grant access to a user."""
        if "=" not in self.args:
            caller.msg("Usage: macl/grant <device> = <name>,<level>")
            caller.msg("Example: macl/grant hub = Alice,10")
            return

        rhs = self.args.split("=", 1)[1].strip()
        parts = [p.strip() for p in rhs.split(",")]

        if len(parts) != 2:
            caller.msg("Usage: macl/grant <device> = <name>,<level>")
            caller.msg("Example: macl/grant hub = Alice,10")
            return

        target_name = parts[0]
        try:
            level = int(parts[1])
        except ValueError:
            caller.msg("|rLevel must be a number between 1 and 10.|n")
            return

        if level < 1 or level > 10:
            caller.msg("|rLevel must be between 1 and 10.|n")
            return

        # Search for character or avatar
        from typeclasses.characters import Character
        from typeclasses.matrix.avatars import MatrixAvatar
        from evennia.utils.search import search_object

        # Try finding a character first (in same location)
        target = caller.search(target_name, location=caller.location, quiet=True)
        if target and isinstance(target[0], Character):
            target = target[0]
            caller.msg(f"|gGranting physical + Matrix access to '{target.key}' at level {level}.|n")
        else:
            # Try finding avatar globally
            avatars = search_object(target_name, typeclass="typeclasses.matrix.avatars.MatrixAvatar")
            if avatars:
                target = avatars[0]
                caller.msg(f"|gGranting Matrix-only access to avatar '{target.key}' at level {level}.|n")
            else:
                caller.msg(f"|rNo character or avatar found matching '{target_name}'.|n")
                return

        device.add_to_acl(target, level=level)
        caller.msg(f"|gAccess granted successfully.|n")

        # Notify target if online
        if target.has_account:
            target.msg(f"|yYou have been granted level {level} access to {device.key}.|n")

    def _handle_revoke(self, caller, device):
        """Revoke access from a user."""
        if "=" not in self.args:
            caller.msg("Usage: macl/revoke <device> = <name>")
            caller.msg("Example: macl/revoke hub = Alice")
            return

        target_name = self.args.split("=", 1)[1].strip()

        # Search in ACL by name
        if not hasattr(device.db, 'acl') or not device.db.acl:
            caller.msg("|rNo one has access to this device.|n")
            return

        from evennia.objects.models import ObjectDB
        found_pk = None
        found_name = None

        for char_pk, level in device.db.acl.items():
            try:
                obj = ObjectDB.objects.get(pk=char_pk)
                if obj.key.lower() == target_name.lower():
                    found_pk = char_pk
                    found_name = obj.key
                    break
            except ObjectDB.DoesNotExist:
                continue

        if not found_pk:
            caller.msg(f"|rNo user '{target_name}' found in ACL.|n")
            return

        # Remove from ACL
        del device.db.acl[found_pk]
        caller.msg(f"|gAccess revoked for '{found_name}'.|n")

        # Notify target if online
        try:
            target = ObjectDB.objects.get(pk=found_pk)
            if target.has_account:
                target.msg(f"|rYour access to {device.key} has been revoked.|n")
        except ObjectDB.DoesNotExist:
            pass

    def _handle_clear(self, caller, device):
        """Clear all ACL entries."""
        if not hasattr(device.db, 'acl') or not device.db.acl:
            caller.msg("ACL is already empty.")
            return

        count = len(device.db.acl)
        device.db.acl = {}
        caller.msg(f"|yCleared {count} ACL entries from {device.key}.|n")


# ACL Management Menu Nodes

def node_acl_list(caller, raw_string, **kwargs):
    """
    Display ACL entries and allow selection for deletion.
    """
    device = kwargs.get("device")
    if not device:
        caller.msg("|rError: No device specified.|n")
        return None, None

    # Get ACL entries
    if not hasattr(device.db, 'acl') or not device.db.acl:
        text = f"|c=== ACL for {device.key} ===|n\n\n"
        text += "No ACL entries (public device).\n"
        return text, [{"key": "q", "desc": "Exit", "goto": "node_exit"}]

    # Build display
    text = f"|c=== ACL for {device.key} ===|n\n"

    from evennia.objects.models import ObjectDB

    acl_list = []
    for char_pk, level in device.db.acl.items():
        try:
            obj = ObjectDB.objects.get(pk=char_pk)
            if obj.typeclass_path and 'MatrixAvatar' in obj.typeclass_path:
                name = f"{obj.key} (matrix, level {level})"
            else:
                name = f"{obj.key} (physical, level {level})"
        except ObjectDB.DoesNotExist:
            name = f"<err> (<err>, level {level})"

        acl_list.append((char_pk, name))

    # Build options
    options = []
    for i, (char_pk, display_name) in enumerate(acl_list, 1):
        options.append({
            "key": str(i),
            "desc": display_name,
            "goto": ("node_confirm_delete", {"device": device, "char_pk": char_pk, "name": display_name})
        })

    options.append({"key": "q", "desc": "Exit", "goto": "node_exit"})

    return text, options


def node_confirm_delete(caller, raw_string, **kwargs):
    """
    Confirm deletion of an ACL entry.
    """
    device = kwargs.get("device")
    char_pk = kwargs.get("char_pk")
    name = kwargs.get("name")

    if not device or char_pk is None:
        caller.msg("|rError: Invalid parameters.|n")
        return ("node_acl_list", {"device": device})

    text = f"|yConfirm removal of:|n\n"
    text += f"  {name}\n\n"
    text += "This will revoke all access for this user.\n"

    options = [
        {
            "key": "y",
            "desc": "Yes, remove",
            "goto": ("node_do_delete", {"device": device, "char_pk": char_pk, "name": name})
        },
        {
            "key": "n",
            "desc": "No, go back",
            "goto": ("node_acl_list", {"device": device})
        }
    ]

    return text, options


def node_do_delete(caller, raw_string, **kwargs):
    """
    Actually delete the ACL entry.
    """
    device = kwargs.get("device")
    char_pk = kwargs.get("char_pk")
    name = kwargs.get("name")

    if not device or char_pk is None:
        caller.msg("|rError: Invalid parameters.|n")
        return ("node_acl_list", {"device": device})

    # Remove from ACL
    if hasattr(device.db, 'acl') and char_pk in device.db.acl:
        del device.db.acl[char_pk]
        caller.msg(f"|gRemoved {name} from ACL.|n")

        # Notify target if they still exist and are online
        try:
            from evennia.objects.models import ObjectDB
            target = ObjectDB.objects.get(pk=char_pk)
            if target.has_account:
                target.msg(f"|rYour access to {device.key} has been revoked.|n")
        except ObjectDB.DoesNotExist:
            pass
    else:
        caller.msg(f"|rEntry not found in ACL.|n")

    # Return to list
    return node_acl_list(caller, "", device=device)


def node_exit(caller, raw_string, **kwargs):
    """Exit the menu."""
    return None, None


# Router Access Menu Nodes are in commands/matrix_menus.py
