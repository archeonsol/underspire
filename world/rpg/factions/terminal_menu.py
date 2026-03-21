"""
EvMenu for faction registry terminals. IC terminal aesthetic; staff bypass.
"""

import time
from datetime import datetime

from evennia.utils.search import search_object

from world.rpg.factions import get_faction, is_faction_member
from world.rpg.factions.membership import (
    enlist,
    discharge,
    promote,
    demote,
    set_rank,
    get_member_rank,
    get_member_permission,
    get_faction_roster,
)
from world.rpg.factions.ranks import get_rank_name, get_max_rank, get_rank_pay
from world.rpg.factions.pay import can_collect_pay, collect_pay

_W = 52
_N = "|n"
_DIM = "|x"
_LABEL = "|w"

ROSTER_PAGE_SIZE = 30


def _faction_line(fdata, char="="):
    c = fdata.get("color", "|w") if fdata else "|w"
    return f"{c}{char * _W}{_N}"


def _line(fdata=None):
    c = (fdata or {}).get("color", "|x") if fdata else "|x"
    return f"{c}{'-' * _W}{_N}"


def _is_staff(caller):
    try:
        acc = getattr(caller, "account", None)
        if acc and (acc.permissions.check("Builder") or acc.permissions.check("Admin")):
            return True
    except Exception:
        pass
    return False


def _terminal_fdata(terminal):
    key = getattr(getattr(terminal, "db", None), "faction_key", None)
    return get_faction(key) if key else None


def _caller_online_status(character):
    if not character:
        return "offline"
    try:
        if character.sessions.count():
            return "ONLINE"
    except Exception:
        pass
    return "offline"


def _format_joined_ago(character, faction_key):
    joined = (character.db.faction_joined or {}).get(faction_key)
    if not joined:
        return "—"
    delta = time.time() - joined
    days = int(delta / 86400)
    if days < 1:
        return "<1d"
    return f"{days}d"


def _pay_status_line(caller, fdata):
    can, reason, amount = can_collect_pay(caller, fdata["key"])
    if can:
        return f"{amount}/week (available)"
    if "Next pay" in reason or "h" in reason:
        return f"{get_rank_pay(fdata['ranks'], get_member_rank(caller, fdata['key']))}/week ({reason})"
    return f"{get_rank_pay(fdata['ranks'], get_member_rank(caller, fdata['key']))}/week ({reason})"


def _get_terminal(caller, kwargs):
    t = kwargs.get("terminal")
    if not t:
        t = getattr(getattr(caller, "ndb", None), "_evmenu", None)
        if t:
            t = getattr(t, "terminal", None)
    return t


def start_faction_terminal(caller, terminal):
    """Open the registry EvMenu for this terminal."""
    from evennia.utils.evmenu import EvMenu

    try:
        caller.ndb._faction_terminal = terminal
    except Exception:
        pass
    EvMenu(
        caller,
        "world.rpg.factions.terminal_menu",
        startnode="node_terminal_main",
        terminal=terminal,
        persistent=False,
    )


