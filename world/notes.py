"""
PC Note system.

Storage:
  Notes are persisted in a Global Script (PCNoteStorage) to ensure
  high performance and clean database separation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# REMOVED ServerConfig. Added search_script and create_script
from evennia import search_script, create_script

STAFF_READ_ATTR = "pc_notes_read_ids_v1"
DEFAULT_CATEGORIES = ("IC", "OOC", "JOB", "PLOT", "PVP")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _get_storage_script():
    """
    Finds the global note storage script. If it doesn't exist yet,
    it creates it on the fly.
    """
    scripts = search_script("pc_note_storage")
    if scripts:
        return scripts[0]

    # If it wasn't found, spin it up
    return create_script("typeclasses.scripts.PCNoteStorage", key="pc_note_storage", persistent=True)


def _load_notes() -> List[Dict[str, Any]]:
    script = _get_storage_script()
    notes = script.db.notes
    if not notes:
        return []
    return list(notes)


def _save_notes(notes: List[Dict[str, Any]]) -> None:
    script = _get_storage_script()
    # Save a copy to the script's database
    script.db.notes = list(notes)


def _next_id() -> int:
    script = _get_storage_script()

    # Get the current ID, default to 1 if it's broken
    nxt_int = script.db.next_id or 1

    # Increment and save
    script.db.next_id = nxt_int + 1

    return nxt_int

def add_note(
    *,
    character,
    account,
    category: str,
    title: str,
    body: str,
) -> Dict[str, Any]:
    """
    Add a new note and persist it globally.
    """
    note_id = _next_id()
    cat = (category or "").strip().upper() or "UNCATEGORIZED"
    ttl = (title or "").strip() or "(untitled)"
    txt = (body or "").rstrip()

    note = {
        "id": note_id,
        "created_at": _utc_now_iso(),
        "category": cat,
        "title": ttl,
        "body": txt,
        "char_id": getattr(character, "id", None),
        "char_key": getattr(character, "key", None) or getattr(character, "name", None),
        "account_id": getattr(account, "id", None),
        "account_key": getattr(account, "key", None) or getattr(account, "username", None),
    }
    notes = _load_notes()
    notes.append(note)
    _save_notes(notes)
    return note


def notes_for_character(character, *, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    All notes for a given character, optionally filtered by category (case-insensitive).
    Most-recent first.
    """
    cid = getattr(character, "id", None)
    if not cid:
        return []
    notes = [n for n in _load_notes() if n.get("char_id") == cid]
    if category:
        wanted = category.strip().lower()
        notes = [n for n in notes if (n.get("category") or "").strip().lower() == wanted]
    # Sort by id descending (creation order)
    notes.sort(key=lambda n: int(n.get("id") or 0), reverse=True)
    return notes


def notes_for_character_name(char_name: str, *, account=None, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Helper for staff: find notes for a character by (case-insensitive) name.
    If account is given, restrict to notes where account_id matches.
    """
    if not char_name:
        return []
    name_low = char_name.strip().lower()
    acc_id = getattr(account, "id", None) if account else None
    notes = []
    for n in _load_notes():
        if not n.get("char_key"):
            continue
        if n.get("char_key", "").strip().lower() != name_low:
            continue
        if acc_id is not None and n.get("account_id") != acc_id:
            continue
        notes.append(n)
    if category:
        wanted = category.strip().lower()
        notes = [n for n in notes if (n.get("category") or "").strip().lower() == wanted]
    notes.sort(key=lambda n: int(n.get("id") or 0), reverse=True)
    return notes


def get_note_by_id(note_id: int) -> Optional[Dict[str, Any]]:
    try:
        nid = int(note_id)
    except Exception:
        return None
    for n in _load_notes():
        if int(n.get("id") or 0) == nid:
            return n
    return None


def staff_read_ids(account) -> set[int]:
    raw = getattr(getattr(account, "db", None), STAFF_READ_ATTR, None) or []
    try:
        ids = set(int(x) for x in raw)
    except Exception:
        ids = set()
    return ids


def staff_mark_read(account, note_id: int) -> None:
    if not getattr(account, "db", None):
        return
    ids = staff_read_ids(account)
    try:
        ids.add(int(note_id))
    except Exception:
        return
    # Force-save by reassigning a plain list.
    setattr(account.db, STAFF_READ_ATTR, sorted(ids))


def staff_unread_notes(account) -> List[Dict[str, Any]]:
    read = staff_read_ids(account)
    notes = _load_notes()
    # Only PC notes (anything with an account_id and character id).
    pc_notes = [n for n in notes if n.get("account_id") and n.get("char_id")]
    unread = [n for n in pc_notes if int(n.get("id") or 0) not in read]
    return unread
