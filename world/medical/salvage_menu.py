"""
EvMenu flow for corpse cyberware salvage.
"""

from world.medical.salvage import get_assessment_entries, start_extraction


_W = 58
_BORDER_COLOR = "|x"
_HEADER_COLOR = "|c"
_LABEL_COLOR = "|w"
_DIM = "|x"
_N = "|n"


def _line(char="-"):
    return f"{_BORDER_COLOR}{''.ljust(_W, char)}{_N}"


def _heavy_line():
    return f"{_BORDER_COLOR}{''.ljust(_W, '=')}{_N}"


def _get_target(caller, kwargs):
    target = kwargs.get("target")
    if target is not None and hasattr(target, "db"):
        return target
    menu = getattr(getattr(caller, "ndb", None), "_evmenu", None)
    if menu and getattr(menu, "target", None):
        return menu.target
    return None


def _assessment_text(caller, corpse, entries):
    c_name = corpse.get_display_name(caller) if hasattr(corpse, "get_display_name") else corpse.key
    lines = [
        "",
        _heavy_line(),
        f"  {_HEADER_COLOR}S A L V A G E   A S S E S S M E N T{_N}",
        _heavy_line(),
        "",
        f"  The body of {c_name} is cold. Rigor is setting in. The chrome is still here.",
        "",
        _line(),
        f"  {_HEADER_COLOR}INSTALLED CYBERWARE{_N}",
        _line(),
    ]
    if not entries:
        lines.extend(
            [
                f"  {_DIM}The body has been stripped. Nothing left worth taking.{_N}",
                "",
            ]
        )
        return "\n".join(lines)

    for idx, entry in enumerate(entries, 1):
        lines.extend(
            [
                f"  {_LABEL_COLOR}{idx}.{_N} {entry['name']} - {entry['location']}.",
                f"     Extraction: {entry['label']}.",
                "",
            ]
        )
    lines.append(_line())
    return "\n".join(lines)


def node_salvage_main(caller, raw_string, **kwargs):
    corpse = _get_target(caller, kwargs)
    if not corpse:
        return "No body to work on.", [{"key": "q", "desc": "Step back", "goto": "node_salvage_exit"}]

    entries = get_assessment_entries(corpse)
    text = _assessment_text(caller, corpse, entries)
    options = []
    for idx, entry in enumerate(entries, 1):
        options.append(
            {
                "key": str(idx),
                "desc": f"Extract {entry['name']}",
                "goto": ("node_salvage_confirm", {"target": corpse, "cw_id": entry["id"]}),
            }
        )
    options.append({"key": "q", "desc": "Step back from the body", "goto": "node_salvage_exit"})
    return text, options


def node_salvage_confirm(caller, raw_string, **kwargs):
    corpse = _get_target(caller, kwargs)
    if not corpse:
        return "No body to work on.", [{"key": "q", "desc": "Step back", "goto": "node_salvage_exit"}]
    cw_id = kwargs.get("cw_id")
    cw = None
    for entry in get_assessment_entries(corpse):
        if entry["id"] == cw_id:
            cw = entry["obj"]
            break
    if not cw:
        return node_salvage_main(caller, raw_string, target=corpse)
    text = (
        f"\n{_line()}\n"
        f"  You are about to cut {cw.key} from the body.\n\n"
        f"  {_DIM}This takes time. Once you start, your hands are busy.{_N}\n"
        f"{_line()}\n"
    )
    options = [
        {"key": ("y", "yes"), "desc": "Proceed", "goto": ("node_salvage_result", {"target": corpse, "cw_id": cw.id})},
        {"key": ("n", "no"), "desc": "Back", "goto": ("node_salvage_main", {"target": corpse})},
    ]
    return text, options


def node_salvage_result(caller, raw_string, **kwargs):
    corpse = _get_target(caller, kwargs)
    if not corpse:
        return node_salvage_main(caller, raw_string)
    cw_id = kwargs.get("cw_id")
    cw = None
    for entry in get_assessment_entries(corpse):
        if entry["id"] == cw_id:
            cw = entry["obj"]
            break
    if not cw:
        caller.msg("That piece is already gone.")
        return node_salvage_main(caller, raw_string, target=corpse)
    ok, err = start_extraction(caller, corpse, cw)
    if not ok:
        caller.msg(err)
    return node_salvage_main(caller, raw_string, target=corpse)


def node_salvage_exit(caller, raw_string, **kwargs):
    caller.msg(f"{_DIM}You step back from the body.{_N}")
    return None, None


def start_salvage_menu(caller, corpse):
    from evennia.utils.evmenu import EvMenu

    EvMenu(
        caller,
        "world.medical.salvage_menu",
        startnode="node_salvage_main",
        target=corpse,
        persistent=False,
    )
