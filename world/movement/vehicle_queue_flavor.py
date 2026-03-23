"""
Brief cabin / rider lines for queued vehicle moves (no full windscreen between steps).
"""
from __future__ import annotations

_DIR_ALIASES = {
    "n": "north",
    "s": "south",
    "e": "east",
    "w": "west",
    "ne": "northeast",
    "nw": "northwest",
    "se": "southeast",
    "sw": "southwest",
    "u": "up",
    "d": "down",
}

_OPP = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "northeast": "southwest",
    "southwest": "northeast",
    "northwest": "southeast",
    "southeast": "northwest",
    "up": "down",
    "down": "up",
}


def _norm(d: str | None) -> str:
    if not d:
        return ""
    x = d.strip().lower()
    return _DIR_ALIASES.get(x, x)


def _rev(d: str) -> str:
    return _OPP.get(d, d)


def _dir_word(d: str | None) -> str:
    """Full direction word for prose (e.g. west, northeast)."""
    n = _norm(d or "")
    return n or (d or "").strip().lower() or "ahead"


def _turn_kind(prev_dir: str | None, curr_dir: str) -> str:
    p = _norm(prev_dir or "")
    c = _norm(curr_dir) or curr_dir
    if not p:
        return "same"
    if p == c:
        return "same"
    if _rev(p) == c:
        return "opposite"
    return "turn"


def queued_segment_interior_line(
    vehicle_type: str | None, prev_dir: str | None, curr_dir: str
) -> str:
    """One line for a middle step in a multi-segment drive/fly queue."""
    vt = (vehicle_type or "ground").lower()
    kind = _turn_kind(prev_dir, curr_dir)
    dw = _dir_word(curr_dir)
    if vt == "aerial":
        if kind == "opposite":
            return (
                f"|xYou bank into a wide turn, reversing heading and scanning the grid below, "
                f"then roll out toward the {dw}.|n"
            )
        if kind == "turn":
            return f"|xYou check your airspace cams and vector onto the new heading—bearing {dw}.|n"
        return f"|xYou cruise {dw}, checking your surroundings as you go.|n"
    if vt == "motorcycle":
        if kind == "opposite":
            return f"|xYou brake and swing the bike through a tight turnaround, then haul toward the {dw}.|n"
        if kind == "turn":
            return f"|xYou check mirrors and lean into the new line, rolling {dw}.|n"
        return f"|xYou roll {dw}, engine note steady under you.|n"
    # enclosed ground / default
    if kind == "opposite":
        return f"|xYou slow, circle, and point the nose back the other way, then track {dw}.|n"
    if kind == "turn":
        return f"|xYou check mirrors and ease onto the new heading—{dw}.|n"
    return f"|xYou cruise {dw}, eyes on the road ahead.|n"


def queued_segment_exterior_line(
    vehicle_name: str, vehicle_type: str | None, prev_dir: str | None, curr_dir: str
) -> str:
    """Third-person line for observers when a queued segment begins (old room, after move)."""
    vn = vehicle_name or "The vehicle"
    vt = (vehicle_type or "ground").lower()
    kind = _turn_kind(prev_dir, curr_dir)
    dw = _dir_word(curr_dir)
    if vt == "aerial":
        if kind == "opposite":
            return f"{vn} banks wide, reverses heading, straightens, then tracks toward the {dw}."
        if kind == "turn":
            return f"{vn} checks its line and vectors onto a new heading—toward the {dw}."
        return f"{vn} cruises {dw}, running lights steady on its heading."
    if vt == "motorcycle":
        if kind == "opposite":
            return (
                f"{vn} brakes hard, swings through a tight turnaround, then rolls on toward the {dw}."
            )
        if kind == "turn":
            return f"{vn} leans into a new line toward the {dw}, mirrors flashing in the sun."
        return f"{vn} rolls {dw}, engine note holding steady."
    if kind == "opposite":
        return f"{vn} slows, circles, and points back the other way, then tracks {dw}."
    if kind == "turn":
        return f"{vn} eases {dw}, indicators ticking onto the new line."
    return f"{vn} cruises {dw} with the traffic."


def queued_finish_exterior_line(
    vehicle_name: str, vehicle_type: str | None, last_dir: str | None = None
) -> str:
    """Optional observer line when the last queued leg completes (departure room)."""
    vn = vehicle_name or "The vehicle"
    vt = (vehicle_type or "ground").lower()
    dw = _dir_word(last_dir) if last_dir else ""
    if vt == "aerial":
        if dw:
            return f"{vn} slows to a hover, thrusters trimming—last run toward the {dw}."
        return f"{vn} slows, thrusters trimming as it comes to a hover."
    if vt == "motorcycle":
        if dw:
            return f"{vn} rolls to a stop, engine ticking over, last pull {dw}."
        return f"{vn} rolls to a stop, engine ticking over."
    if dw:
        return f"{vn} slows and pulls to a stop, last stretch {dw}."
    return f"{vn} slows and pulls to a stop."


def queued_finish_interior_line(vehicle_type: str | None, last_dir: str | None = None) -> str:
    """Cabin / rider line when the last queued segment completes."""
    vt = (vehicle_type or "ground").lower()
    dw = _dir_word(last_dir) if last_dir else ""
    if vt == "aerial":
        if dw:
            return (
                f"|xYou cut the horizontal thrusters and ease to a hover, the last vector {dw} behind you.|n"
            )
        return (
            "|xYou slowly cut the horizontal thrusters and apply the engine brake, "
            "bringing the craft to a stop.|n"
        )
    if vt == "motorcycle":
        if dw:
            return f"|xYou roll to a stop, engine ticking over—that last pull was {dw}.|n"
        return "|xYou roll to a stop, engine ticking over.|n"
    if dw:
        return f"|xYou ease off the throttle and settle, last run {dw}.|n"
    return "|xYou ease off the throttle and let the vehicle settle.|n"
