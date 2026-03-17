# D:\ColonyGame\mootest\world\combat.py
# Body parts and trauma: single source in world.medical
import random
from world.medical import BODY_PARTS
from world.skills import SKILL_STATS, WEAPON_KEY_TO_SKILL, DEFENSE_SKILL
from world.ammo import is_ranged_weapon
from evennia.utils import delay
try:
    from world.levels import SKILL_LEVEL_TIER_1, SKILL_LEVEL_FOR_C
except ImportError:
    SKILL_LEVEL_TIER_1 = 60
    SKILL_LEVEL_FOR_C = 123

# Roll value range for gradient: attack_value is clamped to [ROLL_MIN, ROLL_MAX] then normalized to 0..1
_ROLL_MIN, _ROLL_MAX = 1, 100

# Seconds between each combat round (your attack and their attack each run on this interval)
COMBAT_INTERVAL = 5
# Stagger so turns alternate: defender's first attack runs this many seconds after attacker's first
COMBAT_STAGGER = COMBAT_INTERVAL / 2.0  # 2.5s -> my attack, their attack, my attack, their attack...
# Delay before first round (random in range so combat starts 5-6s after "ready" messages)
COMBAT_START_DELAY_MIN, COMBAT_START_DELAY_MAX = 5.0, 6.0

# "Ready" messages when combat is initiated: attacker sees weapon-specific line; defender and room see defender squaring up.
# Templates use {target} for the defender's name. Customize per weapon class as needed.
COMBAT_READY_ATTACKER_MSG = {
    "fists": "|rYou raise your fists, eyeing {target}.|n",
    "knife": "|rYou ready your blade, eyeing {target}.|n",
    "long_blade": "|rYou ready your blade, eyeing {target}.|n",
    "blunt": "|rYou heft your weapon, eyeing {target}.|n",
    "sidearm": "|rYou bring your sidearm up, eyeing {target}.|n",
    "longarm": "|rYou shoulder your weapon, eyeing {target}.|n",
    "automatic": "|rYou bring the weapon to bear, eyeing {target}.|n",
}
COMBAT_READY_DEFENDER_MSG = "|rYou square up, getting ready to fight.|n"
COMBAT_READY_ROOM_MSG = "|r{defender} squares up, getting ready to fight.|n"
# Room sees attacker initiate (so e.g. p3 attack Bob shows "Test readies..." to the room)
COMBAT_READY_ATTACKER_ROOM_MSG = "|r{attacker} gets ready to fight {target}.|n"

# Parry: melee-only. Defender rolls parry first; if they beat the attack roll (with penalty), attack is parried (no damage). Else evasion runs as normal.
MELEE_WEAPON_KEYS = ("fists", "knife", "long_blade", "blunt")
PARRY_PENALTY = 8  # Applied to parry roll so equal skill favors attacker; parry must still beat attack value

# Hands required per weapon: 1 = one-handed, 2 = two-handed. Used for wield/unwield.
WEAPON_HANDS = {
    "fists": 1,
    "knife": 1,
    "long_blade": 2,
    "blunt": 2,
    "sidearm": 1,
    "longarm": 2,
    "automatic": 2,
}


def _combat_display_name(char, viewer):
    """Name for char as seen by viewer (sdesc/recog for Characters, else .name/.key)."""
    if char is None:
        return "Someone"
    if viewer is not None and hasattr(char, "get_display_name"):
        out = char.get_display_name(viewer)
        if out:
            return out
    return getattr(char, "name", None) or getattr(char, "key", None) or "Someone"


def _body_part_and_multiplier(attack_value):
    """
    Map attack roll outcome to body part hit and damage multiplier (0.5 to 1.5).
    Body part is chosen mostly at random, with a small bias from a strong roll
    toward higher-severity locations (torso/head) so good hits feel better
    without every high-skill strike auto-gravitating to the face/head.
    """
    # Normalize roll 0..1 for damage scaling and bias strength.
    normalized = (max(_ROLL_MIN, min(_ROLL_MAX, attack_value)) - _ROLL_MIN) / (_ROLL_MAX - _ROLL_MIN)

    # Start from a mostly random body part.
    base_index = random.randrange(len(BODY_PARTS))

    # Small upward bias for better rolls: stronger rolls are *more likely* to
    # drift toward high-value locations, but never guarantee head/face.
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

    multiplier = 0.5 + normalized  # 0.5 .. 1.5 based on roll quality only
    return BODY_PARTS[index], multiplier


