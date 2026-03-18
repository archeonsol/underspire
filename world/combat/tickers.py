from __future__ import annotations

import random

from evennia import TICKER_HANDLER as ticker
from evennia.utils import delay

from .utils import get_object_by_id, get_combat_target, set_combat_target, combat_display_name
from .engine import execute_combat_turn
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
    if b and hasattr(b, "db"):
        set_combat_target(b, None)
        b.db.combat_ended = True


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
    if get_combat_target(defender) != attacker or get_combat_target(attacker) != defender:
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

    weapon_key = _get_attacker_weapon_key(attacker)
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


def stop_combat_ticker(attacker, target):
    if not attacker or not target:
        return
    if get_combat_target(attacker) != target:
        attacker.msg("|yYou're not attacking them.|n")
        return
    id_me = ticker_id(attacker, target)
    if not id_me:
        attacker.msg("|yYou are not in a fight.|n")
        return
    try:
        ticker.remove(COMBAT_INTERVAL, execute_combat_turn, idstring=id_me, persistent=True)
        set_combat_target(attacker, None)
        attacker.msg(f"|yYou pull back from the fight with {combat_display_name(target, attacker)}.|n")
    except KeyError:
        set_combat_target(attacker, None)
        attacker.msg("|yYou pull back from the fight.|n")
