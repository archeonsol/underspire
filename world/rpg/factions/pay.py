"""
Weekly pay collection. Characters collect pay at a registry terminal.
Pay is available once every 7 real-time days per faction.

Currency is stored on character.db.currency (int) via world.rpg.economy.
All wallet mutations go through economy helpers so the transaction log stays
consistent across faction pay, shop purchases, and manual transfers.
"""

import logging
import time

from world.rpg.factions.membership import _log_faction_event, get_member_rank

logger = logging.getLogger("evennia")

PAY_COOLDOWN_SECONDS = 7 * 24 * 60 * 60  # 7 days

# Minimum membership before first paycheck (anti join-collect-discharge exploit).
FIRST_PAY_DELAY_SECONDS = 3 * 24 * 60 * 60  # 3 days after joining


def can_collect_pay(character, faction_key):
    """
    Check if a character can collect weekly pay from a faction.

    Returns (can_collect: bool, reason: str, amount: int).
    """
    from world.rpg.factions import get_faction, is_faction_member
    from world.rpg.factions.ranks import get_rank_pay

    fdata = get_faction(faction_key)
    if not fdata:
        return False, "Unknown faction.", 0

    if not is_faction_member(character, faction_key):
        return False, "Not a member.", 0

    rank = get_member_rank(character, faction_key)
    pay_amount = get_rank_pay(fdata["ranks"], rank)

    if pay_amount <= 0:
        return False, "Your rank does not include pay.", 0

    # First-pay delay: new members must wait before collecting.
    first_cd_key = f"pay_first_{fdata['key']}"
    if not character.cooldowns.ready(first_cd_key):
        remaining = character.cooldowns.time_left(first_cd_key)
        remaining_hours = int(remaining / 3600)
        return False, f"New member. First pay available in {remaining_hours}h.", 0

    # Weekly pay cooldown gate (CooldownHandler is authoritative; db.faction_pay_collected kept for display).
    pay_cd_key = f"pay_{fdata['key']}"
    if not character.cooldowns.ready(pay_cd_key):
        remaining = character.cooldowns.time_left(pay_cd_key)
        remaining_days = int(remaining / 86400)
        remaining_hours = int((remaining % 86400) / 3600)
        return False, f"Next pay in {remaining_days}d {remaining_hours}h.", 0

    return True, "Pay available.", pay_amount


def collect_pay(character, faction_key):
    """
    Collect weekly pay. Adds currency to character, updates timestamp.

    Returns (success: bool, message: str, amount: int).
    """
    from world.rpg.factions import get_faction

    can, reason, amount = can_collect_pay(character, faction_key)
    if not can:
        return False, reason, 0

    fdata = get_faction(faction_key)

    from world.rpg.economy import add_funds
    add_funds(character, amount, party=fdata["name"], reason="faction pay")

    # Set weekly cooldown (authoritative gate).
    character.cooldowns.add(f"pay_{fdata['key']}", PAY_COOLDOWN_SECONDS)

    # Keep db.faction_pay_collected for display purposes (terminal shows last pay date).
    pay_times = character.db.faction_pay_collected or {}
    pay_times[fdata["key"]] = time.time()
    character.db.faction_pay_collected = pay_times

    _log_faction_event(
        character,
        fdata["key"],
        "pay_collected",
        f"{amount} credits",
    )

    return True, f"Collected {amount} from {fdata['name']}.", amount


# ---------------------------------------------------------------------------
# APScheduler job registration
# ---------------------------------------------------------------------------

def _weekly_faction_pay_announcement():
    """
    Broadcast weekly pay availability to all online faction members.
    Runs once per week via APScheduler (registered in world/scheduler.py).
    """
    try:
        from evennia import SESSION_HANDLER
        from world.rpg.factions import get_character_factions
    except Exception as exc:
        logger.warning("[faction_pay_announcement] import unavailable, skipping: %s", exc)
        return
    try:
        for session in SESSION_HANDLER.get_sessions():
            try:
                char = session.get_puppet()
                if not char:
                    continue
                factions = get_character_factions(char)
                if factions:
                    char.msg("|g[FACTION] Weekly pay is now available at your faction terminal.|n")
            except Exception as exc:
                logger.warning("[faction_pay_announcement] skipped session %r: %s", session, exc)
    except Exception as exc:
        logger.error("[faction_pay_announcement] failed: %s", exc, exc_info=True)


def _weekly_faction_economy_log_flush():
    """
    Flush/archive faction economy log entries older than 30 days.
    Runs once per day via APScheduler.
    """
    import time as _time
    cutoff = _time.time() - (30 * 24 * 3600)
    try:
        from typeclasses.characters import Character
    except Exception as exc:
        logger.warning("[faction_economy_log_flush] import unavailable, skipping: %s", exc)
        return
    try:
        for char in Character.objects.all():
            try:
                log = getattr(char.db, "faction_log", None)
                if not log:
                    continue
                trimmed = [
                    e for e in log if (e.get("time", e.get("timestamp", 0)) or 0) >= cutoff
                ]
                if len(trimmed) != len(log):
                    char.db.faction_log = trimmed
            except Exception as exc:
                logger.warning("[faction_economy_log_flush] skipped %r: %s", char, exc)
    except Exception as exc:
        logger.error("[faction_economy_log_flush] failed: %s", exc, exc_info=True)


def register_pay_jobs(sched):
    """
    Register faction pay APScheduler jobs.
    Called by world/scheduler.py register_all_jobs().

    Args:
        sched: A running APScheduler BackgroundScheduler instance.
    """
    sched.add_job(
        _weekly_faction_pay_announcement,
        trigger="interval",
        weeks=1,
        id="faction_pay_weekly_announcement",
        replace_existing=True,
    )
    sched.add_job(
        _weekly_faction_economy_log_flush,
        trigger="cron",
        hour=1,
        minute=0,
        id="faction_economy_log_flush",
        replace_existing=True,
    )
