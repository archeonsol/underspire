from __future__ import annotations

import random

from world.medical import BODY_PARTS, apply_trauma, get_brutal_hit_flavor
from world.skills import SKILL_STATS, WEAPON_KEY_TO_SKILL, DEFENSE_SKILL
from world.ammo import is_ranged_weapon
from world.weapon_definitions import WEAPON_DATA
from world.combat_messages import hit_message
from world.damage_types import get_damage_type
from world.armor import (
    get_armor_protection_for_location,
    compute_armor_reduction,
    degrade_armor,
)

try:
    from world.stamina import (
        is_exhausted,
        spend_stamina,
        can_fight,
        STAMINA_COST_ATTACK,
        STAMINA_COST_DEFEND,
    )
except ImportError:  # keep combat usable even if stamina module is missing
    is_exhausted = lambda _: False
    spend_stamina = lambda _c, _a: True
    can_fight = lambda _: True
    STAMINA_COST_ATTACK = STAMINA_COST_DEFEND = 0

try:
    from world.levels import SKILL_LEVEL_TIER_1, SKILL_LEVEL_FOR_C
except ImportError:
    SKILL_LEVEL_TIER_1 = 60
    SKILL_LEVEL_FOR_C = 123

from .utils import combat_display_name, resolve_combat_objects

ROLL_MIN, ROLL_MAX = 1, 100

MELEE_WEAPON_KEYS = ("fists", "knife", "long_blade", "blunt")
PARRY_PENALTY = 8

_ATTACK_INDICES_DEFAULT = (1, 2, 3)
_ATTACK_INDICES_TIER_1 = (1, 2, 3, 4, 5)
_ATTACK_INDICES_TIER_2 = (1, 2, 3, 4, 5, 6)


def _allowed_attack_indices(skill_level):
    if skill_level is None or skill_level < 0:
        skill_level = 0
    if skill_level >= SKILL_LEVEL_FOR_C:
        return _ATTACK_INDICES_TIER_2
    if skill_level >= SKILL_LEVEL_TIER_1:
        return _ATTACK_INDICES_TIER_1
    return _ATTACK_INDICES_DEFAULT


def _weapon_attack_table(weapon_key, weapon_obj, skill_level):
    try:
        from world.weapon_tiers import get_weapon_tier, find_weapon_template
    except Exception:
        return WEAPON_DATA.get(weapon_key, WEAPON_DATA["fists"])

    entry = None
    tier = None
    if weapon_obj is not None and getattr(weapon_obj, "db", None):
        template_name = getattr(weapon_obj.db, "weapon_template", None)
        if template_name:
            entry, tier = find_weapon_template(weapon_key, template_name)
        if not entry:
            tier = getattr(weapon_obj.db, "weapon_tier", None)

    if not isinstance(tier, int) or tier < 1:
        tier = 1
    tier = max(1, min(10, tier))

    if not entry:
        entry = get_weapon_tier(weapon_key, tier)
    if not entry:
        return WEAPON_DATA.get(weapon_key, WEAPON_DATA["fists"])

    attacks = list(entry.get("attacks") or [])
    if not attacks:
        return WEAPON_DATA.get(weapon_key, WEAPON_DATA["fists"])

    table = {}
    max_index = 6
    allowed = _allowed_attack_indices(skill_level)
    max_allowed = min(max(allowed), len(attacks), max_index)

    for idx in range(1, max_allowed + 1):
        atk = attacks[(idx - 1) % len(attacks)]
        dmg_min = int(atk.get("damage_min", 0))
        dmg_max = int(atk.get("damage_max", dmg_min))
        mid = max(1, int((dmg_min + dmg_max) / 2))
        table[idx] = {"name": atk.get("name", f"Attack {idx}"), "damage": mid}

    if not table:
        return WEAPON_DATA.get(weapon_key, WEAPON_DATA["fists"])
    return table


