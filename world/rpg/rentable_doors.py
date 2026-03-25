"""
Rentable door system for apartment buildings.

Door attributes stored on the exit object (ex.db.*):
  rentable            bool  -- True marks this as a rentable door
  rent_cost           int   -- weekly cost in script (set by staff)
  rent_tenant_id      int   -- db-id of the renting character, or None
  rent_tenant_name    str   -- display name snapshot
  rent_expires        float -- unix timestamp when rent expires (None if vacant)
  rent_master_code    str   -- 7-digit string set by tenant on first rent
  rent_secondary_codes list[str] -- additional codes (cannot program door)

Door state uses the existing door system:
  door                bool  -- always True for rentable doors
  door_open           bool  -- current open/closed state
  door_locked         bool  -- True when closed (auto-locked)
  door_name           str   -- display name ("door", "apartment door", etc.)
  door_pair           int   -- paired exit id (for two-sided sync)

Weekly tick: 7 * 86400 = 604800 seconds.
"""

from __future__ import annotations

import time

RENT_WEEK_SECONDS = 7 * 24 * 60 * 60  # 604800

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_rentable(exit_obj) -> bool:
    return bool(getattr(getattr(exit_obj, "db", None), "rentable", None))


def is_rented(exit_obj) -> bool:
    if not is_rentable(exit_obj):
        return False
    tenant_id = getattr(exit_obj.db, "rent_tenant_id", None)
    expires = getattr(exit_obj.db, "rent_expires", None)
    if not tenant_id or not expires:
        return False
    return True


def is_expired(exit_obj) -> bool:
    """True if rented but past expiry timestamp."""
    if not is_rented(exit_obj):
        return False
    expires = getattr(exit_obj.db, "rent_expires", None)
    return expires is not None and time.time() > expires


def is_tenant(character, exit_obj) -> bool:
    tid = getattr(exit_obj.db, "rent_tenant_id", None)
    return tid is not None and tid == getattr(character, "id", None)


def time_remaining(exit_obj) -> float:
    """Seconds until expiry (may be negative if expired)."""
    expires = getattr(exit_obj.db, "rent_expires", None)
    if expires is None:
        return 0.0
    return expires - time.time()


