"""
Builder-only vehicle testing: spawn catalog weapons onto mounts, set part mods (types), full repair.
"""

from __future__ import annotations

from commands.base_cmds import Command


def _vehicle_in_room(caller, name: str):
    """Resolve a vehicle in the caller's room (ground object or aerial)."""
    try:
        from typeclasses.vehicles import AerialVehicle, Motorcycle, Vehicle
    except ImportError:
        return None
    loc = caller.location
    if not loc:
        return None
    obj = caller.search(name, location=loc)
    if not obj:
        return None
    if isinstance(obj, (Vehicle, Motorcycle, AerialVehicle)):
        return obj
    return None


class CmdVweaponKeys(Command):
    """Staff: list vehicle weapon catalog keys. Usage: vweaponkeys"""

    key = "vweaponkeys"
    aliases = ["weaponcatalog", "listvweapons"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        from world.combat.vehicle_weapons import VEHICLE_WEAPONS

        keys = sorted(VEHICLE_WEAPONS.keys())
        self.caller.msg("|wVehicle weapon catalog:|n " + ", ".join(keys))


class CmdVweaponInstall(Command):
    """
    Staff: create a vehicle weapon from the catalog and mount it (no inventory, no rolls).
    Usage: vweaponinstall <vehicle> <catalog_key> <mount_id>
    Example: vweaponinstall sedan railgun m0
    """
    key = "vweaponinstall"
    aliases = ["vweapon", "installvweapon", "staffmountweapon"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip().split()
        if len(args) >= 1 and args[0].lower() in ("keys", "list", "catalog"):
            from world.combat.vehicle_weapons import VEHICLE_WEAPONS

            keys = sorted(VEHICLE_WEAPONS.keys())
            caller.msg("|wVehicle weapon catalog:|n " + ", ".join(keys))
            return
        if len(args) < 3:
            caller.msg("Usage: |wvweaponinstall <vehicle> <catalog_key> <mount_id>|n  |x(or |wvweaponkeys|x for list)|n")
            return
        vname, catalog_key, mount_id = args[0], args[1], args[2]
        vehicle = _vehicle_in_room(caller, vname)
        if not vehicle:
            caller.msg("No vehicle by that name here.")
            return
        from world.combat.vehicle_weapons import VEHICLE_WEAPONS

        data = VEHICLE_WEAPONS.get(catalog_key)
        if not data:
            caller.msg(f"Unknown catalog key |w{catalog_key}|n. Use |wvweaponkeys|n.")
            return
        meta = getattr(vehicle.db, "weapon_mount_types", None) or {}
        if mount_id not in meta and meta:
            caller.msg(
                f"|yMount |w{mount_id}|n not in schema {list(meta.keys())}. Installing anyway (staff).|n"
            )
        try:
            from evennia.utils.create import create_object
        except ImportError as e:
            caller.msg(f"|rCannot create weapon: {e}|n")
            return
        wname = data.get("name", catalog_key)
        weapon = create_object(
            "typeclasses.vehicle_weapon_item.VehicleWeapon",
            key=wname,
            location=vehicle,
        )
        weapon.apply_catalog(catalog_key)
        mounts = dict(getattr(vehicle.db, "weapon_mounts", None) or {})
        mounts[mount_id] = weapon
        vehicle.db.weapon_mounts = mounts
        weapon.db.installed_on = vehicle.id
        caller.msg(f"|gInstalled|n |w{catalog_key}|n on |w{vehicle.key}|n mount |w{mount_id}|n.")


class CmdVweaponRemove(Command):
    """
    Staff: remove a mounted weapon from a vehicle (destroy the weapon object).
    Usage: vweaponremove <vehicle> <mount_id>
    """
    key = "vweaponremove"
    aliases = ["uninstallvweapon", "staffunmountweapon"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip().split()
        if len(args) < 2:
            caller.msg("Usage: |wvweaponremove <vehicle> <mount_id>|n")
            return
        vehicle = _vehicle_in_room(caller, args[0])
        if not vehicle:
            caller.msg("No vehicle by that name here.")
            return
        mount_id = args[1]
        mounts = dict(getattr(vehicle.db, "weapon_mounts", None) or {})
        w = mounts.pop(mount_id, None)
        vehicle.db.weapon_mounts = mounts
        if not w:
            caller.msg(f"No weapon on mount |w{mount_id}|n.")
            return
        try:
            w.delete()
        except Exception:
            pass
        caller.msg(f"|gRemoved|n mount |w{mount_id}|n from |w{vehicle.key}|n.")


class CmdVmod(Command):
    """
    Staff: set a vehicle part mod (installed type id from PART_TYPE_OPTIONS).
    Usage: vmod <vehicle> <part_id> <type_id>
    Use |wvmodtypes <part_id>|n to see valid type ids.
    """
    key = "vmod"
    aliases = ["vehiclemod", "setvparttype"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip().split()
        if len(args) < 3:
            caller.msg("Usage: |wvmod <vehicle> <part_id> <type_id>|n")
            return
        vehicle = _vehicle_in_room(caller, args[0])
        if not vehicle:
            caller.msg("No vehicle by that name here.")
            return
        part_id = args[1].lower().replace(" ", "_")
        type_id = args[2].lower().replace(" ", "_")
        from world.vehicle_parts import (
            PART_TYPE_OPTIONS,
            get_part_ids,
            get_part_display_name,
            set_part_type_id,
        )

        valid_parts = get_part_ids(vehicle)
        if part_id not in valid_parts:
            caller.msg(f"Invalid part for this vehicle. Valid: {', '.join(valid_parts)}")
            return
        opts = PART_TYPE_OPTIONS.get(part_id, [])
        valid_ids = [t["id"] for t in opts]
        if not set_part_type_id(vehicle, part_id, type_id):
            caller.msg(
                f"Invalid type |w{type_id}|n for |w{part_id}|n. Valid: {', '.join(valid_ids) or 'none'}"
            )
            return
        pname = get_part_display_name(part_id)
        caller.msg(f"|gSet|n {vehicle.key} |w{pname}|n → type |w{type_id}|n.")


class CmdVmodtypes(Command):
    """
    Staff: list part ids that have mod options, or list type ids for one part.
    Usage:
      vmodtypes
      vmodtypes <part_id>
    """
    key = "vmodtypes"
    aliases = ["vparttypes", "vehicleparttypes"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        arg = (self.args or "").strip()
        from world.vehicle_parts import PART_TYPE_OPTIONS

        if not arg:
            keys = sorted(PART_TYPE_OPTIONS.keys())
            caller.msg("|wParts with type options:|n " + ", ".join(keys))
            return
        part_id = arg.lower().replace(" ", "_")
        opts = PART_TYPE_OPTIONS.get(part_id)
        if not opts:
            caller.msg(f"No options for |w{part_id}|n. Try |wvmodtypes|n without args.")
            return
        lines = []
        for t in opts:
            tid = t.get("id", "?")
            name = t.get("name", tid)
            lines.append(f"  |w{tid}|n — {name}")
        caller.msg(f"Types for |w{part_id}|n:\n" + "\n".join(lines))


class CmdVrepair(Command):
    """
    Staff: restore vehicle hull HP, clear combat damage flags, repair all parts to 100%, top off mounted weapons.
    Usage:
      vrepair <vehicle>           — full (hull + parts + weapons)
      vrepair <vehicle> hull      — hull HP only
      vrepair <vehicle> parts     — subsystem parts only (no hull)
    """
    key = "vrepair"
    aliases = ["vfix", "vehiclefix", "staffvrepair"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        parts = (self.args or "").strip().split()
        if not parts:
            caller.msg("Usage: |wvrepair <vehicle> [hull|parts]|n")
            return
        vehicle = _vehicle_in_room(caller, parts[0])
        if not vehicle:
            caller.msg("No vehicle by that name here.")
            return
        mode = (parts[1].lower() if len(parts) > 1 else "full")
        try:
            from world.combat.vehicle_combat import init_vehicle_hp_for_type
            from world.vehicle_parts import get_part_ids, refresh_vehicle_armor, set_part_condition
        except ImportError:
            caller.msg("|rVehicle repair helpers not available.|n")
            return

        init_vehicle_hp_for_type(vehicle)
        max_hp = int(getattr(vehicle.db, "vehicle_max_hp", 100) or 100)

        if mode in ("full", "hull"):
            vehicle.db.vehicle_hp = max_hp
            vehicle.db.vehicle_destroyed = False
            caller.msg(f"Hull → {max_hp}.")

        if mode in ("full", "parts"):
            for pid in get_part_ids(vehicle):
                set_part_condition(vehicle, pid, 100)
            refresh_vehicle_armor(vehicle)
            caller.msg("All parts → 100%. Armor refreshed.")

        if mode == "full":
            mounts = getattr(vehicle.db, "weapon_mounts", None) or {}
            for w in mounts.values():
                if not w or not getattr(w, "db", None):
                    continue
                cap = int(getattr(w.db, "ammo_capacity", 0) or 0)
                if cap > 0:
                    w.db.ammo_current = cap
                w.db.weapon_condition = 100.0
            for attr in (
                "burning_ticks",
                "burning_damage",
                "emp_disabled_until",
                "tethered_to",
                "tethered_by",
                "spun_out_until",
                "entangled_until",
            ):
                if hasattr(vehicle.db, attr):
                    try:
                        delattr(vehicle.db, attr)
                    except Exception:
                        setattr(vehicle.db, attr, None)
            try:
                vehicle.db.engine_running = bool(getattr(vehicle.db, "engine_running", False))
            except Exception:
                pass
            caller.msg("Mounted weapons refilled/reconditioned. Status flags cleared.")

        if mode not in ("full", "hull", "parts"):
            caller.msg("|yUnknown mode; use hull, parts, or omit for full.|n")
