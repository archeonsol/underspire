"""Biometric vehicle security: authorize, break-in, hotwire."""

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


class CmdAuthorize(Command):
    key = "authorize"
    aliases = ["auth"]
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        al = args.lower()
        perms = None
        if " full on " in al:
            parts = args.split(" full on ", 1)
            if len(parts) < 2:
                caller.msg("Usage: authorize <name> full on <vehicle>")
                return
            name_str = parts[0].strip()
            veh_part = parts[1].strip()
            perms = {"full"}
        elif " to " in al and " on " in al:
            try:
                before, rest = args.split(" to ", 1)
                perm_part, veh_part = rest.rsplit(" on ", 1)
                name_str = before.strip()
                perms = {p.strip() for p in perm_part.split(",") if p.strip()}
            except ValueError:
                caller.msg("Usage: authorize <name> to <permission> on <vehicle>")
                return
        else:
            caller.msg("Usage: authorize <name> to <permission> on <vehicle> | authorize <name> full on <vehicle>")
            return
        if not perms:
            caller.msg("No permissions specified.")
            return

        loc = caller.location
        if not loc:
            return
        try:
            from typeclasses.vehicles import Vehicle
            from world.vehicles.vehicle_security import authorize_character, resolve_recog_to_character
        except ImportError:
            return

        vehicle = resolve_vehicle_for_caller(caller, veh_part.strip())
        if not vehicle or not isinstance(vehicle, Vehicle):
            caller.msg("No such vehicle here.")
            return
        target = resolve_recog_to_character(caller, name_str)
        if not target:
            caller.msg(f"You don't recognize anyone as '{name_str}'.")
            return
        ok, msg = authorize_character(vehicle, caller, target, perms)
        caller.msg(f"|g{msg}|n" if ok else f"|r{msg}|n")


class CmdDeauthorize(Command):
    key = "deauthorize"
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        loc = caller.location
        if not loc:
            return
        try:
            from typeclasses.vehicles import Vehicle
            from world.vehicles.vehicle_security import deauthorize_character, resolve_recog_to_character
        except ImportError:
            return
        if " from " in args.lower() and " on " in args.lower():
            try:
                name_part, rest = args.split(" from ", 1)
                perm_or_empty, veh_part = rest.rsplit(" on ", 1)
                name_str = name_part.strip()
                perms = {p.strip() for p in perm_or_empty.split(",") if p.strip()} if perm_or_empty.strip() else None
            except ValueError:
                caller.msg("Usage: deauthorize <name> from <vehicle> | deauthorize <name> from <perm> on <vehicle>")
                return
        elif " from " in args.lower():
            parts = args.split(" from ", 1)
            name_str = parts[0].strip()
            veh_part = parts[1].strip()
            perms = None
        else:
            caller.msg("Usage: deauthorize <name> from <vehicle>")
            return
        vehicle = resolve_vehicle_for_caller(caller, veh_part.strip())
        if not vehicle or not isinstance(vehicle, Vehicle):
            caller.msg("No such vehicle here.")
            return
        target = resolve_recog_to_character(caller, name_str)
        if not target:
            caller.msg("You don't recognize that name.")
            return
        ok, msg = deauthorize_character(vehicle, caller, target, perms)
        caller.msg(f"|g{msg}|n" if ok else f"|r{msg}|n")


