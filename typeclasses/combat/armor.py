"""
Armor typeclass: protective wear with layers, coverage, damage reduction, and stacking limits.
Inherits from Clothing so it uses covered_parts and worn_desc for look; adds armor_layer,
protection, stacking_score, mobility_impact, and quality (durability) for combat and wear rules.
Uses world.armor_levels for full damage type list (physical + fire, radiation).
"""
from typeclasses.clothing import Clothing
from world.combat.damage_types import DAMAGE_TYPES
from world.races import ALL_COVERABLE_BODY_PARTS

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
        # Bind to an armor template by default, using the object's key as identifier.
        if not getattr(self.db, "armor_template", None):
            self.db.armor_template = self.key
        self._apply_armor_template_defaults()

    def _apply_armor_template_defaults(self):
        """
        Populate this Armor from world.armor_levels based on db.armor_template or the key.
        Allows staff to @create e.g. 'Tunnelbone wrap':Armor and get a fully defined piece.
        """
        ident = getattr(self.db, "armor_template", None) or self.key
        if not ident:
            return
        try:
            from world.armor_levels import find_armor_template
        except Exception:
            return
        template = find_armor_template(ident)
        if not template:
            return
        # Store canonical template key and level
        self.db.armor_template = template.get("key", ident)
        self.db.armor_level = template.get("level", getattr(self.db, "armor_level", 1) or 1)
        # Core armor stats
        self.db.armor_layer = template.get("layer", getattr(self.db, "armor_layer", 0) or 0)
        self.db.covered_parts = list(template.get("covered_parts") or [])
        prot = template.get("protection")
        if isinstance(prot, dict):
            self.db.protection = dict(prot)
        self.db.stacking_score = template.get("stacking_score", getattr(self.db, "stacking_score", 0) or 0)
        self.db.mobility_impact = template.get("mobility_impact", getattr(self.db, "mobility_impact", 0) or 0)
        # Quality defaults to 100 unless caller has already set something else
        if getattr(self.db, "quality", None) is None:
            self.db.quality = 100
        # Descriptions
        if not getattr(self.db, "desc", None) and template.get("desc"):
            self.db.desc = template["desc"]
        if template.get("worn_desc"):
            self.db.worn_desc = template["worn_desc"]

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
        return [p for p in parts if p in ALL_COVERABLE_BODY_PARTS]
