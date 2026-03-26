"""
Server startstop hooks

This module contains functions called by Evennia at various
points during its startup, reload and shutdown sequence. It
allows for customizing the server operation as desired.

This module must contain at least these global functions:

at_server_init()
at_server_start()
at_server_stop()
at_server_reload_start()
at_server_reload_stop()
at_server_cold_start()
at_server_cold_stop()

"""


def at_server_init():
    """
    This is called first as the server is starting up, regardless of how.
    """
    pass


def at_server_start():
    """
    This is called every time the server starts up, regardless of
    how it was shut down.
    """
    # Auto-apply any pending Django migrations (idempotent — no-op if up to date).
    try:
        from django.core.management import call_command
        call_command("migrate", interactive=False, verbosity=0)
    except Exception as _migrate_exc:
        import logging as _logging
        _logging.getLogger("evennia").warning(f"[at_server_start] migrate failed: {_migrate_exc}")

    from evennia import create_channel, search_channel
    from world.rpg.language import ensure_lore_languages
    from world.combat.tickers import cleanup_orphaned_combat_tickers

    ensure_lore_languages()

    # ------------------------------------------------------------------
    # One-time data migrations: move legacy Script-based data stores to
    # their proper homes (ServerConfig, Django models). Each block is a
    # no-op once the script no longer exists in the DB.
    # ------------------------------------------------------------------
    _migrate_global_climate_script()
    _migrate_staff_pending_script()
    _migrate_pc_note_storage()
    # Profiling script had no persistent data (all ndb) — just delete it.
    _delete_legacy_script("profiling")

    # ------------------------------------------------------------------
    # Ticking global scripts — each class owns its own ensure() logic
    # ------------------------------------------------------------------
    from typeclasses.scripts import (
        StaminaRegenScript,
        BleedingTickScript,
        AddictionWithdrawalScript,
        HandsetMessageCleanupScript,
    )
    from typeclasses.matrix.scripts import MatrixCleanupScript, MatrixConnectionScript

    for script_cls in (
        StaminaRegenScript,
        BleedingTickScript,
        AddictionWithdrawalScript,
        HandsetMessageCleanupScript,
        MatrixCleanupScript,
        MatrixConnectionScript,
    ):
        script_cls.ensure()

    # Fix legacy matrix script typeclass paths (typeclasses.scripts.* alias → canonical)
    _migrate_matrix_script_paths()

    # ------------------------------------------------------------------
    # Channels
    # ------------------------------------------------------------------
    from world.staff_pending import STAFF_PENDING_CHANNEL_ALIAS
    if not list(search_channel(STAFF_PENDING_CHANNEL_ALIAS)):
        create_channel(
            key=STAFF_PENDING_CHANNEL_ALIAS,
            aliases=["pending", "staffpending"],
            desc="Staff queue for pending approval requests (sdesc custom terms, etc.). Subscribe to see new requests.",
            locks="listen:perm(Builder);send:perm(Builder);control:perm(Admin)",
        )

    # Nuke any legacy Help/xhelp channels and recreate OOC channels cleanly.
    try:
        legacy_help = list(search_channel("Help")) + list(search_channel("xhelp"))
        seen = set()
        for ch in legacy_help:
            if not ch or ch.id in seen:
                continue
            seen.add(ch.id)
            try:
                ch.delete()
            except Exception:
                continue
    except Exception:
        pass

    ooc_channels = (
        ("OOC-Chat", ["xooc"], "OOC chat. Uses your account OOC name (set with @oocname).", "listen:all();send:all();control:perm(Admin)"),
        ("Game-Help", ["xgame"], "Game help. Ask questions about how to play.", "listen:all();send:all();control:perm(Admin)"),
        ("Staff", ["xstaff"], "Staff-only channel.", "listen:perm(Builder);send:perm(Builder);control:perm(Admin)"),
        ("Assist", ["xassist"], "One-way assistance channel to staff. You only see your own messages; staff see all. Staff reply privately with xhelpreply <account> <message>.", "listen:all();send:all();control:perm(Admin)"),
    )
    for key, aliases, desc, locks in ooc_channels:
        if not list(search_channel(aliases[0])):
            create_channel(key=key, aliases=aliases, desc=desc, locks=locks)

    cleanup_orphaned_combat_tickers()

    # ------------------------------------------------------------------
    # APScheduler
    # ------------------------------------------------------------------
    try:
        from world.scheduler import start_scheduler
        start_scheduler()
    except Exception as _sched_exc:
        import logging as _logging
        _logging.getLogger("evennia").warning(f"[at_server_start] APScheduler failed to start: {_sched_exc}")

    # ------------------------------------------------------------------
    # Whoosh help search index
    # ------------------------------------------------------------------
    try:
        from world.help_search import build_help_index
        build_help_index()
    except Exception as _help_exc:
        import logging as _logging
        _logging.getLogger("evennia").warning(f"[at_server_start] Help index build failed: {_help_exc}")

    # ------------------------------------------------------------------
    # Profiling baselines (ndb is cleared on every reload — always reset)
    # ------------------------------------------------------------------
    try:
        import time
        import resource
        import world.profiling as _prof
        from evennia.scripts.models import ScriptDB
        _prof._script_count_baseline = ScriptDB.objects.count()
        _prof._start_time = time.time()
        _prof._rss_baseline_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        _prof._timing_enabled = False
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Migration helpers — called once per legacy script, no-op once deleted
# ---------------------------------------------------------------------------

