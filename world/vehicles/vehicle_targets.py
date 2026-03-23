"""
Resolve a Vehicle for commands issued in the exterior room or inside VehicleInterior.

The Vehicle object lives in the street room, not in cabin contents — search must use db.vehicle.
"""

from __future__ import annotations

INTERIOR_VEHICLE_ALIASES = frozenset(("here", "vehicle", "cabin", "doors", "door", "it"))


def resolve_vehicle_for_caller(caller, args: str | None):
    """
    Return the target Vehicle, or None.

    Inside a VehicleInterior: empty string or aliases (here, vehicle, …) select loc.db.vehicle;
    otherwise substring match on vehicle label/key, then normal search in the cabin (usually empty).
    Outside: search caller.location for a Vehicle by name.
    """
    from typeclasses.vehicles import Vehicle, VehicleInterior, vehicle_label

    loc = caller.location
    if not loc:
        return None
    raw = (args or "").strip()
    al = raw.lower()

    if isinstance(loc, VehicleInterior):
        v = getattr(loc.db, "vehicle", None)
        if v and isinstance(v, Vehicle):
            if not raw or al in INTERIOR_VEHICLE_ALIASES:
                return v
            lab = vehicle_label(v).lower()
            vk = (v.key or "").lower()
            if al in lab or al in vk:
                return v
    if not raw:
        return None
    target = caller.search(raw, location=loc)
    if target and isinstance(target, Vehicle):
        return target
    return None
