"""
Recipe creation, storage, retrieval, and item spawning for the food/drink system.

Recipes are stored as dicts on station.db.recipes (a list).
Each recipe carries all mechanical values from its base ingredient plus
player-written cosmetic fields (name, desc, taste, extras).

Mechanical values are NOT customizable — they come from the base ingredient.
"""

import time

from evennia.utils.ansi import strip_ansi


# ══════════════════════════════════════════════════════════════════════════════
#  Internal helpers
# ══════════════════════════════════════════════════════════════════════════════

def _strip_color_codes(text: str) -> str:
    """Strip Evennia ANSI color codes from player-provided text."""
    try:
        return strip_ansi(str(text))
    except Exception:
        return str(text)


def _get_recipe_price(station, recipe: dict) -> int:
    """
    Return the price for a recipe on a bar station.
    Checks per-recipe overrides first, then falls back to station default.
    """
    prices = dict(getattr(station.db, "recipe_prices", None) or {})
    name_key = recipe.get("custom_name", "").lower()
    if name_key in prices:
        return int(prices[name_key])
    return int(getattr(station.db, "drink_price_default", 10) or 10)


# ══════════════════════════════════════════════════════════════════════════════
#  Recipe creation
# ══════════════════════════════════════════════════════════════════════════════

def create_recipe(
    station,
    creator,
    base_key: str,
    custom_name: str,
    custom_desc: str,
    custom_taste: str,
    extra_ingredients=None,
) -> tuple:
    """
    Create a new recipe on a station.

    Args:
        station:           Bar or Kitchenette station object.
        creator:           Character creating the recipe.
        base_key:          Key from FOOD_BASES, NON_ALCOHOLIC_BASES, or ALCOHOL_BASES.
        custom_name:       Player-written item name.
        custom_desc:       Player-written look description.
        custom_taste:      Player-written taste/consume message.
        extra_ingredients: List of cosmetic flavor strings (max 6).

    Returns:
        (success: bool, message: str)
    """
    from world.food.ingredients import get_base, get_base_tier_level
    from world.food import get_tier_level
    from world.food.stations import _validate_base_for_station

    base = get_base(base_key)
    if not base:
        return False, "Unknown base ingredient."

    # Validate station type allows this base category
    ok, msg = _validate_base_for_station(station, base_key)
    if not ok:
        return False, msg

    # Check station tier allows this base
    station_tier = getattr(station.db, "social_tier", "slum")
    station_level = get_tier_level(station_tier)
    base_level = get_base_tier_level(base_key)

    if base_level > station_level:
        from world.food import get_tier_name
        tier_display = get_tier_name(base.get("tier", "unknown"))
        station_display = get_tier_name(station_tier)
        return False, (
            f"This station can't prepare {tier_display}-tier ingredients. "
            f"It's a {station_display} establishment."
        )

    # Sanitize and validate player-written fields
    custom_name = _strip_color_codes(custom_name).strip()
    custom_desc = _strip_color_codes(custom_desc).strip()
    custom_taste = _strip_color_codes(custom_taste).strip()

    if not custom_name or len(custom_name) < 3 or len(custom_name) > 60:
        return False, "Item name must be 3-60 characters."
    if not custom_desc or len(custom_desc) < 10 or len(custom_desc) > 500:
        return False, "Description must be 10-500 characters."
    if not custom_taste or len(custom_taste) < 10 or len(custom_taste) > 300:
        return False, "Taste message must be 10-300 characters."

    extras = []
    if extra_ingredients:
        for e in extra_ingredients[:6]:
            cleaned = _strip_color_codes(str(e)).strip()
            if cleaned and len(cleaned) <= 80:
                extras.append(cleaned)

    recipes = list(getattr(station.db, "recipes", None) or [])

    # Duplicate name check
    for r in recipes:
        if r.get("custom_name", "").lower() == custom_name.lower():
            return False, f"A recipe named '{custom_name}' already exists on this station."

    recipe = {
        "base_key": base_key,
        "custom_name": custom_name,
        "custom_desc": custom_desc,
        "custom_taste": custom_taste,
        "extra_ingredients": extras,
        "created_by": creator.id,
        "created_by_name": creator.key,
        "created_at": time.time(),
        "times_prepared": 0,
        # Mechanical values from base — NOT player-customizable
        "hunger_restore": base.get("hunger_restore", 0),
        "thirst_restore": base.get("thirst_restore", 0),
        "alcohol_strength": base.get("alcohol_strength", 0.0),
        "is_nutritious": base.get("is_nutritious", False),
        "category": base.get("category", "food"),
    }

    recipes.append(recipe)
    station.db.recipes = recipes

    return True, f"Recipe '{custom_name}' added to the menu."


# ══════════════════════════════════════════════════════════════════════════════
#  Taste message construction
# ══════════════════════════════════════════════════════════════════════════════

def build_taste_message(recipe: dict) -> str:
    """
    Build the full taste echo from a recipe.
    Combines the custom taste with any extra ingredient flavor notes.
    """
    parts = [recipe["custom_taste"]]

    extras = recipe.get("extra_ingredients") or []
    if extras:
        extras_str = ", ".join(extras)
        parts.append(f"You taste: {extras_str}.")

    return " ".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
#  Item spawning
# ══════════════════════════════════════════════════════════════════════════════

