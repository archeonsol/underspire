"""
Medical treatment menu: GUI for scanning and treating trauma.
EvMenu flow: target -> main panel (vitals, trauma, actions) -> perform action -> result -> back to main.
 
All text is fully in-character. The menu represents what the surgeon sees and
thinks while working — not a game interface but a medical assessment viewed
through the lens of an undercity practitioner with steady hands and no bedside
manner.
"""
import time
 
from world.medical import _ensure_medical_db, get_medical_summary, BLEEDING_LEVELS
from world.medical.injuries import compute_effective_bleed_level
from world.medical.medical_treatment import get_treatment_options, TOOL_SCANNER
from typeclasses.medical_tools import get_medical_tools_from_inventory
from world.theme_colors import COMBAT_COLORS as CC, MEDICAL_COLORS as MC
 
# ── Visual constants ─────────────────────────────────────────────────────────
 
_W = 58  # inner width
_BORDER_COLOR = "|x"  # dim grey for frame
_HEADER_COLOR = CC["parry"]  # cyan for section titles
_LABEL_COLOR = "|w"   # white for field labels
_DIM = "|x"           # grey for secondary info
_WARN = MC["compensated"]           # yellow for caution
_CRIT = MC["critical"]           # red for danger
_GOOD = MC["stable"]           # green for stable/ok
_N = "|n"
 
 
def _line(char="-"):
    return f"{_BORDER_COLOR}{''.ljust(_W, char)}{_N}"
 
 
def _heavy_line():
    return f"{_BORDER_COLOR}{''.ljust(_W, '=')}{_N}"
 
 
def _padded(text, width=_W):
    """Left-pad a line for consistent indentation inside the frame."""
    return f"  {text}"
 
 
def _bar(current, maximum, width=20):
    """In-character vitals bar using block characters."""
    if maximum <= 0:
        maximum = 1
    pct = current / maximum
    filled = max(0, min(width, int(width * pct)))
    empty = width - filled
    if pct >= 0.8:
        color = _GOOD
    elif pct >= 0.4:
        color = _WARN
    else:
        color = _CRIT
    return f"{_BORDER_COLOR}[{_N}{color}{'|' * filled}{_BORDER_COLOR}{'.' * empty}{_N}{_BORDER_COLOR}]{_N}"
 
 
def _bleed_label(level):
    """In-character bleeding description."""
    if level <= 0:
        return f"{_GOOD}No active haemorrhage.{_N}"
    labels = {
        1: f"{_WARN}Capillary ooze. Manageable.{_N}",
        2: f"{_WARN}Steady venous flow. Needs attention.{_N}",
        3: f"{_CRIT}Significant blood loss. Act now.{_N}",
        4: f"{_CRIT}Arterial. Life-threatening. Seconds count.{_N}",
    }
    return labels.get(min(level, 4), f"{_CRIT}Bleeding.{_N}")
 
 
def _sedation_label(target):
    sedated_until = float(getattr(target.db, "sedated_until", 0.0) or 0.0)
    now = time.time()
    if sedated_until > now:
        remaining = int((sedated_until - now) / 60)
        return f"{_GOOD}Under. ~{remaining}m remaining.{_N}"
    return f"{_DIM}Conscious. Sedate before cutting.{_N}"
 
 
def _condition_word(pct):
    """Single-word triage assessment."""
    if pct >= 95:
        return f"{_GOOD}Stable{_N}"
    if pct >= 75:
        return f"{_GOOD}Functional{_N}"
    if pct >= 50:
        return f"{_WARN}Compromised{_N}"
    if pct >= 25:
        return f"{_CRIT}Critical{_N}"
    if pct > 0:
        return f"{_CRIT}Failing{_N}"
    return f"{_CRIT}Arrest{_N}"
 
 
