"""
Medical commands: CmdHt, CmdPatient, CmdApply, CmdStabilize, CmdSedate, CmdSurgery, CmdDefib.
(CmdUse is in use_cmds.py as global use command.)
"""

from commands.base_cmds import Command
from commands.inventory_cmds import _obj_in_hands
from evennia.utils import logger
from evennia.utils.ansi import strip_ansi

from world.theme_colors import MEDICAL_COLORS as MC


def _norm_name(text):
    return " ".join((strip_ansi(text or "")).strip().lower().split())


def _resolve_medical_target(caller, query, location=None):
    """
    Resolve a character target using what the caller sees (recog/sdesc/display name)
    before falling back to Evennia's default search behavior.
    """
    q = (query or "").strip()
    if not q:
        return None
    if q.lower() in ("me", "self", "myself"):
        return caller
    loc = location or getattr(caller, "location", None)
    qn = _norm_name(q)
    chars = []
    if loc and hasattr(loc, "contents_get"):
        chars = list(loc.contents_get(content_type="character") or [])
    elif loc and hasattr(loc, "contents"):
        chars = [obj for obj in loc.contents if hasattr(obj, "db")]
    # Exact display-name / key match first
    exact = []
    for ch in chars:
        disp = ch.get_display_name(caller) if hasattr(ch, "get_display_name") else getattr(ch, "key", "")
        if _norm_name(disp) == qn or _norm_name(getattr(ch, "key", "")) == qn:
            exact.append(ch)
    if len(exact) == 1:
        return exact[0]
    # Prefix match on display names
    pref = []
    for ch in chars:
        disp = ch.get_display_name(caller) if hasattr(ch, "get_display_name") else getattr(ch, "key", "")
        if _norm_name(disp).startswith(qn):
            pref.append(ch)
    if len(pref) == 1:
        return pref[0]
    # Fallback to engine search for aliases/dbrefs, etc.
    return caller.search(q, location=loc)


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
            target = _resolve_medical_target(caller, self.args, location=caller.location)
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


class CmdPatient(Command):
    """
    Open the medical treatment menu for a nearby patient.

    Usage:
      patient <target>
    """
    key = "patient"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: patient <target>")
            return
        target = _resolve_medical_target(caller, args, location=caller.location)
        if not target:
            return
        if not hasattr(target, "db"):
            caller.msg("You cannot assess that.")
            return
        from world.medical.medical_menu import start_medical_menu
        start_medical_menu(caller, target)


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
        target = _resolve_medical_target(caller, args, location=caller.location)
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
        if target != caller:
            from world.rpg.trust import check_trust_or_incapacitated

            ok, _r = check_trust_or_incapacitated(target, caller, "heal")
            if not ok:
                caller.msg("They don't trust you enough for that. They need to @trust you to heal.")
                return
        success, msg = table.use_for_sedation(caller, target)
        if success:
            caller.msg(MC["stable"] + msg + "|n")
        else:
            caller.msg(MC["critical"] + (msg or "Sedation failed.") + "|n")


