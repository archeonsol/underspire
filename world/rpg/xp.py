"""
XP system: time-based gains (2 XP per 6h window, max 4 drops per 24h).
Drops use UTC-aligned 6h windows (00:00, 06:00, 12:00, 18:00 UTC); granted on login (catch-up).
XP_CAP = 3050 (max in-game earnings; chargen XP is separate). XP spent on languages does not count
toward the cap (tracked in xp_spent_on_languages) so characters can earn that XP back.
Skills: stored = display (0-150). Levels 0-80 = level*0.5; 81+ from world.constants.SKILL_XP_CURVE_LATE.
Stats: stored 0-300, display = stored//2 (via character.get_display_stat). Cost: 2.0 to 180, then exponential.
"""
import logging
import time

logger = logging.getLogger("evennia")

from world.constants import SKILL_XP_CURVE_LATE
from world.levels import MAX_LEVEL, MAX_STAT_LEVEL, letter_to_level_range

try:
    from boltons.mathutils import clamp as _clamp
except ImportError:
    def _clamp(val, lower=None, upper=None):
        if lower is not None:
            val = max(lower, val)
        if upper is not None:
            val = min(upper, val)
        return val

# Time-based drip: 2 XP per 6-hour window, max 4 drops per 24h = 8 XP/day
DROP_XP = 2
DROP_INTERVAL_SECS = 6 * 3600
DROPS_PER_24H = 4
WINDOW_24H_SECS = 24 * 3600

# Hard lifetime cap on earnable XP (starting power from chargen is separate)
XP_CAP = 3050


# -----------------------------------------------------------------------------
# Universal cost helpers (single source of truth)
# -----------------------------------------------------------------------------
def get_skill_cumulative_xp(level):
    """Cumulative XP to reach skill level. Levels 0-80 = level * 0.5; 81+ from SKILL_XP_CURVE_LATE."""
    if level is None or level < 0:
        return 0.0
    level = int(level)
    if level <= 80:
        return level * 0.5
    return float(SKILL_XP_CURVE_LATE.get(min(level, 151), 0.0))


def get_skill_cost(current_level):
    """XP cost to move from current_level to current_level + 1. Returns None if current_level >= 151."""
    if current_level is None or current_level < 0:
        current_level = 0
    cur = int(current_level)
    if cur >= 151:
        return None
    return round(get_skill_cumulative_xp(cur + 1) - get_skill_cumulative_xp(cur), 3)


def get_stat_cost(stored_level):
    """XP cost to move from stored_level to stored_level + 1. Flat 2.0 to 180, then 20-level bands anchored at 2.344."""
    if stored_level is None or stored_level < 0:
        stored_level = 0
    stored_level = int(stored_level)
    if stored_level >= 300:
        return None
    if stored_level < 180:
        return 2.0
    band = (stored_level - 180) // 20
    base_level = 180 + (band * 20)
    base_cost = 2.344 * (2 ** band)
    step = base_cost / 20.0
    level_cost = base_cost + ((stored_level - base_level) * step)
    return round(level_cost, 3)


# Aliases for existing callers
get_skill_cost_for_next_level = get_skill_cost
get_stat_cost_for_next_level = get_stat_cost
xp_cost_for_skill_level = get_skill_cost
xp_cost_for_stat_level = get_stat_cost


def total_xp_for_skill(level):
    """Total cumulative XP to reach skill level (0-150)."""
    return get_skill_cumulative_xp(level)


def total_xp_for_stat(stored_level):
    """Total cumulative XP to reach stored stat level (0-300). Sum of get_stat_cost per step."""
    if stored_level is None or stored_level < 0:
        return 0.0
    stored_level = int(stored_level)
    total = 0.0
    for i in range(stored_level):
        c = get_stat_cost(i)
        if c is None:
            break
        total += c
    return round(total, 3)


