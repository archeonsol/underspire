"""
Cybersurgery pipeline: install/remove/replace/repair with phased narrative flow.
"""

import random
import time
from evennia.utils import delay

from world.body import get_cyberware_for_part
from world.medical import add_injury, rebuild_derived_trauma_views, ORGAN_INFO
from world.medical.medical_surgery import ORGAN_SURGERY_NARRATIVES
from world.medical.cybersurgery_narratives import (
    get_install_narrative,
    get_removal_narrative,
    get_narrative_step_count,
)

CYBERSURGERY_STAMINA_PER_PHASE = 3
PHASE_DELTA = 7

_BLOOD_LOSS_TO_BLEED = {"none": 0.0, "minor": 1.0, "moderate": 2.0, "severe": 3.0}
_COMPLICATION_WEIGHTS = {
    "prep": [("bleeding", 4), ("tool_slip", 1), ("patient_movement", 2)],
    "interface": [("rejection_flare", 3), ("bleeding", 2), ("patient_movement", 2)],
    "vascular": [("bleeding", 5), ("tool_slip", 1), ("patient_movement", 2)],
    "neural": [("nerve_damage", 4), ("rejection_flare", 2), ("patient_movement", 2)],
    "integration": [("rejection_flare", 3), ("tool_slip", 2), ("patient_movement", 2)],
    "closure": [("bleeding", 2), ("tool_slip", 1)],
}


def _cwattr(cw, key, default=None):
    db = getattr(cw, "db", None)
    if db and hasattr(db, key):
        val = getattr(db, key, None)
        if val is not None:
            return val
    return getattr(cw, key, default)


def _get_object_by_id(dbref):
    if dbref is None:
        return None
    try:
        from world.combat import _get_object_by_id as combat_resolve
        return combat_resolve(dbref)
    except Exception:
        pass
    try:
        from evennia.utils.search import search_object
        res = search_object("#%s" % int(dbref))
        return res[0] if res else None
    except Exception:
        return None


def _cybersurgery_roll(operator, difficulty=0, modifier=0):
    if not hasattr(operator, "roll_check"):
        return 0, 0
    result, value = operator.roll_check(
        ["intelligence", "agility"],
        "cyber_surgery",
        difficulty=difficulty,
        modifier=modifier,
    )
    if result == "Critical Success":
        return 3, value
    if result == "Full Success":
        return 2, value
    if result == "Marginal Success":
        return 1, value
    return 0, value


def _is_sedated(target):
    now = time.time()
    if float(getattr(target.db, "sedated_until", 0.0) or 0.0) > now:
        return True
    if bool(getattr(target.db, "unconscious", False)):
        wake_at = float(getattr(target.db, "unconscious_until", 0.0) or 0.0)
        return wake_at <= 0.0 or wake_at > now
    return False


def _table_bonus():
    return -20


def _check_cyberware_conflicts(target, cyberware_obj):
    from typeclasses.cyberware import CyberwareBase
    if not isinstance(cyberware_obj, CyberwareBase):
        return "That is not cyberware."
    installed = list(target.db.cyberware or [])
    if any(type(c) is type(cyberware_obj) for c in installed):
        return f"{type(cyberware_obj).__name__} is already installed."
    installed_types = {type(c).__name__ for c in installed}
    for conflict_name in (getattr(cyberware_obj, "conflicts_with", None) or []):
        if conflict_name in installed_types:
            return f"Conflicts with installed {conflict_name}."
    reqs = list(getattr(cyberware_obj, "required_implants", None) or [])
    if reqs:
        for req in reqs:
            if req not in installed_types:
                return f"Requires {req}."
    req_any = list(getattr(cyberware_obj, "required_implants_any", None) or [])
    if req_any and not any(req in installed_types for req in req_any):
        return f"Requires one of: {', '.join(req_any)}."
    locked = target.db.locked_descriptions or {}
    for part, (mode, _) in (getattr(cyberware_obj, "body_mods", None) or {}).items():
        if mode == "lock" and part in locked:
            return f"Body part '{part}' is already locked by installed cyberware."
    return None


