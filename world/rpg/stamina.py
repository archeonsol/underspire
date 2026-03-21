"""
Stamina system: actions cost stamina; regen varies by endurance, posture, and
recent nutrition. At very low stamina you become winded/exhausted and take
combat penalties instead of hitting a hard action lockout.
"""
import time

# Costs per action (deducted when the action is taken)
STAMINA_COST_WALK = 1
STAMINA_COST_CRAWL = 0   # Crawling is slow; no extra drain (you're already exhausted)
STAMINA_COST_ATTACK = 8
STAMINA_COST_DEFEND = 5
STAMINA_COST_RESIST_GRAPPLE = 12
STAMINA_COST_GRAPPLE_STRIKE = 5   # grappler spends this per strike while holding someone

# Regen: interval (seconds) and points per tick
STAMINA_REGEN_INTERVAL = 10
STAMINA_REGEN_BASE = 2
STAMINA_REGEN_SITTING = 2   # extra points when sitting
STAMINA_REGEN_LYING = 3     # extra points when lying (bed/table)
STAMINA_REGEN_COMBAT = 1    # reduced but nonzero regen while actively in combat
# Recent nutritious meal: multiplier for regen (e.g. 1.5 = 50% faster) for N minutes
NUTRITION_REGEN_MULTIPLIER = 1.5
NUTRITION_BUFF_MINUTES = 10
HYDRATION_REGEN_MULTIPLIER = 1.2
HYDRATION_BUFF_MINUTES = 5
STAMINA_WINDED_THRESHOLD = 0.2


def _current(character):
    """Return current stamina value (int), initializing from max if None."""
    if not character or not getattr(character, "db", None):
        return 0
    cur = character.db.current_stamina
    if cur is None and hasattr(character, "max_stamina"):
        character.db.current_stamina = character.max_stamina
        return character.db.current_stamina
    return int(cur) if cur is not None else 0


def is_exhausted(character):
    """True if character has 0 or less stamina."""
    return _current(character) <= 0


def can_fight(character):
    """
    Combat is no longer hard-locked by stamina.
    Exhausted characters can still act, but with severe penalties.
    """
    return bool(character)


def spend_stamina(character, amount):
    """
    Deduct stamina; clamp to 0. Returns True if the full amount was spent,
    False if character had less (and is now at 0).
    """
    if not character or not getattr(character, "db", None) or amount <= 0:
        return True
    cur = _current(character)
    character.db.current_stamina = max(0, cur - amount)
    return cur >= amount


def get_regen_rate(character):
    """
    Stamina points added per regen tick. Base + bonus for sitting/lying
    + multiplier for recent nutritious meal.
    """
    rate = STAMINA_REGEN_BASE
    if getattr(character, "db", None):
        max_stam = getattr(character, "max_stamina", 100) or 100
        endurance_bonus = max(0, (max_stam - 75)) // 25
        rate += endurance_bonus

        if getattr(character.db, "lying_on", None) is not None or getattr(character.db, "lying_on_table", None) is not None:
            rate += STAMINA_REGEN_LYING
        elif getattr(character.db, "sitting_on", None) is not None:
            rate += STAMINA_REGEN_SITTING

        # Medical state directly affects stamina recovery.
        try:
            from world.medical import get_infection_penalties
            organ_damage = getattr(character.db, "organ_damage", None) or {}
            lung_sev = int(organ_damage.get("lungs", 0) or 0)
            heart_sev = int(organ_damage.get("heart", 0) or 0)
            rate -= (lung_sev + heart_sev)
            inf = get_infection_penalties(character)
            rate += int(inf.get("stamina_recovery", 0) or 0)
        except Exception:
            pass

        cyber = list(getattr(character.db, "cyberware", None) or [])
        from typeclasses.cyberware_catalog import CardioPulmonaryBooster, MetabolicRegulator
        has_cardio = any(isinstance(cw, CardioPulmonaryBooster) and not bool(getattr(cw.db, "malfunctioning", False)) for cw in cyber)
        has_metabolic = any(isinstance(cw, MetabolicRegulator) and not bool(getattr(cw.db, "malfunctioning", False)) for cw in cyber)
        if has_cardio:
            rate += 2
        if has_metabolic:
            rate += 1

        last_meal = getattr(character.db, "last_nutritious_meal", None)
        last_drink = getattr(character.db, "last_hydrating_drink", None)
        if (not has_metabolic) and last_meal and (time.time() - last_meal) < (NUTRITION_BUFF_MINUTES * 60):
            rate = int(rate * NUTRITION_REGEN_MULTIPLIER)

        if last_drink and (time.time() - last_drink) < (HYDRATION_BUFF_MINUTES * 60):
            rate = int(rate * HYDRATION_REGEN_MULTIPLIER)

        # Hunger/thirst directly affect stamina recovery quality.
        hunger = int(getattr(character.db, "hunger", 100) or 100)
        thirst = int(getattr(character.db, "thirst", 100) or 100)
        if hunger <= 25:
            rate -= 1
        elif hunger >= 70:
            rate += 1
        if thirst <= 25:
            rate -= 1
        elif thirst >= 70:
            rate += 1
    return max(1, rate)


