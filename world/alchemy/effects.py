"""
Apply drug effects: buffs, special db flags, echoes, comedown scheduling.
"""
import random
import time

from evennia.utils import delay
from evennia.utils import logger

from world.alchemy import DRUGS
from world.alchemy.crafting import potency_multiplier, tolerance_multiplier
from world.buffs import build_drug_buff_class
from world.rpg.survival import _clamp, _has_cyberware, flush_bac


def has_pain_suppression(character):
    """True if pain editor chrome or drug suppression is active."""
    if not character or not getattr(character, "db", None):
        return False
    if bool(getattr(character.db, "drug_pain_suppression", False)):
        return True
    return _has_cyberware(character, "pain_editor")


def _scale_stat_value(base_value, potency_mult):
    return int(round(float(base_value) * float(potency_mult)))


def _modify_psychosis(character, delta):
    cur = int(getattr(character.db, "cyberpsychosis_score", 0) or 0)
    character.db.cyberpsychosis_score = _clamp(cur + int(delta), 0, 200)


def _apply_color_shift_text(text):
    colors = ["|c", "|m", "|M", "|C", "|g", "|G", "|y"]
    words = text.split(" ")
    result = []
    for word in words:
        if "|" in word or len(word) < 4:
            result.append(word)
            continue
        if random.random() < 0.15:
            color = random.choice(colors)
            result.append(f"{color}{word}|n")
        else:
            result.append(word)
    return " ".join(result)


def apply_msg_color_shift(character, text):
    """Used from Character.msg when drug_color_shift is set."""
    if not isinstance(text, str) or not text:
        return text
    return _apply_color_shift_text(text)


def _apply_special(character, key, potency_mult, turning_on):
    """Apply or remove special effect flags and hooks."""
    if key == "pain_suppression":
        character.db.drug_pain_suppression = bool(turning_on)
    elif key == "bleeding_resistance":
        character.db.drug_bleed_resistance = 0.3 if turning_on else 0.0
    elif key == "consciousness_sustain":
        character.db.drug_consciousness_sustain = bool(turning_on)
    elif key == "stamina_regen_boost":
        character.db.drug_stamina_regen_bonus = 3 if turning_on else 0
    elif key == "regen_boost_major":
        character.db.drug_regen_multiplier = 2.0 if turning_on else 1.0
    elif key == "infection_resistance":
        character.db.drug_infection_resistance = 0.05 if turning_on else 0.0
    elif key == "flush_alcohol" and turning_on:
        # Flush 50% of current BAC; does nothing on comedown (one-shot on-apply only).
        flush_bac(character, fraction=0.5)
    elif key == "hunger_increase":
        character.db.drug_hunger_multiplier = 2.0 if turning_on else 1.0
    elif key == "visual_color_shift":
        character.db.drug_color_shift = bool(turning_on)
    elif key == "hallucination_mild":
        character.db.drug_hallucination_severity = 1 if turning_on else 0
    elif key == "hallucination_severe":
        character.db.drug_hallucination_severity = 3 if turning_on else 0
    elif key == "void_sight":
        character.db.drug_void_sight = bool(turning_on)
    elif key == "chrome_psychosis_reduction":
        # Psychosis changes are permanent mutations — we snapshot the delta on the
        # active_drug entry and restore it on comedown to avoid additive stacking
        # when the same drug is taken multiple times.  The actual write happens in
        # _apply_specials_for_drug / _clear_specials_for_drug via the snapshot.
        if turning_on:
            _modify_psychosis(character, -15)
        # Reversal is handled by _clear_specials_for_drug using the snapshot.
    elif key == "cyberpsychosis_spike":
        if turning_on:
            _modify_psychosis(character, 30)
        # Reversal is handled by _clear_specials_for_drug using the snapshot.
    elif key == "tolerance_buildup_fast":
        pass  # handled in addiction roll for greenmote


def _clear_specials_for_drug(character, drug, drug_key=None):
    """
    Reverse special effects when a drug wears off.

    For psychosis-mutating specials we restore from the snapshot stored at
    application time rather than applying a fixed inverse delta, preventing
    additive drift when the drug is taken multiple times.
    """
    specials = drug.get("effects", {}).get("special", []) or []
    psychosis_keys = {"chrome_psychosis_reduction", "cyberpsychosis_spike"}

    # Load snapshot if available
    snapshot = {}
    if drug_key:
        active = getattr(character.db, "active_drugs", None) or {}
        entry = active.get(drug_key) or {}
        snapshot = entry.get("psychosis_snapshot") or {}

    for sp in specials:
        if sp in psychosis_keys and snapshot:
            # Restore to the value recorded before the drug was applied.
            saved = snapshot.get(sp)
            if saved is not None:
                character.db.cyberpsychosis_score = _clamp(int(saved), 0, 200)
            # If no snapshot (old data), fall back to inverse delta.
            else:
                if sp == "chrome_psychosis_reduction":
                    _modify_psychosis(character, 15)
                elif sp == "cyberpsychosis_spike":
                    _modify_psychosis(character, -30)
        else:
            _apply_special(character, sp, 1.0, False)


