"""
Medical / trauma system: internal organs, fractures, bleeding.
User-friendly but realistic; integrates with body-part combat.
Single source of body parts: combat imports BODY_PARTS from here.
Injury slots: each wound occupies HP until it heals; minor self-heal, severe need treatment + time.
"""
import random
import time
import uuid
from world.medical.core import (
    _ensure_medical_db,
    _injury_type_for_weapon,
    _cardiovascular_resistance,
    TREATMENT_QUALITY_LABELS,
    ORGAN_MECHANICAL_EFFECTS,
)

# -----------------------------------------------------------------------------
# Canonical body part list (severity order: index 0 = glancing, -1 = devastating)
# -----------------------------------------------------------------------------
BODY_PARTS = [
    "left foot", "right foot", "left hand", "right hand",
    "left thigh", "right thigh", "left arm", "right arm",
    "left shoulder", "right shoulder", "torso", "back", "abdomen",
    "groin", "neck", "left ear", "right ear", "face", "left eye", "right eye", "head",
]

# Display order: head to feet (for describe_bodypart usage and body listing)
BODY_PARTS_HEAD_TO_FEET = [
    "head", "face", "left eye", "right eye", "left ear", "right ear", "neck",
    "left shoulder", "right shoulder", "torso", "back", "abdomen",
    "left arm", "right arm", "left hand", "right hand",
    "groin", "left thigh", "right thigh", "left foot", "right foot",
]

# Short aliases for describe_bodypart (alias -> full name)
BODY_PART_ALIASES = {
    "lfoot": "left foot", "rfoot": "right foot",
    "lhand": "left hand", "rhand": "right hand",
    "lthigh": "left thigh", "rthigh": "right thigh",
    "larm": "left arm", "rarm": "right arm",
    "lshoulder": "left shoulder", "rshoulder": "right shoulder",
    "leye": "left eye", "reye": "right eye",
    "lear": "left ear", "rear": "right ear",
    "earl": "left ear", "earr": "right ear",
    "l ear": "left ear", "r ear": "right ear",
    "leftear": "left ear", "rightear": "right ear",
}

# -----------------------------------------------------------------------------
# Anatomy: body part -> organs that can be damaged when hit
# -----------------------------------------------------------------------------
BODY_PART_ORGANS = {
    "head": ["brain"],
    "face": ["eyes"],
    "left eye": ["eyes"],
    "right eye": ["eyes"],
    "left ear": [],
    "right ear": [],
    "neck": ["throat", "carotid"],
    "left shoulder": ["collarbone_area"],
    "right shoulder": ["collarbone_area"],
    "left arm": [],
    "right arm": [],
    "left hand": [],
    "right hand": [],
    "torso": ["heart", "lungs"],
    "back": ["lungs", "spine_cord"],
    "abdomen": ["liver", "spleen", "stomach", "kidneys"],
    "groin": ["pelvic_organs"],
    "left thigh": [],
    "right thigh": [],
    "left foot": [],
    "right foot": [],
}

# Organ display names and severity descriptions (0 = fine, 1 = bruised, 2 = damaged, 3 = critical/ruptured)
ORGAN_INFO = {
    "brain": ("brain", "concussion", "traumatic injury", "severe trauma"),
    "eyes": ("eyes", "bruised", "damaged", "ruptured"),
    "throat": ("throat", "bruised", "damaged", "crushed"),
    "carotid": ("carotid", "nicked", "lacerated", "severed"),
    "collarbone_area": ("collarbone area", "bruised", "damaged", "crushed"),
    "heart": ("heart", "bruised", "damaged", "punctured"),
    "lungs": ("lungs", "bruised", "punctured", "collapsed"),
    "spine_cord": ("spinal area", "bruised", "compressed", "severely damaged"),
    "liver": ("liver", "bruised", "lacerated", "ruptured"),
    "spleen": ("spleen", "bruised", "lacerated", "ruptured"),
    "stomach": ("stomach", "bruised", "perforated", "ruptured"),
    "kidneys": ("kidneys", "bruised", "lacerated", "ruptured"),
    "pelvic_organs": ("pelvic region", "bruised", "damaged", "severely damaged"),
}


def is_unconscious(character):
    """
    True if character is in the global knocked-out/unconscious state.

    This is a simple flag on character.db and is used by grapple, sever,
    and any future mechanics (drugs, injuries, etc.) that need to check
    or set unconsciousness.
    """
    db = getattr(character, "db", None)
    return bool(getattr(db, "unconscious", False) or getattr(db, "medical_unconscious", False))