def format_time_remaining(exit_obj) -> str:
    secs = time_remaining(exit_obj)
    if secs <= 0:
        return "|rEXPIRED|n"
    days = int(secs // 86400)
    hours = int((secs % 86400) // 3600)
    mins = int((secs % 3600) // 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if not days:
        parts.append(f"{mins}m")
    return " ".join(parts) or "< 1m"


# ---------------------------------------------------------------------------
# Code validation
# ---------------------------------------------------------------------------


def is_valid_code(code: str) -> bool:
    """Must be exactly 7 digits."""
    return bool(code) and code.isdigit() and len(code) == 7


def check_code(exit_obj, code: str) -> bool:
    """Return True if code matches master or any secondary code."""
    master = getattr(exit_obj.db, "rent_master_code", None)
    if master and code == master:
        return True
    secondaries = list(getattr(exit_obj.db, "rent_secondary_codes", None) or [])
    return code in secondaries


def is_master_code(exit_obj, code: str) -> bool:
    master = getattr(exit_obj.db, "rent_master_code", None)
    return bool(master and code == master)


# ---------------------------------------------------------------------------
# Rent / Renewal
# ---------------------------------------------------------------------------


def do_rent(character, exit_obj) -> tuple[bool, str]:
    """
    First-time rent of a vacant exit. Does NOT deduct money — caller handles that.
    Returns (ok, message).
    """
    from world.rpg.factions.doors import sync_door_pair

    if not is_rentable(exit_obj):
        return False, "That door is not rentable."
    if is_rented(exit_obj) and not is_expired(exit_obj):
        tenant_name = getattr(exit_obj.db, "rent_tenant_name", "someone")
        return False, f"That door is already rented by {tenant_name}."

    exit_obj.db.rent_tenant_id = character.id
    exit_obj.db.rent_tenant_name = character.key
    exit_obj.db.rent_expires = time.time() + RENT_WEEK_SECONDS
    exit_obj.db.rent_secondary_codes = []
    # Door starts locked
    exit_obj.db.door_open = False
    exit_obj.db.door_locked = True
    sync_door_pair(exit_obj, False)
    # Sync kitchenette ownership to new tenant
    try:
        from world.food.stations import sync_kitchenette_ownership
        sync_kitchenette_ownership(character, exit_obj)
    except Exception:
        pass
    return True, "ok"


def do_pay_rent(character, exit_obj) -> tuple[bool, str]:
    """
    Pay rent (extend by one week). Does NOT deduct money — caller handles that.
    Can be called by anyone (not just the tenant).
    """
    if not is_rentable(exit_obj):
        return False, "That door is not rentable."
    if not is_rented(exit_obj):
        return False, "That door isn't currently rented."

    current_expires = getattr(exit_obj.db, "rent_expires", time.time())
    base = max(current_expires, time.time())
    exit_obj.db.rent_expires = base + RENT_WEEK_SECONDS
    return True, "ok"


def do_vacate(exit_obj):
    """Clear rental data (called by staff or expiry eviction)."""
    from world.rpg.factions.doors import sync_door_pair

    exit_obj.db.rent_tenant_id = None
    exit_obj.db.rent_tenant_name = None
    exit_obj.db.rent_expires = None
    exit_obj.db.rent_master_code = None
    exit_obj.db.rent_secondary_codes = []
    exit_obj.db.door_open = False
    exit_obj.db.door_locked = True
    sync_door_pair(exit_obj, False)
    # Clear kitchenette ownership when tenant vacates
    try:
        from world.food.stations import clear_kitchenette_ownership
        clear_kitchenette_ownership(exit_obj)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Open / Close integration
# ---------------------------------------------------------------------------


def rentable_can_open(character, exit_obj) -> tuple[bool, str]:
    """
    Check whether character may open this rentable door without a code prompt.
    Returns (allowed: bool, reason: str).
    - True  → open immediately (staff bypass)
    - False → deny with reason
    - None  → ask for code (caller handles prompt)
    """
    from world.rpg.factions.doors import staff_bypass

    if staff_bypass(character):
        return True, ""

    if not is_rented(exit_obj):
        return False, "The door is vacant and locked."

    if is_expired(exit_obj):
        return False, "The rental has expired. The door remains locked."

    return None, "needs_code"


def rentable_auto_lock_on_close(exit_obj):
    """
    Lock the door when it closes.
    Called for:
      - The rentable (outside) exit directly.
      - Any plain paired exit whose pair is rentable (inside exit closing).
    Locks both sides so neither can be pushed open without a code.
    """
    exit_obj.db.door_locked = True
    pair = _resolve_door_pair(exit_obj)
    if pair and getattr(pair.db, "door", None):
        pair.db.door_locked = True


def is_paired_with_rentable(exit_obj) -> bool:
    """True if this (non-rentable) exit's pair is a rentable door."""
    if is_rentable(exit_obj):
        return False
    pair = _resolve_door_pair(exit_obj)
    return pair is not None and is_rentable(pair)


def _resolve_door_pair(exit_obj):
    from evennia.utils.search import search_object

    ref = getattr(getattr(exit_obj, "db", None), "door_pair", None)
    if ref is None:
        return None
    if isinstance(ref, int):
        rid = ref
    else:
        s = str(ref).strip().lstrip("#")
        try:
            rid = int(s)
        except ValueError:
            return None
    res = search_object(f"#{rid}")
    return res[0] if res else None


# ---------------------------------------------------------------------------
# Code-entry flow helpers (stored on ndb)
# ---------------------------------------------------------------------------


def start_code_prompt(character, exit_obj, purpose: str):
    """
    Store pending code-entry context on the character's ndb.
    purpose: "open" | "menu"
    """
    character.ndb._rentdoor_pending = {
        "exit_id": exit_obj.id,
        "purpose": purpose,
    }


def clear_code_prompt(character):
    try:
        del character.ndb._rentdoor_pending
    except Exception:
        pass


def get_code_prompt(character) -> dict | None:
    return getattr(character.ndb, "_rentdoor_pending", None)


# ---------------------------------------------------------------------------
# Secondary code management
# ---------------------------------------------------------------------------


def add_secondary_code(exit_obj, code: str) -> tuple[bool, str]:
    if not is_valid_code(code):
        return False, "Codes must be exactly 7 digits."
    master = getattr(exit_obj.db, "rent_master_code", None)
    if master and code == master:
        return False, "That is the master code."
    codes = list(getattr(exit_obj.db, "rent_secondary_codes", None) or [])
    if code in codes:
        return False, "That code is already registered."
    if len(codes) >= 10:
        return False, "Maximum of 10 secondary codes allowed."
    codes.append(code)
    exit_obj.db.rent_secondary_codes = codes
    return True, "ok"


def remove_secondary_code(exit_obj, code: str) -> tuple[bool, str]:
    codes = list(getattr(exit_obj.db, "rent_secondary_codes", None) or [])
    if code not in codes:
        return False, "That code is not registered."
    codes.remove(code)
    exit_obj.db.rent_secondary_codes = codes
    return True, "ok"


def set_master_code(exit_obj, code: str) -> tuple[bool, str]:
    if not is_valid_code(code):
        return False, "Codes must be exactly 7 digits."
    exit_obj.db.rent_master_code = code
    return True, "ok"


# ---------------------------------------------------------------------------
# Find exit helper (re-exported for command use)
# ---------------------------------------------------------------------------


def find_rentable_exit(caller, arg):
    """Find a rentable exit in caller's location by direction."""
    from commands.door_cmds import find_exit_by_direction

    ex = find_exit_by_direction(caller, arg)
    if ex and is_rentable(ex):
        return ex
    return None
