from __future__ import annotations

import random

from evennia import TICKER_HANDLER as ticker
from evennia.utils import logger
from evennia.utils import delay

from .utils import (
    get_object_by_id,
    get_combat_target,
    set_combat_target,
    combat_display_name,
    has_reciprocal_combat,
    clear_engagement_index,
    unregister_as_attacker,
    is_attacking_target,
)
from .engine import execute_combat_turn
from .instance import ensure_instance, leave_instance
from .range_system import on_combat_start, on_combat_end
from .cover import clear_suppression, clear_cover_state, maybe_reset_room_cover, mark_room_combat_activity
from world.combat.weapon_definitions import COMBAT_READY_ATTACKER_MSG

COMBAT_INTERVAL = 5
COMBAT_STAGGER = COMBAT_INTERVAL / 2.0
COMBAT_START_DELAY_MIN, COMBAT_START_DELAY_MAX = 5.0, 6.0

COMBAT_READY_DEFENDER_MSG = "|rYou square up, getting ready to fight.|n"
COMBAT_READY_ROOM_MSG = "|r{defender} squares up, getting ready to fight.|n"
COMBAT_READY_ATTACKER_ROOM_MSG = "|r{attacker} gets ready to fight {target}.|n"


def ticker_id(attacker, defender):
    if not attacker or not defender:
        return None
    return f"combat_{attacker.id}_{defender.id}"


def _clear_combat_round_flags(character):
    """Drop flee/skip flags when combat ends so they do not carry into the next fight."""
    if not character or not hasattr(character, "db"):
        return
    if getattr(character.db, "combat_flee_attempted", False):
        character.attributes.remove("combat_flee_attempted")
    if getattr(character.db, "combat_skip_next_turn", False):
        character.attributes.remove("combat_skip_next_turn")


def remove_both_combat_tickers(a, b):
    """Stop both combat tickers for this pair and end combat for both. Call when someone dies or flees."""
    id_ab = ticker_id(a, b)
    id_ba = ticker_id(b, a)
    for idstring in (id_ab, id_ba):
        if idstring:
            try:
                ticker.remove(COMBAT_INTERVAL, execute_combat_turn, idstring=idstring, persistent=True)
            except KeyError:
                pass
    if a and hasattr(a, "db"):
        set_combat_target(a, None)
        a.db.combat_ended = True
        clear_suppression(a)
        leave_instance(a)
        _clear_combat_round_flags(a)
    if b and hasattr(b, "db"):
        set_combat_target(b, None)
        b.db.combat_ended = True
        clear_suppression(b)
        leave_instance(b)
        _clear_combat_round_flags(b)
    on_combat_end(a, b)


def _clear_stale_pair(a, b):
    if a and hasattr(a, "db"):
        set_combat_target(a, None)
        a.db.combat_ended = True
    if b and hasattr(b, "db"):
        set_combat_target(b, None)
        b.db.combat_ended = True


def cleanup_orphaned_combat_tickers():
    """
    Run on server start.
    Remove persistent combat tickers whose combatants no longer reciprocally target each other.
    """
    clear_engagement_index()
    total = 0
    removed = 0
    handlers = []
    for attr in ("all", "get_all", "storage", "_storage"):
        obj = getattr(ticker, attr, None)
        if obj is None:
            continue
        handlers.append((attr, obj))
    for attr, obj in handlers:
        try:
            records = obj() if callable(obj) else obj
        except Exception:
            continue
        if isinstance(records, dict):
            records = records.values()
        for rec in records or []:
            try:
                callback = getattr(rec, "callback", None) or rec.get("callback")
                if callback != execute_combat_turn:
                    continue
                kwargs = getattr(rec, "kwargs", None) or rec.get("kwargs") or {}
                a = get_object_by_id(kwargs.get("attacker_id"))
                d = get_object_by_id(kwargs.get("defender_id"))
                total += 1
                if not a or not d or not has_reciprocal_combat(a, d):
                    removed += 1
                    try:
                        idstring = getattr(rec, "idstring", None) or rec.get("idstring")
                        ticker.remove(COMBAT_INTERVAL, execute_combat_turn, idstring=idstring, persistent=True)
                    except Exception:
                        pass
                    _clear_stale_pair(a, d)
            except Exception:
                continue
        if total:
            break
    logger.log_info(f"combat.cleanup_orphaned_combat_tickers checked={total} removed={removed}")


