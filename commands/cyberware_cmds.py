"""
Staff cyberware command.

Temporary install/remove interface until the medical system supports it.

Usage:
    @cyberware/install <character> = <cyberware object>
    @cyberware/remove  <character> = <cyberware name>
    @cyberware/list    <character>
"""

from commands.base_cmds import Command, ADMIN_LOCK
import time


class CmdCyberware(Command):
    """
    Manage cyberware installation on a character. Builder+.

    Usage:
        @cyberware/install <character> = <cyberware object>
        @cyberware/remove  <character> = <cyberware name>
        @cyberware/list    <character>

    /install  Installs the cyberware object into the character.
    /remove   Removes cyberware by name (object drops in room).
    /list     Lists all installed cyberware.
    """

    key = "@cyberware"
    aliases = ["cyberware"]
    switch_options = ("install", "remove", "list", "forceinstall", "malfunction", "repair")
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
            self._do_remove()
        elif "forceinstall" in self.switches:
            self._do_force_install()
        elif "malfunction" in self.switches:
            self._do_malfunction()
        elif "repair" in self.switches:
            self._do_repair()
        else:
            caller.msg("Usage: @cyberware/install, /remove, or /list")

    def _parse_char_and_arg(self):
        """Parse 'character = arg' from self.args. Returns (character, arg) or (None, None)."""
        if "=" not in self.args:
            self.caller.msg("Usage: @cyberware/<switch> <character> = <object or name>")
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
        cyberware = char.get_cyberware() if hasattr(char, "get_cyberware") else []
        if not cyberware:
            caller.msg(f"{char.key} has no cyberware installed.")
            return
        lines = [f"Cyberware installed on {char.key}:"]
        for obj in cyberware:
            lines.append(f"  {obj.key} (#{obj.id}) [{type(obj).__name__}]")
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
        result = char.install_cyberware(obj, skip_surgery=True)
        if result is True:
            caller.msg(f"Installed {obj.key} into {char.key}.")
        else:
            caller.msg(f"Install failed: {result}")

    def _do_remove(self):
        caller = self.caller
        char, obj_name = self._parse_char_and_arg()
        if not char:
            return
        if not hasattr(char, "remove_cyberware"):
            caller.msg(f"{char.key} does not support cyberware.")
            return
        result = char.remove_cyberware(obj_name)
        if result is True:
            caller.msg(f"Removed '{obj_name}' from {char.key}. Object is now in the room.")
        else:
            caller.msg(f"Remove failed: {result}")

    def _do_force_install(self):
        caller = self.caller
        char, obj_name = self._parse_char_and_arg()
        if not char:
            return
        obj = caller.search(obj_name)
        if not obj:
            return
        result = char.install_cyberware(obj, skip_surgery=True)
        caller.msg(f"Force install {'ok' if result is True else 'failed: ' + str(result)}")

    def _do_malfunction(self):
        caller = self.caller
        char, obj_name = self._parse_char_and_arg()
        if not char:
            return
        cyberware = list(char.db.cyberware or [])
        match = next((c for c in cyberware if c.key.lower() == obj_name.lower()), None)
        if not match:
            caller.msg("Installed cyberware not found.")
            return
        match.db.malfunctioning = True
        match.db.chrome_hp = 0
        if getattr(match, "buff_class", None):
            char.buffs.remove(match.buff_class.key)
        caller.msg(f"{match.key} set to malfunctioning.")

    def _do_repair(self):
        caller = self.caller
        char, obj_name = self._parse_char_and_arg()
        if not char:
            return
        cyberware = list(char.db.cyberware or [])
        match = next((c for c in cyberware if c.key.lower() == obj_name.lower()), None)
        if not match:
            caller.msg("Installed cyberware not found.")
            return
        match.db.malfunctioning = False
        mx = int(getattr(match.db, "chrome_max_hp", 100) or 100)
        match.db.chrome_hp = mx
        if getattr(match, "buff_class", None):
            char.buffs.add(match.buff_class)
        caller.msg(f"{match.key} repaired.")


