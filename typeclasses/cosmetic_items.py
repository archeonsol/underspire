"""
Cosmetic item typeclasses: InkWriter (tattooing tool) and MakeupItem
(consumable cosmetics: lipstick, nail polish, eye shadow, eyeliner).

Buff classes for makeup charisma bonuses live here so pickle can resolve
them as typeclasses.cosmetic_items.<ClassName> after server restarts.
"""

import sys

from evennia.contrib.rpg.buffs.buff import BaseBuff, Mod

from typeclasses.items import Item
from world.buffs import GameBuffBase


# ── Makeup buff classes ───────────────────────────────────────────────────
# One buff key per makeup type — maxstacks=1 prevents two lipsticks stacking.

class LipstickBuff(GameBuffBase):
    """Temporary Charisma bonus from lipstick."""
    key = "lipstick"
    name = "Lipstick"
    flavor = "You are wearing lipstick."
    duration = 7200
    maxstacks = 1
    stacks = 1
    mods = [Mod(stat="charisma_display", modifier="add", value=2)]


class NailPolishBuff(GameBuffBase):
    """Temporary Charisma bonus from nail polish."""
    key = "nail_polish"
    name = "Nail Polish"
    flavor = "Your nails are painted."
    duration = 14400
    maxstacks = 1
    stacks = 1
    mods = [Mod(stat="charisma_display", modifier="add", value=2)]


class EyeShadowBuff(GameBuffBase):
    """Temporary Charisma bonus from eye shadow."""
    key = "eye_shadow"
    name = "Eye Shadow"
    flavor = "You are wearing eye shadow."
    duration = 5400
    maxstacks = 1
    stacks = 1
    mods = [Mod(stat="charisma_display", modifier="add", value=2)]


class EyelinerBuff(GameBuffBase):
    """Temporary Charisma bonus from eyeliner."""
    key = "eyeliner"
    name = "Eyeliner"
    flavor = "You are wearing eyeliner."
    duration = 5400
    maxstacks = 1
    stacks = 1
    mods = [Mod(stat="charisma_display", modifier="add", value=2)]


# Register buff classes on world.buffs so pickle can resolve them.
try:
    import world.buffs as _buffs_module
    for _cls in (LipstickBuff, NailPolishBuff, EyeShadowBuff, EyelinerBuff):
        if not hasattr(_buffs_module, _cls.__name__):
            setattr(_buffs_module, _cls.__name__, _cls)
except Exception:
    pass


# ── InkWriter ─────────────────────────────────────────────────────────────

class InkWriter(Item):
    """
    A tattooing device. Required to apply or remove tattoos on another character.
    Quality tier (db.inkwriter_tier 1-3) limits the best result achievable.

    Tier 1 — Scrap Needle: max quality 'clean'
    Tier 2 — Guild Inkwriter: max quality 'fine'
    Tier 3 — Master's Inkwriter: max quality 'masterwork'
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.is_inkwriter = True
        self.db.inkwriter_tier = 1
        self.db.inkwriter_name = "inkwriter"
        if not self.db.desc:
            self.db.desc = "A handheld tattooing device with a cluster of vibrating needles."

    def get_display_desc(self, looker, **kwargs):
        from world.cosmetics import INKWRITER_TIERS
        tier = int(self.db.inkwriter_tier or 1)
        tier_info = INKWRITER_TIERS.get(tier, INKWRITER_TIERS[1])
        base = self.db.desc or tier_info["desc"]
        max_q = tier_info["max_quality"]
        return f"{base}\n\nTier {tier} — {tier_info['name']}. Maximum tattoo quality: |w{max_q}|n."


# ── MakeupItem ────────────────────────────────────────────────────────────

class MakeupItem(Item):
    """
    A cosmetic item that applies a temporary description to one or more body parts.
    Consumed after db.uses_remaining reaches 0.

    db.makeup_type: "lipstick", "nail_polish", "eye_shadow", "eyeliner"
    db.makeup_color_key: color registry key (e.g. "siren", "smoke")
    db.makeup_color_name: display name (e.g. "siren red", "smoke")
    db.makeup_color_code: Evennia color code (e.g. "|R", "|=h")
    db.uses_remaining: applications left before the item is consumed
    db.color_changeable: whether the player can switch colors
    db.available_colors: {color_key: {"name": ..., "code": ...}} for changeable items
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.is_makeup = True
        self.db.makeup_type = ""
        self.db.makeup_color_key = ""
        self.db.makeup_color_name = ""
        self.db.makeup_color_code = ""
        self.db.uses_remaining = 10
        self.db.color_changeable = False
        self.db.available_colors = {}

    def get_display_desc(self, looker, **kwargs):
        base = self.db.desc or ""
        uses = int(self.db.uses_remaining or 0)
        color_name = (self.db.makeup_color_name or "").strip()
        color_code = (self.db.makeup_color_code or "").strip()

        lines = [base] if base else []

        if color_name and color_code:
            lines.append(f"Color: {color_code}{color_name}|n")
        elif self.db.color_changeable:
            lines.append("|xNo color set. Use |wcolor <item> <color>|n|x to choose one.|n")

        lines.append(f"|x{uses} use{'s' if uses != 1 else ''} remaining.|n")
        return "\n".join(lines)


