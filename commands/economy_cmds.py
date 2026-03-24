"""
Economy commands: pay, dropm, list (shop), buy, wire, bank.

  count / count money       -- check your on-hand cash (via roleplay_cmds.CmdCount)
  pay <target> <amount>     -- hand cash to a character or NPC in the room
  dropm <amount>            -- drop a cash pile on the ground
  list                      -- show shop listing if a vendor is in the room
  buy <item> [qty]          -- purchase from a vendor in the room
  buy <qty> <item>          -- alternate syntax
  buy <item> haggle         -- attempt to haggle for a discount
  wire <network_id> <amount>-- Matrix wire transfer (requires signal coverage)
  bank                      -- open bank EvMenu (requires bank room or terminal)

Staff commands:
  @shopset <vendor> ...     -- configure a vendor's shop
  @shopitem <vendor> ...    -- add/remove/restock items
  @spawnbank                -- spawn a bank terminal object in the current room
"""

from __future__ import annotations

import random

from commands.base_cmds import Command
from world.rpg.economy import (
    CURRENCY_NAME,
    format_currency,
    get_balance,
    transfer_funds,
    format_transaction_log,
    add_funds,
    deduct_funds,
)
from world.rpg.bank import has_account, get_bank_balance
from world.rpg.shop import find_vendor_in_room, format_shop_listing, buy_item

# ---------------------------------------------------------------------------
# Shared UI helpers  (open-right-border, ANSIString-safe)
# ---------------------------------------------------------------------------

_W = 60
_N = "|n"
_DIM = "|x"
_LABEL = "|w"
_ACCENT = "|c"
_GOLD = "|y"
_ERR = "|r"
_OK = "|g"


def _pline(content="", indent=2):
    """Panel row: left border + content, no right border (ANSI-safe)."""
    from evennia.utils.ansi import ANSIString
    padded = ANSIString(f"{' ' * indent}{content}").ljust(_W - 1)
    return f"{_ACCENT}│{_N}{padded}"


def _pheader(title, subtitle=None):
    """Decorative open-right panel header."""
    from evennia.utils.ansi import ANSIString
    from world.ui_utils import fade_rule
    title_len = len(ANSIString(title))
    left_fill = 3
    right_w = max(4, _W - 1 - left_fill - title_len - 2)
    top = (
        f"{_ACCENT}╔{'═' * left_fill}"
        f"[{_GOLD}{title}{_ACCENT}]"
        f"{_DIM}{fade_rule(right_w, '═')}{_N}"
    )
    lines = [top]
    if subtitle:
        lines.append(_pline(f"{_DIM}{subtitle}{_N}"))
    from world.ui_utils import fade_rule as _fr
    lines.append(f"{_ACCENT}╟{_DIM}{_fr(_W - 1, '─')}{_N}")
    return "\n".join(lines)


def _psection(label):
    """In-panel section label with fading rule."""
    from world.ui_utils import fade_rule
    raw = f"── {label} "
    rest = max(0, _W - 1 - len(raw))
    return f"{_DIM}{raw}{fade_rule(rest, '─')}{_N}"


def _pkv(key, value, key_w=12):
    """Key · · · value row."""
    dots = "." * max(1, key_w - len(key))
    return _pline(f"{_LABEL}{key}{_N}{_DIM}{dots}{_N} {value}")


def _pclose():
    from world.ui_utils import fade_rule
    return f"{_ACCENT}╚{_DIM}{fade_rule(_W - 1, '─')}{_N}"


def _receipt(vendor_name, items_desc, total, remaining_wallet):
    """Return a styled purchase receipt."""
    return "\n".join([
        _pheader("RECEIPT"),
        _pkv("Vendor",    vendor_name),
        _pkv("Item",      items_desc),
        _pline(),
        _psection("PAYMENT"),
        _pkv("Paid",      format_currency(total)),
        _pkv("On Hand",   format_currency(remaining_wallet)),
        _pline(),
        _pclose(),
    ])


# ---------------------------------------------------------------------------
# CmdPay
# ---------------------------------------------------------------------------

