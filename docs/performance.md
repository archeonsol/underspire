# Evennia Performance Best Practices

Evennia's performance model differs from a typical Django app: almost all game data flows through the attribute system rather than model fields, and game objects are long-lived in process memory. Most pitfalls come from misunderstanding where the cache boundary is and from treating Evennia's scripting system like a general-purpose task queue.

---

## 1. `db` vs `ndb` — Know the Boundary

`obj.db.foo` is a persistent attribute. Every **write** flushes to SQLite immediately. Reads go through Evennia's `AttributeHandler`, which maintains an in-process cache per object — the first access after a server start hits the database; subsequent reads within the same process are served from cache.

`obj.ndb.foo` is a Python dict on the instance. It is completely free — no SQL, no serialization — and survives nothing beyond a server reload.

**Rule:** if a value only matters while the object is active (session state, combat flags, in-flight timers), use `ndb`. If it must survive `/reload` or a server restart, use `db`.

**Good example** — `commands/performance_cmds.py` stores all performance state (`performance_lines`, `performance_cooldown_until`, `performance_room_id`, `performance_outcome`, `performance_result`, `performance_improvising`) on `character.ndb`. None of it needs to survive a reload. Writing these to `db` every tick would be gratuitous DB churn.

**Anti-pattern** — reading `obj.db.foo` inside a loop when the value won't change during that loop:

```python
# Bad: AttributeHandler lookup on every iteration
for item in inventory:
    if item.db.weight > obj.db.carry_limit:  # obj.db.carry_limit hit N times
        ...

# Good: cache the Python value once
carry_limit = obj.db.carry_limit
for item in inventory:
    if item.db.weight > carry_limit:
        ...
```

**Many small attribute writes vs one dict** — clearing three attributes is three DB writes:

```python
# Three writes
obj.db.checkpoint_node = None
obj.db.interface_node = None
obj.db.cluster_id = None

# One write
obj.db.cluster = {"checkpoint": None, "interface": None, "id": None}
```

Grouping related state into a single dict attribute halves or thirds the write count for that operation.

---

## 2. Scripts and Tickers

### Global scripts, not per-object

A single global script that fans out to all affected objects in `at_repeat()` is almost always right. Creating one script per character (e.g. a `StaminaRegenScript` per character) creates N script rows, N ticker registrations, and fires N callbacks per tick.

This codebase does it correctly: `StaminaRegenScript`, `BleedingTickScript`, `MatrixCleanupScript`, and `MatrixConnectionScript` are all global scripts that iterate affected objects in `at_repeat()`.

### `start_delay = True`

Always set this on ticking global scripts. Without it, the first tick fires immediately on every server restart, before everything is fully initialized.

### Idempotent startup

Always guard `create_script` with an existence check. Never call it unconditionally — you will accumulate duplicate persistent scripts across reloads.

```python
# at_server_startstop.py — correct pattern
if not ScriptDB.objects.filter(db_key="stamina_regen").first():
    create_script("typeclasses.scripts.StaminaRegenScript", ...)
```

### Zero-interval storage scripts

Scripts used as pure data stores should have `interval=0`, `repeats=0`, `autodelete=False`. They never tick, they just act as a keyed DB row you can attach attributes to. `PCNoteStorage` and `StaffPendingScript` follow this pattern correctly.

### TickerHandler vs Script

`TICKER_HANDLER` (used in `world/combat/tickers.py`) registers per-pair callbacks and is appropriate for short-lived, self-managing subscriptions with distinct intervals. Scripts carry a persistent DB row and are better for long-lived game systems. Don't use Scripts where TickerHandler subscriptions are cheaper to create and discard.

### Interval sizing

Don't tick at 1s if 60s is fine. Current intervals are reasonable (stamina/bleeding: 10s, matrix connection check: 10s, matrix cleanup: 60s, handset cleanup: 3600s). Avoid sub-second intervals entirely — Evennia is not designed for real-time ticking.

---

## 3. Database Query Optimization

### You cannot filter on attribute values in SQL