def _apply_specials_for_drug(character, drug, potency_mult, drug_key=None):
    """
    Apply special effects and snapshot psychosis score before any mutation,
    so comedown can restore it exactly.
    """
    specials = drug.get("effects", {}).get("special", []) or []
    psychosis_keys = {"chrome_psychosis_reduction", "cyberpsychosis_spike"}

    # Build snapshot of current psychosis score for any psychosis-mutating specials.
    psychosis_snapshot = {}
    if any(sp in psychosis_keys for sp in specials) and drug_key:
        cur_score = int(getattr(character.db, "cyberpsychosis_score", 0) or 0)
        for sp in specials:
            if sp in psychosis_keys:
                psychosis_snapshot[sp] = cur_score

    for sp in specials:
        _apply_special(character, sp, potency_mult, True)

    # Store snapshot on the active_drug entry so comedown can read it.
    if psychosis_snapshot and drug_key:
        active = dict(getattr(character.db, "active_drugs", None) or {})
        entry = dict(active.get(drug_key) or {})
        entry["psychosis_snapshot"] = psychosis_snapshot
        active[drug_key] = entry
        character.db.active_drugs = active


def _schedule_active_echoes(character, drug_key, duration_seconds):
    """Random echo every 120-180s during effect."""
    if duration_seconds <= 0:
        return

    def _tick(char_id, dk, remaining):
        try:
            from evennia.utils.search import search_object

            res = search_object(f"#{char_id}")
            if not res:
                return
            ch = res[0]
            drug = DRUGS.get(dk)
            if not drug:
                return
            pool = drug.get("effects", {}).get("echo_active", []) or []
            if pool:
                ch.msg(random.choice(pool))
            next_in = random.randint(120, 180)
            if remaining - next_in > 30:
                delay(next_in, _tick, char_id, dk, remaining - next_in)
        except Exception as err:
            logger.log_trace(f"_schedule_active_echoes tick: {err}")

    first = random.randint(120, min(180, max(60, duration_seconds)))
    if duration_seconds > first:
        delay(first, _tick, character.id, drug_key, duration_seconds - first)


def _active_drugs_provide_special(character, special_key):
    """True if any currently active drug (other than the one being cleared) provides this special."""
    active = getattr(character.db, "active_drugs", None) or {}
    for dk, entry in active.items():
        drug = DRUGS.get(dk)
        if not drug:
            continue
        specials = drug.get("effects", {}).get("special", []) or []
        if special_key in specials:
            return True
    return False


def _begin_comedown(character_id, drug_key):
    try:
        from evennia.utils.search import search_object

        res = search_object(f"#{character_id}")
        if not res:
            return
        character = res[0]
        drug = DRUGS.get(drug_key)
        if not drug:
            return
        _clear_specials_for_drug(character, drug, drug_key=drug_key)
        cd = drug.get("comedown", {}) or {}
        dur = int(cd.get("duration_seconds", 0) or 0)
        debuffs = cd.get("stat_debuffs") or {}
        name = drug.get("name", drug_key)
        cls = build_drug_buff_class(drug_key, "comedown", f"{name} comedown", max(1, dur), {}, debuffs)
        character.buffs.add(cls, duration=max(1, dur))
        echoes = cd.get("echo_comedown") or []
        if echoes:
            character.msg(random.choice(echoes))
        # Track comedown window for chasing-the-high
        cdm = dict(getattr(character.db, "comedown_drugs", None) or {})
        cdm[drug_key] = time.time() + max(1, dur)
        character.db.comedown_drugs = cdm
        # Only clear consciousness_sustain if no other active drug still provides it.
        if not _active_drugs_provide_special(character, "consciousness_sustain"):
            character.db.drug_consciousness_sustain = False
            if (character.db.current_hp or 0) <= 0:
                try:
                    from world.death import make_flatlined

                    make_flatlined(character, attacker=None)
                except Exception:
                    pass
        delay(max(1, dur), _end_comedown_track, character.id, drug_key)
    except Exception as err:
        logger.log_trace(f"_begin_comedown: {err}")