class CmdPay(Command):
    """
    Pay another character or NPC with cash from your wallet.

    Usage:
      pay <target> <amount>
      pay <target> = <amount>

    The target must be in the same room. Money is transferred immediately
    from your on-hand wallet; no bank account required.

    Example:
      pay Kira 50
      pay the_merchant = 200
    """

    key = "pay"
    locks = "cmd:all()"
    help_category = "Economy"

    def func(self):
        caller = self.caller
        raw = (self.args or "").strip()

        if not raw:
            caller.msg("Usage: pay <target> <amount>")
            return

        # Parse: "target amount" or "target = amount"
        if "=" in raw:
            parts = raw.split("=", 1)
            target_str = parts[0].strip()
            amount_str = parts[1].strip()
        else:
            tokens = raw.rsplit(None, 1)
            if len(tokens) < 2:
                caller.msg("Usage: pay <target> <amount>")
                return
            target_str, amount_str = tokens[0].strip(), tokens[1].strip()

        # Parse amount
        try:
            amount = int(amount_str.replace(",", ""))
        except ValueError:
            caller.msg(f"{_ERR}Invalid amount.{_N}")
            return

        if amount <= 0:
            caller.msg(f"{_ERR}Amount must be positive.{_N}")
            return

        # Resolve target in room
        target = caller.search(target_str, location=caller.location)
        if not target:
            return

        if target == caller:
            caller.msg(f"{_ERR}You can't pay yourself.{_N}")
            return

        # Check funds
        wallet = get_balance(caller)
        if wallet < amount:
            caller.msg(
                f"{_ERR}You only have {format_currency(wallet)} on hand.{_N}"
            )
            return

        # Transfer
        ok, msg = transfer_funds(caller, target, amount, reason="cash payment")
        if not ok:
            caller.msg(f"{_ERR}{msg}{_N}")
            return

        # Room messages
        caller_name = caller.key
        target_name = target.key
        amt_str = format_currency(amount)

        caller.msg(
            f"You count out {amt_str} and hand it to {_LABEL}{target_name}{_N}."
        )
        target.msg(
            f"{_LABEL}{caller_name}{_N} hands you {amt_str}."
        )
        caller.location.msg_contents(
            f"{_LABEL}{caller_name}{_N} counts out {amt_str} and hands it to {_LABEL}{target_name}{_N}.",
            exclude=[caller, target],
        )


# ---------------------------------------------------------------------------
# CmdDropMoney
# ---------------------------------------------------------------------------

# Tag and typeclass used to identify cash pile objects on the ground.
_CASH_PILE_TAG = "cash_pile"
_CASH_PILE_TAG_CAT = "economy"


def _find_cash_pile_in_room(room):
    """Return the first cash pile object in the room, or None."""
    for obj in room.contents:
        if obj.tags.get(_CASH_PILE_TAG, category=_CASH_PILE_TAG_CAT):
            return obj
    return None


class CmdDropMoney(Command):
    """
    Drop cash on the ground for others to pick up.

    Usage:
      dropm <amount>
      dropm all

    Drops the specified amount from your on-hand cash as a pile on the
    ground. Anyone in the room can pick it up with 'get <pile name>'.
    Multiple drops stack into a single pile per room.

    Example:
      dropm 50
      dropm all
    """

    key = "dropm"
    aliases = ["dropmoney"]
    locks = "cmd:all()"
    help_category = "Economy"

    def func(self):
        caller = self.caller
        raw = (self.args or "").strip()

        if not raw:
            caller.msg("Usage: dropm <amount>  or  dropm all")
            return

        room = caller.location
        if not room:
            caller.msg("You aren't anywhere.")
            return

        wallet = get_balance(caller)
        if wallet == 0:
            caller.msg(f"You have no {CURRENCY_NAME} to drop.")
            return

        if raw.lower() == "all":
            amount = wallet
        else:
            try:
                amount = int(raw.replace(",", ""))
            except ValueError:
                caller.msg(f"|rInvalid amount.|n")
                return

        if amount <= 0:
            caller.msg("|rAmount must be positive.|n")
            return

        if amount > wallet:
            caller.msg(
                f"|rYou only have {format_currency(wallet)} on hand.|n"
            )
            return

        # Deduct from wallet
        ok = deduct_funds(caller, amount, party="ground", reason="dropped cash")
        if not ok:
            caller.msg("|rTransaction failed.|n")
            return

        # Stack onto existing pile in room, or create a new one
        pile = _find_cash_pile_in_room(room)
        if pile:
            existing = int(getattr(pile.db, "cash_amount", 0) or 0)
            pile.db.cash_amount = existing + amount
            pile.key = _cash_pile_name(existing + amount)
            pile.db.desc = _cash_pile_desc(existing + amount)
        else:
            from evennia import create_object
            from evennia.objects.objects import DefaultObject
            pile = create_object(
                DefaultObject,
                key=_cash_pile_name(amount),
                location=room,
            )
            pile.tags.add(_CASH_PILE_TAG, category=_CASH_PILE_TAG_CAT)
            pile.db.cash_amount = amount
            pile.db.desc = _cash_pile_desc(amount)

        amt_str = format_currency(amount)
        caller.msg(f"You drop {amt_str} on the ground.")
        room.msg_contents(
            f"|w{caller.key}|n drops {amt_str} on the ground.",
            exclude=[caller],
        )