# Body part -> bones that can fracture
BODY_PART_BONES = {
    "head": ["skull"],
    "face": ["jaw", "nose"],
    "left eye": [],
    "right eye": [],
    "left ear": [],
    "right ear": [],
    "neck": ["cervical_spine"],
    "left shoulder": ["clavicle", "scapula"],
    "right shoulder": ["clavicle", "scapula"],
    "left arm": ["humerus"],
    "right arm": ["humerus"],
    "left hand": ["metacarpals"],
    "right hand": ["metacarpals"],
    "torso": ["ribs"],
    "back": ["ribs", "spine"],
    "abdomen": ["ribs"],
    "groin": ["pelvis"],
    "left thigh": ["femur"],
    "right thigh": ["femur"],
    "left foot": ["ankle", "metatarsals"],
    "right foot": ["ankle", "metatarsals"],
}

# Bone display names
BONE_INFO = {
    "skull": "skull",
    "jaw": "jaw",
    "nose": "nose",
    "cervical_spine": "neck (c-spine)",
    "clavicle": "clavicle",
    "scapula": "scapula",
    "humerus": "upper arm",
    "metacarpals": "hand",
    "ribs": "ribs",
    "spine": "spine",
    "pelvis": "pelvis",
    "femur": "thigh",
    "ankle": "ankle",
    "metatarsals": "foot",
}

# Bleeding: 0 = none, 1 = minor, 2 = moderate, 3 = severe, 4 = critical
BLEEDING_LEVELS = [
    "None",
    "Minor (capillary ooze)",
    "Moderate (steady haemorrhage)",
    "Severe (significant blood loss)",
    "Critical (arterial / life-threatening)",
]

# Diagnose command: medicine skill tiers (physical exam only; scanner gives full detail)
DIAGNOSE_TIER_1 = 10   # Basic: bleeding present/absent, "possible fracture"
DIAGNOSE_TIER_2 = 25   # Bleeding level, fracture by region (arm, leg, chest, etc.)
DIAGNOSE_TIER_3 = 50   # Fractures by bone name, bleeding, "internal trauma (region)"
DIAGNOSE_TIER_4 = 75   # Full physical exam summary (no vitals; scanner still needed for exact organs/vitals)
BIOSCANNER_MIN_MEDICINE = 25  # Minimum medicine skill to operate the bioscanner

# Bone key -> broad region for tier-2 diagnose (physical exam can't pinpoint exact bone)
BONE_TO_REGION = {
    "humerus": "arm", "metacarpals": "hand", "clavicle": "shoulder", "scapula": "shoulder",
    "femur": "leg", "ankle": "ankle", "metatarsals": "foot",
    "ribs": "chest", "spine": "back", "cervical_spine": "neck",
    "skull": "head", "jaw": "face", "nose": "face",
    "pelvis": "pelvis",
}

# Organ key -> region for tier-3/4 (no exact organ names without scanner)
ORGAN_TO_REGION = {
    "brain": "head", "eyes": "face", "throat": "neck", "carotid": "neck",
    "collarbone_area": "shoulder", "heart": "chest", "lungs": "chest",
    "spine_cord": "back", "liver": "abdomen", "spleen": "abdomen",
    "stomach": "abdomen", "kidneys": "abdomen", "pelvic_organs": "pelvis",
}

# -----------------------------------------------------------------------------
# Cardiovascular / bleeding by body part: (base_chance 0-1, vessel_type for gory flavour)
# vessel_type: "arterial" (spray/pulse), "venous" (steady pour), "capillary" (ooze), "none"
# Neck/groin/face = high chance + arterial/venous; torso/abdomen = moderate; limbs = low; hands/feet = very low
BODY_PART_BLEED = {
    "head": (0.35, "venous"),      # scalp vessels
    "face": (0.55, "arterial"),    # facial artery, nose
    "left eye": (0.60, "arterial"),
    "right eye": (0.60, "arterial"),
    "left ear": (0.44, "arterial"),
    "right ear": (0.44, "arterial"),
    "neck": (0.72, "arterial"),    # carotid/jugular - life-threatening
    "left shoulder": (0.28, "venous"),
    "right shoulder": (0.28, "venous"),
    "left arm": (0.18, "venous"),
    "right arm": (0.18, "venous"),
    "left hand": (0.08, "capillary"),
    "right hand": (0.08, "capillary"),
    "torso": (0.38, "venous"),     # intercostals, muscle
    "back": (0.32, "venous"),
    "abdomen": (0.48, "venous"),   # organs, rich vasculature
    "groin": (0.65, "arterial"),  # femoral region
    "left thigh": (0.22, "venous"),
    "right thigh": (0.22, "venous"),
    "left foot": (0.06, "capillary"),
    "right foot": (0.06, "capillary"),
}


