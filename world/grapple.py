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
UNCONSCIOUS_WAKE_MIN = 10   # seconds
UNCONSCIOUS_WAKE_MAX = 30   # seconds (endurance scales within this range)

# Unarmed flat bonus for holding/contesting the grapple (third party grab and defender both use it).
GRAPPLE_UNARMED_BONUS = 5


def _roll_result(character, stat_list, skill_name, modifier=0):
    """Return (result_string, final_result) from character's roll_check."""
    if not hasattr(character, "roll_check"):
        return "Failure", 0
    return character.roll_check(stat_list, skill_name, modifier=modifier)


def _resolve_grapple_callback(grappler_id, victim_id):
    """Called after GRAPPLE_DELAY: run the roll and send phase-2 messages."""
    try:
        g = search_object("#%s" % grappler_id)
        v = search_object("#%s" % victim_id)
        if not g or not v:
            return
        grappler, victim = g[0], v[0]
    except Exception:
        return
    if not grappler or not victim or grappler.location != victim.location:
        if hasattr(grappler, "msg") and grappler:
            grappler.msg("|yThe moment passed; the grapple doesn't connect.|n")
        return
    if getattr(victim.db, "grappled_by", None) or getattr(grappler.db, "grappling", None):
        if hasattr(grappler, "msg") and grappler:
            grappler.msg("|yThey're no longer in a position to be grappled.|n")
        return
    success, msg = attempt_grapple(grappler, victim)
    loc = grappler.location
    if success:
        grappler.msg("|g%s|n" % msg)
        if victim != grappler:
            victim.msg("|r%s has you locked in their grasp! You can try |wresist|n to break free.|n" % grappler.name)
        if loc:
            loc.msg_contents(
                "%s locks %s in their grasp." % (grappler.name, victim.name),
                exclude=(grappler, victim),
            )
    else:
        grappler.msg("|r%s|n" % msg)
        victim.msg("|gYou slip free of %s's grab!|n" % grappler.name)
        if loc:
            loc.msg_contents(
                "%s grabs at %s but %s slips free." % (grappler.name, victim.name, victim.name),
                exclude=(grappler, victim),
            )


def start_grapple_attempt(grappler, victim):
    """
    Phase 1: validate, send tense/lunge messages, then schedule resolution after 3–4s.
    Returns (started: bool, error_message: str or None).
    """
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
        from world.death import is_flatlined, is_permanently_dead, is_character_logged_off
        if is_flatlined(victim) or is_permanently_dead(victim):
            return False, "You cannot grapple the dead."
        if is_character_logged_off(victim) and not getattr(victim.db, "is_npc", False):
            return False, "You cannot grapple someone who is not here."
    except ImportError:
        pass

    g_name = grappler.name
    v_name = victim.name

    # Phase 1: grappler sees lunge; room sees tense + lunge; target sees tense then lunge
    grappler.msg("|rYou lunge towards %s!|n" % v_name)
    victim.msg("|yYou see %s tense up!|n" % g_name)
    victim.msg("|r%s lunges towards you!|n" % g_name)
    if grappler.location:
        grappler.location.msg_contents(
            "%s tenses up and lunges towards %s!" % (g_name, v_name),
            exclude=(grappler, victim),
        )

    sec = random.uniform(GRAPPLE_DELAY_MIN, GRAPPLE_DELAY_MAX)
    delay(sec, _resolve_grapple_callback, grappler.id, victim.id)
    return True, None