def _body_part_and_multiplier(attack_value):
    normalized = (max(ROLL_MIN, min(ROLL_MAX, attack_value)) - ROLL_MIN) / (ROLL_MAX - ROLL_MIN)
    base_index = random.randrange(len(BODY_PARTS))
    bias_steps = 0
    if normalized > 0.25:
        bias_steps += 1
    if normalized > 0.55:
        bias_steps += 1
    if normalized > 0.85:
        bias_steps += 1
    index = base_index
    if bias_steps > 0 and random.random() < 0.6:
        step = random.randint(1, bias_steps)
        index = min(len(BODY_PARTS) - 1, base_index + step)
    multiplier = 0.5 + normalized
    return BODY_PARTS[index], multiplier


def _defender_parry_skill(defender):
    try:
        from typeclasses.weapons import get_weapon_key
    except Exception as e:
        from evennia.utils import logger

        logger.log_trace("combat._defender_parry_skill: import get_weapon_key failed: %s" % e)
        return "unarmed"
    wielded = getattr(defender.db, "wielded_obj", None)
    if not wielded or getattr(wielded, "location", None) != defender:
        return "unarmed"
    def_key = get_weapon_key(wielded)
    if def_key and def_key in MELEE_WEAPON_KEYS:
        return WEAPON_KEY_TO_SKILL.get(def_key, "unarmed")
    return "unarmed"


def resolve_attack(attacker, defender, weapon_key="fists"):
    atk_stance = attacker.db.combat_stance or "balanced"
    def_stance = defender.db.combat_stance or "balanced"

    atk_mod = 0
    def_mod = 0
    if atk_stance == "aggressive":
        atk_mod = 20
    elif atk_stance == "defensive":
        atk_mod = -25
    if def_stance == "aggressive":
        def_mod = -20
    elif def_stance == "defensive":
        def_mod = 25

    try:
        from world.medical import get_trauma_combat_modifiers

        t_atk, t_def = get_trauma_combat_modifiers(attacker)
        atk_mod += t_atk
        t_def_atk, t_def_def = get_trauma_combat_modifiers(defender)
        def_mod += t_def_def
    except Exception as e:
        from evennia.utils import logger

        logger.log_trace("combat.resolve_attack: get_trauma_combat_modifiers failed: %s" % e)

    attack_skill = WEAPON_KEY_TO_SKILL.get(weapon_key, "unarmed")
    attack_stats = SKILL_STATS.get(attack_skill, ["strength", "agility"])
    success_level, attack_value = attacker.roll_check(attack_stats, attack_skill, modifier=atk_mod)

    if success_level == "Failure":
        return "MISS", attack_value

    if weapon_key in MELEE_WEAPON_KEYS:
        parry_skill = _defender_parry_skill(defender)
        parry_stats = SKILL_STATS.get(parry_skill, ["agility", "strength"])
        _parry_level, parry_value = defender.roll_check(
            parry_stats,
            parry_skill,
            modifier=def_mod - PARRY_PENALTY,
        )
        if parry_value > attack_value:
            return "PARRIED", attack_value

    defense_stats = SKILL_STATS.get(DEFENSE_SKILL, ["agility", "perception"])
    def_level, defense_value = defender.roll_check(defense_stats, DEFENSE_SKILL, modifier=def_mod)

    if defense_value >= attack_value:
        return "DODGED", attack_value

    if success_level == "Critical Success":
        norm = (max(ROLL_MIN, min(ROLL_MAX, attack_value)) - ROLL_MIN) / (ROLL_MAX - ROLL_MIN)
        crit_chance = 0.04 + 0.11 * norm
        if random.random() < crit_chance:
            return "CRITICAL", attack_value

    return "HIT", attack_value


def _check_body_shield(defender, attack_value):
    BODY_SHIELD_PENALTY = 15
    effective_defender = defender
    hit_shield = False
    shield = getattr(defender.db, "grappling", None)
    if shield and getattr(shield, "db", None) and getattr(shield, "at_damage", None):
        try:
            def_roll = defender.roll_check(["agility", "perception"], "evasion", modifier=0)
            shield_value = def_roll[1] if isinstance(def_roll, (tuple, list)) else 0
            if shield_value >= attack_value + BODY_SHIELD_PENALTY:
                hit_shield = True
                effective_defender = shield
        except Exception as e:
            from evennia import logger

            logger.log_trace(f"Body shield error: {e}")
    return effective_defender, hit_shield


