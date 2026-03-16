"""
Staff pending approvals: a reusable foundation for player requests that require
staff approval (custom sdesc gender terms, future: name changes, etc.).

- Pending jobs are stored on a global Script (staff_pending).
- When a job is added, a message is sent to the staff_pending channel so staff see it.
- Staff use the @pending command to list, approve, or deny.
- Each job type has a resolver that applies the change (or not) and notifies the player.
"""

import uuid
from datetime import datetime

# Script key and channel alias used by this system
PENDING_SCRIPT_KEY = "staff_pending"
STAFF_PENDING_CHANNEL_ALIAS = "staff_pending"


def _get_script():
    """Return the staff_pending Script, or None if not created yet."""
    from evennia import search_script
    scripts = search_script(PENDING_SCRIPT_KEY)
    return scripts[0] if scripts else None


def _get_pending_list():
    """Return the list of pending job dicts; initializes to [] if missing."""
    script = _get_script()
    if not script:
        return []
    pending = getattr(script.db, "pending", None)
    if pending is None:
        script.db.pending = []
        return []
    return list(pending)


def _save_pending(pending_list):
    """Persist the pending list to the Script."""
    script = _get_script()
    if script:
        script.db.pending = pending_list


def _notify_staff_channel(job):
    """Send a notification to the staff pending channel so staff see new requests."""
    from evennia import create_channel, search_channel
    # Search by key or alias
    channels = search_channel(STAFF_PENDING_CHANNEL_ALIAS)
    if not channels:
        channel = create_channel(
            key=STAFF_PENDING_CHANNEL_ALIAS,
            aliases=["pending", "staffpending"],
            desc="Staff queue for pending approval requests (sdesc custom terms, etc.).",
            locks="listen:perm(Builder);send:perm(Builder);control:perm(Admin)",
        )
    else:
        channel = list(channels)[0] if hasattr(channels, "__iter__") else channels
    # Format a one-line summary
    summary = _format_job_summary(job)
    if summary:
        try:
            channel.msg(summary, senders=None)
        except Exception:
            pass


def _format_job_summary(job):
    """One-line human-readable summary for channel and list. Uses character name and short id."""
    job_type = job.get("type") or "unknown"
    full_id = job.get("id", "")
    short_id = full_id[:8] if len(full_id) >= 8 else full_id
    req_id = job.get("requester_id")
    requester_name = "#%s" % req_id if req_id else "?"
    if req_id is not None:
        from evennia import search_object
        objs = search_object("#%s" % req_id)
        if objs:
            try:
                obj = objs[0]
            except (TypeError, IndexError):
                obj = None
            if obj is not None:
                requester_name = obj.get_display_name(None) if hasattr(obj, "get_display_name") else getattr(obj, "key", str(obj))
    payload = job.get("payload") or {}
    if job_type == "sdesc_gender_term":
        term = payload.get("term", "?")
        return "[Pending %s] %s requested custom sdesc gender term: |w%s|n (|wsdesc custom|n). Use |w@pending approve %s|n or |w@pending deny %s|n." % (short_id, requester_name, term, short_id, short_id)
    return "[Pending %s] %s: type=%s (use |w@pending approve %s|n or |w@pending deny %s|n)." % (short_id, requester_name, job_type, short_id, short_id)


def add_pending(job_type, requester, payload, **meta):
    """
    Add a pending job. requester is the Character (or Object) requesting.

    Returns (job_id, True) on success, or (None, False) if storage unavailable.
    """
    script = _get_script()
    if not script:
        return None, False
    job_id = uuid.uuid4().hex
    requester_id = getattr(requester, "id", None) or getattr(requester, "dbref", None)
    job = {
        "id": job_id,
        "type": job_type,
        "requester_id": requester_id,
        "payload": dict(payload),
        "created": datetime.utcnow().isoformat() + "Z",
        "meta": dict(meta),
    }
    pending = _get_pending_list()
    pending.append(job)
    _save_pending(pending)
    _notify_staff_channel(job)
    return job_id, True


def get_pending(job_type=None):
    """Return list of pending job dicts, optionally filtered by job_type."""
    pending = _get_pending_list()
    if job_type:
        pending = [j for j in pending if j.get("type") == job_type]
    return pending


def get_by_id(job_id):
    """Return the job dict with the given id (full hex or short 8-char prefix), or None. If multiple match by prefix, returns first."""
    if not job_id:
        return None
    job_id = job_id.strip().lower()
    for j in _get_pending_list():
        jid = (j.get("id") or "")
        if jid == job_id or (len(job_id) <= 8 and jid.startswith(job_id)):
            return j
    return None


def resolve(job_id, approved, staff_member):
    """
    Resolve a pending job: approve or deny. Runs the type-specific handler,
    removes the job from the list, and returns (success, message).
    """
    job = get_by_id(job_id)
    if not job:
        return False, "No pending job with that id."
    handler = _RESOLVERS.get(job.get("type"))
    if not handler:
        return False, "Unknown job type: %s." % job.get("type")
    # Remove from list first so we don't double-process (use full id from job)
    full_id = job.get("id")
    pending = _get_pending_list()
    pending = [j for j in pending if j.get("id") != full_id]
    _save_pending(pending)
    return handler(job, approved, staff_member)


def _resolve_sdesc_gender_term(job, approved, staff_member):
    """On approve: set character's sdesc_gender_term and sdesc_gender_term_custom. Notify requester."""
    from evennia import search_object
    req_id = job.get("requester_id")
    payload = job.get("payload") or {}
    term = (payload.get("term") or "").strip().lower()
    objs = search_object("#%s" % req_id) if req_id else []
    try:
        character = objs[0] if objs else None
    except (TypeError, IndexError):
        character = None
    if approved:
        if not term:
            return False, "Payload missing 'term'."
        if not character:
            return False, "Requester character no longer found."
        character.db.sdesc_gender_term = term
        character.db.sdesc_gender_term_custom = True
        try:
            character.msg("|gStaff approved your custom sdesc gender term. You will now appear as \"%s\" (e.g. a rangy %s).|n" % (term, term))
        except Exception:
            pass
        return True, "Approved: %s now has custom sdesc term |w%s|n." % (character.get_display_name(staff_member), term)
    else:
        if character:
            try:
                character.msg("|yYour request for a custom sdesc gender term was declined by staff.|n")
            except Exception:
                pass
        return True, "Denied."


# Register type-specific resolvers (approve/deny logic and notifications)
_RESOLVERS = {
    "sdesc_gender_term": _resolve_sdesc_gender_term,
}


def register_resolver(job_type, handler):
    """
    Register a resolver for a job type. Handler signature: (job, approved, staff_member) -> (success, message).
    Use this for future approval types (e.g. name changes, custom titles).
    """
    _RESOLVERS[job_type] = handler
