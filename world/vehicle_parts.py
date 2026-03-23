"""
Vehicle parts: per-class schemas (ground / motorcycle / aerial), condition 0-100, repairs,
stall/start/drive logic, evaluate (mechanic inspection), performance aggregation, fuel, wear, heat.
"""
from __future__ import annotations

import random
import time
from typing import Any

# --- Surface / mods: off-road-capable tire variant ids ---
OFFROAD_TIRE_TYPE_IDS = frozenset({"all_terrain", "mud"})

# Room tag: workshop (category matches other builder room tags)
GARAGE_TAG = "garage"
GARAGE_TAG_CATEGORY = "room_type"


def is_garage_room(room) -> bool:
    """True if room is tagged as a garage (repair / swap / paint / customize)."""
    if not room or not hasattr(room, "tags"):
        return False
    try:
        return bool(room.tags.has(GARAGE_TAG, category=GARAGE_TAG_CATEGORY))
    except Exception:
        return False


def is_fuel_station_room(room) -> bool:
    if not room or not hasattr(room, "tags"):
        return False
    try:
        return bool(room.tags.has("fuel_station", category=GARAGE_TAG_CATEGORY))
    except Exception:
        try:
            return bool(room.tags.has("fuel_station"))
        except Exception:
            return False


# Ordered schemas: vehicle_type -> list of (part_id, display_name)
PART_SCHEMAS: dict[str, list[tuple[str, str]]] = {
    "ground": [
        ("engine", "Engine"),
        ("transmission", "Transmission"),
        ("brakes", "Brakes"),
        ("suspension", "Suspension"),
        ("tires", "Tires"),
        ("battery", "Battery"),
        ("fuel_pump", "Fuel pump"),
        ("radiator", "Radiator"),
        ("wiring", "Wiring"),
        ("security", "Security system"),
        ("armor", "Armor"),
    ],
    "motorcycle": [
        ("engine", "Engine"),
        ("chain_drive", "Chain drive"),
        ("brakes", "Brakes"),
        ("forks", "Forks"),
        ("tires", "Tires"),
        ("battery", "Battery"),
        ("fuel_pump", "Fuel pump"),
        ("oil_cooler", "Oil cooler"),
        ("wiring", "Wiring"),
        ("security", "Security system"),
        ("armor", "Armor"),
    ],
    "aerial": [
        ("turbines", "Turbines"),
        ("thrust_nozzles", "Thrust nozzles"),
        ("stabilizers", "Stabilizers"),
        ("airframe", "Airframe"),
        ("landing_gear", "Landing gear"),
        ("avionics", "Avionics"),
        ("coolant", "Coolant system"),
        ("fuel_injectors", "Fuel injectors"),
        ("wiring", "Wiring"),
        ("security", "Security system"),
        ("armor", "Armor"),
    ],
}

# Semantic legacy keys -> canonical part id per vehicle class (admin / old tools)
LEGACY_PART_MAP: dict[str, dict[str, str]] = {
    "engine": {"ground": "engine", "motorcycle": "engine", "aerial": "turbines"},
    "transmission": {"ground": "transmission", "motorcycle": "chain_drive", "aerial": "thrust_nozzles"},
    "brakes": {"ground": "brakes", "motorcycle": "brakes", "aerial": "stabilizers"},
    "suspension": {"ground": "suspension", "motorcycle": "forks", "aerial": "airframe"},
    "tires": {"ground": "tires", "motorcycle": "tires", "aerial": "landing_gear"},
    "battery": {"ground": "battery", "motorcycle": "battery", "aerial": "avionics"},
    "fuel_system": {"ground": "fuel_pump", "motorcycle": "fuel_pump", "aerial": "fuel_injectors"},
    "cooling_system": {"ground": "radiator", "motorcycle": "oil_cooler", "aerial": "coolant"},
    "electrical": {"ground": "wiring", "motorcycle": "wiring", "aerial": "wiring"},
}

# Direct old persisted part ids -> new id (per vehicle class)
_OLD_PART_ID_REMAP: dict[str, dict[str, str]] = {
    "ground": {
        "powerplant": "engine",
        "drivetrain": "transmission",
        "braking": "brakes",
        "chassis": "suspension",
        "cell": "battery",
        "fuel_delivery": "fuel_pump",
        "thermal": "radiator",
        "bus": "wiring",
    },
    "motorcycle": {
        "mill": "engine",
        "chaincase": "chain_drive",
        "rubber": "tires",
        "cell": "battery",
        "injectors": "fuel_pump",
        "oil_loop": "oil_cooler",
        "harness": "wiring",
    },
    "aerial": {
        "lift_core": "turbines",
        "vectoring": "thrust_nozzles",
        "attitude": "stabilizers",
        "hull_stress": "airframe",
        "avionics_stack": "avionics",
        "reactor_coolant": "coolant",
        "nozzle_manifold": "fuel_injectors",
        "bus": "wiring",
    },
}

VEHICLE_PART_IDS: list[str] = sorted({pid for pairs in PART_SCHEMAS.values() for pid, _ in pairs})

PART_DISPLAY_NAMES: dict[str, str] = {
    pid: title for pairs in PART_SCHEMAS.values() for pid, title in pairs
}


def _canonical_part_id(vehicle, part_key: str) -> str | None:
    """Map a raw db key (old id or semantic key) to current schema part id."""
    vt = get_vehicle_type(vehicle)
    schema_ids = [pid for pid, _ in PART_SCHEMAS.get(vt) or PART_SCHEMAS["ground"]]
    if part_key in schema_ids:
        return part_key
    if part_key in LEGACY_PART_MAP:
        return LEGACY_PART_MAP[part_key].get(vt)
    remap = _OLD_PART_ID_REMAP.get(vt) or {}
    return remap.get(part_key)


def get_vehicle_type(vehicle) -> str:
    return getattr(vehicle.db, "vehicle_type", None) or "ground"


def get_part_ids(vehicle) -> list[str]:
    vt = get_vehicle_type(vehicle)
    schema = PART_SCHEMAS.get(vt) or PART_SCHEMAS["ground"]
    return [pid for pid, _ in schema]


def get_part_display_name(part_id: str) -> str:
    return PART_DISPLAY_NAMES.get(part_id, part_id.replace("_", " ").title())


def get_engine_part_id(vehicle) -> str:
    vt = get_vehicle_type(vehicle)
    if vt == "aerial":
        return "turbines"
    return "engine"