def _phase_names_for(cyberware_obj):
    category = (_cwattr(cyberware_obj, "surgery_category", "implant") or "implant").lower()
    if category in ("limb", "neural"):
        return ["prep", "interface", "vascular", "neural", "integration", "closure"]
    return ["prep", "interface", "integration", "closure"]


def _room_msg(caller, target, table, txt=None):
    loc = table.location if table else caller.location
    if not loc or not hasattr(loc, "contents_get"):
        return
    for v in loc.contents_get(content_type="character"):
        if v in (caller, target):
            continue
        c = caller.get_display_name(v) if hasattr(caller, "get_display_name") else caller.name
        t = target.get_display_name(v) if hasattr(target, "get_display_name") else target.name
        v.msg(txt or f"{c} works over {t} - chrome surgery. The theatre hums with power tools and ozone.")


def _select_complication(phase):
    pool = _COMPLICATION_WEIGHTS.get(phase, _COMPLICATION_WEIGHTS["integration"])
    weighted = []
    for key, wt in pool:
        weighted.extend([key] * max(1, int(wt)))
    return random.choice(weighted) if weighted else None


def _apply_complication(state, phase):
    caller = state["caller"]
    target = state["target"]
    injuries = target.db.injuries or []
    surgery_injury = None
    for i in reversed(injuries):
        if i.get("injury_id") == state.get("injury_id"):
            surgery_injury = i
            break
    kind = _select_complication(phase)
    if not kind:
        return
    state["complications"] += 1
    if kind == "bleeding":
        if surgery_injury:
            surgery_injury["bleed_rate"] = float(surgery_injury.get("bleed_rate", 0.0) or 0.0) + random.choice((1.0, 2.0))
            surgery_injury["bleed_treated"] = False
        caller.msg("|rA vessel tears. Blood fills the field. You clamp and pack. The clock is ticking.|n")
    elif kind == "nerve_damage":
        state["neural_debuff"] = True
        caller.msg("|rThe nerve trunk recoils from the interface. Damage. You work around it but function will be reduced.|n")
    elif kind == "rejection_flare":
        if surgery_injury:
            surgery_injury["infection_risk"] = min(1.0, float(surgery_injury.get("infection_risk", 0.0) or 0.0) + random.uniform(0.15, 0.25))
        caller.msg("|rThe tissue rejects the interface. Inflammation blooms. You administer immunosuppressant and push through.|n")
    elif kind == "tool_slip":
        add_injury(caller, 3, body_part="right hand", weapon_key="surgery")
        caller.msg("|rThe retractor slips. You cut yourself. You clamp your hand, re-glove, and continue.|n")
    elif kind == "patient_movement":
        state["next_check_penalty"] += 10
        caller.msg("|rThey move. The field shifts. You bark at them to stay still. The work is harder now.|n")
    target.db.injuries = injuries


def _consume_stamina(state):
    caller = state["caller"]
    cur = int(getattr(caller.db, "current_stamina", 0) or 0)
    cur -= CYBERSURGERY_STAMINA_PER_PHASE
    caller.db.current_stamina = max(0, cur)
    if cur <= 0:
        state["exhausted_phases"] += 1


def _primary_body_part(cyberware_obj):
    if getattr(cyberware_obj, "surgery_body_part", None):
        return cyberware_obj.surgery_body_part
    mods = getattr(cyberware_obj, "body_mods", None) or {}
    for part, (mode, _) in mods.items():
        if mode == "lock":
            return part
    return next(iter(mods), "torso")


def _create_surgery_wound(target, cyberware_obj):
    part = _primary_body_part(cyberware_obj)
    iid = add_injury(target, max(8, int(_cwattr(cyberware_obj, "surgery_wound_hp", 8) or 8)), body_part=part, weapon_key="surgery")
    injuries = target.db.injuries or []
    for i in reversed(injuries):
        if i.get("injury_id") == iid:
            i["bleed_rate"] = max(float(i.get("bleed_rate", 0.0) or 0.0), _BLOOD_LOSS_TO_BLEED.get(_cwattr(cyberware_obj, "surgery_blood_loss", "moderate"), 2.0))
            i["bleed_treated"] = False
            break
    target.db.injuries = injuries
    return iid