WEAPON_DATA = {
    # Kept as a safe fallback if weapon tiers are missing or misconfigured.
    "fists": {
        1: {"name": "Jab", "damage": 5},
        2: {"name": "Cross", "damage": 8},
        3: {"name": "Hook", "damage": 12},
        4: {"name": "Uppercut", "damage": 15},
        5: {"name": "Kidney Punch", "damage": 10},
        6: {"name": "Headbutt", "damage": 20},
    },
    "knife": {
        1: {"name": "Slash", "damage": 12},
        2: {"name": "Stab", "damage": 18},
        3: {"name": "Gut-rip", "damage": 25},
        4: {"name": "Throat-slit", "damage": 35},
        5: {"name": "Pommel Strike", "damage": 8},
        6: {"name": "Arterial Nick", "damage": 22},
    },
    "long_blade": {
        1: {"name": "Cut", "damage": 14},
        2: {"name": "Thrust", "damage": 20},
        3: {"name": "Sweep", "damage": 18},
        4: {"name": "Overhead", "damage": 28},
        5: {"name": "Pommel Bash", "damage": 10},
        6: {"name": "Deep Strike", "damage": 32},
    },
    "blunt": {
        1: {"name": "Swing", "damage": 12},
        2: {"name": "Strike", "damage": 18},
        3: {"name": "Crush", "damage": 24},
        4: {"name": "Overhead Smash", "damage": 30},
        5: {"name": "Rib Shot", "damage": 16},
        6: {"name": "Skull Crack", "damage": 26},
    },
    "sidearm": {
        1: {"name": "Single Shot", "damage": 14},
        2: {"name": "Double Tap", "damage": 22},
        3: {"name": "Center Mass", "damage": 28},
        4: {"name": "Head Shot", "damage": 38},
        5: {"name": "Quick Draw", "damage": 18},
        6: {"name": "Controlled Pair", "damage": 26},
    },
    "longarm": {
        1: {"name": "Single Shot", "damage": 20},
        2: {"name": "Aimed Shot", "damage": 32},
        3: {"name": "Burst", "damage": 28},
        4: {"name": "Precision Hit", "damage": 42},
        5: {"name": "Hip Fire", "damage": 16},
        6: {"name": "Follow-through", "damage": 36},
    },
    "automatic": {
        1: {"name": "Short Burst", "damage": 18},
        2: {"name": "Sweep", "damage": 24},
        3: {"name": "Sustained Fire", "damage": 30},
        4: {"name": "Controlled Burst", "damage": 36},
        5: {"name": "Spray", "damage": 22},
        6: {"name": "Mag Dump", "damage": 44},
    },
}

# Attack tiers by move index: 1–3 = default (everyone), 4–5 = tier 1 (skill >= SKILL_LEVEL_TIER_1), 6 = tier 2 / C (skill >= SKILL_LEVEL_FOR_C)
_ATTACK_INDICES_DEFAULT = (1, 2, 3)
_ATTACK_INDICES_TIER_1 = (1, 2, 3, 4, 5)
_ATTACK_INDICES_TIER_2 = (1, 2, 3, 4, 5, 6)


def _allowed_attack_indices(skill_level):
    """Return tuple of move indices (1–6) the attacker can use based on their weapon skill level (0–150)."""
    if skill_level is None or skill_level < 0:
        skill_level = 0
    if skill_level >= SKILL_LEVEL_FOR_C:
        return _ATTACK_INDICES_TIER_2
    if skill_level >= SKILL_LEVEL_TIER_1:
        return _ATTACK_INDICES_TIER_1
    return _ATTACK_INDICES_DEFAULT


def _weapon_attack_table(weapon_key, weapon_obj, skill_level):
    """
    Build a 1–6 attack table for this weapon_key using world.weapon_tiers if available.
    Falls back to static WEAPON_DATA on any error.

    Tier selection:
      - weapon_obj.db.weapon_tier (1–10) if set
      - else 1

    Damage:
      - uses the midpoint of (damage_min, damage_max) for each attack, then
        the existing body-part multiplier and critical scaling.
    """
    # Fallback to old static table if we can't import or look up tiers
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
    # Respect skill gating (1–3 / 1–5 / 1–6) but clamp to number of defined attacks.
    allowed = _allowed_attack_indices(skill_level)
    max_allowed = min(max(allowed), len(attacks), max_index)

    for idx in range(1, max_allowed + 1):
        atk = attacks[(idx - 1) % len(attacks)]
        dmg_min = int(atk.get("damage_min", 0))
        dmg_max = int(atk.get("damage_max", dmg_min))
        mid = max(1, int((dmg_min + dmg_max) / 2))
        table[idx] = {"name": atk.get("name", f"Attack {idx}"), "damage": mid}

    # Ensure we always have something to roll on
    if not table:
        return WEAPON_DATA.get(weapon_key, WEAPON_DATA["fists"])
    return table


