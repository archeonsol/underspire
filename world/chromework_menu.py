"""
EvMenu flow for cyberware customization at the Cyberware Customization Station.
Requires Electrical Engineering 75. Put cyberware in the station, then use the station.

Note: Evennia EvMenu ignores an "exec" key on options; use a callable "goto" to run side effects.
"""

from world.theme_colors import CHROME_COLORS, COMBAT_COLORS as CC

CHROMOWORK_SKILL = "electrical_engineering"
CHROMOWORK_MIN_SKILL = 75
CHROMOWORK_DESC_DIFFICULTY = 10
CHROMOWORK_DESC_MIN = 20
CHROMOWORK_DESC_MAX = 500

_W = 58
_BORDER_COLOR = "|x"
_HEADER_COLOR = CC["parry"]
_LABEL_COLOR = "|w"
_DIM = "|x"
_N = "|n"


def _line(char="-"):
    return f"{_BORDER_COLOR}{''.ljust(_W, char)}{_N}"


def _get_station(caller, kwargs):
    """EvMenu stores start kwargs on ndb._evmenu, not in the node's **kwargs."""
    station = kwargs.get("station")
    if station is None:
        menu = getattr(getattr(caller, "ndb", None), "_evmenu", None)
        if menu:
            station = getattr(menu, "station", None)
    return station


def _get_cyberware(caller, kwargs):
    cyberware = kwargs.get("cyberware")
    if cyberware is None:
        menu = getattr(getattr(caller, "ndb", None), "_evmenu", None)
        if menu:
            cyberware = getattr(menu, "cyberware", None)
    return cyberware


def _format_color_line_plain(cyberware):
    """Human-readable color summary (avoid printing raw |codes alone on the 'Color:' line)."""
    code = getattr(cyberware.db, "custom_color", None)
    if not code:
        return "default chrome — bold white"
    for _key, entry in CHROME_COLORS.items():
        if entry["code"] == code:
            return f"{entry['preview']} — {entry['desc']}"
    return f"custom ({code})"


def _view_text(caller, cyberware):
    from world.skin_tones import get_chrome_desc_color, get_chrome_desc_text

    lines = [
        "",
        _line(),
        f"  {_HEADER_COLOR}{cyberware.key}{_N} — chromework preview",
        _line(),
        "",
    ]
    color = get_chrome_desc_color(cyberware)
    lines.append(f"  Color: {_format_color_line_plain(cyberware)}")
    mods = getattr(cyberware, "body_mods", {}) or {}
    for part, (mode, _) in mods.items():
        txt = get_chrome_desc_text(cyberware, part)
        if not txt:
            continue
        frag = f"{color or '|w'}{txt}{_N}"
        lines.append(f"  [{mode}] {part}: {frag}")
    lines.append("")
    return "\n".join(lines)


def _ctx(station, cyberware, **extra):
    d = {"station": station, "cyberware": cyberware}
    d.update(extra)
    return d


def _goto_apply_color_return_main(caller, raw_string, **kwargs):
    """Apply CHROME_COLORS preset; EvMenu requires a callable goto (exec is not supported)."""
    station = _get_station(caller, kwargs)
    cyberware = _get_cyberware(caller, kwargs)
    color_key = kwargs.get("color_key")
    if not station or not cyberware or cyberware.location != station:
        caller.msg("The chrome is no longer in the station.")
        return "node_chromework_exit"
    if color_key and color_key in CHROME_COLORS:
        entry = CHROME_COLORS[color_key]
        cyberware.db.custom_color = entry["code"]
        caller.msg(f"Chrome color set to {entry['preview']} — {entry['desc']}")
    return "node_chromework_main"