def _final_install_outcome(state):
    caller = state["caller"]
    target = state["target"]
    table = state["table"]
    cw = state["cyberware"]
    try:
        injuries = target.db.injuries or []
        injury = None
        for i in reversed(injuries):
            if i.get("injury_id") == state.get("injury_id"):
                injury = i
                break
        base = int(_cwattr(cw, "surgery_difficulty", 15) or 15)
        if not state["sedated"]:
            base += 18
        bleed_lvl = int(getattr(target.db, "bleeding_level", 0) or 0)
        if bleed_lvl >= 3:
            base += 8
        if state["complications"] >= 2:
            base += 5 * (state["complications"] - 1)
        base += state["next_check_penalty"]
        base += (state["exhausted_phases"] * 5)
        final_difficulty = max(0, base + _table_bonus())
        success_level, _ = _cybersurgery_roll(caller, difficulty=final_difficulty, modifier=0)

        if success_level == 0:
            caller.msg("|rThe interface won't seat. Tissue rejection, poor alignment, or bad luck. The implant comes back out. You close what you can.|n")
            if injury:
                injury["treated"] = True
                injury["treatment_quality"] = 1
            target.db.injuries = injuries
            _room_msg(caller, target, table)
            return

        if success_level == 3:
            tq = 3
            restore_ratio = 0.30
            rejection = 0.0
        elif success_level == 2:
            tq = 2
            restore_ratio = 0.20
            rejection = float(_cwattr(cw, "surgery_rejection_risk", 0.05) or 0.05)
        else:
            tq = 1
            restore_ratio = 0.0
            rejection = float(_cwattr(cw, "surgery_rejection_risk", 0.05) or 0.05) * 2.0
            if injury:
                injury["infection_risk"] = min(1.0, float(injury.get("infection_risk", 0.0) or 0.0) + 0.1)

        res = target.install_cyberware(cw, skip_surgery=True)
        if res is not True:
            caller.msg(f"|rInstall failed after procedure: {res}|n")
            return
        # Defensive persistence: ensure installed list actually contains this object.
        installed = list(target.db.cyberware or [])
        if not any(getattr(obj, "id", None) == getattr(cw, "id", None) for obj in installed):
            installed.append(cw)
            target.db.cyberware = installed

        if success_level == 3:
            caller.msg("|gThe implant seats perfectly. Interface is clean. Response is immediate. This is textbook work.|n")
        elif success_level == 2:
            caller.msg("|gThe implant takes. Interface holds. Function confirmed. Good work.|n")
        else:
            caller.msg("|yThe implant seats, but the interface is rough. It'll work. It won't be pretty. Watch for rejection.|n")

        if injury:
            injury["treated"] = True
            injury["treatment_quality"] = tq
            hp_occ = float(injury.get("hp_occupied", 0) or 0)
            restore = int(round(hp_occ * restore_ratio))
            injury["hp_occupied"] = max(0, hp_occ - restore)
            target.db.current_hp = min(getattr(target, "max_hp", 100) or 100, int((target.db.current_hp or 0) + restore))
            injury["cyberware_dbref"] = cw.id
            injury["rejection_risk"] = rejection
            injury["recovery_phase"] = "acute"
            injury["recovery_started"] = time.time()
            if state.get("neural_debuff"):
                injury["neural_minor_debuff"] = True
        target.db.injuries = injuries
        rebuild_derived_trauma_views(target)
        _room_msg(caller, target, table)
    finally:
        caller.db.surgery_in_progress = False


def _run_install_phase(ids, state, idx):
    caller = _get_object_by_id(ids[0])
    target = _get_object_by_id(ids[1])
    table = _get_object_by_id(ids[2])
    if not caller or not target:
        return
    state["caller"] = caller
    state["target"] = target
    state["table"] = table
    if idx >= len(state["phases"]):
        _final_install_outcome(state)
        return
    _consume_stamina(state)
    narratives = state.get("narratives") or []
    if idx < len(narratives):
        caller.msg("|w%s|n" % narratives[idx])
    if (not state["sedated"]) and idx > 0:
        target.msg("|r%s's hands are inside you. The pain is white noise. You feel something cold click into place.|n" % (caller.get_display_name(target) if hasattr(caller, "get_display_name") else caller.name))
    _room_msg(caller, target, table)
    phase = state["phases"][idx]
    base_comp = 0.03 + (0.02 * float(_cwattr(state["cyberware"], "surgery_difficulty", 15) or 15) / 15.0)
    risk_mult = 1.0 + (0.15 * idx)
    if random.random() < (base_comp * risk_mult):
        _apply_complication(state, phase)
    delay(PHASE_DELTA, lambda: _run_install_phase(ids, state, idx + 1))


