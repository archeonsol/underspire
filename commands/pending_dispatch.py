"""
Universal pending-input dispatcher.

Any system that uses ndb._pending_* for multi-step flows registers a handler
here. All entry points that need to route raw player input — CmdNoMatch and
any command that uses "yes"/"no" as a keyword (e.g. CmdWireConfirm) — call
dispatch_pending_input() instead of importing individual handlers.

To add a new system: append a (label, import_path, function_name) tuple to
_HANDLERS. Order matters: earlier entries take priority.
"""

from __future__ import annotations

# Each entry: (human label for tracing, module path, function name)
# The function must have signature: handler(caller, raw: str) -> bool
_HANDLERS: list[tuple[str, str, str]] = [
    ("rentable_door",  "commands.rentable_door_cmds", "handle_pending_input"),
    ("food",           "commands.food_cmds",           "handle_pending_food_input"),
    ("cosmetic",       "commands.cosmetic_cmds",        "handle_pending_cosmetic_input"),
    ("wire",           "commands.pending_dispatch",     "_handle_pending_wire"),
]


def _handle_pending_wire(caller, raw: str) -> bool:
    """Pending-input handler for the wire transfer confirmation flow."""
    pending = getattr(caller.ndb, "_pending_wire", None)
    if not pending:
        return False

    # Wire confirmation only triggers on an explicit "yes"; anything else cancels.
    if raw.strip().lower() != "yes":
        try:
            del caller.ndb._pending_wire
        except Exception:
            pass
        caller.msg("|xWire transfer cancelled.|n")
        return True

    try:
        del caller.ndb._pending_wire
    except Exception:
        pass

    network_id = pending["network_id"]
    amount = pending["amount"]

    try:
        from world.utils import get_containing_room, room_has_network_coverage
        room = get_containing_room(caller)
        if not room_has_network_coverage(room, include_matrix_nodes=True):
            caller.msg("|rSignal lost. Wire transfer cancelled.|n")
            return True

        from world.rpg.bank import bank_wire, _resolve_wire_recipient
        from world.rpg.economy import format_currency, get_bank_balance
        from commands.economy_cmds import (
            _pheader, _pkv, _pline, _psection, _pclose,
            _OK, _N, _ACCENT, _LABEL, _ERR,
        )

        ok, msg, recip_name, fee = bank_wire(caller, network_id, amount)

        if ok:
            lines = [
                _pheader("TRANSFER COMPLETE", subtitle="Funds dispatched via Matrix routing."),
                _pkv("Sent",      f"{_OK}{format_currency(amount, color=False)}{_N}"),
                _pkv("Fee",       format_currency(fee)),
                _pkv("Recipient", f"{_ACCENT}{recip_name}{_N}"),
                _pline(),
                _psection("ACCOUNT"),
                _pkv("Bank Bal",  format_currency(get_bank_balance(caller))),
                _pline(),
                _pclose(),
            ]
            caller.msg("\n".join(lines))

            recipient = _resolve_wire_recipient(network_id)
            if recipient and hasattr(recipient, "msg"):
                from world.matrix_accounts import get_alias
                sender_alias = get_alias(caller)
                sender_display = f"@{sender_alias}" if sender_alias else caller.key
                recipient.msg(
                    f"\n{_ACCENT}[WIRE TRANSFER]{_N} You received {format_currency(amount)} "
                    f"from {_LABEL}{sender_display}{_N}."
                )
        else:
            caller.msg(f"{_ERR}{msg}{_N}")

    except Exception:
        caller.msg("|rWire transfer failed due to an internal error.|n")

    return True


def dispatch_pending_input(caller, raw: str) -> bool:
    """
    Try each registered pending-input handler in order.

    Returns True if any handler consumed the input, False otherwise.
    Each handler is called inside its own try/except so a broken module
    never silently swallows input or crashes the caller.
    """
    for _label, module_path, fn_name in _HANDLERS:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            handler = getattr(mod, fn_name)
            if handler(caller, raw):
                return True
        except Exception:
            pass
    return False
