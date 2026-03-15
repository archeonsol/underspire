"""
XP system: time-based gains (3 XP per 6h window, max 4 drops per 24h), catch-up on login.
Skills: 1 raise = 1 point (0-150). Stats: 1 raise = 0.5 points (stored 0-300, display 0-150). Tuned for ~1-1.5 year cap.
"""
import time

from world.levels import MAX_LEVEL, MAX_STAT_LEVEL, xp_cost_for_next_level, letter_to_level_range

# Gain: 3 XP every 6 hours, max 4 drops per rolling 24h (~12 XP/day)
DROP_XP = 3
DROP_INTERVAL_SECS = 6 * 3600
DROPS_PER_24H = 4
WINDOW_24H_SECS = 24 * 3600

# Cap: ~1-1.5 year; escalating cost + stat scale means 3-4 stats to D-E and 4-5 skills to D-C
XP_CAP = 5500


def _stat_level(character, stat_key):
    """Return stored stat level 0-300 (1 XP raise = +1 here = +0.5 displayed points)."""
    from world.chargen import STAT_KEYS
    if stat_key not in STAT_KEYS:
        return 0
    stats = getattr(character.db, "stats", None) or {}
    val = stats.get(stat_key, 0)
    if isinstance(val, int):
        if 0 <= val <= 150:
            val = min(MAX_STAT_LEVEL, val * 2)  # legacy 0-150 scale -> 0-300
        return max(0, min(MAX_STAT_LEVEL, val))
    lo, hi = letter_to_level_range(str(val).upper() if val else "Q", MAX_STAT_LEVEL)
    return (lo + hi) // 2


def _stat_display_level(character, stat_key):
    """Return stat level for display only: 0-150 (stored // 2). Same scale as skills; 1 raise = 0.5 points."""
    return _stat_level(character, stat_key) // 2


def _skill_level(character, skill_key):
    """Return current skill level as int 0-150 (normalizes legacy letter to mid-tier level)."""
    from world.skills import SKILL_KEYS
    if skill_key not in SKILL_KEYS:
        return 0
    skills = getattr(character.db, "skills", None) or {}
    val = skills.get(skill_key, 0)
    if isinstance(val, int):
        return max(0, min(MAX_LEVEL, val))
    lo, hi = letter_to_level_range(str(val).upper() if val else "Q", MAX_LEVEL)
    return (lo + hi) // 2


def _stat_cap_level(character, stat_key):
    """Return stat cap as int 0-300. Legacy int caps in 0-150 are treated as old scale and doubled."""
    caps = getattr(character.db, "stat_caps", None) or {}
    val = caps.get(stat_key, MAX_STAT_LEVEL)
    if isinstance(val, int):
        if 0 <= val <= 150:
            val = val * 2  # legacy chargen used 80-140 on 0-150 scale
        return max(0, min(MAX_STAT_LEVEL, val))
    lo, hi = letter_to_level_range(str(val).upper() if val else "A", MAX_STAT_LEVEL)
    return hi


def _skill_cap_level(character, skill_key):
    """Return skill cap as int 0-150."""
    caps = getattr(character.db, "skill_caps", None) or {}
    val = caps.get(skill_key, MAX_LEVEL)
    if isinstance(val, int):
        return max(0, min(MAX_LEVEL, val))
    lo, hi = letter_to_level_range(str(val).upper() if val else "A", MAX_LEVEL)
    return hi


def get_xp_cost_stat(character, stat_key):
    """Return (cost_for_next_raise, None) to raise stat by 1 level, or (None, None) if at cap."""
    cur = _stat_level(character, stat_key)
    cap = _stat_cap_level(character, stat_key)
    if cur >= cap or cur >= MAX_STAT_LEVEL:
        return None, None
    cost = xp_cost_for_next_level(cur, MAX_STAT_LEVEL)
    return cost, None


def get_xp_cost_skill(character, skill_key):
    """Return (cost_for_next_raise, None) to raise skill by 1 level, or (None, None) if at cap."""
    cur = _skill_level(character, skill_key)
    cap = _skill_cap_level(character, skill_key)
    if cur >= cap or cur >= MAX_LEVEL:
        return None, None
    cost = xp_cost_for_next_level(cur, MAX_LEVEL)
    return cost, None


def grant_pending_xp(character):
    """
    Grant at most one XP drop on login if a 6h window has passed (catch-up: you don't
    have to be online at the exact strike time). Still need to log in multiple times
    per day to get all 4 drops. Respects 4-per-24h and XP cap.
    Returns (xp_granted, drops_used).
    """
    now = time.time()
    xp = int(getattr(character.db, "xp", 0) or 0)
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
    # At most one drop per login (catch-up = next eligible window, not all missed)
    can_claim = min(1, periods_elapsed, DROPS_PER_24H - len(drop_times))
    if can_claim <= 0:
        return 0, 0

    total_grant = min(can_claim * DROP_XP, cap - xp)
    drops_used = total_grant // DROP_XP
    if drops_used <= 0:
        return 0, 0

    drop_times.append(now)
    drop_times = [t for t in drop_times if now - t < WINDOW_24H_SECS]
    drop_times.sort()
    character.db.xp_drop_times = drop_times[-DROPS_PER_24H:]
    character.db.xp_last_drop_time = now
    character.db.xp = xp + total_grant
    return total_grant, drops_used