class CmdWakePatient(Command):
    """
    Wake an anesthetized patient currently lying on an operating table.

    Usage:
      wake <target>
    """
    key = "wake"
    aliases = ["rouse", "awaken", "wake patient"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Wake whom? Usage: wake <target>")
            return
        target = _resolve_medical_target(caller, args, location=caller.location)
        if not target:
            return
        if not hasattr(target, "db"):
            caller.msg("You cannot wake that.")
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
        success, msg = table.wake_patient(caller, target)
        if success:
            caller.msg(MC["stable"] + msg + "|n")
        else:
            caller.msg(MC["critical"] + (msg or "Wake attempt failed.") + "|n")


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

        target = _resolve_medical_target(caller, args, location=caller.location)
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
            caller.msg(MC["stable"] + msg + "|n")
            if target != caller:
                target.msg(MC["stable"] + "%s works to control the bleeding: %s|n" % ((caller.get_display_name(target) if hasattr(caller, "get_display_name") else caller.name), msg[:60] + ("..." if len(msg) > 60 else "")))
        else:
            caller.msg(MC["critical"] + msg + "|n")
            if target != caller:
                target.msg(MC["critical"] + "%s tries to stem the bleed: %s|n" % ((caller.get_display_name(target) if hasattr(caller, "get_display_name") else caller.name), msg[:60] + ("..." if len(msg) > 60 else "")))


def do_medical_apply(caller, args):
    """
    Core logic for applying a medical tool to a target.

    Extracted from CmdApply so the unified apply dispatcher in
    commands.cosmetic_cmds can call it directly without instantiating
    a second Command object.

    args: the raw argument string after the 'apply' keyword.
    Returns True if the action was handled (even on error), False if args
    were empty/missing ' to ' so the caller can show combined usage.
    """
    from world.medical.medical_treatment import get_treatment_options, BONE_ALIASES, ORGAN_ALIASES
    from typeclasses.medical_tools import MedicalTool

    args = (args or "").strip()
    if not args or " to " not in args:
        return False

    left_str, right_str = args.split(" to ", 1)
    item_part = left_str.strip()
    rest = right_str.strip().split()
    if not rest:
        caller.msg("Apply to whom? Usage: apply [item] to <target> [body part]")
        return True
    target_name = rest[0]
    bodypart = " ".join(rest[1:]).strip().lower() or None

    left_hand = getattr(caller.db, "left_hand_obj", None)
    right_hand = getattr(caller.db, "right_hand_obj", None)
    if item_part:
        tool = caller.search(item_part, location=caller)
        if not tool:
            return True
        if not _obj_in_hands(caller, tool):
            caller.msg("You're not holding that. Hold the correct tool and try again.")
            return True
    else:
        tool = None
        if right_hand and right_hand.location == caller and isinstance(right_hand, MedicalTool):
            tool = right_hand
        elif left_hand and left_hand.location == caller and isinstance(left_hand, MedicalTool):
            tool = left_hand
        if not tool:
            caller.msg("You need to hold a medical tool in your hands to apply it. Wield it first.")
            return True
    if getattr(tool.db, "uses_remaining", 1) is not None and (tool.db.uses_remaining or 0) <= 0:
        caller.msg("Your supplies are spent. You need a fresh pack or another tool before you can treat anyone.")
        return True

    target = _resolve_medical_target(caller, target_name, location=caller.location)
    if not target:
        return True
    if not hasattr(target, "db"):
        caller.msg("You cannot treat that.")
        return True
    try:
        from world.death import is_flatlined
        if is_flatlined(target):
            caller.msg("They're flatlined. You need to restart their heart with a defibrillator before you can treat their injuries.")
            return True
    except ImportError as e:
        logger.log_trace("medical_cmds.do_medical_apply is_flatlined: %s" % e)

    if target != caller:
        from world.rpg.trust import check_trust_or_incapacitated
        ok, _r = check_trust_or_incapacitated(target, caller, "heal")
        if not ok:
            caller.msg("They don't trust you enough for that. They need to @trust you to heal.")
            return True

    tool_type = tool.medical_tool_type
    tools_by_type = {tool_type: [tool]}
    options = get_treatment_options(caller, target, tools_by_type)
    if not options:
        caller.msg("There is nothing to treat on them with what you're holding, or they don't need that treatment.")
        return True

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
            if (
                action_id in ("clean", "infection")
                and target_info == bodypart.replace(" ", "_")
                and _t == tool_type
            ):
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
            return True
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
        return True

    action_id, target_info = choice
    success, msg = tool.use_for_treatment(caller, target, action_id, target_info)
    tool.consume_use()
    if success:
        caller.msg(MC["stable"] + msg + "|n")
        if target != caller:
            target.msg(MC["stable"] + "%s works on you: %s|n" % (
                (caller.get_display_name(target) if hasattr(caller, "get_display_name") else caller.name),
                msg[:70] + ("..." if len(msg) > 70 else ""),
            ))
    else:
        caller.msg(MC["critical"] + msg + "|n")
        if target != caller:
            target.msg(MC["critical"] + "%s tries to help: %s|n" % (
                (caller.get_display_name(target) if hasattr(caller, "get_display_name") else caller.name),
                msg[:70] + ("..." if len(msg) > 70 else ""),
            ))
    return True


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
        handled = do_medical_apply(self.caller, self.args)
        if not handled:
            self.caller.msg("Usage: apply [item] to <target> [body part]  (e.g. apply bandage to Bob, apply splint to Bob arm)")


class CmdSurgery(Command):
    """
    Perform surgical procedures on a patient on an operating table.

    This command covers standard trauma surgery and cyberware procedures.
    Place the patient on the operating table first (they use |wlie on operating table|n),
    then use one of the forms below. All surgery including |wreplace|n requires that table,
    a patient on it, and you in the room — there is no field chrome install for replacement limbs/organs.

    Usage:
      surgery <organ|bone>
      surgery install <cyberware> on <patient>
      surgery remove <cyberware> from <patient>
      surgery replace <organ> on <patient>
      surgery repair <cyberware> on <patient>
      surgery list <patient>

    Examples:
      surgery heart
      surgery femur
      surgery install chrome arm on Vex
      surgery remove chrome arm from Vex
      surgery replace heart on Vex
      surgery replace left arm on Vex
      surgery repair chrome arm on Vex
      surgery list Vex
    """
    key = "surgery"
    aliases = []
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: surgery <organ|bone> OR surgery install/remove/replace/repair/list ...")
            return
        parts = args.split()
        verb = parts[0].lower()
        from world.medical.medical_treatment import ORGAN_ALIASES, BONE_ALIASES
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
        if patient != caller:
            from world.rpg.trust import check_trust_or_incapacitated

            ok, _r = check_trust_or_incapacitated(patient, caller, "operate", operate_strict=True)
            if not ok:
                caller.msg("They don't trust you enough for that. They need to @trust you to operate.")
                return
        if verb in ("install", "remove", "replace", "repair", "list"):
            from world.medical.cybersurgery import (
                start_cybersurgery_install,
                start_cybersurgery_remove,
                start_cybersurgery_replace,
                start_cybersurgery_repair,
            )
            if verb == "list":
                target_name = " ".join(parts[1:]).strip() if len(parts) > 1 else patient.key
                target = patient
                if target_name:
                    looked = _resolve_medical_target(caller, target_name, location=caller.location)
                    if looked:
                        target = looked
                cyber = list(target.get_cyberware() if hasattr(target, "get_cyberware") else (target.db.cyberware or []))
                # If search resolved to a different object with no cyberware, fall back to the table patient.
                if not cyber and target != patient:
                    cyber = list(patient.get_cyberware() if hasattr(patient, "get_cyberware") else (patient.db.cyberware or []))
                    if cyber:
                        target = patient
                if not cyber:
                    caller.msg("No installed cyberware.")
                else:
                    target_label = target.get_display_name(caller) if hasattr(target, "get_display_name") else target.key
                    caller.msg("\n".join([f"Installed on {target_label}:"] + [f"  {c.key} (#{c.id})" for c in cyber]))
                return
            if verb == "install":
                # surgery install <cyberware> on <patient>
                if " on " not in args.lower():
                    caller.msg("Usage: surgery install <cyberware> on <patient>")
                    return
                left, right = args[8:].split(" on ", 1)
                cw = caller.search(left.strip(), location=caller)
                right = right.strip()
                coverage_words = []
                if " coverage " in right.lower():
                    patient_part, _, coverage_part = right.partition(" coverage ")
                    right = patient_part.strip()
                    coverage_words = [w.strip().lower() for w in coverage_part.split() if w.strip()]
                target = _resolve_medical_target(caller, right.strip(), location=caller.location)
                if not cw or not target:
                    return
                if table.get_patient() != target:
                    caller.msg("That patient is not on the operating table.")
                    return
                if type(cw).__name__ == "SkinWeave":
                    try:
                        from typeclasses.cyberware_catalog import SKINWEAVE_EXTENDED_COVERAGE
                        parts = {"torso", "face"}
                        diff_bonus = 0
                        for token in coverage_words:
                            if token in ("torso", "face", "left arm", "right arm", "neck", "left thigh", "right thigh", "left hand", "right hand"):
                                parts.add(token)
                            elif token in SKINWEAVE_EXTENDED_COVERAGE:
                                add_parts, add_diff = SKINWEAVE_EXTENDED_COVERAGE[token]
                                parts.update(add_parts)
                                diff_bonus += int(add_diff)
                        cw.db.weave_parts = sorted(parts)
                        cw.db.weave_descriptions = {p: cw.db.weave_descriptions.get(p) if (cw.db.weave_descriptions or {}).get(p) else __import__("typeclasses.cyberware_catalog", fromlist=["SKINWEAVE_DEFAULTS"]).SKINWEAVE_DEFAULTS.get(p, "The skin here is synthetic.") for p in cw.db.weave_parts}
                        cw.db.surgery_difficulty = int(getattr(cw, "surgery_difficulty", 12) or 12) + diff_bonus
                    except Exception:
                        pass
                from world.medical import is_sedated_for_surgery

                sedated = is_sedated_for_surgery(target)
                if getattr(cw, "surgery_requires_sedation", True) and not sedated:
                    caller.msg(f"{MC['compensated']}Patient is not sedated. Surgery difficulty will be significantly higher.|n")
                started, err = start_cybersurgery_install(caller, target, table, cw)
                if not started:
                    caller.msg(err or "You cannot perform that surgery now.")
                return
            if verb == "remove":
                if " from " not in args.lower():
                    caller.msg("Usage: surgery remove <cyberware> from <patient>")
                    return
                left, right = args[7:].split(" from ", 1)
                target = _resolve_medical_target(caller, right.strip(), location=caller.location)
                if not target:
                    return
                started, err = start_cybersurgery_remove(caller, target, table, left.strip())
                if not started:
                    caller.msg(err or "You cannot perform that surgery now.")
                return
            if verb == "replace":
                if " on " not in args.lower():
                    caller.msg("Usage: surgery replace <organ> on <patient>")
                    return
                left, right = args[8:].split(" on ", 1)
                target = _resolve_medical_target(caller, right.strip(), location=caller.location)
                if not target:
                    return
                organ_arg = left.strip().lower()
                normalized = organ_arg.replace(" ", "_")
                from world.medical.limb_trauma import LIMB_ALIASES
                limb_key = LIMB_ALIASES.get(organ_arg) or LIMB_ALIASES.get(normalized)
                if limb_key:
                    rep_key = limb_key
                else:
                    rep_key = ORGAN_ALIASES.get(organ_arg, ORGAN_ALIASES.get(normalized, normalized))
                started, err = start_cybersurgery_replace(caller, target, table, rep_key)
                if not started:
                    caller.msg(err or "You cannot perform that surgery now.")
                return
            if verb == "repair":
                if " on " not in args.lower():
                    caller.msg("Usage: surgery repair <cyberware> on <patient>")
                    return
                left, right = args[7:].split(" on ", 1)
                target = _resolve_medical_target(caller, right.strip(), location=caller.location)
                if not target:
                    return
                started, err = start_cybersurgery_repair(caller, target, table, left.strip())
                if not started:
                    caller.msg(err or "You cannot perform that surgery now.")
                return

        organ_arg = args.strip().lower()
        normalized = organ_arg.replace(" ", "_")
        organ_key = ORGAN_ALIASES.get(organ_arg, ORGAN_ALIASES.get(normalized, normalized))
        bone_key = BONE_ALIASES.get(organ_arg, BONE_ALIASES.get(normalized, normalized))
        target_key = organ_key if organ_key in ORGAN_ALIASES.values() else bone_key
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
        target = _resolve_medical_target(caller, args, location=caller.location)
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
        if target != caller:
            from world.rpg.trust import check_trust_or_incapacitated

            ok, _r = check_trust_or_incapacitated(target, caller, "heal")
            if not ok:
                caller.msg("They don't trust you enough for that. They need to @trust you to heal.")
                return
        from world.medical.medical_defib import start_defib_sequence
        started, err = start_defib_sequence(caller, target, defib)
        if not started:
            caller.msg(err if err else "You cannot do that right now.")