class CmdSkinWeave(Command):
    key = "skinweave"
    aliases = ["sw"]
    locks = "cmd:all()"
    help_category = "Cyberware"

    def _get_weave(self):
        from typeclasses.cyberware_catalog import SkinWeave
        for cw in (self.caller.db.cyberware or []):
            if isinstance(cw, SkinWeave) and not getattr(cw.db, "malfunctioning", False):
                return cw
        return None

    def func(self):
        caller = self.caller
        weave = self._get_weave()
        if not weave:
            caller.msg("You don't have a functional skin weave installed.")
            return
        args = (self.args or "").strip()
        if not args:
            caller.msg("|wSkin weave appearance:|n")
            for part in (weave.db.weave_parts or []):
                caller.msg(f"  {part}: {dict(weave.db.weave_descriptions or {}).get(part, '')}")
            return
        low = args.lower()
        if low == "coverage":
            caller.msg("Coverage: " + ", ".join(weave.db.weave_parts or []))
            return
        if low == "reset":
            ok, msg = weave.reset_to_defaults(caller)
            caller.msg(msg if ok else f"|r{msg}|n")
            return
        if low.startswith("set ") and "=" in args:
            from commands.roleplay_cmds import _resolve_body_part
            left, _, desc = args[4:].partition("=")
            part = _resolve_body_part(left.strip(), caller=caller) or left.strip().lower()
            ok, msg = weave.update_weave_appearance(caller, part, desc.strip())
            caller.msg(msg if ok else f"|r{msg}|n")
            return
        if low.startswith("preset "):
            bits = args.split()
            if len(bits) < 2:
                caller.msg("Usage: skinweave preset save/load/list/delete <name>")
                return
            action = bits[1].lower()
            if action == "list":
                presets = sorted((weave.db.weave_presets or {}).keys())
                caller.msg("Presets: " + (", ".join(presets) if presets else "none"))
                return
            if len(bits) < 3:
                caller.msg("Provide a preset name.")
                return
            name = bits[2]
            if action == "save":
                ok, msg = weave.save_preset(name)
            elif action == "load":
                if name.strip().lower() == "default":
                    ok, msg = weave.reset_to_defaults(caller)
                else:
                    ok, msg = weave.load_preset(caller, name)
            elif action == "delete":
                presets = dict(weave.db.weave_presets or {})
                key = name.strip().lower()
                if key in presets:
                    del presets[key]
                    weave.db.weave_presets = presets
                    ok, msg = True, f"Deleted preset '{key}'."
                else:
                    ok, msg = False, f"No preset named '{key}'."
            else:
                caller.msg("Usage: skinweave preset save/load/list/delete <name>")
                return
            caller.msg(msg if ok else f"|r{msg}|n")
            return
        caller.msg("Usage: skinweave | skinweave set <body part> = <desc> | skinweave preset save/load/list/delete <name> | skinweave reset | skinweave coverage")


class CmdSurge(Command):
    key = "surge"
    locks = "cmd:all()"
    help_category = "Cyberware"

    def _get_pump(self):
        from typeclasses.cyberware_catalog import AdrenalPump
        for cw in (self.caller.db.cyberware or []):
            if isinstance(cw, AdrenalPump) and not getattr(cw.db, "malfunctioning", False):
                return cw
        return None

    def func(self):
        caller = self.caller
        pump = self._get_pump()
        if not pump:
            caller.msg("You don't have a functional adrenal pump.")
            return
        now = time.time()
        if (self.args or "").strip().lower() == "status":
            active_until = float(getattr(pump.db, "surge_active_until", 0.0) or 0.0)
            crash_until = float(getattr(pump.db, "surge_crash_until", 0.0) or 0.0)
            cd_until = float(getattr(pump.db, "surge_cooldown_until", 0.0) or 0.0)
            if active_until > now:
                caller.msg(f"Surge active ({int(active_until - now)}s remaining).")
            elif crash_until > now:
                caller.msg(f"Surge crash active ({int(crash_until - now)}s remaining).")
            elif cd_until > now:
                caller.msg(f"Pump cooling down ({int(cd_until - now)}s remaining).")
            else:
                caller.msg("Pump is ready.")
            return
        cd_until = float(getattr(pump.db, "surge_cooldown_until", 0.0) or 0.0)
        if cd_until > now:
            caller.msg(f"Pump still cooling down for {int(cd_until - now)}s.")
            return
        active_until = float(getattr(pump.db, "surge_active_until", 0.0) or 0.0)
        if active_until > now:
            caller.msg("Surge is already active.")
            return
        pump.db.surge_active_until = now + 600
        pump.db.surge_crash_until = now + 900
        pump.db.surge_cooldown_until = now + 1800
        pump.db.surge_crash_applied = False
        caller.msg("|rAdrenal surge floods your system.|n")


class CmdClaws(Command):
    key = "claws"
    aliases = ["claw"]
    locks = "cmd:all()"
    help_category = "Cyberware"

    def _get_claws(self):
        from typeclasses.cyberware_catalog import RetractableClaws
        for cw in (self.caller.db.cyberware or []):
            if isinstance(cw, RetractableClaws) and not getattr(cw.db, "malfunctioning", False):
                return cw
        return None

    def func(self):
        caller = self.caller
        claws = self._get_claws()
        if not claws:
            caller.msg("You don't have functional retractable claws.")
            return
        arg = (self.args or "").strip().lower()
        if arg in ("", "status"):
            caller.msg("Claws are " + ("deployed." if claws.are_deployed() else "retracted."))
            return
        if arg == "deploy":
            ok, msg = claws.deploy(caller)
        elif arg == "retract":
            ok, msg = claws.retract(caller)
        else:
            caller.msg("Usage: claws [status|deploy|retract]")
            return
        caller.msg(msg if ok else f"|r{msg}|n")
