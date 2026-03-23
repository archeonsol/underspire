"""
Biometric vehicle security: tiers, permissions, break-in, hotwire, alarms.
"""
from __future__ import annotations

import time
from typing import Any

SECURITY_PERMISSIONS = {
    "unlock": "Lock and unlock the vehicle.",
    "enter": "Enter the vehicle (or mount, for motorcycles).",
    "start": "Start the engine.",
    "drive": "Drive or fly the vehicle.",
    "modify": "Swap parts, paint, customize.",
    "authorize": "Add or remove other authorizations (delegate).",
    "full": "All permissions. Equivalent to owner access without ownership transfer.",
}

SECURITY_TIERS: dict[int, dict[str, Any]] = {
    1: {
        "name": "Thumb Scanner",
        "break_in_difficulty": 15,
        "hotwire_difficulty": 12,
        "lockout_after_fails": 10,
        "lockout_duration": 60,
        "has_alarm": False,
        "has_tracker": False,
        "has_immobilizer": False,
        "hotwire_checks_required": 1,
    },
    2: {
        "name": "Palm Reader",
        "break_in_difficulty": 25,
        "hotwire_difficulty": 22,
        "lockout_after_fails": 7,
        "lockout_duration": 180,
        "has_alarm": True,
        "has_tracker": False,
        "has_immobilizer": False,
        "hotwire_checks_required": 2,
    },
    3: {
        "name": "Retinal Lock",
        "break_in_difficulty": 40,
        "hotwire_difficulty": 35,
        "lockout_after_fails": 5,
        "lockout_duration": 600,
        "has_alarm": True,
        "has_tracker": True,
        "has_immobilizer": True,
        "hotwire_checks_required": 3,
    },
    4: {
        "name": "Multi-Biometric Array",
        "break_in_difficulty": 55,
        "hotwire_difficulty": 50,
        "lockout_after_fails": 3,
        "lockout_duration": 1800,
        "has_alarm": True,
        "has_tracker": True,
        "has_immobilizer": True,
        "hotwire_checks_required": 4,
    },
    5: {
        "name": "Inquisitorate Biolock",
        "break_in_difficulty": 75,
        "hotwire_difficulty": 70,
        "lockout_after_fails": 2,
        "lockout_duration": 3600,
        "has_alarm": True,
        "has_tracker": True,
        "has_immobilizer": True,
        "hotwire_checks_required": 5,
    },
}


def _staff_bypass(character) -> bool:
    try:
        acc = getattr(character, "account", None)
        if acc and (acc.permissions.check("Builder") or acc.permissions.check("Admin")):
            return True
    except Exception:
        pass
    return False


def effective_security_tier(vehicle) -> int:
    from world.vehicle_parts import get_part_condition

    base = int(getattr(vehicle.db, "security_tier", 1) or 1)
    base = max(1, min(5, base))
    try:
        c = get_part_condition(vehicle, "security") / 100.0
    except Exception:
        c = 1.0
    if c >= 0.5:
        return base
    reduction = int((0.5 - c) * 4)
    return max(1, base - reduction)


def check_vehicle_permission(vehicle, character, permission: str) -> bool:
    if not vehicle or not character:
        return False
    if _staff_bypass(character):
        return True
    owner_id = getattr(vehicle.db, "security_owner", None)
    if owner_id is None:
        return True
    if getattr(vehicle.db, "security_hotwired", False):
        return True
    if owner_id and character.id == owner_id:
        return True
    auths = getattr(vehicle.db, "security_authorizations", None) or {}
    char_perms = auths.get(character.id, set())
    if isinstance(char_perms, list):
        char_perms = set(char_perms)
    if "full" in char_perms:
        return True
    return permission in char_perms


def _can_authorize(vehicle, character) -> bool:
    owner_id = getattr(vehicle.db, "security_owner", None)
    if owner_id and character.id == owner_id:
        return True
    return check_vehicle_permission(vehicle, character, "authorize")