def prepare_recipe(character, station, recipe_name: str) -> tuple:
    """
    Spawn a food/drink item from a recipe on this station.

    Returns:
        (success: bool, item_or_None, message: str)
    """
    recipes = list(getattr(station.db, "recipes", None) or [])
    recipe = None
    recipe_idx = None

    for i, r in enumerate(recipes):
        if r.get("custom_name", "").lower() == recipe_name.lower():
            recipe = r
            recipe_idx = i
            break

    if not recipe:
        return False, None, f"No recipe called '{recipe_name}' on the menu."

    from evennia.utils.create import create_object

    item = create_object(
        "typeclasses.items.Item",
        key=recipe["custom_name"],
        location=character,
    )

    category = recipe.get("category", "food")

    if category == "food":
        item.db.edible = True
        item.db.hunger_restore = recipe.get("hunger_restore", 0)
        item.tags.add("food")
    elif category == "drink":
        item.db.drinkable = True
        item.db.thirst_restore = recipe.get("thirst_restore", 0)
        item.tags.add("drink")
    elif category == "alcohol":
        item.db.drinkable = True
        item.db.thirst_restore = recipe.get("thirst_restore", 0)
        item.db.alcohol_strength = recipe.get("alcohol_strength", 0.0)
        item.tags.add("drink")

    # Also set cross-category values if the base has them (e.g. broth_cup has both)
    if recipe.get("hunger_restore") and category != "food":
        item.db.hunger_restore = recipe.get("hunger_restore", 0)

    item.db.is_nutritious = recipe.get("is_nutritious", False)
    item.db.desc = recipe["custom_desc"]
    item.db.taste_msg = build_taste_message(recipe)
    item.db.prepared_at = station.db.station_name or "somewhere"
    item.db.prepared_by = character.key
    item.db.prepared_time = time.time()
    # Prepared station items are multi-portion consumables.
    item.db.portions_total = 5
    item.db.uses_remaining = 5

    # Spoilage: food items expire in 1 hour; alcohol does not spoil
    if category == "food":
        item.db.expires_at = time.time() + 3600

    # Track recipe popularity
    if recipe_idx is not None:
        recipes[recipe_idx]["times_prepared"] = recipe.get("times_prepared", 0) + 1
        station.db.recipes = recipes

    return True, item, f"You prepare: |w{recipe['custom_name']}|n."


# ══════════════════════════════════════════════════════════════════════════════
#  Menu formatting
# ══════════════════════════════════════════════════════════════════════════════

_MENU_WIDTH = 52
_CAT_LABELS = {
    "food": "|gFOOD|n",
    "drink": "|cDRINK|n",
    "alcohol": "|rALC|n",
}
_CAT_ORDER = ["food", "drink", "alcohol"]


def _format_rating(recipe: dict) -> str:
    """
    Return a short rating string for menu display, e.g. '|G★★★★|x★|n  4.2'
    Returns empty string if no ratings yet.
    """
    count = recipe.get("rating_count", 0)
    total = recipe.get("rating_total", 0)
    if not count:
        return ""
    avg = total / count
    filled = round(avg)
    filled = max(1, min(5, filled))
    stars = "|G" + "★" * filled + "|x" + "★" * (5 - filled) + "|n"
    return f" {stars} |x{avg:.1f}|n"


def format_menu(station) -> str:
    """
    Build the menu display text for a station.
    Groups recipes by category. Shows prices for bars.
    Shows a popularity star for recipes prepared 10+ times.
    Shows average rating if any ratings have been submitted.
    """
    from world.rpg.economy import format_currency

    recipes = list(getattr(station.db, "recipes", None) or [])
    station_name = getattr(station.db, "station_name", None) or "menu"
    is_bar = getattr(station.db, "station_type", "kitchenette") == "bar"

    divider = f"|x{'═' * _MENU_WIDTH}|n"
    lines = [
        divider,
        f"  |w{station_name.upper()} — MENU|n",
        divider,
    ]

    if not recipes:
        lines.append(f"  |xNothing on the menu yet.|n")
        lines.append(divider)
        return "\n".join(lines)

    # Group by category
    grouped = {cat: [] for cat in _CAT_ORDER}
    for r in recipes:
        cat = r.get("category", "food")
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(r)

    first_section = True
    for cat in _CAT_ORDER:
        cat_recipes = grouped.get(cat, [])
        if not cat_recipes:
            continue

        if not first_section:
            lines.append(f"|x{'─' * _MENU_WIDTH}|n")
        first_section = False

        cat_label = _CAT_LABELS.get(cat, cat.upper())
        lines.append(f"  {cat_label}")

        for recipe in cat_recipes:
            name = recipe.get("custom_name", "???")
            times = recipe.get("times_prepared", 0)
            popular = " |y★|n" if times >= 10 else ""
            rating_str = _format_rating(recipe)

            price_str = ""
            if is_bar:
                price = _get_recipe_price(station, recipe)
                price_str = f"  |y{format_currency(price, color=False)}|n"

            lines.append(f"  |w{name}|n{popular}{rating_str}{price_str}")

            desc = recipe.get("custom_desc", "")
            if desc:
                short = desc[:80] + "..." if len(desc) > 80 else desc
                lines.append(f"    |x{short}|n")

    lines.append(divider)
    return "\n".join(lines)


def format_compact_menu(station) -> str:
    """
    One-line-per-item compact menu for embedding in room/object descriptions.
    """
    from world.rpg.economy import format_currency

    recipes = list(getattr(station.db, "recipes", None) or [])
    if not recipes:
        return ""

    is_bar = getattr(station.db, "station_type", "kitchenette") == "bar"
    lines = []
    for recipe in recipes:
        name = recipe.get("custom_name", "???")
        if is_bar:
            price = _get_recipe_price(station, recipe)
            lines.append(f"  |w{name}|n — |y{format_currency(price, color=False)}|n")
        else:
            lines.append(f"  |w{name}|n")
    return "\n".join(lines)