def _cash_pile_name(amount):
    return f"a pile of {CURRENCY_NAME}"


def _cash_pile_desc(amount):
    return (
        f"A loose pile of {format_currency(amount, color=False)} "
        f"sitting here on the ground."
    )


# ---------------------------------------------------------------------------
# CmdShopList
# ---------------------------------------------------------------------------

class CmdShopList(Command):
    """
    Browse what's for sale at a vendor in the room.

    Usage:
      list
      list <vendor name>   -- if multiple vendors are present

    Shows all items, their prices, and stock. Restricted items are shown
    with a [RESTRICTED] label. Sale items display the discounted price.
    """

    key = "list"
    locks = "cmd:all()"
    help_category = "Economy"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()

        room = caller.location
        if not room:
            caller.msg("You aren't anywhere.")
            return

        if args:
            vendor = caller.search(args, location=room)
            if not vendor:
                return
            if getattr(vendor.db, "shop_inventory", None) is None:
                caller.msg(f"{vendor.key} doesn't sell anything.")
                return
        else:
            vendor = find_vendor_in_room(room)
            if not vendor:
                caller.msg("There's nothing for sale here.")
                return

        caller.msg(format_shop_listing(vendor, caller))


# ---------------------------------------------------------------------------
# CmdBuy
# ---------------------------------------------------------------------------

_HAGGLE_SKILL = "diplomacy"
_HAGGLE_DISCOUNT_MIN = 5    # percent
_HAGGLE_DISCOUNT_MAX = 15
_HAGGLE_FAIL_MARKUP = 5     # percent price increase on critical fail


