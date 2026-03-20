"""
Injury-state helpers split from world.medical.__init__.
"""
import time
import uuid

BLEED_DAMPENING_FACTOR = 0.45
BLEED_RATE_TO_LEVEL = (
    (0.5, 0),
    (1.5, 1),
    (2.5, 2),
    (3.5, 3),
    (999.0, 4),
)


def _set_injury_treatment_quality(injury, quality):
    if not injury:
        return
    q = max(0, min(3, int(quality or 0)))
    cur = int(injury.get("treatment_quality", 0) or 0)
    if q > cur:
        injury["treatment_quality"] = q
    if (injury.get("treatment_quality", 0) or 0) > 0:
        injury["treated"] = True
    if "infection_risk" in injury:
        infection = float(injury.get("infection_risk", 0.0) or 0.0)
        injury["infection_risk"] = max(0.0, infection - (0.02 * (injury.get("treatment_quality", 0) or 0)))
    if (injury.get("treatment_quality", 0) or 0) >= 2:
        injury["cleaned_at"] = time.time()


def ensure_injury_schema(injury):
    if not isinstance(injury, dict):
        return None
    injury.setdefault("injury_id", str(uuid.uuid4()))
    injury.setdefault("hp_occupied", int(injury.get("hp_occupied", 0) or 0))
    injury.setdefault("severity", int(injury.get("severity", 1) or 1))
    injury.setdefault("body_part", injury.get("body_part") or "")
    injury.setdefault("type", injury.get("type", "trauma"))
    injury.setdefault("treated", bool(injury.get("treated", False)))
    injury.setdefault("created_at", float(injury.get("created_at", time.time()) or time.time()))
    injury.setdefault("organ_damage", {})
    injury.setdefault("fracture", None)
    injury.setdefault("bleed_rate", 0.0)
    injury.setdefault("vessel_type", "none")
    injury.setdefault("bleed_treated", False)
    injury.setdefault("infection_risk", 0.0)
    injury.setdefault("treatment_quality", 0)
    injury.setdefault("cleaned_at", 0.0)
    injury.setdefault("infection_type", None)
    injury.setdefault("infection_stage", 0)
    injury.setdefault("infection_since", 0.0)
    injury.setdefault("last_infection_tick", 0.0)
    injury.setdefault("last_infection_reminder", 0.0)
    injury.setdefault("antibiotic_until", 0.0)
    injury.setdefault("antibiotic_potency", 0.0)
    injury.setdefault("antibiotic_profile", None)
    injury["hp_occupied"] = max(0, int(injury.get("hp_occupied", 0) or 0))
    injury["severity"] = max(1, min(4, int(injury.get("severity", 1) or 1)))
    injury["bleed_rate"] = max(0.0, float(injury.get("bleed_rate", 0.0) or 0.0))
    if not isinstance(injury.get("organ_damage"), dict):
        injury["organ_damage"] = {}
    injury["treatment_quality"] = max(0, min(3, int(injury.get("treatment_quality", 0) or 0)))
    return injury


def _normalize_injuries(character):
    injuries = getattr(character.db, "injuries", None) or []
    out = []
    changed = False
    for item in injuries:
        norm = ensure_injury_schema(item)
        if not norm:
            changed = True
            continue
        if norm is not item:
            changed = True
        out.append(norm)
    if changed or len(out) != len(injuries):
        character.db.injuries = out
    return out


def rebuild_derived_trauma_views(character):
    injuries = _normalize_injuries(character)
    organ_damage = {}
    fractures = []
    for injury in injuries:
        if (injury.get("hp_occupied", 0) or 0) <= 0:
            continue
        for organ_key, sev in (injury.get("organ_damage") or {}).items():
            if sev <= 0:
                continue
            organ_damage[organ_key] = max(organ_damage.get(organ_key, 0), int(sev))
        bone = injury.get("fracture")
        if bone and bone not in fractures:
            fractures.append(bone)
    character.db.organ_damage = organ_damage
    character.db.fractures = fractures
    return organ_damage, fractures


def get_active_bleed_wounds(character):
    injuries = _normalize_injuries(character)
    active = []
    for injury in injuries:
        if (injury.get("hp_occupied", 0) or 0) <= 0:
            continue
        if injury.get("bleed_treated"):
            continue
        rate = float(injury.get("bleed_rate", 0.0) or 0.0)
        if rate <= 0:
            continue
        active.append(injury)
    return sorted(active, key=lambda w: float(w.get("bleed_rate", 0.0) or 0.0), reverse=True)


def compute_effective_bleed_level(character):
    active = get_active_bleed_wounds(character)
    if not active:
        character.db.bleeding_level = 0
        return 0, 0.0
    weighted = 0.0
    for idx, injury in enumerate(active):
        rate = float(injury.get("bleed_rate", 0.0) or 0.0)
        weighted += rate if idx == 0 else (rate * BLEED_DAMPENING_FACTOR)
    level = 4
    for threshold, lvl in BLEED_RATE_TO_LEVEL:
        if weighted <= threshold:
            level = lvl
            break
    character.db.bleeding_level = level
    return level, weighted
