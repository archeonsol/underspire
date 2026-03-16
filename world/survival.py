"""
Survival systems: hunger, thirst, and intoxication.

Hunger/thirst:
- Stored on character.db.hunger / character.db.thirst (0-100; higher = better).
- Only drain in scavenging-tagged rooms (wildscavenge/urbanscavenge), on movement.
- Eating/drinking restores these and can buff stamina regen via last_nutritious_meal.

Alcohol:
- Character.db.blood_alcohol accumulates per drink (scaled by endurance).
- Drunk levels:
    0 = sober
    1 = tipsy
    2 = drunk (speech slurs)
    3 = wasted (speech slurs + staggered movement, see typeclasses.exits.Exit)
"""

import time

from world.scavenging import SCAVENGE_TAGS_WILD, SCAVENGE_TAGS_URBAN


HUNGER_MAX = 100
THIRST_MAX = 100

# How much hunger/thirst to lose per move in a scavenging room.
HUNGER_MOVE_COST = 1
THIRST_MOVE_COST = 2


def _clamp(val, low, high):
    return max(low, min(high, val))


def is_scavenge_room(room):
    """True if room is tagged as wilderness/urban scavenging."""
    if not room or not hasattr(room, "tags"):
        return False
    tags = set(room.tags.all())
    return bool(SCAVENGE_TAGS_WILD & tags or SCAVENGE_TAGS_URBAN & tags)


def apply_move_hunger_thirst(character, from_room, to_room):
    """
    Called on movement; only drains hunger/thirst if either room is a scavenge tile.
    """
    if not character or not getattr(character, "db", None):
        return
    if not (is_scavenge_room(from_room) or is_scavenge_room(to_room)):
        return
    hunger = int(getattr(character.db, "hunger", HUNGER_MAX) or HUNGER_MAX)
    thirst = int(getattr(character.db, "thirst", THIRST_MAX) or THIRST_MAX)

    # Endurance reduces per-move drain: higher END = smaller costs.
    end = 0
    if hasattr(character, "get_stat_level"):
        try:
            end = int(character.get_stat_level("endurance") or 0)
        except Exception:
            end = 0
    # Scale factor: END 0 -> 1.0, END 150 -> ~0.6, END 300 -> ~0.4
    scale = max(0.4, 1.0 - (end / 500.0))
    h_cost = max(0, int(round(HUNGER_MOVE_COST * scale)))
    t_cost = max(0, int(round(THIRST_MOVE_COST * scale)))

    hunger = _clamp(hunger - h_cost, 0, HUNGER_MAX)
    thirst = _clamp(thirst - t_cost, 0, THIRST_MAX)
    character.db.hunger = hunger
    character.db.thirst = thirst
    # Simple feedback at low levels (optional)
    if hunger <= 20:
        character.msg("|yYour stomach knots with hunger.|n")
    if thirst <= 20:
        character.msg("|yYour mouth is dry; you are getting thirsty.|n")


def apply_food_effects(character, food_obj):
    """
    Eating food: restore hunger and optionally mark last_nutritious_meal.
    Food can define:
      db.hunger_restore (int)
      db.is_nutritious (bool)
    """
    if not character or not getattr(character, "db", None):
        return
    hunger = int(getattr(character.db, "hunger", HUNGER_MAX) or HUNGER_MAX)
    restore = int(getattr(getattr(food_obj, "db", None), "hunger_restore", 15) or 15)
    character.db.hunger = _clamp(hunger + restore, 0, HUNGER_MAX)
    if getattr(getattr(food_obj, "db", None), "is_nutritious", True):
        character.db.last_nutritious_meal = time.time()


