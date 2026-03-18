"""
Base commands: Command (flatline/dead blocking), _command_character, CmdLook, CmdExamine, CmdGet, CmdPut, CmdOperate.
"""

import re
from evennia.utils import logger
from evennia.commands.command import Command as BaseCommand
from evennia.commands.default.general import CmdLook as DefaultCmdLook

try:
    from evennia.commands.default.general import CmdGet as DefaultCmdGet
except ImportError:
    DefaultCmdGet = None

# Lock string for admin-only commands (Builder and Admin accounts)
ADMIN_LOCK = "cmd:perm(Builder) or perm(Admin)"


def _command_character(self):
    """Resolve to the puppeted character when command runs with Account as caller (e.g. Session cmdset)."""
    caller = self.caller
    if getattr(self, "session", None) and getattr(self.session, "puppet", None):
        puppet = self.session.puppet
        if puppet and (getattr(caller, "db", None) is None or not hasattr(caller.db, "current_hp")):
            return puppet
    return caller


class Command(BaseCommand):
    """
    Base command. Blocks all commands when character is flatlined (dying) or dead except for Admins/Builders.
    """
    def at_pre_cmd(self):
        """Block commands if character is flatlined (dying) or permanently dead."""
        caller = self.caller
        if not caller:
            return super().at_pre_cmd()
        char = _command_character(self)
        from world.death import character_can_act
        can_act, msg = character_can_act(char, allow_builders=True)
        if not can_act and msg:
            caller.msg(msg)
            return True
        return super().at_pre_cmd()


class CmdLook(DefaultCmdLook):
    """
    Look at location, object, or a directional exit.

    Usage:
      look
      look <obj>
      look <direction>   (e.g. look north, look n)
    """

    def at_pre_cmd(self):
        """Block look when flatlined/dead so state-specific cmdset message can show."""
        caller = self.caller
        if not caller:
            return super().at_pre_cmd() if hasattr(super(), "at_pre_cmd") else None
        char = _command_character(self)
        from world.death import character_can_act
        can_act, msg = character_can_act(char, allow_builders=True)
        if not can_act and msg:
            caller.msg(msg)
            return True
        return super().at_pre_cmd() if hasattr(super(), "at_pre_cmd") else None

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()

        # Directional look: look north / look n, etc.
        if args:
            lower = args.lower()
            dir_map = {
                "n": "north",
                "s": "south",
                "e": "east",
                "w": "west",
                "ne": "northeast",
                "nw": "northwest",
                "se": "southeast",
                "sw": "southwest",
                "u": "up",
                "d": "down",
            }
            direction = dir_map.get(lower, lower)
            loc = getattr(caller, "location", None)
            if loc:
                # Find an exit in this room whose key or alias matches the direction
                exits = [obj for obj in loc.contents if getattr(obj, "destination", None)]
                target_exit = None
                for ex in exits:
                    key = (getattr(ex, "key", "") or "").lower()
                    # ex.aliases is an AliasHandler; use .all() to get strings
                    aliases = []
                    if hasattr(ex, "aliases"):
                        try:
                            aliases = [a.lower() for a in ex.aliases.all()]
                        except Exception as e:
                            logger.log_trace("base_cmds.CmdLook exit aliases: %s" % e)
                            aliases = []
                    if direction == key or direction in aliases:
                        target_exit = ex
                        break
                if target_exit and target_exit.destination:
                    dest = target_exit.destination
                    # Collect visible characters in the destination room (players and NPCs, but not corpses).
                    contents = getattr(dest, "contents", [])
                    try:
                        from typeclasses.corpse import Corpse
                        def _is_char(o):
                            if isinstance(o, Corpse):
                                return False
                            if getattr(o, "has_account", False):
                                return True
                            return bool(getattr(getattr(o, "db", None), "is_npc", False))
                        chars = [o for o in contents if _is_char(o)]
                    except Exception:
                        chars = [
                            o for o in contents
                            if getattr(o, "has_account", False) or bool(getattr(getattr(o, "db", None), "is_npc", False))
                        ]
                    if not chars:
                        caller.msg(f"To the {direction} you see |wnothing of note|n.")
                        return
                    # Build a natural-language list: John, Bob and James
                    names = [obj.get_display_name(caller) for obj in chars]
                    if len(names) == 1:
                        who = names[0]
                    elif len(names) == 2:
                        who = f"{names[0]} and {names[1]}"
                    else:
                        who = ", ".join(names[:-1]) + f" and {names[-1]}"
                    caller.msg(f"To the {direction} you see {who}.")
                    return

        # Fallback to default look behavior (objects, room, etc.)
        super().func()


