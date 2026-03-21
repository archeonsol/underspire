"""
Open, close, lock, unlock, and verify — doors and bioscan exits.
"""

from commands.base_cmds import Command


def _dir_map():
    return {
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
        "o": "out",
    }


def find_exit_by_direction(caller, arg):
    """Find exit in caller's location matching direction string (key or alias)."""
    loc = caller.location
    if not loc or not arg:
        return None
    raw = arg.strip().lower()
    direction = _dir_map().get(raw, raw)
    exits = [o for o in (loc.contents or []) if getattr(o, "destination", None)]
    for ex in exits:
        key = (ex.key or "").lower().strip()
        try:
            aliases = [a.lower() for a in (ex.aliases.all() if hasattr(ex.aliases, "all") else [])]
        except Exception:
            aliases = []
        if direction == key or direction in aliases:
            return ex
    return None


class CmdOpenDoor(Command):
    """
    Open a door on an exit.

    Usage:
        open <direction>
    """

    key = "open"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from evennia.utils import delay
        from world.rpg.factions.doors import staff_bypass, sync_door_pair, schedule_door_auto_close

        if not self.args:
            self.caller.msg("Open which way? Usage: open <direction>")
            return
        ex = find_exit_by_direction(self.caller, self.args)
        if not ex:
            self.caller.msg("There is no exit in that direction.")
            return
        if not getattr(ex.db, "door", None):
            self.caller.msg("There is no door there.")
            return
        if getattr(ex.db, "door_open", None):
            self.caller.msg("It's already open.")
            return
        if getattr(ex.db, "door_locked", None) and not staff_bypass(self.caller):
            self.caller.msg("It's locked.")
            return
        if getattr(ex.db, "door_locked", None) and staff_bypass(self.caller):
            ex.db.door_locked = False
        if getattr(ex.db, "bioscan", None):
            self.caller.msg("This door requires bioscan verification. Use: verify <direction>")
            return
        ex.db.door_open = True
        sync_door_pair(ex, True)
        door_name = getattr(ex.db, "door_name", None) or "door"
        self.caller.msg(f"You open the {door_name}.")
        loc = self.caller.location
        if loc:
            loc.msg_contents(
                "{name} opens the {dn}.",
                exclude=self.caller,
                mapping={"name": self.caller, "dn": door_name},
                from_obj=self.caller,
            )
        auto_close = int(getattr(ex.db, "door_auto_close", None) or 0)
        if auto_close > 0:
            from world.rpg.factions.doors import auto_close_door

            delay(auto_close, auto_close_door, ex.id)


class CmdCloseDoor(Command):
    """
    Close an open door.

    Usage:
        close <direction>
    """

    key = "close"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.rpg.factions.doors import staff_bypass, sync_door_pair

        if not self.args:
            self.caller.msg("Close which way? Usage: close <direction>")
            return
        ex = find_exit_by_direction(self.caller, self.args)
        if not ex:
            self.caller.msg("There is no exit in that direction.")
            return
        if not getattr(ex.db, "door", None):
            self.caller.msg("There is no door there.")
            return
        if not getattr(ex.db, "door_open", None):
            self.caller.msg("It's already closed.")
            return
        ex.db.door_open = False
        sync_door_pair(ex, False)
        door_name = getattr(ex.db, "door_name", None) or "door"
        self.caller.msg(f"You close the {door_name}.")
        loc = self.caller.location
        if loc:
            loc.msg_contents(
                "{name} closes the {dn}.",
                exclude=self.caller,
                mapping={"name": self.caller, "dn": door_name},
                from_obj=self.caller,
            )


class CmdUnlockDoor(Command):
    """Unlock a locked door (requires key in inventory). Staff bypass."""

    key = "unlock"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.rpg.factions.doors import staff_bypass, has_key

        if not self.args:
            self.caller.msg("Unlock which way? Usage: unlock <direction>")
            return
        ex = find_exit_by_direction(self.caller, self.args)
        if not ex:
            self.caller.msg("There is no exit in that direction.")
            return
        if not getattr(ex.db, "door", None):
            self.caller.msg("There is no door there.")
            return
        if not getattr(ex.db, "door_locked", None):
            self.caller.msg("It's not locked.")
            return
        if staff_bypass(self.caller):
            ex.db.door_locked = False
            self.caller.msg("You unlock it (staff).")
            return
        tag = getattr(ex.db, "door_key_tag", None)
        if not has_key(self.caller, tag):
            self.caller.msg("You lack the right key.")
            return
        ex.db.door_locked = False
        self.caller.msg("You unlock it.")


class CmdLockDoor(Command):
    """Lock a door (requires key). Staff bypass."""

    key = "lock"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.rpg.factions.doors import staff_bypass, has_key

        if not self.args:
            self.caller.msg("Lock which way? Usage: lock <direction>")
            return
        ex = find_exit_by_direction(self.caller, self.args)
        if not ex:
            self.caller.msg("There is no exit in that direction.")
            return
        if not getattr(ex.db, "door", None):
            self.caller.msg("There is no door there.")
            return
        if getattr(ex.db, "door_locked", None):
            self.caller.msg("It's already locked.")
            return
        if not getattr(ex.db, "door_open", None):
            self.caller.msg("Close it first.")
            return
        if staff_bypass(self.caller):
            ex.db.door_locked = True
            self.caller.msg("You lock it (staff).")
            return
        tag = getattr(ex.db, "door_key_tag", None)
        if not has_key(self.caller, tag):
            self.caller.msg("You lack the right key.")
            return
        ex.db.door_locked = True
        self.caller.msg("You lock it.")


class CmdVerify(Command):
    """
    Submit to bioscan at a secured door.

    Usage:
        verify <direction>
    """

    key = "verify"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from evennia.utils import delay
        from world.rpg.factions.doors import run_bioscan, sync_door_pair, schedule_bioscan_auto_close

        if not self.args:
            self.caller.msg("Verify at which door? Usage: verify <direction>")
            return
        ex = find_exit_by_direction(self.caller, self.args.strip())
        if not ex:
            self.caller.msg("No exit in that direction.")
            return
        if not getattr(ex.db, "bioscan", None):
            self.caller.msg("That door doesn't have a bioscan.")
            return
        if getattr(ex.db, "door_open", None):
            self.caller.msg("The door is already open.")
            return

        passed, message = run_bioscan(self.caller, ex)
        door_name = getattr(ex.db, "door_name", None) or "bioscan door"

        if passed:
            ex.db.door_open = True
            sync_door_pair(ex, True)
            pass_msg = getattr(ex.db, "bioscan_message_pass", None) or "Bioscan accepted."
            self.caller.msg(f"|g{pass_msg}|n")
            loc = self.caller.location
            if loc:
                loc.msg_contents(
                    "The {dn} opens for {name}.",
                    exclude=self.caller,
                    mapping={"name": self.caller, "dn": door_name},
                    from_obj=self.caller,
                )
            schedule_bioscan_auto_close(ex)
        else:
            fail_msg = getattr(ex.db, "bioscan_message_fail", None) or "Bioscan rejected."
            self.caller.msg(f"|r{fail_msg}|n")
            if getattr(ex.db, "bioscan_sound_fail", None):
                loc = self.caller.location
                if loc:
                    loc.msg_contents(
                        "The {dn} buzzes — access denied for {name}.",
                        exclude=self.caller,
                        mapping={"name": self.caller, "dn": door_name},
                        from_obj=self.caller,
                    )
