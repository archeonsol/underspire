"""Vehicle combat: fire, ram, gunner seat, install, reload, eject."""

from commands.base_cmds import Command

from world.combat.utils import melee_target_blocked_enclosed_cabin


def _vehicle_in_room(caller):
    loc = caller.location
    if not loc:
        return None
    try:
        from typeclasses.vehicles import Vehicle, Motorcycle

        for o in loc.contents:
            if isinstance(o, (Vehicle, Motorcycle)):
                return o
    except ImportError:
        pass
    return None


def _caller_vehicle_context(caller):
    """Return (vehicle, is_driver, is_gunner, is_rider) for motorcycle/interior."""
    try:
        from typeclasses.vehicles import Vehicle, Motorcycle
    except ImportError:
        return None, False, False, False
    bike = getattr(caller.db, "mounted_on", None)
    if bike and isinstance(bike, Motorcycle):
        return bike, True, False, True
    v = getattr(caller.db, "in_vehicle", None)
    if v and isinstance(v, Vehicle):
        is_drv = getattr(v.db, "driver", None) == caller
        is_gun = getattr(v.db, "gunner", None) == caller
        return v, is_drv, is_gun, False
    return None, False, False, False


class CmdFire(Command):
    """
    Fire a vehicle-mounted weapon (optional; use |wattack <target>|n for the same ticker as normal combat).

    Usage:
        fire at <target>
        fire <mount_id> at <target>
    """

    key = "fire"
    aliases = ["shoot", "vfire"]
    locks = "cmd:all()"
    help_category = "Vehicle Combat"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        vehicle, is_drv, is_gun, _rider = _caller_vehicle_context(caller)
        if not vehicle:
            caller.msg("You need to be driving or crewing a vehicle.")
            return
        target = None
        mount_id = "m0"
        mounts = getattr(vehicle.db, "weapon_mounts", None) or {}

        mount_keys = {k.lower(): k for k in mounts}

        def _resolve_mount_token(tok: str) -> str | None:
            t = tok.strip().replace(" ", "")
            if not t:
                return None
            if t in mounts:
                return t
            if t.lower() in mount_keys:
                return mount_keys[t.lower()]
            return None

        ext_room = getattr(vehicle, "location", None) or caller.location
        if not args:
            mount_id = "m0"
        else:
            low = args.lower()
            if low.startswith("at "):
                target = caller.search(args[3:].strip(), location=ext_room)
            elif " at " in low:
                left, _, right = args.partition(" at ")
                left = left.strip()
                right = right.strip()
                if left:
                    m = _resolve_mount_token(left)
                    if m:
                        mount_id = m
                target = caller.search(right, location=ext_room)
            else:
                parts = args.split(None, 1)
                if len(parts) == 1:
                    tok = parts[0]
                    m = _resolve_mount_token(tok)
                    if m:
                        mount_id = m
                    else:
                        target = caller.search(tok, location=ext_room)
                else:
                    target = caller.search(args, location=ext_room)

        from world.combat.vehicle_combat import (
            _get_mount_type,
            announce_vehicle_attack,
            apply_weapon_specials,
            can_fire_mount,
            deploy_weapon,
            is_deployable_weapon,
            resolve_vehicle_weapon_attack,
        )

        weapon = mounts.get(mount_id) or mounts.get(mount_id.lower())
        if not weapon:
            caller.msg("No weapon on that mount.")
            return
        mtype = _get_mount_type(vehicle, mount_id)
        if not can_fire_mount(caller, vehicle, mount_id):
            if not is_drv and not is_gun:
                caller.msg("You're a passenger. Use |wman turret|n to take the gunner station, or |wcontrol|n for the driver's seat.")
            elif is_gun and getattr(vehicle.db, "gunner_mount", None) != mount_id:
                caller.msg("That mount isn't your station. Use |wman turret|n or |wman rear gun|n to switch.")
            else:
                caller.msg("You can't fire that mount from your current position.")
            return

        room = ext_room
        if is_deployable_weapon(weapon):
            ok, msg = deploy_weapon(caller, vehicle, weapon, mount_id)
            caller.msg(msg or ("Deployed." if ok else "Failed."))
            return

        if not target:
            caller.msg("Usage: |wfire at <target>|n or |wfire <mount_id> at <target>|n")
            return

        blocked = melee_target_blocked_enclosed_cabin(caller, target, ext_room)
        if blocked:
            caller.msg(blocked)
            return

        hit, tier, dmg, dtype = resolve_vehicle_weapon_attack(caller, vehicle, weapon, target, mtype)
        if tier == "empty":
            caller.msg("The weapon is empty.")
            return
        if tier == "cooldown":
            caller.msg(dtype or "Weapon cycling.")
            return
        announce_vehicle_attack(room, vehicle, target, weapon, hit, tier or "")
        apply_weapon_specials(weapon, vehicle, target, hit, room)
        if hit and not hasattr(target, "vehicle_type"):
            if hasattr(target, "at_damage"):
                target.at_damage(caller, int(dmg), weapon_key=dtype or "fists")
        if hit and hasattr(target, "db") and getattr(target.db, "vehicle_hp", None) is not None:
            caller.msg(f"|yHull damage: {dmg}|n")


