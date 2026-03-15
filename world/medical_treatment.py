"""
Medical treatment procedures: bleeding control, splinting, organ stabilization.
IRL-inspired but streamlined. Uses medicine skill; tools improve success or unlock procedures.
"""
import random
from world.medical import (
    _ensure_medical_db,
    BLEEDING_LEVELS,
    BONE_INFO,
    ORGAN_INFO,
    get_bleeding_drain_per_tick,
)

# Realistic treatment labels per bone (splint limb vs bind chest vs spinal immobilization, etc.)
BONE_TREATMENT_LABEL = {
    "skull": "Stabilize head injury",
    "jaw": "Immobilize jaw",
    "nose": "Stabilize nose",
    "cervical_spine": "Cervical spine immobilization",
    "clavicle": "Splint collarbone",
    "scapula": "Stabilize shoulder",
    "humerus": "Splint upper arm",
    "metacarpals": "Splint hand",
    "ribs": "Bind chest",
    "spine": "Spinal immobilization",
    "pelvis": "Pelvic stabilization",
    "femur": "Splint thigh",
    "ankle": "Splint ankle",
    "metatarsals": "Splint foot",
}

# Realistic treatment labels per organ (secure airway, not "stabilize throat", etc.)
ORGAN_TREATMENT_LABEL = {
    "brain": "Reduce intracranial pressure",
    "eyes": "Protect eye",
    "throat": "Secure airway",
    "carotid": "Control carotid bleeding",
    "collarbone_area": "Stabilize collarbone area",
    "heart": "Stabilize cardiac function",
    "lungs": "Stabilize breathing",
    "spine_cord": "Spinal support",
    "liver": "Stabilize liver",
    "spleen": "Stabilize spleen",
    "stomach": "Stabilize stomach",
    "kidneys": "Stabilize kidneys",
    "pelvic_organs": "Stabilize pelvic region",
}

# Tool types (db.medical_tool_type on MedicalTool objects)
TOOL_SCANNER = "scanner"
TOOL_BANDAGES = "bandages"
TOOL_MEDKIT = "medkit"
TOOL_SUTURE_KIT = "suture_kit"
TOOL_SPLINT = "splint"
TOOL_HEMOSTATIC = "hemostatic"
TOOL_SURGICAL_KIT = "surgical_kit"

# What each tool can do
TOOL_CAN_STOP_BLEEDING = (TOOL_BANDAGES, TOOL_MEDKIT, TOOL_SUTURE_KIT, TOOL_HEMOSTATIC, TOOL_SURGICAL_KIT)
TOOL_CAN_SPLINT = (TOOL_SPLINT, TOOL_MEDKIT, TOOL_SURGICAL_KIT)
TOOL_CAN_STABILIZE_ORGAN = (TOOL_MEDKIT, TOOL_SURGICAL_KIT)
TOOL_IS_SCANNER = (TOOL_SCANNER,)

# Aliases for "apply splint to X arm" / "apply medkit to X throat" (body part -> bone_key or organ_key)
BONE_ALIASES = {
    "arm": "humerus", "arms": "humerus", "upper arm": "humerus",
    "leg": "femur", "thigh": "femur", "thighs": "femur",
    "hand": "metacarpals", "hands": "metacarpals",
    "foot": "metatarsals", "feet": "metatarsals", "ankle": "ankle",
    "ribs": "ribs", "chest": "ribs",
    "head": "skull", "skull": "skull",
    "spine": "spine", "back": "spine",
    "neck": "cervical_spine", "c-spine": "cervical_spine", "cervical": "cervical_spine",
    "pelvis": "pelvis", "hip": "pelvis",
    "jaw": "jaw", "nose": "nose",
    "clavicle": "clavicle", "collarbone": "clavicle",
    "scapula": "scapula", "shoulder": "scapula",
}
ORGAN_ALIASES = {
    "throat": "throat", "airway": "throat",
    "brain": "brain", "head": "brain",
    "eyes": "eyes", "eye": "eyes",
    "carotid": "carotid", "neck": "carotid",
    "heart": "heart", "cardiac": "heart",
    "lungs": "lungs", "lung": "lungs", "breathing": "lungs",
    "spine_cord": "spine_cord", "spinal": "spine_cord",
    "liver": "liver", "spleen": "spleen", "stomach": "stomach", "kidneys": "kidneys", "kidney": "kidneys",
    "pelvic_organs": "pelvic_organs", "collarbone_area": "collarbone_area",
}

