"""
Creature combat: PvE move resolution. Creatures use a moves dict (instant or telegraph);
this module picks moves by weight and executes them (damage, stamina drain, messages).
"""
import random
import time
from evennia.utils import delay
from evennia.utils.search import search_object
from evennia import TICKER_HANDLER as ticker

try:
    from world.combat import _combat_display_name
except ImportError:
    def _combat_display_name(char, viewer):
        return getattr(char, "name", None) or getattr(char, "key", None) or "Someone"

# Seconds per "tick" for creature telegraphs (wind-up then execute).
CREATURE_TICK_INTERVAL = 3.0
# Seconds between creature AI decisions when it has a target.
CREATURE_AI_INTERVAL = 8.0
# Cooldown: ignore a tick if we already attacked within this many seconds (prevents ghost double-fire).
CREATURE_AI_COOLDOWN = 4.0


def _creature_ai_ticker_id(creature):
    """Unique id for this creature's AI ticker."""
    if not creature:
        return None
    return "creature_ai_%s" % creature.id


def _creature_ai_tick_callback(creature_id=None, **kwargs):
    """Ticker callback: run one AI decision, then re-add ticker if creature still has valid target."""
    if creature_id is None:
        return
    try:
        cre = search_object("#%s" % creature_id)
        if not cre:
            return
        creature = cre[0]
    except Exception:
        return
    if not creature or not getattr(creature.db, "is_creature", False):
        stop_creature_ai_ticker(creature)
        return
    creature_ai_tick(creature)
    # Re-add ticker only if target still valid and not flatlined
    target = getattr(creature.db, "current_target", None)
    if not target or not hasattr(target, "db"):
        stop_creature_ai_ticker(creature)
        return
    if (target.db.current_hp or 0) <= 0 or creature.location != target.location:
        stop_creature_ai_ticker(creature)
        return
    try:
        from world.death import is_flatlined
        if is_flatlined(target):
            creature.db.ai_state = "idle"
            creature.db.current_target = None
            stop_creature_ai_ticker(creature)
            return
    except ImportError:
        pass
    if target and creature.location == target.location:
        try:
            ticker.add(
                CREATURE_AI_INTERVAL,
                _creature_ai_tick_callback,
                idstring=_creature_ai_ticker_id(creature),
                persistent=True,
                creature_id=creature.id,
            )
        except Exception:
            pass
    else:
        stop_creature_ai_ticker(creature)


def start_creature_ai_ticker(creature):
    """Start the recurring AI ticker for this creature (only if it has current_target).
    Always remove any existing ticker first so we never double-add (avoids ghost dodges)."""
    if not creature or not getattr(creature.db, "is_creature", False):
        return
    target = getattr(creature.db, "current_target", None)
    if not target:
        return
    idstring = _creature_ai_ticker_id(creature)
    if not idstring:
        return
    try:
        stop_creature_ai_ticker(creature)
        ticker.add(
            CREATURE_AI_INTERVAL,
            _creature_ai_tick_callback,
            idstring=idstring,
            persistent=True,
            creature_id=creature.id,
        )
    except Exception:
        pass


def stop_creature_ai_ticker(creature):
    """Stop the creature's AI ticker (e.g. when target is cleared or creature dies)."""
    idstring = _creature_ai_ticker_id(creature) if creature else None
    if not idstring:
        return
    try:
        ticker.remove(CREATURE_AI_INTERVAL, _creature_ai_tick_callback, idstring=idstring, persistent=True)
    except (KeyError, Exception):
        pass


def get_creature_moves(creature):
    """Return the moves dict for this creature (from get_moves() or db.creature_moves)."""
    if not creature:
        return {}
    if hasattr(creature, "get_moves") and callable(creature.get_moves):
        return creature.get_moves() or {}
    return getattr(creature.db, "creature_moves", None) or {}


def pick_creature_move(creature):
    """
    Pick a move by weight. Returns (move_key, move_spec) or (None, None).
    """
    moves = get_creature_moves(creature)
    if not moves:
        return None, None
    total = sum(m.get("weight", 10) for m in moves.values())
    if total <= 0:
        return None, None
    r = random.randint(1, total)
    for key, spec in moves.items():
        w = spec.get("weight", 10)
        if r <= w:
            return key, spec
        r -= w
    return None, None


