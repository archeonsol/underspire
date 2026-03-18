"""
Medical treatment menu: GUI for scanning and treating trauma.
EvMenu flow: target -> main panel (vitals, trauma, actions) -> perform action -> result -> back to main.
"""
from world.medical import _ensure_medical_db, get_medical_detail, get_medical_summary, BLEEDING_LEVELS
from world.medical.medical_treatment import get_treatment_options, TOOL_SCANNER
from typeclasses.medical_tools import get_medical_tools_from_inventory, MedicalTool, Bioscanner


def _format_vitals(target):
    hp = getattr(target, "hp", 0)
    mx = getattr(target, "max_hp", 1)
    pct = (hp / mx * 100) if mx else 0
    if pct >= 80:
        bar = "|g" + "|" * 10 + "|n"
    elif pct >= 50:
        bar = "|y" + "|" * 6 + "| " * 4 + "|n"
    elif pct >= 25:
        bar = "|y" + "|" * 3 + "| " * 7 + "|n"
    else:
        bar = "|r" + "|" * max(1, int(10 * pct / 100)) + "| " * (10 - max(1, int(10 * pct / 100))) + "|n"
    return f"  |wHP|n {hp}/{mx} {bar} ({pct:.0f}%)"


def _main_panel_text(caller, target, compact=False):
    _ensure_medical_db(target)

    if compact:
        # After a treatment/scan: header only; EvMenu shows the option list below
        lines = [
            "",
            "|c" + "-" * 52 + "|n",
            f"  |wPatient|n: {target.name}  |xWhat do you do next?|n",
            "|c" + "-" * 52 + "|n",
        ]
    else:
        intro = "Your assessment panel." if target == caller else f"Assessment panel for {target.name}."
        lines = [
            "",
            "|c" + "=" * 52 + "|n",
            "|W  M E D I C A L   A S S E S S M E N T|n",
            "|c" + "=" * 52 + "|n",
            f"  |wPatient|n: {target.name}  |x({intro})|n",
            "",
            _format_vitals(target),
            "",
            "|wTrauma|n:",
            "  " + get_medical_summary(target).replace("\n", "\n  "),
            "",
            "|c" + "-" * 52 + "|n",
        ]
    # Don't embed the option list here; EvMenu displays it from the options dict
    return "\n".join(lines)


def _get_menu_target(caller, kwargs):
    """EvMenu stores init kwargs on caller.ndb._evmenu; they are not passed to the start node."""
    target = kwargs.get("target")
    if target is not None and hasattr(target, "db"):
        return target
    menu = getattr(getattr(caller, "ndb", None), "_evmenu", None)
    target = getattr(menu, "target", None) if menu else None
    return target if (target and hasattr(target, "db")) else None


def node_medical_main(caller, raw_string, **kwargs):
    target = _get_menu_target(caller, kwargs)
    if not target:
        caller.msg("Invalid target.")
        return None, None

    compact = kwargs.get("compact", False)
    text = _main_panel_text(caller, target, compact=compact)
    options = []
    tools = get_medical_tools_from_inventory(caller)
    treatment_options = get_treatment_options(caller, target, tools)

    # Option 1: Scan
    if tools.get(TOOL_SCANNER):
        scanner = tools[TOOL_SCANNER][0]
        options.append({
            "key": "1",
            "desc": "Scan (bioscanner readout)",
            "goto": ("node_do_scan", {"target": target, "scanner": scanner}),
        })
    else:
        options.append({
            "key": "1",
            "desc": "Scan (no scanner)",
            "goto": ("node_medical_main", {}),
        })

    # Options 2+ : treatments
    for i, (action_id, display_name, tool_type, target_info) in enumerate(treatment_options):
        key = str(i + 2)
        tool_list = tools.get(tool_type, [])
        tool_obj = tool_list[0] if tool_list else None
        options.append({
            "key": key,
            "desc": display_name,
            "goto": ("node_do_treatment", {
                "target": target,
                "action_id": action_id,
                "target_info": target_info,
                "tool_type": tool_type,
            }),
        })

    options.append({"key": "q", "desc": "Quit", "goto": "node_medical_exit"})
    return text, options


def node_do_scan(caller, raw_string, **kwargs):
    target = kwargs.get("target") or _get_menu_target(caller, kwargs)
    scanner = kwargs.get("scanner")
    if not scanner or not hasattr(scanner, "use_for_scan"):
        caller.msg("|rNo scanner available.|n")
        return node_medical_main(caller, raw_string, target=target, compact=True)

    success, out = scanner.use_for_scan(caller, target)
    if not success:
        caller.msg("|r" + (out if isinstance(out, str) else "Scan failed.") + "|n")
        return node_medical_main(caller, raw_string, target=target, compact=True)

    if isinstance(out, dict):
        if out.get("formatted"):
            caller.msg(out["formatted"])
        else:
            hp = out.get("hp", 0)
            max_hp = out.get("max_hp", 1)
            detail = out.get("detail", "")
            target_name = out.get("target_name", target.name)
            caller.msg(f"|c[ BIOSCANNER: {target_name} ]|n  {hp}/{max_hp} HP\n\n{detail}")
        if target != caller:
            target.msg(f"{(caller.get_display_name(target) if hasattr(caller, 'get_display_name') else caller.name)} runs a scanner over you. You see the readout in their hands.")
    else:
        caller.msg(out)

    # Return compact menu so the scan readout stays visible
    return node_medical_main(caller, raw_string, target=target, compact=True)


def node_do_treatment(caller, raw_string, **kwargs):
    target = kwargs.get("target") or _get_menu_target(caller, kwargs)
    if not target:
        caller.msg("|rInvalid target.|n")
        return node_medical_main(caller, raw_string)
    action_id = kwargs.get("action_id")
    target_info = kwargs.get("target_info")
    tool_type = kwargs.get("tool_type")

    tools = get_medical_tools_from_inventory(caller)
    tool_list = tools.get(tool_type, [])
    if not tool_list:
        caller.msg("|rYou no longer have the right tool.|n")
        return node_medical_main(caller, raw_string, target=target, compact=True)

    tool = tool_list[0]
    if not tool.consume_use():
        caller.msg("|y" + f"{tool.get_display_name(caller)} is used up." + "|n")
        return node_medical_main(caller, raw_string, target=target, compact=True)

    success, msg = tool.use_for_treatment(caller, target, action_id, target_info)
    # Color the result so it stands out (success = green, failure = red)
    if success:
        caller.msg("|g" + msg + "|n")
        if target != caller:
            target.msg("|g" + f"{(caller.get_display_name(target) if hasattr(caller, 'get_display_name') else caller.name)} works on you: {msg[:70]}..." + "|n")
    else:
        caller.msg("|r" + msg + "|n")
        if target != caller:
            target.msg("|r" + f"{(caller.get_display_name(target) if hasattr(caller, 'get_display_name') else caller.name)} tries to help: {msg[:70]}..." + "|n")

    # Return compact menu (options only, no full readout) so the result message stays visible
    return node_medical_main(caller, raw_string, target=target, compact=True)


def node_medical_exit(caller, raw_string, **kwargs):
    caller.msg("You step back from the patient.")
    return None, None


def start_medical_menu(caller, target):
    """Start the medical EvMenu for the given target."""
    from evennia.utils.evmenu import EvMenu
        EvMenu(
        caller,
        "world.medical.medical_menu",
        startnode="node_medical_main",
        target=target,
        persistent=False,
    )