def _trauma_summary_ic(target):
    """
    In-character trauma summary. No organ keys, no severity numbers.
    Written as terse clinical shorthand a field surgeon would think in.
    """
    _ensure_medical_db(target)
    lines = []
 
    organ_damage = target.db.organ_damage or {}
    organ_labels = {
        "brain": "neuro", "eyes": "ocular", "throat": "airway",
        "carotid": "carotid", "collarbone_area": "shoulder complex",
        "heart": "cardiac", "lungs": "pulmonary", "spine_cord": "spinal",
        "liver": "hepatic", "spleen": "splenic", "stomach": "gastric",
        "kidneys": "renal", "pelvic_organs": "pelvic",
    }
    severity_words = {1: "bruised", 2: "damaged", 3: f"{MC['arrest']}DESTROYED{_N}"}
    if organ_damage:
        parts = []
        for organ_key, sev in organ_damage.items():
            if sev <= 0:
                continue
            label = organ_labels.get(organ_key, organ_key)
            word = severity_words.get(min(sev, 3), "injured")
            stab = f" {_DIM}[stabilized]{_N}" if (target.db.stabilized_organs or {}).get(organ_key) else ""
            parts.append(f"{_CRIT}{label}{_N}: {word}{stab}")
        if parts:
            lines.append(f"  {_LABEL_COLOR}Internal:{_N} " + "; ".join(parts))

    from world.medical.limb_trauma import LIMB_INFO, LIMB_SLOTS
    limb_damage = target.db.limb_damage or {}
    if limb_damage:
        limb_labels = {"left_arm": "L arm", "right_arm": "R arm", "left_leg": "L leg", "right_leg": "R leg"}
        lparts = []
        for limb_key in sorted(LIMB_SLOTS):
            sev = int(limb_damage.get(limb_key, 0) or 0)
            if sev <= 0:
                continue
            label = limb_labels.get(limb_key, limb_key)
            destroyed = any(
                limb_key in (i.get("limb_damage") or {}) and i.get("fracture_destroyed")
                for i in (target.db.injuries or [])
            )
            word = f"{MC['arrest']}UNSALVAGEABLE{_N}" if destroyed else severity_words.get(min(sev, 3), "injured")
            lparts.append(f"{_CRIT}{label}{_N}: {word}")
        if lparts:
            lines.append(f"  {_LABEL_COLOR}Limbs:{_N} " + "; ".join(lparts))
 
    fractures = target.db.fractures or []
    splinted = target.db.splinted_bones or []
    bone_labels = {
        "skull": "skull", "jaw": "jaw", "nose": "nasal",
        "cervical_spine": "c-spine", "clavicle": "clavicle",
        "scapula": "scapula", "humerus": "humerus",
        "metacarpals": "hand", "ribs": "ribs", "spine": "spine",
        "pelvis": "pelvis", "femur": "femur", "ankle": "ankle",
        "metatarsals": "foot",
    }
    if fractures:
        parts = []
        for b in fractures:
            label = bone_labels.get(b, b)
            sp = f" {_DIM}[set]{_N}" if b in splinted else ""
            parts.append(f"{_WARN}{label}{_N}{sp}")
        lines.append(f"  {_LABEL_COLOR}Fractures:{_N} " + ", ".join(parts))
 
    from world.medical.infection import INFECTION_CATALOG, INFECTION_STAGE_LABELS
    from world.medical.injuries import _normalize_injuries
    infected = []
    for injury in (_normalize_injuries(target) or []):
        stage = int(injury.get("infection_stage", 0) or 0)
        if stage <= 0:
            continue
        itype = injury.get("infection_type") or "surface_cellulitis"
        ilabel = INFECTION_CATALOG.get(itype, {}).get("label", itype.replace("_", " "))
        part = (injury.get("body_part") or "wound").strip()
        color = _CRIT if stage >= 3 else MC["infection"]
        infected.append(f"{color}{part}: {ilabel}{_N}")
    if infected:
        lines.append(f"  {_LABEL_COLOR}Infection:{_N} " + "; ".join(infected))
 
    if not lines:
        lines.append(f"  {_GOOD}No significant trauma noted.{_N}")
    return "\n".join(lines)
 
 
def _action_label(action_id, display_name, tool_type):
    """
    Rewrite treatment options as in-character actions.
    No tool names, no game terms. What the surgeon would actually say.
    """
    tool_verbs = {
        "bandages": "gauze",
        "medkit": "kit",
        "suture_kit": "needle",
        "hemostatic": "hemostatic",
        "surgical_kit": "instruments",
        "tourniquet": "tourniquet",
        "antibiotics": "antibiotics",
        "splint": "splint",
        "scanner": "scanner",
    }
    tool_word = tool_verbs.get(tool_type, "")
    # The display_name from get_treatment_options is already descriptive.
    # We strip the mechanical prefix and let the action speak for itself.
    return f"{display_name}" + (f" {_DIM}({tool_word}){_N}" if tool_word else "")
 
 