def apply_drink_effects(character, drink_obj):
    """
    Drinking: restore thirst, and if alcoholic, adjust intoxication.
    Drinks can define:
      db.thirst_restore (int)  # ignored for alcohol
      db.alcohol_strength (float)  # per-drink alcohol value
    """
    if not character or not getattr(character, "db", None):
        return
    thirst_restore = int(getattr(getattr(drink_obj, "db", None), "thirst_restore", 20) or 20)
    alcohol_strength = float(getattr(getattr(drink_obj, "db", None), "alcohol_strength", 0.0) or 0.0)

    # Non-alcoholic: restore thirst normally
    if alcohol_strength <= 0.0:
        thirst = int(getattr(character.db, "thirst", THIRST_MAX) or THIRST_MAX)
        character.db.thirst = _clamp(thirst + thirst_restore, 0, THIRST_MAX)
    # Alcohol: no thirst benefit, adjust intoxication
    update_intoxication(character, alcohol_strength)


def _drunk_thresholds_for(character):
    """
    Compute thresholds for tipsy/drunk/wasted based on endurance.
    Higher endurance -> higher thresholds.
    """
    end = 0
    if hasattr(character, "get_stat_level"):
        try:
            end = int(character.get_stat_level("endurance") or 0)
        except Exception:
            end = 0
    # Base thresholds and endurance scaling
    base1, base2, base3 = 10.0, 20.0, 35.0
    scale = 1.0 + (end / 300.0)  # endurance 0 -> 1.0x, 300 -> 2.0x
    return base1 * scale, base2 * scale, base3 * scale


def update_intoxication(character, alcohol_delta):
    """
    Increase blood_alcohol, recalc drunk_level thresholds (0-3), and message on changes.
    """
    if not character or not getattr(character, "db", None):
        return
    bac = float(getattr(character.db, "blood_alcohol", 0.0) or 0.0)
    bac += float(alcohol_delta or 0.0)
    # Simple decay over time could be added later; for now just cap.
    bac = max(0.0, min(100.0, bac))
    t1, t2, t3 = _drunk_thresholds_for(character)

    def _level_for(val):
        if val < t1:
            return 0
        if val < t2:
            return 1
        if val < t3:
            return 2
        return 3

    old_level = int(getattr(character.db, "drunk_level", 0) or 0)
    new_level = _level_for(bac)
    character.db.blood_alcohol = bac
    character.db.drunk_level = new_level

    if new_level > old_level:
        if new_level == 1:
            character.msg("|yYou feel a warm fuzziness creeping in — you're getting tipsy.|n")
        elif new_level == 2:
            character.msg("|yThe room sways a little; your thoughts and tongue feel heavy.|n")
        elif new_level == 3:
            character.msg("|rYou are completely wasted. The world tilts and your steps wander.|n")


def slur_text_if_drunk(character, text):
    """
    Lightly slur text for mid/high drunkenness (levels 2-3).
    We randomly duplicate letters, swap some vowels, and drop a few letters.
    """
    if not text or not character or not getattr(character, "db", None):
        return text
    level = int(getattr(character.db, "drunk_level", 0) or 0)
    if level < 2:
        return text
    import random

    # Slur intensity: level 2 = mild, level 3 = stronger
    dup_chance = 0.05 if level == 2 else 0.12
    drop_chance = 0.02 if level == 2 else 0.06
    swap_chance = 0.03 if level == 2 else 0.08

    vowels = "aeiouAEIOU"
    vowel_swaps = {
        "a": "aa", "e": "ee", "i": "ii", "o": "oo", "u": "uu",
        "A": "Aa", "E": "Ee", "I": "Ii", "O": "Oo", "U": "Uu",
    }

    out = []
    for ch in text:
        # Skip slurring inside quotes so speech content stays mostly readable
        out.append(ch)
    raw = "".join(out)
    result = []
    in_quote = False
    for ch in raw:
        if ch == '"':
            in_quote = not in_quote
            result.append(ch)
            continue
        if in_quote:
            result.append(ch)
            continue
        r = random.random()
        # Occasionally drop characters (mostly consonants)
        if r < drop_chance and ch.isalpha() and ch.lower() not in "aeiou":
            continue
        # Occasionally swap vowels to double them
        if ch in vowels and random.random() < swap_chance:
            result.append(vowel_swaps.get(ch, ch))
            continue
        # Occasionally duplicate letters
        if random.random() < dup_chance and ch.isalpha():
            result.append(ch * 2)
            continue
        result.append(ch)
    return "".join(result)

