"""
XP system: time-based gains (2 XP per 6h window, max 4 drops per 24h).
XP_CAP = 3050 (max in-game earnings; chargen XP is separate).
Skills: stored = display (0-150). Levels 0-80 = level*0.5; 81+ from world.constants.SKILL_XP_CURVE_LATE.
Stats: stored 0-300, display = stored//2 (via character.get_display_stat). Cost: 2.0 to 180, then exponential.
"""
import time

from world.constants import SKILL_XP_CURVE_LATE
from world.levels import MAX_LEVEL, MAX_STAT_LEVEL, letter_to_level_range


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
    """Return stored stat level 0-300."""
    from world.chargen import STAT_KEYS
    if stat_key not in STAT_KEYS:
        return 0
    stats = getattr(character.db, "stats", None) or {}
    val = stats.get(stat_key, 0)
    if isinstance(val, int):
        if 0 <= val <= 150:
            val = min(MAX_STAT_LEVEL, val * 2)  # legacy 0-150 scale -> 0-300
        return max(0, min(MAX_STAT_LEVEL, val))
    lo, hi = letter_to_level_range(str(val).upper() if val else "U", MAX_STAT_LEVEL)
    return (lo + hi) // 2


def _stat_display_level(character, stat_key):
    """Return stat display level 0-150. Prefer character.get_display_stat(stat_key) to avoid leaky abstraction."""
    if hasattr(character, "get_display_stat"):
        return character.get_display_stat(stat_key)
    return _stat_level(character, stat_key) // 2


def _skill_level(character, skill_key):
    """Return current skill level 0-150 (stored = display)."""
    from world.skills import SKILL_KEYS
    if skill_key not in SKILL_KEYS:
        return 0
    skills = getattr(character.db, "skills", None) or {}
    val = skills.get(skill_key, 0)
    if isinstance(val, int):
        return max(0, min(MAX_LEVEL, val))
    lo, hi = letter_to_level_range(str(val).upper() if val else "U", MAX_LEVEL)
    return (lo + hi) // 2


def _stat_cap_level(character, stat_key):
    """Return stat cap as stored 0-300."""
    caps = getattr(character.db, "stat_caps", None) or {}
    val = caps.get(stat_key, MAX_STAT_LEVEL)
    if isinstance(val, int):
        if 0 <= val <= 150:
            val = val * 2
        return max(0, min(MAX_STAT_LEVEL, val))
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


def grant_pending_xp(character):
    """
    Grant at most one XP drop on login if a 6h window has passed.
    Max 4 drops per rolling 24h. Respects XP_CAP (3050).
    Returns (xp_granted, drops_used).
    """
    now = time.time()
    xp = float(getattr(character.db, "xp", 0) or 0)
    cap = int(getattr(character.db, "xp_cap", XP_CAP) or XP_CAP)
    if xp >= cap:
        return 0, 0

    last = getattr(character.db, "xp_last_drop_time", None) or 0
    drop_times = list(getattr(character.db, "xp_drop_times", None) or [])
    drop_times = [t for t in drop_times if now - t < WINDOW_24H_SECS]
    drop_times.sort()

    if last <= 0:
        periods_elapsed = DROPS_PER_24H
    else:
        periods_elapsed = int((now - last) / DROP_INTERVAL_SECS)
    can_claim = min(1, periods_elapsed, DROPS_PER_24H - len(drop_times))
    if can_claim <= 0:
        return 0, 0

    total_grant = min(can_claim * DROP_XP, cap - xp)
    drops_used = total_grant // DROP_XP if DROP_XP else 0
    if drops_used <= 0:
        return 0, 0

    drop_times.append(now)
    drop_times = [t for t in drop_times if now - t < WINDOW_24H_SECS]
    drop_times.sort()
    character.db.xp_drop_times = drop_times[-DROPS_PER_24H:]
    character.db.xp_last_drop_time = now
    character.db.xp = xp + total_grant
    return total_grant, drops_used