def _end_comedown_track(character_id, drug_key):
    try:
        from evennia.utils.search import search_object

        res = search_object(f"#{character_id}")
        if not res:
            return
        ch = res[0]
        cdm = dict(getattr(ch.db, "comedown_drugs", None) or {})
        if drug_key in cdm:
            del cdm[drug_key]
        ch.db.comedown_drugs = cdm
    except Exception:
        pass


def _announce_drug_administration(character, drug, administrator=None):
    """
    Echo the physical act of taking a drug to the character, any administrator, and the room.
    Tablet/capsule: swallow. Injectable and liquid (vials): inject. Other forms: generic.
    """
    if not character or not drug:
        return
    form = (drug.get("form") or "").lower()
    loc = getattr(character, "location", None)

    if administrator and administrator != character:
        if form in ("tablet", "capsule"):
            character.msg(f"{administrator.get_display_name(character)} gives you a dose; you swallow it.")
            administrator.msg(f"You give {character.get_display_name(administrator)} a dose; they swallow it.")
            if loc:
                loc.msg_contents(
                    "{admin} gives {targ} something to swallow.",
                    exclude=[administrator, character],
                    mapping={"admin": administrator, "targ": character},
                )
        elif form in ("injectable", "liquid"):
            character.msg(f"{administrator.get_display_name(character)} injects you.")
            administrator.msg(f"You inject {character.get_display_name(administrator)}.")
            if loc:
                loc.msg_contents(
                    "{admin} injects {targ}.",
                    exclude=[administrator, character],
                    mapping={"admin": administrator, "targ": character},
                )
        else:
            character.msg(f"{administrator.get_display_name(character)} administers a dose. Your blood answers.")
            administrator.msg(f"You administer a dose to {character.get_display_name(administrator)}.")
            if loc:
                loc.msg_contents(
                    "{admin} administers something to {targ}.",
                    exclude=[administrator, character],
                    mapping={"admin": administrator, "targ": character},
                )
        return

    if form in ("tablet", "capsule"):
        character.msg("You swallow a dose.")
        if loc:
            loc.msg_contents(
                "{name} swallows something.",
                exclude=character,
                mapping={"name": character},
            )
    elif form in ("injectable", "liquid"):
        character.msg("You inject the dose.")
        if loc:
            loc.msg_contents(
                "{name} injects something — a vial or syringe, quick and practiced.",
                exclude=character,
                mapping={"name": character},
            )
    else:
        character.msg("You take a dose.")
        if loc:
            loc.msg_contents(
                "{name} takes a dose.",
                exclude=character,
                mapping={"name": character},
            )


def _roll_addiction(character, drug_key, rate_mult=1.0):
    drug = DRUGS.get(drug_key)
    if not drug:
        return
    add = drug.get("addiction", {}) or {}
    base = float(add.get("addiction_rate", 0.0) or 0.0) * float(rate_mult)
    if base <= 0:
        return
    if random.random() >= base:
        return
    ad = dict(getattr(character.db, "addictions", None) or {})
    entry = dict(ad.get(drug_key) or {})
    level = min(4, int(entry.get("level", 0) or 0) + 1)
    entry["level"] = level
    entry["last_dose"] = time.time()
    entry["total_doses"] = int(entry.get("total_doses", 0) or 0) + 1
    entry["withdrawal_active"] = False
    entry["last_recovery_reduction_at"] = 0
    ad[drug_key] = entry
    character.db.addictions = ad