# ── Menu helpers ─────────────────────────────────────────────────────────────
 
def _find_operating_table(caller):
    if not caller.location:
        return None
    from typeclasses.medical_tools import OperatingTable
    for obj in caller.location.contents:
        if isinstance(obj, OperatingTable):
            return obj
    return None
 
 
def _is_dangerous_action(action_id):
    return action_id in ("sedate_patient", "cyber_remove", "chrome_replace")
 
 
def _build_treatment_options(caller, target, tools, treatment_options, operating_table):
    options = []
    idx = 2
 
    bleed_opts = [t for t in treatment_options if t[0] == "bleeding"]
    fracture_opts = [t for t in treatment_options if t[0] == "splint"]
    organ_opts = [t for t in treatment_options if t[0] == "organ"]
    wound_opts = [t for t in treatment_options if t[0] in ("clean", "infection")]
    cyber_opts = [t for t in treatment_options if t[0].startswith("cyber") or t[0] in ("chrome_replace", "sedate_patient")]
    other_opts = [t for t in treatment_options if t not in bleed_opts + fracture_opts + organ_opts + wound_opts + cyber_opts]
 
    grouped = [
        (f"{_CRIT}HAEMORRHAGE{_N}", bleed_opts),
        (f"{_WARN}FRACTURES{_N}", fracture_opts),
        (f"{_CRIT}INTERNAL{_N}", organ_opts),
        (f"{_LABEL_COLOR}WOUND CARE{_N}", wound_opts),
        (f"{_HEADER_COLOR}CHROME{_N}", cyber_opts),
        (f"{_DIM}OTHER{_N}", other_opts),
    ]
 
    for label, group in grouped:
        if not group:
            continue
        for action_id, display_name, tool_type, target_info in group:
            tool_list = tools.get(tool_type, [])
            tool_obj = tool_list[0] if tool_list else None
            uses = getattr(getattr(tool_obj, "db", None), "uses_remaining", None) if tool_obj else None
            desc_text = _action_label(action_id, display_name, tool_type)
            if uses is not None:
                desc_text += f" {_DIM}x{uses}{_N}"
            treatment_kwargs = {
                "target": target,
                "action_id": action_id,
                "target_info": target_info,
                "tool_type": tool_type,
                "operating_table": operating_table,
                "display_name": display_name,
            }
            if _is_dangerous_action(action_id):
                goto = ("node_confirm_action", {
                    "target": target,
                    "action_desc": display_name,
                    "proceed_kwargs": treatment_kwargs,
                    "operating_table": operating_table,
                })
            else:
                goto = ("node_do_treatment", treatment_kwargs)
            options.append({"key": str(idx), "desc": desc_text, "goto": goto})
            idx += 1
    return options
 
 
def _get_menu_target(caller, kwargs):
    target = kwargs.get("target")
    if target is not None and hasattr(target, "db"):
        return target
    menu = getattr(getattr(caller, "ndb", None), "_evmenu", None)
    target = getattr(menu, "target", None) if menu else None
    return target if (target and hasattr(target, "db")) else None
 
 
# ── Nearby injured ───────────────────────────────────────────────────────────
 
def _get_injured_nearby(caller, current_target):
    """Find other injured characters in the room for triage switching."""
    if not caller.location or not hasattr(caller.location, "contents_get"):
        return []
    injured = []
    for char in caller.location.contents_get(content_type="character"):
        if char == current_target or char == caller:
            continue
        if not hasattr(char, "db") or not getattr(char.db, "injuries", None):
            continue
        hp = getattr(char, "hp", 0)
        mx = getattr(char, "max_hp", 1)
        bleed = getattr(char.db, "bleeding_level", 0) or 0
        if hp < mx or bleed > 0:
            injured.append(char)
    return injured[:5]
 
 
# ── Main panel ───────────────────────────────────────────────────────────────
 