def get_tire_part_id(vehicle) -> str | None:
    vt = get_vehicle_type(vehicle)
    if vt in ("ground", "motorcycle"):
        return "tires"
    return None


def get_fuel_part_id(vehicle) -> str:
    vt = get_vehicle_type(vehicle)
    if vt == "aerial":
        return "fuel_injectors"
    return "fuel_pump"


def get_cool_part_id(vehicle) -> str:
    vt = get_vehicle_type(vehicle)
    if vt == "motorcycle":
        return "oil_cooler"
    if vt == "aerial":
        return "coolant"
    return "radiator"


def tires_ok_for_offroad(vehicle) -> bool:
    vt = get_vehicle_type(vehicle)
    if vt == "aerial":
        return True
    tid = get_tire_part_id(vehicle)
    if not tid:
        return False
    info = get_part_type_info(vehicle, tid)
    if info.get("offroad"):
        return True
    tid_type = get_part_type_id(vehicle, tid)
    return tid_type in OFFROAD_TIRE_TYPE_IDS


# --- Part type options (stats used by performance aggregation) ---
PART_TYPE_OPTIONS: dict[str, list[dict[str, Any]]] = {
    "engine": [
        {
            "id": "stock",
            "name": "Salvage-yard block",
            "performance": 1.0,
            "top_speed_mod": 0,
            "accel_mod": 0.0,
            "fuel_rate": 1.0,
            "description": "Pulled from a wreck. Runs. Don't ask how.",
        },
        {
            "id": "rebuilt",
            "name": "Rebuilt standard",
            "performance": 1.1,
            "top_speed_mod": 5,
            "accel_mod": 0.1,
            "fuel_rate": 1.1,
            "description": "Same block, new internals. Reliable.",
        },
        {
            "id": "performance",
            "name": "Vulcani performance block",
            "performance": 1.3,
            "top_speed_mod": 15,
            "accel_mod": 0.25,
            "fuel_rate": 1.4,
            "description": "Licensed Vulcani build. More power, more fuel, more maintenance.",
        },
        {
            "id": "racing",
            "name": "Vulcani racing block",
            "performance": 1.5,
            "top_speed_mod": 25,
            "accel_mod": 0.4,
            "fuel_rate": 1.8,
            "description": "Competition spec. Fragile. Fast. Expensive to keep running.",
        },
    ],
    "turbines": [
        {
            "id": "stock",
            "name": "Stock lift turbines",
            "performance": 1.0,
            "top_speed_mod": 0,
            "accel_mod": 0.0,
            "fuel_rate": 1.0,
            "description": "Baseline turbines.",
        },
        {
            "id": "rebuilt",
            "name": "Rebuilt turbine pack",
            "performance": 1.1,
            "top_speed_mod": 5,
            "accel_mod": 0.1,
            "fuel_rate": 1.1,
            "description": "Refurbished cores.",
        },
        {
            "id": "performance",
            "name": "Vulcani performance turbines",
            "performance": 1.3,
            "top_speed_mod": 15,
            "accel_mod": 0.25,
            "fuel_rate": 1.4,
            "description": "More thrust, more heat, more fuel.",
        },
        {
            "id": "racing",
            "name": "Vulcani racing turbines",
            "performance": 1.5,
            "top_speed_mod": 25,
            "accel_mod": 0.4,
            "fuel_rate": 1.8,
            "description": "Competition spec.",
        },
    ],
    "transmission": [
        {"id": "stock", "name": "Automatic", "performance": 1.0, "shift_speed": 0.0, "description": "Slush box. Works."},
        {"id": "manual_5", "name": "5-speed manual", "performance": 1.1, "shift_speed": 0.1, "description": "Five gears. More control."},
        {"id": "manual_6", "name": "6-speed manual", "performance": 1.2, "shift_speed": 0.2, "description": "Six gears. Tighter ratios."},
        {"id": "sequential", "name": "Vulcani sequential", "performance": 1.35, "shift_speed": 0.35, "description": "Paddle shift. Race-grade."},
    ],
    "thrust_nozzles": [
        {"id": "stock", "name": "Stock nozzle routing", "performance": 1.0, "shift_speed": 0.0, "description": "Baseline thrust paths."},
        {"id": "manual_5", "name": "5-port vectoring", "performance": 1.1, "shift_speed": 0.1, "description": "Sharper thrust angles."},
        {"id": "manual_6", "name": "6-port vectoring", "performance": 1.2, "shift_speed": 0.2, "description": "Fine-grained control."},
        {"id": "sequential", "name": "Vulcani rapid vectoring", "performance": 1.35, "shift_speed": 0.35, "description": "Aggressive routing."},
    ],
    "chain_drive": [
        {"id": "stock", "name": "Stock chain drive", "performance": 1.0, "shift_speed": 0.0, "description": "Factory gearing."},
        {"id": "manual_5", "name": "5-speed cassette", "performance": 1.1, "shift_speed": 0.1, "description": "Five-speed box."},
        {"id": "manual_6", "name": "6-speed cassette", "performance": 1.2, "shift_speed": 0.2, "description": "Six-speed; sharper shifts."},
        {"id": "sequential", "name": "Vulcani quick-shift", "performance": 1.35, "shift_speed": 0.35, "description": "Race cassette."},
    ],
    "brakes": [
        {"id": "stock", "name": "Stock drums", "performance": 1.0, "stopping_mod": 0.0, "description": "They stop you. Eventually."},
        {"id": "disc", "name": "Disc conversion", "performance": 1.1, "stopping_mod": 0.1, "description": "Discs all round."},
        {"id": "performance", "name": "Vulcani performance kit", "performance": 1.25, "stopping_mod": 0.25, "description": "Big rotors, braided lines."},
    ],
    "stabilizers": [
        {"id": "stock", "name": "Stock RCS", "performance": 1.0, "stopping_mod": 0.0, "description": "Baseline attitude jets."},
        {"id": "disc", "name": "Upgraded RCS", "performance": 1.1, "stopping_mod": 0.1, "description": "Faster correction."},
        {"id": "performance", "name": "Vulcani stabilizer kit", "performance": 1.25, "stopping_mod": 0.25, "description": "Aggressive attitude control."},
    ],
    "suspension": [
        {"id": "stock", "name": "Factory springs", "performance": 1.0, "handling_mod": 0.0, "description": "Soft. Comfortable."},
        {"id": "sport", "name": "Lowered sport kit", "performance": 1.15, "handling_mod": 0.15, "description": "Stiffer. Corners better."},
        {"id": "coilover", "name": "Adjustable coilovers", "performance": 1.25, "handling_mod": 0.25, "description": "Fully adjustable."},
    ],
    "forks": [
        {"id": "stock", "name": "Stock forks", "performance": 1.0, "handling_mod": 0.0, "description": "Factory front end."},
        {"id": "sport", "name": "Sport cartridge forks", "performance": 1.15, "handling_mod": 0.15, "description": "Stiffer, more feedback."},
        {"id": "coilover", "name": "Racing forks", "performance": 1.25, "handling_mod": 0.25, "description": "Track bias."},
    ],
    "airframe": [
        {"id": "stock", "name": "Factory airframe", "performance": 1.0, "handling_mod": 0.0, "description": "Standard structure."},
        {"id": "sport", "name": "Stiffened frame", "performance": 1.15, "handling_mod": 0.15, "description": "Less flex."},
        {"id": "coilover", "name": "Reinforced shell", "performance": 1.25, "handling_mod": 0.25, "description": "Hard-use spec."},
    ],
    "tires": [
        {
            "id": "stock",
            "name": "City rubber",
            "performance": 1.0,
            "grip_mod": 0.0,
            "offroad": False,
            "description": "Standard road tires. Fine on pavement.",
        },
        {
            "id": "sport",
            "name": "Sport compound",
            "performance": 1.1,
            "grip_mod": 0.1,
            "offroad": False,
            "description": "Softer rubber. Wears faster.",
        },
        {
            "id": "all_terrain",
            "name": "All-terrain",
            "performance": 1.05,
            "grip_mod": 0.05,
            "offroad": True,
            "description": "Knobby tread. Jack of all trades.",
        },
        {
            "id": "mud",
            "name": "Mud treads",
            "performance": 1.0,
            "grip_mod": -0.05,
            "offroad": True,
            "description": "Deep lugs. Terrible on pavement.",
        },
    ],
    "landing_gear": [
        {"id": "stock", "name": "Stock skids", "performance": 1.0, "grip_mod": 0.0, "offroad": True, "description": "Baseline touchdown gear."},
        {"id": "sport", "name": "Rough-field pads", "performance": 1.05, "grip_mod": 0.05, "offroad": True, "description": "Better unimproved landing."},
        {"id": "all_terrain", "name": "Soft-field kit", "performance": 1.05, "grip_mod": 0.05, "offroad": True, "description": "Mud and slush rated."},
        {"id": "mud", "name": "Assault skids", "performance": 1.0, "grip_mod": -0.05, "offroad": True, "description": "Extreme landing bias."},
    ],
    "battery": [
        {"id": "stock", "name": "Factory battery", "performance": 1.0, "start_reliability": 0.0, "stall_resistance": 0.0, "description": "Gets you started."},
        {"id": "rebuilt", "name": "Rebuilt pack", "performance": 1.1, "start_reliability": 0.1, "stall_resistance": 0.05, "description": "Fresh cells."},
        {"id": "performance", "name": "Mythos heavy-duty", "performance": 1.2, "start_reliability": 0.2, "stall_resistance": 0.1, "description": "Cold cranking amps for days."},
    ],
    "avionics": [
        {"id": "stock", "name": "Stock avionics", "performance": 1.0, "start_reliability": 0.0, "stall_resistance": 0.0, "description": "Baseline flight brain."},
        {"id": "rebuilt", "name": "Refurbished stack", "performance": 1.1, "start_reliability": 0.1, "stall_resistance": 0.05, "description": "Redundant buses."},
        {"id": "performance", "name": "Mythos redundant avionics", "performance": 1.2, "start_reliability": 0.2, "stall_resistance": 0.1, "description": "Backup everything."},
    ],
    "fuel_pump": [
        {"id": "stock", "name": "Stock pump", "performance": 1.0, "fuel_efficiency": 1.0, "description": "Factory lines."},
        {"id": "high_flow", "name": "High-flow kit", "performance": 1.1, "fuel_efficiency": 0.95, "description": "More flow; thirstier."},
        {"id": "performance", "name": "Vulcani rail kit", "performance": 1.2, "fuel_efficiency": 0.9, "description": "Racing delivery."},
    ],
    "fuel_injectors": [
        {"id": "stock", "name": "Stock injectors", "performance": 1.0, "fuel_efficiency": 1.0, "description": "Baseline mix."},
        {"id": "high_flow", "name": "High-flow manifold", "performance": 1.1, "fuel_efficiency": 0.95, "description": "Aggressive trim."},
        {"id": "performance", "name": "Vulcani spray kit", "performance": 1.2, "fuel_efficiency": 0.9, "description": "Maximum thrust bias."},
    ],
    "radiator": [
        {"id": "stock", "name": "Stock radiator", "performance": 1.0, "overheat_threshold": 100.0, "description": "Baseline cooling."},
        {"id": "upgraded", "name": "Upgraded loop", "performance": 1.1, "overheat_threshold": 115.0, "description": "Larger core."},
        {"id": "performance", "name": "Vulcani racing radiator", "performance": 1.25, "overheat_threshold": 130.0, "description": "Track cooling."},
    ],
    "coolant": [
        {"id": "stock", "name": "Stock coolant loop", "performance": 1.0, "overheat_threshold": 100.0, "description": "Reactor cooling."},
        {"id": "upgraded", "name": "Upgraded cryo loop", "performance": 1.1, "overheat_threshold": 115.0, "description": "More thermal mass."},
        {"id": "performance", "name": "Mythos cryo manifold", "performance": 1.25, "overheat_threshold": 130.0, "description": "Military surplus cooling."},
    ],
    "oil_cooler": [
        {"id": "stock", "name": "Stock oil cooler", "performance": 1.0, "overheat_threshold": 100.0, "description": "Bike loop."},
        {"id": "upgraded", "name": "Upgraded cooler", "performance": 1.1, "overheat_threshold": 115.0, "description": "Better headroom."},
        {"id": "performance", "name": "Racing oil cooler", "performance": 1.25, "overheat_threshold": 130.0, "description": "Track oil temps."},
    ],
    "wiring": [
        {"id": "stock", "name": "Factory harness", "performance": 1.0, "stall_resistance": 0.0, "description": "Standard electrics."},
        {"id": "upgraded", "name": "Mythos-clean harness", "performance": 1.05, "stall_resistance": 0.08, "description": "Better grounds."},
        {"id": "performance", "name": "Vulcani bus upgrade", "performance": 1.15, "stall_resistance": 0.15, "description": "Alternator and shielding."},
    ],
    "security": [
        {"id": "tier_1", "name": "Thumb scanner", "performance": 1.0, "security_tier": 1, "description": "Basic biometric."},
        {"id": "tier_2", "name": "Palm reader", "performance": 1.0, "security_tier": 2, "description": "Vein patterns."},
        {"id": "tier_3", "name": "Retinal lock", "performance": 1.0, "security_tier": 3, "description": "Guild-grade."},
        {"id": "tier_4", "name": "Multi-biometric array", "performance": 1.0, "security_tier": 4, "description": "Three-factor."},
        {"id": "tier_5", "name": "Inquisitorate biolock", "performance": 1.0, "security_tier": 5, "description": "Don't bother."},
    ],
    "armor": [
        {
            "id": "none",
            "name": "No armor",
            "armor_value": 0,
            "weight_penalty": 0.0,
            "description": "Stock panels. Sheet metal.",
        },
        {
            "id": "light",
            "name": "Light plating",
            "armor_value": 5,
            "weight_penalty": 0.05,
            "description": "Bolted scrap plate on the doors and quarter panels. Stops small-caliber.",
        },
        {
            "id": "medium",
            "name": "Welded plate",
            "armor_value": 12,
            "weight_penalty": 0.12,
            "description": "Heavy steel plate welded to the frame. Slows you down. Keeps you alive.",
        },
        {
            "id": "heavy",
            "name": "Vulcani combat armor",
            "armor_value": 20,
            "weight_penalty": 0.20,
            "description": "Military-spec plating. Ceramic composite over steel. The vehicle handles like a pig. Nobody cares.",
        },
        {
            "id": "reactive",
            "name": "Mythos reactive armor",
            "armor_value": 25,
            "weight_penalty": 0.15,
            "description": "Detonates outward on impact, deflecting penetration. Expensive. Effective. Loud.",
        },
    ],
}


