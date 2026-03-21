"""
Performance profiling for the server.

ProfilingScript - global zero-interval storage script that accumulates metrics.
Helper functions used by commands/base_cmds.py and global scripts.

Always-on metrics (no flag needed):
  - Command rate (rolling 1-minute, 10s bucket-based — O(1) write)
  - Script tick durations (one time.monotonic() per tick — negligible)
  - ScriptDB/RSS baselines (set at server start)

Opt-in timing (requires @profiling/timing):
  - Per-command wall-clock time (p50/p95/max)
  - Per-command DB query count (requires settings.DEBUG = True)

Budgets are calibrated for 300 concurrent users (~7 cmds/user/min peak).
"""

import time
from contextlib import contextmanager

from evennia.scripts.scripts import DefaultScript


# ---------------------------------------------------------------------------
# Budget targets — calibrated for 300 concurrent users
# ---------------------------------------------------------------------------
BUDGETS = {
    "cmd_rate_per_min": 2000,   # 300 users × ~7 cmds/min
    "cmd_avg_ms":       15,
    "cmd_p95_ms":       75,
    "cmd_max_ms":       200,
    "cmd_queries_avg":  10,
    "cmd_queries_warn": 25,
    "script_tick_pct":  0.10,   # max fraction of interval consumed by a single tick
}

_SAMPLES_CAP = 100  # ms_samples list is capped at this many entries per command


# ---------------------------------------------------------------------------
# Module-level script cache — same pattern as world/staff_pending.py
# ---------------------------------------------------------------------------
_SCRIPT = None


def get_profiling_script():
    global _SCRIPT
    if _SCRIPT is None:
        from evennia import search_script
        results = search_script("profiling")
        _SCRIPT = results[0] if results else None
    return _SCRIPT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_timing_enabled():
    script = get_profiling_script()
    return bool(script and script.ndb.timing_enabled)


def get_cmd_rate_1min(script):
    """Rolling 1-minute command count using 10-second buckets."""
    buckets = script.ndb.cmd_rate_buckets or {}
    now_bucket = int(time.time() // 10)
    return sum(v for k, v in buckets.items() if now_bucket - k <= 6)


def get_p95(samples):
    """95th-percentile value from a list of floats."""
    if not samples:
        return 0.0
    s = sorted(samples)
    idx = min(int(len(s) * 0.95), len(s) - 1)
    return s[idx]


# ---------------------------------------------------------------------------
# Instrumentation — called from commands/base_cmds.py
# ---------------------------------------------------------------------------

def record_command_start(cmd):
    """
    Called from Command.at_pre_cmd (and CmdLook.at_pre_cmd / CmdGet.at_pre_cmd).

    Always: increments the rolling rate bucket.
    If timing enabled: stamps _prof_start and _prof_queries on the command instance.
    """
    try:
        script = get_profiling_script()
        if not script:
            return

        # Always-on: O(1) bucket write
        bucket = int(time.time() // 10)
        buckets = script.ndb.cmd_rate_buckets or {}
        buckets[bucket] = buckets.get(bucket, 0) + 1
        # Trim entries older than 8 buckets (80s) to bound memory
        cutoff = bucket - 7
        script.ndb.cmd_rate_buckets = {k: v for k, v in buckets.items() if k >= cutoff}

        # Opt-in timing
        if script.ndb.timing_enabled:
            cmd._prof_start = time.monotonic()
            try:
                from django.db import connection
                cmd._prof_queries = len(connection.queries)
            except Exception:
                cmd._prof_queries = 0
    except Exception:
        pass


def record_command_end(cmd):
    """
    Called from Command.at_post_cmd (and CmdLook / CmdGet equivalents).

    Records elapsed ms and query count if timing was stamped by record_command_start.
    No-op if timing is off or command was blocked before func() ran.
    """
    start = getattr(cmd, '_prof_start', None)
    if start is None:
        return
    try:
        script = get_profiling_script()
        if not script:
            return

        elapsed_ms = (time.monotonic() - start) * 1000

        try:
            from django.db import connection
            queries = max(0, len(connection.queries) - getattr(cmd, '_prof_queries', 0))
        except Exception:
            queries = 0

        key = getattr(cmd, 'key', None) or 'unknown'
        counts = script.ndb.cmd_counts or {}
        entry = counts.get(key)
        if entry is None:
            entry = {
                "calls": 0,
                "total_ms": 0.0,
                "max_ms": 0.0,
                "total_queries": 0,
                "ms_samples": [],
            }
        entry["calls"] += 1
        entry["total_ms"] += elapsed_ms
        if elapsed_ms > entry["max_ms"]:
            entry["max_ms"] = elapsed_ms
        entry["total_queries"] += queries

        samples = entry["ms_samples"]
        samples.append(elapsed_ms)
        if len(samples) > _SAMPLES_CAP:
            entry["ms_samples"] = samples[-_SAMPLES_CAP:]

        counts[key] = entry
        script.ndb.cmd_counts = counts
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Object count snapshots — called from cleanup scripts (zero extra queries)
# ---------------------------------------------------------------------------

def snapshot_object_counts(counts_dict):
    """
    Merge counts_dict into ndb.object_counts on the profiling script.

    Call this at the end of cleanup script runs with counts derived from
    querysets already evaluated during the cleanup — no extra DB queries.

    counts_dict: e.g. {"MatrixNode": 42, "Handset": 17}
    """
    try:
        script = get_profiling_script()
        if script:
            existing = script.ndb.object_counts or {}
            existing.update(counts_dict)
            script.ndb.object_counts = existing
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Tick timing — context manager for global script at_repeat() bodies
# ---------------------------------------------------------------------------

@contextmanager
def timed_tick(script_key, interval_s):
    """
    Wrap a global script's at_repeat() body to record tick duration.

    Always active (not gated behind timing flag) — overhead is one
    time.monotonic() call per tick (microseconds, for scripts that fire
    every 10–3600 seconds).

    Usage:
        def at_repeat(self):
            from world.profiling import timed_tick
            with timed_tick("stamina_regen", self.interval):
                stamina_regen_all()
    """
    start = time.monotonic()
    try:
        yield
    finally:
        elapsed_ms = (time.monotonic() - start) * 1000
        try:
            script = get_profiling_script()
            if script:
                ticks = script.ndb.script_ticks or {}
                entry = ticks.get(script_key)
                if entry is None:
                    entry = {
                        "calls": 0,
                        "total_ms": 0.0,
                        "max_ms": 0.0,
                        "last_ms": 0.0,
                        "interval_s": interval_s,
                    }
                entry["calls"] += 1
                entry["total_ms"] += elapsed_ms
                if elapsed_ms > entry["max_ms"]:
                    entry["max_ms"] = elapsed_ms
                entry["last_ms"] = elapsed_ms
                ticks[script_key] = entry
                script.ndb.script_ticks = ticks
        except Exception:
            pass


# ---------------------------------------------------------------------------
# ProfilingScript
# ---------------------------------------------------------------------------

class ProfilingScript(DefaultScript):
    """
    Global zero-interval storage script for profiling data.

    All metrics live on ndb (ephemeral — discarded on reload by design).
    Baselines are reset in at_server_startstop.at_server_start() each boot.

    Pattern: same as PCNoteStorage in typeclasses/scripts.py.
    """

    def at_script_creation(self):
        self.key = "profiling"
        self.desc = "Server performance profiling storage"
        self.interval = 0
        self.repeats = 0
        self.persistent = True
        self.autodelete = False