class CmdBuy(Command):
    """
    Purchase an item from a vendor in the room.

    Usage:
      buy <item number>
      buy <item number> <quantity>
      buy <quantity> <item number>
      buy <item number> haggle      -- attempt to negotiate a discount

    Use 'list' to see what's available and the item numbers.

    Examples:
      buy 1
      buy 3 2          -- buy 2 of item #3
      buy 1 haggle     -- try to haggle on item #1
    """

    key = "buy"
    locks = "cmd:all()"
    help_category = "Economy"

    def func(self):
        caller = self.caller
        raw = (self.args or "").strip()

        if not raw:
            caller.msg("Usage: buy <item number> [quantity] [haggle]")
            return

        room = caller.location
        if not room:
            caller.msg("You aren't anywhere.")
            return

        vendor = find_vendor_in_room(room)
        if not vendor:
            caller.msg("There's nothing for sale here.")
            return

        # Parse: haggle flag
        haggle = False
        tokens = raw.split()
        if tokens and tokens[-1].lower() == "haggle":
            haggle = True
            tokens = tokens[:-1]

        if not tokens:
            caller.msg("Usage: buy <item number> [quantity] [haggle]")
            return

        # Parse item ref and quantity
        # Formats: "1", "1 2" (item 1, qty 2), "2 1" (qty 2, item 1)
        item_ref = tokens[0]
        qty = 1
        if len(tokens) >= 2:
            try:
                qty = int(tokens[1])
            except ValueError:
                pass
            try:
                # "buy 2 1" — first token is qty, second is item
                qty_first = int(tokens[0])
                item_ref = tokens[1]
                qty = qty_first
            except ValueError:
                pass

        if qty < 1:
            qty = 1

        # Haggle: roll diplomacy for discount
        if haggle:
            self._do_haggle_buy(caller, vendor, item_ref, qty)
            return

        ok, msg, spawned = buy_item(caller, vendor, item_ref, qty)
        if not ok:
            caller.msg(f"{_ERR}{msg}{_N}")
            return

        # Success receipt
        item = vendor.get_item_by_number(item_ref) or vendor.get_item_by_key(str(item_ref))
        item_name = item["name"] if item else str(item_ref)
        qty_str = f" ×{qty}" if qty > 1 else ""

        from world.rpg.shop import _effective_price
        price = _effective_price(item) * qty if item else 0

        caller.msg(_receipt(
            getattr(vendor.db, "shop_name", None) or vendor.key,
            f"{item_name}{qty_str}",
            price,
            get_balance(caller),
        ))

        if spawned:
            for obj in spawned:
                caller.msg(f"You receive {_LABEL}{obj.key}{_N}.")

        # Vendor emote
        vendor_name = vendor.key
        caller.location.msg_contents(
            f"{_LABEL}{vendor_name}{_N} hands {_LABEL}{caller.key}{_N} their purchase.",
            exclude=[caller],
        )

    def _do_haggle_buy(self, caller, vendor, item_ref, qty):
        """Attempt a diplomacy skill check to get a discount."""
        item = None
        if hasattr(vendor, "get_item_by_number"):
            item = vendor.get_item_by_number(item_ref)
        if not item and hasattr(vendor, "get_item_by_key"):
            item = vendor.get_item_by_key(str(item_ref))
        if not item:
            caller.msg(f"{_ERR}That item isn't available here.{_N}")
            return

        from world.rpg.shop import _effective_price, _item_accessible, STOCK_UNLIMITED
        accessible, reason = _item_accessible(item, caller)
        if not accessible:
            caller.msg(f"{_ERR}{reason}{_N}")
            return

        stock = item.get("stock", STOCK_UNLIMITED)
        if stock == 0:
            caller.msg(f"{_ERR}{item['name']} is sold out.{_N}")
            return

        base_price = _effective_price(item)

        # Skill roll
        diplomacy = (getattr(caller.db, "skills", {}) or {}).get(_HAGGLE_SKILL, 0)
        roll = random.randint(1, 150)
        success = roll <= diplomacy

        vendor_name = vendor.key

        if success:
            discount_pct = random.randint(_HAGGLE_DISCOUNT_MIN, _HAGGLE_DISCOUNT_MAX)
            discount = max(1, int(base_price * discount_pct / 100))
            final_price = max(1, base_price - discount)

            caller.location.msg_contents(
                f"{_LABEL}{caller.key}{_N} talks {_LABEL}{vendor_name}{_N} down on the price.",
                exclude=[caller],
            )
            caller.msg(
                f"{_OK}{vendor_name} agrees to a {discount_pct}% discount.{_N} "
                f"Price: {format_currency(final_price)} (was {format_currency(base_price)})."
            )

            # Temporarily override price for this purchase
            import copy
            temp_item = copy.deepcopy(item)
            temp_item["price"] = final_price
            temp_item["sale_price"] = None
            temp_item["sale_until"] = None

            # Inline purchase with modified price
            wallet = get_balance(caller)
            total = final_price * qty
            if wallet < total:
                caller.msg(f"{_ERR}You need {format_currency(total)} but only have {format_currency(wallet)}.{_N}")
                return

            from world.rpg.economy import deduct_funds
            ok = deduct_funds(caller, total, party=vendor_name, reason=f"haggle purchase: {item['name']} x{qty}")
            if not ok:
                caller.msg(f"{_ERR}Transaction failed.{_N}")
                return

            # Decrement stock
            if stock != STOCK_UNLIMITED:
                inv = list(vendor.db.shop_inventory or [])
                for i, it in enumerate(inv):
                    if it.get("key") == item.get("key"):
                        inv[i]["stock"] = max(0, stock - qty)
                        break
                vendor.db.shop_inventory = inv

            # Spawn
            spawned = []
            prototype_key = item.get("prototype")
            if prototype_key:
                from evennia.prototypes.spawner import spawn
                for _ in range(qty):
                    try:
                        objs = spawn(prototype_key)
                        if objs:
                            obj = objs[0]
                            obj.location = caller
                            spawned.append(obj)
                    except Exception as e:
                        from evennia.utils import logger
                        logger.log_err(f"haggle spawn error: {e}")

            qty_str = f" ×{qty}" if qty > 1 else ""
            caller.msg(_receipt(
                getattr(vendor.db, "shop_name", None) or vendor_name,
                f"{item['name']}{qty_str} (haggled)",
                total,
                get_balance(caller),
            ))
            for obj in spawned:
                caller.msg(f"You receive {_LABEL}{obj.key}{_N}.")

        else:
            # Failed haggle — vendor is annoyed; possible price markup
            crit_fail = roll > int(diplomacy * 1.5) + 10
            if crit_fail:
                markup_pct = _HAGGLE_FAIL_MARKUP
                new_price = int(base_price * (1 + markup_pct / 100))
                caller.msg(
                    f"{_ERR}{vendor_name} scowls at the attempt. "
                    f"The price just went up to {format_currency(new_price)}.{_N}"
                )
                caller.location.msg_contents(
                    f"{_LABEL}{vendor_name}{_N} looks annoyed at {_LABEL}{caller.key}{_N}'s haggling.",
                    exclude=[caller],
                )
            else:
                caller.msg(
                    f"{_DIM}{vendor_name} shakes their head. No deal.{_N} "
                    f"Regular price: {format_currency(base_price)}."
                )
                caller.location.msg_contents(
                    f"{_LABEL}{caller.key}{_N} tries to haggle with {_LABEL}{vendor_name}{_N}, without success.",
                    exclude=[caller],
                )


