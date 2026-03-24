"""
Food and drink crafting commands.

  menu <station>                        — view the station's recipe menu
  newrecipe <station>                   — start the recipe creation wizard
  prepare <recipe> on <station>         — prepare a recipe (spawns item)
  serve <recipe> to <character>         — offer a drink to a customer (bar employees)
  delrecipe <recipe> on <station>       — remove a recipe (manager/owner)
  rate <item> <1-5>                     — rate a prepared item (touchscreen echo)

Pending input flows (via ndb):
  _pending_recipe   — newrecipe wizard
  _pending_serve    — customer confirmation of a serve offer
handle_pending_food_input() is called from CmdNoMatch in roleplay_cmds.py.
"""

from __future__ import annotations

from commands.base_cmds import Command

# ── UI constants ──────────────────────────────────────────────────────────────
_N = "|n"
_W = "|w"
_DIM = "|x"
_G = "|g"
_R = "|r"
_Y = "|y"
_C = "|c"
_BOX_W = 52


def _line(char="═"):
    return f"|x{char * _BOX_W}|n"


def _header(title):
    pad = max(0, _BOX_W - len(title) - 4)
    return f"|c╔══[ |w{title}|c ]{'═' * pad}|n"


def _footer():
    return f"|c╚{'═' * (_BOX_W - 1)}|n"


def _display_name(obj, viewer):
    """Return object name as seen by viewer (recog-aware when available)."""
    if hasattr(obj, "get_display_name"):
        try:
            return obj.get_display_name(viewer)
        except Exception:
            pass
    return getattr(obj, "key", str(obj))


def _broadcast_room_recog(room, line_builder, exclude=None):
    """
    Send per-viewer room echoes so each viewer sees their own recog names.

    Args:
        room: Room-like object.
        line_builder: callable(viewer) -> str
        exclude: iterable of objects to exclude.
    """
    if not room:
        return
    excluded = set(exclude or [])
    if hasattr(room, "contents_get"):
        for viewer in room.contents_get(content_type="character"):
            if viewer in excluded:
                continue
            viewer.msg(line_builder(viewer))
    else:
        room.msg_contents(line_builder(None), exclude=list(excluded))


# ══════════════════════════════════════════════════════════════════════════════
#  CmdMenu — menu <station>
# ══════════════════════════════════════════════════════════════════════════════

class CmdMenu(Command):
    """
    View the menu of a bar or kitchenette.

    Usage:
      menu <station>
      menu bar
      menu kitchenette

    Shows all available recipes grouped by category.
    Bars show prices. Popular items are marked with a star.
    """

    key = "menu"
    locks = "cmd:all()"
    help_category = "Food & Drink"

    def func(self):
        from world.food.stations import find_station_in_room
        from world.food.recipes import format_menu

        caller = self.caller
        arg = (self.args or "").strip()

        station = find_station_in_room(caller, arg)
        if not station:
            return

        caller.msg(format_menu(station))


# ══════════════════════════════════════════════════════════════════════════════
#  CmdNewRecipe — newrecipe <station>  (multi-step wizard)
# ══════════════════════════════════════════════════════════════════════════════

class CmdNewRecipe(Command):
    """
    Start the recipe creation wizard at a bar or kitchenette.

    Usage:
      newrecipe <station>

    You will be guided through choosing a base ingredient, naming your
    creation, writing a description and taste message, and adding optional
    flavor notes. Access: bar manager/employees or kitchenette owner.
    """

    key = "newrecipe"
    locks = "cmd:all()"
    help_category = "Food & Drink"

    def func(self):
        from world.food.stations import find_station_in_room, can_use_station

        caller = self.caller
        arg = (self.args or "").strip()

        station = find_station_in_room(caller, arg)
        if not station:
            return

        ok, reason = can_use_station(caller, station)
        if not ok:
            caller.msg(f"|r{reason}|n")
            return

        _start_recipe_wizard(caller, station)