def _resolve_third_party_grapple_callback(third_party_id, victim_id):
    """Called after GRAPPLE_DELAY: run the contested roll and send result messages."""
    try:
        tp = search_object("#%s" % third_party_id)
        v = search_object("#%s" % victim_id)
        if not tp or not v:
            return
        third_party, victim = tp[0], v[0]
    except Exception:
        return
    if not third_party or not victim or third_party.location != victim.location:
        if hasattr(third_party, "msg") and third_party:
            third_party.msg("|yThe moment passed; the grapple doesn't connect.|n")
        return
    grappler = getattr(victim.db, "grappled_by", None)
    if not grappler or getattr(grappler.db, "grappling", None) != victim:
        if hasattr(third_party, "msg") and third_party:
            third_party.msg("|yThey're no longer in a position to be grappled.|n")
        return
    success, msg_you, msg_grappler, msg_victim, msg_room = attempt_grapple_third_party(third_party, victim)
    third_party.msg("|g%s|n" % msg_you if success else "|r%s|n" % msg_you)
    if grappler and hasattr(grappler, "msg"):
        grappler.msg("|r%s|n" % msg_grappler if success else "|y%s|n" % msg_grappler)
    if victim and hasattr(victim, "msg"):
        victim.msg("|y%s|n" % msg_victim)
    if msg_room and third_party.location:
        third_party.location.msg_contents(msg_room, exclude=(third_party, victim, grappler))


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
    if third_party.location != victim.location or grappler.location != victim.location:
        return False, "You need to be in the same place."
    tp_name = third_party.name
    v_name = victim.name
    g_name = grappler.name
    loc = third_party.location
    # Phase 1: lunge messages (third_party = you, victim = target, grappler = current holder)
    third_party.msg("|rYou lunge towards %s, trying to pull them from %s's grasp!|n" % (v_name, g_name))
    victim.msg("|yYou see %s tense up!|n" % tp_name)
    victim.msg("|r%s lunges towards you!|n" % tp_name)
    grappler.msg("|yYou see %s tense up and lunge towards %s!|n" % (tp_name, v_name))
    if loc:
        loc.msg_contents(
            "%s tenses up and lunges towards %s!" % (tp_name, v_name),
            exclude=(third_party, victim, grappler),
        )
    sec = random.uniform(GRAPPLE_DELAY_MIN, GRAPPLE_DELAY_MAX)
    delay(sec, _resolve_third_party_grapple_callback, third_party.id, victim.id)
    return True, None