# ---------------------------------------------------------------------------
# CmdWire
# ---------------------------------------------------------------------------

class CmdWire(Command):
    """
    Send a Matrix wire transfer to another character's bank account.

    Usage:
      wire <@alias or ^MatrixID> <amount>

    Requires:
      - You must have a bank account with sufficient funds.
      - You must be in a room with active Matrix signal coverage.
      - A small percentage fee is charged on all wire transfers.

    The recipient is identified by their Matrix alias (@handle) or
    Matrix ID (^XXXXXX). You can find someone's alias on the Network.

    Example:
      wire @kira 500
      wire ^AB12CD 1000
    """

    key = "wire"
    locks = "cmd:all()"
    help_category = "Economy"

    def func(self):
        caller = self.caller
        raw = (self.args or "").strip()

        if not raw:
            caller.msg("Usage: wire <@alias or ^MatrixID> <amount>")
            return

        tokens = raw.rsplit(None, 1)
        if len(tokens) < 2:
            caller.msg("Usage: wire <@alias or ^MatrixID> <amount>")
            return

        network_id = tokens[0].strip()
        try:
            amount = int(tokens[1].replace(",", ""))
        except ValueError:
            caller.msg(f"{_ERR}Invalid amount.{_N}")
            return

        if amount <= 0:
            caller.msg(f"{_ERR}Amount must be positive.{_N}")
            return

        # Signal check
        from world.utils import get_containing_room, room_has_network_coverage
        room = get_containing_room(caller)
        if not room_has_network_coverage(room, include_matrix_nodes=True):
            caller.msg(
                f"{_ERR}No Matrix signal.{_N} Wire transfers require network coverage.\n"
                f"{_DIM}Find a room with an active router to send a wire.{_N}"
            )
            return

        # Bank account check
        if not has_account(caller):
            caller.msg(
                f"{_ERR}You don't have a bank account.{_N} "
                f"Visit a bank terminal to open one."
            )
            return

        # Show confirmation panel before executing
        from world.rpg.bank import _compute_wire_fee, _resolve_wire_recipient
        recipient = _resolve_wire_recipient(network_id)
        if not recipient:
            caller.msg(f"{_ERR}No account found for '{network_id}'.{_N}")
            return

        fee = _compute_wire_fee(amount)
        total = amount + fee
        bank_bal = get_bank_balance(caller)

        lines = [
            _pheader("WIRE TRANSFER", subtitle="Review before confirming."),
            _pkv("To",      f"{_ACCENT}{network_id}{_N}  {_DIM}({recipient.key}){_N}"),
            _pkv("Amount",  format_currency(amount)),
            _pkv("Fee",     f"{format_currency(fee)}  {_DIM}(1%){_N}"),
            _pkv("Total",   f"{_GOLD}{format_currency(total, color=False)}{_N}"),
            _pline(),
            _psection("ACCOUNT"),
            _pkv("Bank Bal", format_currency(bank_bal)),
            _pline(),
            _pline(f"Type {_LABEL}yes{_N} to confirm, or anything else to cancel."),
            _pline(),
            _pclose(),
        ]
        caller.msg("\n".join(lines))

        # Store pending wire on ndb for confirmation
        caller.ndb._pending_wire = {
            "network_id": network_id,
            "amount": amount,
            "fee": fee,
        }