# ── Nail polish prototypes ────────────────────────────────────────────────
# Generated at module load from NAIL_POLISH_COLORS.
# Each color is a separate prototype (color is fixed on the bottle).

def _build_nail_polish_prototypes():
    from world.cosmetics.makeup import NAIL_POLISH_COLORS
    protos = {}
    for color_key, color_data in NAIL_POLISH_COLORS.items():
        proto_key = f"nail_polish_{color_key}"
        protos[proto_key] = {
            "prototype_key": proto_key,
            "typeclass": "typeclasses.cosmetic_items.MakeupItem",
            "key": f"bottle of {color_data['name']} nail polish",
            "attrs": [
                ("makeup_type", "nail_polish"),
                ("makeup_color_key", color_key),
                ("makeup_color_name", color_data["name"]),
                ("makeup_color_code", color_data["code"]),
                ("uses_remaining", 8),
                ("color_changeable", False),
                ("desc", f"A small glass bottle of {color_data['name']} nail polish with a brush applicator."),
            ],
        }
    return protos


NAIL_POLISH_PROTOTYPES = _build_nail_polish_prototypes()

# ── Static prototypes for color-changeable items ──────────────────────────

LIPSTICK_PROTOTYPE = {
    "prototype_key": "lipstick",
    "typeclass": "typeclasses.cosmetic_items.MakeupItem",
    "key": "lipstick tube",
    "attrs": [
        ("makeup_type", "lipstick"),
        ("uses_remaining", 12),
        ("color_changeable", True),
        ("desc", "A slim tube of lipstick with a twist-up base. The color is visible through the cap."),
    ],
}

EYE_SHADOW_PROTOTYPE = {
    "prototype_key": "eye_shadow_palette",
    "typeclass": "typeclasses.cosmetic_items.MakeupItem",
    "key": "eye shadow palette",
    "attrs": [
        ("makeup_type", "eye_shadow"),
        ("uses_remaining", 15),
        ("color_changeable", True),
        ("desc", "A compact palette of pressed pigment in multiple shades. A small brush is clipped to the lid."),
    ],
}

EYELINER_PROTOTYPE = {
    "prototype_key": "eyeliner_pencil",
    "typeclass": "typeclasses.cosmetic_items.MakeupItem",
    "key": "eyeliner pencil",
    "attrs": [
        ("makeup_type", "eyeliner"),
        ("uses_remaining", 15),
        ("color_changeable", True),
        ("desc", "A slim pencil with a waxy, pigmented tip. Twist to extend."),
    ],
}