def node_terminal_main(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal") or _get_terminal(caller, kwargs)
    fdata = _terminal_fdata(terminal)
    if not fdata:
        caller.msg(f"{_DIM}Terminal offline.{_N}")
        return None, None

    staff = _is_staff(caller)
    member = is_faction_member(caller, fdata["key"]) or staff
    allow_public = bool(getattr(getattr(terminal, "db", None), "allow_public_info", False))

    if not member and not staff:
        text = (
            f"{_faction_line(fdata)}\n"
            f"  {fdata['color']}{fdata['name'].upper()} — REGISTRY{_N}\n"
            f"{_faction_line(fdata)}\n\n"
        )
        if allow_public:
            text += f"  {_DIM}{fdata['description']}{_N}\n\n"
            text += f"  {_DIM}Public information only. Not a member.{_N}\n"
        else:
            text += "  |rACCESS DENIED.|n\n"
            text += f"  {_DIM}You are not a member of {fdata['name']}.{_N}\n"
        text += f"\n{_line(fdata)}\n"
        text += "  q — Disconnect\n"
        options = [{"key": "q", "desc": "Disconnect", "goto": "node_terminal_exit"}]
        return text, options

    perm = get_member_permission(caller, fdata["key"])
    rank = get_member_rank(caller, fdata["key"])
    rname = get_rank_name(fdata["ranks"], rank) if rank else "—"

    text = (
        f"{_faction_line(fdata)}\n"
        f"  {fdata['color']}{fdata['name'].upper()} — REGISTRY TERMINAL{_N}\n"
        f"{_faction_line(fdata)}\n\n"
        f"  {_LABEL}Name:{_N}    {caller.key}\n"
        f"  {_LABEL}Rank:{_N}    {rname} ({rank})\n"
        f"  {_LABEL}Joined:{_N}  {_format_joined_ago(caller, fdata['key'])}\n"
        f"  {_LABEL}Pay:{_N}     {_pay_status_line(caller, fdata)}\n\n"
        f"{_line(fdata)}\n"
    )

    options = []
    n = 1

    def add_opt(desc, node, **extra):
        nonlocal n
        opts = {"key": str(n), "desc": desc, "goto": (node, {"terminal": terminal, **extra})}
        options.append(opts)
        n += 1

    add_opt("Collect pay", "node_collect_pay")
    if perm >= 1 or staff:
        add_opt("View roster", "node_view_roster", roster_page=0)
    add_opt("View own record", "node_own_record")

    if perm >= 2 or staff:
        add_opt("Enlist new member", "node_enlist")
    if perm >= 2 or staff:
        add_opt("Promote member", "node_promote_pick")
    if perm >= 2 or staff:
        add_opt("Demote member", "node_demote_pick")
    if perm >= 2 or staff:
        add_opt("Discharge member", "node_discharge_pick")
    if perm >= 3 or staff:
        add_opt("Set rank (leader)", "node_setrank_pick")

    text += "  " + "\n  ".join([f"{i}. {o['desc']}" for i, o in enumerate(options, start=1)])
    text += f"\n\n  q — Disconnect\n"

    options.append({"key": "q", "desc": "Disconnect", "goto": "node_terminal_exit"})

    # numeric keys 1..n map to options - EvMenu uses key from options
    return text, options


def node_terminal_exit(caller, raw_string, **kwargs):
    caller.msg(f"{_DIM}Session closed.{_N}")
    return None, None


def node_collect_pay(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal") or _get_terminal(caller, kwargs)
    fdata = _terminal_fdata(terminal)
    if not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)

    ok, msg, amt = collect_pay(caller, fdata["key"])
    if ok:
        caller.msg(f"|g{msg}|n")
    else:
        caller.msg(f"|r{msg}|n")
    return node_terminal_main(caller, raw_string, terminal=terminal)


def node_view_roster(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal") or _get_terminal(caller, kwargs)
    fdata = _terminal_fdata(terminal)
    page = int(kwargs.get("roster_page", 0) or 0)
    if not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)

    perm = get_member_permission(caller, fdata["key"])
    if perm < 1 and not _is_staff(caller):
        caller.msg("|rAccess denied. Insufficient clearance.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    roster = get_faction_roster(fdata["key"])
    total = len(roster)
    start = page * ROSTER_PAGE_SIZE
    chunk = roster[start : start + ROSTER_PAGE_SIZE]
    online_n = sum(1 for c, _ in roster if _caller_online_status(c) == "ONLINE")

    lines = [
        f"{_faction_line(fdata, '-')}",
        f"  ROSTER — {fdata['name'].upper()}",
        f"{_faction_line(fdata, '-')}",
    ]
    for char, rnk in chunk:
        rname = get_rank_name(fdata["ranks"], rnk)
        joined = _format_joined_ago(char, fdata["key"])
        on = _caller_online_status(char)
        lines.append(
            f"  {str(char.key)[:22].ljust(22)} [{rnk}] {rname[:16].ljust(16)} {joined:>5}  {on}"
        )
    lines.append(f"{_faction_line(fdata, '-')}")
    lines.append(f"  {total} member(s). {online_n} online. (page {page + 1})")

    text = "\n".join(lines) + "\n"
    options = [{"key": "q", "desc": "Back", "goto": (node_terminal_main, {"terminal": terminal})}]
    if start > 0:
        options.insert(
            0,
            {
                "key": "p",
                "desc": "Previous page",
                "goto": (
                    node_view_roster,
                    {"terminal": terminal, "roster_page": page - 1},
                ),
            },
        )
    if start + ROSTER_PAGE_SIZE < total:
        options.insert(
            0,
            {
                "key": "n",
                "desc": "Next page",
                "goto": (
                    node_view_roster,
                    {"terminal": terminal, "roster_page": page + 1},
                ),
            },
        )
    return text, options


def node_own_record(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal") or _get_terminal(caller, kwargs)
    fdata = _terminal_fdata(terminal)
    if not fdata or not is_faction_member(caller, fdata["key"]):
        caller.msg("|rNo record for this faction.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    rank = get_member_rank(caller, fdata["key"])
    rname = get_rank_name(fdata["ranks"], rank)
    joined = _format_joined_ago(caller, fdata["key"])
    last_pay = (caller.db.faction_pay_collected or {}).get(fdata["key"])
    pay_s = "Never"
    if last_pay:
        pay_s = datetime.utcfromtimestamp(last_pay).strftime("%Y-%m-%d %H:%M UTC")

    log = caller.db.faction_log or []
    log_lines = [e for e in log if e.get("faction") == fdata["key"]][-10:]

    lines = [
        f"{_faction_line(fdata)}",
        f"  RECORD — {fdata['short_name'].upper()}",
        f"{_faction_line(fdata)}",
        f"  Rank: {rname} ({rank})",
        f"  Joined: {joined}",
        f"  Last pay recorded: {pay_s}",
        "",
        "  Recent log:",
    ]
    for entry in log_lines:
        details = entry.get("details", "")
        ev = entry.get("event", "")
        lines.append(f"  — {ev}: {details[:60]}")

    text = "\n".join(lines) + f"\n\n{_line(fdata)}\n  q — Back\n"
    options = [{"key": "q", "desc": "Back", "goto": (node_terminal_main, {"terminal": terminal})}]
    return text, options


def _resolve_target_name(caller, name, terminal, remote_ok):
    """Resolve a character by key/name in room, or dbref if remote_ok (staff)."""
    name = (name or "").strip()
    if not name:
        return None
    if name.startswith("#"):
        if not remote_ok:
            return None
        o = search_object(name)
        return o[0] if o else None
    room = caller.location
    if not room:
        return None
    results = caller.search(name, location=room, quiet=True)
    if not results:
        return None
    return results[0] if isinstance(results, (list, tuple)) else results


def node_enlist(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal") or _get_terminal(caller, kwargs)
    fdata = _terminal_fdata(terminal)
    if not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)

    perm = get_member_permission(caller, fdata["key"])
    if perm < 2 and not _is_staff(caller):
        caller.msg("|rAccess denied. Insufficient clearance.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    wait_key = "_faction_enlist_line"
    if getattr(caller.ndb, wait_key, None) != 1:
        setattr(caller.ndb, wait_key, 1)
        text = "Enter name of character to enlist (or |wq|n to cancel):\n"
        options = [{"key": "q", "desc": "Cancel", "goto": ("node_enlist_cancel", {"terminal": terminal})}]
        return text, options

    try:
        delattr(caller.ndb, wait_key)
    except Exception:
        pass

    line = (raw_string or "").strip()
    if line.lower() in ("q", "quit", "cancel"):
        return node_terminal_main(caller, "", terminal=terminal)

    target = _resolve_target_name(caller, line, terminal, remote_ok=_is_staff(caller))
    if not target:
        caller.msg("No match. Enter a name of someone present, or #dbref (staff).")
        setattr(caller.ndb, wait_key, 1)
        text = "Enter name of character to enlist (or |wq|n to cancel):\n"
        options = [{"key": "q", "desc": "Cancel", "goto": ("node_enlist_cancel", {"terminal": terminal})}]
        return text, options

    if not hasattr(target, "tags"):
        caller.msg("Invalid target.")
        return node_terminal_main(caller, "", terminal=terminal)

    return node_enlist_confirm(
        caller,
        "",
        terminal=terminal,
        enlist_target=target,
    )


def node_enlist_cancel(caller, raw_string, **kwargs):
    try:
        delattr(caller.ndb, "_faction_enlist_line")
    except Exception:
        pass
    return node_terminal_main(caller, raw_string, **kwargs)


def node_enlist_confirm(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal")
    target = kwargs.get("enlist_target")
    fdata = _terminal_fdata(terminal)

    if raw_string and raw_string.strip().lower() in ("y", "yes", "1"):
        if not target or not fdata:
            return node_terminal_main(caller, raw_string, terminal=terminal)
        staff = _is_staff(caller)
        if not staff:
            if not caller.location or target.location != caller.location:
                caller.msg("Target must be present at this terminal.")
                return node_terminal_main(caller, raw_string, terminal=terminal)
        ok, msg = enlist(target, fdata["key"], enlisted_by=caller.key)
        caller.msg(msg if ok else f"|r{msg}|n")
        if target != caller:
            target.msg(f"|yYou have been enlisted in {fdata['name']}.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if raw_string and raw_string.strip().lower() in ("n", "no", "2", "q"):
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if not target or not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)

    tname = target.key
    text = (
        f"Enlist |w{tname}|n at default rank in {fdata['name']}?\n"
        f"  y — Confirm\n  n — Cancel\n"
    )
    options = [
        {"key": ("y", "yes", "1"), "desc": "Confirm", "goto": (node_enlist_confirm, kwargs)},
        {"key": ("n", "no", "2"), "desc": "Cancel", "goto": (node_terminal_main, {"terminal": terminal})},
    ]
    return text, options


def _can_promote_to(caller, fdata, target, new_rank):
    """Return (ok, err_msg)."""
    staff = _is_staff(caller)
    if staff:
        return True, None
    op_rank = get_member_rank(caller, fdata["key"])
    perm = get_member_permission(caller, fdata["key"])
    if perm >= 3:
        return True, None
    if perm < 2:
        return False, "Insufficient clearance."
    if new_rank >= op_rank:
        return False, "You cannot promote anyone to your rank or above."
    return True, None


def _can_affect_rank(caller, fdata, target_rank, discharge=False):
    """Whether caller may change/discharge someone at target_rank."""
    staff = _is_staff(caller)
    if staff:
        return True, None
    op_rank = get_member_rank(caller, fdata["key"])
    perm = get_member_permission(caller, fdata["key"])
    if perm >= 3:
        return True, None
    if perm < 2:
        return False, "Insufficient clearance."
    if target_rank >= op_rank:
        return False, "Target's rank is not below yours."
    return True, None


def node_promote_pick(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal") or _get_terminal(caller, kwargs)
    fdata = _terminal_fdata(terminal)
    if not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)
    perm = get_member_permission(caller, fdata["key"])
    if perm < 2 and not _is_staff(caller):
        caller.msg("|rAccess denied.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    wait_key = "_faction_promote_line"
    if getattr(caller.ndb, wait_key, None) != 1:
        setattr(caller.ndb, wait_key, 1)
        text = "Name of member to promote (or |wq|n to cancel):\n"
        options = [{"key": "q", "desc": "Back", "goto": ("node_promote_cancel", {"terminal": terminal})}]
        return text, options

    try:
        delattr(caller.ndb, wait_key)
    except Exception:
        pass

    line = (raw_string or "").strip()
    if line.lower() in ("q", "quit", "cancel"):
        return node_terminal_main(caller, "", terminal=terminal)

    target = _resolve_target_name(caller, line, terminal, remote_ok=_is_staff(caller))
    if not target:
        caller.msg("No match.")
        setattr(caller.ndb, wait_key, 1)
        text = "Name of member to promote (or |wq|n to cancel):\n"
        options = [{"key": "q", "desc": "Back", "goto": ("node_promote_cancel", {"terminal": terminal})}]
        return text, options

    if target == caller:
        caller.msg("You cannot promote yourself.")
        return node_terminal_main(caller, "", terminal=terminal)

    if not is_faction_member(target, fdata["key"]):
        caller.msg("They are not a member of this faction.")
        return node_terminal_main(caller, "", terminal=terminal)

    cur = get_member_rank(target, fdata["key"])
    max_r = get_max_rank(fdata["ranks"])
    if cur >= max_r:
        caller.msg("They are already at maximum rank.")
        return node_terminal_main(caller, "", terminal=terminal)

    new_rank = cur + 1
    ok, err = _can_promote_to(caller, fdata, target, new_rank)
    if not ok:
        caller.msg(f"|r{err}|n")
        return node_terminal_main(caller, "", terminal=terminal)

    return node_promote_confirm(
        caller,
        "",
        terminal=terminal,
        promote_target=target,
        new_rank=new_rank,
    )


def node_promote_cancel(caller, raw_string, **kwargs):
    try:
        delattr(caller.ndb, "_faction_promote_line")
    except Exception:
        pass
    return node_terminal_main(caller, raw_string, **kwargs)


def node_promote_confirm(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal")
    target = kwargs.get("promote_target")
    new_rank = kwargs.get("new_rank")
    fdata = _terminal_fdata(terminal)

    if raw_string and raw_string.strip().lower() in ("y", "yes", "1"):
        if not target or not fdata:
            return node_terminal_main(caller, raw_string, terminal=terminal)
        ok, msg = promote(target, fdata["key"], promoted_by=caller.key)
        caller.msg(msg if ok else f"|r{msg}|n")
        if ok and target != caller:
            target.msg(f"|yYour rank in {fdata['name']} has changed.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if raw_string and raw_string.strip().lower() in ("n", "no", "2", "q"):
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if not target or not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)

    cur = get_member_rank(target, fdata["key"])
    text = (
        f"Promote |w{target.key}|n from rank {cur} to {new_rank}?\n"
        f"  y / n\n"
    )
    options = [
        {"key": ("y", "yes"), "desc": "Confirm", "goto": (node_promote_confirm, kwargs)},
        {"key": ("n", "no", "q"), "desc": "Cancel", "goto": (node_terminal_main, {"terminal": terminal})},
    ]
    return text, options


def node_demote_pick(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal") or _get_terminal(caller, kwargs)
    fdata = _terminal_fdata(terminal)
    if not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)
    perm = get_member_permission(caller, fdata["key"])
    if perm < 2 and not _is_staff(caller):
        caller.msg("|rAccess denied.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    wait_key = "_faction_demote_line"
    if getattr(caller.ndb, wait_key, None) != 1:
        setattr(caller.ndb, wait_key, 1)
        text = "Name of member to demote (or |wq|n to cancel):\n"
        options = [{"key": "q", "desc": "Back", "goto": ("node_demote_cancel", {"terminal": terminal})}]
        return text, options

    try:
        delattr(caller.ndb, wait_key)
    except Exception:
        pass

    line = (raw_string or "").strip()
    if line.lower() in ("q", "quit", "cancel"):
        return node_terminal_main(caller, "", terminal=terminal)

    target = _resolve_target_name(caller, line, terminal, remote_ok=_is_staff(caller))
    if not target:
        caller.msg("No match.")
        setattr(caller.ndb, wait_key, 1)
        text = "Name of member to demote (or |wq|n to cancel):\n"
        options = [{"key": "q", "desc": "Back", "goto": ("node_demote_cancel", {"terminal": terminal})}]
        return text, options

    if target == caller:
        caller.msg("You cannot demote yourself.")
        return node_terminal_main(caller, "", terminal=terminal)

    if not is_faction_member(target, fdata["key"]):
        caller.msg("They are not a member.")
        return node_terminal_main(caller, "", terminal=terminal)

    tr = get_member_rank(target, fdata["key"])
    ok, err = _can_affect_rank(caller, fdata, tr)
    if not ok:
        caller.msg(f"|r{err}|n")
        return node_terminal_main(caller, "", terminal=terminal)

    return node_demote_confirm(caller, "", terminal=terminal, demote_target=target)


def node_demote_cancel(caller, raw_string, **kwargs):
    try:
        delattr(caller.ndb, "_faction_demote_line")
    except Exception:
        pass
    return node_terminal_main(caller, raw_string, **kwargs)


def node_demote_confirm(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal")
    target = kwargs.get("demote_target")
    fdata = _terminal_fdata(terminal)

    if raw_string and raw_string.strip().lower() in ("y", "yes", "1"):
        if not target or not fdata:
            return node_terminal_main(caller, raw_string, terminal=terminal)
        ok, msg = demote(target, fdata["key"], demoted_by=caller.key)
        caller.msg(msg if ok else f"|r{msg}|n")
        if ok and target != caller:
            target.msg(f"|yYour rank in {fdata['name']} has changed.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if raw_string and raw_string.strip().lower() in ("n", "no", "2", "q"):
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if not target or not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)

    cur = get_member_rank(target, fdata["key"])
    text = f"Demote |w{target.key}|n from rank {cur} by one step?\n  y / n\n"
    options = [
        {"key": ("y", "yes"), "desc": "Confirm", "goto": (node_demote_confirm, kwargs)},
        {"key": ("n", "no", "q"), "desc": "Cancel", "goto": (node_terminal_main, {"terminal": terminal})},
    ]
    return text, options


def node_discharge_pick(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal") or _get_terminal(caller, kwargs)
    fdata = _terminal_fdata(terminal)
    if not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)
    perm = get_member_permission(caller, fdata["key"])
    if perm < 2 and not _is_staff(caller):
        caller.msg("|rAccess denied.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    wait_key = "_faction_discharge_line"
    if getattr(caller.ndb, wait_key, None) != 1:
        setattr(caller.ndb, wait_key, 1)
        text = "Name of member to discharge (or |wq|n to cancel):\n"
        options = [{"key": "q", "desc": "Back", "goto": ("node_discharge_cancel", {"terminal": terminal})}]
        return text, options

    try:
        delattr(caller.ndb, wait_key)
    except Exception:
        pass

    line = (raw_string or "").strip()
    if line.lower() in ("q", "quit", "cancel"):
        return node_terminal_main(caller, "", terminal=terminal)

    target = _resolve_target_name(caller, line, terminal, remote_ok=_is_staff(caller))
    if not target:
        caller.msg("No match.")
        setattr(caller.ndb, wait_key, 1)
        text = "Name of member to discharge (or |wq|n to cancel):\n"
        options = [{"key": "q", "desc": "Back", "goto": ("node_discharge_cancel", {"terminal": terminal})}]
        return text, options

    if target == caller:
        caller.msg("You cannot discharge yourself from this terminal.")
        return node_terminal_main(caller, "", terminal=terminal)

    if not is_faction_member(target, fdata["key"]):
        caller.msg("They are not a member.")
        return node_terminal_main(caller, "", terminal=terminal)

    tr = get_member_rank(target, fdata["key"])
    ok, err = _can_affect_rank(caller, fdata, tr, discharge=True)
    if not ok:
        caller.msg(f"|r{err}|n")
        return node_terminal_main(caller, "", terminal=terminal)

    return node_discharge_confirm(caller, "", terminal=terminal, discharge_target=target)


def node_discharge_cancel(caller, raw_string, **kwargs):
    try:
        delattr(caller.ndb, "_faction_discharge_line")
    except Exception:
        pass
    return node_terminal_main(caller, raw_string, **kwargs)


def node_discharge_confirm(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal")
    target = kwargs.get("discharge_target")
    fdata = _terminal_fdata(terminal)

    if raw_string and raw_string.strip().lower() in ("y", "yes", "1"):
        if not target or not fdata:
            return node_terminal_main(caller, raw_string, terminal=terminal)
        ok, msg = discharge(target, fdata["key"], discharged_by=caller.key, reason="discharged")
        caller.msg(msg if ok else f"|r{msg}|n")
        if ok and target != caller:
            target.msg(f"|rYou have been discharged from {fdata['name']}.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if raw_string and raw_string.strip().lower() in ("n", "no", "2", "q"):
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if not target or not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)

    text = (
        f"Discharge |w{target.key}|n from {fdata['name']}? They lose rank and clearance.\n"
        f"  y / n\n"
    )
    options = [
        {"key": ("y", "yes"), "desc": "Confirm", "goto": (node_discharge_confirm, kwargs)},
        {"key": ("n", "no", "q"), "desc": "Cancel", "goto": (node_terminal_main, {"terminal": terminal})},
    ]
    return text, options


def node_setrank_pick(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal") or _get_terminal(caller, kwargs)
    fdata = _terminal_fdata(terminal)
    if not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)
    perm = get_member_permission(caller, fdata["key"])
    if perm < 3 and not _is_staff(caller):
        caller.msg("|rAccess denied. Leader clearance required.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    tgt = getattr(caller.ndb, "_faction_setrank_target", None)
    if tgt is None:
        wait_key = "_faction_setrank_name_line"
        if getattr(caller.ndb, wait_key, None) != 1:
            setattr(caller.ndb, wait_key, 1)
            text = "Name of member (or |wq|n to cancel):\n"
            options = [{"key": "q", "desc": "Back", "goto": ("node_setrank_cancel", {"terminal": terminal})}]
            return text, options
        try:
            delattr(caller.ndb, wait_key)
        except Exception:
            pass
        line = (raw_string or "").strip()
        if line.lower() in ("q", "quit", "cancel"):
            return node_terminal_main(caller, "", terminal=terminal)
        target = _resolve_target_name(caller, line, terminal, remote_ok=_is_staff(caller))
        if not target:
            caller.msg("No match.")
            setattr(caller.ndb, wait_key, 1)
            text = "Name of member (or |wq|n to cancel):\n"
            options = [{"key": "q", "desc": "Back", "goto": ("node_setrank_cancel", {"terminal": terminal})}]
            return text, options
        if not is_faction_member(target, fdata["key"]):
            caller.msg("Not a member.")
            return node_terminal_main(caller, "", terminal=terminal)
        caller.ndb._faction_setrank_target = target
        setattr(caller.ndb, "_faction_setrank_rank_line", 1)
        text = "Enter new rank number (or |wq|n to cancel):\n"
        options = [{"key": "q", "desc": "Back", "goto": ("node_setrank_cancel", {"terminal": terminal})}]
        return text, options

    wait_rank = "_faction_setrank_rank_line"
    if getattr(caller.ndb, wait_rank, None) == 1:
        try:
            delattr(caller.ndb, wait_rank)
        except Exception:
            pass
        line = (raw_string or "").strip()
        if line.lower() in ("q", "quit", "cancel"):
            try:
                delattr(caller.ndb, "_faction_setrank_target")
            except Exception:
                pass
            return node_terminal_main(caller, "", terminal=terminal)
        try:
            new_r = int(line)
        except ValueError:
            caller.msg("Enter a number.")
            setattr(caller.ndb, wait_rank, 1)
            text = "Enter new rank number (or |wq|n to cancel):\n"
            options = [{"key": "q", "desc": "Back", "goto": ("node_setrank_cancel", {"terminal": terminal})}]
            return text, options
        target = tgt
        try:
            delattr(caller.ndb, "_faction_setrank_target")
        except Exception:
            pass
        return node_setrank_confirm(
            caller,
            "",
            terminal=terminal,
            setrank_target=target,
            setrank_new=new_r,
        )

    return node_terminal_main(caller, raw_string, terminal=terminal)


def node_setrank_cancel(caller, raw_string, **kwargs):
    for attr in (
        "_faction_setrank_name_line",
        "_faction_setrank_rank_line",
        "_faction_setrank_target",
    ):
        try:
            delattr(caller.ndb, attr)
        except Exception:
            pass
    return node_terminal_main(caller, raw_string, **kwargs)


def node_setrank_confirm(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal")
    target = kwargs.get("setrank_target")
    new_r = kwargs.get("setrank_new")
    fdata = _terminal_fdata(terminal)

    if raw_string and raw_string.strip().lower() in ("y", "yes", "1"):
        if not target or not fdata:
            return node_terminal_main(caller, raw_string, terminal=terminal)
        ok, msg = set_rank(target, fdata["key"], new_r, set_by=caller.key)
        caller.msg(msg if ok else f"|r{msg}|n")
        if ok and target != caller:
            target.msg(f"|yYour rank in {fdata['name']} has been set.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if raw_string and raw_string.strip().lower() in ("n", "no", "2", "q"):
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if not target or not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)

    cur = get_member_rank(target, fdata["key"])
    text = f"Set |w{target.key}|n from rank {cur} to {new_r}? y/n\n"
    options = [
        {"key": ("y", "yes"), "desc": "Confirm", "goto": (node_setrank_confirm, kwargs)},
        {"key": ("n", "no", "q"), "desc": "Cancel", "goto": (node_terminal_main, {"terminal": terminal})},
    ]
    return text, options