def _main_panel_full(caller, target, operating_table=None):
    hp = getattr(target, "hp", 0)
    mx = getattr(target, "max_hp", 1) or 1
    pct = (hp / mx * 100) if mx > 0 else 0
    bleed_level, _ = compute_effective_bleed_level(target)
    bar = _bar(hp, mx)
    condition = _condition_word(pct)
 
    lines = [
        "",
        _heavy_line(),
        f"  {_HEADER_COLOR}A S S E S S M E N T{_N}",
        _heavy_line(),
        "",
        f"  {_LABEL_COLOR}Condition:{_N}  {condition}",
        f"  {_LABEL_COLOR}Perfusion:{_N}  {bar} {_DIM}{pct:.0f}%{_N}",
        f"  {_LABEL_COLOR}Bleeding:{_N}   {_bleed_label(bleed_level)}",
        f"  {_LABEL_COLOR}Sedation:{_N}   {_sedation_label(target)}",
        "",
        _line(),
        f"  {_HEADER_COLOR}TRAUMA{_N}",
        _line(),
        _trauma_summary_ic(target),
        "",
        _line(),
        f"  {_HEADER_COLOR}INTERVENTIONS{_N}",
        _line(),
    ]
    return "\n".join(lines)
 
 
def _main_panel_compact(caller, target):
    hp = getattr(target, "hp", 0)
    mx = getattr(target, "max_hp", 1) or 1
    pct = (hp / mx * 100) if mx > 0 else 0
    bleed_level, _ = compute_effective_bleed_level(target)
    bar = _bar(hp, mx, width=12)
    condition = _condition_word(pct)
 
    log = getattr(caller.ndb, "_medical_session_log", None) or []
    log_line = ""
    if log:
        log_line = f"\n  {_DIM}" + " > ".join(log[-3:]) + f"{_N}"
 
    lines = [
        "",
        _line(),
        f"  {condition} {bar} {_DIM}{pct:.0f}%{_N}  {_bleed_label(bleed_level)}",
        _line() + log_line,
    ]
    return "\n".join(lines)
 
 
# ── Menu nodes ───────────────────────────────────────────────────────────────
 
def node_medical_main(caller, raw_string, **kwargs):
    target = _get_menu_target(caller, kwargs)
    if not target:
        caller.msg("Invalid target.")
        return None, None
 
    compact = kwargs.get("compact", False)
    operating_table = kwargs.get("operating_table") or _find_operating_table(caller)
 
    if compact:
        text = _main_panel_compact(caller, target)
    else:
        text = _main_panel_full(caller, target, operating_table)
 
    options = []
    tools = get_medical_tools_from_inventory(caller)
    treatment_options = get_treatment_options(caller, target, tools)
 
    # Scan
    if tools.get(TOOL_SCANNER):
        scanner = tools[TOOL_SCANNER][0]
        options.append({
            "key": "1",
            "desc": f"Scan {_DIM}(bioscanner){_N}",
            "goto": ("node_do_scan", {"target": target, "scanner": scanner, "operating_table": operating_table}),
        })
    else:
        options.append({
            "key": "1",
            "desc": f"{_DIM}Scan (no scanner available){_N}",
            "goto": ("node_medical_main", {"target": target, "compact": True, "operating_table": operating_table}),
        })
 
    # Treatments
    options.extend(_build_treatment_options(caller, target, tools, treatment_options, operating_table))
 
    # Wound detail
    options.append({
        "key": "w",
        "desc": f"Wound detail",
        "goto": ("node_wound_detail", {"target": target, "operating_table": operating_table}),
    })
 
    # Triage: nearby injured
    injured_nearby = _get_injured_nearby(caller, target)
    if injured_nearby:
        for j, char in enumerate(injured_nearby):
            char_hp = getattr(char, "hp", 0)
            char_mx = getattr(char, "max_hp", 1) or 1
            char_pct = (char_hp / char_mx * 100) if char_mx > 0 else 0
            key = chr(ord('a') + j)
            char_name = char.get_display_name(caller) if hasattr(char, "get_display_name") else char.name
            char_condition = _condition_word(char_pct)
            options.append({
                "key": key,
                "desc": f"{_DIM}Switch to{_N} {char_name} {_DIM}({char_condition}{_DIM}){_N}",
                "goto": ("node_medical_main", {"target": char, "compact": False, "operating_table": operating_table}),
            })
 
    options.append({"key": "q", "desc": f"Step back", "goto": "node_medical_exit"})
    return text, options
 
 
