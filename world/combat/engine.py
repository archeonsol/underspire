from __future__ import annotations

import random
from evennia.utils import logger

from world.medical import BODY_PARTS, apply_trauma, get_brutal_hit_flavor
from world.skills import SKILL_STATS, WEAPON_KEY_TO_SKILL, DEFENSE_SKILL
from world.ammo import is_ranged_weapon
from world.combat.weapon_definitions import WEAPON_DATA
from world.combat.combat_messages import hit_message, get_result_messages, get_soak_messages
from world.combat.damage_types import get_damage_type
from world.combat.range_system import (
    get_attack_range_penalty,
    get_parry_range_penalty,
    get_combat_range,
    get_range_display_line,
    RANGE_LABELS,
)
from world.combat.cover import (
    get_cover_defense_bonus,
    get_suppressed_attack_penalty,
    apply_cover_damage_reduction,
)
from world.armor import (
    get_armor_protection_for_location,
    compute_armor_reduction,
    degrade_armor,
    degrade_cyberware_armor,
)

try:
    from world.rpg.stamina import (
        is_exhausted,
        spend_stamina,
        can_fight,
        get_stamina_modifier,
        STAMINA_COST_ATTACK,
        STAMINA_COST_DEFEND,
    )
except ImportError:  # keep combat usable even if stamina module is missing
    is_exhausted = lambda _: False
    spend_stamina = lambda _c, _a: True
    can_fight = lambda _: True
    get_stamina_modifier = lambda _: 0
    STAMINA_COST_ATTACK = STAMINA_COST_DEFEND = 0

try:
    from world.levels import SKILL_LEVEL_TIER_1, SKILL_LEVEL_FOR_C
except ImportError:
    SKILL_LEVEL_TIER_1 = 60
    SKILL_LEVEL_FOR_C = 123

from .utils import (
    combat_display_name,
    combat_role_name,
    combat_msg,
    resolve_combat_objects,
    get_combat_target,
)
from .instance import get_instance_for, try_auto_switch_target

ROLL_MIN, ROLL_MAX = 1, 100

MELEE_WEAPON_KEYS = ("fists", "claws", "knife", "long_blade", "blunt")
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


def _has_deployed_claws(character):
    for cw in (getattr(character.db, "cyberware", None) or []):
        if type(cw).__name__ == "RetractableClaws" and bool(getattr(cw.db, "claws_deployed", False)) and not bool(
            getattr(cw.db, "malfunctioning", False)
        ):
            return True
    return False


def _weapon_attack_table(weapon_key, weapon_obj, skill_level):
    try:
        from world.combat.weapon_tiers import get_weapon_tier, find_weapon_template
    except Exception:
        return WEAPON_DATA.get(weapon_key, WEAPON_DATA["fists"])

    entry = None
    tier = None
    if weapon_obj is not None and getattr(weapon_obj, "db", None):
        template_name = getattr(weapon_obj.db, "weapon_template", None)
        tier = getattr(weapon_obj.db, "weapon_tier", None)

        # If this object declares a specific template (or tier), we must use the tier system.
        # This ensures a template weapon only ever uses its defined move list (names + damage ranges).
        if template_name:
            entry, tier = find_weapon_template(weapon_key, template_name)
            # Common legacy case: weapon was renamed to the template name but weapon_template wasn't set right.
            if not entry:
                logger.log_warn(
                    f"combat.weapon table miss key={weapon_key} template={template_name}; trying object key fallback."
                )
                entry2, tier2 = find_weapon_template(weapon_key, getattr(weapon_obj, "key", None) or "")
                if entry2:
                    entry, tier = entry2, tier2
                    try:
                        weapon_obj.db.weapon_template = entry.get("name") or template_name
                    except Exception:
                        pass
        # If still no entry, fall back to tier lookup (never to WEAPON_DATA when tiers are available).
        if not entry:
            try:
                tier_int = int(tier) if tier is not None else 1
            except Exception:
                tier_int = 1
            logger.log_warn(
                f"combat.weapon template unresolved key={weapon_key}; falling back to tier={tier_int}."
            )
            entry = get_weapon_tier(weapon_key, tier_int)

    if not isinstance(tier, int) or tier < 1:
        tier = 1
    tier = max(1, min(10, tier))

    if not entry:
        logger.log_warn(f"combat.weapon tier miss key={weapon_key} tier={tier}; using WEAPON_DATA fallback.")
        entry = get_weapon_tier(weapon_key, tier)
    if not entry:
        # If weapon_tiers is importable but contains no data, keep combat functional.
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


