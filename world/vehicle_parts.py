"""
Vehicle parts system: IRL-inspired components that can be damaged and repaired.
Each part has a condition 0-100; mechanics use mechanical_engineering to repair.
Parts affect starting, idling, driving, and failure chances.

Part types: each slot (engine, transmission, etc.) can have a variant (e.g. V4 vs V8 engine).
Part type affects performance; condition affects reliability. Template ready for future expansion.
"""
import random

# Part IDs and display names. Order is display order in status.
VEHICLE_PART_IDS = [
    "engine",           # Core: start success, stall chance when running
    "transmission",     # Gearbox: drive success, smooth acceleration
    "brakes",           # Stopping power: brake failure chance, control
    "suspension",       # Ride: drive penalty when bad, comfort
    "tires",            # Traction: drive success, grip
    "battery",          # Electrical start: needed to crank engine
    "fuel_system",      # Fuel delivery: run stability, stalling
    "cooling_system",   # Overheating: engine damage over time if bad
    "electrical",       # Ignition, lights, sensors: start and run
]

PART_DISPLAY_NAMES = {
    "engine": "Engine",
    "transmission": "Transmission",
    "brakes": "Brakes",
    "suspension": "Suspension",
    "tires": "Tires",
    "battery": "Battery",
    "fuel_system": "Fuel system",
    "cooling_system": "Cooling system",
    "electrical": "Electrical system",
}

# Part type template: each part_id maps to a list of variant dicts.
# performance: multiplier for drive/start (1.0 = baseline; >1 = better). Used later for modifiers.
# Placeholder variants for all slots; add more (V8, performance brakes, etc.) as needed.
PART_TYPE_OPTIONS = {
    "engine": [
        {"id": "stock", "name": "Stock inline", "performance": 1.0, "description": "Standard factory engine."},
        {"id": "v4", "name": "V4", "performance": 1.1, "description": "Compact four-cylinder."},
        {"id": "v8", "name": "V8", "performance": 1.35, "description": "Eight-cylinder; more power and torque."},
    ],
    "transmission": [
        {"id": "stock", "name": "Stock automatic", "performance": 1.0, "description": "Basic automatic."},
        {"id": "manual_5", "name": "5-speed manual", "performance": 1.1, "description": "Five-speed manual."},
        {"id": "manual_6", "name": "6-speed manual", "performance": 1.2, "description": "Six-speed manual; better response."},
    ],
    "brakes": [
        {"id": "stock", "name": "Stock brakes", "performance": 1.0, "description": "Standard disc/drum."},
        {"id": "performance", "name": "Performance brakes", "performance": 1.15, "description": "Upgraded pads and discs."},
    ],
    "suspension": [
        {"id": "stock", "name": "Stock suspension", "performance": 1.0, "description": "Factory suspension."},
        {"id": "stiff", "name": "Stiffened suspension", "performance": 1.1, "description": "Tighter handling."},
    ],
    "tires": [
        {"id": "stock", "name": "Stock tires", "performance": 1.0, "description": "Standard road tires."},
        {"id": "all_terrain", "name": "All-terrain", "performance": 1.05, "description": "Better grip in poor conditions."},
    ],
    "battery": [
        {"id": "stock", "name": "Stock battery", "performance": 1.0, "description": "Standard lead-acid."},
        {"id": "heavy_duty", "name": "Heavy-duty battery", "performance": 1.1, "description": "Higher cold-crank amps."},
    ],
    "fuel_system": [
        {"id": "stock", "name": "Stock fuel system", "performance": 1.0, "description": "Factory pump and lines."},
        {"id": "high_flow", "name": "High-flow fuel system", "performance": 1.1, "description": "Upgraded delivery."},
    ],
    "cooling_system": [
        {"id": "stock", "name": "Stock cooling", "performance": 1.0, "description": "Standard radiator and coolant."},
        {"id": "upgraded", "name": "Upgraded cooling", "performance": 1.05, "description": "Larger radiator; runs cooler."},
    ],
    "electrical": [
        {"id": "stock", "name": "Stock electrical", "performance": 1.0, "description": "Factory wiring and alternator."},
        {"id": "upgraded", "name": "Upgraded electrical", "performance": 1.05, "description": "Better alternator and grounds."},
    ],
}