def node_do_scan(caller, raw_string, **kwargs):
    target = kwargs.get("target") or _get_menu_target(caller, kwargs)
    scanner = kwargs.get("scanner")
    operating_table = kwargs.get("operating_table")
    if not scanner or not hasattr(scanner, "use_for_scan"):
        caller.msg(f"{_CRIT}No scanner.{_N}")
        return node_medical_main(caller, raw_string, target=target, compact=True, operating_table=operating_table)
    success, out = scanner.use_for_scan(caller, target)
    if not success:
        caller.msg(f"{_CRIT}" + (out if isinstance(out, str) else "Scan failed.") + f"{_N}")
        return node_medical_main(caller, raw_string, target=target, compact=True, operating_table=operating_table)
 
    scan_output = ""
    if isinstance(out, dict):
        scan_output = out.get("formatted") or ""
        if not scan_output:
            hp = out.get("hp", 0)
            max_hp = out.get("max_hp", 1)
            detail = out.get("detail", "")
            scan_output = f"{_HEADER_COLOR}BIOSCANNER{_N}  {hp}/{max_hp}\n\n{detail}"
        if target != caller:
            target.msg(f"{(caller.get_display_name(target) if hasattr(caller, 'get_display_name') else caller.name)} runs a scanner over you.")
    else:
        scan_output = str(out)
 
    return node_scan_result(caller, raw_string, target=target, scan_output=scan_output, operating_table=operating_table)
 
 
def node_scan_result(caller, raw_string, **kwargs):
    target = kwargs.get("target") or _get_menu_target(caller, kwargs)
    if not target:
        return node_medical_main(caller, raw_string)
    scan_output = kwargs.get("scan_output", "No data.")
    operating_table = kwargs.get("operating_table") or _find_operating_table(caller)
 
    text = scan_output + "\n\n" + _line()
 
    tools = get_medical_tools_from_inventory(caller)
    treatment_options = get_treatment_options(caller, target, tools)
    options = []
    if tools.get(TOOL_SCANNER):
        scanner = tools[TOOL_SCANNER][0]
        options.append({
            "key": "1",
            "desc": f"Scan again",
            "goto": ("node_do_scan", {"target": target, "scanner": scanner, "operating_table": operating_table}),
        })
    options.extend(_build_treatment_options(caller, target, tools, treatment_options, operating_table))
    options.append({"key": "w", "desc": "Wound detail", "goto": ("node_wound_detail", {"target": target, "operating_table": operating_table})})
    options.append({"key": "b", "desc": "Back", "goto": ("node_medical_main", {"target": target, "compact": True, "operating_table": operating_table})})
    options.append({"key": "q", "desc": "Step back", "goto": "node_medical_exit"})
    return text, options
 
 
