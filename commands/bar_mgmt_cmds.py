"""
Bar management commands.

  barset <station> employee add <name>       — add an employee
  barset <station> employee remove <name>    — remove an employee
  barset <station> employee list             — list employees
  barset <station> price <recipe> = <n>      — set a recipe's price
  barset <station> price default = <n>       — set default drink price
  barset <station> register                  — check register balance
  barset <station> register collect          — collect register into wallet (manager only)
  barset <station> register log              — view recent sales log

Staff only:
  @barset <station> manager = <character>    — set the manager
  @barset <station> tier = <tier>            — set social tier
  @barset <station> name = <name>            — set station display name
"""

from __future__ import annotations

import time

from commands.base_cmds import Command, ADMIN_LOCK

# ── UI helpers ────────────────────────────────────────────────────────────────
_N = "|n"
_W = "|w"
_DIM = "|x"
_G = "|g"
_R = "|r"
_Y = "|y"
_C = "|c"
_BOX_W = 56


def _line(char="─"):
    return f"|x{char * _BOX_W}|n"


def _header(title):
    pad = max(0, _BOX_W - len(title) - 4)
    return f"|c╔══[ |w{title}|c ]{'═' * pad}|n"


def _footer():
    return f"|c╚{'═' * (_BOX_W - 1)}|n"


def _row(label, value, lw=16):
    dots = "·" * max(1, lw - len(label))
    return f"  |w{label}|n |x{dots}|n {value}"


def _find_bar_station(caller, station_arg: str):
    """Find a bar station in caller's room by name."""
    from world.food.stations import find_station_in_room
    station = find_station_in_room(caller, station_arg, station_type="bar")
    return station


# ══════════════════════════════════════════════════════════════════════════════
#  CmdBarSet — barset <station> <subcommand>
# ══════════════════════════════════════════════════════════════════════════════

class CmdBarSet(Command):
    """
    Manage a bar station. Requires manager access.

    Usage:
      barset <station> employee add <name>
      barset <station> employee remove <name>
      barset <station> employee list
      barset <station> price <recipe> = <amount>
      barset <station> price default = <amount>
      barset <station> register
      barset <station> register collect
      barset <station> register log

    Only the bar manager can use these commands.
    'register collect' transfers all register funds to your wallet.
    """

    key = "barset"
    locks = "cmd:all()"
    help_category = "Food & Drink"

    def func(self):
        from world.food.stations import is_bar_manager, is_staff

        caller = self.caller
        raw = (self.args or "").strip()

        if not raw:
            caller.msg(
                "Usage: |wbarset <station> <subcommand>|n\n"
                "Subcommands: |wemployee add/remove/list|n, |wprice <recipe> = <n>|n, "
                "|wprice default = <n>|n, |wregister|n, |wregister collect|n, |wregister log|n"
            )
            return

        parts = raw.split(None, 1)
        station_arg = parts[0]
        rest = parts[1].strip() if len(parts) > 1 else ""

        station = _find_bar_station(caller, station_arg)
        if not station:
            return

        if not is_bar_manager(caller, station) and not is_staff(caller):
            caller.msg("|rOnly the bar manager can use barset.|n")
            return

        if not rest:
            caller.msg(
                "Specify a subcommand: |wemployee|n, |wprice|n, or |wregister|n."
            )
            return

        rest_lower = rest.lower()

        # ── employee subcommands ──────────────────────────────────────────────
        if rest_lower.startswith("employee"):
            self._handle_employee(caller, station, rest[8:].strip())
            return

        # ── price subcommands ─────────────────────────────────────────────────
        if rest_lower.startswith("price"):
            self._handle_price(caller, station, rest[5:].strip())
            return

        # ── register subcommands ──────────────────────────────────────────────
        if rest_lower.startswith("register"):
            self._handle_register(caller, station, rest[8:].strip())
            return

        caller.msg(
            "Unknown subcommand. Use |wemployee|n, |wprice|n, or |wregister|n."
        )

    def _handle_employee(self, caller, station, rest: str):
        from evennia.utils.search import search_object

        parts = rest.split(None, 1)
        sub = parts[0].lower() if parts else ""
        name_arg = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list":
            employees = list(getattr(station.db, "employees", None) or [])
            if not employees:
                caller.msg("No employees registered.")
                return
            lines = [_header("EMPLOYEES")]
            for emp_id in employees:
                results = search_object(f"#{emp_id}")
                emp_name = results[0].key if results else f"#{emp_id} (not found)"
                lines.append(f"  |w{emp_name}|n")
            lines.append(_footer())
            caller.msg("\n".join(lines))
            return

        if not name_arg:
            caller.msg("Usage: |wbarset <station> employee add/remove <name>|n")
            return

        target = caller.search(name_arg, location=caller.location)
        if not target:
            return

        employees = list(getattr(station.db, "employees", None) or [])
        target_id = getattr(target, "id", None)

        if sub == "add":
            if target_id in employees:
                caller.msg(f"{target.key} is already an employee.")
                return
            employees.append(target_id)
            station.db.employees = employees
            caller.msg(f"|g{target.key} added as an employee.|n")
            target.msg(f"You have been added as an employee at |w{station.db.station_name or station.key}|n.")
            return

        if sub == "remove":
            if target_id not in employees:
                caller.msg(f"{target.key} is not an employee.")
                return
            employees.remove(target_id)
            station.db.employees = employees
            caller.msg(f"|g{target.key} removed from employees.|n")
            target.msg(f"You have been removed as an employee at |w{station.db.station_name or station.key}|n.")
            return

        caller.msg("Usage: |wbarset <station> employee add/remove/list|n")

    def _handle_price(self, caller, station, rest: str):
        from world.rpg.economy import format_currency

        if not rest:
            caller.msg("Usage: |wbarset <station> price <recipe> = <amount>|n or |wprice default = <amount>|n")
            return

        if "=" not in rest:
            caller.msg("Usage: |wbarset <station> price <recipe> = <amount>|n")
            return

        left, right = rest.split("=", 1)
        target_name = left.strip()
        try:
            amount = int(right.strip().replace(",", ""))
        except ValueError:
            caller.msg("Price must be a number.")
            return

        if amount < 0:
            caller.msg("Price cannot be negative.")
            return

        if target_name.lower() == "default":
            station.db.drink_price_default = amount
            caller.msg(f"|gDefault drink price set to {format_currency(amount)}.|n")
            return

        # Per-recipe price
        recipes = list(getattr(station.db, "recipes", None) or [])
        match = None
        for r in recipes:
            if r.get("custom_name", "").lower() == target_name.lower():
                match = r
                break

        if not match:
            caller.msg(f"|rNo recipe called '{target_name}' on the menu.|n")
            return

        prices = dict(getattr(station.db, "recipe_prices", None) or {})
        prices[target_name.lower()] = amount
        station.db.recipe_prices = prices
        caller.msg(f"|gPrice for '{match['custom_name']}' set to {format_currency(amount)}.|n")

    def _handle_register(self, caller, station, rest: str):
        from world.rpg.economy import format_currency, add_funds

        sub = rest.lower().strip()

        if sub == "collect":
            balance = int(getattr(station.db, "register_balance", 0) or 0)
            if balance <= 0:
                caller.msg("The register is empty.")
                return
            add_funds(caller, balance)
            station.db.register_balance = 0
            caller.msg(f"|gYou collect {format_currency(balance)} from the register.|n")
            return

        if sub == "log":
            log = list(getattr(station.db, "register_log", None) or [])
            if not log:
                caller.msg("No sales recorded yet.")
                return
            lines = [_header("REGISTER LOG")]
            for entry in reversed(log[-20:]):
                t = time.strftime("%m/%d %H:%M", time.localtime(entry.get("time", 0)))
                amt = format_currency(entry.get("amount", 0))
                employee = entry.get("employee", "?")
                recipe = entry.get("recipe", "?")
                lines.append(
                    f"  |x{t}|n  {amt}  |w{recipe}|n  "
                    f"|xby {employee}|n"
                )
            lines.append(_footer())
            caller.msg("\n".join(lines))
            return

        # Default: show balance
        balance = int(getattr(station.db, "register_balance", 0) or 0)
        station_name = getattr(station.db, "station_name", None) or station.key
        lines = [
            _header(f"REGISTER — {station_name.upper()}"),
            _row("Balance", format_currency(balance)),
            _footer(),
            f"  |xUse |wbarset {station.key} register collect|x to withdraw.|n",
        ]
        caller.msg("\n".join(lines))