class CmdWireConfirm(Command):
    """
    Universal yes-confirmation dispatcher.

    Routes 'yes' to whichever pending-input flow is currently active
    (wire transfer, recipe wizard, serve offer, etc.).  If nothing is
    pending, prints a neutral message.
    """

    key = "yes"
    locks = "cmd:all()"
    help_category = "Economy"
    auto_help = False

    def func(self):
        caller = self.caller
        try:
            from commands.pending_dispatch import dispatch_pending_input
            if dispatch_pending_input(caller, "yes"):
                return
        except Exception:
            pass
        caller.msg("(Nothing to confirm.)")


# ---------------------------------------------------------------------------
# CmdBankMenu
# ---------------------------------------------------------------------------

def _is_bank_location(room):
    """
    Return (is_bank: bool, terminal_or_None).

    A location qualifies as a bank if:
      - The room itself is tagged 'bank' (any category), OR
      - The room contains an object tagged 'bank_terminal'.
    """
    if not room:
        return False, None

    # Room-level bank tag
    if room.tags.get("bank") or room.tags.get("bank", category="bank"):
        # Use a sentinel terminal so the menu still works
        return True, None

    # Object-level terminal
    for obj in room.contents:
        if obj.tags.get("bank_terminal", category="bank_terminal"):
            return True, obj
        if obj.tags.get("bank_terminal"):
            return True, obj

    return False, None


class CmdBankMenu(Command):
    """
    Access banking services.

    Usage:
      bank

    You must be in a bank room (a room tagged 'bank') or a room containing
    a bank terminal object. From the terminal you can:

      - Check your balance
      - Deposit or withdraw cash
      - Send wire transfers (requires Matrix signal)
      - View your transaction history
      - Open a new account (first visit)
    """

    key = "bank"
    locks = "cmd:all()"
    help_category = "Economy"

    def func(self):
        caller = self.caller
        room = caller.location
        if not room:
            caller.msg("You aren't anywhere.")
            return

        is_bank, terminal = _is_bank_location(room)
        if not is_bank:
            caller.msg(
                f"{_DIM}You need to be at a bank to do that.{_N}\n"
                f"Find a bank branch in the city."
            )
            return

        from world.rpg.bank import start_bank_menu
        start_bank_menu(caller, terminal)


# ---------------------------------------------------------------------------
# Staff: @shopset
# ---------------------------------------------------------------------------