def _goto_process_desc_input(caller, raw_string, **kwargs):
    """Free-text line from _default option; validate, roll, save custom_descriptions."""
    from world.skin_tones import strip_color_codes

    station = kwargs.get("station") or _get_station(caller, kwargs)
    cyberware = kwargs.get("cyberware") or _get_cyberware(caller, kwargs)
    part = kwargs.get("desc_part")
    retry = _ctx(station, cyberware, desc_part=part)

    if not station or not cyberware or cyberware.location != station:
        caller.msg("The chrome is no longer in the station.")
        return "node_chromework_exit"
    if not part:
        return "node_chromework_desc_pick"

    mods = getattr(cyberware, "body_mods", {}) or {}
    if part not in mods:
        caller.msg("That cyberware does not modify that body part.")
        return ("node_chromework_desc_pick", _ctx(station, cyberware))

    text = (raw_string or "").strip()
    if not text:
        caller.msg(f"Type {CHROMOWORK_DESC_MIN}-{CHROMOWORK_DESC_MAX} characters, or |wb|n to go back.")
        return ("node_chromework_desc_enter", retry)

    if len(text) < CHROMOWORK_DESC_MIN or len(text) > CHROMOWORK_DESC_MAX:
        caller.msg(f"Description must be {CHROMOWORK_DESC_MIN}-{CHROMOWORK_DESC_MAX} characters.")
        return ("node_chromework_desc_enter", retry)

    clean = strip_color_codes(text)
    if clean != text:
        caller.msg("Color codes were stripped from the description; use Set color for tint.")

    if not hasattr(caller, "roll_check"):
        caller.msg("You cannot perform chromework.")
        return ("node_chromework_main", _ctx(station, cyberware))

    tier, total = caller.roll_check(
        ["intelligence", "strength"],
        CHROMOWORK_SKILL,
        difficulty=CHROMOWORK_DESC_DIFFICULTY,
    )
    if tier == "Failure":
        caller.msg(
            f"You botch the fine adjustment. (Electrical Engineering vs {CHROMOWORK_DESC_DIFFICULTY}, got {total})"
        )
        return ("node_chromework_desc_enter", retry)

    custom = dict(getattr(cyberware.db, "custom_descriptions", None) or {})
    custom[part] = clean
    cyberware.db.custom_descriptions = custom
    cyberware.db.customized_by = caller.dbref
    caller.msg(f"Updated description for |w{part}|n on {cyberware.key}.")
    return "node_chromework_main"


def node_chromework_main(caller, raw_string, **kwargs):
    station = _get_station(caller, kwargs)
    cyberware = _get_cyberware(caller, kwargs)
    if not station or not cyberware or cyberware.location != station:
        caller.msg("The chrome is no longer in the station.")
        return None, None

    text = _view_text(caller, cyberware)
    options = [
        {"key": "1", "desc": "View (refresh)", "goto": ("node_chromework_main", _ctx(station, cyberware))},
        {"key": "2", "desc": "Set color", "goto": ("node_chromework_color", _ctx(station, cyberware))},
        {"key": "3", "desc": "Set description", "goto": ("node_chromework_desc_pick", _ctx(station, cyberware))},
        {"key": "4", "desc": "Retrieve chrome", "goto": ("node_chromework_retrieve", _ctx(station, cyberware))},
        {"key": ("q", "quit"), "desc": "Step back", "goto": "node_chromework_exit"},
    ]
    return text, options


def node_chromework_color(caller, raw_string, **kwargs):
    station = _get_station(caller, kwargs)
    cyberware = _get_cyberware(caller, kwargs)
    if not station or not cyberware or cyberware.location != station:
        caller.msg("The chrome is no longer in the station.")
        return None, None

    preset_list = sorted(CHROME_COLORS.keys())
    lines = ["", _line(), f"  {_HEADER_COLOR}COLOR PRESETS{_N}", _line(), ""]
    options = []
    for idx, key in enumerate(preset_list, 1):
        entry = CHROME_COLORS[key]
        lines.append(f"  {idx}. {entry['preview']} — {entry['desc']}")
        options.append(
            {
                "key": str(idx),
                "desc": key,
                "goto": (
                    _goto_apply_color_return_main,
                    _ctx(station, cyberware, color_key=key),
                ),
            }
        )
    lines.append("")
    options.append({"key": "b", "desc": "Back", "goto": ("node_chromework_main", _ctx(station, cyberware))})
    return "\n".join(lines), options


