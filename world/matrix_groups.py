"""
Decentralized handset group chats: per-handset db.group_chats + unified db.texts entries.

No central server; group id links copies across handsets. Member lists drift is corrected
via member_sync / admin_sync on system messages.
"""

from __future__ import annotations

import random
import string
import time
from datetime import datetime
from collections.abc import Mapping

MAX_GROUPS_PER_HANDSET = 8
MAX_GROUP_MEMBERS = 20
GROUP_NAME_MIN_LEN = 2
GROUP_NAME_MAX_LEN = 30
GROUP_ID_LEN = 6
_ID_ALPHABET = string.ascii_uppercase + string.digits


def _ts_display() -> str:
    return datetime.now().strftime("%b %d %H:%M")


def normalize_matrix_id(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    return s if s.startswith("^") else f"^{s}"


def generate_group_id(handset) -> str:
    """Generate a unique 6-char alphanumeric group id for this handset's existing keys."""
    existing = getattr(getattr(handset, "db", None), "group_chats", None) or {}
    if not isinstance(existing, dict):
        existing = {}
    for _ in range(200):
        gid = "".join(random.choices(_ID_ALPHABET, k=GROUP_ID_LEN))
        if gid not in existing:
            return gid
    return "".join(random.choices(_ID_ALPHABET, k=GROUP_ID_LEN))


def validate_group_name(name: str) -> tuple[bool, str]:
    n = (name or "").strip()
    if len(n) < GROUP_NAME_MIN_LEN or len(n) > GROUP_NAME_MAX_LEN:
        return False, f"Group name must be {GROUP_NAME_MIN_LEN}-{GROUP_NAME_MAX_LEN} characters."
    if not n.isprintable():
        return False, "Group name contains invalid characters."
    return True, n


def _groups(handset) -> dict:
    g = getattr(getattr(handset, "db", None), "group_chats", None)
    if isinstance(g, Mapping):
        try:
            return dict(g)
        except Exception:
            return {}
    return {}


def _save_groups(handset, data: dict) -> None:
    handset.db.group_chats = dict(data)


def create_group(handset, name: str) -> tuple[bool, str, str | None]:
    """Create a group on this handset. Returns (success, message, group_id)."""
    ok, n = validate_group_name(name)
    if not ok:
        return False, f"|r{n}|n", None
    chats = _groups(handset)
    if len(chats) >= MAX_GROUPS_PER_HANDSET:
        return False, "|rYou can only be in 8 group chats on one handset.|n", None
    try:
        self_id = handset.get_matrix_id() if hasattr(handset, "get_matrix_id") else None
    except Exception:
        self_id = None
    self_id = normalize_matrix_id(self_id or "")
    if not self_id:
        return False, "|rNo Matrix ID on this handset.|n", None
    gid = generate_group_id(handset)
    now = time.time()
    entry = {
        "name": n,
        "members": [self_id],
        "admins": [self_id],
        "creator": self_id,
        "joined_at": now,
        "muted": False,
        "role": "admin",
        "pending_invites": [],
        "last_read_t": 0.0,
    }
    chats[gid] = entry
    _save_groups(handset, chats)
    return True, f"|gStarted group|n |w{n}|n |x({gid})|n.", gid


def add_member_to_group(handset, group_id: str, matrix_id: str, role: str | None = None) -> None:
    mid = normalize_matrix_id(matrix_id)
    if not mid:
        return
    chats = dict(_groups(handset))
    g = chats.get(group_id)
    if not isinstance(g, dict):
        return
    members = list(g.get("members") or [])
    if mid not in members:
        members.append(mid)
    g["members"] = members
    if role:
        g["role"] = role
    chats[group_id] = g
    _save_groups(handset, chats)


def remove_member_from_group(handset, group_id: str, matrix_id: str) -> None:
    mid = normalize_matrix_id(matrix_id)
    chats = dict(_groups(handset))
    g = chats.get(group_id)
    if not isinstance(g, dict):
        return
    members = [m for m in (g.get("members") or []) if normalize_matrix_id(str(m)) != mid]
    admins = [a for a in (g.get("admins") or []) if normalize_matrix_id(str(a)) != mid]
    g["members"] = members
    g["admins"] = admins
    chats[group_id] = g
    _save_groups(handset, chats)


def remove_group_entry(handset, group_id: str) -> None:
    chats = dict(_groups(handset))
    if group_id in chats:
        del chats[group_id]
        _save_groups(handset, chats)


def resolve_group_by_name(handset, name: str) -> tuple[str | None, dict | None, str | None]:
    """
    Case-insensitive substring match on local group names.
    Returns (group_id, group_data, error_message). error_message set if none or ambiguous.
    """
    key = (name or "").strip().lower()
    if not key:
        return None, None, "No group name given."
    matches = []
    for gid, data in _groups(handset).items():
        if not isinstance(data, dict):
            continue
        gname = str(data.get("name", "") or "").lower()
        if key in gname or gname.startswith(key):
            matches.append((gid, data))
    if len(matches) == 0:
        return None, None, "No group matches that name."
    if len(matches) > 1:
        names = ", ".join(str(m[1].get("name", m[0])) for m in matches[:5])
        return None, None, f"Several groups match. Be more specific: {names}"
    return matches[0][0], matches[0][1], None


def resolve_group_by_id(handset, group_id: str) -> tuple[str | None, dict | None, str | None]:
    gid = (group_id or "").strip().upper()
    data = _groups(handset).get(gid)
    if not isinstance(data, dict):
        return None, None, "You are not in that group."
    return gid, data, None


def get_group_messages(handset, group_id: str, limit: int = 30) -> list[dict]:
    out = []
    try:
        msgs = handset.get_text_messages() if hasattr(handset, "get_text_messages") else list(getattr(handset.db, "texts", []) or [])
    except Exception:
        msgs = []
    for entry in msgs:
        if not isinstance(entry, dict):
            continue
        if entry.get("group") != group_id:
            continue
        out.append(entry)
    return out[-limit:]


def get_unread_group_count(handset, group_id: str) -> int:
    g = _groups(handset).get(group_id)
    if not isinstance(g, dict):
        return 0
    try:
        last = float(g.get("last_read_t") or 0)
    except Exception:
        last = 0.0
    n = 0
    for entry in get_group_messages(handset, group_id, limit=500):
        if not isinstance(entry, dict):
            continue
        if entry.get("group_invite"):
            continue
        try:
            t = float(entry.get("t", 0))
        except Exception:
            continue
        if t > last:
            n += 1
    return n


def get_pending_invites(handset) -> list[dict]:
    """Invite rows from texts buffer (24h cleanup applies)."""
    try:
        msgs = handset.get_text_messages() if hasattr(handset, "get_text_messages") else list(getattr(handset.db, "texts", []) or [])
    except Exception:
        msgs = []
    seen = set()
    out = []
    for entry in reversed(msgs):
        if not isinstance(entry, dict):
            continue
        gid = entry.get("group_invite")
        if not gid:
            continue
        gid = str(gid).strip().upper()
        if gid in seen:
            continue
        seen.add(gid)
        out.append(entry)
    return out


def lookup_handset(matrix_id: str):
    try:
        from world.matrix_ids import lookup_matrix_id
    except Exception:
        return None
    mid = normalize_matrix_id(matrix_id)
    obj = lookup_matrix_id(mid)
    if not obj:
        return None
    if getattr(getattr(obj, "db", None), "device_type", None) != "handset":
        return None
    return obj


def apply_sync_from_entry(handset, entry: dict) -> None:
    """Apply member_sync/admin_sync from a system row to local group_chats."""
    if not entry.get("system"):
        return
    gid = entry.get("group")
    if not gid:
        return
    members = entry.get("member_sync")
    admins = entry.get("admin_sync")
    if members is None:
        return
    chats = dict(_groups(handset))
    g = chats.get(gid)
    if not isinstance(g, dict):
        return
    g["members"] = [normalize_matrix_id(str(m)) for m in members if m]
    if admins is not None:
        g["admins"] = [normalize_matrix_id(str(a)) for a in admins if a]
    sid = _self_id(handset)
    if sid and admins is not None:
        g["role"] = "admin" if sid in g["admins"] else "member"
    chats[gid] = g
    _save_groups(handset, chats)


def append_texts_entry(handset, entry: dict) -> bool:
    """Append to texts if handset exposes append_texts_entry (preferred)."""
    if hasattr(handset, "append_texts_entry"):
        return bool(handset.append_texts_entry(entry))
    raw = list(getattr(handset.db, "texts", []) or [])
    raw.append(entry)
    handset.db.texts = raw
    return True


def deliver_texts_entry(handset, entry: dict, line_for_holder: str | None) -> None:
    """
    Store entry, apply group sync side effects, optionally beep + show line (respect mute for group).
    """
    gid = entry.get("group") or entry.get("group_invite")
    muted = False
    if gid:
        g = _groups(handset).get(str(gid).strip().upper())
        if isinstance(g, dict) and g.get("muted"):
            muted = True
    append_texts_entry(handset, dict(entry))
    apply_sync_from_entry(handset, entry)
    if not line_for_holder:
        return
    holder = handset.get_authenticated_user() if hasattr(handset, "get_authenticated_user") else None
    if not holder:
        return
    if muted and (entry.get("group") or entry.get("group_invite")):
        return
    holder.msg("Your handset beeps.")
    holder.msg(line_for_holder)


def format_inbox_line(handset, entry: dict) -> str:
    """Format one texts row for unified inbox / menus."""
    ts = entry.get("ts", "")
    if entry.get("group_invite"):
        gid = str(entry.get("group_invite", "")).strip().upper()
        name = entry.get("group_invite_name", "a group")
        members = entry.get("group_invite_members") or []
        sender = entry.get("from", "")
        disp = handset.display_alias_or_id(sender) if hasattr(handset, "display_alias_or_id") else sender
        cnt = len(members) if isinstance(members, list) else 0
        return (
            f"[{ts}]|c{disp}|n invited you to |w'{name}'|n ({cnt} members). "
            f"|whs group accept {gid}|n |xor|n |whs group decline {gid}|n."
        )
    gid = entry.get("group")
    if gid:
        g = _groups(handset).get(str(gid).strip().upper())
        gname = (g or {}).get("name", gid) if isinstance(g, dict) else gid
        msg = entry.get("msg", "")
        if entry.get("system"):
            return f"[{ts}]|x[{gname}]|n {msg}"
        frm = entry.get("from", "")
        display = handset.display_alias_or_id(frm) if hasattr(handset, "display_alias_or_id") else frm
        kind = (entry.get("kind") or "").strip().lower()
        tag = " [voicemail]" if kind == "voicemail" else ""
        return f"[{ts}]{tag}|c[{gname}]|n {display}: {msg}"
    frm = entry.get("from", "")
    msg = entry.get("msg", "")
    display = handset.display_alias_or_id(frm) if hasattr(handset, "display_alias_or_id") else frm
    kind = (entry.get("kind") or "").strip().lower()
    tag = " [voicemail]" if kind == "voicemail" else ""
    return f"[{ts}]{tag}{display}: {msg}"


def _self_id(handset) -> str:
    try:
        return normalize_matrix_id(handset.get_matrix_id() if hasattr(handset, "get_matrix_id") else "")
    except Exception:
        return ""


def prune_dead_member_from_sender(sender_handset, group_id: str, dead_mid: str) -> None:
    remove_member_from_group(sender_handset, group_id, dead_mid)


def send_group_message(sender_handset, group_id: str, message: str) -> tuple[int, int]:
    """
    Deliver a group chat line to all members. Returns (delivered_count, member_count).
    Plain message stored in entry['msg'].
    """
    msg = (message or "").strip()
    if not msg:
        return 0, 0
    chats = _groups(sender_handset)
    g = chats.get(group_id)
    if not isinstance(g, dict):
        return 0, 0
    members = [normalize_matrix_id(str(m)) for m in (g.get("members") or [])]
    sender = _self_id(sender_handset)
    if sender not in members:
        return 0, 0
    # Drop dead Matrix IDs from sender's copy before delivering.
    for mid in list(members):
        if mid != sender and not lookup_handset(mid):
            prune_dead_member_from_sender(sender_handset, group_id, mid)
    g = _groups(sender_handset).get(group_id) or {}
    members = [normalize_matrix_id(str(m)) for m in (g.get("members") or [])]
    ts = _ts_display()
    now = time.time()
    total = len(members)
    delivered = 0
    gname = str(g.get("name", group_id))

    for mid in members:
        entry = {"t": now, "ts": ts, "from": sender, "msg": msg, "group": group_id}
        if mid == sender:
            line = f"|c[{gname}]|n You: {msg}"
            deliver_texts_entry(sender_handset, entry, line)
            delivered += 1
            continue
        target = lookup_handset(mid)
        if not target or not target.has_network_coverage():
            continue
        disp = target.display_alias_or_id(sender) if hasattr(target, "display_alias_or_id") else sender
        line = f"|c[{gname}]|n {disp}: {msg}"
        deliver_texts_entry(target, entry, line)
        delivered += 1
    return delivered, total


def notify_group_members(
    sender_handset,
    group_id: str,
    system_message: str,
    members: list[str],
    admins: list[str],
    exclude_delivery_to: set[str] | None = None,
    group_display_name: str | None = None,
) -> None:
    """Send a system row with member_sync/admin_sync to listed members (reachable + signal)."""
    exclude_delivery_to = exclude_delivery_to or set()
    members_norm = []
    seen_m = set()
    for m in members:
        n = normalize_matrix_id(str(m))
        if n and n not in seen_m:
            seen_m.add(n)
            members_norm.append(n)
    admins_norm = []
    seen_a = set()
    for a in admins:
        n = normalize_matrix_id(str(a))
        if n and n not in seen_a:
            seen_a.add(n)
            admins_norm.append(n)
    if group_display_name is not None:
        gname = group_display_name
    else:
        g = _groups(sender_handset).get(group_id) or {}
        gname = str(g.get("name", group_id)) if isinstance(g, dict) else group_id
    ts = _ts_display()
    now = time.time()
    entry = {
        "t": now,
        "ts": ts,
        "from": "^SYSTEM",
        "msg": system_message,
        "group": group_id,
        "system": True,
        "member_sync": members_norm,
        "admin_sync": admins_norm,
    }
    line = f"|x[{gname}]|n {system_message}"
    for mid in members_norm:
        if mid in exclude_delivery_to:
            continue
        h = lookup_handset(mid)
        if not h:
            continue
        if not h.has_network_coverage():
            continue
        deliver_texts_entry(h, entry, line)


def invite_to_group(sender_handset, group_resolved_id: str, target_matrix_id: str) -> tuple[bool, str]:
    """Build invite entry and deliver to target. Updates pending_invites on sender."""
    target_matrix_id = normalize_matrix_id(target_matrix_id)
    self_id = _self_id(sender_handset)
    if not target_matrix_id or not self_id:
        return False, "|rInvalid invite target.|n"
    chats = dict(_groups(sender_handset))
    g = chats.get(group_resolved_id)
    if not isinstance(g, dict):
        return False, "|rNo such group.|n"
    members = [normalize_matrix_id(str(m)) for m in (g.get("members") or [])]
    admins = [normalize_matrix_id(str(a)) for a in (g.get("admins") or [])]
    if self_id not in members:
        return False, "|rYou are not in that group.|n"
    if target_matrix_id in members:
        return False, "|rThey're already in that group.|n"
    if len(members) >= MAX_GROUP_MEMBERS:
        return False, "|rThat group is full.|n"
    pending = list(g.get("pending_invites") or [])
    if target_matrix_id not in pending:
        pending.append(target_matrix_id)
    g["pending_invites"] = pending
    chats[group_resolved_id] = g
    _save_groups(sender_handset, chats)

    target = lookup_handset(target_matrix_id)
    if not target or not target.has_network_coverage():
        return True, "|yInvite queued on your end; their handset had no signal.|n"

    ts = _ts_display()
    now = time.time()
    entry = {
        "t": now,
        "ts": ts,
        "from": self_id,
        "msg": "",
        "group_invite": str(group_resolved_id).strip().upper(),
        "group_invite_name": str(g.get("name", "")),
        "group_invite_members": list(members),
        "group_invite_admins": list(admins),
    }
    disp = target.display_alias_or_id(self_id) if hasattr(target, "display_alias_or_id") else self_id
    name = str(g.get("name", ""))
    cnt = len(members)
    line = (
        f"|c{disp}|n invited you to group chat |w'{name}'|n ({cnt} members). "
        f"Use |whs group accept {group_resolved_id}|n or |whs group decline {group_resolved_id}|n."
    )
    deliver_texts_entry(target, entry, line)
    return True, "|gInvite sent.|n"


def remove_invite_entries(handset, group_id: str) -> None:
    gid = str(group_id).strip().upper()
    try:
        msgs = list(handset.get_text_messages() if hasattr(handset, "get_text_messages") else getattr(handset.db, "texts", []) or [])
    except Exception:
        return
    kept = [e for e in msgs if not (isinstance(e, dict) and str(e.get("group_invite", "")).strip().upper() == gid)]
    if len(kept) != len(msgs):
        handset.db.texts = kept


def accept_group_invite(handset, group_id: str) -> tuple[bool, str]:
    gid = str(group_id).strip().upper()
    try:
        msgs = handset.get_text_messages() if hasattr(handset, "get_text_messages") else list(getattr(handset.db, "texts", []) or [])
    except Exception:
        msgs = []
    invite = None
    for e in reversed(msgs):
        if isinstance(e, dict) and str(e.get("group_invite", "")).strip().upper() == gid:
            invite = e
            break
    if not invite:
        return False, "|rNo pending invite for that group.|n"
    if len(_groups(handset)) >= MAX_GROUPS_PER_HANDSET:
        return False, "|rYour handset is already in 8 groups.|n"

    self_id = _self_id(handset)
    members = [normalize_matrix_id(str(m)) for m in (invite.get("group_invite_members") or [])]
    admins = [normalize_matrix_id(str(a)) for a in (invite.get("group_invite_admins") or [])]
    if self_id not in members:
        members.append(self_id)
    if len(members) > MAX_GROUP_MEMBERS:
        return False, "|rThat group is full.|n"
    name = str(invite.get("group_invite_name", "Group"))
    ok, name_clean = validate_group_name(name)
    if not ok:
        name_clean = (name or "Group")[:GROUP_NAME_MAX_LEN].strip() or "Group"
        if len(name_clean) < GROUP_NAME_MIN_LEN:
            name_clean = "Group"
    cr = normalize_matrix_id(str(invite.get("from", "")))
    role = "admin" if self_id in admins else "member"
    chats = dict(_groups(handset))
    chats[gid] = {
        "name": name_clean,
        "members": list(members),
        "admins": list(admins),
        "creator": cr,
        "joined_at": time.time(),
        "muted": False,
        "role": role,
        "pending_invites": [],
        "last_read_t": 0.0,
    }
    _save_groups(handset, chats)
    inviter_mid = normalize_matrix_id(str(invite.get("from", "")))
    remove_invite_entries(handset, gid)

    ih = lookup_handset(inviter_mid)
    if ih:
        ichats = dict(_groups(ih))
        ig = ichats.get(gid)
        if isinstance(ig, dict):
            pend = [
                p
                for p in (ig.get("pending_invites") or [])
                if normalize_matrix_id(str(p)) != self_id
            ]
            ig["pending_invites"] = pend
            ichats[gid] = ig
            _save_groups(ih, ichats)

    holder = handset.get_authenticated_user() if hasattr(handset, "get_authenticated_user") else None
    label = "Someone"
    if holder and hasattr(holder, "key"):
        label = holder.key
    try:
        if holder and hasattr(holder, "get_display_name"):
            label = (holder.get_display_name(holder) or label).strip() or label
    except Exception:
        pass
    sys_msg = f"{label} joined the group."
    notify_group_members(handset, gid, sys_msg, members, admins, exclude_delivery_to=set())
    return True, f"|gYou joined|n |w{name_clean}|n."


def decline_group_invite(handset, group_id: str) -> tuple[bool, str]:
    gid = str(group_id).strip().upper()
    try:
        msgs = handset.get_text_messages() if hasattr(handset, "get_text_messages") else list(getattr(handset.db, "texts", []) or [])
    except Exception:
        msgs = []
    inviter = None
    gname = "the group"
    for e in reversed(msgs):
        if isinstance(e, dict) and str(e.get("group_invite", "")).strip().upper() == gid:
            inviter = normalize_matrix_id(str(e.get("from", "")))
            gname = str(e.get("group_invite_name", gname))
            break
    remove_invite_entries(handset, gid)
    if inviter:
        ih = lookup_handset(inviter)
        if ih and ih.has_network_coverage():
            _beep_decline_notice(ih, handset, gname)
    return True, "|yInvite declined.|n"


def _beep_decline_notice(inviter_handset, declining_handset, group_name: str) -> None:
    holder = inviter_handset.get_authenticated_user() if hasattr(inviter_handset, "get_authenticated_user") else None
    if holder:
        holder.msg("Your handset beeps.")
        holder.msg(f"|yYour invite to|n |w'{group_name}'|n |ywas declined.|n")


def leave_group(handset, group_id: str) -> tuple[bool, str]:
    self_id = _self_id(handset)
    chats = _groups(handset)
    g = chats.get(group_id)
    if not isinstance(g, dict):
        return False, "|rYou are not in that group.|n"
    members = [normalize_matrix_id(str(m)) for m in (g.get("members") or [])]
    admins = [normalize_matrix_id(str(a)) for a in (g.get("admins") or [])]
    if self_id not in members:
        return False, "|rYou are not in that group.|n"

    new_members = [m for m in members if m != self_id]
    new_admins = [a for a in admins if a != self_id]
    # Sole admin left: promote first remaining member by join order (list order).
    if not new_admins and new_members:
        new_admins = [new_members[0]]

    gname = str(g.get("name", group_id))
    remove_group_entry(handset, group_id)

    holder = handset.get_authenticated_user() if hasattr(handset, "get_authenticated_user") else None
    label = holder.key if holder and hasattr(holder, "key") else "Someone"
    if holder and hasattr(holder, "get_display_name"):
        try:
            label = (holder.get_display_name(holder) or label).strip() or label
        except Exception:
            pass
    if new_members:
        notify_group_members(
            handset,
            group_id,
            f"{label} left the group.",
            new_members,
            new_admins,
            group_display_name=gname,
        )
    return True, "|yYou left the group.|n"


def kick_member(admin_handset, group_id: str, target_mid: str) -> tuple[bool, str]:
    target_mid = normalize_matrix_id(target_mid)
    self_id = _self_id(admin_handset)
    g = _groups(admin_handset).get(group_id)
    if not isinstance(g, dict):
        return False, "|rNo such group.|n"
    admins = [normalize_matrix_id(str(a)) for a in (g.get("admins") or [])]
    if self_id not in admins:
        return False, "|rOnly an admin can remove someone.|n"
    members = [normalize_matrix_id(str(m)) for m in (g.get("members") or [])]
    if target_mid not in members:
        return False, "|rThey're not in that group.|n"
    if target_mid == self_id:
        return False, "|rYou can't kick yourself. Use leave.|n"

    new_members = [m for m in members if m != target_mid]
    new_admins = [a for a in admins if a != target_mid]
    gname = str(g.get("name", group_id))

    victim = lookup_handset(target_mid)
    if victim:
        remove_group_entry(victim, group_id)
        if victim.has_network_coverage():
            holder = victim.get_authenticated_user() if hasattr(victim, "get_authenticated_user") else None
            if holder:
                holder.msg("Your handset beeps.")
                holder.msg(f"|rYou were removed from|n |w'{gname}'|n.")

    chats_ad = dict(_groups(admin_handset))
    g_ad = chats_ad.get(group_id)
    if isinstance(g_ad, dict):
        g_ad["members"] = list(new_members)
        g_ad["admins"] = list(new_admins)
        chats_ad[group_id] = g_ad
        _save_groups(admin_handset, chats_ad)
    notify_group_members(
        admin_handset,
        group_id,
        f"{admin_handset.display_alias_or_id(target_mid) if hasattr(admin_handset, 'display_alias_or_id') else target_mid} was removed from the group.",
        new_members,
        new_admins,
    )
    return True, "|gRemoved from the group.|n"


def promote_member(admin_handset, group_id: str, target_mid: str) -> tuple[bool, str]:
    target_mid = normalize_matrix_id(target_mid)
    self_id = _self_id(admin_handset)
    g = _groups(admin_handset).get(group_id)
    if not isinstance(g, dict):
        return False, "|rNo such group.|n"
    admins = [normalize_matrix_id(str(a)) for a in (g.get("admins") or [])]
    if self_id not in admins:
        return False, "|rOnly an admin can promote someone.|n"
    members = [normalize_matrix_id(str(m)) for m in (g.get("members") or [])]
    if target_mid not in members:
        return False, "|rThey're not in that group.|n"
    if target_mid in admins:
        return False, "|rThey're already an admin.|n"
    new_admins = admins + [target_mid]
    gname = str(g.get("name", group_id))
    disp = admin_handset.display_alias_or_id(target_mid) if hasattr(admin_handset, "display_alias_or_id") else target_mid
    chats = dict(_groups(admin_handset))
    gc = chats.get(group_id)
    if isinstance(gc, dict):
        gc["admins"] = list(new_admins)
        chats[group_id] = gc
        _save_groups(admin_handset, chats)
    notify_group_members(
        admin_handset,
        group_id,
        f"{disp} is now an admin.",
        members,
        new_admins,
    )
    return True, f"|gPromoted|n {disp}."


def rename_group_local(handset, group_id: str, new_name: str) -> tuple[bool, str]:
    ok, n = validate_group_name(new_name)
    if not ok:
        return False, f"|r{n}|n"
    chats = dict(_groups(handset))
    g = chats.get(group_id)
    if not isinstance(g, dict):
        return False, "|rNo such group.|n"
    g["name"] = n
    chats[group_id] = g
    _save_groups(handset, chats)
    return True, f"|gRenamed locally to|n |w{n}|n."


def set_group_muted(handset, group_id: str, muted: bool) -> tuple[bool, str]:
    chats = dict(_groups(handset))
    g = chats.get(group_id)
    if not isinstance(g, dict):
        return False, "|rNo such group.|n"
    g["muted"] = bool(muted)
    chats[group_id] = g
    _save_groups(handset, chats)
    return True, "|yNotifications muted for that group.|n" if muted else "|gNotifications on for that group.|n"


def mark_group_read(handset, group_id: str) -> None:
    chats = dict(_groups(handset))
    g = chats.get(group_id)
    if not isinstance(g, dict):
        return
    g["last_read_t"] = time.time()
    chats[group_id] = g
    _save_groups(handset, chats)


def sync_member_removal(*_args, **_kwargs) -> None:
    """Member lists sync via notify_group_members (member_sync). Placeholder for API compatibility."""
    pass
