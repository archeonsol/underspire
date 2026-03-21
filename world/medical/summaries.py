"""
Medical summaries/diagnostics and combat modifiers split from world.medical.__init__.
"""

from world.theme_colors import MEDICAL_COLORS as MC

_FRACTURE_ATTACK_BONES = frozenset({"humerus", "metacarpals", "clavicle", "scapula", "jaw", "nose"})
_FRACTURE_DEFENSE_BONES = frozenset({"femur", "ankle", "metatarsals", "cervical_spine", "spine", "pelvis", "ribs"})


def get_trauma_combat_modifiers(character):
    from world.medical.core import _ensure_medical_db, ORGAN_MECHANICAL_EFFECTS
    from world.medical.injuries import rebuild_derived_trauma_views, compute_effective_bleed_level
    from world.medical.infection import get_infection_penalties
    _ensure_medical_db(character)
    rebuild_derived_trauma_views(character)
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
    # Bilateral upper-limb breakage is worse than additive compensation.
    has_left_arm = any(b in fractures for b in ("humerus", "clavicle", "scapula", "metacarpals"))
    has_right_arm = has_left_arm  # current fracture model is side-agnostic; keep harsher bilateral fallback
    if has_left_arm and has_right_arm and len([b for b in fractures if b in ("humerus", "clavicle", "scapula", "metacarpals")]) >= 2:
        atk_penalty -= 6
    level, _ = compute_effective_bleed_level(character)
    if level >= 1:
        atk_penalty -= (1, 3, 6, 12)[min(level - 1, 3)]
        def_penalty -= (1, 3, 6, 12)[min(level - 1, 3)]
    for organ_key, severity in (character.db.organ_damage or {}).items():
        if severity <= 0:
            continue
        eff = ORGAN_MECHANICAL_EFFECTS.get(organ_key, {})
        atk_penalty += int(eff.get("atk", 0) * severity)
        def_penalty += int(eff.get("def", 0) * severity)
    inf = get_infection_penalties(character)
    atk_penalty += int(inf.get("atk", 0) or 0)
    def_penalty += int(inf.get("def", 0) or 0)
    return (atk_penalty, def_penalty)


def get_medical_summary(character):
    from world.medical.core import _ensure_medical_db, ORGAN_MECHANICAL_EFFECTS
    from world.medical.injuries import rebuild_derived_trauma_views, compute_effective_bleed_level, _normalize_injuries
    from world.medical.infection import INFECTION_CATALOG, INFECTION_STAGE_LABELS
    from world.medical import ORGAN_INFO, BONE_INFO, BLEEDING_LEVELS
    _ensure_medical_db(character)
    rebuild_derived_trauma_views(character)
    lines = []
    organ_damage = character.db.organ_damage or {}
    if organ_damage:
        parts = []
        for organ_key, severity in organ_damage.items():
            if severity <= 0:
                continue
            names = ORGAN_INFO.get(organ_key, (organ_key,) * 4)
            destroyed = any(
                organ_key in (i.get("organ_damage") or {}) and i.get("organ_destroyed")
                for i in (character.db.injuries or [])
            )
            desc = f"{MC['arrest']}DESTROYED - chrome replacement required|n" if destroyed else names[min(severity, 3)]
            stab = " [recent surgery]" if (character.db.stabilized_organs or {}).get(organ_key) else ""
            parts.append(f"{names[0]} ({desc}){stab}")
        if parts:
            lines.append(f"{MC['critical']}Organ trauma:|n " + "; ".join(parts))
    from world.medical.limb_trauma import LIMB_INFO, LIMB_SLOTS
    limb_damage = character.db.limb_damage or {}
    if limb_damage:
        lparts = []
        for limb_key in sorted(LIMB_SLOTS):
            sev = int(limb_damage.get(limb_key, 0) or 0)
            if sev <= 0:
                continue
            names = LIMB_INFO.get(limb_key, (limb_key,) * 4)
            destroyed = any(
                limb_key in (i.get("limb_damage") or {}) and i.get("fracture_destroyed")
                for i in (character.db.injuries or [])
            )
            desc = f"{MC['arrest']}DESTROYED — chrome limb required|n" if destroyed else names[min(sev, 3)]
            lparts.append(f"{names[0]} ({desc})")
        if lparts:
            lines.append(f"{MC['critical']}Limb trauma:|n " + "; ".join(lparts))
    fractures = character.db.fractures or []
    splinted = character.db.splinted_bones or []
    if fractures:
        lines.append(f"{MC['compensated']}Fractures:|n " + ", ".join(BONE_INFO.get(b, b) + (" (splinted)" if b in splinted else "") for b in fractures))
    level, _ = compute_effective_bleed_level(character)
    if level > 0:
        lines.append(f"{MC['critical']}Bleeding:|n " + BLEEDING_LEVELS[min(level, 4)])
    organ_penalty_parts = []
    for organ_key, severity in (character.db.organ_damage or {}).items():
        if severity <= 0:
            continue
        eff = ORGAN_MECHANICAL_EFFECTS.get(organ_key)
        if not eff:
            continue
        bits = []
        if eff.get("atk"):
            bits.append(f"ATK {eff['atk'] * severity}")
        if eff.get("def"):
            bits.append(f"DEF {eff['def'] * severity}")
        if eff.get("stamina_recovery"):
            bits.append(f"STAM REC {eff['stamina_recovery'] * severity}")
        if bits:
            organ_penalty_parts.append(f"{ORGAN_INFO.get(organ_key, (organ_key,))[0]} ({', '.join(bits)})")
    if organ_penalty_parts:
        lines.append("|xOrgan effects:|n " + "; ".join(organ_penalty_parts))
    infected = []
    for injury in (_normalize_injuries(character) or []):
        stage = int(injury.get("infection_stage", 0) or 0)
        if stage <= 0:
            continue
        itype = injury.get("infection_type") or "surface_cellulitis"
        ilabel = INFECTION_CATALOG.get(itype, {}).get("label", itype.replace("_", " "))
        part = (injury.get("body_part") or "wound").strip()
        infected.append(f"{part}: {ilabel} ({INFECTION_STAGE_LABELS.get(stage, 'progressing')})")
    if infected:
        lines.append(f"{MC['infection']}Infection:|n " + "; ".join(infected))
    return "\n".join(lines) if lines else f"{MC['stable']}No significant trauma. Vitals within acceptable parameters.|n"


