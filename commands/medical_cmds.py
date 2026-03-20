"""
Medical commands: CmdHt, CmdUse, CmdApply, CmdStabilize, CmdSedate, CmdSurgery, CmdDefib.
"""

from commands.base_cmds import Command
from commands.inventory_cmds import _obj_in_hands
from evennia.utils import logger


class CmdHt(Command):
    """
    Quick health check: condition (HP), rested (stamina), and recovering (stamina regen rate).
    Use on yourself or another; wording uses their pronouns when checking others.

    Usage:
      ht
      ht <target>
    """
    key = "ht"
    aliases = ["diagnose", "diag", "check"]
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.characters.Character"]
    usage_hint = "|wht|n or |wht <target>|n"

    def func(self):
        caller = self.caller
        if not self.args:
            target = caller
        else:
            target = caller.search(self.args)
        if not target:
            return
        if not hasattr(target, "db") or not hasattr(target, "max_hp"):
            caller.msg("You cannot assess that.")
            return
        from world.medical import get_ht_summary, get_diagnose_trauma_for_skill
        first_person = target == caller
        status = get_ht_summary(target, first_person=first_person)
        med_level = getattr(caller, "get_skill_level", lambda s: 0)("medicine")
        extra = get_diagnose_trauma_for_skill(target, med_level)
        if extra:
            status = status + "\n\n" + extra
        caller.msg(status)


class CmdUse(Command):
    """
    Use a medical tool on a target. The tool must be held in your hands (wield it first).

    Usage:
      use <tool> on <target>
      use <tool>

    Examples:
      wield scanner
      use scanner on Bob   - run bioscanner readout on Bob (detect damage type)
      wield bandage
      apply bandage to Bob  - then use apply to treat (after scanning)

    Scanner gives a readout only; treat with the correct tool using |wapply <item> to <target>|n.
    """
    key = "use"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: use <tool> [on <target>]")
            return
        # Parse "tool on target" or "tool"
        parts = args.split(None, 2)
        tool_name = parts[0]
        target = caller
        if len(parts) >= 3 and parts[1].lower() == "on":
            target = caller.search(parts[2])
            if not target:
                return
            if not hasattr(target, "db"):
                caller.msg("You cannot use that on them.")
                return

        try:
            from typeclasses.medical_tools import MedicalTool, Bioscanner, get_medical_tools_from_inventory
        except ImportError as e:
            logger.log_trace("medical_cmds.CmdUse import medical_tools: %s" % e)
            caller.msg("That is not a medical tool.")
            return
        tool = caller.search(tool_name, location=caller)
        if not tool:
            return
        # Item must be held in either hand to use
        if not _obj_in_hands(caller, tool):
            caller.msg("You need to hold that in your hands to use it. Wield it first (|wwield %s|n)." % tool_name)
            return
        from typeclasses.medical_tools import Defibrillator
        if isinstance(tool, Defibrillator):
            if not target or target == caller:
                caller.msg("Use the defibrillator on who? Usage: use defibrillator on <target>")
                return
            if getattr(target, "hp", 1) > 0:
                caller.msg("They are not in arrest. The defibrillator is for the dead.")
                return
            from world.medical.medical_defib import start_defib_sequence
            started, err = start_defib_sequence(caller, target, tool)
            if not started:
                caller.msg(err or "You cannot do that right now.")
            return

        if not isinstance(tool, MedicalTool):
            caller.msg("You can't use that for medical procedures.")
            return
        if getattr(tool.db, "uses_remaining", 1) is not None and (tool.db.uses_remaining or 0) <= 0:
            caller.msg(f"{tool.get_display_name(caller)} is used up.")
            return

        if isinstance(tool, Bioscanner):
            from world.medical import BIOSCANNER_MIN_MEDICINE
            med_level = getattr(caller, "get_skill_level", lambda s: 0)("medicine")
            if med_level < BIOSCANNER_MIN_MEDICINE:
                caller.msg("You need at least %d medicine skill to operate the bioscanner. You lack the training to interpret its readout." % BIOSCANNER_MIN_MEDICINE)
                return
            success, out = tool.use_for_scan(caller, target)
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

        # Other medical tools: treatment is done via "apply <item> to <target>" with tool wielded
        caller.msg("To treat, keep the tool in your hands and use: |wapply to %s|n (e.g. apply bandage to %s, apply splint to %s arm)." % (
            target.key if hasattr(target, "key") else target.name,
            target.key if hasattr(target, "key") else target.name,
            target.key if hasattr(target, "key") else target.name,
        ))


