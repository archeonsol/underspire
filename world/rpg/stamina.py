"""
Stamina system: actions cost stamina; regen varies by posture and recent nutrition.
Stamina is tied to endurance (max_stamina on Character). At 0 stamina you crawl
and cannot attack or defend.
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
STAMINA_REGEN_INTERVAL = 25
STAMINA_REGEN_BASE = 2
STAMINA_REGEN_SITTING = 4   # extra points when sitting
STAMINA_REGEN_LYING = 6     # extra points when lying (bed/table)
# Recent nutritious meal: multiplier for regen (e.g. 1.5 = 50% faster) for N minutes
NUTRITION_REGEN_MULTIPLIER = 1.5
NUTRITION_BUFF_MINUTES = 10


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
    """True if character has 0 or less stamina (crawling, cannot fight)."""
    return _current(character) <= 0


def can_fight(character):
    """True if character has stamina to attack or defend."""
    return not is_exhausted(character)


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
        if getattr(character.db, "lying_on", None) is not None or getattr(character.db, "lying_on_table", None) is not None:
            rate += STAMINA_REGEN_LYING
        elif getattr(character.db, "sitting_on", None) is not None:
            rate += STAMINA_REGEN_SITTING
        last_meal = getattr(character.db, "last_nutritious_meal", None)
        if last_meal and (time.time() - last_meal) < (NUTRITION_BUFF_MINUTES * 60):
            rate = int(rate * NUTRITION_REGEN_MULTIPLIER)
    return max(1, rate)


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

    # Posture: sitting or lying improves recovery (can partially offset penalties)
    if getattr(character.db, "lying_on", None) is not None or getattr(character.db, "lying_on_table", None) is not None:
        score += 2
    elif getattr(character.db, "sitting_on", None) is not None:
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
