"""
Rich bioscanner readout: vitals randomized by HP state for immersion.
BP, SpO2, HR, RR, temp, status line; plausible ranges per health tier.
 
All output is fully in-character. The readout is what a medical scanner
displays — terse, clinical, machine-generated. No game terms, no HP, no
percentages labeled as game mechanics. The device speaks in vitals, tissue
states, and threat assessments.
"""
import random
from world.medical import (
    _ensure_medical_db,
    get_infection_readout,
    get_active_bleed_wounds,
    ORGAN_INFO,
    BONE_INFO,
)
from world.medical.injuries import (
    _normalize_injuries,
    compute_effective_bleed_level,
    rebuild_derived_trauma_views,
)
from world.medical.limb_trauma import is_limb_destroyed, LIMB_INFO, LIMB_SLOTS
from world.theme_colors import COMBAT_COLORS as CC, MEDICAL_COLORS as MC
 
# ── Visual constants ─────────────────────────────────────────────────────────
 
_DIM = "|x"
_N = "|n"
_W = "|w"
_C = CC["parry"]
_Y = MC["compensated"]
_R = MC["critical"]
_G = MC["stable"]
_M = MC["infection"]
_BORDER = "|x"
_WIDTH = 56
 
 
def _rule(char="-"):
    return f"{_BORDER}  {''.ljust(_WIDTH, char)}{_N}"
 
 
def _heavy():
    return f"{_BORDER}  {''.ljust(_WIDTH, '=')}{_N}"
 
 
def _section(title):
    return f"\n{_rule()}\n  {_C}{title}{_N}\n{_rule()}"
 
 
# ── Vital generation ─────────────────────────────────────────────────────────
 
def _vital_ranges(pct):
    if pct >= 100:
        return (112, 128), (68, 82), (97, 100), (58, 78), (12, 16), (365, 370), "stable"
    if pct >= 85:
        return (108, 124), (66, 80), (96, 99), (62, 88), (12, 18), (364, 369), "stable"
    if pct >= 65:
        return (98, 118), (60, 76), (94, 98), (72, 98), (14, 22), (363, 368), "compensated"
    if pct >= 45:
        return (88, 108), (54, 70), (90, 96), (88, 112), (18, 26), (362, 367), "compromised"
    if pct >= 25:
        return (78, 98), (48, 64), (85, 93), (98, 128), (22, 32), (360, 366), "critical"
    if pct >= 5:
        return (65, 85), (40, 55), (78, 88), (110, 140), (28, 38), (358, 364), "failing"
    return (50, 75), (30, 48), (65, 82), (40, 120), (4, 12), (355, 362), "arrest"
 
 
def _rand(lo, hi):
    return random.randint(lo, hi)
 
 
def _temp_fmt(decicelsius):
    return "{:.1f}".format(decicelsius / 10.0)
 
 
_STATUS_DISPLAY = {
    "stable": f"{_G}STABLE{_N}",
    "compensated": f"{_Y}COMPENSATED{_N}",
    "compromised": f"{_Y}COMPROMISED{_N}",
    "critical": f"{_R}CRITICAL{_N}",
    "failing": f"{_R}FAILING{_N}",
    "arrest": f"{MC['arrest']}ARREST{_N}",
}
 
 
# ── Perfusion bar ────────────────────────────────────────────────────────────
 
def _perfusion_bar(current, maximum, width=24):
    if maximum <= 0:
        maximum = 1
    ratio = current / maximum
    filled = max(0, min(width, int(width * ratio)))
    empty = width - filled
    if ratio >= 0.8:
        color = _G
    elif ratio >= 0.4:
        color = _Y
    else:
        color = _R
    return f"{_BORDER}[{_N}{color}{'|' * filled}{_BORDER}{'.' * empty}{_N}{_BORDER}]{_N}"
 
 
# ── In-character label maps ──────────────────────────────────────────────────
 
_ORGAN_LABELS = {
    "brain": "cerebral", "eyes": "ocular", "throat": "laryngeal",
    "carotid": "carotid", "collarbone_area": "subclavian complex",
    "heart": "cardiac", "lungs": "pulmonary", "spine_cord": "spinal cord",
    "liver": "hepatic", "spleen": "splenic", "stomach": "gastric",
    "kidneys": "renal", "pelvic_organs": "pelvic viscera",
}
 
_ORGAN_SEVERITY = {
    1: "contusion / minor insult",
    2: "structural compromise",
    3: f"{MC['arrest']}NON-VIABLE — replacement indicated{_N}",
}
 
_BONE_LABELS = {
    "skull": "cranial vault", "jaw": "mandible", "nose": "nasal complex",
    "cervical_spine": "cervical vertebrae", "clavicle": "clavicle",
    "scapula": "scapula", "humerus": "humerus", "metacarpals": "metacarpals",
    "ribs": "thoracic cage", "spine": "vertebral column",
    "pelvis": "pelvic ring", "femur": "femur", "ankle": "talocrural joint",
    "metatarsals": "metatarsals",
}
 