# Difficulty modifiers: higher = harder. Base difficulty 0; +10 per tier.
def _bleeding_difficulty(level):
    """Difficulty to reduce bleeding; severe/critical harder."""
    return max(0, (level - 1) * 12)

def _organ_difficulty(severity):
    """Difficulty to stabilize organ; critical (3) much harder."""
    return (0, 5, 15, 30)[min(severity, 3)]

def _splint_difficulty(bone_key):
    """Spine/skull/pelvis harder to splint in field."""
    hard_bones = frozenset({"spine", "cervical_spine", "skull", "pelvis"})
    return 20 if bone_key in hard_bones else 0


# --- Visceral treatment messages: by tool, severity, success/fail ---
# Bleeding: fail (skill roll failed)
_BLEED_FAIL = {
    TOOL_BANDAGES: [
        "You pack and press but the wound keeps filling. Gauze soaks through. The bleed is not controlled; they need more help or a different approach.",
        "The bandage soaks through before you can secure it. Red everywhere. You're not stopping it with gauze alone.",
        "You press. The blood finds a way. Your hands are red. They're still losing. You need better tools or a calmer moment.",
    ],
    TOOL_MEDKIT: [
        "You work from the kit — pressure, packing. The wound keeps filling. You're not getting ahead of it.",
        "Even with the medkit you can't get a seal. Blood wells. They need more than field care.",
        "You pack and clamp. The flow doesn't stop. Something in there is still open. They need a proper setting.",
    ],
    TOOL_SUTURE_KIT: [
        "You try to close the worst of it. The needle slips. The tissue is too torn or the angle wrong. The bleed continues.",
        "You can't get a clean closure. Blood obscures the field. The suture won't hold. They're still losing.",
        "The wound won't hold a stitch. Too deep, too ragged. You back off. The bleed is not controlled.",
    ],
    TOOL_HEMOSTATIC: [
        "You apply the agent. It should be doing more. The wound keeps pumping. Maybe too much flow — you're not winning.",
        "The hemostatic packs in but the blood pushes through. You need direct pressure and time. They don't have much time.",
        "You pack the wound. The agent isn't sealing it. Something bigger is open. They need a surgeon.",
    ],
    TOOL_SURGICAL_KIT: [
        "You go in with proper tools. Still — you can't isolate the source. The field keeps filling. They need an OR.",
        "Even with the surgical kit you're fighting the bleed. You can't get control. They're still losing.",
        "You work as best you can. The damage is beyond what you can close here. The bleed is not controlled.",
    ],
}
# Bleeding: success by outcome (marginal = slow, full = good, critical = stopped)
_BLEED_SUCCESS_MARGINAL = {
    TOOL_BANDAGES: [
        "You get partial control: gauze, direct pressure. The flow slows. Not stopped; contained. They're still losing, but slower.",
        "You pack the worst of it. The bandage holds for now. They're still oozing. You've bought a little time.",
        "Pressure and wrap. The bleed slows. Your hands are red but the worst is held. For now.",
    ],
    TOOL_MEDKIT: [
        "You get the wound packed and dressed from the kit. The flow drops. They're still losing volume but at a survivable rate.",
        "From the medkit you pack and secure. The bleed slows. Not stopped — but they might make it to better care.",
        "You work quickly. Pressure, then dressings. The flow eases. They're still leaking. You've slowed it.",
    ],
    TOOL_SUTURE_KIT: [
        "You close what you can. The suture holds in a few places. The rest weeps. You've reduced the flow, not stopped it.",
        "Needle and thread. You get a partial closure. The wound still oozes. They're losing slower. Good enough for now.",
        "You stitch the worst of it. Not pretty. The bleed slows. They need more later — but they have a later.",
    ],
    TOOL_HEMOSTATIC: [
        "You pack the wound with the agent. It starts to gel. The flow slows. Not fully sealed — but you're winning.",
        "The hemostatic goes in. The bleed backs off. They're still losing a little. You've got most of it.",
        "You pack and hold. The agent does its job. The pump slows. They're stable enough to move.",
    ],
    TOOL_SURGICAL_KIT: [
        "You isolate and pack with the kit. The flow drops. They're still losing but at a rate you can live with.",
        "Proper tools, quick work. You get control. Not perfect — but the bleed is no longer the main problem.",
        "You close and pack. The surgical kit makes the difference. The wound weeps. The crisis eases.",
    ],
}
_BLEED_SUCCESS_FULL = {
    TOOL_BANDAGES: [
        "You get the wound packed and dressed. The flow drops. They're still losing volume but at a survivable rate.",
        "Gauze and pressure. You secure it. The bleed slows to a trickle. They'll make it if they get more care.",
        "You work the bandage in and wrap tight. The flow drops. Red on your hands. They're not out of the woods — but the woods are smaller.",
    ],
    TOOL_MEDKIT: [
        "From the medkit you pack and dress. The flow drops. They're still losing but at a survivable rate. You've done what the field allows.",
        "You get the wound under control. The medkit had what you needed. The bleed is down. They need rest and fluids.",
        "Pressure, packing, dressings. The flow eases. They're stable. The medkit earned its keep.",
    ],
    TOOL_SUTURE_KIT: [
        "You suture the source. The closure holds. The flow drops. They're still losing a little — but you've stopped the main leak.",
        "Needle and thread. You get a real closure. The bleed backs off. They'll need follow-up. They'll have follow-up.",
        "You close the wound. The stitch holds. The pump stops. They're going to be okay. For now.",
    ],
    TOOL_HEMOSTATIC: [
        "The hemostatic packs in and sets. The flow stops. You hold pressure. The wound seals. They're stable.",
        "You pack it. The agent does the rest. The bleed stops. You've bought them time. Maybe enough.",
        "Hemostatic in, pressure on. The wound gels. The flow drops to nothing. They're not losing anymore.",
    ],
    TOOL_SURGICAL_KIT: [
        "You isolate the source and close it. The surgical kit lets you do it right. The flow stops. They're stable.",
        "Proper technique, proper tools. You get the bleed under control. The wound is closed. They'll live.",
        "You work through the kit. The bleed is controlled. They're not out of danger — but they're out of the worst of it.",
    ],
}
_BLEED_SUCCESS_CRITICAL = {
    TOOL_BANDAGES: [
        "You isolate the source: pack and press. The pump stops. Blood no longer leaves the vessel. Bleeding controlled.",
        "You find the spot and hold. The bandage soaks once, then holds. The flow stops. They're not losing anymore.",
        "Pressure and gauze. You get a seal. The bleed stops. Your hands are red. They're not.",
    ],
    TOOL_MEDKIT: [
        "You isolate the source: clamp, pack, or dress. The pump stops. The medkit had what you needed. Bleeding controlled.",
        "From the kit you get control. The flow stops. They're stable. You've done the job.",
        "You work fast. The wound is packed and dressed. The bleed is over. They're going to make it.",
    ],
    TOOL_SUTURE_KIT: [
        "You isolate the source and suture it. The closure holds. The pump stops. Bleeding controlled.",
        "Needle and thread. You close the vessel. The bleed stops. Clean work. They're stable.",
        "You find the leak and close it. The suture holds. No more flow. They're in your debt.",
    ],
    TOOL_HEMOSTATIC: [
        "You pack the source. The hemostatic seals it. The pump stops. Blood no longer leaves the vessel. Bleeding controlled.",
        "The agent goes in. The wound seals. The flow stops. You've shut it down. They're stable.",
        "Hemostatic to the source. It sets. The bleed is over. They're not losing anymore.",
    ],
    TOOL_SURGICAL_KIT: [
        "You isolate the source: clamp, pack, or suture. The pump stops. Blood no longer leaves the vessel. Bleeding controlled.",
        "The surgical kit lets you do it right. You get control. The bleed stops. They're stable. Definitive care can wait.",
        "You work with precision. The source is closed. The flow stops. Bleeding controlled. They'll live.",
    ],
}