# Short combat bleed messages. vague=True for combat (no body part).
def _bleeding_gory_message(body_part, vessel_type, new_level, severity_word, vague=False):
    """Return (msg_for_attacker, msg_for_defender). Short and readable."""
    if new_level <= 0:
        return "", ""
    v = vessel_type or "capillary"
    if v == "arterial":
        atk = "|rBlood sprays. They won't last.|n" if vague else f"|rBlood sprays from their {body_part}. They won't last.|n"
        def_ = "|rYou're bleeding bad. Arterial.|n"
    elif v == "venous":
        atk = "|rThey're bleeding. Steady. Dark.|n" if vague else f"|rDark blood pours from their {body_part}.|n"
        def_ = "|rYou're bleeding. It won't stop.|n"
    else:
        atk = "|rThey're cut. It's bleeding.|n" if vague else f"|rBlood runs from their {body_part}.|n"
        def_ = "|rYou're bleeding.|n"
    return (atk, def_)


# _ensure_medical_db moved to world.medical.core.


# Bone key -> body parts that contain that bone (for splinted descriptor on look)
BONE_TO_BODY_PARTS = {}
for _part, _bones in BODY_PART_BONES.items():
    for _b in _bones:
        BONE_TO_BODY_PARTS.setdefault(_b, []).append(_part)

from world.medical.descriptions import (
    INJURY_SEVERITY_WORDING,
    INJURY_SEVERITY_PLURAL,
    _pronoun_sub_poss,
    _pronoun_verb_has_have,
    format_body_part_injuries,
    get_untreated_injuries_by_part,
)
# Injury type resolved via world.combat.damage_types.get_damage_type -> DAMAGE_TYPE_TO_INJURY_TYPE
# _injury_type_for_weapon moved to world.medical.core.


# Description functions moved to world.medical.descriptions; imported above.


# Injury slot system: wounds occupy HP until healed. Regen runs periodically.
REGEN_INTERVAL_SECS = 600  # 10 min IRL between regen ticks per character
REGEN_PARALLEL_EFFICIENCY = 0.7  # Multi-wound regen: first wound full, others at reduced efficiency.

from world.medical.infection import (
    INFECTION_CATALOG,
    INFECTION_STAGE_LABELS,
    INFECTION_STAGE_PENALTIES,
    INFECTION_RISK_THRESHOLD,
    INFECTION_STAGE_ADVANCE_SECS,
    get_infection_penalties,
    get_infection_readout,
    apply_infection_tick,
)

from world.medical.injuries import (
    BLEED_DAMPENING_FACTOR,
    BLEED_RATE_TO_LEVEL,
    _set_injury_treatment_quality,
    ensure_injury_schema,
    _normalize_injuries,
    rebuild_derived_trauma_views,
    get_active_bleed_wounds,
    compute_effective_bleed_level,
)


# Infection logic moved to world.medical.infection; imported above.


def add_injury(character, hp_occupied, body_part=None, weapon_key="fists", weapon_obj=None):
    """
    Record an injury that occupies HP. Does not change current_hp (caller subtracts).
    Severity 1 = minor, can self-heal. 2+ = need treatment then time.
    """
    if not character or hp_occupied <= 0:
        return
    _ensure_medical_db(character)
    severity = 1 if hp_occupied <= 6 else (2 if hp_occupied <= 15 else (3 if hp_occupied <= 28 else 4))
    injury_type = _injury_type_for_weapon(weapon_key, weapon_obj)
    injury = ensure_injury_schema({
        "injury_id": str(uuid.uuid4()),
        "hp_occupied": int(hp_occupied),
        "severity": severity,
        "body_part": body_part or "",
        "type": injury_type,
        "treated": False,
        "created_at": time.time(),
        "infection_risk": min(0.4, 0.03 * severity),
    })
    character.db.injuries = (character.db.injuries or []) + [injury]
    rebuild_derived_trauma_views(character)
    compute_effective_bleed_level(character)
    _schedule_regen_if_needed(character)
    return injury.get("injury_id")


def _schedule_regen_if_needed(character):
    """Schedule one regen tick for this character if they have injuries."""
    try:
        from evennia.utils import delay
        delay(REGEN_INTERVAL_SECS, _injury_regen_tick, character.id)
    except Exception:
        pass


def _injury_regen_tick(character_id):
    """Heal one point from one eligible injury; reschedule if more remain."""
    from evennia.utils.search import search_object
    from evennia.utils import delay
    try:
        result = search_object("#%s" % character_id)
        if not result:
            return
        character = result[0]
    except Exception:
        return
    if not getattr(character, "db", None) or not character.db.injuries:
        return
    _process_one_regen(character)
    if character.db.injuries:
        delay(REGEN_INTERVAL_SECS, _injury_regen_tick, character.id)