Evennia attributes are stored as pickled blobs in a separate `AttributeDB` table. There is no `filter(db__foo=bar)` — that field doesn't exist on the model. Any attribute-value filtering must happen in Python after the queryset is fetched. This is the reason for the comment in `MatrixCleanupScript`:

```python
# Can't filter by attribute, so get all MatrixNodes and check for ephemeral in Python
all_nodes = MatrixNode.objects.all()
ephemeral_nodes = [node for node in all_nodes if getattr(node.db, 'ephemeral', False)]
```

This is unavoidable when you need to filter on an attribute. Mitigate it by keeping the queryset as narrow as possible using fields that *are* indexed in SQL.

### Filter on `db_typeclass_path`

When you need objects of a specific typeclass, always filter on `db_typeclass_path` — it's a real indexed column on `ObjectDB`. `HandsetMessageCleanupScript` does this correctly:

```python
qs = ObjectDB.objects.filter(db_typeclass_path="typeclasses.matrix.devices.handsets.Handset")
```

The broad scan in `stamina_regen_all()` fetches every located object regardless of typeclass:

```python
for obj in ObjectDB.objects.filter(db_location__isnull=False):
    if hasattr(obj, "max_stamina") and hasattr(obj, "db"):
        tick_stamina_regen(obj)
```

At MUSH scale this is probably fine (most located objects are characters anyway), but if the object count grows significantly, filter on typeclass path instead, or maintain a registry of active characters on a global script's `ndb`.

### N+1 pattern in `MatrixCleanupScript`

After fetching ephemeral nodes, the script does individual `.objects.get(pk=...)` calls for each parent device's checkpoint and interface nodes:

```python
checkpoint_node = MatrixNode.objects.get(pk=checkpoint_id)
interface_node = MatrixNode.objects.get(pk=interface_id)
```

This is an N+1 query pattern. At low node counts it doesn't matter. At scale, collect all needed PKs first and batch-fetch:

```python
needed_pks = {checkpoint_id, interface_id, ...}  # collect across all devices
nodes_by_pk = {n.pk: n for n in MatrixNode.objects.filter(pk__in=needed_pks)}
```

### Linear avatar scan

`jack_in.py` and `matrix_accounts.py` scan `MatrixAvatar.objects.all()` to find one avatar by `db.matrix_id` — O(N) per lookup. If avatar counts grow, an index dict on a global script's `ndb` (keyed by `matrix_id`, rebuilt in `at_start()`) reduces this to O(1).

### Cache `search_script()` results

`search_script("key")` is a database query. Don't call it in per-command paths or `at_repeat()` loops. Cache the result at the module level after the first fetch:

```python
_ACCOUNTS_SCRIPT = None

def get_accounts_script():
    global _ACCOUNTS_SCRIPT
    if _ACCOUNTS_SCRIPT is None:
        from evennia import search_script
        results = search_script("matrix_accounts_registry")
        _ACCOUNTS_SCRIPT = results[0] if results else None
    return _ACCOUNTS_SCRIPT
```

Clear the cache in `at_server_start()` or after the script is recreated.

### `select_related` for FK traversal

When iterating objects and accessing their `.location` (a FK on `ObjectDB`), use `select_related` to avoid one extra query per object:

```python
ObjectDB.objects.filter(...).select_related('db_location')
```

---

## 4. Typeclass Loading

Loading an Evennia object from the DB is not free: it queries `ObjectDB`, imports and instantiates the typeclass, and populates the attribute cache on first access. Once loaded, the object lives in Django's internal cache for the process lifetime.

**`lazy_property`** — use this for expensive handlers or subsystems on a typeclass that aren't always needed. `characters.py` already uses it for the `buffs` handler. Import it from `evennia.utils.utils`.

**Don't iterate `room.contents` to type-filter** — `room.contents` returns all objects in the room as a queryset. If you need objects of a specific typeclass in a room, filter at the DB level with `db_typeclass_path` or use tags, rather than loading everything and isinstance-checking in Python.

**Avoid creating/deleting objects in `at_repeat()`** — matrix avatars are created at jack-in time and deleted at jack-out, not inside a script tick. This is correct. Object creation/deletion involves multiple INSERT/DELETE operations; don't do it in high-frequency tick loops.