def apply_drug(character, drug_key, quality=50, suspicious=False, administrator=None):
    """
    Apply a drug's effects. Returns (success, message).
    administrator: another character giving the dose (e.g. CmdDose ... to <target>); None if self-administered.
    """
    drug = DRUGS.get(drug_key)
    if not drug:
        return False, "Unknown substance."

    _announce_drug_administration(character, drug, administrator=administrator)

    from world.alchemy.overdose import check_overdose, trigger_fatal_overdose, trigger_severe_overdose

    # Chasing the high: comedown active for this drug
    cdm = getattr(character.db, "comedown_drugs", None) or {}
    in_comedown = drug_key in cdm and float(cdm.get(drug_key, 0) or 0) > time.time()

    lowered = 1 if in_comedown else 0
    od = check_overdose(character, drug_key, lowered_threshold=lowered, suspicious_product=suspicious)
    if od == "fatal":
        trigger_fatal_overdose(character, drug_key)
        return True, ""
    elif od == "severe":
        trigger_severe_overdose(character, drug_key)
        # Spec deviation: severe OD skips the positive buff and addiction roll.
        # The overdose handler applies its own harsh penalties; adding the buff on
        # top would be confusing and the addiction skip is intentional — a character
        # who ODed didn't "enjoy" the dose.
        return True, ""

    add = drug.get("addiction", {}) or {}
    tol_rate = float(add.get("tolerance_rate", 0.0) or 0.0)
    ad = dict(getattr(character.db, "addictions", None) or {})
    level = int((ad.get(drug_key) or {}).get("level", 0) or 0)
    if "tolerance_buildup_fast" in (drug.get("effects", {}).get("special") or []):
        tol_rate *= 2.0
    tol_mult = tolerance_multiplier(level, tol_rate)
    qual = _clamp(int(quality), 0, 100)
    potency_mult = potency_multiplier(qual) * tol_mult

    eff = drug.get("effects", {}) or {}
    dur = int(eff.get("duration_seconds", 60) or 60)
    stat_buffs = eff.get("stat_buffs") or {}
    stat_debuffs = eff.get("stat_debuffs") or {}
    scaled_buffs = {k: _scale_stat_value(v, potency_mult) for k, v in stat_buffs.items()}
    scaled_debuffs = {k: _scale_stat_value(v, potency_mult) for k, v in stat_debuffs.items()}

    name = drug.get("name", drug_key)
    cls = build_drug_buff_class(drug_key, "", name, dur, scaled_buffs, scaled_debuffs)
    character.buffs.add(cls, duration=dur)

    # Write active_drugs entry before applying specials so the psychosis snapshot
    # can be stored on the same entry in _apply_specials_for_drug.
    active = dict(getattr(character.db, "active_drugs", None) or {})
    prev = active.get(drug_key, {})
    active[drug_key] = {
        "applied_at": time.time(),
        "duration": dur,
        "dose_count": int(prev.get("dose_count", 0) or 0) + 1,
        "quality": qual,
    }
    character.db.active_drugs = active

    _apply_specials_for_drug(character, drug, potency_mult, drug_key=drug_key)

    onset = eff.get("echo_onset") or []
    if onset:
        character.msg(random.choice(onset))
    _schedule_active_echoes(character, drug_key, dur)
    delay(dur, _begin_comedown, character.id, drug_key)

    rate_mult = 1.5 if in_comedown else 1.0
    if in_comedown:
        character.msg(
            "|yYou dose again. The comedown fades. The high returns. Something in your chest tightens. This is how it starts.|n"
        )
    try:
        from world.alchemy.addiction import clear_withdrawal_on_dose

        clear_withdrawal_on_dose(character, drug_key)
    except Exception:
        pass
    _roll_addiction(character, drug_key, rate_mult=rate_mult)
    return True, ""


def clear_drug_tracking_on_buff_expire(character, drug_key):
    """
    Called when a drug's main buff is removed early (e.g. by a medic, cleanse effect,
    or admin command).  Clears the active_drugs entry and reverses special flags so
    the character isn't left in a half-applied state.  The comedown delay() callback
    will still fire at the original scheduled time; _begin_comedown guards against a
    missing DRUGS entry but will still apply comedown debuffs — acceptable behaviour
    since the drug was in the body.
    """
    try:
        active = dict(getattr(character.db, "active_drugs", None) or {})
        if drug_key not in active:
            return
        drug = DRUGS.get(drug_key)
        if drug:
            _clear_specials_for_drug(character, drug, drug_key=drug_key)
        del active[drug_key]
        character.db.active_drugs = active
    except Exception as err:
        logger.log_trace(f"clear_drug_tracking_on_buff_expire: {err}")


def reconcile_active_drugs_after_reload(character):
    """
    BuffHandler is non-persistent; clear drug tracking and flags so nothing is half-applied.

    Note: delay() callbacks (comedown timers) are also non-persistent across reloads by
    default, so scheduled _begin_comedown calls will not fire after a reload.  If you ever
    switch to a persistent task runner, those callbacks would survive the reload and fire
    against an already-reconciled character — guard against that by checking active_drugs
    is empty at the start of _begin_comedown if needed.
    """
    try:
        from world.alchemy.overdose import _reset_drug_db_flags

        _active = dict(getattr(character.db, "active_drugs", None) or {})
        character.db.active_drugs = {}
        _reset_drug_db_flags(character)
        if _active:
            character.msg("|xThe chemistry in your blood no longer lines up with how you feel. The crash came while you were under.|n")
    except Exception as err:
        logger.log_trace(f"reconcile_active_drugs_after_reload: {err}")