class CmdSedate(Command):
    """
    Induce anesthesia on the patient currently lying on an operating table.

    Usage:
      sedate <target>
    """
    key = "sedate"
    aliases = ["anesthetize", "anaesthetize", "anesthetise", "anaesthetise"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Sedate whom? Usage: sedate <target>")
            return
        target = caller.search(args, location=caller.location)
        if not target:
            return
        if not hasattr(target, "db"):
            caller.msg("You cannot sedate that.")
            return

        from typeclasses.medical_tools import OperatingTable
        table = None
        for obj in caller.location.contents:
            if isinstance(obj, OperatingTable):
                table = obj
                break
        if not table:
            caller.msg("There is no operating table here.")
            return
        if table.get_patient() != target:
            caller.msg("They must be the patient lying on the operating table first.")
            return
        success, msg = table.use_for_sedation(caller, target)
        if success:
            caller.msg("|g" + msg + "|n")
        else:
            caller.msg("|r" + (msg or "Sedation failed.") + "|n")


class CmdStabilize(Command):
    """
    Stop or reduce bleeding on a target using bandages or a medkit (or suture kit,
    hemostatic agent, surgical kit) held in your hands. Purely for haemorrhage control.

    Usage:
      stabilize <target>

    You must be wielding a bleeding-capable tool (e.g. wield bandage, then stabilize Bob).
    """
    key = "stabilize"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.medical.medical_treatment import attempt_stop_bleeding, TOOL_CAN_STOP_BLEEDING
        from typeclasses.medical_tools import MedicalTool

        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Stabilize whom? Usage: stabilize <target>")
            return

        # Tool must be in either hand (prefer right)
        left = getattr(caller.db, "left_hand_obj", None)
        right = getattr(caller.db, "right_hand_obj", None)
        tool = None
        if right and right.location == caller and isinstance(right, MedicalTool) and getattr(right.db, "medical_tool_type", None) in TOOL_CAN_STOP_BLEEDING:
            tool = right
        elif left and left.location == caller and isinstance(left, MedicalTool) and getattr(left.db, "medical_tool_type", None) in TOOL_CAN_STOP_BLEEDING:
            tool = left
        if not tool:
            caller.msg("You need to hold bandages, a medkit, or another bleeding-control tool in your hands. Wield it first.")
            return
        tool_type = getattr(tool.db, "medical_tool_type", None)
        if tool_type not in TOOL_CAN_STOP_BLEEDING:
            caller.msg("That tool isn't meant for bleeding control. Use bandages, a medkit, suture kit, hemostatic agent, tourniquet, or surgical kit.")
            return

        target = caller.search(args)
        if not target:
            return
        if not hasattr(target, "db"):
            caller.msg("You cannot stabilize that.")
            return
        try:
            from world.death import is_flatlined
            if is_flatlined(target):
                caller.msg("They're flatlined. You need to restart their heart with a defibrillator before you can treat their injuries.")
                return
        except ImportError as e:
            logger.log_trace("medical_cmds.CmdStabilize is_flatlined: %s" % e)

        bleeding_level = getattr(target.db, "bleeding_level", 0) or 0
        if bleeding_level <= 0:
            caller.msg("They are not bleeding. Nothing to stabilize.")
            return

        # Only block if tool has limited uses and they're exhausted (None = unlimited)
        uses = getattr(tool.db, "uses_remaining", None)
        if uses is not None and (int(uses) <= 0):
            caller.msg("Your supplies are spent. You need a fresh pack or another tool before you can stabilize anyone.")
            return

        success, msg = attempt_stop_bleeding(caller, target, tool_type)
        tool.consume_use()  # consume a use whether the roll succeeds or fails
        if success:
            caller.msg("|g" + msg + "|n")
            if target != caller:
                target.msg("|g%s works to control the bleeding: %s|n" % ((caller.get_display_name(target) if hasattr(caller, "get_display_name") else caller.name), msg[:60] + ("..." if len(msg) > 60 else "")))
        else:
            caller.msg("|r" + msg + "|n")
            if target != caller:
                target.msg("|r%s tries to stem the bleed: %s|n" % ((caller.get_display_name(target) if hasattr(caller, "get_display_name") else caller.name), msg[:60] + ("..." if len(msg) > 60 else "")))


class CmdApply(Command):
    """
    Apply a medical tool you're holding to a target (after scanning to see what's needed).

    Usage:
      apply to <target> [body part]
      apply <item> to <target> [body part]

    Examples:
      apply to Bob           - use wielded tool on Bob (one clear treatment)
      apply bandage to Bob   - stop bleeding on Bob (must be holding bandage)
      apply splint to Bob arm
      apply medkit to Bob throat

    The item must be wielded. For splints/organ stabilization, specify body part if multiple options.
    """
    key = "apply"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.medical.medical_treatment import get_treatment_options, BONE_ALIASES, ORGAN_ALIASES
        from typeclasses.medical_tools import MedicalTool

        caller = self.caller
        args = (self.args or "").strip()
        if not args or " to " not in args:
            caller.msg("Usage: apply [item] to <target> [body part]  (e.g. apply bandage to Bob, apply splint to Bob arm)")
            return

        left, right = args.split(" to ", 1)
        item_part = left.strip()
        rest = right.strip().split()
        if not rest:
            caller.msg("Apply to whom? Usage: apply [item] to <target> [body part]")
            return
        target_name = rest[0]
        bodypart = " ".join(rest[1:]).strip().lower() or None

        left = getattr(caller.db, "left_hand_obj", None)
        right = getattr(caller.db, "right_hand_obj", None)
        if item_part:
            tool = caller.search(item_part, location=caller)
            if not tool:
                return
            if not _obj_in_hands(caller, tool):
                caller.msg("You're not holding that. Hold the correct tool and try again.")
                return
        else:
            tool = None
            if right and right.location == caller and isinstance(right, MedicalTool):
                tool = right
            elif left and left.location == caller and isinstance(left, MedicalTool):
                tool = left
            if not tool:
                caller.msg("You need to hold a medical tool in your hands to apply it. Wield it first.")
                return
        if getattr(tool.db, "uses_remaining", 1) is not None and (tool.db.uses_remaining or 0) <= 0:
            caller.msg("Your supplies are spent. You need a fresh pack or another tool before you can treat anyone.")
            return

        target = caller.search(target_name)
        if not target:
            return
        if not hasattr(target, "db"):
            caller.msg("You cannot treat that.")
            return
        try:
            from world.death import is_flatlined
            if is_flatlined(target):
                caller.msg("They're flatlined. You need to restart their heart with a defibrillator before you can treat their injuries.")
                return
        except ImportError as e:
            logger.log_trace("medical_cmds.CmdApply is_flatlined: %s" % e)

        tool_type = tool.medical_tool_type
        tools_by_type = {tool_type: [tool]}
        options = get_treatment_options(caller, target, tools_by_type)
        if not options:
            caller.msg("There is nothing to treat on them with what you're holding, or they don't need that treatment.")
            return

        # Resolve which option to use (by body part or single option)
        choice = None
        if bodypart:
            bodypart_key = BONE_ALIASES.get(bodypart) or ORGAN_ALIASES.get(bodypart) or bodypart.replace(" ", "_")
            for action_id, _display, _t, target_info in options:
                if action_id == "splint" and target_info == bodypart_key:
                    choice = (action_id, target_info)
                    break
                if action_id == "organ" and target_info == bodypart_key:
                    choice = (action_id, target_info)
                    break
                if action_id in ("clean", "infection") and target_info == bodypart.replace(" ", "_"):
                    choice = (action_id, target_info)
                    break
                if action_id == "bleeding" and not bodypart_key:
                    choice = (action_id, target_info)
                    break
            if not choice and options:
                for opt in options:
                    if opt[3] == bodypart_key or (opt[3] and bodypart in str(opt[3])):
                        choice = (opt[0], opt[3])
                        break
            if not choice:
                caller.msg("No matching injury or treatment for that body part. Use the scanner to see what's needed.")
                return
        elif len(options) == 1:
            choice = (options[0][0], options[0][3])
        else:
            parts = []
            for _aid, _disp, _t, info in options:
                if info:
                    parts.append(info.replace("_", " "))
                else:
                    parts.append("bleeding")
            caller.msg("Specify what to treat: " + ", ".join(parts) + "  (e.g. apply splint to %s arm)" % target_name)
            return

        action_id, target_info = choice
        success, msg = tool.use_for_treatment(caller, target, action_id, target_info)
        tool.consume_use()  # consume a use whether the roll succeeds or fails
        if success:
            caller.msg("|g" + msg + "|n")
            if target != caller:
                target.msg("|g%s works on you: %s|n" % ((caller.get_display_name(target) if hasattr(caller, "get_display_name") else caller.name), msg[:70] + ("..." if len(msg) > 70 else "")))
        else:
            caller.msg("|r" + msg + "|n")
            if target != caller:
                target.msg("|r%s tries to help: %s|n" % ((caller.get_display_name(target) if hasattr(caller, "get_display_name") else caller.name), msg[:70] + ("..." if len(msg) > 70 else "")))


class CmdSurgery(Command):
    """
    Perform organ or bone surgery on a patient lying on the operating table.
    Long narrative sequence with skill check; severe organ damage only.
    Usage: surgery <organ|bone>
    """
    key = "surgery"
    aliases = ["operate"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Surgery on what target? Usage: surgery <organ|bone> (e.g. surgery heart, surgery femur)")
            return
        from world.medical.medical_treatment import ORGAN_ALIASES, BONE_ALIASES
        organ_arg = args.strip().lower()
        normalized = organ_arg.replace(" ", "_")
        organ_key = ORGAN_ALIASES.get(organ_arg, ORGAN_ALIASES.get(normalized, normalized))
        bone_key = BONE_ALIASES.get(organ_arg, BONE_ALIASES.get(normalized, normalized))
        target_key = organ_key if organ_key in ORGAN_ALIASES.values() else bone_key
        from typeclasses.medical_tools import OperatingTable
        table = None
        for obj in caller.location.contents:
            if isinstance(obj, OperatingTable):
                table = obj
                break
        if not table:
            caller.msg("There is no operating table here. The patient must lie on the table first.")
            return
        patient = table.get_patient()
        if not patient:
            caller.msg("No one is on the operating table. They must use 'lie on operating table' first.")
            return
        from world.medical.medical_surgery import start_surgery_sequence
        from world.medical import ORGAN_INFO, BONE_INFO
        if target_key not in ORGAN_INFO and target_key not in BONE_INFO:
            caller.msg("Unknown surgical target. Try organs (heart, lungs, liver) or bones (femur, humerus, ribs, spine).")
            return
        started, err = start_surgery_sequence(caller, patient, table, target_key)
        if not started:
            caller.msg(err or "You cannot perform that surgery now.")


class CmdDefib(Command):
    """
    Resuscitate a dead or arrested character with a defibrillator.
    Takes about 12 seconds; you are locked in the action. Requires medicine skill.
    Usage: defib <target>
    """
    key = "defib"
    aliases = ["defibrillate", "resuscitate"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Defib who? Usage: defib <target>")
            return
        target = caller.search(args, location=caller.location)
        if not target:
            return
        defib = None
        for obj in caller.contents:
            from typeclasses.medical_tools import Defibrillator
            if isinstance(obj, Defibrillator):
                defib = obj
                break
        if not defib:
            caller.msg("You need a defibrillator in your inventory.")
            return
        from world.medical.medical_defib import start_defib_sequence
        started, err = start_defib_sequence(caller, target, defib)
        if not started:
            caller.msg(err if err else "You cannot do that right now.")