# -----------------------------------------------------------------------------
# Character helpers (stored levels; display = stored // 2 for stats)
# -----------------------------------------------------------------------------
def _stat_level(character, stat_key):
    """Return stored stat level 0-300. Reads from TraitHandler first, falls back to db.stats dict."""
    from world.rpg.chargen import STAT_KEYS
    if stat_key not in STAT_KEYS:
        return 0
    # Traits path (post-migration): trait_stats handler stores base 0-300
    handler = getattr(character, "trait_stats", None)
    if handler is not None:
        trait = handler.get(stat_key)
        if trait is not None:
            return _clamp(int(trait.base or 0), 0, MAX_STAT_LEVEL)
    # Legacy fallback: raw db.stats dict
    stats = getattr(character.db, "stats", None) or {}
    val = stats.get(stat_key, 0)
    if isinstance(val, int):
        # Stored in DB is always 0-300; no legacy scale conversion (would double new writes).
        return _clamp(val, 0, MAX_STAT_LEVEL)
    lo, hi = letter_to_level_range(str(val).upper() if val else "U", MAX_STAT_LEVEL)
    return (lo + hi) // 2


def _stat_display_level(character, stat_key):
    """Return stat display level 0-150. Prefer character.get_display_stat(stat_key) to avoid leaky abstraction."""
    if hasattr(character, "get_display_stat"):
        return character.get_display_stat(stat_key)
    return _stat_level(character, stat_key) // 2


def _skill_level(character, skill_key):
    """Return current skill level 0-150 (stored = display). Reads from TraitHandler first, falls back to db.skills dict."""
    from world.skills import SKILL_KEYS
    if skill_key not in SKILL_KEYS:
        return 0
    # Traits path: trait_skills handler stores base 0-150
    handler = getattr(character, "trait_skills", None)
    if handler is not None:
        trait = handler.get(skill_key)
        if trait is not None:
            return _clamp(int(trait.base or 0), 0, MAX_LEVEL)
    # Fallback: raw db.skills dict
    skills = getattr(character.db, "skills", None) or {}
    val = skills.get(skill_key, 0)
    if isinstance(val, int):
        return _clamp(val, 0, MAX_LEVEL)
    lo, hi = letter_to_level_range(str(val).upper() if val else "U", MAX_LEVEL)
    return (lo + hi) // 2


def _stat_cap_level(character, stat_key):
    """Return stat cap as stored 0-300. Reads from TraitHandler first, falls back to db.stat_caps dict."""
    # Traits path (post-migration): cap stored as "cap_<stat_key>" in trait_stats handler
    handler = getattr(character, "trait_stats", None)
    if handler is not None:
        trait = handler.get(f"cap_{stat_key}")
        if trait is not None:
            return _clamp(int(trait.base or MAX_STAT_LEVEL), 0, MAX_STAT_LEVEL)
    # Legacy fallback: raw db.stat_caps dict
    caps = getattr(character.db, "stat_caps", None) or {}
    val = caps.get(stat_key, MAX_STAT_LEVEL)
    if isinstance(val, int):
        # Cap in DB is always 0-300; no legacy scale conversion.
        return _clamp(val, 0, MAX_STAT_LEVEL)
    lo, hi = letter_to_level_range(str(val).upper() if val else "A", MAX_STAT_LEVEL)
    return hi


def _skill_cap_level(character, skill_key):
    """Return skill cap 0-150. No per-skill cap; always MAX_LEVEL."""
    return MAX_LEVEL


def get_xp_cost_stat(character, stat_key):
    """Return (cost_for_next_raise, None) or (None, None) if at cap."""
    cur = _stat_level(character, stat_key)
    cap = _stat_cap_level(character, stat_key)
    if cur >= cap or cur >= MAX_STAT_LEVEL:
        return None, None
    cost = get_stat_cost_for_next_level(cur)
    return (round(cost, 3), None) if cost is not None else (None, None)


def get_xp_cost_skill(character, skill_key):
    """Return (cost_for_next_raise, None) or (None, None) if at cap."""
    cur = _skill_level(character, skill_key)
    cap = _skill_cap_level(character, skill_key)
    if cur >= cap or cur >= MAX_LEVEL:
        return None, None
    cost = get_skill_cost_for_next_level(cur)
    return (round(cost, 3), None) if cost is not None else (None, None)