def node_chromework_desc_pick(caller, raw_string, **kwargs):
    station = _get_station(caller, kwargs)
    cyberware = _get_cyberware(caller, kwargs)
    if not station or not cyberware or cyberware.location != station:
        caller.msg("The chrome is no longer in the station.")
        return None, None

    mods = getattr(cyberware, "body_mods", {}) or {}
    parts = list(mods.keys())
    if not parts:
        text = "\nNo parts to customize on this chrome.\n"
        return text, [{"key": "b", "desc": "Back", "goto": ("node_chromework_main", _ctx(station, cyberware))}]

    lines = [
        "",
        _line(),
        f"  {_HEADER_COLOR}SET DESCRIPTION{_N}",
        _line(),
        "",
        "  Pick a part to customize.",
        f"  Length: {CHROMOWORK_DESC_MIN}-{CHROMOWORK_DESC_MAX} characters. Electrical Engineering check vs "
        f"{CHROMOWORK_DESC_DIFFICULTY}.",
        "",
    ]
    for i, part in enumerate(parts, 1):
        lines.append(f"  {i}. {part}")
    lines.append("")
    options = []
    for i, part in enumerate(parts, 1):
        options.append(
            {
                "key": str(i),
                "desc": part,
                "goto": ("node_chromework_desc_enter", _ctx(station, cyberware, desc_part=part)),
            }
        )
    options.append({"key": "b", "desc": "Back", "goto": ("node_chromework_main", _ctx(station, cyberware))})
    return "\n".join(lines), options


def node_chromework_desc_enter(caller, raw_string, **kwargs):
    station = _get_station(caller, kwargs)
    cyberware = _get_cyberware(caller, kwargs)
    part = kwargs.get("desc_part")
    if not station or not cyberware or cyberware.location != station:
        caller.msg("The chrome is no longer in the station.")
        return None, None
    if not part:
        return node_chromework_desc_pick(caller, raw_string, **kwargs)

    text = (
        f"\n{_line()}\n"
        f"  {_HEADER_COLOR}DESCRIPTION FOR: {part}{_N}\n"
        f"{_line()}\n\n"
        f" Customize your cyberware now. Do not use color.\n"
        f"{_line()}\n"
    )
    ctx = _ctx(station, cyberware, desc_part=part)
    options = [
        {
            "key": "_default",
            "goto": (_goto_process_desc_input, ctx),
        },
        {"key": "b", "desc": "Back", "goto": ("node_chromework_desc_pick", _ctx(station, cyberware))},
    ]
    return text, options


def node_chromework_retrieve(caller, raw_string, **kwargs):
    station = _get_station(caller, kwargs)
    cyberware = _get_cyberware(caller, kwargs)
    if not station or not cyberware or cyberware.location != station:
        caller.msg("The chrome is no longer in the station.")
        return None, None

    cyberware.move_to(caller, quiet=True)
    cw_name = cyberware.get_display_name(caller) if hasattr(cyberware, "get_display_name") else cyberware.key
    caller.msg(f"You retrieve {cw_name} from the station.")
    if caller.location:
        caller.location.msg_contents(
            f"{caller.key} retrieves {cw_name} from the cyberware customization station.",
            exclude=caller,
        )
    return None, None


def node_chromework_exit(caller, raw_string, **kwargs):
    caller.msg(f"{_DIM}You step back from the station.{_N}")
    return None, None


def start_chromework_menu(caller, station, cyberware):
    from evennia.utils.evmenu import EvMenu

    EvMenu(
        caller,
        "world.chromework_menu",
        startnode="node_chromework_main",
        station=station,
        cyberware=cyberware,
        persistent=False,
    )