def _hit_message(weapon_key, body_part, defender_name, attacker_name, is_critical):
    """
    Flavorful hit messages with hit location. No 'they go down' — combat isn't over.
    body_part is shown so the room knows where the blow landed.
    """
    loc = body_part or "them"
    if weapon_key == "knife":
        if is_critical:
            pool = [
                (f"|yCRITICAL.|n You drive the blade into {defender_name}'s {loc}. Steel goes deep; they buckle.", f"|R{attacker_name}|n sinks the knife into your {loc}. You double over, still standing."),
                (f"|yCRITICAL.|n One vicious thrust into {defender_name}'s {loc}. The blade comes back red.", f"|R{attacker_name}|n opens you at the {loc}. You reel but stay up."),
            ]
        else:
            pool = [
                (f"You slash at {defender_name}'s {loc}. The edge bites; they hiss and stagger.", f"The blade cuts your {loc}. It burns. You're still in the fight."),
                (f"Steel finds flesh at {defender_name}'s {loc}. A cut opens; red runs.", f"|R{attacker_name}|n opens a cut on your {loc}. You press a hand to it and hold your ground."),
            ]
    elif weapon_key == "long_blade":
        if is_critical:
            pool = [
                (f"|yCRITICAL.|n You slice through {defender_name}'s {loc} in one long stroke. The edge is red; they crumple to one knee.", f"|R{attacker_name}|n's blade shears across your {loc}. You drop to a knee, gasping."),
                (f"|yCRITICAL.|n A sweeping cut catches {defender_name}'s {loc}. Flesh parts; they stagger hard.", f"|R{attacker_name}|n cuts you deep across the {loc}. You're still standing — barely."),
            ]
        else:
            pool = [
                (f"You bring the edge down on {defender_name}'s {loc}. A clean cut; they reel back.", f"The blade finds your {loc}. You stagger but keep your feet."),
                (f"Your sword lashes across {defender_name}'s {loc}. Blood on the steel; they're still up.", f"|R{attacker_name}|n opens a gash on your {loc}. You taste blood and hold your stance."),
            ]
    elif weapon_key == "blunt":
        if is_critical:
            pool = [
                (f"|yCRITICAL.|n You put everything into a blow to {defender_name}'s {loc}. You feel the impact; they fold and catch themselves.", f"|R{attacker_name}|n crushes your {loc}. Something gives. You stay up through sheer will."),
                (f"|yCRITICAL.|n One heavy strike to {defender_name}'s {loc}. The crack is ugly. They stagger but don't fall.", f"|R{attacker_name}|n lands it on your {loc}. Your vision blurs. You're still standing."),
            ]
        else:
            pool = [
                (f"Your strike lands on {defender_name}'s {loc}. Solid impact; they grunt and reel.", f"The blow catches your {loc}. Your head rings. You stay in the fight."),
                (f"You hammer {defender_name}'s {loc}. They stagger, still up.", f"Something heavy finds your {loc}. You blink, taste blood, and hold your ground."),
            ]
    elif weapon_key in ("sidearm", "longarm", "automatic"):
        if is_critical:
            pool = [
                (f"|yCRITICAL.|n Your round punches through {defender_name}'s {loc}. They jerk and stagger, hand to the wound.", f"|R{attacker_name}|n shoots you. The bullet hits your {loc}. You're still on your feet."),
                (f"|yCRITICAL.|n The shot finds {defender_name}'s {loc}. They double over but don't drop.", f"|R{attacker_name}|n's round tears into your {loc}. You reel and stay standing."),
            ]
        else:
            pool = [
                (f"Your shot hits {defender_name}'s {loc}. They jerk; blood blooms. Still up.", f"You're hit in the {loc}. Shot. The pain is coming. You're still fighting."),
                (f"The round finds flesh at {defender_name}'s {loc}. They flinch and keep their feet.", f"|R{attacker_name}|n's bullet grazes your {loc}. Shock holds the worst at bay. You hold your ground."),
            ]
    else:
        if is_critical:
            pool = [
                (f"|yCRITICAL.|n Your fist connects with {defender_name}'s {loc}. You feel bone. They stagger badly but stay up.", f"|R{attacker_name}|n lands a brutal shot on your {loc}. Lights flash. You're still standing."),
                (f"|yCRITICAL.|n You put everything into a strike to {defender_name}'s {loc}. They reel and catch themselves.", f"|R{attacker_name}|n hits your {loc} hard. You taste blood. You don't go down."),
            ]
        else:
            pool = [
                (f"Your fist connects with {defender_name}'s {loc}. Solid. They stagger.", f"The punch catches your {loc}. You taste blood. Still up."),
                (f"You hit them in the {loc}. They reel but keep their feet.", f"|R{attacker_name}|n's blow finds your {loc}. You blink and stay in it."),
            ]
    atk, def_ = random.choice(pool)
    return atk, def_


def _defender_parry_skill(defender):
    """
    Skill used for parry: defender's wielded weapon skill if melee, else unarmed (block/deflect).
    Returns skill key for WEAPON_KEY_TO_SKILL / SKILL_STATS.
    """
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
    """
    Combat with Hidden Roll Modifiers.
    weapon_key: key in WEAPON_DATA (e.g. "fists", "knife"); maps to attack skill and stats via world.skills.
    For melee attacks, defender may parry first (roll must beat attack value, with penalty); if parry fails, evasion is rolled.
    Returns (result, attack_value) where result is "MISS", "PARRIED", "DODGED", "HIT", or "CRITICAL".
    Stance and trauma affect attack, parry, and dodge rolls.
    """
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

    # Trauma penalties: fractures (arm=attack, leg=defense), bleeding affects both
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
    success_level, attack_value = attacker.roll_check(
        attack_stats, attack_skill, modifier=atk_mod
    )

    if success_level == "Failure":
        return "MISS", attack_value

    # Melee-only parry: defender rolls parry; must beat attack value (parry roll has penalty so not pure skill vs skill).
    if weapon_key in MELEE_WEAPON_KEYS:
        parry_skill = _defender_parry_skill(defender)
        parry_stats = SKILL_STATS.get(parry_skill, ["agility", "strength"])
        _parry_level, parry_value = defender.roll_check(
            parry_stats, parry_skill, modifier=def_mod - PARRY_PENALTY
        )
        if parry_value > attack_value:
            return "PARRIED", attack_value

    # Evasion (dodge) roll
    defense_stats = SKILL_STATS.get(DEFENSE_SKILL, ["agility", "perception"])
    def_level, defense_value = defender.roll_check(
        defense_stats, DEFENSE_SKILL, modifier=def_mod
    )

    if defense_value >= attack_value:
        return "DODGED", attack_value

    # Criticals: even at high skill, make crits feel special and slightly
    # random instead of every "Critical Success" becoming a guaranteed crit.
    if success_level == "Critical Success":
        # Clamp and normalize roll to 0..1 for scaling.
        norm = (max(_ROLL_MIN, min(_ROLL_MAX, attack_value)) - _ROLL_MIN) / (_ROLL_MAX - _ROLL_MIN)
        # Base ~4% crit chance on a crit success, scaling up to ~15% at
        # extremely strong rolls so high skill still matters but doesn't spam crits.
        crit_chance = 0.04 + 0.11 * norm
        if random.random() < crit_chance:
            return "CRITICAL", attack_value

    return "HIT", attack_value