def _resolve_creature_attack(creature, target):
    """
    Contested roll: creature's attack vs target's evasion. Target can be exhausted (auto-hit).
    Returns (hit: bool, attack_value: int).
    """
    try:
        from world.rpg.stamina import is_exhausted
        if is_exhausted(target):
            return True, 99
    except ImportError:
        pass
    try:
        from world.combat.rolls import DEFAULT_CFG, combat_rating, opposed_probability, quality_value
        from world.skills import DEFENSE_SKILL, SKILL_STATS
        cfg = DEFAULT_CFG

        # Creature attack rating: use its unarmed skill (creatures typically override get_skill_level).
        atk_rating = combat_rating(creature, ["strength"], "unarmed", modifier=0, cfg=cfg)

        defense_stats = SKILL_STATS.get(DEFENSE_SKILL, ["agility", "perception"])
        def_rating = combat_rating(target, defense_stats, DEFENSE_SKILL, modifier=0, cfg=cfg)

        p_hit = opposed_probability(atk_rating, def_rating, cfg=cfg, bias=0.0)
        hit = random.random() < p_hit
        atk_value = quality_value(atk_rating, def_rating, cfg=cfg)
        return hit, atk_value
    except Exception:
        # Legacy fallback
        _, attack_value = creature.roll_check(["strength"], "unarmed", modifier=0)
        try:
            from world.skills import DEFENSE_SKILL, SKILL_STATS
            defense_stats = SKILL_STATS.get(DEFENSE_SKILL, ["agility", "perception"])
            _, defense_value = target.roll_check(defense_stats, DEFENSE_SKILL, modifier=0)
        except ImportError:
            defense_value = 0
        return (defense_value < attack_value, attack_value)


# Default miss message if move spec has no msg_miss
DEFAULT_CREATURE_MISS_MSG = "{target} throws themselves aside — {name}'s blow misses!"