def start_cybersurgery_install(caller, target, table, cyberware_obj, narrative_override=None):
    if getattr(caller.db, "surgery_in_progress", False):
        return False, "You are already in the middle of a procedure."
    if caller.location != table.location or table.get_patient() != target:
        return False, "Patient must be on the operating table with you present."
    if cyberware_obj.location != caller:
        return False, "You must hold the cyberware in your inventory."
    conflict = _check_cyberware_conflicts(target, cyberware_obj)
    if conflict:
        return False, conflict
    caller.db.surgery_in_progress = True
    sedated = _is_sedated(target)
    injury_id = _create_surgery_wound(target, cyberware_obj)
    state = {
        "caller": caller,
        "target": target,
        "table": table,
        "cyberware": cyberware_obj,
        "sedated": sedated,
        "injury_id": injury_id,
        "phases": _phase_names_for(cyberware_obj),
        "narratives": list(narrative_override or get_install_narrative(_cwattr(cyberware_obj, "surgery_narrative_key", None))),
        "complications": 0,
        "next_check_penalty": 0,
        "exhausted_phases": 0,
        "neural_debuff": False,
    }
    ids = (caller.id, target.id, table.id)
    _run_install_phase(ids, state, 0)
    return True, None


def start_cybersurgery_remove(caller, target, table, cyberware_name):
    if getattr(caller.db, "surgery_in_progress", False):
        return False, "You are already in the middle of a procedure."
    if caller.location != table.location or table.get_patient() != target:
        return False, "Patient must be on the operating table with you present."
    installed = list(target.db.cyberware or [])
    matches = [c for c in installed if c.key.lower() == cyberware_name.lower()]
    if not matches:
        return False, "That cyberware is not installed."
    cw = matches[0]
    injury_id = _create_surgery_wound(target, cw)
    removal_narratives = get_removal_narrative(_cwattr(cw, "surgery_narrative_key", None))
    removal_steps = get_narrative_step_count(_cwattr(cw, "surgery_narrative_key", None), is_removal=True)
    caller.msg("|w%s|n" % removal_narratives[0])
    for step in range(1, removal_steps):
        delay(PHASE_DELTA * step, lambda s=step: caller.msg("|w%s|n" % removal_narratives[s]))

    def _finish():
        base = max(0, int(_cwattr(cw, "surgery_difficulty", 15) or 15) - 5 + (_table_bonus()))
        lvl, _ = _cybersurgery_roll(caller, difficulty=base, modifier=0)
        injuries = target.db.injuries or []
        wound = None
        for i in reversed(injuries):
            if i.get("injury_id") == injury_id:
                wound = i
                break
        if lvl == 0:
            caller.msg("|rYou fail to safely extract the hardware. You close and stabilize what you can.|n")
            if wound:
                wound["treated"] = True
                wound["treatment_quality"] = 1
            caller.db.surgery_in_progress = False
            target.db.injuries = injuries
            return
        res = target.remove_cyberware(cw, skip_surgery=True)
        if res is not True:
            caller.msg(f"|rRemoval failed: {res}|n")
        else:
            if (_cwattr(cw, "surgery_category", "") or "").lower() == "limb":
                part = _primary_body_part(cw)
                missing = list(target.db.missing_body_parts or [])
                if part not in missing:
                    missing.append(part)
                target.db.missing_body_parts = missing
            caller.msg("|gYou extract the hardware and close successfully.|n")
            if wound:
                wound["treated"] = True
                wound["treatment_quality"] = 2
        target.db.injuries = injuries
        caller.db.surgery_in_progress = False
    caller.db.surgery_in_progress = True
    delay(PHASE_DELTA * removal_steps, _finish)
    return True, None


def find_chrome_replacement_in_inventory(operator, organ_key):
    for obj in operator.contents:
        if getattr(obj, "chrome_replacement_for", None) == organ_key:
            return obj
    return None