def get_diagnose_trauma_for_skill(character, medicine_level):
    from world.medical.core import _ensure_medical_db
    from world.medical.injuries import compute_effective_bleed_level
    from world.medical import BONE_INFO, BONE_TO_REGION, ORGAN_TO_REGION, BLEEDING_LEVELS, DIAGNOSE_TIER_1, DIAGNOSE_TIER_2, DIAGNOSE_TIER_3, DIAGNOSE_TIER_4
    _ensure_medical_db(character)
    if medicine_level is None or medicine_level < DIAGNOSE_TIER_1:
        return ""
    bleeding_level, _ = compute_effective_bleed_level(character)
    fractures = character.db.fractures or []
    splinted = character.db.splinted_bones or []
    organ_damage = character.db.organ_damage or {}
    if not bleeding_level and not fractures and not organ_damage:
        return ""
    lines = []
    if medicine_level >= DIAGNOSE_TIER_1:
        bits = []
        if bleeding_level > 0:
            bits.append("They are bleeding.")
        if fractures:
            bits.append("You notice possible fracture or serious limb injury.")
        if bits:
            lines.append(f"{MC['compensated']}Physical exam:|n " + " ".join(bits))
        if medicine_level < DIAGNOSE_TIER_2:
            return "\n".join(lines) if lines else ""
    if medicine_level >= DIAGNOSE_TIER_2:
        lines = []
        if bleeding_level > 0:
            lines.append(f"{MC['compensated']}Bleeding:|n " + BLEEDING_LEVELS[min(bleeding_level, 4)])
        if fractures:
            regions = sorted({BONE_TO_REGION.get(b, b) for b in fractures if BONE_TO_REGION.get(b, b)})
            if regions:
                lines.append(f"{MC['compensated']}Possible fracture / serious injury:|n " + ", ".join(regions))
        if medicine_level < DIAGNOSE_TIER_3:
            return "\n".join(lines) if lines else ""
    if medicine_level >= DIAGNOSE_TIER_3:
        lines = []
        if bleeding_level > 0:
            lines.append(f"{MC['compensated']}Bleeding:|n " + BLEEDING_LEVELS[min(bleeding_level, 4)])
        if fractures:
            lines.append(f"{MC['compensated']}Fractures:|n " + ", ".join(BONE_INFO.get(b, b) + (" (splinted)" if b in splinted else "") for b in fractures))
        if organ_damage:
            regions = sorted({ORGAN_TO_REGION.get(ok, "internal") for ok in organ_damage if organ_damage.get(ok, 0) > 0})
            if regions:
                lines.append(f"{MC['compensated']}Signs of internal trauma:|n " + ", ".join(regions) + " — scanner needed for detail.")
        if medicine_level < DIAGNOSE_TIER_4:
            return "\n".join(lines) if lines else ""
    lines = []
    if bleeding_level > 0:
        lines.append(f"{MC['compensated']}Bleeding:|n " + BLEEDING_LEVELS[min(bleeding_level, 4)])
    if fractures:
        lines.append(f"{MC['compensated']}Fractures:|n " + ", ".join(BONE_INFO.get(b, b) + (" (splinted)" if b in splinted else "") for b in fractures))
    if organ_damage:
        regions = sorted({ORGAN_TO_REGION.get(ok, "internal") for ok in organ_damage if organ_damage.get(ok, 0) > 0})
        if regions:
            lines.append(f"{MC['compensated']}Internal trauma (by region):|n " + ", ".join(regions) + ". Use a bioscanner for precise assessment.")
    return "\n".join(lines) if lines else ""