def _ensure_vehicle_parts_migrated(vehicle) -> None:
    """Merge legacy keys into class schema; fill missing slots at 100."""
    if not vehicle or not hasattr(vehicle, "db"):
        return
    ndb = getattr(vehicle, "ndb", None)
    if ndb is not None and getattr(ndb, "_parts_migrated", False):
        return

    vt = get_vehicle_type(vehicle)
    schema_ids = [pid for pid, _ in PART_SCHEMAS.get(vt) or PART_SCHEMAS["ground"]]
    raw = getattr(vehicle.db, "vehicle_parts", None)
    if raw is None:
        raw = {}
    merged: dict[str, int] = {}
    raw_types = getattr(vehicle.db, "vehicle_part_types", None) or {}
    merged_types: dict[str, str] = {}

    def absorb(target_pid: str, cond: int, type_id: str | None):
        cond = max(0, min(100, int(cond)))
        prev = merged.get(target_pid)
        if prev is None or cond > prev:
            merged[target_pid] = cond
        if type_id:
            merged_types[target_pid] = type_id

    for k, v in raw.items():
        target = k if k in schema_ids else _canonical_part_id(vehicle, k)
        if not target:
            if k in LEGACY_PART_MAP:
                target = LEGACY_PART_MAP[k].get(vt)
        if not target:
            continue
        t_val = raw_types.get(k) or raw_types.get(target)
        absorb(target, int(v), t_val)

    for k, v in list(raw_types.items()):
        if k in merged_types:
            continue
        target = k if k in schema_ids else _canonical_part_id(vehicle, k)
        if not target and k in LEGACY_PART_MAP:
            target = LEGACY_PART_MAP[k].get(vt)
        if target and target in schema_ids and target not in merged_types:
            merged_types[target] = v

    for pid in schema_ids:
        if pid not in merged:
            merged[pid] = 100
        if pid not in merged_types:
            merged_types[pid] = "stock"

    for pid in list(merged_types.keys()):
        opts = PART_TYPE_OPTIONS.get(pid, [])
        valid_ids = {t["id"] for t in opts} if opts else {"stock"}
        if merged_types.get(pid) not in valid_ids:
            merged_types[pid] = "stock"

    vehicle.db.vehicle_parts = merged
    vehicle.db.vehicle_part_types = merged_types
    try:
        refresh_vehicle_armor(vehicle)
    except Exception:
        pass
    if ndb is not None:
        ndb._parts_migrated = True