_VESSEL_LABELS = {
    "arterial": f"{_R}arterial{_N}",
    "venous": f"{_Y}venous{_N}",
    "capillary": f"{_DIM}capillary{_N}",
    "none": f"{_DIM}sealed{_N}",
}
 
_BLEED_SEVERITY = [
    (0.5, f"{_DIM}trace{_N}"),
    (1.5, f"{_Y}active{_N}"),
    (2.5, f"{_Y}significant{_N}"),
    (3.5, f"{_R}severe{_N}"),
    (999, f"{MC['arrest']}critical{_N}"),
]
 
_INFECTION_STAGE_LABELS = {
    1: "localised inflammation",
    2: "tissue-level spread",
    3: "systemic involvement",
    4: f"{MC['arrest']}septic cascade{_N}",
}
 
_RECOVERY_LABELS = {
    "acute": f"{_R}acute — implant at reduced capacity{_N}",
    "adapting": f"{_Y}adapting — interface stabilising{_N}",
    "integrated": f"{_G}integrated{_N}",
}
 
 
def _bleed_word(rate):
    for threshold, label in _BLEED_SEVERITY:
        if rate <= threshold:
            return label
    return f"{MC['arrest']}critical{_N}"
 
 
# ── Main readout builder ─────────────────────────────────────────────────────
 