def can_attack(attacker, defender, weapon_key, wielded_obj):
    """Single gatekeeper for combat pre-flight checks."""
    if getattr(attacker.db, "grappled_by", None):
        msg = "You're locked in their grasp; you can't strike back."
        attacker.msg(msg)
        defender.msg(f"{combat_display_name(attacker, defender)} is too restrained to strike.")
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = combat_display_name(attacker, viewer)
                viewer.msg(f"{atk_v} struggles against a hold and can't strike back.")
        return False

    if not can_fight(attacker):
        attacker.msg("You're too exhausted to strike.")
        defender.msg(f"{combat_display_name(attacker, defender)} is too exhausted to strike.")
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = combat_display_name(attacker, viewer)
                viewer.msg(f"{atk_v} looks too exhausted to strike.")
        return False

    if is_ranged_weapon(weapon_key) and wielded_obj and (not getattr(wielded_obj, "has_ammo", lambda: True)()):
        attacker.msg("Click. |rempty.|n The mag is dry. |wReload|n or you're dead.")
        defender.msg(f"{combat_display_name(attacker, defender)} pulls the trigger. Click. Empty. Your turn.")
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = combat_display_name(attacker, viewer)
                viewer.msg(f"{atk_v} pulls the trigger. Click. |rempty.|n")
        return False

    return True