def invalidate_perf_cache(vehicle) -> None:
    ndb = getattr(vehicle, "ndb", None)
    if ndb is not None and hasattr(ndb, "_perf_cache"):
        try:
            delattr(ndb, "_perf_cache")
        except Exception:
            ndb._perf_cache = None


def default_part_types(vehicle=None):
    if vehicle is None:
        return {pid: "stock" for pid, _ in PART_SCHEMAS["ground"]}
    _ensure_vehicle_parts_migrated(vehicle)
    return dict(getattr(vehicle.db, "vehicle_part_types", None) or {})


def default_parts(vehicle=None):
    if vehicle is None:
        return {pid: 100 for pid, _ in PART_SCHEMAS["ground"]}
    _ensure_vehicle_parts_migrated(vehicle)
    return dict(getattr(vehicle.db, "vehicle_parts", None) or {})


def get_part_type_id(vehicle, part_id):
    _ensure_vehicle_parts_migrated(vehicle)
    types = getattr(vehicle.db, "vehicle_part_types", None) or {}
    return types.get(part_id, "stock")


def set_part_type_id(vehicle, part_id, type_id):
    options = PART_TYPE_OPTIONS.get(part_id, [])
    if not any(t["id"] == type_id for t in options):
        return False
    _ensure_vehicle_parts_migrated(vehicle)
    if not vehicle.db.vehicle_part_types:
        vehicle.db.vehicle_part_types = {}
    vehicle.db.vehicle_part_types[part_id] = type_id
    invalidate_perf_cache(vehicle)
    sync_security_tier_from_part(vehicle)
    if part_id == "armor":
        refresh_vehicle_armor(vehicle)
    return True


def sync_security_tier_from_part(vehicle):
    try:
        info = get_part_type_info(vehicle, "security")
        tier = int(info.get("security_tier", 1) or 1)
        vehicle.db.security_tier = max(1, min(5, tier))
    except Exception:
        pass


