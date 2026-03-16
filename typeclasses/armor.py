"""
Armor typeclass: protective wear with layers, coverage, damage reduction, and stacking limits.
Inherits from Clothing so it uses covered_parts and worn_desc for look; adds armor_layer,
protection, stacking_score, mobility_impact, and quality (durability) for combat and wear rules.
Uses world.armor_levels for full damage type list (physical + fire, radiation).
"""
from typeclasses.clothing import Clothing
from world.medical import BODY_PARTS
from world.damage_types import DAMAGE_TYPES

try:
    from world.armor_levels import ALL_ARMOR_DAMAGE_TYPES
except ImportError:
    ALL_ARMOR_DAMAGE_TYPES = DAMAGE_TYPES

# Layer order: 0 = innermost (jumpsuits/base), 5 = outermost (helmets/boots/gloves).
# Wearing a lower layer while already wearing higher layer on same part should warn "wear under X".
ARMOR_LAYER_NAMES = {
    0: "base/jumpsuit",
    1: "pants/shirt",
    2: "shades",
    3: "jacket",
    4: "trenchcoat",
    5: "helmet/boots/gloves",
}


def _default_protection():
    """Default protection dict: 0 for each damage type (physical + fire, radiation)."""
    return {dt: 0 for dt in ALL_ARMOR_DAMAGE_TYPES}


class Armor(Clothing):
    """
    Wearable armor. Has armor_layer (0-5), covered_parts, protection (damage_type -> score),
    stacking_score, weight, mobility_impact, and quality (durability). When worn, stacking
    is checked against the character's max; combat uses protection for coin-flip damage reduction.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.armor_layer = 0
        self.db.covered_parts = []
        self.db.protection = _default_protection()
        self.db.stacking_score = 0
        self.db.weight = 0
        self.db.mobility_impact = 0
        self.db.quality = 100

    def get_protection(self, damage_type):
        """Return effective protection for this damage type (scaled by quality)."""
        prot = getattr(self.db, "protection", None) or _default_protection()
        base = prot.get(damage_type, 0) if isinstance(prot, dict) else 0
        quality = max(0, min(100, int(getattr(self.db, "quality", 100) or 100)))
        return max(0, int(base * quality / 100))

    def get_stacking_score(self):
        """Return this piece's stacking score (used for wear limit)."""
        return max(0, int(getattr(self.db, "stacking_score", 0) or 0))

    def get_armor_layer(self):
        """Return armor_layer (0-5)."""
        return max(0, min(5, int(getattr(self.db, "armor_layer", 0) or 0)))

    def get_mobility_impact(self):
        """Return mobility penalty (positive = worse)."""
        return int(getattr(self.db, "mobility_impact", 0) or 0)

    def get_covered_parts(self):
        """Return list of body part keys this armor covers."""
        parts = getattr(self.db, "covered_parts", None) or []
        return [p for p in parts if p in BODY_PARTS]