def authorize_character(vehicle, owner, target, permissions: set[str] | list[str]):
    if not _can_authorize(vehicle, owner):
        return False, "You don't have authorization privileges on this vehicle."
    if target == owner:
        return False, "You're the owner. You already have full access."
    perms = set(permissions) if not isinstance(permissions, str) else {permissions}
    for p in perms:
        if p not in SECURITY_PERMISSIONS:
            valid = ", ".join(SECURITY_PERMISSIONS.keys())
            return False, f"Unknown permission '{p}'. Valid: {valid}"
    auths = dict(getattr(vehicle.db, "security_authorizations", None) or {})
    tid = target.id
    current = auths.get(tid, set())
    if isinstance(current, list):
        current = set(current)
    current.update(perms)
    auths[tid] = current
    vehicle.db.security_authorizations = auths
    return True, f"Authorized. Permissions: {', '.join(sorted(current))}."


def deauthorize_character(vehicle, owner, target, permissions: set[str] | None = None):
    if not _can_authorize(vehicle, owner):
        return False, "You don't have authorization privileges."
    auths = dict(getattr(vehicle.db, "security_authorizations", None) or {})
    tid = target.id
    if tid not in auths:
        return False, "They have no authorizations on this vehicle."
    if permissions is None:
        del auths[tid]
        vehicle.db.security_authorizations = auths
        return True, "All access revoked."
    current = auths.get(tid, set())
    if isinstance(current, list):
        current = set(current)
    for p in permissions:
        current.discard(p)
    if not current:
        del auths[tid]
    else:
        auths[tid] = current
    vehicle.db.security_authorizations = auths
    return True, "Permissions updated."


def set_owner(vehicle, character):
    vehicle.db.security_owner = character.id
    vehicle.db.security_hotwired = False
    vehicle.db.security_failed_attempts = 0
    vehicle.db.security_lockout_until = 0.0


def transfer_ownership(vehicle, current_owner, new_owner):
    if not current_owner or current_owner.id != getattr(vehicle.db, "security_owner", None):
        return False, "You are not the owner."
    set_owner(vehicle, new_owner)
    vehicle.db.security_authorizations = {}
    return True, "Ownership transferred."


def lock_vehicle(vehicle, character):
    if not _staff_bypass(character) and getattr(vehicle.db, "security_owner", None) is None:
        return (
            False,
            "Biosecurity has no registered owner. Ask staff to assign one, or use a vehicle spawned with |wspawnitem|n.",
        )
    if not check_vehicle_permission(vehicle, character, "unlock"):
        return False, "Bioscan rejected. You are not authorized."
    if getattr(vehicle.db, "security_locked", False):
        return False, "Already locked."
    vehicle.db.security_locked = True
    vehicle.db.security_hotwired = False
    vehicle.db.security_failed_attempts = 0
    return True, "Locked. Biosecurity engaged."


def unlock_vehicle(vehicle, character):
    if not _staff_bypass(character) and getattr(vehicle.db, "security_owner", None) is None:
        return (
            False,
            "Biosecurity has no registered owner. Ask staff to assign one, or use a vehicle spawned with |wspawnitem|n.",
        )
    if not check_vehicle_permission(vehicle, character, "unlock"):
        return False, "Bioscan rejected. You are not authorized."
    if not getattr(vehicle.db, "security_locked", False):
        return False, "Already unlocked."
    vehicle.db.security_locked = False
    return True, "Unlocked. Biosecurity disengaged."


def _find_bypass_probe(character):
    for obj in character.contents:
        if getattr(obj.db, "bypass_probe_key", None):
            return obj
    return None


def _find_splice_kit(character):
    for obj in character.contents:
        if getattr(obj.db, "splice_kit_key", None):
            return obj
    return None