# world/combat.py

def _ticker_id(attacker, defender):
    """Id for the ticker where attacker attacks defender."""
    if not attacker or not defender:
        return None
    return f"combat_{attacker.id}_{defender.id}"


def remove_both_combat_tickers(a, b):
    """Stop both combat tickers for this pair and end combat for both. Call when someone dies or flees."""
    from evennia import TICKER_HANDLER as ticker
    id_ab = _ticker_id(a, b)
    id_ba = _ticker_id(b, a)
    for idstring in (id_ab, id_ba):
        if idstring:
            try:
                ticker.remove(COMBAT_INTERVAL, execute_combat_turn, idstring=idstring, persistent=True)
            except KeyError:
                pass
    if a and hasattr(a, "db"):
        _set_combat_target(a, None)
        a.db.combat_ended = True
    if b and hasattr(b, "db"):
        _set_combat_target(b, None)
        b.db.combat_ended = True


def _get_object_by_id(dbref):
    """Return the typeclassed Object for this dbref (int). Used by ticker callbacks."""
    if dbref is None:
        return None
    from evennia.utils.search import search_object
    from evennia.utils import logger
    try:
        ref = f"#{int(dbref)}"
        result = search_object(ref)
        if result:
            return result[0]
    except Exception as e:
        logger.log_trace("combat._get_object_by_id(#%s): %s" % (dbref, e))
    try:
        result = search_object(key=int(dbref))
        if result:
            return result[0]
    except Exception as e:
        logger.log_trace("combat._get_object_by_id(key=%s): %s" % (dbref, e))
    try:
        result = search_object(int(dbref))
        if result:
            return result[0]
    except Exception as e:
        logger.log_trace("combat._get_object_by_id(%s): %s" % (dbref, e))
    return None


def _resolve_combat_objects(attacker, defender, kwargs):
    """Resolve attacker/defender from ids (ticker callbacks pass ids as kwargs or as positional ints)."""
    attacker_id = kwargs.get("attacker_id")
    defender_id = kwargs.get("defender_id")
    # Ticker may pass ids as positional args (attacker=id, defender=id)
    if isinstance(attacker, int):
        attacker_id = attacker
        attacker = None
    if isinstance(defender, int):
        defender_id = defender
        defender = None
    if attacker_id is None and defender_id is None:
        return attacker, defender
    if attacker is None and attacker_id is not None:
        attacker = _get_object_by_id(attacker_id)
    if defender is None and defender_id is not None:
        defender = _get_object_by_id(defender_id)
    return attacker, defender