def get_medical_detail(character):
    from world.medical.core import _ensure_medical_db
    from world.medical.injuries import rebuild_derived_trauma_views, compute_effective_bleed_level, _normalize_injuries
    from world.medical.infection import INFECTION_CATALOG, INFECTION_STAGE_LABELS
    from world.medical import ORGAN_INFO, BONE_INFO, BLEEDING_LEVELS
    _ensure_medical_db(character)
    rebuild_derived_trauma_views(character)
    out = ["|wTRAUMA ASSESSMENT|n"]
    organ_damage = character.db.organ_damage or {}
    if organ_damage:
        out.append("|wInternal / organ trauma:|n")
        for organ_key, severity in sorted(organ_damage.items()):
            if severity > 0:
                names = ORGAN_INFO.get(organ_key, (organ_key,) * 4)
                destroyed = any(
                    organ_key in (i.get("organ_damage") or {}) and i.get("organ_destroyed")
                    for i in (character.db.injuries or [])
                )
                if destroyed:
                    out.append(f"  {names[0].title()}: {MC['arrest']}DESTROYED - chrome replacement required|n")
                else:
                    out.append(f"  {names[0].title()}: {names[min(severity, 3)]}")
    else:
        out.append("|wInternal / organ trauma:|n  None noted.")
    from world.medical.limb_trauma import LIMB_INFO, LIMB_SLOTS
    limb_damage = character.db.limb_damage or {}
    if limb_damage:
        out.append("|wLimb trauma:|n")
        for limb_key in sorted(LIMB_SLOTS):
            sev = int(limb_damage.get(limb_key, 0) or 0)
            if sev <= 0:
                continue
            names = LIMB_INFO.get(limb_key, (limb_key,) * 4)
            destroyed = any(
                limb_key in (i.get("limb_damage") or {}) and i.get("fracture_destroyed")
                for i in (character.db.injuries or [])
            )
            if destroyed:
                out.append(f"  {names[0].title()}: {MC['arrest']}DESTROYED - chrome limb required|n")
            else:
                out.append(f"  {names[0].title()}: {names[min(sev, 3)]}")
    else:
        out.append("|wLimb trauma:|n  None noted.")
    fractures = character.db.fractures or []
    out.append("|wFractures:|n " + (", ".join(BONE_INFO.get(b, b) for b in fractures) if fractures else " None."))
    level, _ = compute_effective_bleed_level(character)
    out.append("|wBleeding:|n " + BLEEDING_LEVELS[min(level, 4)])
    infected = []
    for injury in (_normalize_injuries(character) or []):
        stage = int(injury.get("infection_stage", 0) or 0)
        if stage <= 0:
            continue
        ikey = injury.get("infection_type") or "surface_cellulitis"
        ilabel = INFECTION_CATALOG.get(ikey, {}).get("label", ikey.replace("_", " "))
        part = (injury.get("body_part") or "wound").strip()
        infected.append(f"{part}: {ilabel} ({INFECTION_STAGE_LABELS.get(stage, 'progressing')})")
    out.append("|wInfection:|n " + ("; ".join(infected) if infected else " None."))
    return "\n".join(out)