def _start_recipe_wizard(caller, station):
    """Begin the recipe creation wizard for a station."""
    from world.food.ingredients import get_bases_for_station

    bases = get_bases_for_station(station)
    if not bases:
        caller.msg("|rNo base ingredients are available for this station.|n")
        return

    station_name = getattr(station.db, "station_name", None) or station.key
    station_type = getattr(station.db, "station_type", "kitchenette")
    tier = getattr(station.db, "social_tier", "slum")

    from world.food import get_tier_name
    tier_display = get_tier_name(tier)

    lines = [
        _header("NEW RECIPE"),
        f"  Station: |w{station_name}|n  ({tier_display} tier)",
        f"|x{'─' * _BOX_W}|n",
        f"  Available base ingredients:",
    ]

    for i, base in enumerate(bases, 1):
        cat = base.get("category", "food")
        cat_tag = {
            "food": f"|gFOOD|n",
            "drink": f"|cDRINK|n",
            "alcohol": f"|rALC|n",
        }.get(cat, cat.upper())

        extra = ""
        if cat == "alcohol":
            strength = base.get("alcohol_strength", 0.0)
            extra = f" |x({strength}% ABV)|n"
        elif cat == "food":
            hunger = base.get("hunger_restore", 0)
            extra = f" |x(+{hunger} hunger)|n"
        elif cat == "drink":
            thirst = base.get("thirst_restore", 0)
            extra = f" |x(+{thirst} thirst)|n"

        lines.append(f"  |w{i:2}.|n {cat_tag} {base['name']}{extra}")

    lines.append(_footer())
    lines.append(f"  |xPick a base (number), or |wcancel|x:|n")
    caller.msg("\n".join(lines))

    caller.ndb._pending_recipe = {
        "stage": "pick_base",
        "station_id": station.id,
        "bases": bases,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  CmdPrepare — prepare <recipe> on <station>
# ══════════════════════════════════════════════════════════════════════════════

class CmdPrepare(Command):
    """
    Prepare a recipe at a bar or kitchenette, creating the item.

    Usage:
      prepare <recipe name> on <station>

    For bars: requires employee or manager access.
    For kitchenettes: requires owner or trusted access.
    The item is placed in your inventory. Use 'serve' to hand it to a customer.
    """

    key = "prepare"
    locks = "cmd:all()"
    help_category = "Food & Drink"

    def func(self):
        from world.food.stations import find_station_in_room, can_use_station
        from world.food.recipes import prepare_recipe

        caller = self.caller
        raw = (self.args or "").strip()

        if " on " not in raw.lower():
            caller.msg("Usage: |wprepare <recipe name> on <station>|n")
            return

        idx = raw.lower().index(" on ")
        recipe_name = raw[:idx].strip()
        station_arg = raw[idx + 4:].strip()

        if not recipe_name:
            caller.msg("Specify a recipe name.")
            return

        station = find_station_in_room(caller, station_arg)
        if not station:
            return

        ok, reason = can_use_station(caller, station)
        if not ok:
            caller.msg(f"|r{reason}|n")
            return

        success, item, msg = prepare_recipe(caller, station, recipe_name)
        if not success:
            caller.msg(f"|r{msg}|n")
            return

        caller.msg(msg)

        # Ambient room echo
        station_name = getattr(station.db, "station_name", None) or station.key
        if caller.location:
            _broadcast_room_recog(
                caller.location,
                lambda viewer: f"{_display_name(caller, viewer)} prepares |w{item.key}|n at {station_name}.",
                exclude=[caller],
            )


# ══════════════════════════════════════════════════════════════════════════════
#  CmdServe — serve <recipe> to <character>
# ══════════════════════════════════════════════════════════════════════════════

class CmdServe(Command):
    """
    Offer a drink to a customer. Bar employees only.

    Usage:
      serve <recipe> to <character>

    The customer receives a prompt and must accept or decline.
    If they accept, they are charged the menu price and receive the drink.
    Revenue goes to the bar register.
    """

    key = "serve"
    locks = "cmd:all()"
    help_category = "Food & Drink"

    def func(self):
        from world.food.stations import find_station_in_room, is_bar_employee, is_staff
        from world.food.recipes import _get_recipe_price
        from world.rpg.economy import get_balance, format_currency

        caller = self.caller
        raw = (self.args or "").strip()

        if " to " not in raw.lower():
            caller.msg("Usage: |wserve <recipe> to <character>|n")
            return

        idx = raw.lower().index(" to ")
        recipe_name = raw[:idx].strip()
        target_name = raw[idx + 4:].strip()

        if not recipe_name or not target_name:
            caller.msg("Usage: |wserve <recipe> to <character>|n")
            return

        # Find bar station in room
        station = find_station_in_room(caller, "", station_type="bar")
        if not station:
            caller.msg("There is no bar here to serve from.")
            return

        # Check employee access
        if not is_bar_employee(caller, station) and not is_staff(caller):
            caller.msg("|rYou're not an employee of this bar.|n")
            return

        # Find the target customer
        target = caller.search(target_name, location=caller.location)
        if not target:
            return

        if target == caller:
            caller.msg("You can't serve yourself. Use |wprepare|n instead.")
            return

        # Check target isn't already being served
        if getattr(target.ndb, "_pending_serve", None):
            caller.msg(f"|r{target.key} already has a pending order. Wait for them to respond.|n")
            return

        # Look up recipe and price
        recipes = list(getattr(station.db, "recipes", None) or [])
        recipe = None
        for r in recipes:
            if r.get("custom_name", "").lower() == recipe_name.lower():
                recipe = r
                break

        if not recipe:
            caller.msg(f"|rNo recipe called '{recipe_name}' on the menu.|n")
            return

        price = _get_recipe_price(station, recipe)

        # Check customer can afford it before even offering
        if price > 0:
            balance = get_balance(target)
            if balance < price:
                caller.msg(
                    f"|r{target.key} can't afford that. "
                    f"They have {format_currency(balance)} but the price is {format_currency(price)}.|n"
                )
                target.msg(
                    f"|r{caller.key} tried to serve you |w{recipe_name}|r, "
                    f"but you can't afford it ({format_currency(price)}).|n"
                )
                return

        # Store pending serve on the TARGET so they can accept/decline
        station_name = getattr(station.db, "station_name", None) or station.key
        target.ndb._pending_serve = {
            "employee_id": caller.id,
            "employee_name": caller.key,
            "station_id": station.id,
            "station_name": station_name,
            "recipe_name": recipe["custom_name"],
            "price": price,
        }

        price_str = format_currency(price) if price > 0 else "|xfree|n"
        caller.msg(
            f"You offer |w{recipe['custom_name']}|n to {target.key} "
            f"({price_str}). Waiting for their response."
        )
        target.msg(
            f"|w{caller.key}|n offers you |w{recipe['custom_name']}|n "
            f"from {station_name} for {price_str}.\n"
            f"  Type |waccept|n to take it or |wdecline|n to refuse."
        )

        if caller.location:
            _broadcast_room_recog(
                caller.location,
                lambda viewer: (
                    f"{_display_name(caller, viewer)} wipes down the counter, pours |w{recipe['custom_name']}|n, "
                    f"and sets it in front of {_display_name(target, viewer)} with a waiting look."
                ),
            )


def _complete_serve(target, pending):
    """
    Finalise a serve transaction after the customer accepts.
    Charges the customer, spawns the item, and delivers it.
    """
    from evennia.utils.search import search_object
    from world.food.recipes import prepare_recipe, _get_recipe_price
    from world.rpg.economy import get_balance, deduct_funds, add_funds, format_currency

    # Resolve station
    station_results = search_object(f"#{pending['station_id']}")
    if not station_results:
        target.msg("|rThe bar station is no longer available. Order cancelled.|n")
        return

    station = station_results[0]

    # Resolve employee (for messaging only; they may have moved)
    employee_results = search_object(f"#{pending['employee_id']}")
    employee = employee_results[0] if employee_results else None

    recipe_name = pending["recipe_name"]
    price = pending["price"]
    station_name = pending.get("station_name", station.key)

    # Charge
    if price > 0:
        balance = get_balance(target)
        if balance < price:
            target.msg(
                f"|rYou no longer have enough to pay for |w{recipe_name}|r "
                f"({format_currency(price)}). Order cancelled.|n"
            )
            if employee:
                employee.msg(
                    f"|r{target.key} can no longer afford |w{recipe_name}|r. Order cancelled.|n"
                )
            return

        deduct_funds(target, price)
        target.msg(f"You slide over {format_currency(price)} for |w{recipe_name}|n.")
        station.log_sale(price, target.key, pending["employee_name"], recipe_name)

    # Spawn item — attributed to the employee if possible, else target
    preparer = employee if employee else target
    success, item, msg = prepare_recipe(preparer, station, recipe_name)
    if not success:
        if price > 0:
            add_funds(target, price)
            target.msg("|rPreparation failed. You have been refunded.|n")
        if employee:
            employee.msg(f"|rFailed to prepare |w{recipe_name}|r: {msg}|n")
        return

    item.location = target

    target.msg(f"You take |w{item.key}|n from the counter.")
    if employee:
        employee.msg(f"{_display_name(target, employee)} accepts. You serve |w{item.key}|n.")

    if target.location:
        _broadcast_room_recog(
            target.location,
            lambda viewer: (
                f"{_display_name(target, viewer)} takes the |w{item.key}|n and nods, "
                f"while {_display_name(employee, viewer) if employee else pending['employee_name']} pockets the payment at {station_name}."
            ),
        )


# ══════════════════════════════════════════════════════════════════════════════
#  CmdRate — rate <item> <1-5>
# ══════════════════════════════════════════════════════════════════════════════

# Rating labels shown to the room
_RATE_LABELS = {
    1: ("taps |r1 star|n", "grimaces"),
    2: ("taps |y2 stars|n", "looks unimpressed"),
    3: ("taps |w3 stars|n", "nods neutrally"),
    4: ("taps |g4 stars|n", "looks pleased"),
    5: ("taps |G5 stars|n", "grins"),
}

# Touchscreen flavour lines per score
_RATE_SCREEN_MSGS = {
    1: "The screen flickers red. A single hollow star lights up.",
    2: "Two dim stars glow amber on the screen.",
    3: "Three steady stars pulse white on the screen.",
    4: "Four bright stars bloom green across the screen.",
    5: "Five blazing stars fill the screen in gold. A soft chime sounds.",
}


class CmdRate(Command):
    """
    Rate a prepared food or drink item you're holding.

    Usage:
      rate <item> <1-5>

    Taps the bar's touchscreen rating panel and broadcasts your verdict
    to the room. The rating is recorded against the recipe on the station
    where the item was prepared.

    Example:
      rate Cinder Pale Ale 4
    """

    key = "rate"
    locks = "cmd:all()"
    help_category = "Food & Drink"

    def func(self):
        caller = self.caller
        raw = (self.args or "").strip()

        if not raw:
            caller.msg("Usage: |wrate <item> <1-5>|n")
            return

        # Last token is the score
        parts = raw.rsplit(None, 1)
        if len(parts) < 2:
            caller.msg("Usage: |wrate <item> <1-5>|n")
            return

        item_name, score_str = parts[0].strip(), parts[1].strip()

        try:
            score = int(score_str)
            if score < 1 or score > 5:
                raise ValueError
        except ValueError:
            caller.msg("|rRating must be a number from 1 to 5.|n")
            return

        # Find the item in caller's inventory
        item = caller.search(item_name, location=caller)
        if not item:
            return

        # Must have been prepared at a station
        prepared_at = getattr(item.db, "prepared_at", None)
        prepared_by = getattr(item.db, "prepared_by", None)
        item_key = item.key

        if not prepared_at:
            caller.msg(f"|r{item_key} wasn't prepared at a bar or kitchenette.|n")
            return

        # Record rating on the station's recipe if we can find it
        _record_rating(item, score)

        # Touchscreen echo
        screen_msg = _RATE_SCREEN_MSGS.get(score, "")
        tap_desc, _reaction = _RATE_LABELS.get(score, ("taps the screen", "reacts"))
        # _RATE_LABELS are third-person phrases; convert to first-person for caller line.
        first_person_tap = tap_desc
        if tap_desc.startswith("taps "):
            first_person_tap = "tap " + tap_desc[len("taps "):]

        caller.msg(
            f"You {first_person_tap} on the rating panel for |w{item_key}|n.\n"
            f"|x{screen_msg}|n"
        )

        if caller.location:
            _broadcast_room_recog(
                caller.location,
                lambda viewer: (
                    f"{_display_name(caller, viewer)} {tap_desc} on the rating panel for "
                    f"|w{item_key}|n. |x{screen_msg}|n"
                ),
                exclude=[caller],
            )


def _record_rating(item, score: int):
    """
    Find the recipe this item came from and record the rating.
    Updates recipe['rating_total'] and recipe['rating_count'] in place.
    """
    prepared_at_name = getattr(item.db, "prepared_at", None)
    item_key_lower = item.key.lower()

    if not prepared_at_name:
        return

    # Search for the station by station_name attribute
    try:
        from evennia.utils.search import search_object_attribute
        stations = search_object_attribute("station_name", prepared_at_name)
    except Exception:
        stations = []

    for station in stations:
        recipes = list(getattr(station.db, "recipes", None) or [])
        changed = False
        for recipe in recipes:
            if recipe.get("custom_name", "").lower() == item_key_lower:
                recipe["rating_total"] = recipe.get("rating_total", 0) + score
                recipe["rating_count"] = recipe.get("rating_count", 0) + 1
                changed = True
                break
        if changed:
            station.db.recipes = recipes
            break


# ══════════════════════════════════════════════════════════════════════════════
#  CmdDelRecipe — delrecipe <recipe> on <station>
# ══════════════════════════════════════════════════════════════════════════════

class CmdDelRecipe(Command):
    """
    Remove a recipe from a bar or kitchenette menu.

    Usage:
      delrecipe <recipe name> on <station>

    Requires manager access (bar) or owner access (kitchenette).
    """

    key = "delrecipe"
    locks = "cmd:all()"
    help_category = "Food & Drink"

    def func(self):
        from world.food.stations import find_station_in_room, can_manage_station

        caller = self.caller
        raw = (self.args or "").strip()

        if " on " not in raw.lower():
            caller.msg("Usage: |wdelrecipe <recipe name> on <station>|n")
            return

        idx = raw.lower().index(" on ")
        recipe_name = raw[:idx].strip()
        station_arg = raw[idx + 4:].strip()

        if not recipe_name:
            caller.msg("Specify a recipe name.")
            return

        station = find_station_in_room(caller, station_arg)
        if not station:
            return

        ok, reason = can_manage_station(caller, station)
        if not ok:
            caller.msg(f"|r{reason}|n")
            return

        recipes = list(getattr(station.db, "recipes", None) or [])
        original_count = len(recipes)
        recipes = [r for r in recipes if r.get("custom_name", "").lower() != recipe_name.lower()]

        if len(recipes) == original_count:
            caller.msg(f"|rNo recipe called '{recipe_name}' found on this station.|n")
            return

        station.db.recipes = recipes
        caller.msg(f"|gRecipe '{recipe_name}' removed from the menu.|n")


# ══════════════════════════════════════════════════════════════════════════════
#  Recipe wizard pending input handler
# ══════════════════════════════════════════════════════════════════════════════

def handle_pending_food_input(caller, raw: str) -> bool:
    """
    Handle pending food-system input. Called from CmdNoMatch.

    Handles two flows:
      _pending_serve   — customer accepting/declining a serve offer
      _pending_recipe  — newrecipe wizard steps

    Returns True if the input was consumed, False otherwise.
    """
    raw = raw.strip()

    # ── Serve confirmation (customer side) ───────────────────────────────────
    serve_pending = getattr(caller.ndb, "_pending_serve", None)
    if serve_pending:
        verb = raw.lower()
        if verb in ("accept", "yes", "y"):
            del caller.ndb._pending_serve
            _complete_serve(caller, serve_pending)
            return True
        if verb in ("decline", "no", "n", "cancel"):
            del caller.ndb._pending_serve
            recipe_name = serve_pending.get("recipe_name", "the order")
            employee_name = serve_pending.get("employee_name", "the bartender")
            caller.msg(f"|xYou decline {recipe_name}.|n")
            # Notify the employee
            from evennia.utils.search import search_object
            emp_results = search_object(f"#{serve_pending['employee_id']}")
            if emp_results:
                emp_results[0].msg(
                    f"{_display_name(caller, emp_results[0])} declines |w{recipe_name}|n."
                )
            if caller.location:
                _broadcast_room_recog(
                    caller.location,
                    lambda viewer: (
                        f"{_display_name(caller, viewer)} eyes the drink, then gives a small shake of the head and declines."
                    ),
                )
            return True
        # Any other input while a serve is pending: remind them
        caller.msg(
            f"|xYou have a pending order for |w{serve_pending.get('recipe_name', 'something')}|n|x. "
            f"Type |waccept|x or |wdecline|x first.|n"
        )
        return True

    # ── Recipe wizard ─────────────────────────────────────────────────────────
    pending = getattr(caller.ndb, "_pending_recipe", None)
    if not pending:
        return False

    if raw.lower() == "cancel":
        del caller.ndb._pending_recipe
        caller.msg("|xRecipe creation cancelled.|n")
        return True

    stage = pending.get("stage")

    if stage == "pick_base":
        return _wizard_pick_base(caller, pending, raw)
    elif stage == "set_name":
        return _wizard_set_name(caller, pending, raw)
    elif stage == "set_desc":
        return _wizard_set_desc(caller, pending, raw)
    elif stage == "set_taste":
        return _wizard_set_taste(caller, pending, raw)
    elif stage == "add_extras":
        return _wizard_add_extras(caller, pending, raw)
    elif stage == "confirm":
        return _wizard_confirm(caller, pending, raw)

    return False


def _get_station_from_pending(pending):
    """Retrieve the station object from a pending dict."""
    from evennia.utils.search import search_object
    station_id = pending.get("station_id")
    if not station_id:
        return None
    results = search_object(f"#{station_id}")
    return results[0] if results else None


def _wizard_pick_base(caller, pending, raw):
    bases = pending.get("bases", [])
    try:
        idx = int(raw) - 1
        if idx < 0 or idx >= len(bases):
            raise ValueError
    except (ValueError, TypeError):
        caller.msg(f"|rInvalid choice. Enter a number from 1 to {len(bases)}, or |wcancel|r.|n")
        return True

    chosen = bases[idx]
    pending["base_key"] = chosen["key"]
    pending["base_name"] = chosen["name"]
    pending["stage"] = "set_name"
    caller.ndb._pending_recipe = pending

    caller.msg(
        f"  Base: |w{chosen['name']}|n\n"
        f"|x{'─' * _BOX_W}|n\n"
        f"  |xName your creation (3-60 characters):|n"
    )
    return True


def _wizard_set_name(caller, pending, raw):
    from evennia.utils.ansi import strip_ansi
    name = strip_ansi(raw).strip()
    if len(name) < 3 or len(name) > 60:
        caller.msg("|rName must be 3-60 characters. Try again:|n")
        return True

    pending["custom_name"] = name
    pending["stage"] = "set_desc"
    caller.ndb._pending_recipe = pending

    caller.msg(
        f"  Name: |w{name}|n\n"
        f"|x{'─' * _BOX_W}|n\n"
        f"  |xDescribe it — how it looks (10-500 characters):|n"
    )
    return True


def _wizard_set_desc(caller, pending, raw):
    from evennia.utils.ansi import strip_ansi
    desc = strip_ansi(raw).strip()
    if len(desc) < 10 or len(desc) > 500:
        caller.msg("|rDescription must be 10-500 characters. Try again:|n")
        return True

    pending["custom_desc"] = desc
    pending["stage"] = "set_taste"
    caller.ndb._pending_recipe = pending

    caller.msg(
        f"  Description set.\n"
        f"|x{'─' * _BOX_W}|n\n"
        f"  |xTaste message — what the consumer experiences (10-300 characters):|n"
    )
    return True


def _wizard_set_taste(caller, pending, raw):
    from evennia.utils.ansi import strip_ansi
    taste = strip_ansi(raw).strip()
    if len(taste) < 10 or len(taste) > 300:
        caller.msg("|rTaste message must be 10-300 characters. Try again:|n")
        return True

    pending["custom_taste"] = taste
    pending["extra_ingredients"] = []
    pending["stage"] = "add_extras"
    caller.ndb._pending_recipe = pending

    caller.msg(
        f"  Taste set.\n"
        f"|x{'─' * _BOX_W}|n\n"
        f"  |xAdd a flavor note (up to 6, max 80 chars each), or |wfinished|x to skip:|n"
    )
    return True


def _wizard_add_extras(caller, pending, raw):
    from evennia.utils.ansi import strip_ansi

    if raw.lower() == "finished":
        pending["stage"] = "confirm"
        caller.ndb._pending_recipe = pending
        _show_recipe_preview(caller, pending)
        return True

    extras = pending.get("extra_ingredients", [])
    if len(extras) >= 6:
        caller.msg("|rMaximum 6 flavor notes reached. Type |wfinished|r to continue.|n")
        return True

    note = strip_ansi(raw).strip()
    if not note:
        caller.msg("|rEmpty note. Add a flavor note or type |wfinished|r.|n")
        return True
    if len(note) > 80:
        caller.msg("|rFlavor note too long (max 80 characters). Try again:|n")
        return True

    extras.append(note)
    pending["extra_ingredients"] = extras
    caller.ndb._pending_recipe = pending

    remaining = 6 - len(extras)
    caller.msg(
        f"  Added: |x{note}|n\n"
        f"  |xAdd another flavor note ({remaining} remaining), or |wfinished|x:|n"
    )
    return True


def _show_recipe_preview(caller, pending):
    base_name = pending.get("base_name", "???")
    custom_name = pending.get("custom_name", "???")
    custom_desc = pending.get("custom_desc", "")
    custom_taste = pending.get("custom_taste", "")
    extras = pending.get("extra_ingredients", [])

    desc_preview = custom_desc[:80] + "..." if len(custom_desc) > 80 else custom_desc
    taste_preview = custom_taste[:80] + "..." if len(custom_taste) > 80 else custom_taste
    extras_str = ", ".join(extras) if extras else "|xnone|n"

    lines = [
        _header("RECIPE PREVIEW"),
        f"  |wName:|n    {custom_name}",
        f"  |wBase:|n    {base_name}",
        f"  |wDesc:|n    |x{desc_preview}|n",
        f"  |wTaste:|n   |x{taste_preview}|n",
        f"  |wFlavors:|n {extras_str}",
        _footer(),
        f"  |xConfirm? (|wyes|x / |wno|x / |wcancel|x):|n",
    ]
    caller.msg("\n".join(lines))


def _wizard_confirm(caller, pending, raw):
    if raw.lower() in ("no", "n"):
        del caller.ndb._pending_recipe
        caller.msg("|xRecipe discarded.|n")
        return True

    if raw.lower() not in ("yes", "y"):
        caller.msg("|xType |wyes|x to confirm, |wno|x to discard, or |wcancel|x to abort.|n")
        return True

    station = _get_station_from_pending(pending)
    if not station:
        del caller.ndb._pending_recipe
        caller.msg("|rStation no longer found. Recipe creation aborted.|n")
        return True

    from world.food.recipes import create_recipe
    success, msg = create_recipe(
        station,
        caller,
        pending["base_key"],
        pending["custom_name"],
        pending["custom_desc"],
        pending["custom_taste"],
        pending.get("extra_ingredients"),
    )

    del caller.ndb._pending_recipe

    if success:
        caller.msg(f"|g{msg}|n")
    else:
        caller.msg(f"|r{msg}|n")

    return True