def refresh_vehicle_armor(vehicle):
    """Set vehicle.db.vehicle_armor from installed armor part type."""
    if not vehicle or not getattr(vehicle, "db", None):
        return
    try:
        info = get_part_type_info(vehicle, "armor")
        vehicle.db.vehicle_armor = int(info.get("armor_value", 0) or 0)
    except Exception:
        vehicle.db.vehicle_armor = int(getattr(vehicle.db, "vehicle_armor", 0) or 0)


def get_part_type_info(vehicle, part_id):
    type_id = get_part_type_id(vehicle, part_id)
    for t in PART_TYPE_OPTIONS.get(part_id, []):
        if t["id"] == type_id:
            return t
    return {"id": "stock", "name": "Stock", "performance": 1.0, "description": "Standard."}


ENGINE_START_MIN = 15
BATTERY_START_MIN = 20
ELECTRICAL_START_MIN = 10
FUEL_SYSTEM_START_MIN = 5

STALL_CHANCE_ENGINE_LOW = 0.25
STALL_CHANCE_FUEL_LOW = 0.15
STALL_CHANCE_ELECTRICAL_LOW = 0.10

DRIVE_PARTS_WEIGHT: dict[str, float] = {
    "engine": 1.5,
    "turbines": 1.5,
    "transmission": 1.2,
    "thrust_nozzles": 1.2,
    "chain_drive": 1.2,
    "brakes": 0.8,
    "stabilizers": 0.8,
    "suspension": 0.5,
    "forks": 0.5,
    "airframe": 0.5,
    "tires": 1.0,
    "landing_gear": 0.4,
}


def _start_slots(vehicle) -> tuple[str, str, str, str]:
    vt = get_vehicle_type(vehicle)
    if vt == "motorcycle":
        return "engine", "fuel_pump", "wiring", "battery"
    if vt == "aerial":
        return "turbines", "fuel_injectors", "wiring", "avionics"
    return "engine", "fuel_pump", "wiring", "battery"


def _stall_slots(vehicle) -> tuple[str, str, str]:
    vt = get_vehicle_type(vehicle)
    if vt == "motorcycle":
        return "engine", "fuel_pump", "wiring"
    if vt == "aerial":
        return "turbines", "fuel_injectors", "wiring"
    return "engine", "fuel_pump", "wiring"


def get_part_condition(vehicle, part_id):
    _ensure_vehicle_parts_migrated(vehicle)
    parts = getattr(vehicle.db, "vehicle_parts", None) or {}
    return max(0, min(100, int(parts.get(part_id, 100))))


def set_part_condition(vehicle, part_id, value):
    _ensure_vehicle_parts_migrated(vehicle)
    parts = vehicle.db.vehicle_parts
    parts[part_id] = max(0, min(100, int(round(value))))
    invalidate_perf_cache(vehicle)


def damage_part(vehicle, part_id, amount):
    c = get_part_condition(vehicle, part_id)
    new_c = max(0, c - amount)
    set_part_condition(vehicle, part_id, new_c)
    return new_c


def repair_part(vehicle, part_id, amount):
    c = get_part_condition(vehicle, part_id)
    new_c = min(100, c + amount)
    set_part_condition(vehicle, part_id, new_c)
    return new_c


def calculate_vehicle_performance(vehicle) -> dict[str, Any]:
    perf: dict[str, Any] = {
        "top_speed": 100,
        "acceleration": 1.0,
        "handling": 1.0,
        "braking_power": 1.0,
        "fuel_efficiency": 1.0,
        "stall_resistance": 0.0,
        "grip": 1.0,
        "reliability": 1.0,
        "shift_speed": 0.0,
        "overheat_threshold": 100.0,
        "start_reliability": 0.0,
    }
    for part_id in get_part_ids(vehicle):
        type_info = get_part_type_info(vehicle, part_id)
        condition = get_part_condition(vehicle, part_id) / 100.0
        perf["top_speed"] += int(type_info.get("top_speed_mod", 0) * condition)
        perf["acceleration"] += float(type_info.get("accel_mod", 0)) * condition
        perf["handling"] += float(type_info.get("handling_mod", 0)) * condition
        perf["braking_power"] += float(type_info.get("stopping_mod", 0)) * condition
        perf["grip"] += float(type_info.get("grip_mod", 0)) * condition
        perf["stall_resistance"] += float(type_info.get("stall_resistance", 0)) * condition
        perf["shift_speed"] += float(type_info.get("shift_speed", 0)) * condition
        perf["start_reliability"] += float(type_info.get("start_reliability", 0)) * condition
        if "fuel_rate" in type_info:
            perf["fuel_efficiency"] *= float(type_info["fuel_rate"])
        if "fuel_efficiency" in type_info:
            perf["fuel_efficiency"] *= float(type_info["fuel_efficiency"])
        ot = type_info.get("overheat_threshold")
        if ot is not None:
            perf["overheat_threshold"] = max(perf["overheat_threshold"], float(ot) * condition)
        if condition < 0.5:
            perf["reliability"] *= 0.5 + condition
    # Armor mass slows acceleration and top speed
    try:
        ainfo = get_part_type_info(vehicle, "armor")
        weight_pen = float(ainfo.get("weight_penalty", 0) or 0)
    except Exception:
        weight_pen = 0.0
    if weight_pen > 0:
        perf["acceleration"] *= 1.0 - weight_pen
        perf["top_speed"] = int(perf["top_speed"] * (1.0 - weight_pen))
    ndb = getattr(vehicle, "ndb", None)
    if ndb is not None:
        ndb._perf_cache = perf
    return perf


def get_vehicle_performance(vehicle) -> dict[str, Any]:
    ndb = getattr(vehicle, "ndb", None)
    if ndb is not None:
        c = getattr(ndb, "_perf_cache", None)
        if c:
            return c
    return calculate_vehicle_performance(vehicle)


def drive_check_modifier(vehicle, maneuver: str = "normal") -> int:
    perf = get_vehicle_performance(vehicle)
    if maneuver == "normal":
        return int((perf["reliability"] - 1.0) * 20)
    if maneuver == "speed":
        return int((perf["acceleration"] - 1.0) * 15 + (perf["top_speed"] - 100) * 0.2)
    if maneuver == "corner":
        return int((perf["handling"] - 1.0) * 20 + (perf["grip"] - 1.0) * 10 + perf["shift_speed"] * 10)
    if maneuver == "stop":
        return int((perf["braking_power"] - 1.0) * 25)
    if maneuver == "offroad":
        return int((perf["grip"] - 1.0) * 15 + (perf["handling"] - 1.0) * 10)
    return 0