def execute_creature_move(creature, target, move_key, move_spec=None):
    """
    Execute a creature move on the target: evasion roll first, then hit (visceral message + damage)
    or miss (miss message). move_spec can be passed in (e.g. when executing a queued telegraph).
    Returns True if executed (whether hit or miss), False if invalid.
    """
    if not creature or not target or not hasattr(target, "at_damage"):
        return False
    moves = get_creature_moves(creature) if move_spec is None else {move_key: move_spec}
    spec = move_spec or (moves.get(move_key) if moves else None)
    if not spec:
        return False

    # Use both so telegraph execution still has a room if creature/target moved
    loc = getattr(creature, "location", None) or getattr(target, "location", None)
    damage = int(spec.get("damage", 0))
    stamina_drain = int(spec.get("stamina_drain", 0))

    # Attack announcement: prefer the move's flavor (msg/execute_msg/msg_hit) so we never show generic when the move has flavor
    attack_msg = spec.get("msg") or spec.get("execute_msg") or spec.get("msg_hit") or spec.get("msg_attack") or "{name} attacks {target}!"
    used_hit_flavor_for_announce = not spec.get("msg_attack")
    if loc:
        for v in loc.contents_get(content_type="character"):
            if v == creature:
                continue
            attack_text = attack_msg.format(name=_combat_display_name(creature, v), target=_combat_display_name(target, v))
            v.msg(attack_text)
    if hasattr(creature, "msg"):
        creature.msg(attack_msg.format(name=_combat_display_name(creature, creature), target=_combat_display_name(target, creature)))

    # Evasion: creature attack vs target dodge (attack_value used for body part + multiplier)
    hit, attack_value = _resolve_creature_attack(creature, target)

    if not hit:
        # Miss: message only, no damage. Room sees it (exclude only creature so target gets room message).
        msg_miss = spec.get("msg_miss") or DEFAULT_CREATURE_MISS_MSG
        if loc:
            for v in loc.contents_get(content_type="character"):
                if v == creature:
                    continue
                v.msg(msg_miss.format(name=_combat_display_name(creature, v), target=_combat_display_name(target, v)))
        if hasattr(creature, "msg"):
            creature.msg(msg_miss.format(name=_combat_display_name(creature, creature), target=_combat_display_name(target, creature)))
        return True

    # Hit: body part and damage multiplier (same as regular combat)
    try:
        from world.combat import _body_part_and_multiplier
        body_part, multiplier = _body_part_and_multiplier(attack_value)
    except ImportError:
        try:
            from world.medical import BODY_PARTS
            body_part = random.choice(BODY_PARTS) if BODY_PARTS else "torso"
            multiplier = 1.0
        except Exception:
            body_part = "torso"
            multiplier = 1.0

    base_damage = int(spec.get("damage", 0))
    damage = max(1, int(base_damage * multiplier))
    weapon_key = spec.get("weapon_key") or "fists"
    is_critical = attack_value >= 90

    # Armor: same reduction as regular combat
    try:
        from world.combat.damage_types import get_damage_type
        from world.armor import (
            get_armor_protection_for_location,
            compute_armor_reduction,
            degrade_armor,
        )
        damage_type = get_damage_type(weapon_key, None)
        total_prot, armor_pieces = get_armor_protection_for_location(target, body_part, damage_type)
        reduction, absorbed_fully = compute_armor_reduction(total_prot, damage)
        damage = max(0, damage - reduction)
        if armor_pieces and reduction > 0:
            degrade_armor(armor_pieces, damage_type, reduction)
    except Exception:
        absorbed_fully = False

    # Stamina drain (e.g. block-crush) before armor check so block-crush still applies
    if stamina_drain and hasattr(target, "db"):
        cur = int(getattr(target.db, "current_stamina", None) or 0)
        target.db.current_stamina = max(0, cur - stamina_drain)

    if absorbed_fully and damage <= 0:
        # Armor absorbed the blow
        if loc:
            for v in loc.contents_get(content_type="character"):
                if v == creature:
                    continue
                tname = _combat_display_name(target, v)
                cname = _combat_display_name(creature, v)
                v.msg("|cThe blow lands on %s's %s but their armor absorbs it.|n" % (tname, body_part))
        if hasattr(creature, "msg"):
            creature.msg("|cYour strike hits %s's %s — their armor takes it.|n" % (_combat_display_name(target, creature), body_part))
        if hasattr(target, "msg"):
            target.msg("|c%s's strike hits your %s; your armor takes it.|n" % (_combat_display_name(creature, target), body_part))
        return True

    # Main hit message (creature move flavor). Skip room if we already used this line as the attack announcement.
    hit_msg = spec.get("msg_hit") or spec.get("execute_msg") or spec.get("msg") or "{name} hits {target}!"
    if not used_hit_flavor_for_announce:
        if loc:
            for v in loc.contents_get(content_type="character"):
                if v == creature:
                    continue
                v.msg(hit_msg.format(name=_combat_display_name(creature, v), target=_combat_display_name(target, v)))
    if hasattr(creature, "msg"):
        creature.msg(hit_msg.format(name=_combat_display_name(creature, creature), target=_combat_display_name(target, creature)))

    # Trauma (organs, fractures, bleeding) and injury display — same as regular combat
    trauma_result = {}
    trauma_room_sent = False
    if damage > 0:
        try:
            from world.medical import apply_trauma, get_brutal_hit_flavor
            trauma_result = apply_trauma(
                target, body_part, damage, is_critical,
                weapon_key=weapon_key, weapon_obj=None,
            )
            target_name_for_tgt = _combat_display_name(target, target)
            creature_name_for_tgt = _combat_display_name(creature, target)
            _, flavor_def = get_brutal_hit_flavor(
                weapon_key, body_part, trauma_result, target_name_for_tgt, creature_name_for_tgt, is_critical, weapon_obj=None,
            )
            if flavor_def and hasattr(target, "msg"):
                target.msg(flavor_def)
            if trauma_result.get("organ") or trauma_result.get("fracture") or trauma_result.get("bleeding"):
                if loc:
                    for v in loc.contents_get(content_type="character"):
                        if v == creature:
                            continue
                        v.msg("|rThe blow tears into %s's %s — blood splashes everywhere like a waterfall|n" % (_combat_display_name(target, v), body_part))
                trauma_room_sent = True
        except Exception:
            pass
        if loc and not trauma_room_sent:
            for v in loc.contents_get(content_type="character"):
                if v == creature:
                    continue
                v.msg("|yThe blow lands on %s's %s.|n" % (_combat_display_name(target, v), body_part))
        target.at_damage(creature, damage, body_part=body_part, weapon_key=weapon_key, weapon_obj=None)

    return True