def _delete_legacy_script(key):
    """Delete a legacy script by key if it exists. Silent no-op otherwise."""
    try:
        from evennia.scripts.models import ScriptDB
        for s in ScriptDB.objects.filter(db_key=key):
            try:
                s.delete()
            except Exception:
                pass
    except Exception:
        pass


def _migrate_global_climate_script():
    """
    Migrate GlobalClimateScript data → ServerConfig keys.
    Runs once; after deletion the block is a no-op.
    """
    try:
        from evennia.scripts.models import ScriptDB
        scripts = list(ScriptDB.objects.filter(db_key="global_climate"))
        if not scripts:
            return
        from evennia.server.models import ServerConfig
        from evennia import search_script
        results = search_script("global_climate")
        if results:
            scr = results[0]
            # Migrate values only if ServerConfig doesn't already have them
            weather = getattr(scr.db, "weather", None)
            if weather and not ServerConfig.objects.conf("CLIMATE_WEATHER", default=None):
                ServerConfig.objects.conf("CLIMATE_WEATHER", weather)
            time_auto = getattr(scr.db, "time_auto_utc", None)
            if time_auto is not None and ServerConfig.objects.conf("CLIMATE_TIME_AUTO_UTC", default=None) is None:
                ServerConfig.objects.conf("CLIMATE_TIME_AUTO_UTC", time_auto)
            tod = getattr(scr.db, "time_of_day", None)
            if tod and not ServerConfig.objects.conf("CLIMATE_TIME_OF_DAY", default=None):
                ServerConfig.objects.conf("CLIMATE_TIME_OF_DAY", tod)
            overrides = getattr(scr.db, "line_overrides", None)
            if isinstance(overrides, dict) and overrides and not ServerConfig.objects.conf("CLIMATE_LINE_OVERRIDES", default=None):
                ServerConfig.objects.conf("CLIMATE_LINE_OVERRIDES", overrides)
        _delete_legacy_script("global_climate")
    except Exception:
        pass