class CmdAuthorizations(Command):
    """
    Show biometric tier, lock state, owner, and delegated permissions.

    Owner appears as |wOwner:|n when |wsecurity_owner|n is set (e.g. staff |wspawnitem|n vehicle).
    """

    key = "authorizations"
    aliases = ["auths", "vehicle access"]
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        from evennia.utils.search import search_object

        caller = self.caller
        loc = caller.location
        if not loc:
            return
        arg = (self.args or "").strip()
        try:
            from typeclasses.vehicles import Vehicle
            from world.vehicle_parts import get_part_condition
            from world.vehicles.vehicle_security import SECURITY_TIERS, _can_authorize
        except ImportError:
            return
        vehicle = resolve_vehicle_for_caller(caller, arg)
        if not arg and not vehicle:
            caller.msg("Usage: authorizations <vehicle> | authorizations (inside a vehicle)")
            return
        if not vehicle or not isinstance(vehicle, Vehicle):
            caller.msg("No such vehicle.")
            return
        if not _can_authorize(vehicle, caller):
            caller.msg("You can't view authorizations on this vehicle.")
            return
        owner_id = getattr(vehicle.db, "security_owner", None)
        tier = int(getattr(vehicle.db, "security_tier", 1) or 1)
        tier_data = SECURITY_TIERS.get(tier, {})
        lines = [
            f"|x{'=' * 48}|n",
            f"  |w{vehicle_label(vehicle).upper()} — SECURITY|n",
            f"  System: {tier_data.get('name', 'Unknown')} (Tier {tier})",
            f"  Condition: {get_part_condition(vehicle, 'security')}%",
            f"  Status: {'|RLOCKED|n' if getattr(vehicle.db, 'security_locked', False) else '|gUNLOCKED|n'}",
            f"  Hotwired: {'|RYES|n' if getattr(vehicle.db, 'security_hotwired', False) else '|xNo|n'}",
            f"|x{'=' * 48}|n",
        ]
        if owner_id:
            ow = search_object(f"#{owner_id}")
            owner_name = ow[0].key if ow else f"#{owner_id}"
            recog = getattr(caller.db, "recog", None) or {}
            disp = recog.get(owner_id, owner_name)
            lines.append(f"  |wOwner:|n {disp}")
        auths = getattr(vehicle.db, "security_authorizations", None) or {}
        if auths:
            lines.append("  |wAuthorized:|n")
            recog = getattr(caller.db, "recog", None) or {}
            for tid, perms in auths.items():
                ch = search_object(f"#{tid}")
                cn = ch[0].key if ch else f"#{tid}"
                disp = recog.get(tid, cn)
                pl = perms if isinstance(perms, (list, set, tuple)) else [perms]
                lines.append(f"    {disp}: {', '.join(sorted(pl))}")
        else:
            lines.append("  No additional authorizations.")
        lines.append(f"|x{'=' * 48}|n")
        caller.msg("\n".join(lines))


class CmdTransferVehicle(Command):
    key = "transfervehicle"
    aliases = ["transfer vehicle"]
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if " to " not in args.lower():
            caller.msg("Usage: transfervehicle <vehicle> to <name>")
            return
        vpart, namepart = args.split(" to ", 1)
        loc = caller.location
        if not loc:
            return
        try:
            from typeclasses.vehicles import Vehicle
            from world.vehicles.vehicle_security import resolve_recog_to_character, transfer_ownership
        except ImportError:
            return
        vehicle = resolve_vehicle_for_caller(caller, vpart.strip())
        if not vehicle or not isinstance(vehicle, Vehicle):
            caller.msg("No such vehicle here.")
            return
        target = resolve_recog_to_character(caller, namepart.strip())
        if not target:
            caller.msg("You don't recognize that name.")
            return
        ok, msg = transfer_ownership(vehicle, caller, target)
        caller.msg(f"|g{msg}|n" if ok else f"|r{msg}|n")


