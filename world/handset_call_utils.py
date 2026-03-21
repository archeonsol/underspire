"""
Shared helpers for handset call state (used by Handset typeclass and handset commands).

Call state lives on ndb; peer resolution is cached on ndb._call_peer_obj.
"""

from __future__ import annotations

from evennia.utils import delay

RING_TIMEOUT = 30.0
RING_ECHO_INTERVAL = 3.5
RINGTONE_MAX_LEN = 20


def ringtone_suffix(handset) -> str:
    """
    Return ', <text>' for custom ringtone, or '' for default.
    Stored on handset.db.ringtone (None or empty = default).
    """
    raw = getattr(getattr(handset, "db", None), "ringtone", None)
    if raw is None:
        return ""
    s = str(raw).strip().replace("\r", " ").replace("\n", " ")
    if len(s) > RINGTONE_MAX_LEN:
        s = s[:RINGTONE_MAX_LEN].rstrip()
    if not s:
        return ""
    return f", {s}"


def get_call_peer(handset):
    """
    Resolve the peer handset for an active call, caching on ndb.
    """
    peer_dbref = getattr(handset.ndb, "call_peer", None)
    if not peer_dbref:
        return None
    cached = getattr(handset.ndb, "_call_peer_obj", None)
    try:
        if cached is not None and int(getattr(cached, "id", -1)) == int(peer_dbref):
            return cached
    except Exception:
        pass
    try:
        from evennia import search_object

        results = search_object(f"#{int(peer_dbref)}")
        obj = results[0] if results else None
        handset.ndb._call_peer_obj = obj
        return obj
    except Exception:
        return None


def clear_call(handset):
    """Reset call ndb fields and peer cache."""
    try:
        handset.ndb.call_state = "idle"
        handset.ndb.call_peer = None
        handset.ndb._call_peer_obj = None
        handset.ndb.call_session_id = None
        handset.ndb.call_outbound = None
    except Exception:
        pass


def _bump_call_session_id(handset):
    cur = getattr(handset.ndb, "call_session_seq", 0) or 0
    try:
        cur = int(cur)
    except Exception:
        cur = 0
    nxt = cur + 1
    handset.ndb.call_session_seq = nxt
    return nxt


def schedule_call_ring_timers(dialer, target):
    """
    Assign a shared session id and schedule ring timeout + repeating ring echo on target.
    Initial ring sound should already have been sent by the caller.
    """
    sid = _bump_call_session_id(dialer)
    try:
        dialer.ndb.call_session_id = sid
        target.ndb.call_session_id = sid
    except Exception:
        return
    delay(RING_TIMEOUT, ring_timeout_callback, dialer.id, target.id, sid)
    delay(RING_ECHO_INTERVAL, ring_echo_callback, target.id, sid)


def ring_echo_callback(handset_id, session_id):
    from evennia import search_object

    try:
        results = search_object(f"#{int(handset_id)}")
        h = results[0] if results else None
    except Exception:
        h = None
    if not h:
        return
    try:
        if getattr(h.ndb, "call_session_id", None) != session_id:
            return
    except Exception:
        return
    state = str(getattr(h.ndb, "call_state", "idle") or "idle")
    if state != "ringing":
        return
    holder = h.get_authenticated_user() if hasattr(h, "get_authenticated_user") else None
    if holder:
        suf = ringtone_suffix(h)
        holder.msg(f"|yYour handset is still ringing{suf}.|n")
        room = getattr(holder, "location", None)
        if room:
            hname = holder.get_display_name(holder) if hasattr(holder, "get_display_name") else holder.key
            try:
                room.msg_contents(f"|y{hname}'s handset is still ringing{suf}.|n", exclude=holder)
            except Exception:
                pass
    delay(RING_ECHO_INTERVAL, ring_echo_callback, handset_id, session_id)


def ring_timeout_callback(dialer_id, target_id, session_id):
    from evennia import search_object

    try:
        dr = search_object(f"#{int(dialer_id)}")
        tr = search_object(f"#{int(target_id)}")
        dialer = dr[0] if dr else None
        target = tr[0] if tr else None
    except Exception:
        dialer = target = None
    if not dialer or not target:
        return
    try:
        if getattr(dialer.ndb, "call_session_id", None) != session_id:
            return
        if getattr(target.ndb, "call_session_id", None) != session_id:
            return
    except Exception:
        return
    ds = str(getattr(dialer.ndb, "call_state", "idle") or "idle")
    ts = str(getattr(target.ndb, "call_state", "idle") or "idle")
    if ds != "dialing" or ts != "ringing":
        return
    try:
        if int(getattr(dialer.ndb, "call_peer", 0) or 0) != target.id:
            return
        if int(getattr(target.ndb, "call_peer", 0) or 0) != dialer.id:
            return
    except Exception:
        return

    clear_call(dialer)
    clear_call(target)

    def _mid(h):
        try:
            return h.get_matrix_id() if hasattr(h, "get_matrix_id") else None
        except Exception:
            return None

    d_mid = _mid(dialer) or ""
    t_mid = _mid(target) or ""

    if hasattr(dialer, "log_call_event"):
        try:
            dialer.log_call_event(t_mid, "out", "missed")
        except Exception:
            pass
    if hasattr(target, "log_call_event"):
        try:
            target.log_call_event(d_mid, "in", "missed")
        except Exception:
            pass

    d_holder = dialer.get_authenticated_user() if hasattr(dialer, "get_authenticated_user") else None
    t_holder = target.get_authenticated_user() if hasattr(target, "get_authenticated_user") else None
    if d_holder:
        d_holder.msg("|yNo answer.|n")
    if t_holder:
        t_holder.msg("|yYou missed a call.|n")