def _migrate_staff_pending_script():
    """
    Migrate StaffPendingScript data → PendingJob model rows.
    Runs once; after deletion the block is a no-op.
    """
    try:
        from evennia.scripts.models import ScriptDB
        if not ScriptDB.objects.filter(db_key="staff_pending").exists():
            return
        from evennia import search_script
        from world.models import PendingJob
        results = search_script("staff_pending")
        if results:
            scr = results[0]
            pending = getattr(scr.db, "pending", None) or []
            for job in pending:
                if not isinstance(job, dict):
                    continue
                job_id = job.get("id") or ""
                if not job_id or PendingJob.objects.filter(job_id=job_id).exists():
                    continue
                try:
                    PendingJob.objects.create(
                        job_id=job_id,
                        job_type=job.get("type", "unknown"),
                        requester_id=job.get("requester_id") or 0,
                        payload=job.get("payload") or {},
                        meta=job.get("meta") or {},
                    )
                except Exception:
                    pass
        _delete_legacy_script("staff_pending")
    except Exception:
        pass


def _migrate_pc_note_storage():
    """
    Migrate PCNoteStorage data → PCNote model rows.
    Runs once; after deletion the block is a no-op.
    """
    try:
        from evennia.scripts.models import ScriptDB
        if not ScriptDB.objects.filter(db_key="pc_note_storage").exists():
            return
        from evennia import search_script
        from world.models import PCNote
        from datetime import datetime, timezone
        results = search_script("pc_note_storage")
        if results:
            scr = results[0]
            notes = getattr(scr.db, "notes", None) or []
            for note in notes:
                if not isinstance(note, dict):
                    continue
                # Skip if already migrated (match by char_id + title + created_at)
                char_id = note.get("char_id")
                if char_id is None:
                    continue
                try:
                    created_str = note.get("created_at") or ""
                    created_at = None
                    if created_str:
                        try:
                            created_at = datetime.fromisoformat(created_str.rstrip("Z")).replace(tzinfo=timezone.utc)
                        except Exception:
                            pass
                    PCNote.objects.create(
                        category=note.get("category") or "UNCATEGORIZED",
                        title=note.get("title") or "(untitled)",
                        body=note.get("body") or "",
                        char_id=char_id,
                        char_key=note.get("char_key") or "",
                        account_id=note.get("account_id"),
                        account_key=note.get("account_key") or "",
                        created_at=created_at or datetime.now(timezone.utc),
                    )
                except Exception:
                    pass
        _delete_legacy_script("pc_note_storage")
    except Exception:
        pass


def _migrate_matrix_script_paths():
    """
    Update legacy matrix script typeclass paths from the re-export alias to canonical.
    No-op once already updated.
    """
    try:
        from evennia.scripts.models import ScriptDB
        _FIXES = {
            "matrix_cleanup": "typeclasses.matrix.scripts.MatrixCleanupScript",
            "matrix_connection_check": "typeclasses.matrix.scripts.MatrixConnectionScript",
        }
        for key, canonical_path in _FIXES.items():
            ScriptDB.objects.filter(db_key=key).exclude(
                db_typeclass_path=canonical_path
            ).update(db_typeclass_path=canonical_path)
    except Exception:
        pass


def at_server_stop():
    """
    This is called just before the server is shut down, regardless
    of it is for a reload, reset or shutdown.
    """
    try:
        from world.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass


def at_server_reload_start():
    """
    This is called only when server starts back up after a reload.

    Evennia invokes this inside run_init_hooks() before portal_sessions_sync() in the
    same PSYNC handler. Schedule a follow-up broadcast on the next reactor tick so it
    runs after sessions are rebuilt and after the default "... Server restarted." line,
    which helps web/telnet clients that otherwise appear stuck on the pre-reload banner.
    """
    from twisted.internet import reactor

    def _after_full_psync():
        from django.conf import settings
        from evennia import SESSION_HANDLER

        if getattr(settings, "BROADCAST_SERVER_RESTART_MESSAGES", True):
            SESSION_HANDLER.announce_all(" |gReload complete.|n")

    reactor.callLater(0, _after_full_psync)


def at_server_reload_stop():
    """
    This is called only time the server stops before a reload.
    """
    pass


def at_server_cold_start():
    """
    This is called only when the server starts "cold", i.e. after a
    shutdown or a reset.
    """
    pass


def at_server_cold_stop():
    """
    This is called only when the server goes down due to a shutdown or
    reset.
    """
    pass