def _get_attacker_weapon_key(attacker):
    wielded_obj = getattr(attacker.db, "wielded_obj", None)
    if wielded_obj and getattr(wielded_obj, "location", None) == attacker:
        return getattr(attacker.db, "wielded", "fists") or "fists"
    return "fists"


def defender_first_attack(defender_id, attacker_id):
    defender = get_object_by_id(defender_id)
    attacker = get_object_by_id(attacker_id)
    if not defender or not attacker:
        return
    if getattr(defender.db, "combat_ended", False) or getattr(attacker.db, "combat_ended", False):
        return
    if get_combat_target(defender) != attacker:
        return
    if getattr(defender.db, "is_creature", False):
        return
    try:
        import traceback

        execute_combat_turn(defender, attacker)
    except Exception as e:
        tb = traceback.format_exc()
        if hasattr(defender, "msg"):
            defender.msg(f"|rCombat error: {e}|n")
        try:
            from evennia import logger

            logger.log_err(f"Combat execute_combat_turn error: {e}\n{tb}")
        except Exception:
            pass
        return
    id_them = ticker_id(defender, attacker)
    if id_them:
        try:
            ticker.add(
                COMBAT_INTERVAL,
                execute_combat_turn,
                idstring=id_them,
                persistent=True,
                attacker_id=defender.id,
                defender_id=attacker.id,
            )
        except Exception as e:
            if hasattr(defender, "msg"):
                defender.msg(f"|rTicker add failed: {e}|n")


def _start_first_round(attacker_id, target_id):
    attacker = get_object_by_id(attacker_id)
    target = get_object_by_id(target_id)
    if not attacker or not target:
        if attacker:
            set_combat_target(attacker, None)
        if target:
            set_combat_target(target, None)
        return
    if getattr(attacker.db, "combat_ended", False) or getattr(target.db, "combat_ended", False):
        return
    if get_combat_target(attacker) != target:
        return
    try:
        import traceback

        execute_combat_turn(attacker, target)
    except Exception as e:
        tb = traceback.format_exc()
        attacker.msg(f"|rCombat error: {e}|n")
        try:
            from evennia import logger

            logger.log_err(f"Combat execute_combat_turn error: {e}\n{tb}")
        except Exception:
            pass
        set_combat_target(attacker, None)
        set_combat_target(target, None)
        return
    id_me = ticker_id(attacker, target)
    if id_me:
        try:
            ticker.add(
                COMBAT_INTERVAL,
                execute_combat_turn,
                idstring=id_me,
                persistent=True,
                attacker_id=attacker.id,
                defender_id=target.id,
            )
        except Exception as e:
            if hasattr(attacker, "msg"):
                attacker.msg(f"|rTicker add failed: {e}|n")
    delay(COMBAT_STAGGER, defender_first_attack, target.id, attacker.id)


