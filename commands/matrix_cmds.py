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
    Navigate the router network to connected devices via menu.

    Usage:
        route via <router>
        route back

    route via <router> - Opens an interactive menu showing all access points (rooms)
                         connected to the specified router. You can browse devices
                         in each access point and connect to their Matrix interface.

    route back - Exit a device interface and return to the router that device is
                 currently connected to. Works from vestibule or interface rooms.

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
        caller.msg(f"|xDEBUG: Searching for '{router_name}' in {caller.location}|n")
        router = caller.search(router_name, location=caller.location)
        caller.msg(f"|xDEBUG: Search returned: {router} (type: {type(router).__name__})|n")
        if not router:
            caller.msg("|xDEBUG: Router is None/False|n")
            return

        caller.msg(f"|xDEBUG: Checking isinstance: {isinstance(router, Router)}|n")
        if not isinstance(router, Router):
            caller.msg("That is not a router.")
            return

        # Check if router is online
        if not router.db.online:
            caller.msg(f"{router.key} is offline. No connection available.")
            return

        # Start the router access menu
        EvMenu(
            caller,
            "commands.matrix_menus",
            startnode="router_access_points",
            startnode_input=("", {"router": router}),
            cmdset_mergetype="Union",
        )

    def route_back(self, caller):
        """
        Exit a device interface and return to the router.

        Traces: interface/vestibule → parent_object → location → router
        """
        room = caller.location
        if not room:
            caller.msg("You are nowhere.")
            return

        # Check if we're in a device interface or vestibule
        parent_device = getattr(room.db, 'parent_object', None)
        if not parent_device:
            caller.msg("You are not in a device interface. Use this command from within a device's vestibule or interface room.")
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
            return

        # Load the router
        try:
            router = Router.objects.get(pk=router_dbref)
        except Router.DoesNotExist:
            caller.msg("|rError: Router no longer exists.|n")
            return

        # Check if router is online
        if not router.db.online:
            caller.msg(f"|rConnection lost: {router.key} is offline.|n")
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


# Router Access Menu Nodes are in commands/matrix_menus.py