class CmdShopSet(Command):
    """
    Configure a vendor's shop settings.

    Usage:
      @shopset <vendor> name = <shop name>
      @shopset <vendor> desc = <description>
      @shopset <vendor> open
      @shopset <vendor> close
      @shopset <vendor> faction = <faction_key>
      @shopset <vendor> faction =        (clear restriction)
      @shopset <vendor> info

    Examples:
      @shopset merchant name = Blackwood Surplus
      @shopset merchant desc = General goods and supplies
      @shopset merchant faction = IMP
    """

    key = "@shopset"
    aliases = ["shopset"]
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        caller = self.caller
        raw = (self.args or "").strip()

        if not raw:
            caller.msg("Usage: @shopset <vendor> <setting> [= <value>]")
            return

        # Split vendor from rest
        parts = raw.split(None, 1)
        vendor_str = parts[0]
        rest = parts[1].strip() if len(parts) > 1 else ""

        vendor = caller.search(vendor_str)
        if not vendor:
            return

        if not rest:
            caller.msg("Usage: @shopset <vendor> <setting> [= <value>]")
            return

        if "=" in rest:
            setting, value = rest.split("=", 1)
            setting = setting.strip().lower()
            value = value.strip()
        else:
            setting = rest.strip().lower()
            value = None

        if setting == "name":
            vendor.db.shop_name = value
            caller.msg(f"Shop name set to '{value}'.")
        elif setting == "desc":
            vendor.db.shop_desc = value
            caller.msg(f"Shop description set.")
        elif setting == "open":
            vendor.db.shop_open = True
            caller.msg(f"{vendor.key} is now open for business.")
        elif setting == "close":
            vendor.db.shop_open = False
            caller.msg(f"{vendor.key} is now closed.")
        elif setting == "faction":
            vendor.db.shop_faction = value or None
            if value:
                caller.msg(f"Shop restricted to faction '{value}'.")
            else:
                caller.msg("Shop faction restriction cleared.")
        elif setting == "info":
            inv = list(vendor.db.shop_inventory or [])
            caller.msg(
                f"Vendor: {vendor.key}\n"
                f"  Shop name: {vendor.db.shop_name}\n"
                f"  Desc: {vendor.db.shop_desc}\n"
                f"  Open: {vendor.db.shop_open}\n"
                f"  Faction: {vendor.db.shop_faction}\n"
                f"  Items: {len(inv)}"
            )
        else:
            caller.msg(f"Unknown setting '{setting}'. Use: name, desc, open, close, faction, info.")


# ---------------------------------------------------------------------------
# Staff: @shopitem
# ---------------------------------------------------------------------------

class CmdShopItem(Command):
    """
    Add, remove, or restock items in a vendor's shop.

    Usage:
      @shopitem <vendor> add <key> = <name> | <price> | <desc> [| <prototype>] [| <stock>]
      @shopitem <vendor> remove <key>
      @shopitem <vendor> restock <key> <amount>
      @shopitem <vendor> sale <key> <sale_price> <hours>
      @shopitem <vendor> list
      @shopitem <vendor> clear

    The pipe | separates fields in the add command.
    Use stock=-1 for unlimited stock (default).

    Examples:
      @shopitem merchant add stim = Stim Pack | 80 | Quick stimulant | stim_pack_proto | 12
      @shopitem merchant remove stim
      @shopitem merchant restock stim 20
      @shopitem merchant sale stim 60 24
    """

    key = "@shopitem"
    aliases = ["shopitem"]
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        caller = self.caller
        raw = (self.args or "").strip()

        if not raw:
            caller.msg("Usage: @shopitem <vendor> <sub> ...")
            return

        parts = raw.split(None, 2)
        if len(parts) < 2:
            caller.msg("Usage: @shopitem <vendor> <sub> ...")
            return

        vendor_str = parts[0]
        sub = parts[1].lower()
        rest = parts[2].strip() if len(parts) > 2 else ""

        vendor = caller.search(vendor_str)
        if not vendor:
            return

        if vendor.db.shop_inventory is None:
            vendor.db.shop_inventory = []

        from world.rpg.shop import add_shop_item, remove_shop_item, restock_item, set_sale, STOCK_UNLIMITED

        if sub == "list":
            inv = list(vendor.db.shop_inventory or [])
            if not inv:
                caller.msg("No items in inventory.")
                return
            lines = [f"Inventory for {vendor.key}:"]
            for i, it in enumerate(inv, 1):
                stock = it.get("stock", STOCK_UNLIMITED)
                stock_str = "∞" if stock == STOCK_UNLIMITED else str(stock)
                lines.append(
                    f"  {i}. [{it['key']}] {it['name']} — "
                    f"{format_currency(it['price'])} — stock: {stock_str}"
                )
            caller.msg("\n".join(lines))
            return

        if sub == "clear":
            vendor.db.shop_inventory = []
            caller.msg(f"Cleared all items from {vendor.key}.")
            return

        if sub == "remove":
            if not rest:
                caller.msg("Usage: @shopitem <vendor> remove <key>")
                return
            ok, msg = remove_shop_item(vendor, rest.strip())
            caller.msg(msg)
            return

        if sub == "restock":
            tokens = rest.split()
            if len(tokens) < 2:
                caller.msg("Usage: @shopitem <vendor> restock <key> <amount>")
                return
            try:
                amount = int(tokens[1])
            except ValueError:
                caller.msg("Amount must be a number.")
                return
            ok, msg = restock_item(vendor, tokens[0], amount)
            caller.msg(msg)
            return

        if sub == "sale":
            tokens = rest.split()
            if len(tokens) < 3:
                caller.msg("Usage: @shopitem <vendor> sale <key> <sale_price> <hours>")
                return
            try:
                sale_price = int(tokens[1])
                hours = float(tokens[2])
            except ValueError:
                caller.msg("sale_price and hours must be numbers.")
                return
            ok, msg = set_sale(vendor, tokens[0], sale_price, hours)
            caller.msg(msg)
            return

        if sub == "add":
            if "=" not in rest:
                caller.msg("Usage: @shopitem <vendor> add <key> = <name> | <price> | <desc> ...")
                return
            key_part, fields_part = rest.split("=", 1)
            item_key = key_part.strip()
            fields = [f.strip() for f in fields_part.split("|")]

            if len(fields) < 2:
                caller.msg("Need at least: name | price")
                return

            try:
                price = int(fields[1].replace(",", ""))
            except ValueError:
                caller.msg("Price must be a number.")
                return

            item_dict = {
                "key":              item_key,
                "name":             fields[0],
                "price":            price,
                "desc":             fields[2] if len(fields) > 2 else "",
                "prototype":        fields[3] if len(fields) > 3 else None,
                "stock":            int(fields[4]) if len(fields) > 4 else STOCK_UNLIMITED,
                "faction_required": None,
                "rank_required":    0,
                "sale_price":       None,
                "sale_until":       None,
                "tags":             [],
            }
            ok, msg = add_shop_item(vendor, item_dict)
            caller.msg(msg)
            return

        caller.msg(f"Unknown sub-command '{sub}'. Use: add, remove, restock, sale, list, clear.")