def execute_combat_turn(attacker=None, defender=None, attack_type=None, **kwargs):
    """
    Single side's attack: resolve one attacker vs one defender.
    If either is dead, remove both tickers and return immediately (no further messages).
    Can be called with attacker/defender objects or with attacker_id/defender_id in kwargs (or as positional ints) for ticker callbacks.
    """
    attacker, defender = _resolve_combat_objects(attacker, defender, kwargs)
    # Re-fetch from DB when we came from ticker so we see latest HP
    if attacker and defender and (kwargs.get("attacker_id") is not None or kwargs.get("defender_id") is not None):
        a_new = _get_object_by_id(attacker.id if hasattr(attacker, "id") else kwargs.get("attacker_id"))
        d_new = _get_object_by_id(defender.id if hasattr(defender, "id") else kwargs.get("defender_id"))
        if a_new:
            attacker = a_new
        if d_new:
            defender = d_new
    if not attacker or not defender:
        remove_both_combat_tickers(attacker, defender)
        return
    # Ensure HP is initialized (Character.hp sets current_hp to max_hp if None)
    if hasattr(attacker, "hp"):
        _ = attacker.hp
    if hasattr(defender, "hp"):
        _ = defender.hp
    # Flag set in at_damage when hp<=0 so the other callback in same tick sees it immediately
    if getattr(attacker.db, "combat_ended", False) or getattr(defender.db, "combat_ended", False):
        remove_both_combat_tickers(attacker, defender)
        return
    # Wield/unwield/free hands during combat: skip this attack (distraction)
    if getattr(attacker.db, "combat_skip_next_turn", False):
        attacker.attributes.remove("combat_skip_next_turn")
        attacker.msg("|yYou're too busy adjusting your grip to strike this moment.|n")
        defender.msg("|y%s is distracted and doesn't strike.|n" % _combat_display_name(attacker, defender))
        # Room echo: attacker is adjusting their grip and does not strike
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = _combat_display_name(attacker, viewer)
                viewer.msg(f"{atk_v} adjusts their grip and doesn't strike this moment.")
        return
    # Attacker stopped or switched target: remove only this ticker (their attacks); don't end defender's combat.
    if _get_combat_target(attacker) != defender:
        remove_both_combat_tickers(attacker, defender)
        return
    # Defender may have stopped attacking; we still run this turn (attacker strikes defender). Do not remove both tickers.
    # Only treat as dead if current_hp was explicitly set to 0 or below (None = not yet in combat)
    if (attacker.db.current_hp is not None and attacker.db.current_hp <= 0) or (
        defender.db.current_hp is not None and defender.db.current_hp <= 0
    ):
        remove_both_combat_tickers(attacker, defender)
        return

    # 1a. Grappled characters cannot strike back
    if getattr(attacker.db, "grappled_by", None):
        attacker.msg("You're locked in their grasp; you can't strike back.")
        defender.msg(f"{_combat_display_name(attacker, defender)} is too restrained to strike.")
        # Room echo: attacker is too restrained to strike
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = _combat_display_name(attacker, viewer)
                viewer.msg(f"{atk_v} struggles against a hold and can't strike back.")
        return

    # 1b. Stamina: exhausted characters cannot attack or defend
    try:
        from world.stamina import is_exhausted, spend_stamina, can_fight
        from world.stamina import STAMINA_COST_ATTACK, STAMINA_COST_DEFEND
    except ImportError:
        is_exhausted = lambda _: False
        spend_stamina = lambda _c, _a: True
        can_fight = lambda _: True
        STAMINA_COST_ATTACK = STAMINA_COST_DEFEND = 0
    if not can_fight(attacker):
        attacker.msg("You're too exhausted to strike.")
        defender.msg(f"{_combat_display_name(attacker, defender)} is too exhausted to strike.")
        # Room echo: attacker is too exhausted to strike
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = _combat_display_name(attacker, viewer)
                viewer.msg(f"{atk_v} looks too exhausted to strike.")
        return
    spend_stamina(attacker, STAMINA_COST_ATTACK)

    # 2. THE WEAPON CHECK
    wielded_obj = attacker.db.wielded_obj
    if wielded_obj and wielded_obj.location == attacker:
        weapon_key = attacker.db.wielded
    else:
        weapon_key = "fists"

    # 2b. Ranged weapons require ammo
    if is_ranged_weapon(weapon_key) and wielded_obj and (not getattr(wielded_obj, "has_ammo", lambda: True)()):
        attacker.msg("Click. |rempty.|n The mag is dry. |wReload|n or you're dead.")
        defender.msg(f"{_combat_display_name(attacker, defender)} pulls the trigger. Click. Empty. Your turn.")
        # Room echo: attacker pulls the trigger on an empty weapon
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = _combat_display_name(attacker, viewer)
                viewer.msg(f"{atk_v} pulls the trigger. Click. |rempty.|n")
        return

    # 3. THE MOVE SELECTION (tiered by skill: default 1–3, tier 1 +4–5, C +6)
    attack_skill = WEAPON_KEY_TO_SKILL.get(weapon_key, "unarmed")
    skill_level = getattr(attacker, "get_skill_level", lambda s: 0)(attack_skill)
    weapon = _weapon_attack_table(weapon_key, wielded_obj, skill_level)
    allowed = tuple(i for i in _allowed_attack_indices(skill_level) if i in weapon)
    roll_1d6 = random.choice(allowed)
    attack_move = weapon[roll_1d6]

    # 4. RESOLVE THE HIT (or auto-hit if defender too exhausted to defend)
    if not can_fight(defender):
        attacker.msg(f"{_combat_display_name(defender, attacker)} is too exhausted to defend. You land a solid blow.")
        defender.msg("You're too exhausted to defend yourself. The blow lands.")
        result, attack_value = "HIT", 10
        # Room echo: defender is too exhausted to defend
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = _combat_display_name(attacker, viewer)
                def_v = _combat_display_name(defender, viewer)
                viewer.msg(f"{def_v} looks too exhausted to defend as {atk_v}'s blow lands.")
    else:
        spend_stamina(defender, STAMINA_COST_DEFEND)
        result, attack_value = resolve_attack(attacker, defender, weapon_key)

    # 5. MESSAGING & DAMAGE (brutal, location-accurate, weapon-specific)
    move_name = attack_move["name"]
    if result == "MISS":
        def_name = _combat_display_name(defender, attacker)
        atk_name = _combat_display_name(attacker, defender)
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
        # Room echo: attacker misses defender
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = _combat_display_name(attacker, viewer)
                def_v = _combat_display_name(defender, viewer)
                viewer.msg(f"{atk_v} attacks {def_v} but |rmisses.|n")

    elif result == "PARRIED":
        def_name = _combat_display_name(defender, attacker)
        atk_name = _combat_display_name(attacker, defender)
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
        # Room echo: defender parries the attack
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = _combat_display_name(attacker, viewer)
                def_v = _combat_display_name(defender, viewer)
                viewer.msg(f"{atk_v} attacks {def_v}, but {def_v} |cparries the blow.|n")

    elif result == "DODGED":
        def_name = _combat_display_name(defender, attacker)
        atk_name = _combat_display_name(attacker, defender)
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
        # Room echo: defender dodges the attack
        loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
        if loc and hasattr(loc, "contents_get"):
            for viewer in loc.contents_get(content_type="character"):
                if viewer in (attacker, defender):
                    continue
                atk_v = _combat_display_name(attacker, viewer)
                def_v = _combat_display_name(defender, viewer)
                viewer.msg(f"{atk_v} attacks {def_v}, but {def_v} |ydodges aside.|n")

    elif result in ("HIT", "CRITICAL"):
        # Defender already dead this tick (other callback ran first)? Do nothing.
        if (defender.db.current_hp or 0) <= 0:
            remove_both_combat_tickers(attacker, defender)
            return
        # Body shield: defender has someone grappled — roll to see if blow hits the shield instead.
        # Not as reliable as natural dodge: defender must beat attack by a margin (harder to pull off).
        BODY_SHIELD_PENALTY = 15  # shield intercepts only if defender_roll >= attack_value + this
        effective_defender = defender
        hit_shield = False
        shield = getattr(defender.db, "grappling", None)
        if shield and getattr(shield, "db", None) and getattr(shield, "at_damage", None):
            try:
                def_roll = defender.roll_check(
                    ["agility", "perception"], "evasion", modifier=0
                )
                shield_value = def_roll[1] if isinstance(def_roll, (tuple, list)) else 0
                if shield_value >= attack_value + BODY_SHIELD_PENALTY:
                    hit_shield = True
                    effective_defender = shield
            except Exception:
                pass
        body_part, multiplier = _body_part_and_multiplier(attack_value)
        base = attack_move['damage']
        if result == "CRITICAL":
            damage = int(base * 1.5 * multiplier)
        else:
            damage = int(base * multiplier)
        damage = max(1, damage)
        is_critical = result == "CRITICAL"

        # Armor: coin-flip reduction per point of protection on this location
        from world.damage_types import get_damage_type
        from world.armor import (
            get_armor_protection_for_location,
            compute_armor_reduction,
            degrade_armor,
        )
        damage_type = get_damage_type(weapon_key, wielded_obj)
        total_prot, armor_pieces = get_armor_protection_for_location(effective_defender, body_part, damage_type)
        reduction, absorbed_fully = compute_armor_reduction(total_prot, damage)
        damage = max(0, damage - reduction)
        if armor_pieces and reduction > 0:
            degrade_armor(armor_pieces, damage_type, reduction)

        if absorbed_fully and damage <= 0:
            # Armor completely absorbed the blow: distinct message, no trauma or HP loss
            if hit_shield:
                eff_for_atk = _combat_display_name(effective_defender, attacker)
                def_for_atk = _combat_display_name(defender, attacker)
                eff_for_def = _combat_display_name(effective_defender, defender)
                atk_for_def = _combat_display_name(attacker, defender)
                eff_for_eff = _combat_display_name(effective_defender, effective_defender)
                def_for_eff = _combat_display_name(defender, effective_defender)
                atk_for_eff = _combat_display_name(attacker, effective_defender)
                attacker.msg(f"|cYour blow lands on {eff_for_atk}'s {body_part} — {def_for_atk} pulled them in the way — but their armor absorbs it.|n")
                defender.msg(f"|cYou pull {eff_for_def} in the way. {atk_for_def}'s strike hits them but armor takes it.|n")
                effective_defender.msg(f"|c{def_for_eff} uses you as a shield. {atk_for_eff}'s blow hits your {body_part}; your armor takes it.|n")
                # Room echo: attacker hits shield but armor absorbs it
                loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
                if loc and hasattr(loc, "contents_get"):
                    for viewer in loc.contents_get(content_type="character"):
                        if viewer in (attacker, defender, effective_defender):
                            continue
                        atk_v = _combat_display_name(attacker, viewer)
                        def_v = _combat_display_name(defender, viewer)
                        eff_v = _combat_display_name(effective_defender, viewer)
                        viewer.msg(f"{def_v} pulls {eff_v} into the line of fire. {atk_v}'s blow hits {eff_v}'s {body_part}, but their armor |csoaks the impact.|n")
            else:
                attacker.msg(f"|cYour blow lands on {_combat_display_name(defender, attacker)}'s {body_part} but their armor absorbs it.|n")
                defender.msg(f"|c{_combat_display_name(attacker, defender)}'s strike hits your {body_part}; your armor takes it.|n")
                # Room echo: armor absorbs the hit
                loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
                if loc and hasattr(loc, "contents_get"):
                    for viewer in loc.contents_get(content_type="character"):
                        if viewer in (attacker, defender):
                            continue
                        atk_v = _combat_display_name(attacker, viewer)
                        def_v = _combat_display_name(defender, viewer)
                        viewer.msg(f"{atk_v}'s blow lands on {def_v}'s {body_part}, but their armor |cabsorbs the hit.|n")
        else:
            from world.medical import apply_trauma, get_brutal_hit_flavor
            trauma_result = apply_trauma(effective_defender, body_part, damage, is_critical, weapon_key=weapon_key, weapon_obj=wielded_obj)
            def_for_atk = _combat_display_name(defender, attacker)
            atk_for_def = _combat_display_name(attacker, defender)
            eff_for_atk = _combat_display_name(effective_defender, attacker)
            eff_for_def = _combat_display_name(effective_defender, defender)
            eff_for_eff = _combat_display_name(effective_defender, effective_defender)
            def_for_eff = _combat_display_name(defender, effective_defender)
            atk_for_eff = _combat_display_name(attacker, effective_defender)
            if hit_shield:
                attacker.msg(f"|r{def_for_atk} pulls {eff_for_atk} in the way! Your blow lands on {eff_for_atk}'s {body_part}.|n")
                defender.msg(f"|yYou pull {eff_for_def} in the way. The blow hits them.|n")
                _, def_line_shield = _hit_message(
                    weapon_key, body_part, eff_for_atk, atk_for_eff, is_critical
                )
                eff_self = _combat_display_name(effective_defender, effective_defender)
                flavor_atk, flavor_shield = get_brutal_hit_flavor(
                    weapon_key, body_part, trauma_result, eff_self, atk_for_eff, is_critical, weapon_obj=wielded_obj
                )
                effective_defender.msg(f"|r{def_for_eff} uses you as a shield! {atk_for_eff}'s blow hits you — {def_line_shield} {flavor_shield}".strip())
                # Room echo: defender uses someone as a shield and they are hit
                loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
                if loc and hasattr(loc, "contents_get"):
                    for viewer in loc.contents_get(content_type="character"):
                        if viewer in (attacker, defender, effective_defender):
                            continue
                        atk_v = _combat_display_name(attacker, viewer)
                        def_v = _combat_display_name(defender, viewer)
                        eff_v = _combat_display_name(effective_defender, viewer)
                        crit_tag = "|yCRITICAL.|n " if is_critical else ""
                        viewer.msg(f"{def_v} drags {eff_v} into the path of {atk_v}'s attack. {crit_tag}{atk_v}'s blow crashes into {eff_v}'s {body_part}.")
            else:
                main_atk, main_def = _hit_message(
                    weapon_key, body_part, def_for_atk, atk_for_def, is_critical
                )
                flavor_atk, flavor_def = get_brutal_hit_flavor(
                    weapon_key, body_part, trauma_result, def_for_atk, atk_for_def, is_critical, weapon_obj=wielded_obj
                )
                attacker.msg(f"{main_atk} {flavor_atk}".strip())
                defender.msg(f"{main_def} {flavor_def}".strip())
                # Room echo: straightforward damaging hit
                loc = getattr(attacker, "location", None) or getattr(defender, "location", None)
                if loc and hasattr(loc, "contents_get"):
                    for viewer in loc.contents_get(content_type="character"):
                        if viewer in (attacker, defender):
                            continue
                        atk_v = _combat_display_name(attacker, viewer)
                        def_v = _combat_display_name(defender, viewer)
                        crit_tag = "|yCRITICAL.|n " if is_critical else ""
                        viewer.msg(f"{crit_tag}{atk_v}'s strike slams into {def_v}'s {body_part}.")
            effective_defender.at_damage(attacker, damage, body_part=body_part, weapon_key=weapon_key, weapon_obj=wielded_obj)

    # 6. Consume one round for ranged weapons (fired whether hit or miss)
    if is_ranged_weapon(weapon_key) and wielded_obj and hasattr(wielded_obj, "db"):
        current = int(wielded_obj.db.ammo_current or 0)
        if current > 0:
            wielded_obj.db.ammo_current = current - 1