---

## 5. Caching Strategies

**Global script `ndb`** — the cheapest shared in-process cache. Store lookup dicts (avatar registry by matrix_id, active character registry) on a global script's `ndb`. Rebuild in `at_start()`. Zero-cost reads, survives until the next reload.

**Module-level globals** — for static/constant data: skill lists, prototype dicts, compiled regexes, lookup tables. `world/` already uses this pattern throughout. Don't put mutable game state here.

**Per-object `ndb`** — per-object transient state. Used correctly throughout this codebase for performance state, combat flags, matrix connection tracking. Correct default for "only matters while this object is active."

**Don't cache object references across reloads** — stale references point to the old Python objects. Cache dbrefs or PKs and re-fetch; or accept that caches rebuild on `at_start()`.

**Django cache framework** — Evennia uses `LocMemCache` by default (in-process, reload-volatile). Configuring a Redis backend would enable cross-reload caching via `django.core.cache.cache.get/set`. Not needed at current scale.

---

## 6. Profiling and Measurement

**`evennia --profiler`** — runs cProfile for the server process; writes output on shutdown. Useful for identifying hot functions across the entire session.

**Targeted profiling:**

```python
import cProfile, pstats
pr = cProfile.Profile()
pr.enable()
my_function()
pr.disable()
stats = pstats.Stats(pr).sort_stats('cumulative')
stats.print_stats(20)
```

**Django slow query logging** — add to `settings.py` temporarily:

```python
LOGGING = {
    'version': 1,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {
        'django.db.backends': {'handlers': ['console'], 'level': 'DEBUG'},
    },
}
```

This logs every SQL query. Very verbose — use it to pinpoint a specific problem, then remove it.

**In-game query counting** — in an `@py` block with `DEBUG = True` in settings:

```python
from django.db import connection; connection.queries  # list of all queries so far
```

**What to watch for:**
- Scripts with short intervals and many unconditional `db` writes
- `.objects.all()` without typeclass filtering in `at_repeat()`
- Attribute reads inside loops (check for `obj.db.*` inside `for` loops)
- `search_script()` called in per-command paths

---

## 7. Common Anti-Patterns

1. **Attribute reads inside loops without a local cache** — `obj.db.foo` in every iteration. Assign once before the loop.

2. **Scanning `.objects.all()` to find one object by attribute value** — O(N) per call. Build an index on a global script's `ndb` if this is in a hot path.

3. **Per-object scripts for game-wide systems** — one script per character = N rows + N tickers. Always fan out from a single global script.

4. **Unconditional `db` writes** — write only if the value changed. `HandsetMessageCleanupScript` checks `if kept != texts` before writing; do the same anywhere you're updating a collection that might not have changed.

5. **Many small attribute writes that could be one dict write** — clearing three fields is three DB rows updated. Group related state.

6. **`search_script()` in hot paths** — it's a DB query. Cache the result module-level.

7. **Unbounded collections in a single attribute** — attribute values are pickled; the entire list is deserialized on every read. Keep collections bounded (e.g., handset message cleanup prunes to 24 hours). For anything that could grow without bound, consider chunking or pruning on write rather than only on a cleanup timer.

---

## 8. File and Media Storage

**IC text content (descriptions, messages, notes, documents, logs)** — store in `db` attributes. This is what the attribute system is designed for. At MUSH scale, SQLite handles this easily; the database is currently under 1 MB with room to grow into the gigabytes before performance becomes a concern.

**Binary files (actual images, audio, downloadable files)** — do not pickle binary blobs into `AttributeDB`. Store the file on disk (Django's `MEDIA_ROOT` / `FileField` pattern) and keep only the path or filename in a `db` attribute.

**Prototype/template data** — belongs in Python module files registered under `PROTOTYPE_MODULES` in `settings.py`. Already done correctly in this project. Don't store prototype dicts in script `db` attributes — they can't be version-controlled or linted.

**Editor/upload buffers** — if buffering multi-step input (e.g. an in-game text editor session), use `ndb` to hold the buffer during the session, then flush to `db` (or disk) on commit.