# ---------------------------------------------------------------------------
# Staff: @spawnbank
# ---------------------------------------------------------------------------

class CmdSpawnBank(Command):
    """
    Spawn a bank terminal object in the current room.

    Usage:
      @spawnbank [name]

    Creates a bank terminal object. Players can use 'bank' in the same room.
    Also tags the room itself as a bank so 'bank' works even without the object.

    Example:
      @spawnbank ATM Unit 7
      @spawnbank
    """

    key = "@spawnbank"
    aliases = ["spawnbank"]
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        caller = self.caller
        name = (self.args or "").strip() or "Bank Terminal"
        room = caller.location

        from evennia import create_object
        from evennia.objects.objects import DefaultObject

        terminal = create_object(
            DefaultObject,
            key=name,
            location=room,
        )
        terminal.tags.add("bank_terminal", category="bank_terminal")
        terminal.db.desc = (
            "A sleek terminal interface connected to the Frame banking network. "
            "A small screen displays account options."
        )
        # Also tag the room so 'bank' works even if the terminal is moved/deleted.
        room.tags.add("bank", category="bank")
        caller.msg(
            f"Spawned bank terminal '{name}' (#{terminal.id}) in {room.key}.\n"
            f"Room '{room.key}' tagged as bank."
        )
        room.msg_contents(
            f"A bank terminal flickers to life.",
            exclude=[caller],
        )


class CmdTagBank(Command):
    """
    Tag or untag the current room as a bank location.

    Usage:
      @tagbank        -- tag this room as a bank
      @tagbank remove -- remove the bank tag from this room

    Players can use the 'bank' command in any room tagged as a bank,
    even without a physical terminal object present.
    """

    key = "@tagbank"
    aliases = ["tagbank"]
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        caller = self.caller
        room = caller.location
        if not room:
            caller.msg("You aren't in a room.")
            return

        args = (self.args or "").strip().lower()
        if args == "remove":
            room.tags.remove("bank", category="bank")
            room.tags.remove("bank")
            caller.msg(f"Removed bank tag from '{room.key}'.")
        else:
            room.tags.add("bank", category="bank")
            caller.msg(f"Tagged '{room.key}' as a bank location.")