class CmdStopWalking(Command):
    """
    Stop a pending staggered walk before it completes.

    Usage:
      stop walking
    """

    key = "stop walking"
    aliases = ["stop walk", "halt walking", "halt walk"]
    locks = "cmd:all()"
    help_category = "Movement"

    def func(self):
        caller = _command_character(self)
        if not getattr(caller, "db", None):
            self.caller.msg("You must be in character to do that.")
            return
        # Mark the next delayed walk to be cancelled; the delayed callback
        # in `world.staggered_movement` will honour this flag.
        already_set = bool(getattr(caller.db, "cancel_walking", False))
        caller.db.cancel_walking = True
        if already_set:
            self.caller.msg("You steady yourself, keeping from walking off anywhere.")
        else:
            self.caller.msg("You stop walking.")


class CmdExamine(Command):
    """
    Player examine: look at an object and see what commands you can use with it.

    Usage:
      examine <object>
      ex <object>
    """
    # Player-facing examine (no @). Staff continue to use Evennia's default
    # '@examine' from the base cmdset for builder/staff-style inspection.
    key = "examine"
    aliases = ["ex"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Examine what? Usage: examine <object>")
            return
        obj = caller.search(self.args.strip(), location=caller.location)
        if not obj:
            # Try inventory
            obj = caller.search(self.args.strip(), location=caller)
        if not obj:
            return
        # Description (same as look)
        try:
            appearance = obj.return_appearance(caller)
            if appearance:
                caller.msg(appearance)
        except Exception:
            desc = obj.get_display_desc(caller) if hasattr(obj, "get_display_desc") else getattr(obj.db, "desc", None)
            if desc:
                caller.msg(desc)
        # Player-usable command hints
        try:
            from world.examine import get_usage_hints
            hints = get_usage_hints(obj)
            if hints:
                caller.msg("\n|wYou can use:|n " + ", ".join(hints))
            else:
                caller.msg("\n|wYou can use:|n Nothing special (get, drop, give if portable).")
        except Exception as e:
            logger.log_trace("base_cmds.CmdExamine usage: %s" % e)
            caller.msg(f"\n|y(Could not determine usage: {e})|n")


class CmdGet(DefaultCmdGet if DefaultCmdGet else BaseCommand):
    """Get: supports 'get <item> from <container>'; from logged-off/corpse only when allowed."""
    key = "get"
    aliases = ["take", "pick up"]

    def at_pre_cmd(self):
        """Block when flatlined/dead (CmdGet does not inherit from Command)."""
        char = _command_character(self)
        from world.death import character_can_act
        can_act, msg = character_can_act(char, allow_builders=True)
        if not can_act and msg:
            self.caller.msg(msg)
            return True
        return super().at_pre_cmd() if hasattr(super(), "at_pre_cmd") else None

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            if DefaultCmdGet:
                super().func()
            else:
                caller.msg("Get what?")
            return
        if " from " not in args:
            if DefaultCmdGet:
                super().func()
            return
        # Parse "get <item> from <container>" — default CmdGet does NOT support this, so we handle it fully
        item_spec, _, container_spec = args.partition(" from ")
        item_spec = item_spec.strip()
        container_spec = container_spec.strip()
        if not item_spec or not container_spec:
            caller.msg("Usage: get <item> from <container>")
            return
        container = caller.search(container_spec, location=caller.location)
        if not container:
            return
        try:
            from typeclasses.corpse import Corpse
            from evennia import DefaultCharacter
            from world.death import is_character_logged_off, character_logged_off_long_enough
            if isinstance(container, DefaultCharacter) and not isinstance(container, Corpse):
                if not is_character_logged_off(container):
                    caller.msg("You can't take from someone who's wide awake!")
                    return
                if not character_logged_off_long_enough(container):
                    caller.msg("They haven't been gone long enough. You can only take from someone who's been logged off at least half an hour.")
                    return
        except ImportError as e:
            logger.log_trace("base_cmds.CmdGet get-from-container check: %s" % e)
        # Search for the item inside the container (contents, not location=caller.location)
        obj = caller.search(item_spec, location=container)
        if not obj:
            return
        from evennia.utils import utils
        objs = utils.make_iter(obj)
        if len(objs) == 1 and objs[0] == caller:
            caller.msg("You can't get yourself.")
            return
        for o in objs:
            if not o.access(caller, "get"):
                err = getattr(getattr(o, "db", None), "get_err_msg", None)
                caller.msg(err if err else "You can't get that.")
                return
            if not o.at_pre_get(caller):
                return
        moved = []
        for o in objs:
            if o.move_to(caller, quiet=True, move_type="get"):
                moved.append(o)
                o.at_get(caller)
        if not moved:
            caller.msg("That can't be picked up.")
        else:
            obj_name = moved[0].get_numbered_name(len(moved), caller, return_string=True)
            caller.msg("You get %s from %s." % (obj_name, container.get_display_name(caller)))
            caller.location.msg_contents(
                "%s gets %s from %s." % (caller.get_display_name(caller), obj_name, container.get_display_name(caller)),
                exclude=caller,
            )


class CmdPut(Command):
    """Put an object you're holding into a container (e.g. put cassette in television)."""
    key = "put"
    aliases = ["insert"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller or not caller.location:
            return
        args = (self.args or "").strip()
        if " in " not in args and " into " not in args:
            self.caller.msg("Usage: put <item> in <container>")
            return
        for sep in (" in ", " into "):
            if sep in args:
                item_spec, _, container_spec = args.partition(sep)
                break
        else:
            item_spec = container_spec = ""
        item_spec = item_spec.strip()
        container_spec = container_spec.strip()
        if not item_spec or not container_spec:
            self.caller.msg("Usage: put <item> in <container>")
            return
        obj = caller.search(item_spec, location=caller)
        if not obj:
            return
        container = caller.search(container_spec, location=caller.location)
        if not container:
            return
        if container == caller:
            self.caller.msg("You can't put something into yourself.")
            return
        if obj == container:
            self.caller.msg("You can't put something into itself.")
            return
        if not hasattr(obj, "move_to"):
            self.caller.msg("You can't put that anywhere.")
            return
        if obj.location != caller:
            self.caller.msg("You're not holding that.")
            return
        if not container.access(caller, "get"):
            self.caller.msg("You can't put anything in that.")
            return
        if hasattr(container, "at_pre_object_receive") and not container.at_pre_object_receive(obj, caller):
            return
        if obj.move_to(container, quiet=True):
            if hasattr(container, "at_object_receive"):
                container.at_object_receive(obj, caller)
            obj_name = obj.get_numbered_name(1, caller, return_string=True)
            cont_name = container.get_display_name(caller)
            self.caller.msg("You put %s in %s." % (obj_name, cont_name))
            caller.location.msg_contents(
                "%s puts %s in %s." % (caller.get_display_name(caller), obj_name, cont_name),
                exclude=caller,
            )
        else:
            self.caller.msg("You can't put that in there.")


class CmdOperate(Command):
    """
    Operate a networked device.

    Usage:
        operate <device>
        op <device>

    Opens an interactive menu for controlling networked devices like hubs,
    cameras, terminals, etc. The menu shows device info, available commands,
    and file storage (if applicable).

    This is the meatspace equivalent of running 'patch cmd.exe' in the Matrix.
    """

    key = "operate"
    aliases = ["op"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)

        # If no args, check if we're in a device interface room
        if not self.args:
            room = caller.location
            if room and hasattr(room.db, 'parent_object') and room.db.parent_object:
                device = room.db.parent_object
                from typeclasses.matrix.mixins import NetworkedMixin
                if isinstance(device, NetworkedMixin):
                    # We're in a device interface - open its menu
                    from typeclasses.matrix.device_menu import start_device_menu
                    # Check if caller is a Matrix avatar
                    from typeclasses.matrix.avatars import MatrixAvatar
                    from_matrix = isinstance(caller, MatrixAvatar)
                    start_device_menu(caller, device, from_matrix=from_matrix)
                    return

            caller.msg("Usage: operate <device>")
            return

        # Find the device (check both location and inventory)
        device = caller.search(self.args.strip())
        if not device:
            return

        # Check if it's a networked device
        from typeclasses.matrix.mixins import NetworkedMixin
        if not isinstance(device, NetworkedMixin):
            caller.msg(f"{device.get_display_name(caller)} is not a networked device.")
            return

        # Launch the device menu
        from typeclasses.matrix.device_menu import start_device_menu
        start_device_menu(caller, device, from_matrix=False)
