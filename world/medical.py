"""
Medical / trauma system: internal organs, fractures, bleeding.
User-friendly but realistic; integrates with body-part combat.
Single source of body parts: combat imports BODY_PARTS from here.
Injury slots: each wound occupies HP until it heals; minor self-heal, severe need treatment + time.
"""
import random
import time

# -----------------------------------------------------------------------------
# Canonical body part list (severity order: index 0 = glancing, -1 = devastating)
# -----------------------------------------------------------------------------
BODY_PARTS = [
    "left foot", "right foot", "left hand", "right hand",
    "left thigh", "right thigh", "left arm", "right arm",
    "left shoulder", "right shoulder", "torso", "back", "abdomen",
    "groin", "neck", "face", "head",
]

# Display order: head to feet (for describe_bodypart usage and body listing)
BODY_PARTS_HEAD_TO_FEET = [
    "head", "face", "neck",
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
}

# -----------------------------------------------------------------------------
# Anatomy: body part -> organs that can be damaged when hit
# -----------------------------------------------------------------------------
BODY_PART_ORGANS = {
    "head": ["brain"],
    "face": ["eyes"],
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

# Body part -> bones that can fracture
BODY_PART_BONES = {
    "head": ["skull"],
    "face": ["jaw", "nose"],
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


def _ensure_medical_db(character):
    """Ensure character has medical attributes."""
    if character.db.organ_damage is None:
        character.db.organ_damage = {}
    if character.db.fractures is None:
        character.db.fractures = []  # list of bone keys
    if character.db.bleeding_level is None:
        character.db.bleeding_level = 0
    if character.db.splinted_bones is None:
        character.db.splinted_bones = []  # bones that have been splinted (reduces combat penalty)
    if character.db.stabilized_organs is None:
        character.db.stabilized_organs = {}  # organ_key -> True if stabilized this session (no repeated stabilize)
    if character.db.body_part_injuries is None:
        character.db.body_part_injuries = {}  # body_part -> list of short colored descriptor strings (for look when naked)
    if character.db.bandaged_body_parts is None:
        character.db.bandaged_body_parts = []  # body parts that have been bandaged (for treated look text)


# Bone key -> body parts that contain that bone (for splinted descriptor on look)
BONE_TO_BODY_PARTS = {}
for _part, _bones in BODY_PART_BONES.items():
    for _b in _bones:
        BONE_TO_BODY_PARTS.setdefault(_b, []).append(_part)

# Severity (1-4) -> wording per injury type. Used for "They have a {wording} on their {body_part}."
INJURY_SEVERITY_WORDING = {
    "cut": {1: "a minor cut", 2: "a weeping cut", 3: "a deep cut", 4: "a grievous laceration"},
    "bruise": {1: "a bruise", 2: "heavy bruising", 3: "a severe contusion", 4: "massive contusion"},
    "gunshot": {1: "a graze", 2: "a gunshot wound", 3: "a severe gunshot wound", 4: "a critical gunshot wound"},
    "trauma": {1: "an abrasion", 2: "bruising", 3: "heavy impact trauma", 4: "severe trauma"},
}
# Plural form for "two X" / "multiple X" when same part has several of same type+severity
INJURY_SEVERITY_PLURAL = {
    "cut": {1: "minor cuts", 2: "weeping cuts", 3: "deep cuts", 4: "grievous lacerations"},
    "bruise": {1: "bruises", 2: "areas of heavy bruising", 3: "severe contusions", 4: "massive contusions"},
    "gunshot": {1: "grazes", 2: "gunshot wounds", 3: "severe gunshot wounds", 4: "critical gunshot wounds"},
    "trauma": {1: "abrasions", 2: "areas of bruising", 3: "heavy impact trauma", 4: "areas of severe trauma"},
}
INJURY_TYPE_BY_WEAPON = {"knife": "cut", "long_blade": "cut", "blunt": "bruise", "sidearm": "gunshot", "longarm": "gunshot", "automatic": "gunshot"}


def _pronoun_sub_poss(character):
    """Return (Sub, poss) for third-person: He/his, She/her, They/their."""
    key = (getattr(character.db, "pronoun", None) or "neutral").lower()
    from world.emote import PRONOUN_MAP
    sub, poss, _ = PRONOUN_MAP.get(key, PRONOUN_MAP["neutral"])
    return (sub or "They").capitalize(), (poss or "their")


def _pronoun_verb_has_have(character):
    """Return 'have' for they/neutral, 'has' for he/she (subject-verb agreement)."""
    key = (getattr(character.db, "pronoun", None) or "neutral").lower()
    from world.emote import PRONOUN_MAP
    sub, _, _ = PRONOUN_MAP.get(key, PRONOUN_MAP["neutral"])
    return "have" if (sub or "they").lower() == "they" else "has"


def add_body_part_injury(character, body_part, weapon_key, damage=0):
    """Add an injury record for this body part (type + severity). Display is aggregated in get_effective_body_descriptions."""
    _ensure_medical_db(character)
    severity = 1 if damage <= 6 else (2 if damage <= 15 else (3 if damage <= 28 else 4))
    injury_type = INJURY_TYPE_BY_WEAPON.get(weapon_key, "trauma")
    entry = {"type": injury_type, "severity": severity}
    part_list = character.db.body_part_injuries.setdefault(body_part, [])
    part_list.append(entry)
    character.db.body_part_injuries[body_part] = part_list


def format_body_part_injuries(character, body_part, part_entries):
    """
    Turn a list of injury entries (dicts with type/severity, or legacy strings) into one combined line.
    Multiple same type+severity become "two deep cuts" / "multiple deep cuts"; mixed become "X and Y on their part."
    """
    if not part_entries:
        return ""
    # Legacy: list of pre-formatted strings -> join as-is (no aggregation)
    if isinstance(part_entries[0], str):
        return " ".join(part_entries).strip()
    from collections import Counter
    sub, poss = _pronoun_sub_poss(character)
    verb = _pronoun_verb_has_have(character)
    groups = Counter((e.get("type", "trauma"), e.get("severity", 1)) for e in part_entries if isinstance(e, dict))
    wording_map = INJURY_SEVERITY_WORDING
    plural_map = INJURY_SEVERITY_PLURAL
    bits = []
    for (itype, sev), count in groups.items():
        w = wording_map.get(itype, wording_map["trauma"])
        p = plural_map.get(itype, plural_map["trauma"])
        singular = w.get(sev, w[1])
        plural_phrase = p.get(sev, p[1])
        if count == 1:
            bits.append(singular)
        elif count == 2:
            bits.append(f"two {plural_phrase}")
        else:
            bits.append(f"multiple {plural_phrase}")
    if not bits:
        return ""
    combined = " and ".join(bits)
    return f"|r{sub} {verb} {combined} on {poss} {body_part}.|n"


def get_untreated_injuries_by_part(character):
    """
    Return dict body_part -> list of {type, severity} for injuries that are not treated.
    Used for look: show wound line only for untreated injuries; treated parts show bandaged/splinted instead.
    """
    injuries = getattr(character.db, "injuries", None) or []
    by_part = {}
    for i in injuries:
        if i.get("treated"):
            continue
        part = (i.get("body_part") or "").strip()
        if not part:
            continue
        by_part.setdefault(part, []).append({
            "type": i.get("type", "trauma"),
            "severity": i.get("severity", 1),
        })
    return by_part


# Injury slot system: wounds occupy HP until healed. Regen runs periodically.
REGEN_INTERVAL_SECS = 600  # 10 min IRL between regen ticks per character


def add_injury(character, hp_occupied, body_part=None, weapon_key="fists"):
    """
    Record an injury that occupies HP. Does not change current_hp (caller subtracts).
    Severity 1 = minor, can self-heal. 2+ = need treatment then time.
    """
    if not character or hp_occupied <= 0:
        return
    _ensure_medical_db(character)
    severity = 1 if hp_occupied <= 6 else (2 if hp_occupied <= 15 else (3 if hp_occupied <= 28 else 4))
    injury_type = INJURY_TYPE_BY_WEAPON.get(weapon_key, "trauma")
    injury = {
        "hp_occupied": int(hp_occupied),
        "severity": severity,
        "body_part": body_part or "",
        "type": injury_type,
        "treated": False,
        "created_at": time.time(),
    }
    character.db.injuries = (character.db.injuries or []) + [injury]
    _schedule_regen_if_needed(character)


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
    injury = eligible[0]
    injury["hp_occupied"] -= 1
    character.db.current_hp = min(max_hp, current + 1)
    if injury["hp_occupied"] <= 0:
        healed_part = (injury.get("body_part") or "").strip()
        was_treated = injury.get("treated")
        character.db.injuries = [i for i in injuries if i["hp_occupied"] > 0]
        # If healed injury was treated, remove that part from bandaged_body_parts if no other treated injury there
        if was_treated and healed_part:
            bandaged = getattr(character.db, "bandaged_body_parts", None) or []
            if healed_part in bandaged:
                remaining_treated_on_part = [
                    i for i in character.db.injuries
                    if (i.get("body_part") or "").strip() == healed_part and i.get("treated")
                ]
                if not remaining_treated_on_part:
                    character.db.bandaged_body_parts = [p for p in bandaged if p != healed_part]
    else:
        character.db.injuries = injuries


def _cardiovascular_resistance(character):
    """Better endurance = slightly harder to cause severe bleeding. Uses stat level 0-300."""
    try:
        from world.levels import level_to_effective_grade, letter_to_level_range, MAX_STAT_LEVEL
        end = (character.db.stats or {}).get("endurance", 0)
        if isinstance(end, str):
            lo, hi = letter_to_level_range(end.upper(), MAX_STAT_LEVEL)
            end = (lo + hi) // 2
        val = level_to_effective_grade(end if isinstance(end, int) else 0, MAX_STAT_LEVEL)
        return 1.0 - (val - 5) * 0.02  # 0.84 to 1.16 roughly; clamp in use
    except Exception:
        return 1.0


# Weapon bias: blades -> bleed, blunt -> bones, guns -> organ. Multipliers applied to base chance.
WEAPON_BLEED_MULT = {"knife": 1.6, "long_blade": 1.5, "blunt": 0.5, "sidearm": 0.9, "longarm": 0.9, "automatic": 0.9}
WEAPON_FRACTURE_MULT = {"knife": 0.4, "long_blade": 0.5, "blunt": 1.8, "sidearm": 0.3, "longarm": 0.35, "automatic": 0.3}
WEAPON_ORGAN_MULT = {"knife": 0.9, "long_blade": 0.9, "blunt": 0.7, "sidearm": 1.3, "longarm": 1.2, "automatic": 1.2}


def apply_trauma(character, body_part, damage, is_critical=False, weapon_key="fists"):
    """
    Apply trauma from a hit: possible organ damage, fracture, and bleeding.
    weapon_key biases outcome: blades favour bleed, blunt favour fracture, guns favour organ.
    Base rates kept low so trauma feels serious. Re-hit same area increases severity.
    Returns dict: { "organ": ..., "fracture": ..., "bleeding": ... } for combat messaging.
    """
    _ensure_medical_db(character)
    # Wound display is derived from injuries[] in get_untreated_injuries_by_part; add_injury is called by at_damage
    organs = BODY_PART_ORGANS.get(body_part, [])
    bones = BODY_PART_BONES.get(body_part, [])
    result = {"organ": None, "fracture": None, "bleeding": None}
    bleed_mult = WEAPON_BLEED_MULT.get(weapon_key, 1.0)
    fracture_mult = WEAPON_FRACTURE_MULT.get(weapon_key, 1.0)
    organ_mult = WEAPON_ORGAN_MULT.get(weapon_key, 1.0)

    existing_organ_here = any(character.db.organ_damage.get(o, 0) > 0 for o in organs)
    existing_fracture_here = any(b in (character.db.fractures or []) for b in bones)
    rehit_bonus = 1.35 if (existing_organ_here or existing_fracture_here) else 1.0

    # --- Organ: lower base, guns/organ-focused weapons higher chance ---
    base_organ = 0.06 + (damage / 120) + (0.12 if is_critical else 0)
    organ_chance = min(0.7, base_organ * rehit_bonus * organ_mult)
    if organs and random.random() < organ_chance:
        organ = random.choice(organs)
        severity_roll = random.random()
        current_sev = character.db.organ_damage.get(organ, 0)
        if existing_organ_here and organ in character.db.organ_damage:
            step = 2 if (is_critical or damage >= 18) else 1
            new_severity = min(3, current_sev + step)
        elif is_critical and damage >= 20:
            new_severity = min(3, current_sev + 2)
        elif damage >= 15:
            new_severity = min(3, current_sev + (2 if severity_roll > 0.5 else 1))
        else:
            new_severity = min(3, current_sev + 1)
        character.db.organ_damage[organ] = new_severity
        result["organ"] = (organ, new_severity)

    # --- Fracture: blunt favoured; blades/guns less likely ---
    base_fracture = 0.04 + damage / 80 + (0.12 if is_critical else 0)
    fracture_chance = min(0.55, base_fracture * rehit_bonus * fracture_mult)
    if bones and damage >= 10 and random.random() < fracture_chance:
        bone = random.choice(bones)
        if bone not in character.db.fractures:
            character.db.fractures.append(bone)
        result["fracture"] = bone

    # --- Bleeding: blades favoured; location + cardiovascular ---
    bleed_data = BODY_PART_BLEED.get(body_part, (0.1, "capillary"))
    base_chance, vessel_type = bleed_data[0], bleed_data[1]
    cardio = max(0.7, min(1.2, _cardiovascular_resistance(character)))
    chance = base_chance * (damage / 30.0) * (1.3 if is_critical else 1.0) * rehit_bonus * bleed_mult / cardio
    chance = min(0.75, chance)
    if random.random() >= chance:
        return result
    current = character.db.bleeding_level or 0
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
    new_level = min(4, current + delta)
    character.db.bleeding_level = new_level
    atk_msg, def_msg = _bleeding_gory_message(body_part, vessel_type, new_level, BLEEDING_LEVELS[new_level], vague=True)
    result["bleeding"] = (new_level, atk_msg, def_msg)
    return result


def get_brutal_hit_flavor(weapon_key, body_part, trauma_result, defender_name, attacker_name, is_critical):
    """
    Short trauma lines with hit location. One phrase per type.
    Returns (attacker_msg, defender_msg).
    """
    if not trauma_result:
        return "", ""
    loc = body_part or "them"
    lines_atk = []
    lines_def = []
    organ = trauma_result.get("organ")
    fracture = trauma_result.get("fracture")
    bleeding = trauma_result.get("bleeding")
    is_blade = weapon_key in ("knife", "long_blade")
    is_blunt = weapon_key == "blunt"
    is_gun = weapon_key in ("sidearm", "longarm", "automatic")

    if organ:
        if is_blade:
            lines_atk.append(f"|rYou opened something vital at their {loc}.|n")
            lines_def.append(f"|rSomething inside your {loc} tore.|n")
        elif is_gun:
            lines_atk.append(f"|rThe round did real damage inside their {loc}.|n")
            lines_def.append(f"|rSomething inside your {loc} is wrong.|n")
        else:
            lines_atk.append(f"|rThat blow to their {loc} went deep. Something gave.|n")
            lines_def.append(f"|rSomething broke in your {loc}. Not bone.|n")
    if fracture:
        if is_blade:
            lines_atk.append(f"|ySteel on bone at their {loc}. You felt it.|n")
            lines_def.append(f"|yThe blade hit bone in your {loc}.|n")
        elif is_blunt:
            lines_atk.append(f"|yYou hear the crack in their {loc}. Something broke.|n")
            lines_def.append(f"|ySomething broke in your {loc}. You heard it.|n")
        else:
            lines_atk.append(f"|yBone at their {loc}. You felt it give.|n")
            lines_def.append(f"|ySomething broke in your {loc}.|n")
    if bleeding:
        triple = bleeding
        if len(triple) >= 3 and triple[1]:
            lines_atk.append(triple[1])
        if len(triple) >= 3 and triple[2]:
            lines_def.append(triple[2])
    return " ".join(lines_atk), " ".join(lines_def)


def get_bleeding_drain_per_tick(character):
    """HP lost per combat tick from bleeding (0 if none)."""
    level = character.db.bleeding_level or 0
    if level == 0:
        return 0
    # 1 = 1, 2 = 2, 3 = 4, 4 = 8 (escalating)
    return (1, 2, 4, 8)[min(level - 1, 3)]


# Bones that impair attack (arm, hand, shoulder) vs defense (leg, foot, spine)
_FRACTURE_ATTACK_BONES = frozenset({"humerus", "metacarpals", "clavicle", "scapula", "jaw", "nose"})
_FRACTURE_DEFENSE_BONES = frozenset({"femur", "ankle", "metatarsals", "cervical_spine", "spine", "pelvis", "ribs"})


def get_trauma_combat_modifiers(character):
    """
    Return (attack_penalty, defense_penalty) from existing trauma.
    Fractured arms/hands reduce attack; fractured legs/feet/spine reduce dodge.
    Splinted bones apply only half penalty. Bleeding adds a penalty to both.
    """
    _ensure_medical_db(character)
    atk_penalty = 0
    def_penalty = 0
    fractures = character.db.fractures or []
    splinted = character.db.splinted_bones or []
    for bone in fractures:
        mult = 0.5 if bone in splinted else 1.0
        if bone in _FRACTURE_ATTACK_BONES:
            atk_penalty -= int(8 * mult)
        if bone in _FRACTURE_DEFENSE_BONES:
            def_penalty -= int(10 * mult)
    level = character.db.bleeding_level or 0
    if level >= 1:
        atk_penalty -= (1, 3, 6, 12)[min(level - 1, 3)]
        def_penalty -= (1, 3, 6, 12)[min(level - 1, 3)]
    return (atk_penalty, def_penalty)


def get_medical_summary(character):
    """
    User-friendly one-paragraph summary of trauma: organs, bones, bleeding, splints.
    """
    _ensure_medical_db(character)
    lines = []

    # Organ damage
    organ_damage = character.db.organ_damage or {}
    if organ_damage:
        parts = []
        for organ_key, severity in organ_damage.items():
            if severity <= 0:
                continue
            names = ORGAN_INFO.get(organ_key, (organ_key,)*4)
            desc = names[min(severity, 3)]
            stab = " [stabilized]" if (character.db.stabilized_organs or {}).get(organ_key) else ""
            parts.append(f"{names[0]} ({desc}){stab}")
        if parts:
            lines.append("|rOrgan trauma:|n " + "; ".join(parts))

    # Fractures (mark splinted)
    fractures = character.db.fractures or []
    splinted = character.db.splinted_bones or []
    if fractures:
        bone_names = [BONE_INFO.get(b, b) + (" (splinted)" if b in splinted else "") for b in fractures]
        lines.append("|yFractures:|n " + ", ".join(bone_names))

    # Bleeding
    level = character.db.bleeding_level or 0
    if level > 0:
        lines.append("|rBleeding:|n " + BLEEDING_LEVELS[min(level, 4)])

    if not lines:
        return "|gNo significant trauma. Vitals within acceptable parameters.|n"
    return "\n".join(lines)


def get_diagnose_trauma_for_skill(character, medicine_level):
    """
    Physical-exam style trauma summary for diagnose command, tiered by medicine skill.
    Returns extra lines to show (or empty string). Not as detailed as scanner; scanner
    remains the only way to get exact vitals and precise organ/bone labels.
    """
    _ensure_medical_db(character)
    if medicine_level is None or medicine_level < DIAGNOSE_TIER_1:
        return ""

    bleeding_level = character.db.bleeding_level or 0
    fractures = character.db.fractures or []
    splinted = character.db.splinted_bones or []
    organ_damage = character.db.organ_damage or {}
    if not bleeding_level and not fractures and not organ_damage:
        return ""

    lines = []
    # Tier 1 (10+): bleeding present/absent, possible fracture
    if medicine_level >= DIAGNOSE_TIER_1:
        if bleeding_level > 0:
            lines.append("|yPhysical exam:|n They are bleeding.")
        if fractures:
            lines.append("|yPhysical exam:|n You notice possible fracture or serious limb injury.")
        if medicine_level < DIAGNOSE_TIER_2:
            return "\n".join(lines) if lines else ""

    # Tier 2 (25+): bleeding level, fracture by region
    if medicine_level >= DIAGNOSE_TIER_2:
        lines = []
        if bleeding_level > 0:
            lines.append("|yBleeding:|n " + BLEEDING_LEVELS[min(bleeding_level, 4)])
        if fractures:
            regions = set()
            for b in fractures:
                r = BONE_TO_REGION.get(b, b)
                if r:
                    regions.add(r)
            if regions:
                lines.append("|yPossible fracture / serious injury:|n " + ", ".join(sorted(regions)))
        if medicine_level < DIAGNOSE_TIER_3:
            return "\n".join(lines) if lines else ""

    # Tier 3 (50+): fractures by bone name, bleeding, internal trauma by region
    if medicine_level >= DIAGNOSE_TIER_3:
        lines = []
        if bleeding_level > 0:
            lines.append("|yBleeding:|n " + BLEEDING_LEVELS[min(bleeding_level, 4)])
        if fractures:
            bone_names = [BONE_INFO.get(b, b) + (" (splinted)" if b in splinted else "") for b in fractures]
            lines.append("|yFractures:|n " + ", ".join(bone_names))
        if organ_damage:
            regions = set()
            for ok in organ_damage:
                if organ_damage.get(ok, 0) <= 0:
                    continue
                r = ORGAN_TO_REGION.get(ok, "internal")
                regions.add(r)
            if regions:
                lines.append("|ySigns of internal trauma:|n " + ", ".join(sorted(regions)) + " — scanner needed for detail.")
        if medicine_level < DIAGNOSE_TIER_4:
            return "\n".join(lines) if lines else ""

    # Tier 4 (75+): full physical-exam summary (still no vitals; scanner for exact organs)
    lines = []
    if bleeding_level > 0:
        lines.append("|yBleeding:|n " + BLEEDING_LEVELS[min(bleeding_level, 4)])
    if fractures:
        bone_names = [BONE_INFO.get(b, b) + (" (splinted)" if b in splinted else "") for b in fractures]
        lines.append("|yFractures:|n " + ", ".join(bone_names))
    if organ_damage:
        regions = set()
        for ok in organ_damage:
            if organ_damage.get(ok, 0) <= 0:
                continue
            r = ORGAN_TO_REGION.get(ok, "internal")
            regions.add(r)
        if regions:
            lines.append("|yInternal trauma (by region):|n " + ", ".join(sorted(regions)) + ". Use a bioscanner for precise assessment.")
    return "\n".join(lines) if lines else ""


def get_medical_detail(character):
    """Full medical readout for diagnose command: organs, fractures, bleeding."""
    _ensure_medical_db(character)
    out = []

    out.append("|wTRAUMA ASSESSMENT|n")
    # Organs
    organ_damage = character.db.organ_damage or {}
    if organ_damage:
        out.append("|wInternal / organ trauma:|n")
        for organ_key, severity in sorted(organ_damage.items()):
            if severity <= 0:
                continue
            names = ORGAN_INFO.get(organ_key, (organ_key,)*4)
            out.append(f"  {names[0].title()}: {names[min(severity, 3)]}")
    else:
        out.append("|wInternal / organ trauma:|n  None noted.")

    # Fractures
    fractures = character.db.fractures or []
    if fractures:
        out.append("|wFractures:|n " + ", ".join(BONE_INFO.get(b, b) for b in fractures))
    else:
        out.append("|wFractures:|n  None.")

    # Bleeding
    level = character.db.bleeding_level or 0
    out.append("|wBleeding:|n " + BLEEDING_LEVELS[min(level, 4)])

    return "\n".join(out)


def reset_medical(character):
    """Clear all trauma and treatment state (e.g. after full heal or respawn).
    Clears injuries (so wound/treated body descs disappear), bandaged/splinted state,
    organ damage, fractures, bleeding, and combat flag.
    """
    character.db.injuries = []
    character.db.bandaged_body_parts = []
    character.db.body_part_injuries = {}
    character.db.organ_damage = {}
    character.db.fractures = []
    character.db.bleeding_level = 0
    character.db.splinted_bones = []
    character.db.stabilized_organs = {}
    character.db.combat_ended = False