def _body_part_and_multiplier(attack_value, defender=None):
    # Filter out missing body parts — can't hit what isn't there.
    # Chrome parts are still hittable (the blow lands, but biological
    # trauma is suppressed in apply_trauma).
    available = BODY_PARTS
    if defender:
        from world.body import get_missing_parts
        missing = get_missing_parts(defender)
        if missing:
            available = [p for p in BODY_PARTS if p not in missing]
            if not available:
                available = BODY_PARTS  # shouldn't happen, but safe fallback
    normalized = (max(ROLL_MIN, min(ROLL_MAX, attack_value)) - ROLL_MIN) / (ROLL_MAX - ROLL_MIN)
    n = len(available)
    weights = []
    for idx in range(n):
        rank = idx / max(1, n - 1)
        weights.append(1.0 + normalized * 3.0 * rank)
    index = random.choices(range(n), weights=weights, k=1)[0]
    multiplier = 0.5 + normalized
    return available[index], multiplier


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
    # If you're holding a ranged weapon (pistol/rifle/etc), you can't effectively parry.
    # Fall back to dodge-only reactions in this exchange.
    if def_key and is_ranged_weapon(def_key):
        return None
    if def_key and def_key in MELEE_WEAPON_KEYS:
        return WEAPON_KEY_TO_SKILL.get(def_key, "unarmed")
    return "unarmed"