# Splint: fail
_SPLINT_FAIL = [
    "You cannot get a stable reduction. The bone won't hold. They need better gear or a proper setting. Do not force it.",
    "You try to align and hold. It won't stay. The fracture is beyond what you can do here. Don't make it worse.",
    "You can't get a clean reduction. The limb is wrong. They need an OR or someone with more than a field kit.",
]
# Splint success messages stay per-bone below; we can add tool flavor there if needed.

# Organ: fail
_ORGAN_FAIL = [
    "You cannot safely do more in the field. The damage is beyond what you can stabilize here. They need OR or a controlled environment.",
    "You work but you're not getting control. Internal trauma doesn't forgive mistakes. They need a surgeon.",
    "You back off. The risk is too high. Whatever's wrong in there needs better than a field kit.",
]


def _medicine_roll(operator, difficulty=0, modifier=0):
    """Roll medicine skill; return (success_level, roll_value). success_level: 0=fail, 1=marginal, 2=full, 3=critical."""
    if not hasattr(operator, "roll_check"):
        return 0, 0
    result, value = operator.roll_check(
        ["intelligence", "perception"],
        "medicine",
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


def attempt_stop_bleeding(operator, target, tool_type=None):
    """
    Attempt to reduce or stop bleeding. Requires bandages, medkit, suture kit, hemostatic, or surgical kit.
    Returns (success: bool, message: str). Success reduces bleeding_level by 1–2 (or to 0 on critical).
    """
    _ensure_medical_db(target)
    if tool_type not in TOOL_CAN_STOP_BLEEDING:
        return False, "You need haemostatic capability: bandages, medkit, suture kit, hemostatic agent, or surgical kit."

    level = target.db.bleeding_level or 0
    if level <= 0:
        return False, "No significant haemorrhage to control."

    # Tool modifier: hemostatic/surgical make it easier
    tool_mod = 0
    if tool_type == TOOL_HEMOSTATIC:
        tool_mod = 15
    elif tool_type in (TOOL_SUTURE_KIT, TOOL_SURGICAL_KIT):
        tool_mod = 10
    elif tool_type == TOOL_MEDKIT:
        tool_mod = 5

    difficulty = _bleeding_difficulty(level) - tool_mod
    success_level, _ = _medicine_roll(operator, max(0, difficulty), tool_mod)

    if success_level == 0:
        pool = _BLEED_FAIL.get(tool_type, _BLEED_FAIL[TOOL_BANDAGES])
        return False, random.choice(pool)

    # Marginal: reduce by 1. Full: reduce by 2. Critical: reduce to 0 (or by 2 if already low)
    if success_level >= 3:
        new_level = 0
        pool = _BLEED_SUCCESS_CRITICAL.get(tool_type, _BLEED_SUCCESS_CRITICAL[TOOL_BANDAGES])
        msg = random.choice(pool)
    elif success_level >= 2:
        new_level = max(0, level - 2)
        pool = _BLEED_SUCCESS_FULL.get(tool_type, _BLEED_SUCCESS_FULL[TOOL_BANDAGES])
        msg = random.choice(pool)
    else:
        new_level = max(0, level - 1)
        pool = _BLEED_SUCCESS_MARGINAL.get(tool_type, _BLEED_SUCCESS_MARGINAL[TOOL_BANDAGES])
        msg = random.choice(pool)

    target.db.bleeding_level = new_level
    # Mark one severe injury as treated and record bandaged body part for look text
    injuries = getattr(target.db, "injuries", None) or []
    bandaged = list(getattr(target.db, "bandaged_body_parts", None) or [])
    for i in injuries:
        if not i.get("treated") and i.get("severity", 1) >= 2:
            i["treated"] = True
            target.db.injuries = injuries
            part = (i.get("body_part") or "").strip()
            if part and part not in bandaged:
                bandaged.append(part)
                target.db.bandaged_body_parts = bandaged
            break
    return True, msg


def attempt_splint(operator, target, bone_key, tool_type=None):
    """
    Splint a fracture. Reduces combat penalty from that bone; does not remove the fracture.
    Requires splint, medkit, or surgical kit.
    """
    _ensure_medical_db(target)
    if tool_type not in TOOL_CAN_SPLINT:
        return False, "You need a splint, medkit, or surgical kit to reduce and immobilize the fracture."

    fractures = target.db.fractures or []
    if bone_key not in fractures:
        label = BONE_TREATMENT_LABEL.get(bone_key, f"fractured {BONE_INFO.get(bone_key, bone_key)}")
        return False, f"There is no fracture there to treat ({label})."

    splinted = target.db.splinted_bones or []
    if bone_key in splinted:
        return False, "That fracture is already reduced and immobilized. No further field intervention indicated."

    difficulty = _splint_difficulty(bone_key)
    tool_mod = 10 if tool_type == TOOL_SURGICAL_KIT else 0
    success_level, _ = _medicine_roll(operator, max(0, difficulty - tool_mod), tool_mod)

    label = BONE_TREATMENT_LABEL.get(bone_key, f"Splint {BONE_INFO.get(bone_key, bone_key)}")
    if success_level == 0:
        return False, random.choice(_SPLINT_FAIL)

    splinted = list(splinted) + [bone_key]
    target.db.splinted_bones = splinted
    # Mark one severe injury as treated so it can regen
    injuries = getattr(target.db, "injuries", None) or []
    for i in injuries:
        if not i.get("treated") and i.get("severity", 1) >= 2:
            i["treated"] = True
            target.db.injuries = injuries
            break
    # Injury-specific success messages
    if bone_key in ("ribs",):
        msg = "You bind the chest: rigid wrap, padding. Ribs are reduced; breathing will be shallow. Watch for pneumothorax."
    elif bone_key in ("spine", "cervical_spine"):
        msg = "You immobilize the spine: collar, board, neutral alignment. No further movement. C-spine is protected; they need definitive care."
    elif bone_key in ("pelvis",):
        msg = "You apply a pelvic binder. Unstable pelvis reduced. No further movement; internal bleeding risk remains."
    elif bone_key in ("skull",):
        msg = "You stabilize the head, neutral alignment. Skull cannot be splinted; you have limited further shear and ICP."
    elif bone_key in ("jaw", "nose"):
        msg = f"You immobilize the {BONE_INFO.get(bone_key, bone_key)}. Field fix only; they need maxillofacial or ENT."
    else:
        msg = f"You splint the {BONE_INFO.get(bone_key, bone_key)}. Fracture reduced; no further displacement. Pain and soft-tissue risk remain."
    return True, msg


def attempt_stabilize_organ(operator, target, organ_key, tool_type=None):
    """
    Stabilize damaged organ (reduce severity by 1, once per organ per session). Requires medkit or surgical kit.
    Critical (severity 3) is very hard; may still reduce to 2.
    """
    _ensure_medical_db(target)
    if tool_type not in TOOL_CAN_STABILIZE_ORGAN:
        return False, "You need a medkit or surgical kit for internal stabilization. Do not dig blind."

    organ_damage = target.db.organ_damage or {}
    severity = organ_damage.get(organ_key, 0)
    if severity <= 0:
        return False, "No significant trauma to that organ; nothing to stabilize."

    stabilized = target.db.stabilized_organs or {}
    if stabilized.get(organ_key):
        return False, "That organ is already stabilized. Further field intervention would risk iatrogenic injury."

    names = ORGAN_INFO.get(organ_key, (organ_key,) * 4)
    difficulty = _organ_difficulty(severity)
    tool_mod = 15 if tool_type == TOOL_SURGICAL_KIT else 0
    success_level, _ = _medicine_roll(operator, max(0, difficulty - tool_mod), tool_mod)

    if success_level == 0:
        return False, random.choice(_ORGAN_FAIL)

    target.db.organ_damage[organ_key] = severity - 1
    if severity - 1 <= 0:
        del target.db.organ_damage[organ_key]
    stabilized = dict(stabilized)
    stabilized[organ_key] = True
    target.db.stabilized_organs = stabilized
    # Mark one severe injury as treated so it can regen
    injuries = getattr(target.db, "injuries", None) or []
    for i in injuries:
        if not i.get("treated") and i.get("severity", 1) >= 2:
            i["treated"] = True
            target.db.injuries = injuries
            break
    # Injury-specific success messages
    if organ_key == "throat":
        msg = "You secure the airway: jaw-thrust, clearance, protection. They are moving air. Still at risk; watch for swelling."
    elif organ_key == "carotid":
        msg = "You control the carotid bleed: direct pressure, packing. Flow stemmed. Vessel is not repaired; they need vascular."
    elif organ_key == "brain":
        msg = "You reduce ICP as best you can: head elevated, neutral alignment, limit movement. They need neuro; you have bought time."
    elif organ_key == "eyes":
        msg = "You protect the eye: patch and shield. No further contamination or pressure. They need a specialist."
    elif organ_key == "heart":
        msg = "You stabilize cardiac function: positioning, monitoring, minimal intervention. Rhythm holds. They need a cath lab or OR."
    elif organ_key == "lungs":
        msg = "You stabilize breathing: chest seal, positioning, support. They are moving air. Tension ruled out for now; they need a tube or thoracostomy."
    elif organ_key == "spine_cord":
        msg = "You provide spinal immobilization and support. Cord damage is not reversible here; you have limited further insult."
    else:
        msg = f"You reduce threat to the {names[0]}: pressure, positioning, minimal intervention. Immediate crisis eased; they are not out of danger."
    return True, msg


def get_treatment_options(operator, target, tools_by_type):
    """
    Given operator, target, and dict tool_type -> list of objects (from inventory), return list of
    (action_id, display_name, tool_type, target_info) for available treatments.
    target_info: for bleeding None; for splint bone_key; for organ organ_key.
    """
    _ensure_medical_db(target)
    options = []

    # Stop bleeding
    if (target.db.bleeding_level or 0) > 0:
        for t in TOOL_CAN_STOP_BLEEDING:
            if tools_by_type.get(t):
                options.append(("bleeding", "Stop bleeding", t, None))
                break

    # Fracture treatments: use realistic label per bone (splint leg, bind chest, spinal immobilization, etc.)
    fractures = target.db.fractures or []
    splinted = target.db.splinted_bones or []
    for bone_key in fractures:
        if bone_key in splinted:
            continue
        for t in TOOL_CAN_SPLINT:
            if tools_by_type.get(t):
                display = BONE_TREATMENT_LABEL.get(bone_key, f"Splint {BONE_INFO.get(bone_key, bone_key)}")
                options.append(("splint", display, t, bone_key))
                break

    # Organ/internal treatments: use realistic label per organ (secure airway, not "stabilize throat", etc.)
    organ_damage = target.db.organ_damage or {}
    stabilized = target.db.stabilized_organs or {}
    for organ_key, sev in organ_damage.items():
        if sev <= 0 or stabilized.get(organ_key):
            continue
        for t in TOOL_CAN_STABILIZE_ORGAN:
            if tools_by_type.get(t):
                display = ORGAN_TREATMENT_LABEL.get(organ_key, ORGAN_INFO.get(organ_key, (organ_key,))[0])
                options.append(("organ", display, t, organ_key))
                break

    return options


def attempt_resuscitate(caller, target):
    """
    Attempt to bring a flatlined character back (defibrillator or similar).
    Target must be flatlined (hp <= 0, not permanently dead). Uses medicine skill.
    Returns (success: bool, message: str). On success sets target.current_hp and clears flatline.
    """
    try:
        from world.death import can_be_defibbed, is_permanently_dead, clear_flatline
        if is_permanently_dead(target):
            return False, "They are gone. Nothing can bring them back."
        if not can_be_defibbed(target):
            if getattr(target, "hp", 1) > 0:
                return False, "They are not in arrest. The defibrillator is for the dead."
            return False, "They are not in a state that can be revived."
    except ImportError:
        clear_flatline = None
        if getattr(target, "hp", 1) > 0:
            return False, "They are not in arrest. The defibrillator is for the dead."
    from world.medical import _ensure_medical_db
    _ensure_medical_db(target)
    hp = getattr(target, "hp", 0)
    if hp > 0:
        return False, "They are not in arrest. The defibrillator is for the dead."
    
    # Medicine roll: low difficulty, +5 modifier for equipment (defibrillator)
    success_level, _ = _medicine_roll(caller, difficulty=0, modifier=5)
    
    if success_level == 0:
        return False, "No rhythm. Flatline. You charge again, deliver another shock. Nothing. They are gone."
    
    mx = getattr(target, "max_hp", 1)
    target.db.current_hp = max(1, mx // 10)
    try:
        from world.death import clear_flatline
        clear_flatline(target)
    except Exception:
        pass

    return True, "A pulse. Then another. The monitor picks up a rhythm. They are back. For now."