def _break_in_flavor(caller_id, tier, stage):
    from evennia.utils.search import search_object

    results = search_object(f"#{caller_id}")
    if not results:
        return
    caller = results[0]
    if not getattr(caller.ndb, "_break_in_started", False):
        return
    msgs = {
        1: {1: "The probe hums. LEDs flicker.", 2: "The scanner cycles.", 3: "The lock clicks once."},
        2: {1: "Data scrolls on the probe.", 2: "The scanner pulses.", 3: "Second handshake layer."},
    }
    tg = min(2, (tier + 1) // 2)
    m = msgs.get(tg, msgs[1]).get(stage)
    if m:
        caller.msg(f"|x{m}|n")


def _resolve_break_in(caller_id, vehicle_id):
    from evennia.utils.search import search_object

    from world.vehicles.vehicle_security import attempt_break_in

    rc = search_object(f"#{caller_id}")
    rv = search_object(f"#{vehicle_id}")
    if not rc or not rv:
        return
    caller, vehicle = rc[0], rv[0]
    if not getattr(caller.ndb, "_break_in_started", False):
        return
    if getattr(caller.ndb, "_break_in_vehicle", None) != vehicle.id:
        return
    caller.ndb._break_in_started = False
    caller.ndb._break_in_vehicle = None
    if caller.location != vehicle.location:
        caller.msg("|rYou moved away from the vehicle. Attempt aborted.|n")
        return
    ok, msg = attempt_break_in(caller, vehicle)
    lab = vehicle_label(vehicle)
    if ok:
        caller.msg(f"|gThe panel blinks green. {lab} unlocks.|n")
        loc = vehicle.location
        if loc:
            loc.msg_contents(
                "A soft click from {v}. The lock disengages.",
                exclude=caller,
                mapping={"v": lab},
            )
    else:
        caller.msg(f"|r{msg}|n")


class CmdBreakIn(Command):
    key = "break-in"
    aliases = ["breakin", "bypass"]
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        from evennia.utils import delay

        caller = self.caller
        if not self.args:
            caller.msg("Usage: break-in <vehicle>")
            return
        loc = caller.location
        if not loc:
            return
        try:
            from typeclasses.vehicles import Vehicle
        except ImportError:
            return
        from world.vehicles.vehicle_security import _find_bypass_probe, effective_security_tier

        vehicle = caller.search(self.args.strip(), location=loc)
        if not vehicle or not isinstance(vehicle, Vehicle):
            return
        if not getattr(vehicle.db, "security_locked", False):
            caller.msg("It's not locked.")
            return
        if getattr(vehicle.db, "security_hotwired", False):
            caller.msg("Security is already bypassed.")
            return
        probe = _find_bypass_probe(caller)
        if not probe:
            caller.msg("You need a bypass probe.")
            return
        tier = effective_security_tier(vehicle)
        probe_max = int(getattr(probe.db, "bypass_max_tier", 1) or 1)
        if tier > probe_max:
            caller.msg("Your probe can't handle this security system.")
            return
        lab = vehicle_label(vehicle)
        caller.msg(f"You press the bypass probe against {lab}'s biometric panel.")
        loc.msg_contents(
            "{n} crouches by {v} and presses something against the door panel.",
            exclude=caller,
            mapping={"n": caller, "v": lab},
        )
        caller.ndb._break_in_vehicle = vehicle.id
        caller.ndb._break_in_started = True
        delay_time = 3 + tier
        delay(delay_time, _resolve_break_in, caller.id, vehicle.id)
        delay(2, _break_in_flavor, caller.id, tier, 1)
        if tier >= 3:
            delay(4, _break_in_flavor, caller.id, tier, 2)


def _resolve_hotwire(caller_id, vehicle_id):
    from evennia.utils.search import search_object

    from world.vehicles.vehicle_security import attempt_hotwire

    rc = search_object(f"#{caller_id}")
    rv = search_object(f"#{vehicle_id}")
    if not rc or not rv:
        return
    caller, vehicle = rc[0], rv[0]
    if not getattr(caller.ndb, "_hotwire_started", False):
        return
    caller.ndb._hotwire_started = False
    caller.ndb._hotwire_vehicle = None
    loc = vehicle.location
    int_ok = caller.location == loc or getattr(caller.db, "mounted_on", None) == vehicle
    if not int_ok:
        caller.msg("|rYou lost contact with the vehicle. Hotwire aborted.|n")
        return
    ok, msg = attempt_hotwire(caller, vehicle)
    if ok:
        caller.msg("|gThe harness bridges. The engine catches.|n")
    else:
        caller.msg(f"|r{msg}|n")


class CmdHotwire(Command):
    key = "hotwire"
    aliases = ["hot-wire", "splice"]
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        from evennia.utils import delay

        caller = self.caller
        try:
            from typeclasses.vehicles import Vehicle
            from world.vehicles.vehicle_security import _find_splice_kit, effective_security_tier
        except ImportError:
            return
        from commands.vehicle_cmds import _get_vehicle_from_caller

        vehicle = _get_vehicle_from_caller(caller)
        if not vehicle or not isinstance(vehicle, Vehicle):
            caller.msg("You need to be inside or on the vehicle.")
            return
        if getattr(vehicle.db, "security_locked", False):
            caller.msg("The vehicle is still locked.")
            return
        kit = _find_splice_kit(caller)
        if not kit:
            caller.msg("You need a splice kit.")
            return
        tier = effective_security_tier(vehicle)
        km = int(getattr(kit.db, "splice_max_tier", 1) or 1)
        if tier > km:
            caller.msg("Your kit can't handle this security tier.")
            return
        caller.ndb._hotwire_started = True
        caller.ndb._hotwire_vehicle = vehicle.id
        caller.msg("You expose the ignition harness and start bridging leads...")
        delay(5 + tier, _resolve_hotwire, caller.id, vehicle.id)


