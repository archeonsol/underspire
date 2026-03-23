"""
Grapple system: three-step resolution (see it coming, land the grab, hold/resist).
Victim is 'locked in the grasp of' grappler; grappler can drag them when moving.

Flow: phase-1 messages (tense up / lunge), 3–4s delay, then roll and phase-2 messages (locked or dodged).
"""
import random
import time

from evennia.utils import delay
from evennia.utils.search import search_object
from evennia import TICKER_HANDLER as ticker
from world.combat.utils import combat_display_name as _combat_display_name
from world.combat.range_system import validate_grapple_range
from world.combat.cover import force_leave_cover

from world.theme_colors import COMBAT_COLORS as CC
from world.unconscious_state import (
    UNCONSCIOUS_WAKE_MAX,
    UNCONSCIOUS_WAKE_MIN,
    _restore_prev_room_pose_after_unconscious,
    _wake_unconscious_callback,
    clear_sedation_markers,
    force_wake_unconscious,
    get_unconscious_wake_seconds,
    set_unconscious,
    set_unconscious_for_seconds,
)

# Delay (seconds) between "lunge" and resolution
GRAPPLE_DELAY_MIN, GRAPPLE_DELAY_MAX = 3.0, 4.0

# Step 1: grappler wins = defender didn't see it (attacker buff step 2). Defender wins = huge defender buff step 2.
STEP1_ATTACKER_BUFF = 12   # grappler won step 1
STEP1_DEFENDER_BUFF = 25   # defender won step 1 (saw it coming)

# Hold strength: starts from this + grappler strength factor; degrades each resist
# High-str grapplers can keep a hold for a long time; resist only chips away slowly.
HOLD_STRENGTH_BASE = 18
HOLD_STRENGTH_PER_STR = 3   # per 10 strength points (high str = much more hold)
HOLD_DEGRADE_PER_RESIST = 2  # each resist attempt weakens hold only slightly

# Resist cooldown (seconds) — limits how often victim can try
RESIST_COOLDOWN = 15

# Grapple strike (attack while holding): stamina drain on victim until knockout
STAMINA_DRAIN_GRAPPLE_STRIKE = 15   # victim loses this much per strike
GRAPPLE_STRIKE_INTERVAL = 10   # seconds between strangle ticks while holding

# Unarmed flat bonus for holding/contesting the grapple (third party grab and defender both use it).
GRAPPLE_UNARMED_BONUS = 5


def _clear_operating_room_sedation(character):
    """Clear OR anesthesia flags when unconsciousness ends (timer or wake command)."""
    clear_sedation_markers(character)


def _apply_grappled_cmdset(character):
    """Lock victim commands while held in a grapple (look + resist only)."""
    if not character:
        return
    try:
        # Idempotent: remove any prior one first, then re-add.
        character.cmdset.remove("GrappledCmdSet")
    except Exception:
        pass
    try:
        character.cmdset.add("commands.default_cmdsets.GrappledCmdSet")
    except Exception:
        pass


def _clear_grappled_cmdset(character):
    """Remove grappled command lock from character (if present)."""
    if not character:
        return
    try:
        character.cmdset.remove("GrappledCmdSet")
    except Exception:
        pass


def _apply_grappling_cmdset(grappler):
    """Lock grappler commands to grapple actions + movement while holding someone."""
    if not grappler:
        return
    try:
        grappler.cmdset.remove("GrapplingCmdSet")
    except Exception:
        pass
    try:
        grappler.cmdset.add("commands.default_cmdsets.GrapplingCmdSet")
    except Exception:
        pass


def _clear_grappling_cmdset(grappler):
    """Remove grappling command lock from grappler (if present)."""
    if not grappler:
        return
    try:
        grappler.cmdset.remove("GrapplingCmdSet")
    except Exception:
        pass


def clear_grapple_cmdsets_on_clone_reset(character):
    """Remove grapple/grappling cmdsets when clone/respawn logic clears grapple db state."""
    if not character:
        return
    _clear_grappled_cmdset(character)
    _clear_grappling_cmdset(character)


