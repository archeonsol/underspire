"""
Bleeding subsystem split from world.medical.__init__.
"""
import random

BLEEDING_TICK_INTERVAL = 18
BLEEDING_DRAIN_PER_TICK = (1, 2, 3, 5)
HEMOSTATIC_REOPEN_CHANCE = 0.12
TOURNIQUET_TICKS_BEFORE_REOPEN = 6


def get_bleeding_drain_per_tick(character):
    from world.medical.injuries import compute_effective_bleed_level
    level, _ = compute_effective_bleed_level(character)
    if level == 0:
        return 0
    drain = BLEEDING_DRAIN_PER_TICK[min(level - 1, 3)]
    from typeclasses.cyberware_catalog import HemostaticRegulator
    has_hemo_reg = any(isinstance(cw, HemostaticRegulator) and not bool(getattr(cw.db, "malfunctioning", False)) for cw in (getattr(character.db, "cyberware", None) or []))
    if has_hemo_reg:
        drain = max(0, int(round(drain * 0.7)))
    return drain


def apply_bleeding_tick(character):
    from world.medical.core import _ensure_medical_db
    from world.medical.injuries import _normalize_injuries, get_active_bleed_wounds, compute_effective_bleed_level
    _ensure_medical_db(character)
    level, _ = compute_effective_bleed_level(character)
    tourniquet = getattr(character.db, "tourniquet_applied", False)
    # Exertion can reopen recently treated severe wounds.
    strenuous = bool(
        getattr(character.db, "combat_target", None)
        or getattr(character.db, "is_running", False)
        or getattr(character.db, "is_climbing", False)
        or getattr(character.db, "is_swimming", False)
    )
    if strenuous:
        for wound in _normalize_injuries(character):
            if (wound.get("hp_occupied", 0) or 0) <= 0:
                continue
            if int(wound.get("severity", 1) or 1) < 2:
                continue
            if int(wound.get("treatment_quality", 0) or 0) < 2:
                continue
            if random.random() < 0.04:
                wound["bleed_treated"] = False
                wound["bleed_rate"] = max(0.8, float(wound.get("bleed_rate", 0.0) or 0.0) + 0.8)
                if hasattr(character, "msg"):
                    character.msg("|yExertion tears at a recent closure. A wound reopens.|n")
                break
    if tourniquet:
        if level > 0:
            character.db.tourniquet_applied = False
            character.db.tourniquet_ticks = 0
        else:
            ticks = getattr(character.db, "tourniquet_ticks", 0) or 0
            character.db.tourniquet_ticks = ticks + 1
            if character.db.tourniquet_ticks >= TOURNIQUET_TICKS_BEFORE_REOPEN:
                injuries = _normalize_injuries(character)
                candidates = [i for i in injuries if (i.get("hp_occupied", 0) or 0) > 0]
                if candidates:
                    wound = sorted(candidates, key=lambda i: float(i.get("bleed_rate", 0.0) or 0.0), reverse=True)[0]
                    wound["bleed_treated"] = False
                    wound["bleed_rate"] = max(1.0, float(wound.get("bleed_rate", 0.0) or 0.0))
                    wound["bleed_rate"] = max(0.5, wound["bleed_rate"] - (0.3 * int(wound.get("treatment_quality", 0) or 0)))
                character.db.tourniquet_applied = False
                character.db.tourniquet_ticks = 0
                compute_effective_bleed_level(character)
                if character.location:
                    character.msg("|yThe tourniquet has been on too long. You loosen it; the wound reopens. Get proper closure soon.|n")
                    character.location.msg_contents(
                        "|y%s loosens the tourniquet; the wound reopens.|n" % character.get_display_name(character),
                        exclude=character,
                    )
            return False

    hemo_reopen = HEMOSTATIC_REOPEN_CHANCE
    active = get_active_bleed_wounds(character)
    if active:
        best_quality = max(int(w.get("treatment_quality", 0) or 0) for w in active)
        hemo_reopen = max(0.02, hemo_reopen - (0.02 * best_quality))
    if getattr(character.db, "bleeding_hemostatic_stabilized", False) and random.random() < hemo_reopen:
        injuries = get_active_bleed_wounds(character)
        if injuries:
            wound = injuries[0]
            wound["bleed_rate"] = min(4.0, float(wound.get("bleed_rate", 0.0) or 0.0) + 1.0)
            wound["bleed_treated"] = False
        else:
            all_injuries = _normalize_injuries(character)
            if all_injuries:
                wound = sorted(all_injuries, key=lambda i: float(i.get("created_at", 0) or 0), reverse=True)[0]
                wound["bleed_rate"] = max(1.0, float(wound.get("bleed_rate", 0.0) or 0.0))
                wound["bleed_treated"] = False
        character.db.bleeding_hemostatic_stabilized = False
        level, _ = compute_effective_bleed_level(character)
        if character.location:
            character.msg("|yThe hemostatic seal gives. The wound is bleeding again.|n")
            character.location.msg_contents(
                "|y%s's wound reopens; the hemostatic seal did not hold.|n" % character.get_display_name(character),
                exclude=character,
            )

    if level == 0:
        return False
    drain = get_bleeding_drain_per_tick(character)
    if drain <= 0:
        return False
    current = character.db.current_hp
    if current is None and hasattr(character, "max_hp"):
        character.db.current_hp = character.max_hp
        current = character.db.current_hp
    if (current or 0) <= 0:
        return False
    character.db.current_hp = max(0, (current or 0) - drain)
    if character.location:
        from typeclasses.cyberware_catalog import PainEditor
        has_pain_editor = any(isinstance(cw, PainEditor) and not bool(getattr(cw.db, "malfunctioning", False)) for cw in (getattr(character.db, "cyberware", None) or []))
        if not has_pain_editor:
            character.msg("|rYou're bleeding.|n")
        character.location.msg_contents(
            "|r%s is bleeding.|n" % character.get_display_name(character),
            exclude=character,
        )
    return True


def bleeding_tick_all():
    from world.medical.injuries import compute_effective_bleed_level
    from world.medical.infection import apply_infection_tick
    try:
        from evennia.objects.models import ObjectDB
        from world.death import is_flatlined, is_permanently_dead
        for obj in ObjectDB.objects.filter(db_location__isnull=False):
            try:
                if not getattr(obj, "db", None):
                    continue
                level, _ = compute_effective_bleed_level(obj)
                tourniquet = getattr(obj.db, "tourniquet_applied", False)
                has_injuries = bool(getattr(obj.db, "injuries", None) or [])
                if level == 0 and not tourniquet and not has_injuries:
                    continue
                if is_flatlined(obj) or is_permanently_dead(obj):
                    continue
                apply_bleeding_tick(obj)
                apply_infection_tick(obj)
                if (obj.db.current_hp or 0) <= 0:
                    if hasattr(obj, "at_damage"):
                        obj.at_damage(None, 0)
            except Exception:
                pass
    except Exception:
        pass