def drive_failure_modifier(vehicle):
    """Back-compat: higher was harder; map from reliability penalty."""
    perf = get_vehicle_performance(vehicle)
    return max(0.0, (1.0 - perf["reliability"]) * 25.0)


def can_start_engine(vehicle):
    eng, fuel, elec, batt = _start_slots(vehicle)
    vt = get_vehicle_type(vehicle)
    e = get_part_condition(vehicle, eng)
    f = get_part_condition(vehicle, fuel)
    el = get_part_condition(vehicle, elec)
    b = get_part_condition(vehicle, batt)
    perf = get_vehicle_performance(vehicle)
    start_bonus = perf.get("start_reliability", 0) * 20
    if e < ENGINE_START_MIN:
        return False, "The engine is too damaged to turn over."
    if b < BATTERY_START_MIN - start_bonus / 10:
        return False, "The battery doesn't have enough juice to crank."
    if el < ELECTRICAL_START_MIN:
        return False, "The wiring won't energize the starter."
    if f < FUEL_SYSTEM_START_MIN:
        return False, "No fuel reaching the engine."
    fuel_level = float(getattr(vehicle.db, "fuel_level", 100) or 0)
    if fuel_level <= 0:
        return False, "The tank is empty."
    return True, ""


def roll_stall_chance(vehicle):
    if not getattr(vehicle.db, "engine_running", False):
        return False
    perf = get_vehicle_performance(vehicle)
    resist = perf.get("stall_resistance", 0)
    roll = random.random()
    e_id, f_id, el_id = _stall_slots(vehicle)
    e = get_part_condition(vehicle, e_id)
    f = get_part_condition(vehicle, f_id)
    el = get_part_condition(vehicle, el_id)
    stall_e = STALL_CHANCE_ENGINE_LOW * (1 - e / 100.0) if e < 60 else 0
    stall_f = STALL_CHANCE_FUEL_LOW * (1 - f / 100.0) if f < 50 else 0
    stall_el = STALL_CHANCE_ELECTRICAL_LOW * (1 - el / 100.0) if el < 50 else 0
    total = max(0.0, stall_e + stall_f + stall_el - resist)
    return roll < total


# --- Fuel ---
def consume_fuel(vehicle, rooms_driven: int = 1, maneuver: str = "normal") -> tuple[bool, float]:
    from typeclasses.vehicles import _msg_all_vehicle_occupants

    perf = get_vehicle_performance(vehicle)
    base = 1.0
    if maneuver == "speed":
        base = 1.5
    elif maneuver == "offroad":
        base = 2.0
    consumption = base * float(perf.get("fuel_efficiency", 1.0)) * rooms_driven
    cap = float(getattr(vehicle.db, "fuel_capacity", 100) or 100)
    current = float(getattr(vehicle.db, "fuel_level", cap) or 0)
    new_level = max(0.0, current - consumption)
    vehicle.db.fuel_level = new_level
    invalidate_perf_cache(vehicle)
    if new_level <= 0:
        try:
            vehicle.stop_engine()
        except Exception:
            vehicle.db.engine_running = False
        _msg_all_vehicle_occupants(vehicle, "|rThe engine sputters. Out of fuel.|n")
        return False, 0.0
    if new_level < cap * 0.15:
        _msg_all_vehicle_occupants(vehicle, "|y[FUEL] Low fuel warning.|n")
    return True, new_level


# --- Wear ---
WEAR_RATES: dict[str, float] = {
    "engine": 2.0,
    "turbines": 2.0,
    "transmission": 1.5,
    "thrust_nozzles": 1.5,
    "chain_drive": 1.5,
    "brakes": 3.0,
    "stabilizers": 2.0,
    "suspension": 1.0,
    "forks": 1.0,
    "airframe": 0.8,
    "tires": 4.0,
    "landing_gear": 3.0,
    "battery": 0.5,
    "avionics": 0.5,
    "fuel_pump": 1.0,
    "fuel_injectors": 1.0,
    "radiator": 0.8,
    "coolant": 0.8,
    "oil_cooler": 0.8,
    "wiring": 0.3,
    "security": 0.2,
}


def _get_wear_rate(part_id: str) -> float:
    return WEAR_RATES.get(part_id, 1.0)


def apply_drive_wear(vehicle, rooms: int = 1):
    for part_id in get_part_ids(vehicle):
        rate = _get_wear_rate(part_id)
        if rate <= 0:
            continue
        wear = rate * rooms / 100.0
        type_info = get_part_type_info(vehicle, part_id)
        perf_mult = float(type_info.get("performance", 1.0))
        if perf_mult > 1.0:
            wear *= 1.0 + (perf_mult - 1.0) * 0.5
        current = get_part_condition(vehicle, part_id)
        new_cond = max(0, current - wear)
        set_part_condition(vehicle, part_id, new_cond)
    invalidate_perf_cache(vehicle)


CONDITION_WARNINGS = {
    50: "|y[VEHICLE] {part_name} is getting worn. Consider maintenance.|n",
    25: "|R[VEHICLE] {part_name} is in bad shape. Performance affected.|n",
    10: "|R[VEHICLE] WARNING: {part_name} is critical. Failure imminent.|n",
}


def _maybe_warn_part_wear(vehicle, part_id: str, old_c: float, new_c: float, driver):
    if not driver or not hasattr(driver, "msg"):
        return
    for threshold in (50, 25, 10):
        if old_c >= threshold > new_c:
            name = get_part_display_name(part_id)
            driver.msg(CONDITION_WARNINGS[threshold].format(part_name=name))
            break


def apply_drive_wear_with_warnings(vehicle, rooms: int, driver):
    for part_id in get_part_ids(vehicle):
        rate = _get_wear_rate(part_id)
        if rate <= 0:
            continue
        wear = rate * rooms / 100.0
        type_info = get_part_type_info(vehicle, part_id)
        perf_mult = float(type_info.get("performance", 1.0))
        if perf_mult > 1.0:
            wear *= 1.0 + (perf_mult - 1.0) * 0.5
        old_c = float(get_part_condition(vehicle, part_id))
        new_cond = max(0, old_c - wear)
        set_part_condition(vehicle, part_id, new_cond)
        _maybe_warn_part_wear(vehicle, part_id, old_c, new_cond, driver)