def _process_one_regen(character):
    """
    Heal 1 HP from one eligible injury. Severity 1 always eligible; 2+ only if treated.
    """
    _ensure_medical_db(character)
    injuries = character.db.injuries or []
    now = time.time()
    for injury in injuries:
        if not injury.get("cyberware_dbref"):
            continue
        started = float(injury.get("recovery_started", now) or now)
        elapsed = now - started
        if elapsed < 24 * 3600:
            injury["recovery_phase"] = "acute"
        elif elapsed < 72 * 3600:
            injury["recovery_phase"] = "adapting"
        else:
            injury["recovery_phase"] = "integrated"
            injury["rejection_risk"] = max(0.0, float(injury.get("rejection_risk", 0.0) or 0.0) * 0.1)
    max_hp = getattr(character, "max_hp", 100) or 100
    current = character.db.current_hp
    if current is None:
        character.db.current_hp = max_hp
        current = max_hp
    if current >= max_hp:
        return
    eligible = [i for i in injuries if i["hp_occupied"] > 0 and (i["severity"] == 1 or i.get("treated"))]
    if not eligible:
        return
    healed_total = 0
    for idx, injury in enumerate(eligible):
        if character.db.current_hp >= max_hp:
            break
        quality = int(injury.get("treatment_quality", 0) or 0)
        quality_mult = 1.0 + (0.2 * quality)
        heal_amt = (1.0 if idx == 0 else REGEN_PARALLEL_EFFICIENCY) * quality_mult
        old_hp = injury["hp_occupied"]
        injury["hp_occupied"] = max(0, old_hp - heal_amt)
        healed = max(0.0, old_hp - injury["hp_occupied"])
        healed_total += healed
        # Super-rare complications on treated wounds.
        if injury.get("treated") and random.random() < 0.003:
            complication_roll = random.random()
            if complication_roll < 0.45:
                injury["bleed_treated"] = False
                injury["bleed_rate"] = max(0.8, float(injury.get("bleed_rate", 0.0) or 0.0) + 0.7)
                character.msg("|yA treated wound reopens under strain. Seek care again.|n")
            elif complication_roll < 0.8:
                injury["infection_risk"] = min(1.0, float(injury.get("infection_risk", 0.0) or 0.0) + 0.12)
                character.msg("|yA postoperative complication forms under the dressing. You need follow-up care.|n")
            else:
                injury["hp_occupied"] = min(float(injury.get("hp_occupied", 0.0) or 0.0) + 1.0, 999.0)
                character.msg("|yA hematoma forms and recovery slows. You should be re-evaluated.|n")
    if healed_total > 0:
        character.db.current_hp = min(max_hp, current + int(round(healed_total)))

    # Remove fully healed injuries and clean treatment cosmetics.
    remaining = []
    healed_parts = []
    for injury in injuries:
        if injury.get("hp_occupied", 0) > 0:
            remaining.append(injury)
        else:
            healed_parts.append(((injury.get("body_part") or "").strip(), injury.get("treated")))
    character.db.injuries = remaining
    if healed_parts:
        bandaged = getattr(character.db, "bandaged_body_parts", None) or []
        for healed_part, was_treated in healed_parts:
            if not (was_treated and healed_part and healed_part in bandaged):
                continue
            remaining_treated_on_part = [
                i for i in remaining
                if (i.get("body_part") or "").strip() == healed_part and i.get("treated")
            ]
            if not remaining_treated_on_part:
                bandaged = [p for p in bandaged if p != healed_part]
        character.db.bandaged_body_parts = bandaged
    rebuild_derived_trauma_views(character)
    compute_effective_bleed_level(character)