def node_do_treatment(caller, raw_string, **kwargs):
    target = kwargs.get("target") or _get_menu_target(caller, kwargs)
    if not target:
        caller.msg(f"{_CRIT}No patient.{_N}")
        return node_medical_main(caller, raw_string)
    action_id = kwargs.get("action_id")
    target_info = kwargs.get("target_info")
    tool_type = kwargs.get("tool_type")
    operating_table = kwargs.get("operating_table")
    display_name = kwargs.get("display_name") or action_id or "intervention"
    if not action_id:
        return node_medical_main(caller, raw_string, target=target, compact=True, operating_table=operating_table)
 
    tools = get_medical_tools_from_inventory(caller)
    tool_list = tools.get(tool_type, [])
    if not tool_list:
        caller.msg(f"{_CRIT}You don't have what you need.{_N}")
        return node_medical_main(caller, raw_string, target=target, compact=True, operating_table=operating_table)
 
    tool = tool_list[0]
 
    if action_id == "sedate_patient":
        table = operating_table or _find_operating_table(caller)
        if not table or table.get_patient() != target:
            success, msg = False, "They need to be on the table."
        else:
            success, msg = table.use_for_sedation(caller, target)
    elif action_id in ("cyber_install", "cyber_remove", "chrome_replace", "cyber_repair"):
        from world.medical.cybersurgery import (
            start_cybersurgery_install,
            start_cybersurgery_remove,
            start_cybersurgery_replace,
            start_cybersurgery_repair,
        )
        table = operating_table or _find_operating_table(caller)
        if not table or table.get_patient() != target:
            caller.msg(f"{_CRIT}They need to be on the table for chrome work.{_N}")
            return node_medical_main(caller, raw_string, target=target, compact=True, operating_table=table)
        if action_id == "cyber_install":
            cw = None
            for o in caller.contents:
                if o.id == target_info:
                    cw = o
                    break
            success, msg = start_cybersurgery_install(caller, target, table, cw) if cw else (False, "Chrome is missing from your hands.")
        elif action_id == "cyber_remove":
            success, msg = start_cybersurgery_remove(caller, target, table, str(target_info))
        elif action_id == "chrome_replace":
            if isinstance(target_info, (tuple, list)) and len(target_info) == 2:
                organ_key, replacement_id = target_info
            else:
                caller.msg(f"{_CRIT}Bad data. Try again.{_N}")
                return node_medical_main(caller, raw_string, target=target, compact=True, operating_table=table)
            replacement_obj = None
            for o in caller.contents:
                if o.id == replacement_id:
                    replacement_obj = o
                    break
            if not replacement_obj or getattr(replacement_obj, "chrome_replacement_for", None) != organ_key:
                caller.msg(f"{_CRIT}You don't have the right replacement.{_N}")
                return node_medical_main(caller, raw_string, target=target, compact=True, operating_table=table)
            success, msg = start_cybersurgery_replace(caller, target, table, str(organ_key))
        else:
            success, msg = start_cybersurgery_repair(caller, target, table, str(target_info))
    else:
        if not tool.consume_use():
            caller.msg(f"{_WARN}Empty. That tool has nothing left to give.{_N}")
            return node_medical_main(caller, raw_string, target=target, compact=True, operating_table=operating_table)
        success, msg = tool.use_for_treatment(caller, target, action_id, target_info)
 
    # Result messaging — the treatment functions already produce visceral text.
    # We wrap in color and relay to the patient.
    if success:
        caller.msg(f"{_GOOD}{msg}{_N}")
        if target != caller:
            caller_name = caller.get_display_name(target) if hasattr(caller, "get_display_name") else caller.name
            target.msg(f"{_GOOD}{caller_name} works on you. {msg[:80]}{_N}")
    else:
        caller.msg(f"{_CRIT}{msg}{_N}")
        if target != caller:
            caller_name = caller.get_display_name(target) if hasattr(caller, "get_display_name") else caller.name
            target.msg(f"{_CRIT}{caller_name} tries something. {msg[:80]}{_N}")
 
    log = getattr(caller.ndb, "_medical_session_log", None) or []
    abbrev = display_name[:20] if len(display_name) > 20 else display_name
    log.append(f"{'done' if success else 'FAIL'}: {abbrev}")
    caller.ndb._medical_session_log = log[-8:]
    return node_medical_main(caller, raw_string, target=target, compact=True, operating_table=operating_table)
 
 