# ══════════════════════════════════════════════════════════════════════════════
#  CmdBarSetAdmin — @barset <station> <subcommand>  (staff only)
# ══════════════════════════════════════════════════════════════════════════════

class CmdBarSetAdmin(Command):
    """
    Configure a bar station (staff only).

    Usage:
      @barset <station> manager = <character>
      @barset <station> tier = <tier>
      @barset <station> name = <name>

    Tiers: gutter, slum, guild, bourgeois, elite

    Example:
      @barset bar manager = Jake
      @barset bar tier = guild
      @barset bar name = The Marrow Bar
    """

    key = "@barset"
    aliases = ["@barset"]
    locks = ADMIN_LOCK
    help_category = "Admin"

    def func(self):
        from world.food import SOCIAL_TIERS
        from evennia.utils.search import search_object

        caller = self.caller
        raw = (self.args or "").strip()

        if not raw:
            caller.msg("Usage: |w@barset <station> <sub> = <value>|n")
            return

        parts = raw.split(None, 1)
        station_arg = parts[0]
        rest = parts[1].strip() if len(parts) > 1 else ""

        station = _find_bar_station(caller, station_arg)
        if not station:
            return

        if "=" not in rest:
            caller.msg(
                "Usage: |w@barset <station> manager = <char>|n | "
                "|wtier = <tier>|n | |wname = <name>|n"
            )
            return

        sub, val = rest.split("=", 1)
        sub = sub.strip().lower()
        val = val.strip()

        if sub == "manager":
            if not val:
                caller.msg("Provide a character name.")
                return
            results = caller.search(val, global_search=True)
            if not results:
                return
            target = results if not isinstance(results, list) else results[0]
            station.db.manager_id = target.id
            station_name = getattr(station.db, "station_name", None) or station.key
            caller.msg(f"|g{target.key} set as manager of {station_name}.|n")
            target.msg(f"You have been set as manager of |w{station_name}|n.")
            return

        if sub == "tier":
            tier_key = val.lower()
            if tier_key not in SOCIAL_TIERS:
                valid = ", ".join(SOCIAL_TIERS.keys())
                caller.msg(f"|rUnknown tier '{val}'. Valid tiers: {valid}|n")
                return
            station.db.social_tier = tier_key
            from world.food import get_tier_name
            caller.msg(f"|gStation tier set to {get_tier_name(tier_key)}.|n")
            return

        if sub == "name":
            if not val:
                caller.msg("Provide a station name.")
                return
            station.db.station_name = val
            caller.msg(f"|gStation name set to '{val}'.|n")
            return

        caller.msg(
            "Unknown subcommand. Use |wmanager|n, |wtier|n, or |wname|n."
        )