def apply_trauma(character, body_part, damage, is_critical=False, weapon_key="fists", weapon_obj=None, injury_id=None):
    """
    Apply trauma from a hit: possible organ damage, fracture, and bleeding.
    Multipliers are damage-type × body-region (e.g. slashing on neck = high bleed; impact on limb = high fracture).
    Base rates kept low so trauma feels serious. Re-hit same area increases severity.

    Chrome (fully replaced) and missing body parts skip biological trauma entirely.
    Augmented parts still have biological tissue and take normal trauma.

    Returns dict: { "organ": ..., "fracture": ..., "bleeding": ... } for combat messaging.
    """
    from world.body import get_part_state, get_effective_organs, get_effective_bones, get_cyberware_for_part
    from world.combat.damage_types import get_damage_type, get_trauma_multipliers

    _ensure_medical_db(character)
    injuries = _normalize_injuries(character)
    rebuild_derived_trauma_views(character)
    compute_effective_bleed_level(character)
    result = {"organ": None, "fracture": None, "bleeding": None}

    def _apply_cyberware_damage(cw, amount):
        """Apply deterministic durability loss and handle malfunction transitions."""
        amount = int(amount or 0)
        if amount <= 0 or bool(getattr(cw.db, "malfunctioning", False)):
            return
        chrome_hp = getattr(cw.db, "chrome_hp", None)
        if chrome_hp is None:
            chrome_hp = int(getattr(cw, "chrome_max_hp", 100) or 100)
            cw.db.chrome_hp = chrome_hp
            cw.db.chrome_max_hp = chrome_hp
        cw.db.chrome_hp = max(0, int(chrome_hp) - amount)
        if cw.db.chrome_hp <= 0:
            cw.db.malfunctioning = True
            if getattr(cw, "buff_class", None):
                character.buffs.remove(cw.buff_class.key)

    # Chrome/missing parts have no biological tissue — no biological trauma.
    part_state = get_part_state(character, body_part or "torso")
    if part_state == "missing":
        return result
    if part_state == "chrome":
        chrome_damage_mult = {"arc": 1.5, "void": 1.8, "impact": 0.8, "slashing": 0.5, "penetrating": 0.7, "burn": 0.6, "freeze": 0.4}
        damage_type = get_damage_type(weapon_key, weapon_obj)
        mult = chrome_damage_mult.get(damage_type, 0.6)
        effective_damage = int(damage * mult)
        if effective_damage >= 15:
            cw_list = get_cyberware_for_part(character, body_part or "torso")
            if cw_list:
                cw = cw_list[0]
                chrome_hp = getattr(cw.db, "chrome_hp", None)
                if chrome_hp is None:
                    chrome_hp = int(getattr(cw, "chrome_max_hp", 100) or 100)
                    cw.db.chrome_hp = chrome_hp
                    cw.db.chrome_max_hp = chrome_hp
                _apply_cyberware_damage(cw, effective_damage)
                result["chrome_damage"] = (cw, effective_damage, cw.db.chrome_hp)
                # Memory core instability under heavy damage can trigger flashback episodes.
                from typeclasses.cyberware_catalog import MemoryCore
                if isinstance(cw, MemoryCore):
                    mx = int(getattr(cw.db, "chrome_max_hp", getattr(cw, "chrome_max_hp", 25)) or 25)
                    if cw.db.chrome_hp < (mx * 0.5):
                        if random.random() < 0.35:
                            character.db.memory_core_flashback_until = time.time() + 120
                            memories = list(getattr(character.db, "memories", None) or [])
                            if memories and random.random() < 0.25:
                                lose_idx = random.randint(0, len(memories) - 1)
                                lost = memories.pop(lose_idx)
                                character.db.memories = memories
                                character.msg(f"|mA violent memory loop wipes a stored memory: {lost}|n")
                            else:
                                character.msg("|mA vivid memory loop hijacks your thoughts.|n")
                if cw.db.chrome_hp <= 0:
                    result["chrome_destroyed"] = cw
                    # Cardiopulmonary failure cascades into immediate stamina collapse.
                    from typeclasses.cyberware_catalog import CardioPulmonaryBooster
                    if isinstance(cw, CardioPulmonaryBooster):
                        character.db.current_stamina = 0
        if damage_type == "arc" and effective_damage >= 12:
            neural_chrome = [
                cw for cw in (character.db.cyberware or [])
                if getattr(cw, "damage_model", "none") == "arc_only"
                and not bool(getattr(cw.db, "malfunctioning", False))
            ]
            for cw in neural_chrome:
                _apply_cyberware_damage(cw, int(effective_damage * 0.25))
        return result

    damage_type = get_damage_type(weapon_key, weapon_obj)
    if damage_type == "arc" and (character.db.cyberware or []):
        try:
            from world.medical.cybersurgery import apply_emp_effect
            apply_emp_effect(character, damage)
        except Exception:
            pass
        if damage >= 12:
            neural_chrome = [
                cw for cw in (character.db.cyberware or [])
                if getattr(cw, "damage_model", "none") == "arc_only"
                and not bool(getattr(cw.db, "malfunctioning", False))
            ]
            for cw in neural_chrome:
                _apply_cyberware_damage(cw, int(damage * 0.25))
        # Arc-specific neural side effects for certain implants.
        for cw in (character.db.cyberware or []):
            if getattr(cw.db, "malfunctioning", False):
                continue
            from typeclasses.cyberware_catalog import WiredReflexes, SynapticAccelerator
            if isinstance(cw, WiredReflexes) and random.random() < 0.10:
                character.db.combat_skip_next_turn = True
            if isinstance(cw, SynapticAccelerator):
                until = time.time() + 60
                if float(getattr(character.db, "synaptic_arc_debuff_until", 0.0) or 0.0) < until:
                    character.db.synaptic_arc_debuff_until = until
    bleed_mult, fracture_mult, organ_mult = get_trauma_multipliers(damage_type, body_part or "torso")
    organs = get_effective_organs(character, body_part or "torso")
    bones = get_effective_bones(character, body_part or "torso")

    wound = None
    if injury_id:
        for injury in injuries:
            if injury.get("injury_id") == injury_id:
                wound = injury
                break
    if wound is None:
        same_part = [i for i in injuries if (i.get("body_part") or "") == (body_part or "")]
        if same_part:
            wound = sorted(same_part, key=lambda i: float(i.get("created_at", 0) or 0), reverse=True)[0]
    if wound is None:
        # Do not bind trauma to unrelated body parts; create a fresh wound event.
        inferred_hp = max(1, int(round(max(1, damage) * 0.35)))
        new_id = add_injury(character, inferred_hp, body_part=body_part or "", weapon_key=weapon_key, weapon_obj=weapon_obj)
        injuries = _normalize_injuries(character)
        for injury in injuries:
            if injury.get("injury_id") == new_id:
                wound = injury
                break
    # New trauma to an existing wound/part degrades prior treatment quality.
    if wound and (wound.get("body_part") or "") == (body_part or ""):
        tq = int(wound.get("treatment_quality", 0) or 0)
        if tq > 0:
            wound["treatment_quality"] = max(0, tq - 1)
            if wound["treatment_quality"] == 0:
                wound["treated"] = False
            wound["bleed_treated"] = False

    existing_organ_here = any((wound.get("organ_damage") or {}).get(o, 0) > 0 for o in organs) if wound else False
    existing_fracture_here = bool(wound and wound.get("fracture") in bones)
    rehit_bonus = 1.35 if (existing_organ_here or existing_fracture_here) else 1.0

    # --- Organ: lower base, guns/organ-focused weapons higher chance ---
    base_organ = 0.06 + (damage / 120) + (0.12 if is_critical else 0)
    organ_chance = min(0.7, base_organ * rehit_bonus * organ_mult)
    if organs and random.random() < organ_chance:
        organ = random.choice(organs)
        severity_roll = random.random()
        current_sev = (wound.get("organ_damage") or {}).get(organ, 0) if wound else 0
        if existing_organ_here and wound and organ in (wound.get("organ_damage") or {}):
            step = 2 if (is_critical or damage >= 18) else 1
            new_severity = min(3, current_sev + step)
        elif is_critical and damage >= 20:
            new_severity = min(3, current_sev + 2)
        elif damage >= 15:
            new_severity = min(3, current_sev + (2 if severity_roll > 0.5 else 1))
        else:
            new_severity = min(3, current_sev + 1)
        if wound:
            od = dict(wound.get("organ_damage") or {})
            od[organ] = new_severity
            wound["organ_damage"] = od
            if new_severity >= 3 and current_sev >= 3:
                wound["organ_destroyed"] = True
            stabilized = dict(getattr(character.db, "stabilized_organs", None) or {})
            if organ in stabilized:
                del stabilized[organ]
                character.db.stabilized_organs = stabilized
        else:
            character.db.organ_damage[organ] = new_severity
        result["organ"] = (organ, new_severity)
        collateral_chrome = []
        for cw in get_cyberware_for_part(character, body_part or "torso"):
            if getattr(cw, "damage_model", "none") != "collateral":
                continue
            mods = getattr(cw, "body_mods", None) or {}
            mode_and_text = mods.get(body_part or "torso")
            if not mode_and_text or mode_and_text[0] != "append":
                continue
            collateral_chrome.append(cw)
        for cw in collateral_chrome:
            _apply_cyberware_damage(cw, int(damage * 0.3))

    # --- Fracture: blunt favoured; blades/guns less likely ---
    base_fracture = 0.04 + damage / 80 + (0.12 if is_critical else 0)
    fracture_chance = min(0.55, base_fracture * rehit_bonus * fracture_mult)
    # Bone lacing lowers fracture likelihood.
    from typeclasses.cyberware_catalog import BoneLacing
    has_bone_lacing = any(isinstance(cw, BoneLacing) and not bool(getattr(cw.db, "malfunctioning", False)) for cw in (character.db.cyberware or []))
    if has_bone_lacing:
        fracture_chance *= 0.6
    if bones and damage >= 10 and random.random() < fracture_chance:
        bone = random.choice(bones)
        if wound:
            wound["fracture"] = bone
        elif bone not in character.db.fractures:
            character.db.fractures.append(bone)
        result["fracture"] = bone

    # --- Bleeding: blades favoured; location + cardiovascular ---
    bleed_data = BODY_PART_BLEED.get(body_part, (0.1, "capillary"))
    base_chance, vessel_type = bleed_data[0], bleed_data[1]
    cardio = max(0.6, min(1.2, _cardiovascular_resistance(character, organ_damage=character.db.organ_damage)))
    chance = base_chance * (damage / 30.0) * (1.3 if is_critical else 1.0) * rehit_bonus * bleed_mult / cardio
    chance = min(0.75, chance)
    if random.random() >= chance:
        return result
    current, _ = compute_effective_bleed_level(character)
    if damage >= 20 or (is_critical and damage >= 12):
        delta = 2
    elif damage >= 10:
        delta = 1
    else:
        delta = 1 if random.random() < 0.35 else 0
    if existing_organ_here or existing_fracture_here:
        delta = min(2, delta + 1)
    if delta <= 0 and current == 0:
        return result
    if wound:
        rate_map = {"capillary": 1.0, "venous": 2.0, "arterial": 3.0}
        base_rate = rate_map.get(vessel_type, 1.0)
        added = float(delta) * (1.2 if is_critical else 1.0)
        from typeclasses.cyberware_catalog import HemostaticRegulator
        has_hemo_reg = any(isinstance(cw, HemostaticRegulator) and not bool(getattr(cw.db, "malfunctioning", False)) for cw in (character.db.cyberware or []))
        if has_hemo_reg:
            base_rate = max(0.0, base_rate - 1.0)
        wound["bleed_rate"] = max(float(wound.get("bleed_rate", 0.0) or 0.0), base_rate + added)
        wound["vessel_type"] = vessel_type
        wound["bleed_treated"] = False
        wound["infection_risk"] = min(0.8, float(wound.get("infection_risk", 0.0) or 0.0) + (0.01 * max(1, delta)))
    new_level, _ = compute_effective_bleed_level(character)
    atk_msg, def_msg = _bleeding_gory_message(body_part, vessel_type, new_level, BLEEDING_LEVELS[new_level], vague=True)
    result["bleeding"] = (new_level, atk_msg, def_msg)
    rebuild_derived_trauma_views(character)
    return result