class CmdRam(Command):
    key = "ram"
    locks = "cmd:all()"
    help_category = "Vehicle Combat"

    def func(self):
        caller = self.caller
        vehicle, is_drv, _, _ = _caller_vehicle_context(caller)
        if not vehicle or not is_drv:
            caller.msg("You need to be driving a vehicle to ram.")
            return
        if not self.args:
            caller.msg("Ram what? |wram <target>|n")
            return
        ext = getattr(vehicle, "location", None) or caller.location
        target = caller.search(self.args.strip(), location=ext)
        if not target:
            return
        blocked = melee_target_blocked_enclosed_cabin(caller, target, ext)
        if blocked:
            caller.msg(blocked)
            return
        from world.combat.vehicle_combat import resolve_ram

        ok, kind = resolve_ram(vehicle, caller, target)
        if not ok:
            if kind == "recovery":
                caller.msg("|yYou need to line up another ram — still recovering from the last impact.|n")
            else:
                caller.msg("You miss the ram.")
        else:
            caller.msg("|rImpact.|n")


class CmdManGunner(Command):
    """Take gunner seat for a turret mount."""

    key = "man"
    locks = "cmd:all()"
    help_category = "Vehicle Combat"

    def func(self):
        caller = self.caller
        rest = (self.args or "").strip().lower()
        vehicle = getattr(caller.db, "in_vehicle", None)
        if not vehicle:
            caller.msg("You must be inside a vehicle.")
            return
        mount_types = getattr(vehicle.db, "weapon_mount_types", None) or {}
        weapon_mounts = getattr(vehicle.db, "weapon_mounts", None) or {}
        if rest.startswith("turret"):
            wanted_type = "turret"
            station = "turret"
        elif "rear" in rest:
            wanted_type = "rear"
            station = "rear gun"
        else:
            caller.msg("Usage: |wman turret|n or |wman rear gun|n")
            return
        # Find the first mount that has the right type AND has a weapon installed
        mount_id = None
        for mid in sorted(weapon_mounts.keys()):
            if mount_types.get(mid) == wanted_type and weapon_mounts.get(mid):
                mount_id = mid
                break
        # Fallback: first mount of the right type even without a weapon
        if mount_id is None:
            for mid in sorted(mount_types.keys()):
                if mount_types.get(mid) == wanted_type:
                    mount_id = mid
                    break
        if mount_id is None:
            caller.msg(f"This vehicle has no {station} mount.")
            return
        # Already on this exact station — no-op
        if getattr(vehicle.db, "gunner", None) == caller and getattr(vehicle.db, "gunner_mount", None) == mount_id:
            caller.msg(f"You are already manning the {station}.")
            return
        # Station occupied by someone else
        cur_gunner = getattr(vehicle.db, "gunner", None)
        if cur_gunner and cur_gunner != caller and getattr(vehicle.db, "gunner_mount", None) == mount_id:
            gname = cur_gunner.get_display_name(caller) if hasattr(cur_gunner, "get_display_name") else str(cur_gunner)
            caller.msg(f"The {station} is already manned by {gname}.")
            return
        # Leave the driver's seat if currently driving
        if getattr(vehicle.db, "driver", None) == caller:
            vehicle.db.driver = None
        vehicle.db.gunner = caller
        vehicle.db.gunner_mount = mount_id
        caller.msg(f"You move to the {station}.")
        interior = getattr(vehicle.db, "interior", None)
        if interior and hasattr(interior, "msg_contents"):
            interior.msg_contents(
                f"|w{caller.get_display_name(caller)} moves to the {station}.|n",
                exclude=[caller],
            )


class CmdLeaveGunner(Command):
    key = "gunnerout"
    aliases = ["leavegun", "leave guns"]
    locks = "cmd:all()"
    help_category = "Vehicle Combat"

    def func(self):
        caller = self.caller
        vehicle = getattr(caller.db, "in_vehicle", None)
        if not vehicle:
            return
        if getattr(vehicle.db, "gunner", None) == caller:
            vehicle.db.gunner = None
            vehicle.db.gunner_mount = None
            caller.msg("You leave the gunner station.")
        else:
            caller.msg("You aren't on the guns.")


class CmdEject(Command):
    key = "eject"
    locks = "cmd:all()"
    help_category = "Vehicle Combat"

    def func(self):
        caller = self.caller
        vehicle = getattr(caller.db, "in_vehicle", None)
        if not vehicle:
            caller.msg("You aren't in a vehicle.")
            return
        # Placeholder: eject occupant — staff/driver only
        caller.msg("Eject: target a passenger (not fully implemented).")