def get_scanner_readout(target):
    """
    Build a full bioscanner readout. In-character medical device output.
    No game terms. The scanner is a machine. It speaks in data.
    """
    _ensure_medical_db(target)
    rebuild_derived_trauma_views(target)
 
    hp = getattr(target, "hp", 0)
    mx = getattr(target, "max_hp", 1) or 1
    pct = (hp / mx * 100) if mx > 0 else 0
    in_arrest = pct <= 0
 
    infections = get_infection_readout(target)
    max_inf_stage = max([i.get("stage", 0) for i in infections], default=0)
 
    # ── Header ───────────────────────────────────────────────────────────
    lines = [
        "",
        _heavy(),
        f"  {_C}B I O S C A N N E R{_N}",
        _heavy(),
    ]
 
    # ── Vitals ───────────────────────────────────────────────────────────
    lines.append(f"\n  {_W}VITALS{_N}")
    lines.append(_rule())
 
    if in_arrest:
        status = _STATUS_DISPLAY["arrest"]
        lines.append(f"  {_W}BP{_N}    ---/---          {_W}SpO2{_N}  ---         {_W}Status{_N} {status}")
        lines.append(f"  {_W}HR{_N}    ---              {_W}RR{_N}    ---         {_W}Temp{_N}   {_DIM}cooling{_N}")
    else:
        bp_sys_r, bp_dia_r, spo2_r, hr_r, rr_r, temp_r, status_key = _vital_ranges(pct)
 
        # Infection modifies vitals: fever and tachycardia
        if max_inf_stage >= 2:
            temp_r = (max(temp_r[0], 374), max(temp_r[1], 389 if max_inf_stage >= 3 else 382))
            hr_r = (max(hr_r[0], 94), max(hr_r[1], 150 if max_inf_stage >= 3 else 130))
            if status_key in ("stable", "compensated"):
                status_key = "compromised"
            if max_inf_stage >= 4:
                status_key = "critical"
 
        bp_sys = _rand(*bp_sys_r)
        bp_dia = _rand(*bp_dia_r)
        spo2 = _rand(*spo2_r)
        hr = _rand(*hr_r)
        rr = _rand(*rr_r)
        temp = _rand(*temp_r)
        status = _STATUS_DISPLAY.get(status_key, status_key.upper())
 
        # Color vitals individually based on danger thresholds
        bp_color = _R if bp_sys < 80 else (_Y if bp_sys < 100 else _N)
        spo2_color = _R if spo2 < 88 else (_Y if spo2 < 94 else _N)
        hr_color = _R if (hr > 130 or hr < 50) else (_Y if (hr > 100 or hr < 60) else _N)
        rr_color = _R if (rr > 30 or rr < 8) else (_Y if (rr > 22 or rr < 12) else _N)
        temp_color = _R if temp > 385 else (_Y if temp > 375 else _N)
 
        lines.append(
            f"  {_W}BP{_N}    {bp_color}{bp_sys:3d}/{bp_dia:<3d}{_N} mmHg"
            f"    {_W}SpO2{_N}  {spo2_color}{spo2:2d}%{_N}"
            f"         {_W}Status{_N} {status}"
        )
        lines.append(
            f"  {_W}HR{_N}    {hr_color}{hr:3d}{_N} bpm"
            f"          {_W}RR{_N}    {rr_color}{rr:2d}{_N}/min"
            f"       {_W}Temp{_N}   {temp_color}{_temp_fmt(temp)}{_N} C"
        )
 
    # ── Perfusion ────────────────────────────────────────────────────────
    lines.append(f"\n  {_W}PERFUSION{_N}")
    lines.append(_rule())
 
    bar = _perfusion_bar(hp, mx)
    if in_arrest:
        perf_label = f"{MC['arrest']}no perfusion detected{_N}"
    elif pct >= 80:
        perf_label = f"{_G}adequate{_N}"
    elif pct >= 50:
        perf_label = f"{_Y}diminished{_N}"
    elif pct >= 25:
        perf_label = f"{_R}critical deficit{_N}"
    else:
        perf_label = f"{MC['arrest']}near-total depletion{_N}"
 
    lines.append(f"  {bar}  {perf_label}")
 
    # ── Haemorrhage ──────────────────────────────────────────────────────
    lines.append(_section("HAEMORRHAGE"))
 
    active_bleeds = get_active_bleed_wounds(target)
    bleed_level, _ = compute_effective_bleed_level(target)
 
    if not active_bleeds and bleed_level <= 0:
        lines.append(f"  {_G}No active haemorrhage detected.{_N}")
    else:
        for w in active_bleeds:
            part = (w.get("body_part") or "unknown").strip()
            rate = float(w.get("bleed_rate", 0.0) or 0.0)
            vessel = w.get("vessel_type") or "capillary"
            vessel_display = _VESSEL_LABELS.get(vessel, vessel)
            severity = _bleed_word(rate)
            lines.append(f"  {_W}{part}{_N}: {severity}, {vessel_display}")
        if bleed_level >= 3:
            lines.append(f"  {_R}>> HAEMORRHAGE CONTROL REQUIRED IMMEDIATELY{_N}")
 
    # ── Trauma ───────────────────────────────────────────────────────────
    lines.append(_section("INTERNAL ASSESSMENT"))
 
    organ_damage = target.db.organ_damage or {}
    has_organ = False
    if organ_damage:
        for organ_key, sev in sorted(organ_damage.items()):
            if sev <= 0:
                continue
            has_organ = True
            label = _ORGAN_LABELS.get(organ_key, organ_key)
            severity = _ORGAN_SEVERITY.get(min(sev, 3), "insult noted")
            stab = f" {_DIM}[stabilised]{_N}" if (target.db.stabilized_organs or {}).get(organ_key) else ""
            lines.append(f"  {_W}{label}{_N}: {severity}{stab}")
    if not has_organ:
        lines.append(f"  {_G}No organ insult detected.{_N}")
 
    # ── Fractures ────────────────────────────────────────────────────────
    fractures = target.db.fractures or []
    splinted = target.db.splinted_bones or []
    if fractures:
        lines.append(f"\n  {_W}SKELETAL{_N}")
        lines.append(_rule())
        for bone in fractures:
            label = _BONE_LABELS.get(bone, bone)
            immob = f" {_DIM}[immobilised]{_N}" if bone in splinted else f" {_Y}[unstable]{_N}"
            lines.append(f"  {_W}{label}{_N}: discontinuity{immob}")
 
    # ── Wound inventory ──────────────────────────────────────────────────
    lines.append(_section("WOUND INVENTORY"))
 
    injuries = _normalize_injuries(target) or []
    active_wounds = [i for i in injuries if (i.get("hp_occupied", 0) or 0) > 0]
 
    _type_labels = {
        "cut": "laceration", "bruise": "contusion", "gunshot": "ballistic wound",
        "trauma": "blunt trauma", "arcane": "arcane burn", "surgery": "surgical wound",
        "burn": "thermal injury", "frostbite": "cryo injury", "electrocution": "arc injury",
        "dissolution": "void erosion",
    }
    _sev_labels = {1: "superficial", 2: "moderate", 3: "deep", 4: "catastrophic"}
    _quality_labels = {0: "untreated", 1: "field dressed", 2: "sutured", 3: "surgically closed"}
 
    if not active_wounds:
        lines.append(f"  {_G}No open wounds.{_N}")
    else:
        for idx, inj in enumerate(active_wounds, 1):
            part = (inj.get("body_part") or "unspecified").strip()
            wtype = _type_labels.get(inj.get("type", "trauma"), "wound")
            sev = _sev_labels.get(inj.get("severity", 1), "wound")
            treated = inj.get("treated", False)
            quality = _quality_labels.get(inj.get("treatment_quality", 0), "untreated")
 
            if treated:
                status = f"{_G}{quality}{_N}"
            else:
                status = f"{_R}open{_N}"
 
            lines.append(f"  {_DIM}{idx}.{_N} {_W}{part}{_N} — {sev} {wtype} [{status}]")
 
    # ── Infection ────────────────────────────────────────────────────────
    lines.append(_section("PATHOGEN ALERTS"))
 
    if not infections:
        lines.append(f"  {_G}No pathogens detected.{_N}")
    else:
        for inf in infections:
            part = inf.get("body_part", "wound").strip()
            label = inf.get("label", "unknown pathogen")
            stage = inf.get("stage", 0)
            stage_label = _INFECTION_STAGE_LABELS.get(stage, "progressing")
            if stage >= 4:
                color = MC["arrest"]
            elif stage >= 3:
                color = _R
            else:
                color = _M
            lines.append(f"  {_W}{part}{_N}: {color}{label}{_N}")
            lines.append(f"     {_DIM}stage:{_N} {stage_label}")
        if max_inf_stage >= 3:
            lines.append(f"  {_R}>> SYSTEMIC INFECTION — IMMEDIATE TREATMENT REQUIRED{_N}")
 
    # ── Cyberware ────────────────────────────────────────────────────────
    cyber = list(getattr(target.db, "cyberware", None) or [])
    if cyber:
        lines.append(_section("INSTALLED CYBERWARE"))
 
        for cw in cyber:
            chrome_hp = getattr(cw.db, "chrome_hp", None)
            chrome_max = getattr(cw.db, "chrome_max_hp", None)
            malfunctioning = bool(getattr(cw.db, "malfunctioning", False))
 
            # Determine recovery phase from associated surgery wound
            recovery = "integrated"
            for inj in injuries:
                if inj.get("cyberware_dbref") == cw.id and inj.get("recovery_phase"):
                    recovery = inj.get("recovery_phase")
                    break
            recovery_display = _RECOVERY_LABELS.get(recovery, f"{_G}integrated{_N}")
 
            # Chrome structural integrity
            if chrome_hp is not None and chrome_max is not None and chrome_max > 0:
                chrome_pct = chrome_hp / chrome_max
                if chrome_pct >= 0.8:
                    integrity = f"{_G}nominal{_N}"
                elif chrome_pct >= 0.5:
                    integrity = f"{_Y}degraded{_N}"
                elif chrome_pct >= 0.2:
                    integrity = f"{_R}compromised{_N}"
                elif chrome_pct > 0:
                    integrity = f"{MC['arrest']}failing{_N}"
                else:
                    integrity = f"{MC['arrest']}DESTROYED{_N}"
            else:
                integrity = f"{_DIM}n/a{_N}"
 
            # Functional status
            if malfunctioning:
                func_status = f"{MC['arrest']}MALFUNCTION{_N}"
            else:
                func_status = f"{_G}operational{_N}"
 
            lines.append(f"  {_W}{cw.key}{_N}")
            lines.append(f"     function: {func_status}  integrity: {integrity}")
            if recovery != "integrated":
                lines.append(f"     recovery: {recovery_display}")
 
            # EMP glitch state
            import time
            glitch_until = float(getattr(cw.db, "emp_glitch_until", 0.0) or 0.0)
            if glitch_until > time.time():
                remaining = int(glitch_until - time.time())
                lines.append(f"     {_R}>> EMP DISRUPTION — {remaining}s remaining{_N}")
 
    # ── Destroyed organs ─────────────────────────────────────────────────
    destroyed = []
    for organ_key, sev in (target.db.organ_damage or {}).items():
        if int(sev or 0) < 3:
            continue
        for inj in injuries:
            if organ_key in (inj.get("organ_damage") or {}) and inj.get("organ_destroyed"):
                organ_name = ORGAN_INFO.get(organ_key, (organ_key,))[0]
                destroyed.append((_ORGAN_LABELS.get(organ_key, organ_key), organ_name))
                break
    if destroyed:
        lines.append(_section("ORGAN REPLACEMENT REQUIRED"))
        for label, name in destroyed:
            lines.append(f"  {_W}{label}{_N}: {MC['arrest']}non-viable — chrome replacement indicated{_N}")

    destroyed_limbs = []
    for limb_key in LIMB_SLOTS:
        if int((target.db.limb_damage or {}).get(limb_key, 0) or 0) < 3:
            continue
        if is_limb_destroyed(target, limb_key):
            destroyed_limbs.append(LIMB_INFO.get(limb_key, (limb_key,))[0])
    if destroyed_limbs:
        lines.append(_section("LIMB REPLACEMENT REQUIRED"))
        for name in destroyed_limbs:
            lines.append(f"  {_W}{name}{_N}: {MC['arrest']}non-viable — prosthetic replacement indicated{_N}")
 
    # ── Footer ───────────────────────────────────────────────────────────
    lines.append("")
    lines.append(_heavy())
    lines.append(f"  {_DIM}scan complete{_N}")
    lines.append("")
 
    return "\n".join(lines)
 