# --- Heat ---
def apply_heat(vehicle, rooms: int = 1):
    from typeclasses.vehicles import _msg_all_vehicle_occupants

    rad_id = get_cool_part_id(vehicle)
    eng_id = get_engine_part_id(vehicle)
    rad_condition = get_part_condition(vehicle, rad_id) / 100.0
    rad_type = get_part_type_info(vehicle, rad_id)
    cooling_mult = float(rad_type.get("performance", 1.0)) * rad_condition
    engine_type = get_part_type_info(vehicle, eng_id)
    heat_gen = float(engine_type.get("fuel_rate", 1.0)) * 2.0
    heat_gain = heat_gen * rooms
    heat_loss = cooling_mult * 3.0 * rooms
    current = float(getattr(vehicle.db, "heat_level", 0) or 0)
    new_heat = max(0, current + heat_gain - heat_loss)
    vehicle.db.heat_level = new_heat
    perf = get_vehicle_performance(vehicle)
    threshold = float(perf.get("overheat_threshold", 100) or 100)
    vehicle.db.overheat_threshold = threshold
    if new_heat >= threshold:
        _overheat_event(vehicle)
    elif new_heat >= threshold * 0.8:
        _msg_all_vehicle_occupants(vehicle, "|y[TEMP] Engine running hot. Consider stopping.|n")


def _overheat_event(vehicle):
    from typeclasses.vehicles import _msg_all_vehicle_occupants

    _msg_all_vehicle_occupants(vehicle, "|R[TEMP] OVERHEAT. The engine seizes. Steam everywhere.|n")
    damage_part(vehicle, get_engine_part_id(vehicle), 15)
    damage_part(vehicle, get_cool_part_id(vehicle), 20)
    try:
        vehicle.stop_engine()
    except Exception:
        vehicle.db.engine_running = False
    vehicle.db.heat_level = 80.0


def cool_down_tick_vehicle(vehicle):
    current = float(getattr(vehicle.db, "heat_level", 0) or 0)
    if current <= 0:
        return
    if getattr(vehicle.db, "engine_running", False):
        return
    vehicle.db.heat_level = max(0, current - 5.0)


def _cooldown_chain(vehicle_id: int):
    from evennia.utils import delay
    from evennia.utils.search import search_object

    r = search_object(f"#{vehicle_id}")
    if not r:
        return
    v = r[0]
    cool_down_tick_vehicle(v)
    h = float(getattr(v.db, "heat_level", 0) or 0)
    if h > 0 and not getattr(v.db, "engine_running", False):
        delay(30, _cooldown_chain, vehicle_id)


def schedule_vehicle_cooldown(vehicle):
    from evennia.utils import delay

    delay(30, _cooldown_chain, vehicle.id)


def _vehicle_after_room_transition(vehicle, driver, dest_room, maneuver: str = "normal", rooms: int = 1):
    """Fuel, wear, heat after a successful move."""
    if not getattr(vehicle.db, "engine_running", False):
        return
    consume_fuel(vehicle, rooms_driven=rooms, maneuver=maneuver)
    if driver:
        apply_drive_wear_with_warnings(vehicle, rooms, driver)
    else:
        apply_drive_wear(vehicle, rooms)
    apply_heat(vehicle, rooms)
    # Paint quality decay (~1 per 200 rooms)
    try:
        pq = getattr(vehicle.db, "paint_quality", None)
        if pq is not None and pq > 0:
            decay = rooms / 200.0
            vehicle.db.paint_quality = max(0, float(pq) - decay)
    except Exception:
        pass


def condition_description(condition):
    if condition >= 95:
        return "pristine"
    if condition >= 75:
        return "good"
    if condition >= 50:
        return "fair"
    if condition >= 25:
        return "worn"
    if condition >= 10:
        return "damaged"
    return "critical"


# Minimum seconds until evaluation readout; flavor lines use 2s, 4s, … 2*n — must be > 2 * line_count.
EVALUATE_DURATION_SECONDS = 21
EVALUATE_MECHANICS_MIN_LEVEL = 25

EVALUATE_FLAVOR_MESSAGES: dict[str, list[tuple[str, str]]] = {
    "ground": [
        ("engine", "You pop the hood and trace the engine mounts—seals, leaks, belt tension."),
        ("transmission", "You slide under and check the transmission; linkages and fluid."),
        ("brakes", "You inspect brake lines, pads, and rotors."),
        ("suspension", "You bounce each corner—shocks, springs, bushings."),
        ("tires", "You kneel at each tire, tread and sidewall."),
        ("battery", "You check terminals and the battery tray."),
        ("fuel_pump", "You trace rails from tank to engine; pump, filter, pressure."),
        ("radiator", "You check the radiator, hoses, coolant level."),
        ("wiring", "You pull the panel and scan the harness, fuses, and alternator."),
        ("security", "You test the biometric panel and alarm contacts."),
    ],
    "motorcycle": [
        ("engine", "You listen at idle, then check cases and breathers."),
        ("chain_drive", "You crouch at the chain—tension, seals, sprocket wear."),
        ("brakes", "You trace lines to the calipers; pads, fluid, leaks."),
        ("forks", "You compress the forks and check seals."),
        ("tires", "You inspect tires—tread, sidewall, pressure."),
        ("battery", "You open the tray under the seat."),
        ("fuel_pump", "You trace lines and the pump."),
        ("oil_cooler", "You check oil cooler lines."),
        ("wiring", "You trace the harness—grounds, charging."),
        ("security", "You check the bike's biometric interlock."),
    ],
    "aerial": [
        ("turbines", "You open the inspection hatch; turbine bleed lines."),
        ("thrust_nozzles", "You check thrust nozzles and manifolds."),
        ("stabilizers", "You run diagnostics on the stabilizers."),
        ("airframe", "You walk stress points, seams, paint cracks."),
        ("landing_gear", "You cycle landing gear and inspect pads."),
        ("avionics", "You pull avionics—redundancy lights, buses."),
        ("coolant", "You read coolant pressure and manifold temps."),
        ("fuel_injectors", "You inspect injectors and fuel trims."),
        ("wiring", "You trace the flight harness—grounds, arc marks."),
        ("security", "You test the cockpit biometric suite."),
    ],
}