def attempt_grapple(grappler, victim):
    """
    Step 1: Agility (grappler) + unarmed slightly vs Perception (victim).
    Step 2: Agility vs Agility, both use evasion; step 1 result adds buff.
    Returns (success: bool, message: str).
    """
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
        from world.death import is_flatlined, is_permanently_dead, is_character_logged_off
        if is_flatlined(victim) or is_permanently_dead(victim):
            return False, "You cannot grapple the dead."
        if is_character_logged_off(victim) and not getattr(victim.db, "is_npc", False):
            return False, "You cannot grapple someone who is not here."
    except ImportError:
        pass

    # Auto-succeed if victim is sitting or lying (on seat, bed, or operating table)
    is_seated = getattr(victim.db, "sitting_on", None) is not None
    is_lying_on = getattr(victim.db, "lying_on", None) is not None
    is_on_table = getattr(victim.db, "lying_on_table", None) is not None
    if not (is_seated or is_lying_on or is_on_table):
        r1, v1 = _roll_result(grappler, ["agility"], "unarmed", modifier=5)
        r2, v2 = _roll_result(victim, ["perception"], "evasion")
        step1_attacker_won = v1 > v2

        # Step 2: Agility vs Agility, both evasion; apply step 1 buffs
        mod_grappler = STEP1_ATTACKER_BUFF if step1_attacker_won else -STEP1_DEFENDER_BUFF
        mod_victim = STEP1_DEFENDER_BUFF if not step1_attacker_won else -STEP1_ATTACKER_BUFF
        g2, vg2 = _roll_result(grappler, ["agility"], "evasion", modifier=mod_grappler)
        g2v, vv2 = _roll_result(victim, ["agility"], "evasion", modifier=mod_victim)

        if vg2 <= vv2:
            return False, "You grab at them but they slip free. The grapple fails."

    # Grapple lands: set state and clear sitting/lying/table
    victim.db.grappled_by = grappler
    grappler.db.grappling = victim
    str_display = getattr(grappler, "get_display_stat", lambda x: 0)("strength") or 0
    victim.db.grapple_hold_strength = HOLD_STRENGTH_BASE + (str_display * HOLD_STRENGTH_PER_STR // 10)
    for key in ("lying_on_table", "sitting_on", "lying_on"):
        if hasattr(victim.db, key) and getattr(victim.db, key) is not None:
            victim.attributes.remove(key)
    return True, "You lock {} in your grasp.".format(victim.name)


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
    """Start the recurring strangle ticker (every GRAPPLE_STRIKE_INTERVAL seconds)."""
    if not grappler or not victim or getattr(grappler.db, "grappling", None) != victim:
        return
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
        msg_room = "%s tries to grab %s from %s but %s bats their attempts away." % (
            third_party.name, victim.name, grappler.name, grappler.name,
        )
        return False, "They bat away your attempts.", "They try to grab %s from you but you bat their attempts away." % victim.name, "%s tries to grab you from %s but %s bats their attempts away." % (third_party.name, grappler.name, grappler.name), msg_room

    # Success: transfer grapple. Stop any strangle ticker on the old grappler first.
    stop_grapple_strike_ticker(grappler, victim)
    grappler.db.grappling = None
    victim.db.grappled_by = None
    for key in ("grapple_hold_strength", "grapple_resist_cooldown"):
        if hasattr(victim.db, key):
            victim.attributes.remove(key)
    # New grapple: third_party now holds victim
    victim.db.grappled_by = third_party
    third_party.db.grappling = victim
    str_display = getattr(third_party, "get_display_stat", lambda x: 0)("strength") or 0
    victim.db.grapple_hold_strength = HOLD_STRENGTH_BASE + (str_display * HOLD_STRENGTH_PER_STR // 10)
    victim.db.grapple_resist_cooldown = time.time()

    msg_room = "%s grabs %s from %s and locks them in their grasp!" % (third_party.name, victim.name, grappler.name)
    return True, "You grab %s from %s and lock them in your grasp!" % (victim.name, grappler.name), "%s grabs %s from you!" % (third_party.name, victim.name), "%s grabs you from %s and has you in their grasp!" % (third_party.name, grappler.name), msg_room


def release_grapple(grappler):
    """Release whoever grappler is holding. Returns (success, message)."""
    victim = getattr(grappler.db, "grappling", None)
    if not victim:
        return False, "You are not holding anyone."
    stop_grapple_strike_ticker(grappler, victim)
    grappler.db.grappling = None
    if hasattr(victim.db, "grappled_by") and victim.db.grappled_by == grappler:
        victim.db.grappled_by = None
    for key in ("grapple_hold_strength", "grapple_resist_cooldown"):
        if hasattr(victim.db, key):
            victim.attributes.remove(key)
    return True, "You release {}.".format(victim.name)


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
    if hasattr(victim.db, "grappled_by") and victim.db.grappled_by == grappler:
        victim.db.grappled_by = None
    for key in ("grapple_hold_strength", "grapple_resist_cooldown"):
        if hasattr(victim.db, key):
            victim.attributes.remove(key)
    if room_message and grappler.location:
        grappler.location.msg_contents(room_message, exclude=(grappler, victim))
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
        from world.stamina import is_exhausted, spend_stamina, STAMINA_COST_RESIST_GRAPPLE
        if is_exhausted(victim):
            return False, "You're too tired to resist.", ""
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
        victim.db.grappled_by = None
        for key in ("grapple_hold_strength", "grapple_resist_cooldown"):
            if hasattr(victim.db, key):
                victim.attributes.remove(key)
        return True, "You wrench free of {}'s grasp!".format(grappler.name), "{} breaks free of your grasp!".format(victim.name)
    return False, "You strain but cannot break free yet. Your efforts weaken their hold.", "{} struggles but you keep hold.".format(victim.name)


def is_unconscious(character):
    """True if character is in the knocked-out state (0 stamina from grapple strikes)."""
    return bool(getattr(character.db, "unconscious", False))


def get_unconscious_wake_seconds(character):
    """Wake duration in seconds: min UNCONSCIOUS_WAKE_MIN, max UNCONSCIOUS_WAKE_MAX, scaled by endurance (high = faster wake)."""
    end = 0
    if hasattr(character, "get_stat_level"):
        end = character.get_stat_level("endurance") or 0
    # endurance 0 -> 30s, endurance 300 -> 10s; linear
    ratio = min(1.0, max(0.0, (end or 0) / 300.0))
    return max(UNCONSCIOUS_WAKE_MIN, min(UNCONSCIOUS_WAKE_MAX, UNCONSCIOUS_WAKE_MAX - ratio * (UNCONSCIOUS_WAKE_MAX - UNCONSCIOUS_WAKE_MIN)))


def _wake_unconscious_callback(character_id):
    """Scheduled when setting unconscious; removes unconscious state and cmdset, messages character."""
    try:
        result = search_object("#%s" % character_id)
        if not result:
            return
        character = result[0]
    except Exception:
        return
    if not getattr(character.db, "unconscious", False):
        return
    character.db.unconscious = False
    prev_pose = getattr(character.db, "_unconscious_prev_room_pose", None)
    if prev_pose is not None:
        character.db.room_pose = prev_pose
        try:
            character.attributes.remove("_unconscious_prev_room_pose")
        except Exception:
            pass
    try:
        character.cmdset.remove("UnconsciousCmdSet")
    except Exception:
        pass
    character.msg("|gYou groggily come to.|n")
    if character.location:
        character.location.msg_contents(
            "%s groggily comes to." % character.name,
            exclude=(character,),
        )


def set_unconscious(character):
    """
    Put character in knocked-out state: lock commands (UnconsciousCmdSet), set room pose, schedule wake.
    Call after grapple strike drains their stamina to 0.
    """
    if not character or not getattr(character, "db", None):
        return
    character.db.unconscious = True
    character.db._unconscious_prev_room_pose = getattr(character.db, "room_pose", None) or "standing here"
    character.db.room_pose = "lying here, unconscious"
    try:
        character.cmdset.add("commands.default_cmdsets.UnconsciousCmdSet")
    except Exception:
        pass
    secs = get_unconscious_wake_seconds(character)
    delay(secs, _wake_unconscious_callback, character.id)


def grapple_strike(grappler, victim):
    """
    Attack the grappled victim: grappler spends stamina, victim loses STAMINA_DRAIN_GRAPPLE_STRIKE.
    If victim stamina hits 0, they are knocked out (unconscious), grapple is released, wake is scheduled.
    Returns (success: bool, message: str).
    """
    if not grappler or not victim:
        return False, "You cannot do that."
    held = getattr(grappler.db, "grappling", None)
    if held != victim:
        return False, "You are not holding them."
    try:
        from world.stamina import is_exhausted, spend_stamina, STAMINA_COST_GRAPPLE_STRIKE
        if is_exhausted(grappler):
            return False, "You're too tired to keep strangling."
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

    g_name = grappler.name
    v_name = victim.name
    loc = grappler.location

    if victim.db.current_stamina <= 0:
        # Knock out: release grapple, set unconscious, schedule wake; stop strangle ticker
        stop_grapple_strike_ticker(grappler, victim)
        grappler.db.grappling = None
        victim.db.grappled_by = None
        for key in ("grapple_hold_strength", "grapple_resist_cooldown"):
            if hasattr(victim.db, key):
                victim.attributes.remove(key)
        set_unconscious(victim)
        grappler.msg("|rYou choke %s until they go limp. They're out cold.|n" % v_name)
        if loc:
            loc.msg_contents(
                "%s chokes %s until they go limp. %s is out cold." % (g_name, v_name, v_name),
                exclude=(grappler, victim),
            )
        return True, "They go limp. Out cold."

    grappler.msg("|rYou tighten your grip; %s gasps and sags.|n" % v_name)
    victim.msg("|r%s's grip tightens; you gasp, strength fading.|n" % g_name)
    if loc:
        loc.msg_contents(
            "%s strangles %s." % (g_name, v_name),
            exclude=(grappler, victim),
        )
    return True, "You tighten your grip."
