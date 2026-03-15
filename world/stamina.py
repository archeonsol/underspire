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