def node_wound_detail(caller, raw_string, **kwargs):
    """Individual wound breakdown. Clinical shorthand, no game numbers."""
    target = kwargs.get("target") or _get_menu_target(caller, kwargs)
    if not target:
        return node_medical_main(caller, raw_string)
 
    injuries = target.db.injuries or []
    active = [i for i in injuries if (i.get("hp_occupied", 0) or 0) > 0]
 
    sev_words = {1: "superficial", 2: "moderate", 3: "deep", 4: "catastrophic"}
    type_words = {
        "cut": "laceration", "bruise": "contusion", "gunshot": "ballistic wound",
        "trauma": "blunt trauma", "arcane": "arcane burn", "surgery": "surgical wound",
        "burn": "thermal burn", "frostbite": "cryo injury", "electrocution": "arc burn",
        "dissolution": "void erosion",
    }
    quality_words = {0: "untouched", 1: "field dressed", 2: "sutured", 3: "surgically closed"}
    bleed_words = {
        (0.0, 1.0): "oozing",
        (1.0, 2.5): "bleeding",
        (2.5, 4.0): "haemorrhaging",
        (4.0, 99.0): "arterial",
    }
 
    def _bleed_word(rate):
        for (lo, hi), word in bleed_words.items():
            if lo <= rate < hi:
                return word
        return "bleeding"
 
    lines = [
        "",
        _line(),
        f"  {_HEADER_COLOR}W O U N D   D E T A I L{_N}",
        _line(),
        "",
    ]
 
    if not active:
        lines.append(f"  {_GOOD}No open wounds.{_N}")
    else:
        for idx, inj in enumerate(active, 1):
            part = (inj.get("body_part") or "unknown").strip()
            itype = type_words.get(inj.get("type", "trauma"), "wound")
            sev = sev_words.get(inj.get("severity", 1), "wound")
            treated = inj.get("treated", False)
            quality = quality_words.get(inj.get("treatment_quality", 0), "untouched")
 
            # Wound headline
            if treated:
                status = f"{_GOOD}{quality}{_N}"
            else:
                status = f"{_CRIT}open{_N}"
            lines.append(f"  {_LABEL_COLOR}{idx}.{_N} {_WARN}{part}{_N} — {sev} {itype} [{status}]")
 
            # Sub-details as indented lines
            details = []
            bleed = float(inj.get("bleed_rate", 0.0) or 0.0)
            if bleed > 0 and not inj.get("bleed_treated"):
                word = _bleed_word(bleed)
                details.append(f"{_CRIT}{word}{_N}")
 
            inf_stage = int(inj.get("infection_stage", 0) or 0)
            if inf_stage > 0:
                inf_words = {1: "localised", 2: "spreading", 3: "systemic", 4: "septic"}
                inf_word = inf_words.get(min(inf_stage, 4), "infected")
                color = _CRIT if inf_stage >= 3 else MC["infection"]
                inf_type = inj.get("infection_type") or ""
                from world.medical.infection import INFECTION_CATALOG
                inf_label = INFECTION_CATALOG.get(inf_type, {}).get("label", "")
                details.append(f"{color}{inf_word}{_N}" + (f" {_DIM}({inf_label}){_N}" if inf_label else ""))
 
            fracture = inj.get("fracture")
            if fracture:
                from world.medical import BONE_INFO
                bone_name = BONE_INFO.get(fracture, fracture)
                splinted = fracture in (target.db.splinted_bones or [])
                sp = f" {_DIM}[set]{_N}" if splinted else ""
                details.append(f"{_WARN}fracture: {bone_name}{_N}{sp}")
 
            organ_dmg = inj.get("organ_damage") or {}
            if organ_dmg:
                organ_labels = {
                    "brain": "neuro", "eyes": "ocular", "throat": "airway",
                    "carotid": "carotid", "heart": "cardiac", "lungs": "pulmonary",
                    "spine_cord": "spinal", "liver": "hepatic", "spleen": "splenic",
                    "stomach": "gastric", "kidneys": "renal", "pelvic_organs": "pelvic",
                    "collarbone_area": "shoulder",
                }
                od_parts = []
                for k, v in organ_dmg.items():
                    if v > 0:
                        ol = organ_labels.get(k, k)
                        od_parts.append(f"{ol}")
                if od_parts:
                    details.append(f"{_CRIT}internal: {', '.join(od_parts)}{_N}")
 
            if details:
                lines.append(f"     {' | '.join(details)}")
            lines.append("")
 
    lines.append(_line())
 
    text = "\n".join(lines)
    options = [
        {"key": "b", "desc": "Back", "goto": ("node_medical_main", {"target": target, "compact": True, "operating_table": kwargs.get("operating_table")})},
        {"key": "q", "desc": "Step back", "goto": "node_medical_exit"},
    ]
    return text, options
 
 
def node_confirm_action(caller, raw_string, **kwargs):
    target = kwargs.get("target")
    action_desc = kwargs.get("action_desc", "this")
    proceed_kwargs = kwargs.get("proceed_kwargs", {})
    operating_table = kwargs.get("operating_table")
 
    text = f"""
{_line()}
  {_WARN}You are about to:{_N} {action_desc}
 
  {_DIM}This is not easily undone.{_N}
{_line()}
"""
    options = [
        {"key": ("y", "yes", "1"), "desc": "Do it", "goto": ("node_do_treatment", proceed_kwargs)},
        {"key": ("n", "no", "2"), "desc": "Step back", "goto": ("node_medical_main", {"target": target, "compact": True, "operating_table": operating_table})},
    ]
    return text, options
 
 
def node_medical_exit(caller, raw_string, **kwargs):
    caller.msg(f"{_DIM}You step back from the patient.{_N}")
    return None, None
 
 
def start_medical_menu(caller, target):
    from evennia.utils.evmenu import EvMenu
    EvMenu(
        caller,
        "world.medical.medical_menu",
        startnode="node_medical_main",
        target=target,
        persistent=False,
    )
 