def resolve_attack(attacker, defender, weapon_key="fists"):
    atk_stance = (attacker.db.combat_stance or "neutral").lower()
    def_stance = (defender.db.combat_stance or "neutral").lower()
    if atk_stance == "balanced":
        atk_stance = "neutral"
    if def_stance == "balanced":
        def_stance = "neutral"

    atk_stance_mod = 0
    def_stance_mod = 0
    stance_mods = {
        "allin": 16,
        "aggressive": 8,
        "neutral": 0,
        "defensive": -8,
        "turtle": -14,
    }
    atk_stance_mod = int(stance_mods.get(atk_stance, 0))
    # Defender modifier is mirrored (attack-forward stances weaken defense).
    def_stance_mod = int(-stance_mods.get(def_stance, 0))

    atk_trauma_mod = 0
    def_trauma_mod = 0
    atk_mod = atk_stance_mod
    def_mod = def_stance_mod

    try:
        from world.medical import get_trauma_combat_modifiers

        t_atk, t_def = get_trauma_combat_modifiers(attacker)
        atk_trauma_mod = int(t_atk or 0)
        atk_mod += atk_trauma_mod
        t_def_atk, t_def_def = get_trauma_combat_modifiers(defender)
        def_trauma_mod = int(t_def_def or 0)
        def_mod += def_trauma_mod
    except Exception as e:
        from evennia.utils import logger

        logger.log_trace("combat.resolve_attack: get_trauma_combat_modifiers failed: %s" % e)

    # Low stamina applies a soft combat penalty instead of hard lockout.
    atk_mod += int(get_stamina_modifier(attacker) or 0)
    def_mod += int(get_stamina_modifier(defender) or 0)
    atk_mod += int(get_attack_range_penalty(attacker, defender, weapon_key) or 0)
    atk_mod += int(get_suppressed_attack_penalty(attacker) or 0)
    current_range = get_combat_range(attacker, defender)
    damage_type = get_damage_type(weapon_key, None)
    def_mod += int(get_cover_defense_bonus(defender, weapon_key, damage_type, current_range) or 0)

    attack_skill = WEAPON_KEY_TO_SKILL.get(weapon_key, "unarmed")
    attack_stats = SKILL_STATS.get(attack_skill, ["strength", "agility"])
    from world.combat.rolls import (
        load_cfg,
        combat_rating,
        opposed_probability,
        quality_value,
        combat_debug_snapshot,
    )

    cfg = load_cfg()

    atk_rating = combat_rating(attacker, attack_stats, attack_skill, modifier=atk_mod, cfg=cfg)

    # --- Reaction resolution (System 2: logistic opposed checks) ---
    defense_stats = SKILL_STATS.get(DEFENSE_SKILL, ["agility", "perception"])
    dodge_rating = combat_rating(defender, defense_stats, DEFENSE_SKILL, modifier=def_mod, cfg=cfg)

    # Single defense resolution: compute both (if applicable), pick the better rating, roll once.
    best_kind = "dodge"
    best_rating = dodge_rating
    best_bias = -cfg.dodge_bias
    parry_rating = None

    if weapon_key in MELEE_WEAPON_KEYS:
        parry_skill = _defender_parry_skill(defender)
        if parry_skill:
            parry_range_pen = get_parry_range_penalty(defender, attacker)
            if parry_range_pen is not None:
                parry_stats = SKILL_STATS.get(parry_skill, ["agility", "strength"])
                parry_rating = combat_rating(
                    defender, parry_stats, parry_skill, modifier=(def_mod - PARRY_PENALTY + int(parry_range_pen or 0)), cfg=cfg
                )
                if parry_rating >= best_rating:
                    best_kind = "parry"
                    best_rating = parry_rating
                    best_bias = -cfg.parry_bias

    p_defend = 1.0 - opposed_probability(atk_rating, best_rating, cfg=cfg, bias=best_bias)
    if random.random() < p_defend:
        atk_quality = quality_value(atk_rating, best_rating, cfg=cfg)
        outcome = "PARRIED" if best_kind == "parry" else "DODGED"
        _maybe_emit_combat_debug(
            attacker,
            defender,
            combat_debug_snapshot(
                cfg=cfg,
                attack_skill=attack_skill,
                defense_skill=DEFENSE_SKILL,
                atk_mod=atk_mod,
                def_mod=def_mod,
                atk_stance_mod=atk_stance_mod,
                atk_trauma_mod=atk_trauma_mod,
                def_stance_mod=def_stance_mod,
                def_trauma_mod=def_trauma_mod,
                attacker_rating=atk_rating,
                dodge_rating=dodge_rating,
                parry_skill=parry_skill if weapon_key in MELEE_WEAPON_KEYS else None,
                parry_rating=parry_rating if (weapon_key in MELEE_WEAPON_KEYS and parry_skill) else None,
                best_kind=best_kind,
                best_rating=best_rating,
                p_defend=p_defend,
                outcome=outcome,
                quality=atk_quality,
            ),
        )
        return outcome, atk_quality, atk_rating

    # Hit: quality is relative to the best available defense in this exchange.
    atk_quality = quality_value(atk_rating, best_rating, cfg=cfg)
    # Crit chance scales with quality (1..100) to preserve downstream intent.
    norm = (max(ROLL_MIN, min(ROLL_MAX, atk_quality)) - ROLL_MIN) / (ROLL_MAX - ROLL_MIN)
    crit_chance = 0.02 + 0.08 * norm
    if random.random() < crit_chance:
        outcome = "CRITICAL"
    else:
        outcome = "HIT"
    _maybe_emit_combat_debug(
        attacker,
        defender,
        combat_debug_snapshot(
            cfg=cfg,
            attack_skill=attack_skill,
            defense_skill=DEFENSE_SKILL,
            atk_mod=atk_mod,
            def_mod=def_mod,
            atk_stance_mod=atk_stance_mod,
            atk_trauma_mod=atk_trauma_mod,
            def_stance_mod=def_stance_mod,
            def_trauma_mod=def_trauma_mod,
            attacker_rating=atk_rating,
            dodge_rating=dodge_rating,
            parry_skill=parry_skill if weapon_key in MELEE_WEAPON_KEYS else None,
            parry_rating=parry_rating if (weapon_key in MELEE_WEAPON_KEYS and parry_skill) else None,
            best_kind=best_kind,
            best_rating=best_rating,
            p_defend=p_defend,
            outcome=outcome,
            quality=atk_quality,
            crit_chance=crit_chance,
        ),
    )
    return outcome, atk_quality, atk_rating


def _maybe_emit_combat_debug(attacker, defender, line: str):
    """
    If enabled, emit a debug line to staff in the room (and attacker/defender if they are staff).
    """
    try:
        from django.conf import settings  # type: ignore

        if not getattr(settings, "COMBAT_DEBUG_ROLLS", False):
            return
    except Exception:
        return

    loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
    if not loc or not hasattr(loc, "contents_get"):
        return

    def _is_staff(obj) -> bool:
        if not obj:
            return False
        # Evennia: check_permstring is the common interface.
        if hasattr(obj, "check_permstring"):
            try:
                return bool(obj.check_permstring("Builder"))
            except Exception:
                pass
        # Fallback: explicit tag/attr for custom setups.
        return bool(getattr(getattr(obj, "db", None), "combat_debug", False))

    for viewer in loc.contents_get(content_type="character"):
        if _is_staff(viewer):
            try:
                viewer.msg(f"|w[combat-debug]|n {line}")
            except Exception:
                pass


