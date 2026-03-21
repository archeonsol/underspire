"""
Global use command — dispatches to cyberware station, perfume, medical tools,
networked devices (Matrix hardware), or generic at_use.

Former `operate` / `op` behavior is merged here: use <device> opens the device menu.
"""

from commands.base_cmds import Command, _command_character
from commands.inventory_cmds import _obj_in_hands
from commands.medical_cmds import _resolve_medical_target


def _resolve_use_object(caller, obj_name):
    """Find object by name in caller's inventory, then in room."""
    obj = caller.search(obj_name, location=caller, quiet=True)
    if not obj and caller.location:
        obj = caller.search(obj_name, location=caller.location, quiet=True)
    if not obj:
        return None
    return obj[0] if isinstance(obj, (list, tuple)) else obj


class CmdUse(Command):
    """
    Use an object. Dispatches to cyberware station, perfume, medical tools,
    networked devices, or generic at_use.

    Usage:
      use <object> [on <target>]
      use                    — from inside a device interface room, opens that device

    Examples:
      put cyberarm in cyberware customization station
      use cyberware customization station   — customize chrome (requires EE 75)

      wield perfume
      use perfume   or   use perfume on me   — apply scent to self

      wield scanner
      use scanner on Bob   — bioscanner readout

      use hub   or   use handset   — open networked device menu (same as former |woperate|n)
    """
    key = "use"
    aliases = ["operate", "op"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        args = (self.args or "").strip()
        if not args:
            room = caller.location
            if room and hasattr(room.db, "parent_object") and room.db.parent_object:
                device = room.db.parent_object
                from typeclasses.matrix.mixins import NetworkedMixin
                if isinstance(device, NetworkedMixin):
                    from typeclasses.matrix.device_menu import start_device_menu
                    from typeclasses.matrix.avatars import MatrixAvatar
                    from_matrix = isinstance(caller, MatrixAvatar)
                    start_device_menu(caller, device, from_matrix=from_matrix)
                    return
            caller.msg("Usage: use <object> [on <target>]")
            return

        parts = args.split(None, 2)
        obj_name = parts[0]
        target = caller
        if len(parts) >= 3 and parts[1].lower() == "on":
            target = _resolve_medical_target(caller, parts[2], location=caller.location)
            if not target:
                return
            if not hasattr(target, "db"):
                caller.msg("You cannot use that on them.")
                return

        obj = _resolve_use_object(caller, obj_name)
        if not obj:
            return

        # 1. Cyberware Customization Station
        try:
            from typeclasses.cyberware_station import CyberwareCustomizationStation
            from typeclasses.cyberware import CyberwareBase
            from world.chromework_menu import CHROMOWORK_SKILL, CHROMOWORK_MIN_SKILL, start_chromework_menu
        except ImportError:
            CyberwareCustomizationStation = None

        if CyberwareCustomizationStation and isinstance(obj, CyberwareCustomizationStation):
            if not hasattr(caller, "get_skill_level"):
                caller.msg("You cannot use that.")
                return
            if caller.get_skill_level(CHROMOWORK_SKILL) < CHROMOWORK_MIN_SKILL:
                caller.msg(
                    f"The station requires {CHROMOWORK_SKILL.replace('_', ' ')} {CHROMOWORK_MIN_SKILL}+. "
                    "You lack the skill to operate it."
                )
                return
            cw_list = [c for c in obj.contents if isinstance(c, CyberwareBase)]
            if not cw_list:
                caller.msg("Put a piece of cyberware in the station first (|wput <cyberware> in cyberware customization station|n).")
                return
            if len(cw_list) > 1:
                caller.msg("There is too much chrome in the station. Retrieve some first.")
                return
            cyberware = cw_list[0]
            caller.msg(
                "|xYou settle in at the station, adjust the laser head, and power up the calibration screens. "
                "The machinery hums as you prepare to customize the chrome.|n"
            )
            start_chromework_menu(caller, obj, cyberware)
            return

        # 2. Perfume — self-only, must be wielded
        try:
            from typeclasses.perfume import Perfume
        except ImportError:
            Perfume = None

        if Perfume and isinstance(obj, Perfume):
            if target != caller:
                caller.msg("You can only apply perfume to yourself.")
                return
            if not _obj_in_hands(caller, obj):
                caller.msg("You need to hold that in your hands to use it. Wield it first (|wwield %s|n)." % obj_name)
                return
            obj.at_use(caller)
            return

        # 3. Medical tools — must be wielded
        try:
            from typeclasses.medical_tools import MedicalTool, Bioscanner, Defibrillator
        except ImportError:
            MedicalTool = None
            Bioscanner = None
            Defibrillator = None

        if MedicalTool and isinstance(obj, MedicalTool):
            if not _obj_in_hands(caller, obj):
                caller.msg("You need to hold that in your hands to use it. Wield it first (|wwield %s|n)." % obj_name)
                return
            if getattr(obj.db, "uses_remaining", 1) is not None and (obj.db.uses_remaining or 0) <= 0:
                caller.msg(f"{obj.get_display_name(caller)} is used up.")
                return

            if Defibrillator and isinstance(obj, Defibrillator):
                if not target or target == caller:
                    caller.msg("Use the defibrillator on who? Usage: use defibrillator on <target>")
                    return
                if getattr(target, "hp", 1) > 0:
                    caller.msg("They are not in arrest. The defibrillator is for the dead.")
                    return
                from world.medical.medical_defib import start_defib_sequence
                started, err = start_defib_sequence(caller, target, obj)
                if not started:
                    caller.msg(err or "You cannot do that right now.")
                return

            if Bioscanner and isinstance(obj, Bioscanner):
                success, out = obj.use_for_scan(caller, target)
                if not success:
                    caller.msg(out if isinstance(out, str) else "Scan failed.")
                    return
                if isinstance(out, dict) and out.get("formatted"):
                    caller.msg(out["formatted"])
                elif isinstance(out, dict):
                    caller.msg(out.get("detail", "No readout."))
                else:
                    caller.msg(out)
                if target != caller:
                    target.msg(f"{(caller.get_display_name(target) if hasattr(caller, 'get_display_name') else caller.name)} runs a scanner over you.")
                return

            caller.msg(
                "To treat, keep the tool in your hands and use: |wapply to %s|n (e.g. apply bandage to %s, apply splint to %s arm)."
                % (target.key if hasattr(target, "key") else target.name,
                   target.key if hasattr(target, "key") else target.name,
                   target.key if hasattr(target, "key") else target.name,)
            )
            return

        # 4. Networked Matrix devices (meatspace device menu; was `operate <device>`)
        try:
            from typeclasses.matrix.mixins import NetworkedMixin
        except ImportError:
            NetworkedMixin = None
        if NetworkedMixin and isinstance(obj, NetworkedMixin):
            # Handsets must be in inventory or in hand, not in the room
            if getattr(getattr(obj, "db", None), "device_type", None) == "handset":
                if getattr(obj, "location", None) != caller:
                    caller.msg("You need to have the handset on you to use it.")
                    return
            from typeclasses.matrix.device_menu import start_device_menu
            start_device_menu(caller, obj, from_matrix=False)
            return

        # 5. Generic at_use
        if hasattr(obj, "at_use") and callable(getattr(obj, "at_use")):
            obj.at_use(caller)
            return

        # 6. Fallback
        caller.msg("You can't use that.")
