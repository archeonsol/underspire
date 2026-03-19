"""
Staff cyberware command.

Temporary install/remove interface until the medical system supports it.

Usage:
    @cyberware/install <character> = <cyberware object>
    @cyberware/remove  <character> = <slot>
    @cyberware/rip     <character> = <slot>
    @cyberware/list    <character>
"""

from commands.base_cmds import Command, ADMIN_LOCK
from world.medical import BODY_PARTS


class CmdCyberware(Command):
    """
    Manage cyberware installation on a character. Builder+.

    Usage:
        @cyberware/install <character> = <cyberware object>
        @cyberware/remove  <character> = <slot>
        @cyberware/rip     <character> = <slot>
        @cyberware/list    <character>

    /install  Surgically installs the cyberware object into the character's slot.
    /remove   Surgically removes cyberware from the named slot (object drops in room).
    /rip      Forcibly tears out the cyberware (same mechanical effect, different fiction).
    /list     Lists all installed cyberware and their slots.
    """

    key = "@cyberware"
    aliases = ["cyberware"]
    switch_options = ("install", "remove", "rip", "list")
    locks = ADMIN_LOCK
    help_category = "Staff"

    def parse(self):
        super().parse()
        raw = self.raw_string or ""
        self.switches = []
        parts = raw.split(None, 1)
        if parts:
            segments = parts[0].split("/")
            if len(segments) > 1:
                self.switches = segments[1:]
            self.args = parts[1] if len(parts) > 1 else ""

    def func(self):
        caller = self.caller

        if "list" in self.switches:
            self._do_list()
        elif "install" in self.switches:
            self._do_install()
        elif "remove" in self.switches:
            self._do_remove(rip=False)
        elif "rip" in self.switches:
            self._do_remove(rip=True)
        else:
            caller.msg("Usage: @cyberware/install, /remove, /rip, or /list")

    def _parse_char_and_arg(self):
        """Parse 'character = arg' from self.args. Returns (character, arg) or (None, None)."""
        if "=" not in self.args:
            self.caller.msg("Usage: @cyberware/<switch> <character> = <object or slot>")
            return None, None
        char_name, _, arg = self.args.partition("=")
        char = self.caller.search(char_name.strip(), global_search=True)
        return char, arg.strip()

    def _do_list(self):
        caller = self.caller
        char_name = self.args.strip()
        if not char_name:
            caller.msg("Usage: @cyberware/list <character>")
            return
        char = caller.search(char_name, global_search=True)
        if not char:
            return
        cyberware = char.get_cyberware() if hasattr(char, "get_cyberware") else {}
        if not cyberware:
            caller.msg(f"{char.key} has no cyberware installed.")
            return
        lines = [f"Cyberware installed on {char.key}:"]
        for slot, obj in sorted(cyberware.items()):
            body_note = " (body part)" if slot in BODY_PARTS else " (abstract slot)"
            lines.append(f"  {slot}{body_note}: {obj.key} (#{obj.id})")
        caller.msg("\n".join(lines))

    def _do_install(self):
        caller = self.caller
        char, obj_name = self._parse_char_and_arg()
        if not char:
            return
        if not hasattr(char, "install_cyberware"):
            caller.msg(f"{char.key} does not support cyberware.")
            return
        obj = caller.search(obj_name)
        if not obj:
            return
        result = char.install_cyberware(obj)
        if result is True:
            caller.msg(f"Installed {obj.key} into {char.key} (slot: {obj.slot}).")
        else:
            caller.msg(f"Install failed: {result}")

    def _do_remove(self, rip=False):
        caller = self.caller
        char, slot = self._parse_char_and_arg()
        if not char:
            return
        if not hasattr(char, "remove_cyberware"):
            caller.msg(f"{char.key} does not support cyberware.")
            return
        result = char.remove_cyberware(slot, rip=rip)
        if result is True:
            verb = "Ripped" if rip else "Removed"
            caller.msg(f"{verb} cyberware from slot '{slot}' on {char.key}. Object is now in the room.")
        else:
            caller.msg(f"Remove failed: {result}")