from evennia import TICKER_HANDLER as ticker


def _get_combat_target(caller):
    """Return the character caller is currently in combat with, or None."""
    return getattr(caller.db, "combat_target", None)


def is_being_attacked(character, location=None):
    """True if any other character in the same room has character as their combat_target (they are attacking this one)."""
    if not character or not hasattr(character, "location"):
        return False
    loc = location or getattr(character, "location", None)
    if not loc or not hasattr(loc, "contents_get"):
        return False
    for other in loc.contents_get(content_type="character"):
        if other is character:
            continue
        if getattr(other.db, "combat_target", None) == character:
            return True
    return False


def is_in_combat(character):
    """True if character is attacking someone or is being attacked (movement should use flee)."""
    return (_get_combat_target(character) is not None or
            is_being_attacked(character))


def _set_combat_target(caller, target):
    """Set who caller is fighting; None to clear."""
    caller.db.combat_target = target


def _get_attacker_weapon_key(attacker):
    """Weapon key for ready message; same logic as execute_combat_turn."""
    wielded_obj = getattr(attacker.db, "wielded_obj", None)
    if wielded_obj and getattr(wielded_obj, "location", None) == attacker:
        return getattr(attacker.db, "wielded", "fists") or "fists"
    return "fists"


def _defender_first_attack(defender_id, attacker_id):
    """
    Run defender's first attack (so order is: my attack, their attack, then loop).
    Then add defender's recurring ticker so they keep attacking every COMBAT_INTERVAL.
    When the defender is a creature (is_creature), skip this: creatures only attack via
    their AI ticker (creature_combat), so we avoid duplicate/phantom attacks and wrong timing.
    """
    defender = _get_object_by_id(defender_id)
    attacker = _get_object_by_id(attacker_id)
    if not defender or not attacker:
        return
    if getattr(defender.db, "combat_ended", False) or getattr(attacker.db, "combat_ended", False):
        return
    if _get_combat_target(defender) != attacker or _get_combat_target(attacker) != defender:
        return
    # Creatures attack only via creature AI ticker (~8s), not via PvP combat ticker
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
    id_them = _ticker_id(defender, attacker)
    if id_them:
        try:
            ticker.add(
                COMBAT_INTERVAL, execute_combat_turn, idstring=id_them, persistent=True,
                attacker_id=defender.id, defender_id=attacker.id,
            )
        except Exception as e:
            if hasattr(defender, "msg"):
                defender.msg(f"|rTicker add failed: {e}|n")


