"""
APScheduler jobs for food/bar systems.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("evennia")


def _weekly_bar_register_log_clear():
    """
    Clear register logs on all bar stations once every 7 days.
    """
    try:
        from evennia.objects.models import ObjectDB
    except Exception:
        return

    try:
        bars = ObjectDB.objects.filter(db_typeclass_path="typeclasses.bar_station.BarStation")
    except Exception:
        bars = []

    cleared = 0
    for bar in bars:
        try:
            if getattr(bar.db, "register_log", None):
                bar.db.register_log = []
                cleared += 1
        except Exception:
            continue

    try:
        logger.info(f"[scheduler] Weekly bar register log clear complete. Bars cleared: {cleared}")
    except Exception:
        pass


def register_food_jobs(sched):
    """
    Register food/bar APScheduler jobs.
    Called by world.scheduler.register_all_jobs().
    """
    sched.add_job(
        _weekly_bar_register_log_clear,
        trigger="interval",
        weeks=1,
        id="bar_register_log_weekly_clear",
        replace_existing=True,
    )