def get_brutal_hit_flavor(weapon_key, body_part, trauma_result, defender_name, attacker_name, is_critical, weapon_obj=None):
    """
    Short trauma lines with hit location. One phrase per type.
    Uses damage type (slashing/impact/penetrating/burn/freeze/arc/void) for flavor. Returns (attacker_msg, defender_msg).
    """
    from world.combat.damage_types import get_damage_type
    try:
        # Reuse combat message profile resolution so we can specialize trauma per weapon template too.
        from world.combat.combat_messages import get_message_profile_id
    except Exception:
        get_message_profile_id = None
    try:
        from world.medical.trauma_messages import TRAUMA_MESSAGE_PROFILES
    except Exception:
        TRAUMA_MESSAGE_PROFILES = {}
    if not trauma_result:
        return "", ""
    damage_type = get_damage_type(weapon_key, weapon_obj)
    loc = body_part or "them"
    lines_atk = []
    lines_def = []
    organ = trauma_result.get("organ")
    fracture = trauma_result.get("fracture")
    bleeding = trauma_result.get("bleeding")

    profile_id = None
    if callable(get_message_profile_id):
        try:
            profile_id = get_message_profile_id(str(weapon_key or "fists"), weapon_obj)
        except Exception:
            profile_id = None

    def _profile_line(kind: str):
        if not profile_id:
            return None
        prof = TRAUMA_MESSAGE_PROFILES.get(profile_id)
        if not prof:
            # Fall back to base weapon_key profile if template-specific isn't present.
            prof = TRAUMA_MESSAGE_PROFILES.get(str(weapon_key or "fists"))
        if not prof:
            return None
        table = prof.get(kind) or {}
        tpl = table.get(damage_type)
        if not tpl:
            tpl = table.get("default")
        if not tpl:
            return None
        atk_tpl, def_tpl = tpl
        return atk_tpl.format(loc=loc), def_tpl.format(loc=loc)

    if organ:
        prof_lines = _profile_line("organ")
        if prof_lines:
            lines_atk.append(prof_lines[0])
            lines_def.append(prof_lines[1])
        elif damage_type == "slashing":
            lines_atk.append(f"|rYou opened something vital at their {loc}.|n")
            lines_def.append(f"|rSomething inside your {loc} tore.|n")
        elif damage_type == "penetrating":
            lines_atk.append(f"|rThe round did real damage inside their {loc}.|n")
            lines_def.append(f"|rSomething inside your {loc} is wrong.|n")
        elif damage_type == "burn":
            lines_atk.append(f"|rThe heat sears deep into their {loc}.|n")
            lines_def.append(f"|rSomething inside your {loc} is burning.|n")
        elif damage_type == "freeze":
            lines_atk.append(f"|rThe cold bites into the core of their {loc}.|n")
            lines_def.append(f"|rA killing cold settles deep in your {loc}.|n")
        elif damage_type == "arc":
            lines_atk.append(f"|rThe current rips through nerves and organs in their {loc}.|n")
            lines_def.append(f"|rSomething vital in your {loc} spasms and goes numb.|n")
        elif damage_type == "void":
            lines_atk.append(f"|rSomething inside their {loc} just stops being there.|n")
            lines_def.append(f"|rSomething in your {loc} comes apart in ways it shouldn't.|n")
        else:
            lines_atk.append(f"|rThat blow to their {loc} went deep. Something gave.|n")
            lines_def.append(f"|rSomething broke in your {loc}. Not bone.|n")
    if fracture:
        prof_lines = _profile_line("fracture")
        if prof_lines:
            lines_atk.append(prof_lines[0])
            lines_def.append(prof_lines[1])
        elif damage_type == "slashing":
            lines_atk.append(f"|ySteel on bone at their {loc}. You felt it.|n")
            lines_def.append(f"|yThe blade hit bone in your {loc}.|n")
        elif damage_type == "impact":
            lines_atk.append(f"|yYou hear the crack in their {loc}. Something broke.|n")
            lines_def.append(f"|ySomething broke in your {loc}. You heard it.|n")
        elif damage_type == "burn":
            lines_atk.append(f"|yHeat warps bone at their {loc}.|n")
            lines_def.append(f"|yBone in your {loc} feels soft and wrong.|n")
        elif damage_type == "freeze":
            lines_atk.append(f"|yFrozen bone at their {loc} splinters under the force.|n")
            lines_def.append(f"|ySomething brittle in your {loc} gives way.|n")
        elif damage_type == "arc":
            lines_atk.append(f"|yThe jolt snaps something in their {loc}.|n")
            lines_def.append(f"|yYour {loc} locks and something inside it cracks.|n")
        elif damage_type == "void":
            lines_atk.append(f"|yThe structure of bone at their {loc} just unknits.|n")
            lines_def.append(f"|yYour {loc} feels hollow, like something is missing.|n")
        else:
            lines_atk.append(f"|yBone at their {loc}. You felt it give.|n")
            lines_def.append(f"|ySomething broke in your {loc}.|n")
    if bleeding:
        triple = bleeding
        if len(triple) >= 3 and triple[1]:
            lines_atk.append(triple[1])
        if len(triple) >= 3 and triple[2]:
            lines_def.append(triple[2])
    if trauma_result.get("chrome_damage"):
        cw, dmg, remaining = trauma_result["chrome_damage"]
        if damage_type == "arc":
            lines_atk.append(f"|cSparks explode from their {loc}. The chrome screams.|n")
            lines_def.append(f"|cElectricity arcs through your chrome {loc}. Systems flicker.|n")
        elif damage_type == "void":
            lines_atk.append(f"|cThe chrome at their {loc} warps and buckles. Something fundamental shifts.|n")
            lines_def.append(f"|cYour chrome {loc} feels wrong. Like it's forgetting what shape it should be.|n")
        else:
            lines_atk.append(f"|cMetal dents at their {loc}. The chrome took the hit.|n")
            lines_def.append(f"|cImpact rattles through your chrome {loc}. Damage, but it holds.|n")
    if trauma_result.get("chrome_destroyed"):
        cw = trauma_result["chrome_destroyed"]
        lines_atk.append(f"|R{cw.key} at their {loc} shorts out. The chrome is dead.|n")
        lines_def.append(f"|R{cw.key} in your {loc} goes dark. Malfunction. The chrome is dead.|n")
    return " ".join(lines_atk), " ".join(lines_def)