def start_telegraph(creature, target, move_key, move_spec):
    """
    Start a telegraph: set creature's queued_attack, ticks_to_strike, ai_state.
    Schedules execute when ticks_to_strike reaches 0 (one tick = CREATURE_TICK_INTERVAL seconds).
    """
    if not creature or not move_spec or not target:
        return
    ticks = int(move_spec.get("ticks", 1))
    creature.db.queued_attack = (move_key, move_spec)
    creature.db.ticks_to_strike = ticks
    creature.db.ai_state = "winding_up"
    creature.db.current_target = target
    # Telegraph message (per-viewer so sdesc/recog respected)
    telegraph_msg = move_spec.get("telegraph_msg")
    if telegraph_msg and creature.location:
        loc = creature.location
        for v in loc.contents_get(content_type="character"):
            v.msg(telegraph_msg.format(name=_combat_display_name(creature, v), target=_combat_display_name(target, v)))
    # Schedule execute after ticks * CREATURE_TICK_INTERVAL
    delay_secs = max(0.5, ticks * CREATURE_TICK_INTERVAL)
    delay(delay_secs, _execute_telegraph_callback, creature.id, target.id, move_key)


def _execute_telegraph_callback(creature_id, target_id, move_key):
    """Execute a queued telegraph after the delay."""
    try:
        cre = search_object("#%s" % creature_id)
        tgt = search_object("#%s" % target_id)
        if not cre or not tgt:
            return
        creature, target = cre[0], tgt[0]
    except Exception:
        return
    if not creature or not target:
        return
    queued = getattr(creature.db, "queued_attack", None)
    if not queued or queued[0] != move_key:
        creature.db.ai_state = "idle"
        creature.db.queued_attack = None
        creature.db.ticks_to_strike = 0
        return
    move_key, move_spec = queued
    creature.db.queued_attack = None
    creature.db.ticks_to_strike = 0
    creature.db.ai_state = "aggro"
    execute_creature_move(creature, target, move_key, move_spec)


def creature_ai_tick(creature):
    """
    One AI tick: if creature has current_target, pick a move. Instant = execute now;
    telegraph = start_telegraph (which schedules the execute). If no target or invalid, set idle.
    Cooldown guard prevents double execution if the ticker fires twice in quick succession.
    """
    if not creature or not getattr(creature.db, "is_creature", False):
        return
    now = time.time()
    last = getattr(creature.db, "last_creature_attack_at", None)
    if last is not None and (now - last) < CREATURE_AI_COOLDOWN:
        return
    target = getattr(creature.db, "current_target", None)
    if not target or not hasattr(target, "db"):
        creature.db.ai_state = "idle"
        creature.db.current_target = None
        return
    if getattr(target.db, "current_hp", 1) <= 0:
        creature.db.ai_state = "idle"
        creature.db.current_target = None
        stop_creature_ai_ticker(creature)
        return
    try:
        from world.death import is_flatlined
        if is_flatlined(target):
            creature.db.ai_state = "idle"
            creature.db.current_target = None
            stop_creature_ai_ticker(creature)
            return
    except ImportError:
        pass
    if creature.location != target.location:
        creature.db.ai_state = "idle"
        creature.db.current_target = None
        return
    # Winding up: do nothing this tick (execute is already scheduled)
    if getattr(creature.db, "ai_state", None) == "winding_up":
        return
    move_key, move_spec = pick_creature_move(creature)
    if not move_spec:
        return
    creature.db.last_creature_attack_at = now
    if move_spec.get("type") == "telegraph":
        start_telegraph(creature, target, move_key, move_spec)
    else:
        execute_creature_move(creature, target, move_key, move_spec)