def _check_body_shield(defender, attack_value, attacker_rating=None):
    BODY_SHIELD_PENALTY = 15
    effective_defender = defender
    hit_shield = False
    shield = getattr(defender.db, "grappling", None)
    if shield and getattr(shield, "db", None) and getattr(shield, "at_damage", None):
        try:
            # System 2 body-shield: if the defender can "catch" the attack with the shield-body,
            # redirect damage. We treat this as a (slightly penalized) evasion-style reaction.
            try:
                from world.combat.rolls import (
                    load_cfg,
                    combat_rating,
                    opposed_probability,
                )
                from world.skills import SKILL_STATS, DEFENSE_SKILL
                cfg = load_cfg()
                # If attacker_rating wasn't provided, fall back to an estimate from quality.
                attacker_pressure = float(attacker_rating) if attacker_rating is not None else float(attack_value) * 5.0

                defense_stats = SKILL_STATS.get(DEFENSE_SKILL, ["agility", "perception"])
                shield_rating = combat_rating(defender, defense_stats, DEFENSE_SKILL, modifier=-BODY_SHIELD_PENALTY, cfg=cfg)
                # If defender would "win" against the incoming pressure, the shield catches the hit.
                p_catch = 1.0 - opposed_probability(attacker_pressure, shield_rating, cfg=cfg, bias=cfg.body_shield_bias)
                if random.random() < p_catch:
                    hit_shield = True
                    effective_defender = shield
            except Exception:
                # Legacy fallback: old numeric compare against the defender's roll_check
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
        combat_msg(attacker, msg)
        defender_name = combat_role_name(attacker, defender, role="attacker")
        combat_msg(defender, f"{defender_name} is too restrained to strike.")
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = combat_role_name(attacker, viewer, role="attacker")
                combat_msg(viewer, f"{atk_v} struggles against a hold and can't strike back.")
        return False
    if getattr(attacker.db, "grappling", None):
        held = getattr(attacker.db, "grappling", None)
        held_name = combat_role_name(held, attacker, role="defender")
        combat_msg(attacker, f"You're busy maintaining a grapple on {held_name} and cannot make normal attacks.")
        return False

    if not can_fight(attacker):
        combat_msg(attacker, "You're too exhausted to strike.")
        atk_name = combat_role_name(attacker, defender, role="attacker")
        combat_msg(defender, f"{atk_name} is too exhausted to strike.")
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = combat_role_name(attacker, viewer, role="attacker")
                combat_msg(viewer, f"{atk_v} looks too exhausted to strike.")
        return False

    if is_ranged_weapon(weapon_key) and wielded_obj and (not getattr(wielded_obj, "has_ammo", lambda: True)()):
        combat_msg(attacker, "Click. |rempty.|n The mag is dry. |wReload|n or you're dead.")
        atk_name = combat_role_name(attacker, defender, role="attacker")
        combat_msg(defender, f"{atk_name} pulls the trigger. Click. Empty. Your turn.")
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = combat_role_name(attacker, viewer, role="attacker")
                combat_msg(viewer, f"{atk_v} pulls the trigger. Click. |rempty.|n")
        return False

    return True


def _preflight_checks(attacker, defender):
    if not attacker or not defender:
        return False
    if getattr(attacker.db, "combat_ended", False) or getattr(defender.db, "combat_ended", False):
        return False
    if get_combat_target(attacker) != defender:
        return False
    if getattr(attacker.db, "current_hp", None) is not None and attacker.db.current_hp <= 0:
        return False
    if getattr(defender.db, "current_hp", None) is not None and defender.db.current_hp <= 0:
        return False
    return True