def start_combat_ticker(attacker, target):
    if not attacker or not target:
        return
    maybe_reset_room_cover(getattr(attacker, "location", None) or getattr(target, "location", None))
    mark_room_combat_activity(getattr(attacker, "location", None) or getattr(target, "location", None))

    # Check if target is jacked into the Matrix and trigger emergency disconnect
    if hasattr(target.db, 'sitting_on') and target.db.sitting_on:
        from typeclasses.matrix.devices import DiveRig
        rig = target.db.sitting_on
        if isinstance(rig, DiveRig) and rig.db.active_connection:
            conn = rig.db.active_connection
            if conn and conn.get('character') == target:
                # Emergency disconnect - rig safety systems detect combat stress
                target.msg("|y*** EMERGENCY DISCONNECT ***|n")
                target.msg("|yRig safety protocols detect physical distress - forcing jack-out!|n")
                from typeclasses.matrix.avatars import JACKOUT_EMERGENCY
                rig.disconnect(target, severity=JACKOUT_EMERGENCY, reason="Combat initiated")

    set_combat_target(attacker, target)
    if not getattr(target.db, "is_creature", False) and get_combat_target(target) is None:
        set_combat_target(target, attacker)
    if getattr(attacker.db, "current_hp", None) is None or (attacker.db.current_hp or 0) <= 0:
        attacker.db.current_hp = getattr(attacker, "max_hp", 100)
    if getattr(target.db, "current_hp", None) is None or (target.db.current_hp or 0) <= 0:
        target.db.current_hp = getattr(target, "max_hp", 100)
    attacker.db.combat_ended = False
    target.db.combat_ended = False
    clear_cover_state(attacker, reset_pose=True)
    clear_cover_state(target, reset_pose=True)
    ensure_instance(attacker, target)

    weapon_key = _get_attacker_weapon_key(attacker)
    on_combat_start(attacker, target, weapon_key)
    ready_attacker = COMBAT_READY_ATTACKER_MSG.get(weapon_key, COMBAT_READY_ATTACKER_MSG["fists"])
    attacker.msg(ready_attacker.format(target=combat_display_name(target, attacker)))
    target.msg(COMBAT_READY_DEFENDER_MSG)
    if target.location:
        loc = target.location
        viewers_def = [c for c in loc.contents_get(content_type="character") if c != target]
        for v in viewers_def:
            v.msg(COMBAT_READY_ROOM_MSG.format(defender=combat_display_name(target, v)))
        viewers_atk = [c for c in loc.contents_get(content_type="character") if c != attacker]
        for v in viewers_atk:
            if v is target:
                v.msg(
                    "|r{attacker} gets ready to fight you.|n".format(
                        attacker=combat_display_name(attacker, v)
                    )
                )
            else:
                v.msg(
                    COMBAT_READY_ATTACKER_ROOM_MSG.format(
                        attacker=combat_display_name(attacker, v),
                        target=combat_display_name(target, v),
                    )
                )

    sec = random.uniform(COMBAT_START_DELAY_MIN, COMBAT_START_DELAY_MAX)
    delay(sec, _start_first_round, attacker.id, target.id)


def schedule_staggered_first_round(attacker, target):
    """Queue the first strike + recurring ticker (same cadence as start_combat_ticker)."""
    if not attacker or not target:
        return
    sec = random.uniform(COMBAT_START_DELAY_MIN, COMBAT_START_DELAY_MAX)
    delay(sec, _start_first_round, attacker.id, target.id)


def resume_offensive_schedule(attacker, target):
    """
    Start (or restart) this character's attack ticker against target without re-running combat setup
    (range, cover reset, room messages). Use when they still have combat_target but had stopped attacking.
    Returns True if a schedule was started, False if already actively attacking.
    """
    if not attacker or not target or get_combat_target(attacker) != target:
        return False
    if is_attacking_target(attacker, target):
        return False
    set_combat_target(attacker, target)
    schedule_staggered_first_round(attacker, target)
    return True


def stop_combat_ticker(attacker, target):
    if not attacker or not target:
        return
    if get_combat_target(attacker) != target:
        attacker.msg("|yYou're not attacking them.|n")
        return
    if not is_attacking_target(attacker, target):
        attacker.msg("|yYou're not pressing an attack right now.|n")
        return
    id_at = ticker_id(attacker, target)
    if id_at:
        try:
            ticker.remove(COMBAT_INTERVAL, execute_combat_turn, idstring=id_at, persistent=True)
        except KeyError:
            pass
    unregister_as_attacker(attacker)
    _clear_combat_round_flags(attacker)
    reciprocal = has_reciprocal_combat(attacker, target)
    other_still_attacking = is_attacking_target(target, attacker)
    if reciprocal and not other_still_attacking:
        remove_both_combat_tickers(attacker, target)
        attacker.msg("|yNeither of you press the attack and you disengage completely.|n")
        target.msg("|yNeither of you press the attack and you disengage completely.|n")
        return
    attacker.msg(f"|yYou stop attacking at {combat_display_name(target, attacker)}.|n")
    if hasattr(target, "msg"):
        target.msg(f"|y{combat_display_name(attacker, target)} stops attacking you.|n")
