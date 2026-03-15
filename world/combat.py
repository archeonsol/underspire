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


def _body_part_and_multiplier(attack_value):
    """
    Map attack roll outcome to body part hit and damage multiplier (0.5 to 1.5).
    Higher roll = more precise hit = more severe body part and higher multiplier.
    Adds a random nudge so the same roll doesn't always hit the exact same part.
    """
    normalized = (max(_ROLL_MIN, min(_ROLL_MAX, attack_value)) - _ROLL_MIN) / (_ROLL_MAX - _ROLL_MIN)
    base_index = int(normalized * len(BODY_PARTS))
    # Nudge ±2 so hits vary (right shoulder vs left shoulder vs torso, etc.)
    index = max(0, min(len(BODY_PARTS) - 1, base_index + random.randint(-2, 2)))
    multiplier = 0.5 + normalized  # 0.5 .. 1.5 (unchanged by nudge)
    return BODY_PARTS[index], multiplier


WEAPON_DATA = {
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
    if success_level == "Critical Success":
        return "CRITICAL", attack_value
    return "HIT", attack_value

# world/combat.py

def _ticker_id(attacker, defender):
    """Id for the ticker where attacker attacks defender."""
    if not attacker or not defender:
        return None
    return f"combat_{attacker.id}_{defender.id}"


def remove_both_combat_tickers(a, b):
    """Stop both combat tickers for this pair. Call when someone dies."""
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
        a.db.combat_target = None
    if b and hasattr(b, "db"):
        b.db.combat_target = None


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
    # Only treat as dead if current_hp was explicitly set to 0 or below (None = not yet in combat)
    if (attacker.db.current_hp is not None and attacker.db.current_hp <= 0) or (
        defender.db.current_hp is not None and defender.db.current_hp <= 0
    ):
        remove_both_combat_tickers(attacker, defender)
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
        defender.msg(f"{attacker.name} is too exhausted to strike.")
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
        defender.msg(f"{attacker.name} pulls the trigger. Click. Empty. Your turn.")
        return

    # 3. THE MOVE SELECTION (tiered by skill: default 1–3, tier 1 +4–5, C +6)
    weapon = WEAPON_DATA.get(weapon_key, WEAPON_DATA["fists"])
    attack_skill = WEAPON_KEY_TO_SKILL.get(weapon_key, "unarmed")
    skill_level = getattr(attacker, "get_skill_level", lambda s: 0)(attack_skill)
    allowed = _allowed_attack_indices(skill_level)
    roll_1d6 = random.choice(allowed)
    attack_move = weapon[roll_1d6]

    # 4. RESOLVE THE HIT (or auto-hit if defender too exhausted to defend)
    if not can_fight(defender):
        attacker.msg(f"{defender.name} is too exhausted to defend. You land a solid blow.")
        defender.msg("You're too exhausted to defend yourself. The blow lands.")
        result, attack_value = "HIT", 10
    else:
        spend_stamina(defender, STAMINA_COST_DEFEND)
        result, attack_value = resolve_attack(attacker, defender, weapon_key)

    # 5. MESSAGING & DAMAGE (brutal, location-accurate, weapon-specific)
    move_name = attack_move["name"]
    if result == "MISS":
        if weapon_key == "knife":
            attacker.msg(f"You lunge. |r{defender.name}|n is gone. The blade cuts air. You're open.")
            defender.msg(f"{attacker.name} thrusts. You're already moving. The knife misses. They |rmiss.|n")
        elif weapon_key == "long_blade":
            attacker.msg(f"You swing. |r{defender.name}|n steps clear. Your edge finds nothing. You're exposed.")
            defender.msg(f"The blade comes. You're not there. It passes. {attacker.name} |rmiss.|n")
        elif weapon_key == "blunt":
            attacker.msg(f"You swing. |r{defender.name}|n reads it and moves. Your weapon hits empty. You're open.")
            defender.msg(f"{attacker.name} winds up. You're gone before it lands. They |rmiss.|n")
        elif weapon_key in ("sidearm", "longarm", "automatic"):
            attacker.msg(f"You fire. |r{defender.name}|n isn't there. The round goes wide. Miss.")
            defender.msg(f"The shot cracks past. You moved. They |rmiss.|n")
        else:
            attacker.msg(f"Your punch finds air. |r{defender.name}|n slipped it. You're off balance.")
            defender.msg(f"{attacker.name} throws. You move. They |rmiss.|n")

    elif result == "PARRIED":
        if weapon_key == "knife":
            attacker.msg(f"You thrust. |c{defender.name}|n meets it. Steel on steel. Your blade is turned. |cParried.|n")
            defender.msg(f"The knife comes in. You block. The blade goes wide. |cParried.|n")
        elif weapon_key == "long_blade":
            attacker.msg(f"Your blade comes down. |c{defender.name}|n catches it. Impact. They shove it aside. |cParried.|n")
            defender.msg(f"The edge falls. You meet it. You turn the blow. |cParried.|n")
        elif weapon_key == "blunt":
            attacker.msg(f"You swing. |c{defender.name}|n blocks. Your strike slides off. |cParried.|n")
            defender.msg(f"{attacker.name} swings. You block. The blow goes wide. |cParried.|n")
        else:
            attacker.msg(f"Your punch goes in. |c{defender.name}|n blocks. No contact. |cParried.|n")
            defender.msg(f"{attacker.name} throws. Your guard is up. The punch is turned. |cParried.|n")

    elif result == "DODGED":
        if weapon_key == "knife":
            attacker.msg(f"You go for the gut. |y{defender.name} rolls.|n The blade misses. You're exposed.")
            defender.msg(f"You see the lunge. You |yroll.|n The knife passes. You're still up.")
        elif weapon_key == "long_blade":
            attacker.msg(f"Downstroke. |y{defender.name} slips it.|n Your edge hits nothing. You're open.")
            defender.msg(f"The blade drops. You |yroll clear.|n It misses. You're still standing.")
        elif weapon_key == "blunt":
            attacker.msg(f"You put your weight into it. |y{defender.name} is gone.|n The blow finds air. You're exposed.")
            defender.msg(f"You see it coming. You |yroll.|n The weapon misses. That would have broken you.")
        elif weapon_key in ("sidearm", "longarm", "automatic"):
            attacker.msg(f"You squeeze. |y{defender.name} is already moving.|n The round goes where they were. Miss.")
            defender.msg(f"Muzzle flash. You |ydive.|n The shot goes past. You're still breathing.")
        else:
            attacker.msg(f"You commit. |y{defender.name} slips the punch.|n You're open.")
            defender.msg(f"The punch comes. You |yroll.|n {attacker.name}'s fist misses.")

    elif result in ("HIT", "CRITICAL"):
        # Defender already dead this tick (other callback ran first)? Do nothing.
        if (defender.db.current_hp or 0) <= 0:
            remove_both_combat_tickers(attacker, defender)
            return
        body_part, multiplier = _body_part_and_multiplier(attack_value)
        base = attack_move['damage']
        if result == "CRITICAL":
            damage = int(base * 1.5 * multiplier)
        else:
            damage = int(base * multiplier)
        damage = max(1, damage)
        is_critical = result == "CRITICAL"

        from world.medical import apply_trauma, get_brutal_hit_flavor
        trauma_result = apply_trauma(defender, body_part, damage, is_critical, weapon_key=weapon_key)
        # Send hit messages first, then apply HP/death so "collapses" comes after the hit
        main_atk, main_def = _hit_message(
            weapon_key, body_part, defender.name, attacker.name, is_critical
        )
        flavor_atk, flavor_def = get_brutal_hit_flavor(
            weapon_key, body_part, trauma_result, defender.name, attacker.name, is_critical
        )
        attacker.msg(f"{main_atk} {flavor_atk}".strip())
        defender.msg(f"{main_def} {flavor_def}".strip())
        defender.at_damage(attacker, damage, body_part=body_part, weapon_key=weapon_key)

    # 6. Consume one round for ranged weapons (fired whether hit or miss)
    if is_ranged_weapon(weapon_key) and wielded_obj and hasattr(wielded_obj, "db"):
        current = int(wielded_obj.db.ammo_current or 0)
        if current > 0:
            wielded_obj.db.ammo_current = current - 1

from evennia import TICKER_HANDLER as ticker


def _get_combat_target(caller):
    """Return the character caller is currently in combat with, or None."""
    return getattr(caller.db, "combat_target", None)


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
    """
    defender = _get_object_by_id(defender_id)
    attacker = _get_object_by_id(attacker_id)
    if not defender or not attacker:
        return
    if getattr(defender.db, "combat_ended", False) or getattr(attacker.db, "combat_ended", False):
        return
    if _get_combat_target(defender) != attacker or _get_combat_target(attacker) != defender:
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
    if _get_combat_target(attacker) != target or _get_combat_target(target) != attacker:
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
    """
    if not attacker or not target:
        return
    _set_combat_target(attacker, target)
    _set_combat_target(target, attacker)
    if getattr(attacker.db, "current_hp", None) is None or (attacker.db.current_hp or 0) <= 0:
        attacker.db.current_hp = getattr(attacker, "max_hp", 100)
    if getattr(target.db, "current_hp", None) is None or (target.db.current_hp or 0) <= 0:
        target.db.current_hp = getattr(target, "max_hp", 100)
    attacker.db.combat_ended = False
    target.db.combat_ended = False

    weapon_key = _get_attacker_weapon_key(attacker)
    ready_attacker = COMBAT_READY_ATTACKER_MSG.get(weapon_key, COMBAT_READY_ATTACKER_MSG["fists"])
    attacker.msg(ready_attacker.format(target=target.name))
    target.msg(COMBAT_READY_DEFENDER_MSG)
    if target.location:
        target.location.msg_contents(
            COMBAT_READY_ROOM_MSG.format(defender=target.name),
            exclude=(target,),
        )

    sec = random.uniform(COMBAT_START_DELAY_MIN, COMBAT_START_DELAY_MAX)
    delay(sec, _start_first_round, attacker.id, target.id)


def stop_combat_ticker(attacker, target):
    """Stop only your attacks; the other can keep attacking until someone dies."""
    if not attacker or not target:
        return
    id_me = _ticker_id(attacker, target)
    if not id_me:
        attacker.msg("|yYou are not in a fight.|n")
        return
    try:
        ticker.remove(COMBAT_INTERVAL, execute_combat_turn, idstring=id_me, persistent=True)
        _set_combat_target(attacker, None)
        # Do not clear target's combat_target; they may still be attacking us (e.g. we swapped targets).
        attacker.msg(f"|yYou pull back from the fight with {target.name}.|n")
    except KeyError:
        attacker.msg("|yYou are not in a fight.|n")