def _emit_result_messages(attacker, defender, result, weapon_key, wielded_obj, move_name):
    templates = get_result_messages(result, weapon_key, wielded_obj, move_name=move_name)
    def_name = combat_role_name(defender, attacker, role="defender")
    atk_name = combat_role_name(attacker, defender, role="attacker")
    defaults = {
        "MISS": (
            "You attack {defender} but |rmiss.|n",
            "{attacker} attacks, but you slip the blow. |rMiss.|n",
            "{attacker} attacks {defender} but |rmisses.|n",
        ),
        "PARRIED": (
            "Your strike is |cturned aside|n by {defender}'s guard.",
            "You meet {attacker}'s strike and |cturn it aside.|n",
            "{attacker} attacks {defender}, but {defender} |cparries the blow.|n",
        ),
        "DODGED": (
            "You swing for {defender}, but they're already moving. |yDodge.|n",
            "You move as {attacker} strikes, and the blow |ymisses.|n",
            "{attacker} attacks {defender}, but {defender} |ydodges aside.|n",
        ),
    }
    atk_default, def_default, room_default = defaults[result]
    combat_msg(attacker, (templates.get("attacker") or atk_default).format(attacker=atk_name, defender=def_name))
    combat_msg(defender, (templates.get("defender") or def_default).format(attacker=atk_name, defender=def_name))
    loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
    if not loc or not hasattr(loc, "contents_get"):
        return
    room_tpl = templates.get("room") or room_default
    for viewer in loc.contents_get(content_type="character"):
        if viewer in (attacker, defender):
            continue
        atk_v = combat_role_name(attacker, viewer, role="attacker")
        def_v = combat_role_name(defender, viewer, role="defender")
        combat_msg(viewer, room_tpl.format(attacker=atk_v, defender=def_v))


