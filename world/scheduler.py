"""
Global APScheduler instance for time-based, non-object-tied recurring jobs.

This module owns a single BackgroundScheduler that runs in a daemon thread
alongside Evennia's Twisted reactor. It is started once in at_server_start()
and shut down in at_server_stop().

Use this for:
  - Weekly/daily announcements and global resets (faction pay, XP catch-up)
  - Periodic data flushes or log rotations
  - Any job that is NOT tied to a specific in-game object (use Evennia Scripts
    for per-object tickers, and evennia.utils.delay for one-shot callbacks)

Do NOT use this for:
  - Per-object tickers (use Evennia Scripts with interval=N)
  - Short one-shot delays <60s tied to a game event (use evennia.utils.delay)
  - Combat/movement callbacks (use delay — they need Twisted's callLater)

Public API:
    get_scheduler() -> BackgroundScheduler
    start_scheduler()
    stop_scheduler()
    register_all_jobs()
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore

try:
    from more_itertools import chunked as _chunked
    _MORE_ITERTOOLS_AVAILABLE = True
except ImportError:
    _MORE_ITERTOOLS_AVAILABLE = False

    def _chunked(iterable, n):
        """Minimal fallback: yield successive n-sized chunks from iterable."""
        chunk = []
        for item in iterable:
            chunk.append(item)
            if len(chunk) >= n:
                yield chunk
                chunk = []
        if chunk:
            yield chunk

logger = logging.getLogger("evennia")

try:
    from tenacity import retry, stop_after_attempt, wait_fixed
    _TENACITY_AVAILABLE = True
except ImportError:
    _TENACITY_AVAILABLE = False


def _safe_register(fn, sched):
    """
    Call fn(sched) with up to 2 attempts and a 1-second wait between them.
    Falls back to a single attempt without retry if tenacity is unavailable.
    """
    if _TENACITY_AVAILABLE:
        _wrapped = retry(
            stop=stop_after_attempt(2),
            wait=wait_fixed(1),
            reraise=True,
        )(fn)
        _wrapped(sched)
    else:
        fn(sched)

try:
    from world.gamelog import get_logger as _get_gamelog
    _log = _get_gamelog(__name__)
except Exception:
    _log = logger

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    """
    Return the global BackgroundScheduler, creating it if needed.
    The scheduler is NOT started here — call start_scheduler() explicitly.
    """
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        _scheduler = BackgroundScheduler(
            jobstores={"default": MemoryJobStore()},
            job_defaults={
                "coalesce": True,       # merge missed runs into one
                "max_instances": 1,     # never run the same job twice concurrently
                "misfire_grace_time": 300,  # allow up to 5 min late
            },
            timezone="UTC",
        )
    return _scheduler


def start_scheduler():
    """
    Start the global scheduler. Called from at_server_start().
    Safe to call multiple times — no-ops if already running.
    """
    sched = get_scheduler()
    if not sched.running:
        sched.start()
        try:
            _log.info("scheduler.started")
        except Exception:
            logger.info("[scheduler] APScheduler started.")
    register_all_jobs()


def stop_scheduler():
    """
    Gracefully stop the global scheduler. Called from at_server_stop().
    """
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[scheduler] APScheduler stopped.")
    _scheduler = None


def register_all_jobs():
    """
    Register all global recurring jobs. Called after start_scheduler().
    Uses replace_existing=True so reloads don't duplicate jobs.
    """
    sched = get_scheduler()

    # --- Faction pay weekly announcement ---
    try:
        from world.rpg.factions.pay import register_pay_jobs
        _safe_register(register_pay_jobs, sched)
    except Exception as exc:
        logger.warning(f"[scheduler] Could not register faction pay jobs: {exc}")

    # --- Daily XP drip catch-up check (midnight UTC) ---
    try:
        from world.rpg.xp import register_xp_jobs
        _safe_register(register_xp_jobs, sched)
    except Exception as exc:
        logger.warning(f"[scheduler] Could not register XP jobs: {exc}")

    # --- Wilderness scavenge density refresh (06:00 UTC) ---
    try:
        from world.wilderness_map import register_wilderness_jobs
        _safe_register(register_wilderness_jobs, sched)
    except Exception as exc:
        logger.warning(f"[scheduler] Could not register wilderness jobs: {exc}")

    # --- Food/bar maintenance (weekly bar register log clear) ---
    try:
        from world.food.jobs import register_food_jobs
        _safe_register(register_food_jobs, sched)
    except Exception as exc:
        logger.warning(f"[scheduler] Could not register food jobs: {exc}")

    # --- Infection tick: all characters (online + offline), every 30 min ---
    sched.add_job(
        _infection_tick_job,
        "interval",
        minutes=30,
        id="infection_tick",
        replace_existing=True,
    )

    # --- Addiction tick: all characters (online + offline), every 30 min ---
    sched.add_job(
        _addiction_tick_job,
        "interval",
        minutes=30,
        id="addiction_tick",
        replace_existing=True,
    )

    # --- Wilderness scavenge cooldown reset: all characters, daily at 04:00 UTC ---
    sched.add_job(
        _wilderness_respawn_job,
        "cron",
        hour=4,
        minute=0,
        id="wilderness_scavenge_respawn",
        replace_existing=True,
    )

    try:
        _log.info("scheduler.jobs_registered")
    except Exception:
        logger.info("[scheduler] All jobs registered.")


# ---------------------------------------------------------------------------
# Job implementations
# ---------------------------------------------------------------------------

def _infection_tick_job():
    """
    Run infection/rejection tick for EVERY character (online and offline).
    Fast-skips characters with no active infection conditions.
    Processes in batches of 100 to avoid holding a DB connection open for the full loop.
    """
    try:
        from typeclasses.characters import Character
        from world.medical.infection import apply_infection_tick
    except Exception:
        return
    for batch in _chunked(Character.objects.iterator(), 100):
        for char in batch:
            try:
                injuries = list(getattr(char.db, "injuries", None) or [])
                if not any(
                    inj.get("infection_stage", 0) > 0
                    or inj.get("infection_risk", 0) > 0.05
                    or (inj.get("cyberware_dbref") and inj.get("rejection_risk", 0) > 0)
                    for inj in injuries
                ):
                    continue
                apply_infection_tick(char)
            except Exception:
                continue


def _addiction_tick_job():
    """
    Run addiction withdrawal/recovery tick for EVERY character (online and offline).
    Fast-skips characters with no active addictions.
    The AddictionWithdrawalScript remains for backward compatibility but this job
    is the authoritative path and includes offline characters.
    """
    try:
        from typeclasses.characters import Character
        from world.alchemy.addiction import _tick_character_addiction
    except Exception:
        return
    for batch in _chunked(Character.objects.iterator(), 100):
        for char in batch:
            try:
                if not getattr(char.db, "addictions", None):
                    continue
                _tick_character_addiction(char)
            except Exception:
                continue


def _wilderness_respawn_job():
    """
    Clear per-location scavenge cooldowns for ALL characters (online and offline).
    Gives a hard daily reset so players who logged off mid-cooldown aren't penalised.
    """
    try:
        from typeclasses.characters import Character
    except Exception:
        return
    for batch in _chunked(Character.objects.iterator(), 100):
        for char in batch:
            try:
                if getattr(char.db, "scavenge_location_cooldowns", None):
                    char.db.scavenge_location_cooldowns = {}
            except Exception:
                continue
