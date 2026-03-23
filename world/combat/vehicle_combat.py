"""
Vehicle damage routing, destruction, and combat helpers.
"""

from __future__ import annotations

import random
import time
from typing import Any

ARMOR_EFFECTIVENESS = {
    "kinetic": 1.0,
    "explosive": 0.6,
    "fire": 0.3,
    "electric": 0.2,
    "ram": 0.8,
    "none": 0.0,
}

VEHICLE_BASE_HP = {
    "ground": 100,
    "motorcycle": 40,
    "aerial": 80,
}

VEHICLE_MOUNT_CONFIGS = {
    "motorcycle": {"max_mounts": 1, "mount_types": ["fixed_forward"]},
    "ground": {"max_mounts": 3, "mount_types": ["fixed_forward", "turret", "rear"]},
    "aerial": {"max_mounts": 4, "mount_types": ["fixed_forward", "turret", "underbelly", "rear"]},
}


def _is_vehicle(obj) -> bool:
    try:
        from typeclasses.vehicles import Vehicle

        return isinstance(obj, Vehicle)
    except ImportError:
        return False


def vehicle_label(vehicle):
    try:
        from typeclasses.vehicles import vehicle_label as vl

        return vl(vehicle)
    except ImportError:
        return getattr(vehicle, "key", None) or "vehicle"


def get_enclosed_vehicle_hull_for_crew(character):
    """
    Enclosed cabin crew: foot attacks from outside resolve against this vehicle hull.
    Motorcycle riders are excluded (they are in the room and take personal hits).
    """
    if not character or not getattr(character, "db", None):
        return None
    try:
        from typeclasses.vehicles import Vehicle
    except ImportError:
        return None
    v = getattr(character.db, "in_vehicle", None)
    if not v or not isinstance(v, Vehicle) or getattr(v.db, "vehicle_destroyed", False):
        return None
    if getattr(v.db, "vehicle_type", None) == "motorcycle":
        return None
    if not getattr(v.db, "has_interior", True):
        return None
    return v


def get_vehicle_hull_target_for_crew(character):
    """
    Vehicle object associated with this character for hull-related logic:
    enclosed cabin vehicle, or motorcycle when mounted (rider exposed).
    Combat foot routing uses get_enclosed_vehicle_hull_for_crew only.
    """
    enc = get_enclosed_vehicle_hull_for_crew(character)
    if enc:
        return enc
    try:
        from typeclasses.vehicles import Motorcycle
    except ImportError:
        return None
    bike = getattr(character.db, "mounted_on", None)
    if bike and isinstance(bike, Motorcycle) and not getattr(bike.db, "vehicle_destroyed", False):
        return bike
    return None


