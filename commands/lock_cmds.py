"""
Global lock / unlock: vehicles (biometric) first, then exit doors.

Extend here when other systems need the same verbs.
"""

from __future__ import annotations

from commands.base_cmds import Command

try:
    from typeclasses.vehicles import vehicle_label
except ImportError:

    def vehicle_label(v):
        return getattr(v.db, "vehicle_name", None) or getattr(v, "key", None) or "vehicle"


try:
    from world.vehicles.vehicle_targets import resolve_vehicle_for_caller
except ImportError:

    def resolve_vehicle_for_caller(caller, args):
        return None


class CmdLock(Command):
    """
    Lock a vehicle (biometric) or a door on an exit.

    Usage:
        lock <vehicle>
        lock here   (inside a vehicle cabin)
        lock        (inside a vehicle cabin — same as |wlock here|n)
        lock <direction>
    """

    key = "lock"
    aliases = ["lockvehicle", "vlock", "lockcar"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from commands.door_cmds import find_exit_by_direction
        from world.rpg.factions.doors import has_key, staff_bypass
        from world.vehicles.vehicle_security import lock_vehicle

        caller = self.caller
        loc = caller.location
        if not loc:
            return

        veh = resolve_vehicle_for_caller(caller, self.args or "")
        if veh:
            ok, msg = lock_vehicle(veh, caller)
            caller.msg(msg if ok else f"|r{msg}|n")
            return

        arg = (self.args or "").strip()
        if not arg:
            caller.msg(
                "Lock what? Usage: |wlock <vehicle>|n, |wlock here|n or |wlock|n from inside a vehicle, "
                "or |wlock <direction>|n (door)."
            )
            return

        ex = find_exit_by_direction(caller, arg)
        if not ex:
            caller.msg("You don't see that here.")
            return
        if not getattr(ex.db, "door", None):
            caller.msg("There is no door there.")
            return
        if getattr(ex.db, "door_locked", None):
            caller.msg("It's already locked.")
            return
        if not getattr(ex.db, "door_open", None):
            caller.msg("Close it first.")
            return
        tag = getattr(ex.db, "door_key_tag", None)
        if staff_bypass(caller):
            ex.db.door_locked = True
            caller.msg("You lock it (staff).")
            return
        if not has_key(caller, tag):
            caller.msg("You lack the right key.")
            return
        ex.db.door_locked = True
        caller.msg("You lock it.")


class CmdUnlock(Command):
    """
    Unlock a vehicle (biometric) or a door on an exit.

    From inside a vehicle cabin, |wunlock|n, |wunlock here|n, or a matching name unlocks that vehicle.

    Usage:
        unlock <vehicle>
        unlock here   (inside cabin)
        unlock        (inside cabin)
        unlock <direction>
    """

    key = "unlock"
    aliases = ["unlockvehicle", "vunlock", "unlockcar"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from commands.door_cmds import find_exit_by_direction
        from world.rpg.factions.doors import has_key, staff_bypass
        from world.vehicles.vehicle_security import unlock_vehicle

        caller = self.caller
        loc = caller.location
        if not loc:
            return

        veh = resolve_vehicle_for_caller(caller, self.args or "")
        if veh:
            ok, msg = unlock_vehicle(veh, caller)
            caller.msg(msg if ok else f"|r{msg}|n")
            return

        arg = (self.args or "").strip()
        if not arg:
            caller.msg(
                "Unlock what? Usage: |wunlock <vehicle>|n, |wunlock here|n or |wunlock|n from inside a vehicle, "
                "or |wunlock <direction>|n (door)."
            )
            return

        ex = find_exit_by_direction(caller, arg)
        if not ex:
            caller.msg("You don't see that here.")
            return
        if not getattr(ex.db, "door", None):
            caller.msg("There is no door there.")
            return
        if not getattr(ex.db, "door_locked", None):
            caller.msg("It's not locked.")
            return
        tag = getattr(ex.db, "door_key_tag", None)
        if staff_bypass(caller):
            ex.db.door_locked = False
            caller.msg("You unlock it (staff).")
            return
        if not has_key(caller, tag):
            caller.msg("You lack the right key.")
            return
        ex.db.door_locked = False
        caller.msg("You unlock it.")