def free_hands_for_grapple(character, announce=True):
    """
    Clear both hands; held objects stay in inventory. Used when starting a grapple
    attempt and when a grapple successfully locks so the grappler is never
    holding items while grappling.
    """
    if not character or not getattr(character, "db", None):
        return
    from commands.inventory_cmds import _update_primary_wielded

    left = getattr(character.db, "left_hand_obj", None)
    right = getattr(character.db, "right_hand_obj", None)
    if left and getattr(left, "location", None) != character:
        left = None
    if right and getattr(right, "location", None) != character:
        right = None
    if not left and not right:
        return
    names = []
    if left:
        names.append(left)
    if right and right is not left:
        names.append(right)
    character.db.left_hand_obj = None
    character.db.right_hand_obj = None
    _update_primary_wielded(character)
    if getattr(character.db, "combat_target", None) is not None:
        character.db.combat_skip_next_turn = True
    if not announce or not hasattr(character, "msg"):
        return
    self_names = [
        (obj.get_display_name(character) if hasattr(obj, "get_display_name") else obj.name)
        for obj in names
    ]
    character.msg(
        "|yYou set aside %s to use your hands.|n" % " and ".join("|w%s|n" % n for n in self_names)
    )
    loc = getattr(character, "location", None)
    if loc and hasattr(loc, "contents_get"):
        for viewer in loc.contents_get(content_type="character"):
            if viewer == character:
                continue
            vcaller = character.get_display_name(viewer) if hasattr(character, "get_display_name") else character.name
            vnames = [
                (obj.get_display_name(viewer) if hasattr(obj, "get_display_name") else obj.name)
                for obj in names
            ]
            viewer.msg("%s sets aside %s." % (vcaller, " and ".join(vnames)))


def _roll_result(character, stat_list, skill_name, modifier=0):
    """Return (result_string, final_result) from character's roll_check."""
    if not hasattr(character, "roll_check"):
        return "Failure", 0
    return character.roll_check(stat_list, skill_name, modifier=modifier)


def _resolve_pair(grappler_id, victim_id):
    try:
        g = search_object("#%s" % grappler_id)
        v = search_object("#%s" % victim_id)
        if not g or not v:
            return None, None
        return g[0], v[0]
    except Exception:
        return None, None


def _validate_grapple_resolution(actor, victim, actor_err="" + CC["dodge"] + "The moment passed; the grapple doesn't connect.|n"):
    if not actor or not victim or actor.location != victim.location:
        if hasattr(actor, "msg") and actor:
            actor.msg(actor_err)
        return False
    return True