def _trigger_alarm(vehicle, perpetrator):
    from evennia.utils import delay

    from typeclasses.vehicles import vehicle_label

    vehicle.db.security_alarm_active = True
    vehicle.db.security_alarm_until = time.time() + 120
    vehicle_name = vehicle_label(vehicle)
    room = vehicle.location
    mid = getattr(vehicle.db, "matrix_id", None) or vehicle_name
    if room:
        room.msg_contents(
            f"|R[ALARM] {vehicle_name}'s security alarm blares. Strobing lights. The noise is piercing.|n"
        )
        for exit_obj in getattr(room, "exits", None) or []:
            dest = getattr(exit_obj, "destination", None)
            if dest:
                try:
                    dest.msg_contents("|y[ALARM] A vehicle alarm sounds from nearby.|n")
                except Exception:
                    pass
    tier = effective_security_tier(vehicle)
    tier_data = SECURITY_TIERS.get(tier, SECURITY_TIERS[1])
    if tier_data.get("has_tracker"):
        owner_id = getattr(vehicle.db, "security_owner", None)
        if owner_id:
            from evennia.utils.search import search_object

            owner_results = search_object(f"#{owner_id}")
            if owner_results:
                owner = owner_results[0]
                if owner.sessions.count():
                    perp_name = perpetrator.key if perpetrator else "someone"
                    room_name = room.key if room else "unknown location"
                    owner.msg(
                        f"|R[SECURITY ALERT] Your {vehicle_name} ({mid}) — unauthorized access attempt "
                        f"by {perp_name} at {room_name}.|n"
                    )
    delay(120, _stop_alarm, vehicle.id)
    delay(30, _alarm_tick, vehicle.id)


def _alarm_tick(vehicle_id):
    from evennia.utils import delay
    from evennia.utils.search import search_object

    from typeclasses.vehicles import vehicle_label

    results = search_object(f"#{vehicle_id}")
    if not results:
        return
    vehicle = results[0]
    if not getattr(vehicle.db, "security_alarm_active", False):
        return
    if float(getattr(vehicle.db, "security_alarm_until", 0) or 0) <= time.time():
        return
    room = vehicle.location
    if room:
        room.msg_contents(f"|R[ALARM] {vehicle_label(vehicle)}'s alarm continues to blare.|n")
    delay(30, _alarm_tick, vehicle.id)


def _stop_alarm(vehicle_id):
    from evennia.utils.search import search_object

    from typeclasses.vehicles import vehicle_label

    results = search_object(f"#{vehicle_id}")
    if not results:
        return
    vehicle = results[0]
    vehicle.db.security_alarm_active = False
    room = vehicle.location
    if room:
        room.msg_contents(f"|x{vehicle_label(vehicle)}'s alarm falls silent.|n")


def attempt_break_in(character, vehicle):
    from world.vehicle_parts import get_part_condition

    if not getattr(vehicle.db, "security_locked", False):
        return False, "It's not locked."
    if getattr(vehicle.db, "security_hotwired", False):
        return False, "Security is already bypassed."
    lockout = float(getattr(vehicle.db, "security_lockout_until", 0) or 0)
    if lockout > time.time():
        remaining = int(lockout - time.time())
        return False, f"Security lockout active. Try again in {remaining} seconds."
    probe = _find_bypass_probe(character)
    if not probe:
        return False, "You need a bypass probe. You can't do this with your bare hands."
    tier = effective_security_tier(vehicle)
    tier_data = SECURITY_TIERS.get(tier, SECURITY_TIERS[1])
    probe_max = int(getattr(probe.db, "bypass_max_tier", 1) or 1)
    if tier > probe_max:
        return False, f"Your probe can't handle this security system. You need better hardware."
    uses = int(getattr(probe.db, "bypass_uses_remaining", 1) or 1)
    if uses <= 1:
        probe.delete()
        character.msg("|xYour bypass probe burns out on the last use.|n")
    else:
        probe.db.bypass_uses_remaining = uses - 1
    difficulty = tier_data["break_in_difficulty"]
    probe_bonus = int(getattr(probe.db, "bypass_bonus", 0) or 0)
    sec_condition = get_part_condition(vehicle, "security") / 100.0
    condition_reduction = int((1.0 - sec_condition) * 15)
    effective_difficulty = max(5, difficulty - probe_bonus - condition_reduction)
    tier_result, _ = character.roll_check(
        ["intelligence", "perception"], "electrical_engineering", difficulty=effective_difficulty
    )
    if tier_result in ("Critical Success", "Full Success"):
        vehicle.db.security_locked = False
        vehicle.db.security_failed_attempts = 0
        return True, ""
    fails = int(getattr(vehicle.db, "security_failed_attempts", 0) or 0) + 1
    vehicle.db.security_failed_attempts = fails
    max_fails = tier_data.get("lockout_after_fails", 10)
    if fails >= max_fails:
        lockout_dur = tier_data.get("lockout_duration", 60)
        vehicle.db.security_lockout_until = time.time() + lockout_dur
        vehicle.db.security_failed_attempts = 0
        if tier_data.get("has_alarm"):
            _trigger_alarm(vehicle, character)
        return False, f"The security system locks you out. {lockout_dur} second lockout."
    if tier_data.get("has_alarm") and tier_result == "Failure":
        _trigger_alarm(vehicle, character)
    if tier_result == "Marginal Success":
        return False, "Almost. The signal almost takes. Almost isn't enough."
    return False, "The probe flickers. The scanner rejects the signal."