def default_part_types():
    """Return part_id -> type_id (all 'stock')."""
    return {pid: "stock" for pid in VEHICLE_PART_IDS}


def get_part_type_id(vehicle, part_id):
    """Return the installed part type id for this slot (e.g. 'stock', 'v8')."""
    types = getattr(vehicle.db, "vehicle_part_types", None) or {}
    return types.get(part_id, "stock")


def set_part_type_id(vehicle, part_id, type_id):
    """Set installed part type. type_id must exist in PART_TYPE_OPTIONS[part_id]."""
    options = PART_TYPE_OPTIONS.get(part_id, [])
    if not any(t["id"] == type_id for t in options):
        return False
    if not vehicle.db.vehicle_part_types:
        vehicle.db.vehicle_part_types = default_part_types()
    vehicle.db.vehicle_part_types[part_id] = type_id
    return True


def get_part_type_info(vehicle, part_id):
    """Return the type info dict for the installed part (name, performance, description)."""
    type_id = get_part_type_id(vehicle, part_id)
    for t in PART_TYPE_OPTIONS.get(part_id, []):
        if t["id"] == type_id:
            return t
    return {"id": "stock", "name": "Stock", "performance": 1.0, "description": "Standard."}


# Minimum condition (0-100) for engine to start. Below this, start fails.
ENGINE_START_MIN = 15
BATTERY_START_MIN = 20
ELECTRICAL_START_MIN = 10
FUEL_SYSTEM_START_MIN = 5

# Chance per drive tick to stall (when running) if part is damaged. Scale by (100 - condition)/100.
STALL_CHANCE_ENGINE_LOW = 0.25      # at 0 condition, up to 25% base
STALL_CHANCE_FUEL_LOW = 0.15
STALL_CHANCE_ELECTRICAL_LOW = 0.10

# Drive success penalty: each part below 50 adds failure weight.
DRIVE_PARTS_WEIGHT = {
    "engine": 1.5,
    "transmission": 1.2,
    "brakes": 0.8,
    "suspension": 0.5,
    "tires": 1.0,
}


def default_parts():
    """Return a dict of part_id -> condition (100 = pristine)."""
    return {pid: 100 for pid in VEHICLE_PART_IDS}


def get_part_condition(vehicle, part_id):
    """Return condition 0-100 for a part. Uses db.vehicle_parts or default 100."""
    parts = getattr(vehicle.db, "vehicle_parts", None) or {}
    return max(0, min(100, int(parts.get(part_id, 100))))


def set_part_condition(vehicle, part_id, value):
    """Set part condition; clamps to 0-100. Initializes vehicle_parts if needed."""
    parts = getattr(vehicle.db, "vehicle_parts", None)
    if parts is None:
        vehicle.db.vehicle_parts = default_parts()
        parts = vehicle.db.vehicle_parts
    parts[part_id] = max(0, min(100, int(round(value))))


def damage_part(vehicle, part_id, amount):
    """Reduce part condition by amount. Returns new condition."""
    c = get_part_condition(vehicle, part_id)
    new_c = max(0, c - amount)
    set_part_condition(vehicle, part_id, new_c)
    return new_c


def repair_part(vehicle, part_id, amount):
    """Increase part condition by amount. Returns new condition."""
    c = get_part_condition(vehicle, part_id)
    new_c = min(100, c + amount)
    set_part_condition(vehicle, part_id, new_c)
    return new_c


def can_start_engine(vehicle):
    """
    Check if vehicle can start. Returns (True, "") or (False, reason).
    Requires engine, battery, electrical (and loosely fuel_system) above minimums.
    """
    e = get_part_condition(vehicle, "engine")
    b = get_part_condition(vehicle, "battery")
    el = get_part_condition(vehicle, "electrical")
    f = get_part_condition(vehicle, "fuel_system")
    if e < ENGINE_START_MIN:
        return False, "The engine is too damaged to turn over."
    if b < BATTERY_START_MIN:
        return False, "The battery doesn't have enough juice to crank."
    if el < ELECTRICAL_START_MIN:
        return False, "The electrical system won't engage the starter."
    if f < FUEL_SYSTEM_START_MIN:
        return False, "No fuel reaching the engine."
    return True, ""