class CmdInstallVehicleWeapon(Command):
    key = "mountweapon"
    aliases = ["installweapon", "weaponinstall"]
    locks = "cmd:all()"
    help_category = "Vehicle Combat"

    def func(self):
        caller = self.caller
        from world.combat.vehicle_combat import WEAPON_INSTALL_DIFFICULTY, WEAPON_INSTALL_DURATION

        args = (self.args or "").strip().split()
        if len(args) < 2:
            caller.msg("Usage: |wmountweapon <weapon in inventory> <mount_id>|n (vehicle in same room, engine off)")
            return
        mount_id = args[-1]
        wname = " ".join(args[:-1])
        weapon = caller.search(wname, location=caller)
        if not weapon:
            return
        try:
            from typeclasses.vehicle_weapon_item import VehicleWeapon
        except ImportError:
            VehicleWeapon = None
        if VehicleWeapon and not isinstance(weapon, VehicleWeapon):
            caller.msg("That isn't a vehicle weapon.")
            return
        vehicle = _vehicle_in_room(caller)
        if not vehicle:
            caller.msg("No vehicle here.")
            return
        if getattr(vehicle.db, "engine_running", False):
            caller.msg("Shut the engine off first.")
            return
        from world.combat.vehicle_combat import _get_mount_type

        mtype = _get_mount_type(vehicle, mount_id)
        diff = WEAPON_INSTALL_DIFFICULTY.get(mtype, 25)
        dur = WEAPON_INSTALL_DURATION.get(mtype, 40)
        tier, _ = caller.roll_check(["intelligence", "strength"], "mechanical_engineering", difficulty=diff)
        if tier in ("Failure",):
            caller.msg("You can't get the mounting to line up.")
            return
        if weapon.location != vehicle:
            weapon.move_to(vehicle, quiet=True)
        mounts = getattr(vehicle.db, "weapon_mounts", None) or {}
        mounts[mount_id] = weapon
        vehicle.db.weapon_mounts = mounts
        weapon.db.installed_on = vehicle.id
        caller.msg(f"You install the weapon on {mount_id} ({dur}s).")


class CmdUninstallVehicleWeapon(Command):
    key = "unmountweapon"
    aliases = ["uninstallweapon"]
    locks = "cmd:all()"
    help_category = "Vehicle Combat"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Usage: |wunmountweapon <mount_id>|n")
            return
        mount_id = self.args.strip().split()[0]
        vehicle = _vehicle_in_room(caller)
        if not vehicle:
            return
        mounts = getattr(vehicle.db, "weapon_mounts", None) or {}
        w = mounts.pop(mount_id, None)
        vehicle.db.weapon_mounts = mounts
        if w:
            w.move_to(caller, quiet=True)
            caller.msg("Weapon removed to your inventory.")


class CmdReloadVehicleWeapon(Command):
    key = "vreload"
    aliases = ["reload weapon", "reload mount"]
    locks = "cmd:all()"
    help_category = "Vehicle Combat"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        vehicle, is_drv, is_gun, _ = _caller_vehicle_context(caller)
        if not vehicle:
            caller.msg("You need to be with your vehicle.")
            return
        if not is_drv and not is_gun:
            caller.msg("You're a passenger. Use |wman turret|n to take the gunner station first.")
            return
        mounts = getattr(vehicle.db, "weapon_mounts", None) or {}
        from world.combat.vehicle_combat import _get_mount_type, can_fire_mount

        target_mid = args if args in mounts else "m0"
        w = mounts.get(target_mid)
        if not w:
            caller.msg("No weapon on that mount.")
            return
        if not can_fire_mount(caller, vehicle, target_mid):
            mtype = _get_mount_type(vehicle, target_mid)
            if is_gun and mtype in ("turret", "rear", "underbelly"):
                caller.msg("That isn't your station. Use |wman turret|n or |wman rear gun|n first.")
            else:
                caller.msg("You can't reload that mount from your current position.")
            return
        cap = int(getattr(w.db, "ammo_capacity", 0) or 0)
        if cap <= 0:
            caller.msg("That weapon doesn't need reloading.")
            return
        current = int(getattr(w.db, "ammo_current", 0) or 0)
        if current >= cap:
            caller.msg("That weapon is already full.")
            return
        needed = cap - current
        # find ammo object in inventory
        key = getattr(w.db, "weapon_key", "")
        for o in caller.contents:
            if getattr(o.db, "ammo_for", None) == key:
                cnt = int(getattr(o.db, "ammo_count", 0) or 0)
                if cnt <= 0:
                    continue
                load = min(needed, cnt)
                w.db.ammo_current = current + load
                remaining = cnt - load
                if remaining <= 0:
                    o.delete()
                else:
                    o.db.ammo_count = remaining
                caller.msg(f"You reload {load} rounds.")
                return
        caller.msg("You need compatible ammo.")


class CmdDislodgeHarpoon(Command):
    key = "dislodge"
    locks = "cmd:all()"
    help_category = "Vehicle Combat"

    def func(self):
        self.caller.msg("Get close and use strength + mechanical engineering (stub).")