from world.medical.bleeding import (
    BLEEDING_TICK_INTERVAL,
    BLEEDING_DRAIN_PER_TICK,
    HEMOSTATIC_REOPEN_CHANCE,
    TOURNIQUET_TICKS_BEFORE_REOPEN,
    get_bleeding_drain_per_tick,
    apply_bleeding_tick,
    bleeding_tick_all,
)


from world.medical.summaries import (
    get_trauma_combat_modifiers,
    get_medical_summary,
    get_diagnose_trauma_for_skill,
    get_medical_detail,
)


from world.medical.vitals import (
    HT_CONDITION_FULL_HP_TIERS,
    HT_CONDITION_INJURED_TIERS,
    HT_CONDITION_DEAD,
    HT_RESTED_TIERS,
    get_ht_summary,
)


def reset_medical(character):
    """Clear all trauma and treatment state (e.g. after full heal or respawn).
    Clears injuries (so wound/treated body descs disappear), bandaged/splinted state,
    organ damage, fractures, bleeding, and combat flag.
    """
    character.db.injuries = []
    character.db.bandaged_body_parts = []
    character.db.organ_damage = {}
    character.db.fractures = []
    character.db.bleeding_level = 0
    character.db.splinted_bones = []
    character.db.stabilized_organs = {}
    character.db.tourniquet_applied = False
    character.db.tourniquet_ticks = 0
    if hasattr(character.db, "bleeding_hemostatic_stabilized"):
        character.db.bleeding_hemostatic_stabilized = False
    # Clear infection state on all known wounds.
    for i in (getattr(character.db, "injuries", None) or []):
        i["infection_type"] = None
        i["infection_stage"] = 0
        i["infection_since"] = 0.0
        i["infection_risk"] = 0.0
    character.db.combat_ended = False