def get_stamina_modifier(character):
    """Combat modifier when stamina is low. 0 = no penalty."""
    cur = _current(character)
    mx = getattr(character, "max_stamina", 100) or 100
    if cur <= 0:
        return -20
    ratio = (cur / mx) if mx > 0 else 0
    if ratio < STAMINA_WINDED_THRESHOLD:
        return -8
    return 0


# Recovery condition tiers: 0 = very slowly .. 4 = very well. Default is 2 (moderately).
STAMINA_RECOVERY_LABELS = (
    "recovering very slowly",
    "recovering slowly",
    "recovering moderately",
    "recovering well",
    "recovering very well",
)


def get_stamina_recovery_label(character):
    """
    Stamina recovery as a condition: base is moderately. Goes down when bleeding
    or injured; goes up when sitting or lying. When actively fighting, this reports
    a special "physically active" state instead of implying your stamina is barely
    recovering at all.
    """
    if not character or not getattr(character, "db", None):
        return STAMINA_RECOVERY_LABELS[2]
    score = 2  # default: recovering moderately

    # Actively doing something physical: burning stamina rather than "recovering".
    # Show a dedicated label instead of implying terrible regen.
    is_in_combat = getattr(character.db, "combat_target", None) is not None
    is_sneaking = getattr(character.db, "is_sneaking", False)
    is_hiding = getattr(character.db, "is_hiding", False)
    is_running = getattr(character.db, "is_running", False)
    is_climbing = getattr(character.db, "is_climbing", False)
    is_swimming = getattr(character.db, "is_swimming", False)
    if any((is_in_combat, is_sneaking, is_hiding, is_running, is_climbing, is_swimming)):
        return "physically active"

    # Bleeding: worse bleeding pulls recovery down
    try:
        from world.medical import compute_effective_bleed_level
        bleeding, _ = compute_effective_bleed_level(character)
    except Exception:
        bleeding = getattr(character.db, "bleeding_level", 0) or 0
    if bleeding >= 4:
        score -= 2
    elif bleeding >= 2:
        score -= 1

    # Trauma: fractures, organ damage, or multiple untreated injuries pull down
    fractures = getattr(character.db, "fractures", None) or []
    organ_damage = getattr(character.db, "organ_damage", None) or {}
    injuries = getattr(character.db, "injuries", None) or []
    untreated = sum(1 for i in injuries if not i.get("treated") and (i.get("hp_occupied") or 0) > 0)
    if fractures or organ_damage or untreated >= 2:
        score -= 1

    # Infection burden slows recovery further.
    try:
        from world.medical import get_infection_penalties
        inf = get_infection_penalties(character)
        if int(inf.get("stamina_recovery", 0) or 0) < 0:
            score -= 1
    except Exception:
        pass

    # Posture: sitting or lying improves recovery (can partially offset penalties)
    if getattr(character.db, "lying_on", None) is not None or getattr(character.db, "lying_on_table", None) is not None:
        score += 2
    elif getattr(character.db, "sitting_on", None) is not None:
        score += 1

    # Nutrition/hydration visibly improve stamina recovery.
    now = time.time()
    last_meal = getattr(character.db, "last_nutritious_meal", None)
    last_drink = getattr(character.db, "last_hydrating_drink", None)
    if last_meal and (now - last_meal) < (NUTRITION_BUFF_MINUTES * 60):
        score += 1
    if last_drink and (now - last_drink) < (HYDRATION_BUFF_MINUTES * 60):
        score += 1

    hunger = int(getattr(character.db, "hunger", 100) or 100)
    thirst = int(getattr(character.db, "thirst", 100) or 100)
    if hunger <= 25:
        score -= 1
    elif hunger >= 70:
        score += 1
    if thirst <= 25:
        score -= 1
    elif thirst >= 70:
        score += 1

    score = max(0, min(4, score))
    return STAMINA_RECOVERY_LABELS[score]


def tick_stamina_regen(character):
    """
    Add one tick of stamina regen; cap at max_stamina. Only ticks characters
    that are in the world (have a location). NPCs tick too.
    """
    if not character or not getattr(character, "location", None) or character.location is None:
        return
    if not getattr(character, "max_stamina", None):
        return
    cur = _current(character)
    mx = character.max_stamina
    if cur >= mx:
        return
    gain = get_regen_rate(character)
    if getattr(character.db, "combat_target", None) is not None:
        gain = STAMINA_REGEN_COMBAT
    character.db.current_stamina = min(mx, cur + gain)


def stamina_regen_all():
    """Call tick_stamina_regen for every Character in the game (with a location)."""
    try:
        from evennia.objects.models import ObjectDB
        for obj in ObjectDB.objects.filter(db_location__isnull=False):
            try:
                if hasattr(obj, "max_stamina") and hasattr(obj, "db"):
                    tick_stamina_regen(obj)
            except Exception:
                pass
    except Exception:
        pass