def _random_part_damage(vehicle, damage_dealt: int) -> None:
    from world.vehicle_parts import damage_part, get_part_ids

    parts = get_part_ids(vehicle)
    if not parts:
        return
    if random.random() > 0.6:
        return
    target_part = random.choice(parts)
    collateral = max(1, damage_dealt // 4)
    damage_part(vehicle, target_part, collateral)


def _shock_occupants(vehicle, hit_damage: int) -> None:
    """Large hull hits throw occupants; light damage + messaging."""
    shock = max(1, int(hit_damage) // 5)
    if getattr(vehicle.db, "vehicle_type", None) == "motorcycle":
        rider = getattr(vehicle.db, "rider", None)
        if rider:
            rider.msg("|rThe impact jolts through the frame.|n")
            if hasattr(rider, "at_damage"):
                rider.at_damage(None, shock, weapon_key="shock")
        return
    interior = getattr(vehicle.db, "interior", None)
    if interior and hasattr(interior, "msg_contents"):
        interior.msg_contents("|rThe vehicle shudders from the impact. You're thrown against your seat.|n")
        try:
            chars = interior.contents_get(content_type="character")
        except Exception:
            chars = [c for c in interior.contents or [] if c]
        for char in chars or []:
            if hasattr(char, "at_damage"):
                char.at_damage(None, shock, weapon_key="shock")


def vehicle_drive_movement_blocked(vehicle) -> str | None:
    """Return user-facing message if drive/fly leg cannot start (spin-out)."""
    spun = float(getattr(vehicle.db, "spun_out_until", 0) or 0)
    if spun > time.time():
        return f"You're still recovering from the spin. {int(spun - time.time())}s."
    return None


def apply_vehicle_damage(vehicle, raw_damage: int, damage_type: str = "kinetic", armor_piercing: bool = False) -> int:
    """
    Apply damage to vehicle hull. Armor reduces incoming damage.
    Returns actual damage dealt to HP after armor (0 if fully absorbed).
    """
    if not vehicle or not getattr(vehicle, "db", None):
        return 0
    if getattr(vehicle.db, "vehicle_destroyed", False):
        return 0

    armor = int(getattr(vehicle.db, "vehicle_armor", 0) or 0)
    armor_mult = float(ARMOR_EFFECTIVENESS.get(damage_type, 1.0))
    effective_armor = int(armor * armor_mult)
    if armor_piercing:
        effective_armor = int(effective_armor * 0.5)

    actual = max(0, int(raw_damage) - effective_armor)
    if actual <= 0:
        return 0

    current_hp = int(getattr(vehicle.db, "vehicle_hp", 100) or 100)
    new_hp = max(0, current_hp - actual)
    vehicle.db.vehicle_hp = new_hp

    _random_part_damage(vehicle, int(raw_damage))

    max_hp = int(getattr(vehicle.db, "vehicle_max_hp", 100) or 100)
    if max_hp > 0 and actual > max_hp * 0.2:
        _shock_occupants(vehicle, actual)

    if new_hp <= 0 and not getattr(vehicle.db, "vehicle_destroyed", False):
        _vehicle_destruction(vehicle)

    return actual


def _vehicle_destruction(vehicle) -> None:
    from typeclasses.vehicles import vehicle_label as vl

    vehicle.db.vehicle_destroyed = True
    try:
        vehicle.stop_engine()
    except Exception:
        vehicle.db.engine_running = False

    name = vl(vehicle)
    room = vehicle.location

    if room:
        room.msg_contents(
            f"|R{name} buckles, shudders, and dies. Smoke pours from the wreck. Something structural has given way.|n"
        )

    if getattr(vehicle.db, "vehicle_type", None) == "motorcycle":
        rider = getattr(vehicle.db, "rider", None)
        if rider:
            try:
                from world.vehicle_mounts import force_dismount

                force_dismount(rider, vehicle, reason="destruction")
            except Exception:
                rider.db.mounted_on = None
                vehicle.db.rider = None
                vehicle.db.driver = None
            rider.msg("|rThe bike comes apart beneath you. You hit the ground.|n")
            if hasattr(rider, "at_damage"):
                rider.at_damage(None, 25, weapon_key="crash")
    elif getattr(vehicle.db, "has_interior", True) and vehicle.db.interior:
        interior = vehicle.db.interior
        interior.msg_contents(
            "|RThe vehicle is destroyed. Metal screams. Glass shatters. You need to get out. Now.|n"
        )
        if hasattr(interior, "contents_get"):
            for char in interior.contents_get(content_type="character"):
                if hasattr(char, "at_damage"):
                    char.at_damage(None, 15, weapon_key="crash")

    vehicle.db.desc = (
        f"The burned-out wreck of what was once {name}. The frame is twisted. "
        f"The panels are scorched and buckled. Nothing here works anymore. "
        f"Parts might be salvageable. The vehicle isn't."
    )
    vehicle.key = f"wreck of {vehicle.key}"


def init_vehicle_hp_for_type(vehicle) -> None:
    """Set default HP from vehicle type if not already set."""
    vt = getattr(vehicle.db, "vehicle_type", None) or "ground"
    base = int(VEHICLE_BASE_HP.get(vt, 100))
    if getattr(vehicle.db, "vehicle_max_hp", None) is None:
        vehicle.db.vehicle_max_hp = base
    if getattr(vehicle.db, "vehicle_hp", None) is None:
        vehicle.db.vehicle_hp = int(vehicle.db.vehicle_max_hp)


def apply_fire_dot(vehicle, ticks: int = 3, damage_per_tick: int = 5) -> None:
    vehicle.db.burning_ticks = ticks
    vehicle.db.burning_damage = damage_per_tick


def apply_emp_disable(vehicle) -> None:
    from world.vehicle_parts import damage_part

    try:
        vehicle.stop_engine()
    except Exception:
        vehicle.db.engine_running = False
    damage_part(vehicle, "wiring", 20)
    vehicle.db.emp_disabled_until = time.time() + 30


def apply_suppression_to_character(target, duration: float = 15.0) -> None:
    target.db.suppressed_until = time.time() + duration


PERSONAL_WEAPON_VS_VEHICLE = {
    "unarmed": 0.02,
    "short_blades": 0.05,
    "long_blades": 0.08,
    "blunt_weaponry": 0.15,
    "sidearms": 0.20,
    "longarms": 0.35,
    "automatics": 0.30,
}

PERSONAL_WEAPON_VS_MOTORCYCLE = {
    "unarmed": 0.05,
    "short_blades": 0.10,
    "long_blades": 0.15,
    "blunt_weaponry": 0.25,
    "sidearms": 0.35,
    "longarms": 0.50,
    "automatics": 0.45,
}

VEHICLE_ATTACK_MESSAGES = {
    "unarmed": {
        "hit": "{attacker} punches the {vehicle}. The panel dents. Barely.",
        "miss": "{attacker} swings at the {vehicle} and accomplishes nothing.",
    },
    "short_blades": {
        "hit": "{attacker} drags a blade across {vehicle}'s bodywork. The steel shrieks.",
        "miss": "{attacker} stabs at {vehicle}. The blade skids off the panel.",
    },
    "blunt_weaponry": {
        "hit": "{attacker} brings a heavy swing against {vehicle}. The impact crumples metal.",
        "miss": "{attacker} swings at {vehicle} and misses the sweet spot.",
    },
    "sidearms": {
        "hit": "A gunshot punches through {vehicle}'s panel. Sparks inside.",
        "miss": "A shot ricochets off {vehicle}'s frame.",
    },
    "longarms": {
        "hit": "A rifle round tears through {vehicle}'s bodywork. Exit hole on the far side.",
        "miss": "A rifle crack. The round sparks off {vehicle}'s armor plating.",
    },
    "automatics": {
        "hit": "A burst stitches across {vehicle}'s panels. Glass shatters. Metal screams.",
        "miss": "Rounds pepper the ground around {vehicle}. Near misses.",
    },
    "long_blades": {
        "hit": "{attacker} hacks at {vehicle}'s bodywork. The blade bites metal — sparks and a long gouge.",
        "miss": "{attacker} sweeps a long blade at {vehicle}. The edge skates off armor with a shower of sparks.",
    },
}


def _msg_templates_for_skill(attack_skill: str) -> dict:
    return VEHICLE_ATTACK_MESSAGES.get(
        attack_skill,
        VEHICLE_ATTACK_MESSAGES.get("unarmed", {"hit": "{attacker} hits {vehicle}.", "miss": "{attacker} misses {vehicle}."}),
    )


def resolve_aimed_vehicle_part(vehicle, raw: str | None):
    if not raw or not vehicle:
        return None
    from world.vehicle_parts import get_part_display_name, get_part_ids

    r = raw.lower().strip().replace(" ", "_")
    valid_parts = get_part_ids(vehicle)
    if r in valid_parts:
        return r
    for pid in valid_parts:
        if r in pid or pid in r:
            return pid
    for pid in valid_parts:
        display = get_part_display_name(pid).lower().replace(" ", "_")
        if r in display or display in r:
            return pid
    return None


def execute_on_foot_vs_vehicle_turn(attacker, vehicle, weapon_key: str, wielded_obj, aimed_part: str | None = None) -> None:
    """Resolve one combat tick vs a vehicle (roll_check tiers)."""
    from world.skills import SKILL_STATS, WEAPON_KEY_TO_SKILL
    from world.combat.room_size import get_room_size_modifier
    from world.combat.weapons import get_weapon_class_for_room_mod
    from world.combat.utils import combat_role_name, combat_msg
    from world.vehicle_parts import damage_part

    attack_skill = WEAPON_KEY_TO_SKILL.get(weapon_key, "unarmed")
    attack_stats = SKILL_STATS.get(attack_skill, ["strength", "agility"])
    room = getattr(attacker, "location", None)
    wc = get_weapon_class_for_room_mod(weapon_key)
    room_mod = int(get_room_size_modifier(room, wc))

    base_damage = 10
    if wielded_obj and getattr(wielded_obj, "db", None):
        base_damage = int(getattr(wielded_obj.db, "damage", None) or base_damage)

    vtype = getattr(vehicle.db, "vehicle_type", None) or "ground"
    mult_table = PERSONAL_WEAPON_VS_MOTORCYCLE if vtype == "motorcycle" else PERSONAL_WEAPON_VS_VEHICLE
    mult = float(mult_table.get(attack_skill, 0.1))

    vname = vehicle_label(vehicle)
    tpl = _msg_templates_for_skill(attack_skill)

    from world.combat.utils import combat_display_name as _cdn

    def _notify_vehicle_crew(build) -> None:
        """Send a per-occupant message to all crew inside the vehicle's interior.

        `build(occ, atk_name)` receives the occupant and the attacker's name as seen
        by that occupant (via the recog system), and returns the message string.
        """
        interior = getattr(vehicle.db, "interior", None)
        if not interior or not hasattr(interior, "contents_get"):
            return
        for occ in interior.contents_get(content_type="character"):
            atk_name = combat_role_name(attacker, occ, role="attacker")
            combat_msg(occ, build(occ, atk_name))

    if aimed_part:
        pid = resolve_aimed_vehicle_part(vehicle, aimed_part)
        if not pid:
            combat_msg(attacker, f"You can't find a part called '{aimed_part}' on that vehicle.")
            return
        diff = 25 + (10 if pid in ("engine", "wiring", "turbines", "fuel_pump", "fuel_injectors") else 0)
        tier, _roll = attacker.roll_check(attack_stats, attack_skill, difficulty=diff, modifier=room_mod)
        if tier in ("Critical Success", "Full Success"):
            damage_part(vehicle, pid, base_damage)
            combat_msg(attacker, f"|yYou land a precise hit on {vname}'s {pid.replace('_', ' ')}.|n")
            loc = vehicle.location
            if loc and hasattr(loc, "contents_get"):
                for v in loc.contents_get(content_type="character"):
                    if v != attacker:
                        atk_v = combat_role_name(attacker, v, role="attacker")
                        combat_msg(v, f"{atk_v} strikes a vulnerable point on {vname}.")
            _notify_vehicle_crew(
                lambda occ, atk_name, _pid=pid: f"|r{atk_name} lands a precise hit on the {_pid.replace('_', ' ')}. The vehicle shudders.|n"
            )
        else:
            combat_msg(attacker, "|rYour aimed shot fails to connect.|n")
        return

    tier, _roll = attacker.roll_check(attack_stats, attack_skill, modifier=room_mod)
    if tier in ("Critical Success", "Full Success", "Marginal Success"):
        vehicle_damage = max(0, int(base_damage * mult))
        actual = apply_vehicle_damage(vehicle, vehicle_damage)
        if actual <= 0:
            combat_msg(attacker, f"|xYour strike bounces off {vname}'s armor.|n")
            _notify_vehicle_crew(
                lambda occ, atk_name: f"|x{atk_name} strikes the hull — glances off the armor. No damage.|n"
            )
            return
        hit_txt = tpl.get("hit", "").format(attacker="You", vehicle=vname)
        combat_msg(attacker, f"|yYou strike {vname} — structural damage ({actual}).|n {hit_txt}")
        loc = vehicle.location
        if loc and hasattr(loc, "contents_get"):
            for v in loc.contents_get(content_type="character"):
                if v != attacker:
                    atk_v = combat_role_name(attacker, v, role="attacker")
                    combat_msg(v, f"{atk_v} attacks {vname}.")
        _notify_vehicle_crew(
            lambda occ, atk_name, _dmg=actual: f"|r{atk_name} hits the vehicle. Structural damage: {_dmg}.|n"
        )
    else:
        miss_txt = tpl.get("miss", "").format(attacker="You", vehicle=vname)
        combat_msg(attacker, f"|rGlancing blow — no meaningful damage.|n {miss_txt}")
        _notify_vehicle_crew(
            lambda occ, atk_name: f"|x{atk_name} strikes the hull — glancing blow, no real damage.|n"
        )


WEAPON_INSTALL_DIFFICULTY = {
    "fixed_forward": 20,
    "turret": 30,
    "rear": 20,
    "underbelly": 35,
}

WEAPON_INSTALL_DURATION = {
    "fixed_forward": 30,
    "turret": 45,
    "rear": 25,
    "underbelly": 50,
}


def _get_mount_type(vehicle, mount_id: str) -> str:
    meta = getattr(vehicle.db, "weapon_mount_types", None) or {}
    return str(meta.get(mount_id, "fixed_forward"))


def is_crew_in_enclosed_vehicle(character) -> bool:
    """
    Return True if the character is seated as driver or gunner inside an enclosed (non-motorcycle)
    vehicle.  Used to block fist/melee fallback when no vehicle weapon is available.
    """
    if not character or not getattr(character, "db", None):
        return False
    try:
        from typeclasses.vehicles import Motorcycle, Vehicle
    except ImportError:
        return False
    if getattr(character.db, "mounted_on", None):
        return False
    v = getattr(character.db, "in_vehicle", None)
    if not v or not isinstance(v, Vehicle) or isinstance(v, Motorcycle):
        return False
    is_driver = getattr(v.db, "driver", None) == character
    is_gunner = getattr(v.db, "gunner", None) == character
    return is_driver or is_gunner


def can_fire_mount(character, vehicle, mount_id: str) -> bool:
    mtype = _get_mount_type(vehicle, mount_id)
    if mtype == "fixed_forward":
        return character == getattr(vehicle.db, "driver", None) or character == getattr(vehicle.db, "gunner", None)
    if mtype in ("turret", "rear", "underbelly"):
        return character == getattr(vehicle.db, "gunner", None) and getattr(vehicle.db, "gunner_mount", None) == mount_id
    return False


def get_attacker_vehicle_weapon_context(character):
    """
    If the character can use a mounted, non-deployable weapon for `attack` (same combat ticker),
    return (vehicle, mount_id, weapon, mount_type_str). Otherwise None (use normal melee/ranged).
    """
    if not character or not getattr(character, "db", None):
        return None
    try:
        from typeclasses.vehicles import Vehicle, Motorcycle
    except ImportError:
        return None

    vehicle = None
    is_driver = False
    is_gunner = False
    is_rider = False

    bike = getattr(character.db, "mounted_on", None)
    if bike and isinstance(bike, Motorcycle):
        vehicle = bike
        is_driver = True
        is_rider = True
    else:
        v = getattr(character.db, "in_vehicle", None)
        if not v or not isinstance(v, Vehicle):
            return None
        vehicle = v
        is_driver = getattr(v.db, "driver", None) == character
        is_gunner = getattr(v.db, "gunner", None) == character
        if not is_driver and not is_gunner:
            return None

    mounts = getattr(vehicle.db, "weapon_mounts", None) or {}
    if not mounts:
        return None

    if is_gunner and not is_rider:
        gm = getattr(vehicle.db, "gunner_mount", None)
        if gm:
            w = mounts.get(gm)
            if (
                w
                and not is_deployable_weapon(w)
                and can_fire_mount(character, vehicle, gm)
            ):
                return vehicle, gm, w, _get_mount_type(vehicle, gm)
        # gunner_mount points to a non-existent or empty mount — scan all mounts for one
        # the gunner can fire (handles stale DB state or misconfigured mount IDs).
        # We skip can_fire_mount here because it also checks gunner_mount == mount_id,
        # which is the very mismatch we're recovering from.
        for mid in sorted(mounts.keys()):
            w = mounts.get(mid)
            if not w or is_deployable_weapon(w):
                continue
            mtype = _get_mount_type(vehicle, mid)
            if mtype in ("turret", "rear", "underbelly"):
                return vehicle, mid, w, mtype
        return None

    # Driver or motorcycle rider: first mount the character may fire that has a direct-fire weapon
    for mid in sorted(mounts.keys()):
        w = mounts.get(mid)
        if not w or is_deployable_weapon(w):
            continue
        if not can_fire_mount(character, vehicle, mid):
            continue
        return vehicle, mid, w, _get_mount_type(vehicle, mid)
    return None


def resolve_vehicle_weapon_attack(attacker_char, attacker_vehicle, weapon, target, mount_type: str):
    """Returns (hit: bool, tier_or_result, damage_or_0, damage_type_str or status message)."""
    last_fired = float(getattr(weapon.db, "last_fired", 0) or 0)
    fire_rate = int(getattr(weapon.db, "fire_rate", 1) or 1)
    cooldown = max(2.0, 5.0 - (fire_rate * 0.5))
    now = time.time()
    if now - last_fired < cooldown:
        remaining = cooldown - (now - last_fired)
        return False, "cooldown", 0, f"Weapon cycling. {remaining:.0f}s."

    cap = int(getattr(weapon.db, "ammo_capacity", 0) or 0)
    shots = fire_rate
    if cap > 0:
        current_ammo = int(getattr(weapon.db, "ammo_current", 0) or 0)
        if current_ammo <= 0:
            return False, "empty", 0, ""
        shots = min(current_ammo, fire_rate)
        weapon.db.ammo_current = current_ammo - shots

    vtype = getattr(attacker_vehicle.db, "vehicle_type", None) or "ground"
    if mount_type == "fixed_forward":
        skill = "piloting" if vtype == "aerial" else "driving"
        stats = ["agility", "intelligence"]
    else:
        skill = "gunnery"
        stats = ["agility", "intelligence"]

    weapon_accuracy = int(getattr(weapon.db, "accuracy", 0) or 0)
    cond = float(getattr(weapon.db, "weapon_condition", 100) or 100) / 100.0
    condition_mod = int((cond - 1.0) * 20)
    room = getattr(attacker_vehicle, "location", None)
    smoke_pen = 0
    if room and getattr(room, "db", None):
        smoke_until = float(getattr(room.db, "smoke_until", 0) or 0)
        if smoke_until > time.time():
            smoke_pen = -15
    total_attack_mod = weapon_accuracy + condition_mod + smoke_pen

    if _is_vehicle(target):
        hit, tier, dmg, dtype = _resolve_vw_vs_vehicle(
            attacker_char, attacker_vehicle, weapon, target, skill, stats, total_attack_mod
        )
    else:
        hit, tier, dmg, dtype = _resolve_vw_vs_pedestrian(
            attacker_char, attacker_vehicle, weapon, target, skill, stats, total_attack_mod
        )

    weapon.db.last_fired = time.time()
    wear = float(getattr(weapon.db, "wear_per_shot", 0) or 0) * shots
    if wear > 0:
        wcond = float(getattr(weapon.db, "weapon_condition", 100) or 100)
        weapon.db.weapon_condition = max(0.0, wcond - wear)

    return hit, tier, dmg, dtype


def _resolve_vw_vs_vehicle(attacker_char, attacker_vehicle, weapon, target_vehicle, skill: str, stats: list, attack_mod: int):
    tier, attack_roll = attacker_char.roll_check(stats, skill, modifier=attack_mod)
    target_driver = getattr(target_vehicle.db, "driver", None)
    if target_driver:
        def_skill = "piloting" if getattr(target_vehicle.db, "vehicle_type", None) == "aerial" else "driving"
        _, defense_roll = target_driver.roll_check(["agility", "perception"], def_skill)
    else:
        defense_roll = 0
    hit = attack_roll > defense_roll

    if not hit:
        return False, tier, 0, ""

    base_damage = int(getattr(weapon.db, "damage", 10) or 10)
    damage_type = getattr(weapon.db, "damage_type", "kinetic") or "kinetic"
    ap = "armor_piercing" in (getattr(weapon.db, "special", None) or [])

    bonus_part_damage = 0
    if tier == "Critical Success":
        bonus_part_damage = base_damage // 2

    actual = apply_vehicle_damage(target_vehicle, base_damage, damage_type, armor_piercing=ap)
    if bonus_part_damage > 0:
        _random_part_damage(target_vehicle, bonus_part_damage)

    return True, tier, actual, damage_type


def _resolve_vw_vs_pedestrian(attacker_char, attacker_vehicle, weapon, target, skill: str, stats: list, attack_mod: int):
    ap_mod = int(getattr(weapon.db, "anti_personnel_mod", 0) or 0)
    total_mod = attack_mod + ap_mod
    tier, attack_roll = attacker_char.roll_check(stats, skill, modifier=total_mod)
    _, defense_roll = target.roll_check(["agility", "perception"], "evasion")
    hit = attack_roll > defense_roll
    if hit:
        base_damage = int(getattr(weapon.db, "personnel_damage", None) or getattr(weapon.db, "damage", 10) or 10)
        return True, tier, base_damage, getattr(weapon.db, "damage_type", "kinetic") or "kinetic"
    return False, tier, 0, ""


def _second_person_pedestrian_fire_line(msg: str) -> str:
    """When {target} was replaced with 'you', fix third-person verb agreement in weapon templates."""
    s = msg
    for bad, good in (
        ("you ducks", "you duck"),
        ("You ducks", "You duck"),
        ("you runs", "you run"),
        ("You runs", "You run"),
        ("you swerves", "you swerve"),
        ("You swerves", "You swerve"),
    ):
        s = s.replace(bad, good)
    return s


def announce_vehicle_attack(room, attacker_vehicle, target, weapon, hit: bool, tier: str) -> None:
    if not room:
        return
    from world.combat.utils import combat_display_name, combat_msg

    weapon_name = getattr(weapon.db, "weapon_name", None) or "weapon"
    av_name = vehicle_label(attacker_vehicle)
    if hit:
        if tier == "Critical Success":
            msg_template = getattr(weapon.db, "fire_message_crit", None) or getattr(weapon.db, "fire_crit", "")
        else:
            msg_template = getattr(weapon.db, "fire_message_hit", None) or getattr(weapon.db, "fire_hit", "")
    else:
        msg_template = getattr(weapon.db, "fire_message_miss", None) or getattr(weapon.db, "fire_miss", "")

    drv = getattr(attacker_vehicle.db, "driver", None)

    if not hasattr(room, "contents_get"):
        return
    viewers = room.contents_get(content_type="character") or []
    base_template = msg_template
    for viewer in viewers:
        viewer_is_ped_target = not _is_vehicle(target) and viewer == target
        if viewer_is_ped_target:
            tgt = "you"
        else:
            tgt = vehicle_label(target) if _is_vehicle(target) else combat_display_name(target, viewer)
        tpl = base_template
        if not tpl:
            tpl = f"{av_name}'s {weapon_name} hits {tgt}." if hit else f"{av_name}'s {weapon_name} misses {tgt}."
        atk_disp = combat_display_name(drv, viewer) if drv else "someone"
        try:
            msg = tpl.format(
                attacker_vehicle=av_name,
                target=tgt,
                attacker=atk_disp,
            )
        except Exception:
            msg = tpl
        if viewer_is_ped_target:
            msg = _second_person_pedestrian_fire_line(msg)
        combat_msg(viewer, f"|R{msg}|n")

    # Send the fire announcement to crew inside the attacker vehicle (they are in the interior room,
    # not the exterior room, so the loop above misses them).
    interior = getattr(attacker_vehicle.db, "interior", None)
    if interior and hasattr(interior, "contents_get"):
        tgt_name = vehicle_label(target) if _is_vehicle(target) else (
            combat_display_name(target, drv) if drv else vehicle_label(target) if _is_vehicle(target) else getattr(target, "key", "target")
        )
        tpl_crew = base_template
        if not tpl_crew:
            tpl_crew = f"{av_name}'s {weapon_name} hits {tgt_name}." if hit else f"{av_name}'s {weapon_name} misses {tgt_name}."
        try:
            crew_msg = tpl_crew.format(
                attacker_vehicle=av_name,
                target=tgt_name,
                attacker="You" if drv else "someone",
            )
        except Exception:
            crew_msg = tpl_crew
        for occ in interior.contents_get(content_type="character"):
            combat_msg(occ, f"|R{crew_msg}|n")


def resolve_ram(attacker_vehicle, attacker_driver, target):
    """Ram vehicle or pedestrian. Returns (success: bool, kind: str)."""
    if not attacker_driver or not attacker_vehicle:
        return False, "miss"
    last_ram = float(getattr(attacker_vehicle.db, "last_ram", 0) or 0)
    if time.time() - last_ram < 10:
        return False, "recovery"
    tier, roll = attacker_driver.roll_check(["agility", "intelligence"], "driving", difficulty=15)
    if _is_vehicle(target):
        target_driver = getattr(target.db, "driver", None)
        if target_driver:
            _, defense = target_driver.roll_check(["agility", "perception"], "driving")
        else:
            defense = 0
        if roll <= defense:
            return False, "miss"
        speed_damage = {"slow": 15, "normal": 25, "fast": 35}
        base = speed_damage.get(getattr(attacker_vehicle.db, "speed_class", None) or "normal", 25)
        target_actual = apply_vehicle_damage(target, base, "ram")
        has_plow = _has_weapon_type_installed(attacker_vehicle, "ram_plow")
        attacker_reduction = 0.3 if has_plow else 0.7
        attacker_damage = int(base * attacker_reduction)
        apply_vehicle_damage(attacker_vehicle, attacker_damage, "ram")
        attacker_vehicle.db.last_ram = time.time()
        return True, "vehicle"
    _, defense = target.roll_check(["agility", "perception"], "evasion")
    if roll <= defense:
        return False, "miss"
    speed_damage = {"slow": 20, "normal": 35, "fast": 50}
    damage = speed_damage.get(getattr(attacker_vehicle.db, "speed_class", None) or "normal", 35)
    if hasattr(target, "at_damage"):
        target.at_damage(None, damage, weapon_key="ram")
    apply_vehicle_damage(attacker_vehicle, 5, "ram")
    attacker_vehicle.db.last_ram = time.time()
    return True, "pedestrian"


def _has_weapon_type_installed(vehicle, wkey: str) -> bool:
    mounts = getattr(vehicle.db, "weapon_mounts", None) or {}
    for w in mounts.values():
        if w and getattr(w.db, "weapon_key", None) == wkey:
            return True
    return False


def apply_tether(attacker_vehicle, target_vehicle) -> None:
    attacker_vehicle.db.tethered_to = target_vehicle.id
    target_vehicle.db.tethered_by = attacker_vehicle.id


def deploy_smoke(vehicle, room) -> None:
    if not room or not getattr(room, "db", None):
        return
    room.db.smoke_until = time.time() + 60
    lab = vehicle_label(vehicle)
    room.msg_contents(f"|xThick smoke billows from {lab}. Visibility drops to nothing.|n")


def apply_splash_damage(room, source_vehicle, base_damage: int, damage_type: str) -> None:
    splash = max(1, int(base_damage) // 3)
    for obj in list(room.contents or []):
        if obj == source_vehicle:
            continue
        if _is_vehicle(obj):
            apply_vehicle_damage(obj, splash, damage_type)
        elif hasattr(obj, "at_damage"):
            obj.at_damage(None, splash // 2, weapon_key="explosion")


DEPLOYABLE_SPECIALS = frozenset(
    {"deployable_mine", "deployable_caltrops", "deployable_oil", "smoke_screen", "area_denial"}
)
DEPLOY_WEAPON_KEYS = frozenset({"mine_dropper", "caltrops", "smoke_launcher", "oil_sprayer"})


def is_deployable_weapon(weapon) -> bool:
    wk = getattr(weapon.db, "weapon_key", None) or getattr(weapon.db, "key", None)
    if wk in DEPLOY_WEAPON_KEYS:
        return True
    specials = set(getattr(weapon.db, "special", None) or [])
    overlap = specials & DEPLOYABLE_SPECIALS
    if not overlap:
        return False
    # Napalm etc.: area_denial plus direct-fire specials — use normal fire resolution.
    if specials - DEPLOYABLE_SPECIALS:
        return False
    return True


def _msg_vehicle(vehicle, message: str) -> None:
    if getattr(vehicle.db, "vehicle_type", None) == "motorcycle":
        rider = getattr(vehicle.db, "rider", None)
        if rider:
            rider.msg(message)
        return
    interior = getattr(vehicle.db, "interior", None)
    if interior and hasattr(interior, "msg_contents"):
        interior.msg_contents(message)


def _deploy_mine(vehicle, room, weapon) -> None:
    from evennia.utils.create import create_object

    mine = create_object(
        "typeclasses.objects.Object",
        key="contact mine",
        location=room,
    )
    mine.db.is_mine = True
    mine.db.mine_damage = int(getattr(weapon.db, "damage", None) or 40)
    mine.db.mine_damage_type = getattr(weapon.db, "damage_type", None) or "explosive"
    mine.db.deployed_by = vehicle.id
    mine.db.desc = "A squat metal disc on the road surface. The pressure plate is armed."


def deploy_weapon(character, vehicle, weapon, mount_id: str):
    """
    Room-effect deployables (mines, caltrops, oil, smoke, area denial).
    Returns (ok: bool, message: str).
    """
    room = getattr(vehicle, "location", None)
    if not room:
        return False, "Nowhere to deploy."

    cap = int(getattr(weapon.db, "ammo_capacity", 0) or 0)
    if cap > 0:
        current = int(getattr(weapon.db, "ammo_current", 0) or 0)
        if current <= 0:
            return False, "Empty."
        weapon.db.ammo_current = current - 1

    wear = float(getattr(weapon.db, "wear_per_shot", 0) or 0)
    if wear > 0:
        wcond = float(getattr(weapon.db, "weapon_condition", 100) or 100)
        weapon.db.weapon_condition = max(0.0, wcond - wear)

    weapon.db.last_fired = time.time()

    specials = set(getattr(weapon.db, "special", None) or [])
    lab = vehicle_label(vehicle)

    if "deployable_mine" in specials:
        _deploy_mine(vehicle, room, weapon)
        room.msg_contents(f"|ySomething drops from the back of {lab} and clatters on the road.|n")
        return True, "Mine deployed."

    if "deployable_caltrops" in specials:
        room.db.caltrops_active = True
        room.msg_contents(f"|yCaltrops scatter across the road behind {lab}.|n")
        return True, "Caltrops deployed."

    if "deployable_oil" in specials:
        room.db.oil_slick_until = time.time() + 120
        room.msg_contents(f"|xOil sprays across the road from {lab}. The surface goes slick.|n")
        return True, "Oil deployed."

    if "smoke_screen" in specials:
        deploy_smoke(vehicle, room)
        return True, "Smoke deployed."

    if "area_denial" in specials:
        room.db.fire_zone_until = time.time() + 45
        room.db.fire_zone_damage = int(getattr(weapon.db, "personnel_damage", None) or 10) // 3
        room.msg_contents("|RBurning fuel pools on the ground. The area is a fire zone.|n")
        return True, "Area denial deployed."

    return False, "Unknown deployable."


def check_room_hazards(vehicle, room) -> None:
    """Mines, caltrops, oil slick, fire zone when a vehicle enters a room."""
    if not vehicle or not room or not getattr(room, "db", None):
        return

    mines = [
        o
        for o in list(room.contents or [])
        if getattr(getattr(o, "db", None), "is_mine", False)
        and int(getattr(o.db, "deployed_by", 0) or 0) != int(getattr(vehicle, "id", 0) or 0)
    ]
    if mines:
        mine = mines[0]
        damage = int(getattr(mine.db, "mine_damage", None) or 40)
        dtype = getattr(mine.db, "mine_damage_type", None) or "explosive"
        apply_vehicle_damage(vehicle, damage, dtype)
        room.msg_contents(f"|R{vehicle_label(vehicle)} drives over a mine. BOOM.|n")
        try:
            mine.delete()
        except Exception:
            pass

    if getattr(room.db, "caltrops_active", False):
        driver = getattr(vehicle.db, "driver", None)
        from world.vehicle_parts import damage_part, get_part_ids

        tire_id = None
        for pid in get_part_ids(vehicle):
            if pid in ("tires", "rubber"):
                tire_id = pid
                break
        if tire_id:
            if driver and hasattr(driver, "roll_check"):
                tier, _ = driver.roll_check(["perception", "agility"], "driving", difficulty=15)
                if tier == "Failure":
                    damage_part(vehicle, tire_id, 30)
                    _msg_vehicle(vehicle, "|rCaltrops shred the tires.|n")
                else:
                    _msg_vehicle(vehicle, "|yYou swerve around the caltrops.|n")
            else:
                damage_part(vehicle, tire_id, 30)

    oil_until = float(getattr(room.db, "oil_slick_until", 0) or 0)
    if oil_until > time.time():
        driver = getattr(vehicle.db, "driver", None)
        if driver and hasattr(driver, "roll_check"):
            tier, _ = driver.roll_check(["agility", "perception"], "driving", difficulty=20)
            if tier == "Failure":
                vehicle.db.spun_out_until = time.time() + 5
                _msg_vehicle(vehicle, "|rThe tires hit oil. You spin out.|n")
                room.msg_contents(f"|y{vehicle_label(vehicle)} hits the oil slick and spins!|n")
        else:
            vehicle.db.spun_out_until = time.time() + 5

    fire_until = float(getattr(room.db, "fire_zone_until", 0) or 0)
    if fire_until > time.time():
        fire_dmg = int(getattr(room.db, "fire_zone_damage", None) or 5)
        apply_vehicle_damage(vehicle, fire_dmg, "fire")
        _msg_vehicle(vehicle, "|RYou drive through fire. The heat is immediate.|n")


def _apply_vehicle_entangle(target_vehicle) -> None:
    target_vehicle.db.entangled_until = time.time() + 30
    _msg_vehicle(target_vehicle, "|yThe net tangles your wheels. Handling compromised.|n")


def _apply_pedestrian_entangle(target) -> None:
    if getattr(target, "db", None):
        target.db.netted_until = time.time() + 20
    if hasattr(target, "msg"):
        target.msg("|rThe net wraps around you. You're tangled.|n")


def _apply_spread_damage(room, source_vehicle, primary_target, weapon) -> None:
    extra_damage = int(getattr(weapon.db, "personnel_damage", None) or 10) // 3
    if extra_damage <= 0:
        return
    for obj in list(room.contents or []):
        if obj == source_vehicle or obj == primary_target:
            continue
        if not _is_vehicle(obj) and hasattr(obj, "at_damage"):
            if random.random() < 0.3:
                obj.at_damage(None, extra_damage, weapon_key="shrapnel")
                if hasattr(obj, "msg"):
                    obj.msg("|rShrapnel catches you from the spread.|n")


def _apply_arc_chain(room, source_vehicle, primary_target, chain_damage: int) -> None:
    for obj in list(room.contents or []):
        if obj == source_vehicle or obj == primary_target:
            continue
        if _is_vehicle(obj):
            apply_vehicle_damage(obj, chain_damage, "electric")
            room.msg_contents(f"|cThe arc chains to {vehicle_label(obj)}!|n")
            return
        if hasattr(obj, "db") and getattr(obj.db, "cyberware", None):
            chrome = list(obj.db.cyberware or [])
            if chrome and hasattr(obj, "at_damage"):
                obj.at_damage(None, chain_damage, weapon_key="arc")
                room.msg_contents(f"|cThe arc chains to {getattr(obj, 'key', 'someone')}'s chrome!|n")
                return


def apply_weapon_specials(weapon, attacker_vehicle, target, hit: bool, room) -> None:
    """Post-fire resolution: tether, EMP, DoT, splash, suppression, spread, entangle, arc."""
    if not weapon or not getattr(weapon, "db", None):
        return
    specials = list(getattr(weapon.db, "special", None) or [])
    base_damage = int(getattr(weapon.db, "damage", None) or 10)
    dtype = getattr(weapon.db, "damage_type", None) or "kinetic"

    if not hit:
        if "splash_damage" in specials and room:
            apply_splash_damage(room, attacker_vehicle, base_damage, dtype)
        return

    for special in specials:
        if special == "tether" and _is_vehicle(target):
            apply_tether(attacker_vehicle, target)
        elif special == "emp_disable" and _is_vehicle(target):
            apply_emp_disable(target)
        elif special == "fire_dot":
            if _is_vehicle(target):
                apply_fire_dot(target)
            elif hasattr(target, "at_damage"):
                target.at_damage(None, max(1, base_damage // 4), weapon_key="fire")
        elif special == "splash_damage" and room:
            apply_splash_damage(room, attacker_vehicle, base_damage, dtype)
        elif special == "suppression" and not _is_vehicle(target):
            apply_suppression_to_character(target)
        elif special == "armor_piercing":
            pass
        elif special == "arc_chain" and room:
            _apply_arc_chain(room, attacker_vehicle, target, max(1, base_damage // 3))
        elif special == "entangle":
            if _is_vehicle(target):
                _apply_vehicle_entangle(target)
            elif hasattr(target, "db"):
                _apply_pedestrian_entangle(target)
        elif special == "spread" and not _is_vehicle(target) and room:
            _apply_spread_damage(room, attacker_vehicle, target, weapon)