def _utc_window_id(timestamp=None):
    """Return the 6h UTC window id for a given time (default now). Windows align to 00:00, 06:00, 12:00, 18:00 UTC."""
    t = timestamp if timestamp is not None else time.time()
    return int(t // DROP_INTERVAL_SECS)


def grant_pending_xp(character):
    """
    Grant at most one XP drop on login for the most recent completed UTC 6h window (00:00, 06:00, 12:00, 18:00 UTC).
    No bulk catch-up: missing multiple windows only grants the latest one. Respects XP cap; language XP doesn't count toward cap.
    Returns (xp_granted, drops_used).
    """
    now = time.time()
    xp = float(getattr(character.db, "xp", 0) or 0)
    base_cap = int(getattr(character.db, "xp_cap", XP_CAP) or XP_CAP)
    language_xp_spent = float(getattr(character.db, "xp_spent_on_languages", 0) or 0)
    effective_cap = base_cap + language_xp_spent
    if xp >= effective_cap:
        return 0, 0

    # UTC-aligned 6h windows: catch-up grants only the single most recent completed window (no bulk catch-up)
    current_window = _utc_window_id(now)
    last_completed_window = current_window - 1

    # Migrate legacy xp_drop_times to xp_drop_window_ids (timestamps are UTC epoch)
    drop_window_ids = list(getattr(character.db, "xp_drop_window_ids", None) or [])
    if not drop_window_ids:
        legacy_times = list(getattr(character.db, "xp_drop_times", None) or [])
        if legacy_times:
            drop_window_ids = [_utc_window_id(t) for t in legacy_times]
            character.db.xp_drop_window_ids = drop_window_ids

    # Keep only window ids from the last 24h
    drop_window_ids = [w for w in drop_window_ids if w >= current_window - 4]
    already_got = set(drop_window_ids)
    # Only grant for the most recent completed window if we haven't already
    if last_completed_window in already_got:
        return 0, 0
    # Grant exactly one drop, capped at the gap to effective_cap (handles fractional XP near cap).
    total_grant = min(DROP_XP, effective_cap - xp)
    if total_grant <= 0:
        return 0, 0

    drop_window_ids.append(last_completed_window)
    drop_window_ids = sorted(set(w for w in drop_window_ids if w >= current_window - 4))[-DROPS_PER_24H:]
    character.db.xp_drop_window_ids = drop_window_ids
    character.db.xp = xp + total_grant
    return total_grant, 1


# ---------------------------------------------------------------------------
# APScheduler job registration
# ---------------------------------------------------------------------------

def _daily_xp_catchup():
    """
    Grant catch-up XP to all online characters who missed drops while offline.
    Runs daily at midnight UTC via APScheduler.
    """
    try:
        from evennia import SESSION_HANDLER
    except Exception as exc:
        logger.warning("[xp_daily_catchup] import unavailable, skipping: %s", exc)
        return
    try:
        for session in SESSION_HANDLER.get_sessions():
            try:
                char = session.get_puppet()
                if not char:
                    continue
                granted, _ = grant_pending_xp(char)
                if granted:
                    char.msg(f"|g[XP] Daily catch-up: +{granted} XP.|n")
            except Exception as exc:
                logger.warning("[xp_daily_catchup] skipped session %r: %s", session, exc)
    except Exception as exc:
        logger.error("[xp_daily_catchup] failed: %s", exc, exc_info=True)


def register_xp_jobs(sched):
    """
    Register XP APScheduler jobs.
    Called by world/scheduler.py register_all_jobs().

    Args:
        sched: A running APScheduler BackgroundScheduler instance.
    """
    sched.add_job(
        _daily_xp_catchup,
        trigger="cron",
        hour=0,
        minute=5,
        id="xp_daily_catchup",
        replace_existing=True,
    )