def is_organ_destroyed(target, organ_key):
    if int((target.db.organ_damage or {}).get(organ_key, 0) or 0) < 3:
        return False
    for i in (target.db.injuries or []):
        if organ_key in (i.get("organ_damage") or {}) and i.get("organ_destroyed"):
            return True
    return False


def start_cybersurgery_replace(caller, target, table, organ_key):
    if caller.location != table.location or table.get_patient() != target:
        return False, "Patient must be on the operating table with you present."
    if not is_organ_destroyed(target, organ_key):
        return False, "That organ is damaged but salvageable. Use regular surgery first."
    cw = find_chrome_replacement_in_inventory(caller, organ_key)
    if not cw:
        return False, "You need a chrome replacement organ. You don't have one."
    phases = _phase_names_for(cw)
    phase_count = len(phases)
    organ_open_narratives = ORGAN_SURGERY_NARRATIVES.get(organ_key) or []
    chrome_narratives = get_install_narrative(_cwattr(cw, "surgery_narrative_key", None))
    if organ_open_narratives:
        open_count = min(2, max(1, phase_count - 1))
        seat_count = max(1, phase_count - open_count)
        install_narratives = list(organ_open_narratives[:open_count]) + list(chrome_narratives[-seat_count:])
    else:
        install_narratives = list(chrome_narratives)
    ok, err = start_cybersurgery_install(caller, target, table, cw, narrative_override=install_narratives)
    if not ok:
        return ok, err
    # Organ cleanup happens at end of installation through polling wound on finish hook:
    # keep lightweight delayed clear to avoid coupling internals.
    def _clear_organ():
        od = dict(target.db.organ_damage or {})
        if organ_key in od:
            del od[organ_key]
        target.db.organ_damage = od
        rebuild_derived_trauma_views(target)
    delay(PHASE_DELTA * 8, _clear_organ)
    return True, None


def start_cybersurgery_repair(caller, target, table, cyberware_name):
    if caller.location != table.location or table.get_patient() != target:
        return False, "Patient must be on the operating table with you present."
    installed = list(target.db.cyberware or [])
    matches = [c for c in installed if c.key.lower() == cyberware_name.lower()]
    if not matches:
        return False, "That cyberware is not installed."
    cw = matches[0]
    diff = max(0, int(_cwattr(cw, "surgery_difficulty", 15) or 15) - 10 + _table_bonus())
    caller.db.surgery_in_progress = True
    caller.msg("|wYou open the interface housing and begin repair calibration.|n")

    def _finish():
        lvl, _ = _cybersurgery_roll(caller, difficulty=diff, modifier=0)
        if lvl == 0:
            caller.msg("|rRepair fails. The chrome remains unstable.|n")
        else:
            mx = int(getattr(cw.db, "chrome_max_hp", 100) or 100)
            cw.db.chrome_hp = mx
            cw.db.malfunctioning = False
            if getattr(cw, "buff_class", None):
                target.buffs.add(cw.buff_class)
            caller.msg("|gRepair successful. Systems nominal.|n")
        caller.db.surgery_in_progress = False

    delay(PHASE_DELTA * 2, _finish)
    return True, None


def apply_emp_effect(character, damage):
    cyberware = character.db.cyberware or []
    if not cyberware:
        return
    for cw in cyberware:
        glitch = min(0.4, float(damage) / 100.0)
        if random.random() < glitch:
            cw.db.emp_glitch_until = time.time() + random.uniform(30, 60)
            if getattr(cw, "buff_class", None):
                character.buffs.remove(cw.buff_class.key)
            character.msg(f"|c{cw.key} glitches. Static. Systems disrupted.|n")
    delay(65, _reapply_all_cyberware_buffs, character.id)


def _reapply_all_cyberware_buffs(character_id):
    character = _get_object_by_id(character_id)
    if not character:
        return
    now = time.time()
    for cw in (character.db.cyberware or []):
        if float(getattr(cw.db, "emp_glitch_until", 0.0) or 0.0) > now:
            continue
        if getattr(cw.db, "malfunctioning", False):
            continue
        if getattr(cw, "buff_class", None):
            character.buffs.add(cw.buff_class)