def apply_grapple_lock(grappler, victim):
    """Apply grapple state after a successful grab (contested or voluntary trust)."""
    try:
        from world.rpg import stealth

        if victim and stealth.is_hidden(victim):
            stealth.reveal(victim, reason="combat")
    except Exception:
        pass
    try:
        from typeclasses.vehicles import Motorcycle
        from world.vehicle_mounts import force_dismount

        bike = getattr(victim.db, "mounted_on", None) if victim else None
        if bike and isinstance(bike, Motorcycle):
            force_dismount(victim, bike, reason="grappled")
            if victim and hasattr(victim, "msg"):
                victim.msg("|rYou're dragged off your bike!|n")
    except Exception:
        pass
    free_hands_for_grapple(grappler, announce=False)
    try:
        from world.rpg.staggered_movement import interrupt_staggered_walk

        interrupt_staggered_walk(victim, notify_msg="|yYou stop moving.|n")
    except Exception:
        pass
    victim.db.grappled_by = grappler
    grappler.db.grappling = victim
    _apply_grappling_cmdset(grappler)
    force_leave_cover(victim, reason_msg="" + CC["miss"] + "You're pulled from cover!|n")
    str_display = getattr(grappler, "get_display_stat", lambda x: 0)("strength") or 0
    victim.db.grapple_hold_strength = HOLD_STRENGTH_BASE + (str_display * HOLD_STRENGTH_PER_STR // 10)
    for key in ("lying_on_table", "sitting_on", "lying_on"):
        if hasattr(victim.db, key) and getattr(victim.db, key) is not None:
            victim.attributes.remove(key)
    _apply_grappled_cmdset(victim)
    return True, "You lock {} in your grasp.".format(_combat_display_name(victim, grappler))


def _resolve_grapple_callback(grappler_id, victim_id):
    """Called after GRAPPLE_DELAY: run the roll and send phase-2 messages."""
    grappler, victim = _resolve_pair(grappler_id, victim_id)
    if not grappler or not victim:
        return
    if not _validate_grapple_resolution(grappler, victim):
        return
    if getattr(victim.db, "grappled_by", None) or getattr(grappler.db, "grappling", None):
        if hasattr(grappler, "msg") and grappler:
            grappler.msg("" + CC["dodge"] + "They're no longer in a position to be grappled.|n")
        return
    success, msg = attempt_grapple(grappler, victim)
    loc = grappler.location
    if success:
        grappler.msg("|g%s|n" % msg)
        if victim != grappler:
            victim.msg("" + CC["miss"] + "%s has you locked in their grasp! You can try |wresist|n to break free.|n" % _combat_display_name(grappler, victim))
        if loc and hasattr(loc, "contents_get"):
            for v in loc.contents_get(content_type="character"):
                if v in (grappler, victim):
                    continue
                v.msg("%s locks %s in their grasp." % (_combat_display_name(grappler, v), _combat_display_name(victim, v)))
    else:
        grappler.msg("" + CC["miss"] + "%s|n" % msg)
        victim.msg("|gYou slip free of %s's grab!|n" % _combat_display_name(grappler, victim))
        if loc and hasattr(loc, "contents_get"):
            for v in loc.contents_get(content_type="character"):
                if v in (grappler, victim):
                    continue
                gv = _combat_display_name(grappler, v)
                vv = _combat_display_name(victim, v)
                v.msg("%s grabs at %s but %s slips free." % (gv, vv, vv))


def start_grapple_attempt(grappler, victim):
    """
    Phase 1: validate, send tense/lunge messages, then schedule resolution after 3–4s.
    Returns (started: bool, error_message: str or None).
    """
    allowed, err = validate_grapple_range(grappler, victim)
    if not allowed:
        return False, err
    if not grappler or not victim or grappler == victim:
        return False, "You cannot grapple that."
    if getattr(victim.db, "grappled_by", None):
        return False, "They are already in someone's grasp."
    if getattr(victim.db, "grappling", None):
        return False, "They're busy holding someone. Deal with that first."
    if getattr(grappler.db, "grappling", None):
        return False, "You are already holding someone. Release them first."
    if grappler.location != victim.location:
        return False, "You need to be in the same place."
    try:
        from world.death import is_flatlined, is_permanently_dead
        if is_flatlined(victim) or is_permanently_dead(victim):
            return False, "You cannot grapple the dead."
        # Logged-off (sleeping) characters can be grappled and dragged, but not attacked in the grapple.
    except ImportError:
        pass

    from world.rpg.trust import check_trust

    if check_trust(victim, grappler, "grapple"):
        free_hands_for_grapple(grappler, announce=True)
        apply_grapple_lock(grappler, victim)
        grappler.msg("|gThey don't resist. You take hold.|n")
        victim.msg("|g%s takes hold of you. You allow it.|n" % _combat_display_name(grappler, victim))
        loc = grappler.location
        if loc and hasattr(loc, "contents_get"):
            for v in loc.contents_get(content_type="character"):
                if v in (grappler, victim):
                    continue
                v.msg(
                    "%s takes hold of %s."
                    % (_combat_display_name(grappler, v), _combat_display_name(victim, v))
                )
        return True, None

    free_hands_for_grapple(grappler, announce=True)

    # Phase 1: grappler sees lunge; room sees tense + lunge; target sees tense then lunge (per-viewer display names)
    v_name_for_grappler = _combat_display_name(victim, grappler)
    g_name_for_victim = _combat_display_name(grappler, victim)
    grappler.msg("" + CC["miss"] + "You lunge towards %s!|n" % v_name_for_grappler)
    victim.msg("" + CC["dodge"] + "You see %s tense up!|n" % g_name_for_victim)
    victim.msg("" + CC["miss"] + "%s lunges towards you!|n" % g_name_for_victim)
    if grappler.location:
        loc = grappler.location
        if hasattr(loc, "contents_get"):
            for v in loc.contents_get(content_type="character"):
                if v in (grappler, victim):
                    continue
                v.msg("%s tenses up and lunges towards %s!" % (_combat_display_name(grappler, v), _combat_display_name(victim, v)))
        else:
            loc.msg_contents(
                "%s tenses up and lunges towards %s!" % (_combat_display_name(grappler, None), _combat_display_name(victim, None)),
                exclude=(grappler, victim),
            )

    sec = random.uniform(GRAPPLE_DELAY_MIN, GRAPPLE_DELAY_MAX)
    delay(sec, _resolve_grapple_callback, grappler.id, victim.id)
    return True, None


def _resolve_third_party_grapple_callback(third_party_id, victim_id):
    """Called after GRAPPLE_DELAY: run the contested roll and send result messages."""
    third_party, victim = _resolve_pair(third_party_id, victim_id)
    if not third_party or not victim:
        return
    if not _validate_grapple_resolution(third_party, victim):
        return
    grappler = getattr(victim.db, "grappled_by", None)
    if not grappler or getattr(grappler.db, "grappling", None) != victim:
        if hasattr(third_party, "msg") and third_party:
            third_party.msg("" + CC["dodge"] + "They're no longer in a position to be grappled.|n")
        return
    success, msg_you, msg_grappler, msg_victim, msg_room = attempt_grapple_third_party(third_party, victim)
    third_party.msg("|g%s|n" % msg_you if success else "" + CC["miss"] + "%s|n" % msg_you)
    if grappler and hasattr(grappler, "msg"):
        grappler.msg("" + CC["miss"] + "%s|n" % msg_grappler if success else "" + CC["dodge"] + "%s|n" % msg_grappler)
    if victim and hasattr(victim, "msg"):
        victim.msg("" + CC["dodge"] + "%s|n" % msg_victim)
    if msg_room and third_party.location:
        loc = third_party.location
        if hasattr(loc, "contents_get"):
            if callable(msg_room):
                for v in loc.contents_get(content_type="character"):
                    if v in (third_party, victim, grappler):
                        continue
                    v.msg(msg_room(v))
            else:
                loc.msg_contents(msg_room, exclude=(third_party, victim, grappler))
        elif msg_room:
            fallback = msg_room(None) if callable(msg_room) else msg_room
            loc.msg_contents(fallback, exclude=(third_party, victim, grappler))


def start_grapple_third_party_attempt(third_party, victim):
    """
    Phase 1: third party tries to grab the victim from the current grappler. Send lunge messages,
    then schedule contested resolution after 3–4s. Returns (started: bool, error_message: str or None).
    """
    if not third_party or not victim:
        return False, "You cannot grapple that."
    grappler = getattr(victim.db, "grappled_by", None)
    if not grappler or getattr(grappler.db, "grappling", None) != victim:
        return False, "They are not in anyone's grasp."
    if third_party == grappler:
        return False, "You are already holding them."
    if third_party == victim:
        return False, "You cannot grapple yourself."
    if getattr(third_party.db, "grappling", None):
        return False, "You are already holding someone. Release them first."
    if third_party.location != victim.location or grappler.location != victim.location:
        return False, "You need to be in the same place."
    free_hands_for_grapple(third_party, announce=True)
    v_name_for_tp = _combat_display_name(victim, third_party)
    g_name_for_tp = _combat_display_name(grappler, third_party)
    tp_name_for_v = _combat_display_name(third_party, victim)
    v_name_for_g = _combat_display_name(victim, grappler)
    loc = third_party.location
    # Phase 1: lunge messages (third_party = you, victim = target, grappler = current holder)
    third_party.msg("" + CC["miss"] + "You lunge towards %s, trying to pull them from %s's grasp!|n" % (v_name_for_tp, g_name_for_tp))
    victim.msg("" + CC["dodge"] + "You see %s tense up!|n" % tp_name_for_v)
    victim.msg("" + CC["miss"] + "%s lunges towards you!|n" % tp_name_for_v)
    try:
        from world.rpg.staggered_movement import interrupt_staggered_walk

        interrupt_staggered_walk(victim, notify_msg="|yYou stop moving.|n")
    except Exception:
        pass
    grappler.msg("" + CC["dodge"] + "You see %s tense up and lunge towards %s!|n" % (_combat_display_name(third_party, grappler), v_name_for_g))
    if loc and hasattr(loc, "contents_get"):
        for v in loc.contents_get(content_type="character"):
            if v in (third_party, victim, grappler):
                continue
            v.msg("%s tenses up and lunges towards %s!" % (_combat_display_name(third_party, v), _combat_display_name(victim, v)))
    sec = random.uniform(GRAPPLE_DELAY_MIN, GRAPPLE_DELAY_MAX)
    delay(sec, _resolve_third_party_grapple_callback, third_party.id, victim.id)
    return True, None


def attempt_grapple(grappler, victim):
    """
    Step 1: Agility (grappler) + unarmed slightly vs Perception (victim).
    Step 2: Agility vs Agility, both use evasion; step 1 result adds buff.
    Returns (success: bool, message: str).
    """
    allowed, err = validate_grapple_range(grappler, victim)
    if not allowed:
        return False, err
    if not grappler or not victim or grappler == victim:
        return False, "You cannot grapple that."
    if getattr(victim.db, "grappled_by", None):
        return False, "They are already in someone's grasp."
    if getattr(victim.db, "grappling", None):
        return False, "They're busy holding someone. Deal with that first."
    if getattr(grappler.db, "grappling", None):
        return False, "You are already holding someone. Release them first."
    if grappler.location != victim.location:
        return False, "You need to be in the same place."
    try:
        from world.death import is_flatlined, is_permanently_dead
        if is_flatlined(victim) or is_permanently_dead(victim):
            return False, "You cannot grapple the dead."
        # Logged-off (sleeping) characters can be grappled and dragged, but not attacked in the grapple.
    except ImportError:
        pass

    # Sitting/lying is easier to grab but still allows counterplay.
    is_seated = getattr(victim.db, "sitting_on", None) is not None
    is_lying_on = getattr(victim.db, "lying_on", None) is not None
    is_on_table = getattr(victim.db, "lying_on_table", None) is not None
    opening_bonus = 15 if (is_seated or is_lying_on or is_on_table) else 5
    r1, v1 = _roll_result(grappler, ["agility"], "unarmed", modifier=opening_bonus)
    r2, v2 = _roll_result(victim, ["perception"], "evasion")
    step1_attacker_won = v1 > v2

    # Step 2: Agility vs Agility, both evasion; apply step 1 buffs
    mod_grappler = STEP1_ATTACKER_BUFF if step1_attacker_won else -STEP1_DEFENDER_BUFF
    mod_victim = STEP1_DEFENDER_BUFF if not step1_attacker_won else -STEP1_ATTACKER_BUFF
    g2, vg2 = _roll_result(grappler, ["agility"], "evasion", modifier=mod_grappler)
    g2v, vv2 = _roll_result(victim, ["agility"], "evasion", modifier=mod_victim)

    if vg2 <= vv2:
        return False, "You grab at them but they slip free. The grapple fails."

    return apply_grapple_lock(grappler, victim)


def _grapple_strike_ticker_id(grappler, victim):
    """Unique id for the strangle ticker for this grappler-victim pair."""
    if not grappler or not victim:
        return None
    return "grapple_strike_%s_%s" % (grappler.id, victim.id)


def _execute_grapple_strike_tick(grappler_id=None, victim_id=None, **kwargs):
    """Ticker callback: run one grapple_strike, then re-add ticker if still holding and victim not KO."""
    if grappler_id is None or victim_id is None:
        return
    try:
        objs = search_object("#%s" % grappler_id)
        victims = search_object("#%s" % victim_id)
        if not objs or not victims:
            return
        grappler, victim = objs[0], victims[0]
    except Exception:
        return
    if not grappler or not victim or getattr(grappler.db, "grappling", None) != victim:
        stop_grapple_strike_ticker(grappler, victim)
        return
    success, _ = grapple_strike(grappler, victim)
    if not success:
        stop_grapple_strike_ticker(grappler, victim)
        return
    # Still holding and victim not KO: schedule next tick
    if getattr(grappler.db, "grappling", None) == victim and (victim.db.current_stamina or 0) > 0:
        try:
            ticker.add(
                GRAPPLE_STRIKE_INTERVAL,
                _execute_grapple_strike_tick,
                idstring=_grapple_strike_ticker_id(grappler, victim),
                persistent=True,
                grappler_id=grappler.id,
                victim_id=victim.id,
            )
        except Exception:
            pass


def start_grapple_strike_ticker(grappler, victim):
    """Start the recurring strangle ticker (every GRAPPLE_STRIKE_INTERVAL seconds). Not started for logged-off victims (drag only)."""
    if not grappler or not victim or getattr(grappler.db, "grappling", None) != victim:
        return
    try:
        from world.death import is_character_logged_off
        if is_character_logged_off(victim) and not getattr(victim.db, "is_npc", False):
            return
    except ImportError:
        pass
    idstring = _grapple_strike_ticker_id(grappler, victim)
    if not idstring:
        return
    try:
        ticker.add(
            GRAPPLE_STRIKE_INTERVAL,
            _execute_grapple_strike_tick,
            idstring=idstring,
            persistent=True,
            grappler_id=grappler.id,
            victim_id=victim.id,
        )
    except Exception:
        pass


def stop_grapple_strike_ticker(grappler, victim):
    """Remove the strangle ticker for this pair (call when grapple ends)."""
    idstring = _grapple_strike_ticker_id(grappler, victim) if grappler and victim else None
    if not idstring:
        return
    try:
        ticker.remove(GRAPPLE_STRIKE_INTERVAL, _execute_grapple_strike_tick, idstring=idstring, persistent=True)
    except (KeyError, Exception):
        pass


def attempt_grapple_third_party(third_party, victim):
    """
    A third person tries to grapple the victim away from the current grappler.
    Contested: third_party (Str + Unarmed) vs grappler (Str + Unarmed). Same Unarmed bonus for both.
    Success = victim is transferred to third_party's grasp; old grappler loses them.
    Returns (success: bool, msg_third_party: str, msg_grappler: str, msg_victim: str, msg_room: str or None).
    """
    if not third_party or not victim:
        return False, "You cannot do that.", "", "", None
    grappler = getattr(victim.db, "grappled_by", None)
    if not grappler or getattr(grappler.db, "grappling", None) != victim:
        return False, "They are not in anyone's grasp.", "", "", None
    if third_party == grappler:
        return False, "You are already holding them.", "", "", None
    if third_party == victim:
        return False, "You cannot grapple yourself.", "", "", None
    if third_party.location != victim.location or grappler.location != victim.location:
        return False, "You need to be in the same place.", "", "", None

    # Contested: both use Str + Unarmed (same bonus for holding/contesting the grapple)
    tp_result, tp_val = _roll_result(third_party, ["strength"], "unarmed", modifier=GRAPPLE_UNARMED_BONUS)
    g_result, g_val = _roll_result(grappler, ["strength"], "unarmed", modifier=GRAPPLE_UNARMED_BONUS)
    if tp_val <= g_val:
        msg_room = lambda v: "%s tries to grab %s from %s but %s bats their attempts away." % (
            _combat_display_name(third_party, v), _combat_display_name(victim, v),
            _combat_display_name(grappler, v), _combat_display_name(grappler, v),
        )
        return False, "They bat away your attempts.", "They try to grab %s from you but you bat their attempts away." % _combat_display_name(victim, grappler), "%s tries to grab you from %s but %s bats their attempts away." % (_combat_display_name(third_party, victim), _combat_display_name(grappler, victim), _combat_display_name(grappler, victim)), msg_room

    # Success: transfer grapple. Stop any strangle ticker on the old grappler first.
    stop_grapple_strike_ticker(grappler, victim)
    grappler.db.grappling = None
    _clear_grappling_cmdset(grappler)
    victim.db.grappled_by = None
    for key in ("grapple_hold_strength", "grapple_resist_cooldown"):
        if hasattr(victim.db, key):
            victim.attributes.remove(key)
    # New grapple: third_party now holds victim
    free_hands_for_grapple(third_party, announce=False)
    victim.db.grappled_by = third_party
    third_party.db.grappling = victim
    _apply_grappling_cmdset(third_party)
    force_leave_cover(victim, reason_msg="" + CC["miss"] + "You're pulled from cover!|n")
    str_display = getattr(third_party, "get_display_stat", lambda x: 0)("strength") or 0
    victim.db.grapple_hold_strength = HOLD_STRENGTH_BASE + (str_display * HOLD_STRENGTH_PER_STR // 10)
    victim.db.grapple_resist_cooldown = time.time()
    _apply_grappled_cmdset(victim)

    msg_room = lambda v: "%s grabs %s from %s and locks them in their grasp!" % (_combat_display_name(third_party, v), _combat_display_name(victim, v), _combat_display_name(grappler, v))
    return True, "You grab %s from %s and lock them in your grasp!" % (_combat_display_name(victim, third_party), _combat_display_name(grappler, third_party)), "%s grabs %s from you!" % (_combat_display_name(third_party, grappler), _combat_display_name(victim, grappler)), "%s grabs you from %s and has you in their grasp!" % (_combat_display_name(third_party, victim), _combat_display_name(grappler, victim)), msg_room


def release_grapple(grappler):
    """Release whoever grappler is holding. Returns (success, message)."""
    victim = getattr(grappler.db, "grappling", None)
    if not victim:
        return False, "You are not holding anyone."
    stop_grapple_strike_ticker(grappler, victim)
    grappler.db.grappling = None
    _clear_grappling_cmdset(grappler)
    if hasattr(victim.db, "grappled_by") and victim.db.grappled_by == grappler:
        victim.db.grappled_by = None
    for key in ("grapple_hold_strength", "grapple_resist_cooldown"):
        if hasattr(victim.db, key):
            victim.attributes.remove(key)
    _clear_grappled_cmdset(victim)
    return True, "You release {}.".format(_combat_display_name(victim, grappler))


def release_grapple_forced(grappler, room_message=None):
    """
    Force release (e.g. grappler flatlined or logged off). Clears grapple state;
    optionally announce room_message to location (exclude grappler and victim).
    Tell victim they are no longer held.
    """
    victim = getattr(grappler.db, "grappling", None)
    if not victim:
        return
    stop_grapple_strike_ticker(grappler, victim)
    grappler.db.grappling = None
    _clear_grappling_cmdset(grappler)
    if hasattr(victim.db, "grappled_by") and victim.db.grappled_by == grappler:
        victim.db.grappled_by = None
    for key in ("grapple_hold_strength", "grapple_resist_cooldown"):
        if hasattr(victim.db, key):
            victim.attributes.remove(key)
    _clear_grappled_cmdset(victim)
    if room_message and grappler.location:
        loc = grappler.location
        if hasattr(loc, "contents_get"):
            if callable(room_message):
                for v in loc.contents_get(content_type="character"):
                    if v in (grappler, victim):
                        continue
                    v.msg(room_message(v))
            else:
                loc.msg_contents(room_message, exclude=(grappler, victim))
        elif room_message:
            fallback = room_message(None) if callable(room_message) else room_message
            loc.msg_contents(fallback, exclude=(grappler, victim))
    if hasattr(victim, "msg"):
        victim.msg("You are no longer held.")


def attempt_resist(victim):
    """
    Victim tries to break free. Contested Strength + Unarmed.
    Grappler gets modifier from hold_strength; each attempt (even failed) degrades hold.
    Costs stamina; too exhausted to resist returns failure.
    Returns (freed: bool, message_for_victim: str, message_for_grappler: str).
    """
    grappler = getattr(victim.db, "grappled_by", None)
    if not grappler:
        return False, "You are not grappled.", ""
    now = time.time()
    last = getattr(victim.db, "grapple_resist_cooldown", 0) or 0
    if now - last < RESIST_COOLDOWN:
        return False, "You need a moment before you can try again.", ""
    try:
        from world.rpg.stamina import spend_stamina, STAMINA_COST_RESIST_GRAPPLE
        if (getattr(victim, "stamina", 0) or 0) < STAMINA_COST_RESIST_GRAPPLE:
            return False, "You're too tired to resist.", ""
        spend_stamina(victim, STAMINA_COST_RESIST_GRAPPLE)
    except ImportError:
        pass
    victim.db.grapple_resist_cooldown = now

    hold = int(getattr(victim.db, "grapple_hold_strength", 0))
    # Grappler's roll gets a bonus from hold strength
    g_result, g_val = _roll_result(grappler, ["strength"], "unarmed", modifier=hold)
    v_result, v_val = _roll_result(victim, ["strength"], "unarmed")
    # Degrade hold for next time (even if victim failed)
    victim.db.grapple_hold_strength = max(0, hold - HOLD_DEGRADE_PER_RESIST)

    if v_val > g_val:
        # Break free
        grappler.db.grappling = None
        _clear_grappling_cmdset(grappler)
        victim.db.grappled_by = None
        for key in ("grapple_hold_strength", "grapple_resist_cooldown"):
            if hasattr(victim.db, key):
                victim.attributes.remove(key)
        _clear_grappled_cmdset(victim)
        return True, "You wrench free of {}'s grasp!".format(_combat_display_name(grappler, victim)), "{} breaks free of your grasp!".format(_combat_display_name(victim, grappler))
    return False, "You strain but cannot break free yet. Your efforts weaken their hold.", "{} struggles but you keep hold.".format(_combat_display_name(victim, grappler))


def is_unconscious(character):
    """
    True if character is globally unconscious (trauma KO, OR anesthesia, drugs, etc.).

    Thin wrapper around world.medical.is_unconscious (db.unconscious).
    """
    from world.medical import is_unconscious as _is_unconscious

    return _is_unconscious(character)


def set_medical_unconscious_for_seconds(character, seconds):
    """
    Put character under for OR anesthesia (or equivalent). Uses the same global
    db.unconscious / unconscious_until and wake pipeline as trauma KO.
    """
    set_unconscious_for_seconds(character, seconds)


def force_wake_medical_unconscious(character, silent=False):
    """
    Wake from anesthesia (same global unconscious state as trauma KO).
    Clears OR sedation markers via force_wake_unconscious.
    """
    force_wake_unconscious(character, silent=silent)


def reconcile_grapple_cmdsets_after_reload(character):
    """
    After a server reload, re-apply grapple cmdsets from db state, or clear stale mutual refs.
    Called from Character.at_server_start (each online character).
    """
    if not character or not getattr(character, "db", None):
        return

    def _same_room(a, b):
        la = getattr(a, "location", None)
        lb = getattr(b, "location", None)
        return la is not None and la == lb

    grappling = getattr(character.db, "grappling", None)
    grappled_by = getattr(character.db, "grappled_by", None)

    if grappling:
        valid = (
            grappling
            and getattr(grappling.db, "grappled_by", None) == character
            and _same_room(character, grappling)
        )
        if not valid:
            character.db.grappling = None
            _clear_grappling_cmdset(character)
            try:
                if grappling and getattr(grappling.db, "grappled_by", None) == character:
                    grappling.db.grappled_by = None
                    _clear_grappled_cmdset(grappling)
            except Exception:
                pass
        else:
            free_hands_for_grapple(character, announce=False)
            _apply_grappling_cmdset(character)
            _apply_grappled_cmdset(grappling)

    if grappled_by:
        valid = (
            grappled_by
            and getattr(grappled_by.db, "grappling", None) == character
            and _same_room(character, grappled_by)
        )
        if not valid:
            character.db.grappled_by = None
            _clear_grappled_cmdset(character)
            try:
                if grappled_by and getattr(grappled_by.db, "grappling", None) == character:
                    grappled_by.db.grappling = None
                    _clear_grappling_cmdset(grappled_by)
            except Exception:
                pass
        else:
            _apply_grappled_cmdset(character)
            _apply_grappling_cmdset(grappled_by)


def reconcile_unconscious_state(character):
    """
    Repair unconscious state after reload/startup.

    - Legacy db.medical_unconscious* is merged into global db.unconscious until.
    - If still within the wake window, ensure cmdset and schedule _wake_unconscious_callback.
    """
    if not character or not getattr(character, "db", None):
        return
    db = character.db
    # One-time merge: old OR anesthesia used separate medical_* attributes.
    if bool(getattr(db, "medical_unconscious", False)):
        med_wake_at = float(getattr(db, "medical_unconscious_until", 0.0) or 0.0)
        now = time.time()
        if med_wake_at > now:
            db.unconscious = True
            old_u = float(getattr(db, "unconscious_until", 0.0) or 0.0)
            db.unconscious_until = max(old_u, med_wake_at)
        db.medical_unconscious = False
        db.medical_unconscious_until = 0.0

    is_uncon = bool(getattr(db, "unconscious", False))
    wake_at = float(getattr(db, "unconscious_until", 0.0) or 0.0)
    now = time.time()
    if is_uncon and wake_at > now:
        try:
            character.cmdset.add("commands.default_cmdsets.UnconsciousCmdSet")
        except Exception:
            pass
        delay(max(1.0, wake_at - now), _wake_unconscious_callback, character.id)
    elif is_uncon:
        db.unconscious = False
        db.unconscious_until = 0.0

    if not bool(getattr(db, "unconscious", False)):
        _restore_prev_room_pose_after_unconscious(character)
        _clear_operating_room_sedation(character)
        try:
            character.cmdset.remove("UnconsciousCmdSet")
        except Exception:
            pass


def grapple_strike(grappler, victim):
    """
    Attack the grappled victim: grappler spends stamina, victim loses STAMINA_DRAIN_GRAPPLE_STRIKE.
    If victim stamina hits 0, they are knocked out (unconscious), grapple is released, wake is scheduled.
    Logged-off (sleeping) victims cannot be attacked in the grapple — drag only.
    Returns (success: bool, message: str).
    """
    if not grappler or not victim:
        return False, "You cannot do that."
    held = getattr(grappler.db, "grappling", None)
    if held != victim:
        return False, "You are not holding them."
    try:
        from world.death import is_character_logged_off
        if is_character_logged_off(victim) and not getattr(victim.db, "is_npc", False):
            return False, "You can drag them, but you cannot attack someone who is not here."
    except ImportError:
        pass
    try:
        from world.rpg.stamina import spend_stamina, STAMINA_COST_GRAPPLE_STRIKE
        cur = getattr(grappler.db, "current_stamina", None)
        if (cur is None and hasattr(grappler, "max_stamina")):
            grappler.db.current_stamina = grappler.max_stamina
            cur = grappler.max_stamina
        cur = int(cur or 0)
        if cur < STAMINA_COST_GRAPPLE_STRIKE:
            return False, "You're too tired to keep strangling."
        spend_stamina(grappler, STAMINA_COST_GRAPPLE_STRIKE)
    except ImportError:
        pass

    # Drain victim stamina
    v_cur = getattr(victim.db, "current_stamina", None)
    if v_cur is None and hasattr(victim, "max_stamina"):
        victim.db.current_stamina = victim.max_stamina
        v_cur = victim.max_stamina
    v_cur = int(v_cur or 0)
    drain = min(v_cur, STAMINA_DRAIN_GRAPPLE_STRIKE)
    victim.db.current_stamina = max(0, v_cur - STAMINA_DRAIN_GRAPPLE_STRIKE)

    v_name_for_g = _combat_display_name(victim, grappler)
    g_name_for_v = _combat_display_name(grappler, victim)
    loc = grappler.location

    if victim.db.current_stamina <= 0:
        # Knock out: release grapple, set unconscious, schedule wake; stop strangle ticker
        stop_grapple_strike_ticker(grappler, victim)
        grappler.db.grappling = None
        _clear_grappling_cmdset(grappler)
        victim.db.grappled_by = None
        for key in ("grapple_hold_strength", "grapple_resist_cooldown"):
            if hasattr(victim.db, key):
                victim.attributes.remove(key)
        _clear_grappled_cmdset(victim)
        set_unconscious(victim)
        grappler.msg("" + CC["miss"] + "You choke %s until they go limp. They're out cold.|n" % v_name_for_g)
        if loc and hasattr(loc, "contents_get"):
            for v in loc.contents_get(content_type="character"):
                if v in (grappler, victim):
                    continue
                gv = _combat_display_name(grappler, v)
                vv = _combat_display_name(victim, v)
                v.msg("%s chokes %s until they go limp. %s is out cold." % (gv, vv, vv))
        return True, "They go limp. Out cold."

    grappler.msg("" + CC["miss"] + "You tighten your grip; %s gasps and sags.|n" % v_name_for_g)
    victim.msg("" + CC["miss"] + "%s's grip tightens; you gasp, strength fading.|n" % g_name_for_v)
    if loc and hasattr(loc, "contents_get"):
        for v in loc.contents_get(content_type="character"):
            if v in (grappler, victim):
                continue
            v.msg("%s strangles %s." % (_combat_display_name(grappler, v), _combat_display_name(victim, v)))
    return True, "You tighten your grip."