INSPECT_DURATION_SECONDS = EVALUATE_DURATION_SECONDS
INSPECT_MECHANICS_MIN_LEVEL = EVALUATE_MECHANICS_MIN_LEVEL
INSPECT_FLAVOR_MESSAGES = EVALUATE_FLAVOR_MESSAGES

def _vehicle_evaluate_flavor_callback(caller_id, message):
    from evennia.utils.search import search_object

    try:
        objs = search_object("#%s" % caller_id)
        if objs and hasattr(objs[0], "msg"):
            objs[0].msg("|w  " + message + "|n")
    except Exception:
        pass


def get_evaluation_lines_for_vehicle(vehicle, caller) -> list[str]:
    _ensure_vehicle_parts_migrated(vehicle)
    engine = "|grunning|n" if getattr(vehicle, "engine_running", False) else "|xoff|n"
    lines = [f"|w{vehicle.get_display_name(caller)}|n — Engine: {engine}", ""]
    parts = getattr(vehicle.db, "vehicle_parts", None) or {}
    for part_id in get_part_ids(vehicle):
        cond = max(0, min(100, int(parts.get(part_id, 100))))
        type_info = get_part_type_info(vehicle, part_id)
        slot_name = get_part_display_name(part_id)
        type_name = type_info.get("name", "Stock")
        desc = condition_description(cond)
        lines.append(f"  |w{slot_name}|n — {type_name}: {cond}% ({desc})")
    return lines


def _vehicle_evaluate_final_callback(caller_id, vehicle_id):
    from evennia.utils.search import search_object

    try:
        callers = search_object("#%s" % caller_id)
        vehicles = search_object("#%s" % vehicle_id)
        if not callers or not vehicles:
            return
        caller, vehicle = callers[0], vehicles[0]
        if not hasattr(caller, "msg") or not hasattr(vehicle, "db"):
            return
        lines = get_evaluation_lines_for_vehicle(vehicle, caller)
        caller.msg("\n".join(lines))
    except Exception:
        pass


_vehicle_inspect_flavor_callback = _vehicle_evaluate_flavor_callback
_vehicle_inspect_final_callback = _vehicle_evaluate_final_callback

# --- Repair / swap (tool tiers) ---
REPAIR_CAPS: dict[str, int] = {
    "basic_toolkit": 50,
    "mechanic_toolkit": 80,
    "master_toolkit": 100,
}

REPAIR_FLAVOR: dict[str, list[str]] = {
    "engine": [
        "You crack the valve cover and inspect the internals.",
        "Replacing gaskets. Torquing bolts to spec.",
        "Checking clearances. Adjusting timing.",
    ],
    "turbines": [
        "You open the turbine bay and inspect bleed lines.",
        "Torquing turbine mounts. Checking seals.",
        "Running spool-up diagnostics.",
    ],
    "brakes": [
        "You jack the corner and pull the wheel.",
        "Pads out. Inspecting the rotor face.",
        "New pads in. Bleeding the line.",
    ],
    "tires": [
        "You break the bead and inspect the sidewall.",
        "Patching the inner liner.",
        "Seating the bead. Airing up.",
    ],
    "default": [
        "You set out tools and get to work.",
        "Tracing faults. Replacing what can't be saved.",
        "Torquing to spec. Testing operation.",
    ],
}

SWAP_DIFFICULTY: dict[str, int] = {
    "engine": 35,
    "turbines": 40,
    "transmission": 30,
    "thrust_nozzles": 35,
    "chain_drive": 20,
    "brakes": 15,
    "stabilizers": 30,
    "suspension": 20,
    "forks": 22,
    "airframe": 45,
    "tires": 8,
    "landing_gear": 18,
    "battery": 5,
    "avionics": 38,
    "fuel_pump": 20,
    "fuel_injectors": 25,
    "radiator": 15,
    "coolant": 15,
    "oil_cooler": 12,
    "wiring": 25,
    "security": 28,
}

SWAP_DURATION: dict[str, int] = {
    "engine": 60,
    "turbines": 60,
    "transmission": 45,
    "thrust_nozzles": 45,
    "chain_drive": 30,
    "brakes": 20,
    "stabilizers": 35,
    "suspension": 30,
    "forks": 25,
    "airframe": 55,
    "tires": 15,
    "landing_gear": 20,
    "battery": 10,
    "avionics": 40,
    "fuel_pump": 25,
    "fuel_injectors": 30,
    "radiator": 20,
    "coolant": 20,
    "oil_cooler": 18,
    "wiring": 35,
    "security": 45,
}

PAINT_COLORS: dict[str, dict[str, str]] = {
    "matte_black": {"name": "matte black", "code": "|x", "desc_prefix": "A matte black"},
    "primer_grey": {"name": "primer grey", "code": "|=e", "desc_prefix": "A grey-primered"},
    "rust_red": {"name": "rust red", "code": "|R", "desc_prefix": "A rust-red"},
    "dark_green": {"name": "dark green", "code": "|g", "desc_prefix": "A dark green"},
    "midnight_blue": {"name": "midnight blue", "code": "|b", "desc_prefix": "A midnight blue"},
    "bone_white": {"name": "bone white", "code": "|w", "desc_prefix": "A bone-white"},
    "chrome": {"name": "bare chrome", "code": "|W", "desc_prefix": "A chrome-plated"},
    "burnt_orange": {"name": "burnt orange", "code": "|y", "desc_prefix": "A burnt orange"},
    "flat_olive": {"name": "flat olive drab", "code": "|=f", "desc_prefix": "An olive drab"},
    "faded_gold": {"name": "faded gold", "code": "|Y", "desc_prefix": "A faded gold"},
}


def _repair_tool_tag_from_inventory(caller) -> str | None:
    """Return best repair tool tag on character."""
    order = ("master_toolkit", "mechanic_toolkit", "basic_toolkit")
    for tag in order:
        for obj in caller.contents:
            try:
                if obj.tags.has(tag, category="tool") or obj.tags.has(tag):
                    return tag
            except Exception:
                pass
    return None


def calculate_repair_duration(vehicle, part_id: str, tool_tag: str | None) -> int:
    current = get_part_condition(vehicle, part_id)
    damage = 100 - current
    base = int(10 + damage * 0.5)
    if tool_tag == "basic_toolkit":
        base = int(base * 1.5)
    return max(5, base)
