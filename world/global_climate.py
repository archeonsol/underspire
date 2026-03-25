"""
Global climate: staff-set weather and time-of-day, with per-district ambient prose
for street room descriptions (see typeclasses.rooms.Room street mode).

Time-of-day defaults to real UTC (see utc_time_phase); staff can switch to a fixed
phase with @climate time <phase> or re-enable UTC with @climate time auto.

Storage: persistent Script key GLOBAL_CLIMATE_KEY (typeclasses.scripts.GlobalClimateScript).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    import arrow as _arrow
    _ARROW_AVAILABLE = True
except ImportError:
    _ARROW_AVAILABLE = False

# Must match GlobalClimateScript.key / at_server_start
GLOBAL_CLIMATE_KEY = "global_climate"

WEATHERS = ("rain", "sun", "fog", "snow")
TIMES = ("dusk", "night", "morning", "afternoon", "evening")
DISTRICTS = ("slums", "guild", "bourgeois", "elite")


def utc_time_phase(dt: Optional[datetime] = None) -> str:
    """
    Map real UTC clock time to a narrative phase (same keys as TIMES).

    Bands (UTC hour):
      night 22–05, morning 06–11, afternoon 12–16, dusk 17–19, evening 20–21
    """
    if dt is None:
        if _ARROW_AVAILABLE:
            dt = _arrow.utcnow().datetime
        else:
            dt = datetime.now(timezone.utc)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    h = dt.hour
    if 6 <= h <= 11:
        return "morning"
    if 12 <= h <= 16:
        return "afternoon"
    if 17 <= h <= 19:
        return "dusk"
    if 20 <= h <= 22:
        return "evening"
    return "night"


def _get_script():
    from evennia import search_script

    found = search_script(GLOBAL_CLIMATE_KEY)
    return found[0] if found else None


def normalize_district_key(city_level: Any) -> str:
    """Map room db.city_level (or similar) to a climate district key."""
    if not city_level:
        return "slums"
    c = str(city_level).strip().lower()
    if c in ("shaft", "air"):
        return "slums"
    if c in DISTRICTS:
        return c
    return "slums"


def get_global_weather() -> str:
    """Active global weather key (rain, sun, fog, snow)."""
    scr = _get_script()
    if not scr:
        return "fog"
    w = getattr(scr.db, "weather", None) or "fog"
    return w if w in WEATHERS else "fog"


def get_time_auto_utc() -> bool:
    """When True (default), time-of-day follows real UTC via utc_time_phase()."""
    scr = _get_script()
    if not scr:
        return True
    return getattr(scr.db, "time_auto_utc", True)


def get_global_time_of_day() -> str:
    """Active global time-of-day key: live UTC phase when auto, else stored manual value."""
    scr = _get_script()
    if not scr:
        return utc_time_phase()
    if getattr(scr.db, "time_auto_utc", True):
        return utc_time_phase()
    t = getattr(scr.db, "time_of_day", None) or "morning"
    return t if t in TIMES else "morning"


def set_global_weather(weather: str) -> bool:
    scr = _get_script()
    if not scr:
        return False
    w = str(weather).strip().lower()
    if w not in WEATHERS:
        raise ValueError("invalid weather")
    scr.db.weather = w
    return True


def set_global_time_of_day(time_of_day: str) -> bool:
    """Set a fixed narrative time and disable UTC automation."""
    scr = _get_script()
    if not scr:
        return False
    t = str(time_of_day).strip().lower()
    if t not in TIMES:
        raise ValueError("invalid time")
    scr.db.time_of_day = t
    scr.db.time_auto_utc = False
    return True


def set_time_auto_utc(enabled: bool) -> bool:
    """
    Enable or disable UTC-driven time. When enabling, refreshes db.time_of_day snapshot.
    When disabling, freezes db.time_of_day to the current UTC phase.
    """
    scr = _get_script()
    if not scr:
        return False
    if enabled:
        scr.db.time_auto_utc = True
        scr.db.time_of_day = utc_time_phase()
    else:
        scr.db.time_of_day = utc_time_phase()
        scr.db.time_auto_utc = False
    return True


def _override_key(district: str, weather: str, time_of_day: str) -> str:
    return f"{district}:{weather}:{time_of_day}"


# First sentence of default ambient lines: one narrative opening per (district, weather).
# Staff line_overrides still replace the full composed line when set.
_WEATHER_OPEN_BY_DISTRICT: Dict[str, Dict[str, str]] = {
    "slums": {
        "rain": (
            "Acid rain hisses against rust and tarp, etching pale trails in the grime "
            "and leaving the gutters to run faintly luminous"
        ),
        "sun": (
            "Harsh light cuts through smog in dirty blades, baking the concrete "
            "until the air tastes of hot metal and old sweat"
        ),
        "fog": (
            "Low chemical fog clings to the alley mouths, sour on the tongue "
            "and thick enough to muffle footsteps and hope alike"
        ),
        "snow": (
            "Grey snow slumps from a bruised sky, mixing with ash and oil "
            "until the drifts look more like slag than weather"
        ),
    },
    "guild": {
        "rain": (
            "Rain drums on corrugated roofs and hisses into runoff troughs, "
            "steam rising where hot spill meets cold steel on the shop floors"
        ),
        "sun": (
            "Sun hammers the yards and loading bays, glare ricocheting off cranes "
            "and bare alloy until every edge looks sharp enough to cut"
        ),
        "fog": (
            "A stew of exhaust, coolant mist, and heat hangs over the district, "
            "turning stacks and gantries into looming silhouettes"
        ),
        "snow": (
            "Snow comes down dirty, catching in chain-link and melt-pits, "
            "already grey where it touches grease and grit near the freight lines"
        ),
    },
    "bourgeois": {
        "rain": (
            "Rain runs down glass fronts and arcade canopies, funneling into grates "
            "while shoppers move in a dry hush beneath"
        ),
        "sun": (
            "Sun pools on polished walkways and display glass, warm but tempered, "
            "the kind of light money pays to stand in"
        ),
        "fog": (
            "Soft fog beads on windows and blurs the far towers to pastel, "
            "as if the city agreed to look gentler from this height"
        ),
        "snow": (
            "Snow falls light and almost pretty here, clinging to planters and railings "
            "before crews sweep it away with efficient disinterest"
        ),
    },
    "elite": {
        "rain": (
            "Rain traces the climate glass in thin rivers; beyond it, the lower city "
            "vanishes into sheets of grey while up here the air stays thin and correct"
        ),
        "sun": (
            "Filtered sun spills across terraces and private gardens, bright enough to warm skin "
            "without admitting whatever burns below the barrier"
        ),
        "fog": (
            "Fog fills the canyons far beneath the spires, a soft tide of grey "
            "that never quite climbs high enough to touch the balconies"
        ),
        "snow": (
            "Snow drifts past in veils, caught by fields and vents before it can smear the views; "
            "from here it looks almost like weather belongs to someone else"
        ),
    },
}


def _compose_default_line(district: str, weather: str, time_of_day: str) -> str:
    """
    Template-based ambient line (plain text, no color codes). Staff can override per cell on the script.
    """
    # Short district anchors (second sentence)
    place = {
        "slums": "the cramped streets and leaking neon",
        "guild": "foundries and loading bays",
        "bourgeois": "clean arcades and polished glass",
        "elite": "high balconies and filtered air",
    }.get(district, "the streets")

    dist_table = _WEATHER_OPEN_BY_DISTRICT.get(district) or _WEATHER_OPEN_BY_DISTRICT["slums"]
    w_open = dist_table.get(weather, "The air hangs thick and uncertain")

    t_close = {
        "dusk": "dusk bleeds in at the edges of the sky, and the first false stars are only LEDs",
        "night": "night clamps down; shadows pool where the lamps do not reach",
        "morning": "morning comes grey and reluctant, the way it always does here",
        "afternoon": "afternoon heat shimmers off metal, thick enough to taste",
        "evening": "evening brings a slow exhale, commuters and drifters trading places in the flow",
    }.get(time_of_day, "time slips past in the city's rhythm")

    # Two clear sentences: weather/opening, then district + time beat (avoid "unrealOver").
    first = w_open.rstrip(".")
    return f"{first}. Over {place}, {t_close}."


def get_ambient_weather_line(district_key: Optional[str] = None) -> str:
    """
    Full ambient paragraph for the current global weather/time and given district.
    Returns plain text (caller applies |w in room display).
    """
    dist = normalize_district_key(district_key)
    weather = get_global_weather()
    tod = get_global_time_of_day()
    key = _override_key(dist, weather, tod)

    scr = _get_script()
    overrides: Dict[str, str] = {}
    if scr:
        raw = getattr(scr.db, "line_overrides", None)
        if isinstance(raw, dict):
            overrides = raw

    if key in overrides and (overrides[key] or "").strip():
        return str(overrides[key]).strip()

    return _compose_default_line(dist, weather, tod)


def get_ambient_weather_line_for_room(room: Any) -> str:
    """Resolve district from a room's db.city_level (CityRoom and subclasses)."""
    if room is None:
        return get_ambient_weather_line("slums")
    lvl = getattr(getattr(room, "db", None), "city_level", None)
    return get_ambient_weather_line(lvl)


def set_line_override(district: str, weather: str, time_of_day: str, text: str) -> str:
    """Staff: set custom plain-text line for one matrix cell. Returns the override key."""
    d = normalize_district_key(district)
    w = str(weather).strip().lower()
    t = str(time_of_day).strip().lower()
    if w not in WEATHERS or t not in TIMES:
        raise ValueError("invalid weather or time")
    scr = _get_script()
    if not scr:
        raise RuntimeError("global climate script missing")
    if not isinstance(getattr(scr.db, "line_overrides", None), dict):
        scr.db.line_overrides = {}
    key = _override_key(d, w, t)
    scr.db.line_overrides[key] = (text or "").strip()
    return key


def clear_line_override(district: str, weather: str, time_of_day: str) -> None:
    d = normalize_district_key(district)
    w = str(weather).strip().lower()
    t = str(time_of_day).strip().lower()
    key = _override_key(d, w, t)
    scr = _get_script()
    if not scr or not isinstance(getattr(scr.db, "line_overrides", None), dict):
        return
    overrides: Dict = dict(scr.db.line_overrides)
    overrides.pop(key, None)
    scr.db.line_overrides = overrides