def attempt_hotwire(character, vehicle):
    from world.vehicle_parts import damage_part, get_part_condition

    if getattr(vehicle.db, "security_locked", False):
        return False, "The vehicle is still locked. Break in first."
    if getattr(vehicle.db, "security_hotwired", False):
        return False, "Already hotwired."
    if getattr(vehicle.db, "engine_running", False):
        return False, "The engine is already running."
    kit = _find_splice_kit(character)
    if not kit:
        return False, "You need a splice kit. Wire strippers at minimum."
    tier = effective_security_tier(vehicle)
    tier_data = SECURITY_TIERS.get(tier, SECURITY_TIERS[1])
    kit_max = int(getattr(kit.db, "splice_max_tier", 1) or 1)
    if tier > kit_max:
        return False, f"Your kit can't handle this security system. You need better hardware."
    uses = int(getattr(kit.db, "splice_uses_remaining", 1) or 1)
    if uses <= 1:
        kit.delete()
        character.msg("|xYour splice kit gives out on the last attempt.|n")
    else:
        kit.db.splice_uses_remaining = uses - 1
    checks_required = tier_data.get("hotwire_checks_required", 1)
    difficulty = tier_data["hotwire_difficulty"]
    kit_bonus = int(getattr(kit.db, "splice_bonus", 0) or 0)
    sec_condition = get_part_condition(vehicle, "security") / 100.0
    condition_reduction = int((1.0 - sec_condition) * 10)
    effective_difficulty = max(5, difficulty - kit_bonus - condition_reduction)
    successes = 0
    for check_num in range(checks_required):
        check_diff = effective_difficulty + (check_num * 3)
        tier_result, _ = character.roll_check(
            ["intelligence", "perception"], "electrical_engineering", difficulty=check_diff
        )
        if tier_result in ("Critical Success", "Full Success"):
            successes += 1
        elif tier_result == "Marginal Success" and check_num == 0:
            successes += 1
        else:
            break
    if successes >= checks_required:
        from world.vehicle_parts import can_start_engine

        ok_fuel, err_fuel = can_start_engine(vehicle)
        if not ok_fuel:
            return False, err_fuel
        vehicle.db.security_hotwired = True
        vehicle.db.engine_running = True
        return True, ""
    if tier_data.get("has_immobilizer") and successes == 0:
        damage_part(vehicle, "wiring", 15)
        character.msg("|rThe immobilizer fires. Wiring damage.|n")
    if tier_data.get("has_alarm"):
        _trigger_alarm(vehicle, character)
    return False, f"You got {successes}/{checks_required} handshakes. Not enough."


def resolve_recog_to_character(caller, name_key: str):
    name_key = (name_key or "").strip().lower()
    if not name_key:
        return None

    try:
        from world.rp_features import RecogHandler
        recog_map = RecogHandler(caller).all()  # {recog_string: character_obj}
    except Exception:
        return None

    # Exact match first, then prefix.
    for rname, char_obj in recog_map.items():
        if (rname or "").strip().lower() == name_key:
            return char_obj
    for rname, char_obj in recog_map.items():
        if (rname or "").strip().lower().startswith(name_key):
            return char_obj

    return None