def roll_stall_chance(vehicle):
    """
    While running, bad parts can cause a stall. Returns True if engine stalls this tick.
    """
    if not getattr(vehicle.db, "engine_running", False):
        return False
    roll = random.random()
    e = get_part_condition(vehicle, "engine")
    f = get_part_condition(vehicle, "fuel_system")
    el = get_part_condition(vehicle, "electrical")
    # Probability scales with damage (100 -> 0, 0 -> max chance)
    stall_e = STALL_CHANCE_ENGINE_LOW * (1 - e / 100.0) if e < 60 else 0
    stall_f = STALL_CHANCE_FUEL_LOW * (1 - f / 100.0) if f < 50 else 0
    stall_el = STALL_CHANCE_ELECTRICAL_LOW * (1 - el / 100.0) if el < 50 else 0
    total = stall_e + stall_f + stall_el
    return roll < total


def drive_failure_modifier(vehicle):
    """
    Returns a modifier for drive success. 0 = no penalty, positive = harder.
    Used to add failure weight or reduce roll; mechanics use mechanical_engineering roll.
    """
    total = 0.0
    for part_id, weight in DRIVE_PARTS_WEIGHT.items():
        c = get_part_condition(vehicle, part_id)
        if c < 50:
            total += weight * (50 - c) / 50.0  # 0 condition => full weight
    return total


def condition_description(condition):
    """Short description for status display."""
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


# --- Timed vehicle inspection (mechanic RP) ---
INSPECT_DURATION_SECONDS = 18
INSPECT_MECHANICS_MIN_LEVEL = 25  # minimum mechanical_engineering skill level to inspect
# Flavor messages per part, in order; shown one every ~2 seconds.
INSPECT_FLAVOR_MESSAGES = [
    ("engine", "You pop the hood and peer at the engine block. You run a hand along the mounts and belts."),
    ("transmission", "You crouch beside the transmission housing and check the shift linkages and seals."),
    ("brakes", "You inspect the brake lines and pads, checking for wear and leaks."),
    ("suspension", "You bounce the suspension at each corner and check the shocks and bushings."),
    ("tires", "You kneel at each tire in turn, checking tread depth and pressure."),
    ("battery", "You open the battery compartment and check the terminals and charge."),
    ("fuel_system", "You trace the fuel lines from tank to engine and check the pump and filter."),
    ("cooling_system", "You check the radiator, hoses, and coolant level."),
    ("electrical", "You inspect the wiring harness and fuse box under the dash."),
]


def _vehicle_inspect_flavor_callback(caller_id, message):
    """Send one RP message to the caller during timed inspection."""
    from evennia.utils.search import search_object
    try:
        objs = search_object("#%s" % caller_id)
        if objs and hasattr(objs[0], "msg"):
            objs[0].msg("|w  " + message + "|n")
    except Exception:
        pass


def _vehicle_inspect_final_callback(caller_id, vehicle_id):
    """Send the full status (part type + condition) to the caller after inspection."""
    from evennia.utils.search import search_object
    try:
        callers = search_object("#%s" % caller_id)
        vehicles = search_object("#%s" % vehicle_id)
        if not callers or not vehicles:
            return
        caller, vehicle = callers[0], vehicles[0]
        if not hasattr(caller, "msg") or not hasattr(vehicle, "db"):
            return
        engine = "|grunning|n" if getattr(vehicle, "engine_running", False) else "|xoff|n"
        lines = [f"|w{vehicle.get_display_name(caller)}|n — Engine: {engine}", ""]
        parts = getattr(vehicle.db, "vehicle_parts", None) or {}
        part_types = getattr(vehicle.db, "vehicle_part_types", None) or default_part_types()
        for part_id in VEHICLE_PART_IDS:
            cond = max(0, min(100, int(parts.get(part_id, 100))))
            type_info = get_part_type_info(vehicle, part_id)
            slot_name = PART_DISPLAY_NAMES.get(part_id, part_id)
            type_name = type_info.get("name", "Stock")
            desc = condition_description(cond)
            lines.append(f"  |w{slot_name}|n — {type_name}: {cond}% ({desc})")
        caller.msg("\n".join(lines))
    except Exception:
        pass
