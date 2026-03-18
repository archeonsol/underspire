"""
Armor stacking, damage reduction (coin-flip loop), and degradation.
Used by the wear command (stacking/layer checks) and combat (reduction + quality loss).
"""
import random

from world.clothing import get_worn_items
from world.combat.damage_types import DAMAGE_TYPES

# Maximum total stacking_score a character can wear. Exceeding blocks wear.
MAX_ARMOR_STACKING_SCORE = 24


def _is_armor(obj):
    """True if obj is an Armor typeclass (has armor_layer and protection)."""
    return getattr(obj, "get_armor_layer", None) is not None and getattr(obj, "get_protection", None) is not None


def get_worn_armor(character):
    """Return list of worn items that are Armor, in wear order (bottom to top)."""
    if not character:
        return []
    return [obj for obj in get_worn_items(character) if _is_armor(obj)]


def get_worn_armor_stack_total(character):
    """Sum stacking_score of all currently worn armor. Used to enforce MAX_ARMOR_STACKING_SCORE."""
    return sum(obj.get_stacking_score() for obj in get_worn_armor(character))


def get_armor_protection_for_location(character, body_part, damage_type):
    """
    Sum effective protection (quality-scaled) for the given damage type across all
    worn armor that covers body_part. Returns (total_protection, list of armor objects).
    """
    total = 0
    pieces = []
    for obj in get_worn_armor(character):
        parts = obj.get_covered_parts() if hasattr(obj, "get_covered_parts") else (getattr(obj.db, "covered_parts", None) or [])
        if body_part not in parts:
            continue
        p = obj.get_protection(damage_type) if hasattr(obj, "get_protection") else 0
        if p > 0:
            total += p
            pieces.append(obj)
    return total, pieces


def compute_armor_reduction(total_protection, incoming_damage):
    """
    Coin-flip loop: for each point of armor, 50% chance to block 1 damage.
    Returns (reduction_amount, absorbed_fully).
    """
    if total_protection <= 0 or incoming_damage <= 0:
        return 0, False
    successes = sum(1 for _ in range(total_protection) if random.choice([0, 1]) == 1)
    reduction = min(successes, incoming_damage)
    absorbed_fully = reduction >= incoming_damage
    return reduction, absorbed_fully


def degrade_armor(armor_pieces, damage_type, reduction_amount):
    """
    When armor blocks damage, reduce quality on each piece that contributed.
    reduction_amount is how much was actually blocked; spread degradation across pieces.
    """
    if not armor_pieces or reduction_amount <= 0:
        return
    # Each piece that contributed takes some quality loss (e.g. 1 point per 5 blocked, min 1)
    loss_per_piece = max(1, reduction_amount // max(1, len(armor_pieces)))
    for obj in armor_pieces:
        q = max(0, int(getattr(obj.db, "quality", 100) or 100) - loss_per_piece)
        obj.db.quality = max(0, q)


def repair_armor(armor_obj, amount):
    """
    Restore quality on an armor piece (e.g. after arms_tech + tools). Caps at 100.
    Call from a repair command or item use. amount can be negative (damage).
    """
    if not armor_obj or not getattr(armor_obj, "db", None):
        return
    q = max(0, min(100, int(getattr(armor_obj.db, "quality", 100) or 100) + amount))
    armor_obj.db.quality = q


def check_layer_warning(character, new_item):
    """
    If new_item is armor and has a lower layer than something already worn on the same
    body part, return (True, higher_item) so caller can warn. Else return (False, None).
    """
    if not _is_armor(new_item):
        return False, None
    new_layer = new_item.get_armor_layer()
    new_parts = set(new_item.get_covered_parts())
    if not new_parts:
        return False, None
    for obj in get_worn_armor(character):
        if obj == new_item:
            continue
        existing_layer = obj.get_armor_layer()
        if existing_layer <= new_layer:
            continue
        existing_parts = set(obj.get_covered_parts() if hasattr(obj, "get_covered_parts") else (getattr(obj.db, "covered_parts", None) or []))
        if new_parts & existing_parts:
            return True, obj
    return False, None