def _start_first_round(attacker_id, target_id):
    """
    Called after COMBAT_START_DELAY: run attacker's first strike, add attacker's ticker,
    then schedule defender's first strike in COMBAT_STAGGER sec so order is my -> their -> my -> their...
    """
    attacker = _get_object_by_id(attacker_id)
    target = _get_object_by_id(target_id)
    if not attacker or not target:
        if attacker:
            _set_combat_target(attacker, None)
        if target:
            _set_combat_target(target, None)
        return
    if getattr(attacker.db, "combat_ended", False) or getattr(target.db, "combat_ended", False):
        return
    # Attacker must still be targeting this defender; otherwise their combat was cancelled/swapped.
    # The defender, however, may be targeting someone else (multi-combat): we still allow this
    # attacker to strike them without forcing an aggro swap.
    if _get_combat_target(attacker) != target:
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
        _set_combat_target(attacker, None)
        _set_combat_target(target, None)
        return
    id_me = _ticker_id(attacker, target)
    if id_me:
        try:
            ticker.add(
                COMBAT_INTERVAL, execute_combat_turn, idstring=id_me, persistent=True,
                attacker_id=attacker.id, defender_id=target.id,
            )
        except Exception as e:
            if hasattr(attacker, "msg"):
                attacker.msg(f"|rTicker add failed: {e}|n")
    delay(COMBAT_STAGGER, _defender_first_attack, target.id, attacker.id)


