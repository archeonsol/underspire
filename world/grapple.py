"""
Grapple system: three-step resolution (see it coming, land the grab, hold/resist).
Victim is 'locked in the grasp of' grappler; grappler can drag them when moving.
"""
import time

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


def _roll_result(character, stat_list, skill_name, modifier=0):
    """Return (result_string, final_result) from character's roll_check."""
    if not hasattr(character, "roll_check"):
        return "Failure", 0
    return character.roll_check(stat_list, skill_name, modifier=modifier)


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
    str_level = getattr(grappler, "get_stat_level", lambda x: 0)("strength") or 0
    victim.db.grapple_hold_strength = HOLD_STRENGTH_BASE + (str_level * HOLD_STRENGTH_PER_STR // 10)
    for key in ("lying_on_table", "sitting_on", "lying_on"):
        if hasattr(victim.db, key) and getattr(victim.db, key) is not None:
            del victim.db[key]
    return True, "You lock {} in your grasp.".format(victim.name)


def release_grapple(grappler):
    """Release whoever grappler is holding. Returns (success, message)."""
    victim = getattr(grappler.db, "grappling", None)
    if not victim:
        return False, "You are not holding anyone."
    grappler.db.grappling = None
    if hasattr(victim.db, "grappled_by") and victim.db.grappled_by == grappler:
        victim.db.grappled_by = None
    for key in ("grapple_hold_strength", "grapple_resist_cooldown"):
        if hasattr(victim.db, key):
            del victim.db[key]
    return True, "You release {}.".format(victim.name)


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
    last = getattr(victim.db, "grapple_resist_cooldown", 0)
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
                del victim.db[key]
        return True, "You wrench free of {}'s grasp!".format(grappler.name), "{} breaks free of your grasp!".format(victim.name)
    return False, "You strain but cannot break free yet. Your efforts weaken their hold.", "{} struggles but you keep hold.".format(victim.name)