def _emit_soak(attacker, defender, effective_defender, body_part, weapon_key, wielded_obj, move_name, hit_shield):
    soak_templates = get_soak_messages(weapon_key, wielded_obj, move_name=move_name, shielded=bool(hit_shield))
    names = {
        "atk_for_def": combat_role_name(attacker, defender, role="attacker"),
        "def_for_atk": combat_role_name(defender, attacker, role="defender"),
        "eff_for_atk": combat_role_name(effective_defender, attacker, role="defender"),
        "eff_for_def": combat_role_name(effective_defender, defender, role="defender"),
        "atk_for_eff": combat_role_name(attacker, effective_defender, role="attacker"),
        "def_for_eff": combat_role_name(defender, effective_defender, role="attacker"),
        "eff_for_eff": combat_role_name(effective_defender, effective_defender, role="defender"),
    }
    if hit_shield:
        combat_msg(attacker, (soak_templates.get("attacker") or "|cYour blow lands on {effective_defender}'s {loc} — {defender} pulled them in the way — but their armor absorbs it.|n").format(attacker=names["atk_for_def"], defender=names["def_for_atk"], effective_defender=names["eff_for_atk"], loc=body_part))
        combat_msg(defender, (soak_templates.get("defender") or "|cYou pull {effective_defender} in the way. {attacker}'s strike hits them but armor takes it.|n").format(attacker=names["atk_for_def"], defender=names["def_for_atk"], effective_defender=names["eff_for_def"], loc=body_part))
        combat_msg(effective_defender, (soak_templates.get("effective_defender") or "|c{defender} uses you as a shield. {attacker}'s blow hits your {loc}; your armor takes it.|n").format(attacker=names["atk_for_eff"], defender=names["def_for_eff"], effective_defender=names["eff_for_eff"], loc=body_part))
    else:
        combat_msg(attacker, (soak_templates.get("attacker") or "|cYour blow lands on {defender}'s {loc}, but their armor absorbs it.|n").format(attacker=names["atk_for_def"], defender=names["def_for_atk"], effective_defender=names["def_for_atk"], loc=body_part))
        combat_msg(defender, (soak_templates.get("defender") or "|c{attacker}'s strike hits your {loc}; your armor takes it.|n").format(attacker=names["atk_for_def"], defender=names["def_for_atk"], effective_defender=names["def_for_atk"], loc=body_part))
    loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
    if not loc or not hasattr(loc, "contents_get"):
        return
    room_tpl = soak_templates.get("room") or ("{defender} pulls {effective_defender} into the line of fire. {attacker}'s blow hits {effective_defender}'s {loc}, but their armor |csoaks the impact.|n" if hit_shield else "{attacker}'s blow lands on {defender}'s {loc}, but their armor |cabsorbs the hit.|n")
    for viewer in loc.contents_get(content_type="character"):
        if viewer in (attacker, defender) or (hit_shield and viewer == effective_defender):
            continue
        combat_msg(
            viewer,
            room_tpl.format(
                attacker=combat_role_name(attacker, viewer, role="attacker"),
                defender=combat_role_name(defender, viewer, role="defender"),
                effective_defender=combat_role_name(effective_defender, viewer, role="defender"),
                loc=body_part,
            )
        )


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
    if not _preflight_checks(attacker, defender):
        alt = try_auto_switch_target(attacker)
        if alt:
            attacker.db.combat_target = alt
            defender = alt
        else:
            _remove_both_combat_tickers(attacker, defender)
            return
    inst = get_instance_for(attacker)
    if inst:
        inst.next_round()
    if getattr(attacker.db, "combat_skip_next_turn", False):
        attacker.attributes.remove("combat_skip_next_turn")
        if getattr(attacker.db, "combat_flee_attempted", False):
            attacker.attributes.remove("combat_flee_attempted")
        if getattr(attacker.db, "combat_positioning_attempted", False):
            attacker.attributes.remove("combat_positioning_attempted")
        combat_msg(attacker, "|yYou're too busy adjusting your grip to strike this moment.|n")
        defender_name = combat_role_name(attacker, defender, role="attacker")
        combat_msg(defender, "|y%s is distracted and doesn't strike.|n" % defender_name)
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = combat_role_name(attacker, viewer, role="attacker")
                combat_msg(viewer, f"{atk_v} adjusts their grip and doesn't strike this moment.")
        return
    wielded_obj = attacker.db.wielded_obj
    if wielded_obj and wielded_obj.location == attacker:
        weapon_key = attacker.db.wielded
    elif _has_deployed_claws(attacker):
        weapon_key = "claws"
    else:
        weapon_key = "fists"
    range_penalty = get_attack_range_penalty(attacker, defender, weapon_key)
    if range_penalty is None:
        current_range = get_combat_range(attacker, defender)
        range_label = RANGE_LABELS.get(current_range, "this distance")
        combat_msg(
            attacker,
            f"|rYou can't use that weapon at {range_label} range. Use |wadvance|n or |wretreat|n to reposition.|n"
        )
        combat_msg(attacker, get_range_display_line(attacker, defender))
        return

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
        combat_msg(
            attacker,
            f"{combat_role_name(defender, attacker, role='defender')} is too exhausted to defend. You land a solid blow."
        )
        combat_msg(defender, "You're too exhausted to defend yourself. The blow lands.")
        result, attack_value, attacker_rating = "HIT", 10, None
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = combat_role_name(attacker, viewer, role="attacker")
                def_v = combat_role_name(defender, viewer, role="defender")
                combat_msg(viewer, f"{def_v} looks too exhausted to defend as {atk_v}'s blow lands.")
    else:
        spend_stamina(defender, STAMINA_COST_DEFEND)
        resolved = resolve_attack(attacker, defender, weapon_key)
        attacker_rating = None
        if isinstance(resolved, (tuple, list)) and len(resolved) >= 3:
            result, attack_value, attacker_rating = resolved[0], resolved[1], resolved[2]
        else:
            result, attack_value = resolved

    move_name = attack_move["name"]
    if result in ("MISS", "PARRIED", "DODGED"):
        _emit_result_messages(attacker, defender, result, weapon_key, wielded_obj, move_name)
        combat_msg(attacker, get_range_display_line(attacker, defender))
    elif result in ("HIT", "CRITICAL"):
        if (defender.db.current_hp or 0) <= 0:
            _remove_both_combat_tickers(attacker, defender)
            return
        effective_defender, hit_shield = _check_body_shield(defender, attack_value, attacker_rating=attacker_rating)
        body_part, multiplier = _body_part_and_multiplier(attack_value, defender=effective_defender)
        base = attack_move["damage"]
        if result == "CRITICAL":
            damage = max(int(base * (multiplier + 0.5)), int(base * 1.1))
        else:
            damage = int(base * multiplier)
        damage = max(1, damage)
        is_critical = result == "CRITICAL"

        damage_type = get_damage_type(weapon_key, wielded_obj)
        if damage_type == "arc":
            arc_vuln = getattr(effective_defender, "get_arc_vulnerability", lambda: 0.0)()
            if arc_vuln > 0:
                damage = int(damage * (1.0 + arc_vuln))
        total_prot, armor_pieces, cyberware_pieces = get_armor_protection_for_location(effective_defender, body_part, damage_type)
        reduction, absorbed_fully = compute_armor_reduction(total_prot, damage)
        damage = max(0, damage - reduction)
        damage = apply_cover_damage_reduction(attacker, effective_defender, damage, damage_type)
        if armor_pieces and reduction > 0:
            degrade_armor(armor_pieces, damage_type, reduction)
        if cyberware_pieces and reduction > 0:
            degrade_cyberware_armor(effective_defender, cyberware_pieces, reduction)

        if absorbed_fully and damage <= 0:
            _emit_soak(attacker, defender, effective_defender, body_part, weapon_key, wielded_obj, move_name, hit_shield)
        else:
            trauma_result = apply_trauma(
                effective_defender,
                body_part,
                damage,
                is_critical,
                weapon_key=weapon_key,
                weapon_obj=wielded_obj,
            )
            def_for_atk = combat_role_name(defender, attacker, role="defender")
            atk_for_def = combat_role_name(attacker, defender, role="attacker")
            eff_for_atk = combat_role_name(effective_defender, attacker, role="defender")
            eff_for_def = combat_role_name(effective_defender, defender, role="defender")
            eff_for_eff = combat_role_name(effective_defender, effective_defender, role="defender")
            def_for_eff = combat_role_name(defender, effective_defender, role="attacker")
            atk_for_eff = combat_role_name(attacker, effective_defender, role="attacker")
            if hit_shield:
                combat_msg(
                    attacker,
                    f"|r{def_for_atk} pulls {eff_for_atk} in the way! Your blow lands on {eff_for_atk}'s {body_part}.|n"
                )
                combat_msg(defender, f"|yYou pull {eff_for_def} in the way. The blow hits them.|n")
                _, def_line_shield = hit_message(
                    weapon_key,
                    body_part,
                    eff_for_atk,
                    atk_for_eff,
                    is_critical,
                    weapon_obj=wielded_obj,
                    move_name=move_name,
                )
                eff_self = combat_role_name(effective_defender, effective_defender, role="defender")
                flavor_atk, flavor_shield = get_brutal_hit_flavor(
                    weapon_key,
                    body_part,
                    trauma_result,
                    eff_self,
                    atk_for_eff,
                    is_critical,
                    weapon_obj=wielded_obj,
                )
                combat_msg(
                    effective_defender,
                    f"|r{def_for_eff} uses you as a shield! {atk_for_eff}'s blow hits you — {def_line_shield} {flavor_shield}".strip()
                )
                loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
                if loc and hasattr(loc, "contents_get"):
                    for viewer in loc.contents_get(content_type="character"):
                        if viewer in (attacker, defender, effective_defender):
                            continue
                        atk_v = combat_role_name(attacker, viewer, role="attacker")
                        def_v = combat_role_name(defender, viewer, role="defender")
                        eff_v = combat_role_name(effective_defender, viewer, role="defender")
                        crit_tag = "|yCRITICAL.|n " if is_critical else ""
                        combat_msg(
                            viewer,
                            f"{def_v} drags {eff_v} into the path of {atk_v}'s attack. {crit_tag}{atk_v}'s blow crashes into {eff_v}'s {body_part}."
                        )
            else:
                main_atk, main_def = hit_message(
                    weapon_key,
                    body_part,
                    def_for_atk,
                    atk_for_def,
                    is_critical,
                    weapon_obj=wielded_obj,
                    move_name=move_name,
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
                combat_msg(attacker, f"{main_atk} {flavor_atk}".strip())
                pain_editor = any(type(cw).__name__ == "PainEditor" and not bool(getattr(cw.db, "malfunctioning", False)) for cw in (getattr(defender.db, "cyberware", None) or []))
                if pain_editor:
                    combat_msg(defender, f"|xDamage registered at {body_part}. You feel nothing.|n")
                else:
                    combat_msg(defender, f"{main_def} {flavor_def}".strip())
                loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
                if loc and hasattr(loc, "contents_get"):
                    for viewer in loc.contents_get(content_type="character"):
                        if viewer in (attacker, defender):
                            continue
                        atk_v = combat_role_name(attacker, viewer, role="attacker")
                        def_v = combat_role_name(defender, viewer, role="defender")
                        crit_tag = "|yCRITICAL.|n " if is_critical else ""
                        combat_msg(viewer, f"{crit_tag}{atk_v}'s strike slams into {def_v}'s {body_part}.")
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