def start_combat_ticker(attacker, target):
    """
    Start combat: show "ready" messages immediately, then run first round after 5-6s and add tickers.
    Attacker sees weapon-class "You ready your X, eyeing <target>"; defender sees "You square up..."; attacker and room see "<defender> squares up...".
    When the target is a creature (is_creature), do not set the creature's combat_target — creatures
    attack only via their AI ticker (current_target), not the PvP combat ticker, so they are never in "normal" combat.
    """
    if not attacker or not target:
        return
    # Attacker always targets the defender.
    _set_combat_target(attacker, target)
    # For non-creatures, only set the defender's combat_target if they don't already have one.
    # This allows third parties to join an existing fight without stealing aggro: the defender
    # keeps attacking whoever they were already focused on unless they manually swap targets.
    if not getattr(target.db, "is_creature", False) and _get_combat_target(target) is None:
        _set_combat_target(target, attacker)
    if getattr(attacker.db, "current_hp", None) is None or (attacker.db.current_hp or 0) <= 0:
        attacker.db.current_hp = getattr(attacker, "max_hp", 100)
    if getattr(target.db, "current_hp", None) is None or (target.db.current_hp or 0) <= 0:
        target.db.current_hp = getattr(target, "max_hp", 100)
    attacker.db.combat_ended = False
    target.db.combat_ended = False

    weapon_key = _get_attacker_weapon_key(attacker)
    ready_attacker = COMBAT_READY_ATTACKER_MSG.get(weapon_key, COMBAT_READY_ATTACKER_MSG["fists"])
    attacker.msg(ready_attacker.format(target=_combat_display_name(target, attacker)))
    target.msg(COMBAT_READY_DEFENDER_MSG)
    if target.location:
        loc = target.location
        viewers_def = [c for c in loc.contents_get(content_type="character") if c != target]
        for v in viewers_def:
            v.msg(COMBAT_READY_ROOM_MSG.format(defender=_combat_display_name(target, v)))
        viewers_atk = [c for c in loc.contents_get(content_type="character") if c != attacker]
        for v in viewers_atk:
            if v is target:
                # From defender's own perspective: attacker is getting ready to fight *you*.
                v.msg("|r{attacker} gets ready to fight you.|n".format(
                    attacker=_combat_display_name(attacker, v)
                ))
            else:
                v.msg(COMBAT_READY_ATTACKER_ROOM_MSG.format(
                    attacker=_combat_display_name(attacker, v),
                    target=_combat_display_name(target, v),
                ))

    sec = random.uniform(COMBAT_START_DELAY_MIN, COMBAT_START_DELAY_MAX)
    delay(sec, _start_first_round, attacker.id, target.id)


def stop_combat_ticker(attacker, target):
    """Stop only your attacks on this target; they can keep attacking until they stop too."""
    if not attacker or not target:
        return
    if _get_combat_target(attacker) != target:
        attacker.msg("|yYou're not attacking them.|n")
        return
    id_me = _ticker_id(attacker, target)
    if not id_me:
        attacker.msg("|yYou are not in a fight.|n")
        return
    try:
        ticker.remove(COMBAT_INTERVAL, execute_combat_turn, idstring=id_me, persistent=True)
        _set_combat_target(attacker, None)
        # Do not clear target's combat_target; they may still be attacking us.
        attacker.msg(f"|yYou pull back from the fight with {_combat_display_name(target, attacker)}.|n")
    except KeyError:
        _set_combat_target(attacker, None)
        attacker.msg("|yYou pull back from the fight.|n")