def execute_combat_turn(attacker=None, defender=None, attack_type=None, **kwargs):
    attacker, defender = resolve_combat_objects(attacker, defender, kwargs)
    if attacker and defender and (kwargs.get("attacker_id") is not None or kwargs.get("defender_id") is not None):
        from .utils import get_object_by_id

        a_new = get_object_by_id(attacker.id if hasattr(attacker, "id") else kwargs.get("attacker_id"))
        d_new = get_object_by_id(defender.id if hasattr(defender, "id") else kwargs.get("defender_id"))
        if a_new:
            attacker = a_new
        if d_new:
            defender = d_new
    if not attacker or not defender:
        _remove_both_combat_tickers(attacker, defender)
        return
    if hasattr(attacker, "hp"):
        _ = attacker.hp
    if hasattr(defender, "hp"):
        _ = defender.hp
    if getattr(attacker.db, "combat_ended", False) or getattr(defender.db, "combat_ended", False):
        _remove_both_combat_tickers(attacker, defender)
        return
    if getattr(attacker.db, "combat_skip_next_turn", False):
        attacker.attributes.remove("combat_skip_next_turn")
        attacker.msg("|yYou're too busy adjusting your grip to strike this moment.|n")
        defender.msg("|y%s is distracted and doesn't strike.|n" % combat_display_name(attacker, defender))
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = combat_display_name(attacker, viewer)
                viewer.msg(f"{atk_v} adjusts their grip and doesn't strike this moment.")
        return
    if getattr(attacker.db, "current_hp", None) is not None and attacker.db.current_hp <= 0:
        _remove_both_combat_tickers(attacker, defender)
        return
    if getattr(defender.db, "current_hp", None) is not None and defender.db.current_hp <= 0:
        _remove_both_combat_tickers(attacker, defender)
        return

    wielded_obj = attacker.db.wielded_obj
    if wielded_obj and wielded_obj.location == attacker:
        weapon_key = attacker.db.wielded
    else:
        weapon_key = "fists"

    if not can_attack(attacker, defender, weapon_key, wielded_obj):
        return

    spend_stamina(attacker, STAMINA_COST_ATTACK)

    attack_skill = WEAPON_KEY_TO_SKILL.get(weapon_key, "unarmed")
    skill_level = getattr(attacker, "get_skill_level", lambda s: 0)(attack_skill)
    weapon = _weapon_attack_table(weapon_key, wielded_obj, skill_level)
    allowed = tuple(i for i in _allowed_attack_indices(skill_level) if i in weapon)
    roll_1d6 = random.choice(allowed)
    attack_move = weapon[roll_1d6]

    if not can_fight(defender):
        attacker.msg(
            f"{combat_display_name(defender, attacker)} is too exhausted to defend. You land a solid blow."
        )
        defender.msg("You're too exhausted to defend yourself. The blow lands.")
        result, attack_value = "HIT", 10
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = combat_display_name(attacker, viewer)
                def_v = combat_display_name(defender, viewer)
                viewer.msg(f"{def_v} looks too exhausted to defend as {atk_v}'s blow lands.")
    else:
        spend_stamina(defender, STAMINA_COST_DEFEND)
        result, attack_value = resolve_attack(attacker, defender, weapon_key)

    move_name = attack_move["name"]
    if result == "MISS":
        def_name = combat_display_name(defender, attacker)
        atk_name = combat_display_name(attacker, defender)
        if weapon_key == "knife":
            attacker.msg(f"You lunge. |r{def_name}|n is gone. The blade cuts air. You're open.")
            defender.msg(f"{atk_name} thrusts. You're already moving. The knife misses. They |rmiss.|n")
        elif weapon_key == "long_blade":
            attacker.msg(f"You swing. |r{def_name}|n steps clear. Your edge finds nothing. You're exposed.")
            defender.msg(f"The blade comes. You're not there. It passes. {atk_name} |rmiss.|n")
        elif weapon_key == "blunt":
            attacker.msg(f"You swing. |r{def_name}|n reads it and moves. Your weapon hits empty. You're open.")
            defender.msg(f"{atk_name} winds up. You're gone before it lands. They |rmiss.|n")
        elif weapon_key in ("sidearm", "longarm", "automatic"):
            attacker.msg(f"You fire. |r{def_name}|n isn't there. The round goes wide. Miss.")
            defender.msg(f"The shot cracks past. You moved. They |rmiss.|n")
        else:
            attacker.msg(f"Your punch finds air. |r{def_name}|n slipped it. You're off balance.")
            defender.msg(f"{atk_name} throws. You move. They |rmiss.|n")
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = combat_display_name(attacker, viewer)
                def_v = combat_display_name(defender, viewer)
                viewer.msg(f"{atk_v} attacks {def_v} but |rmisses.|n")
    elif result == "PARRIED":
        def_name = combat_display_name(defender, attacker)
        atk_name = combat_display_name(attacker, defender)
        if weapon_key == "knife":
            attacker.msg(f"You thrust. |c{def_name}|n meets it. Steel on steel. Your blade is turned. |cParried.|n")
            defender.msg(f"The knife comes in. You block. The blade goes wide. |cParried.|n")
        elif weapon_key == "long_blade":
            attacker.msg(f"Your blade comes down. |c{def_name}|n catches it. Impact. They shove it aside. |cParried.|n")
            defender.msg(f"The edge falls. You meet it. You turn the blow. |cParried.|n")
        elif weapon_key == "blunt":
            attacker.msg(f"You swing. |c{def_name}|n blocks. Your strike slides off. |cParried.|n")
            defender.msg(f"{atk_name} swings. You block. The blow goes wide. |cParried.|n")
        else:
            attacker.msg(f"Your punch goes in. |c{def_name}|n blocks. No contact. |cParried.|n")
            defender.msg(f"{atk_name} throws. Your guard is up. The punch is turned. |cParried.|n")
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = combat_display_name(attacker, viewer)
                def_v = combat_display_name(defender, viewer)
                viewer.msg(f"{atk_v} attacks {def_v}, but {def_v} |cparries the blow.|n")
    elif result == "DODGED":
        def_name = combat_display_name(defender, attacker)
        atk_name = combat_display_name(attacker, defender)
        if weapon_key == "knife":
            attacker.msg(f"You go for the gut. |y{def_name} rolls.|n The blade misses. You're exposed.")
            defender.msg(f"You see the lunge. You |yroll.|n The knife passes. You're still up.")
        elif weapon_key == "long_blade":
            attacker.msg(f"Downstroke. |y{def_name} slips it.|n Your edge hits nothing. You're open.")
            defender.msg(f"The blade drops. You |yroll clear.|n It misses. You're still standing.")
        elif weapon_key == "blunt":
            attacker.msg(f"You put your weight into it. |y{def_name} is gone.|n The blow finds air. You're exposed.")
            defender.msg(f"You see it coming. You |yroll.|n The weapon misses. That would have broken you.")
        elif weapon_key in ("sidearm", "longarm", "automatic"):
            attacker.msg(f"You squeeze. |y{def_name} is already moving.|n The round goes where they were. Miss.")
            defender.msg(f"Muzzle flash. You |ydive.|n The shot goes past. You're still breathing.")
        else:
            attacker.msg(f"You commit. |y{def_name} slips the punch.|n You're open.")
            defender.msg(f"The punch comes. You |yroll.|n {atk_name}'s fist misses.")
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = combat_display_name(attacker, viewer)
                def_v = combat_display_name(defender, viewer)
                viewer.msg(f"{atk_v} attacks {def_v}, but {def_v} |ydodges aside.|n")
    elif result in ("HIT", "CRITICAL"):
        if (defender.db.current_hp or 0) <= 0:
            _remove_both_combat_tickers(attacker, defender)
            return
        effective_defender, hit_shield = _check_body_shield(defender, attack_value)
        body_part, multiplier = _body_part_and_multiplier(attack_value)
        base = attack_move["damage"]
        if result == "CRITICAL":
            damage = int(base * 1.5 * multiplier)
        else:
            damage = int(base * multiplier)
        damage = max(1, damage)
        is_critical = result == "CRITICAL"

        damage_type = get_damage_type(weapon_key, wielded_obj)
        total_prot, armor_pieces = get_armor_protection_for_location(effective_defender, body_part, damage_type)
        reduction, absorbed_fully = compute_armor_reduction(total_prot, damage)
        damage = max(0, damage - reduction)
        if armor_pieces and reduction > 0:
            degrade_armor(armor_pieces, damage_type, reduction)

        if absorbed_fully and damage <= 0:
            if hit_shield:
                eff_for_atk = combat_display_name(effective_defender, attacker)
                def_for_atk = combat_display_name(defender, attacker)
                eff_for_def = combat_display_name(effective_defender, defender)
                atk_for_def = combat_display_name(attacker, defender)
                eff_for_eff = combat_display_name(effective_defender, effective_defender)
                def_for_eff = combat_display_name(defender, effective_defender)
                atk_for_eff = combat_display_name(attacker, effective_defender)
                attacker.msg(
                    f"|cYour blow lands on {eff_for_atk}'s {body_part} — {def_for_atk} pulled them in the way — but their armor absorbs it.|n"
                )
                defender.msg(
                    f"|cYou pull {eff_for_def} in the way. {atk_for_def}'s strike hits them but armor takes it.|n"
                )
                effective_defender.msg(
                    f"|c{def_for_eff} uses you as a shield. {atk_for_eff}'s blow hits your {body_part}; your armor takes it.|n"
                )
                loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
                if loc and hasattr(loc, "contents_get"):
                    for viewer in loc.contents_get(content_type="character"):
                        if viewer in (attacker, defender, effective_defender):
                            continue
                        atk_v = combat_display_name(attacker, viewer)
                        def_v = combat_display_name(defender, viewer)
                        eff_v = combat_display_name(effective_defender, viewer)
                        viewer.msg(
                            f"{def_v} pulls {eff_v} into the line of fire. {atk_v}'s blow hits {eff_v}'s {body_part}, but their armor |csoaks the impact.|n"
                        )
            else:
                attacker.msg(
                    f"|cYour blow lands on {combat_display_name(defender, attacker)}'s {body_part} but their armor absorbs it.|n"
                )
                defender.msg(
                    f"|c{combat_display_name(attacker, defender)}'s strike hits your {body_part}; your armor takes it.|n"
                )
                loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
                if loc and hasattr(loc, "contents_get"):
                    for viewer in loc.contents_get(content_type="character"):
                        if viewer in (attacker, defender):
                            continue
                        atk_v = combat_display_name(attacker, viewer)
                        def_v = combat_display_name(defender, viewer)
                        viewer.msg(
                            f"{atk_v}'s blow lands on {def_v}'s {body_part}, but their armor |cabsorbs the hit.|n"
                        )
        else:
            trauma_result = apply_trauma(
                effective_defender,
                body_part,
                damage,
                is_critical,
                weapon_key=weapon_key,
                weapon_obj=wielded_obj,
            )
            def_for_atk = combat_display_name(defender, attacker)
            atk_for_def = combat_display_name(attacker, defender)
            eff_for_atk = combat_display_name(effective_defender, attacker)
            eff_for_def = combat_display_name(effective_defender, defender)
            eff_for_eff = combat_display_name(effective_defender, effective_defender)
            def_for_eff = combat_display_name(defender, effective_defender)
            atk_for_eff = combat_display_name(attacker, effective_defender)
            if hit_shield:
                attacker.msg(
                    f"|r{def_for_atk} pulls {eff_for_atk} in the way! Your blow lands on {eff_for_atk}'s {body_part}.|n"
                )
                defender.msg(f"|yYou pull {eff_for_def} in the way. The blow hits them.|n")
                _, def_line_shield = hit_message(
                    weapon_key,
                    body_part,
                    eff_for_atk,
                    atk_for_eff,
                    is_critical,
                )
                eff_self = combat_display_name(effective_defender, effective_defender)
                flavor_atk, flavor_shield = get_brutal_hit_flavor(
                    weapon_key,
                    body_part,
                    trauma_result,
                    eff_self,
                    atk_for_eff,
                    is_critical,
                    weapon_obj=wielded_obj,
                )
                effective_defender.msg(
                    f"|r{def_for_eff} uses you as a shield! {atk_for_eff}'s blow hits you — {def_line_shield} {flavor_shield}".strip()
                )
                loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
                if loc and hasattr(loc, "contents_get"):
                    for viewer in loc.contents_get(content_type="character"):
                        if viewer in (attacker, defender, effective_defender):
                            continue
                        atk_v = combat_display_name(attacker, viewer)
                        def_v = combat_display_name(defender, viewer)
                        eff_v = combat_display_name(effective_defender, viewer)
                        crit_tag = "|yCRITICAL.|n " if is_critical else ""
                        viewer.msg(
                            f"{def_v} drags {eff_v} into the path of {atk_v}'s attack. {crit_tag}{atk_v}'s blow crashes into {eff_v}'s {body_part}."
                        )
            else:
                main_atk, main_def = hit_message(
                    weapon_key,
                    body_part,
                    def_for_atk,
                    atk_for_def,
                    is_critical,
                )
                flavor_atk, flavor_def = get_brutal_hit_flavor(
                    weapon_key,
                    body_part,
                    trauma_result,
                    def_for_atk,
                    atk_for_def,
                    is_critical,
                    weapon_obj=wielded_obj,
                )
                attacker.msg(f"{main_atk} {flavor_atk}".strip())
                defender.msg(f"{main_def} {flavor_def}".strip())
                loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
                if loc and hasattr(loc, "contents_get"):
                    for viewer in loc.contents_get(content_type="character"):
                        if viewer in (attacker, defender):
                            continue
                        atk_v = combat_display_name(attacker, viewer)
                        def_v = combat_display_name(defender, viewer)
                        crit_tag = "|yCRITICAL.|n " if is_critical else ""
                        viewer.msg(f"{crit_tag}{atk_v}'s strike slams into {def_v}'s {body_part}.")
            effective_defender.at_damage(
                attacker,
                damage,
                body_part=body_part,
                weapon_key=weapon_key,
                weapon_obj=wielded_obj,
            )

    if is_ranged_weapon(weapon_key) and wielded_obj and hasattr(wielded_obj, "db"):
        current = int(wielded_obj.db.ammo_current or 0)
        if current > 0:
            wielded_obj.db.ammo_current = current - 1


def _remove_both_combat_tickers(a, b):
    """
    Lazy import wrapper to avoid circular imports at module load time.
    """
    from world.combat.tickers import remove_both_combat_tickers as _rb

    _rb(a, b)

