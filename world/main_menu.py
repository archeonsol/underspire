# world/main_menu.py
"""
Main menu (soul registry) after login. Account-level: choose to return to a body or forge a new one.
Matches death-lobby tone: bureaucratic, faintly grim, no auto-puppet.
"""

from django.conf import settings
from evennia.utils.evmenu import EvMenu
from evennia.utils.create import create_object
from evennia.utils.ansi import ANSIString
from evennia.utils.utils import wrap
from world.ui_utils import fade_rule

# ══════════════════════════════════════════════════════════════════════════════
# UI HELPERS (Bureaucratic Terminal Aesthetic)
# ══════════════════════════════════════════════════════════════════════════════

_UI_WIDTH = 72
_BLOCKED_MENU_ESCAPES = {"q", "quit", "exit", "@quit", "@q", "logout", "disconnect"}


def _is_blocked_menu_escape(raw_string: str) -> bool:
    return (raw_string or "").strip().lower() in _BLOCKED_MENU_ESCAPES


def _registry_panel(title: str, text: str, status: str = None, width: int = _UI_WIDTH) -> str:
    """
    Auto-wrapping bordered narrative panel styled like a sterile mainframe.
    Uses stark grey and amber/cyan to contrast with the blood-red of Chargen.
    """
    inner = width - 4 
    out   = []

    raw_title = f" [ {title} ] "
    pad_total = width - 2 - len(raw_title)
    pad_l     = pad_total // 2
    pad_r     = pad_total - pad_l
    
    # Render only the left border of the panel to avoid right-panel misalignment.
    out.append(f"|x┌{'─' * pad_l}|y{raw_title}|x{fade_rule(pad_r, '─')}|n")

    explicit_lines = text.split("\n")
    for line in explicit_lines:
        if not line.strip():
            empty_pad = ANSIString("  ").ljust(inner + 2)
            out.append(f"|x│|n{empty_pad}")
        else:
            ansi_line = ANSIString(line)
            if len(ansi_line) <= inner:
                # Fits perfectly, preserve spaces!
                padded = ANSIString(f"  {line}").ljust(inner + 2)
                out.append(f"|x│|n{padded}")
            else:
                # Wrap and split into a list!
                wrapped_string = wrap(line, width=inner)
                for w_line in wrapped_string.split("\n"):
                    padded = ANSIString(f"  {w_line}").ljust(inner + 2)
                    out.append(f"|x│|n{padded}")

    if status:
        out.append(f"|x├{fade_rule(width - 2, '─')}|n")
        status_padded = ANSIString(f"  |c>>|n |w{status}|n").ljust(inner + 2)
        out.append(f"|x│|n{status_padded}")

    out.append(f"|x└{fade_rule(width - 2, '─')}|n")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════════
# MENU NODES
# ══════════════════════════════════════════════════════════════════════════════

def node_start(caller, raw_string, **kwargs):
    """Soul registry — the first thing you see after logging in."""
    if _is_blocked_menu_escape(raw_string):
        caller.msg("\n|r[!] Sign-out is only available via the menu option.|n\n")
    
    text_body = (
        "|wNo body. No pain. Just you and the terminal.|n "
        "The same soft light, the same hum.\n\n"
        "A faded physical sign on the wall reads: "
        "|xPLEASE WAIT. A REPRESENTATIVE WILL ASSIST YOU SHORTLY.|n\n\n"
        "Nobody has ever seen a representative. You have time."
    )
    
    text = _registry_panel("SOUL REGISTRY", text_body, status="SYSTEM IDLE. AWAITING INPUT.")
    
    chars = list(caller.characters.all()) if hasattr(caller, "characters") else []
    options = []
    
    if chars:
        options.append({"desc": "|cReturn to your body|n", "goto": "node_select_character"})
    else:
        options.append({"desc": "|yForge a new soul|n", "goto": "node_create_character"})
        
    options.append({"desc": "|wRead the directives|n", "goto": "node_rules"})
    options.append({"desc": "|xSign out|n", "goto": "node_quit"})
    
    return text, options


def node_select_character(caller, raw_string, **kwargs):
    """List the account's characters."""
    if _is_blocked_menu_escape(raw_string):
        caller.msg("\n|r[!] Sign-out is only available via the menu option.|n\n")

    chars = list(caller.characters.all()) if hasattr(caller, "characters") else []

    if not chars:
        text_body = (
            "|rERROR: NO VESSEL ON FILE.|n\n\n"
            "Your soul is not bound to any body. You went to the light, or you "
            "have never forged one.\n\n"
            "Return to the main menu and select |yForge a new soul|n to enter the world."
        )
        text = _registry_panel("NO VESSEL FOUND", text_body, status="CONNECTION FAILED")
        options = [{"desc": "Back to Soul Registry", "goto": "node_start"}]
        return text, options

    text_body = "|wSouls currently bound to your account:|n"
    text = _registry_panel("VESSEL SELECTION", text_body, status=f"FOUND {len(chars)} REGISTERED VESSEL(S)")
    
    options = []
    for char in chars:
        options.append({"desc": f"|c{char.key}|n", "goto": ("node_puppet_character", {"char": char})})
    options.append({"desc": "|xBack to Soul Registry|n", "goto": "node_start"})
    
    return text, options


def node_puppet_character(caller, raw_string, **kwargs):
    """Puppets the chosen character and cleanly closes the menu."""
    if _is_blocked_menu_escape(raw_string):
        caller.msg("\n|r[!] Sign-out is only available via the menu option.|n\n")
        return "node_start"

    char = kwargs.get("char")

    if not char:
        caller.msg("\n|r[!] Error: No character selected.|n\n")
        return "node_start"

    sessions = caller.sessions.get() if hasattr(caller, "sessions") else []
    if not sessions:
        return "node_start"
    session = sessions[0]

    current = getattr(session, "puppet", None)
    if current is char:
        caller.msg("\n|c>> Downloading consciousness... Returning to body.|n\n")
        return "", None

    caller.msg("\n|c>> Downloading consciousness... Returning to body.|n\n")

    try:
        char.db._suppress_become_message = True
        caller.puppet_object(session, char)
    except RuntimeError:
        caller.msg("\n|r[!] Synchronization failed. That body is no longer available.|n\n")
        return "node_start"

    return "", None


def node_create_character(caller, raw_string, **kwargs):
    """Create a new character (forges a vessel and runs chargen). One per account."""
    if _is_blocked_menu_escape(raw_string):
        caller.msg("\n|r[!] Sign-out is only available via the menu option.|n\n")
        return "node_start"

    chars = list(caller.characters.all()) if hasattr(caller, "characters") else []
    max_chars = getattr(settings, "MAX_NR_CHARACTERS", 1)
    
    if len(chars) >= max_chars:
        text_body = (
            "|rAUTHORIZATION DENIED: YOU ALREADY HAVE A VESSEL ON FILE.|n\n\n"
            "This registry allows one soul per account. Return to your body from "
            "the main menu, or go to the light and forge again."
        )
        text = _registry_panel("QUOTA EXCEEDED", text_body, status="REQUEST REJECTED")
        options = [{"desc": "Back to Soul Registry", "goto": "node_start"}]
        return text, options

    sessions = caller.sessions.get() if hasattr(caller, "sessions") else []
    if not sessions:
        return "node_start"
    session = sessions[0]

    start_loc = getattr(settings, "DEFAULT_HOME", None)
    temp_name = "NewSoul_%s" % caller.id
    new_char = create_object(
        "typeclasses.characters.Character",
        key=temp_name,
        location=start_loc,
        home=start_loc,
    )
    
    if not new_char:
        caller.msg("\n|r[!] The registry could not forge a vessel. Try again or contact staff.|n\n")
        return "node_start"

    caller.characters.add(new_char)
    
    menu = getattr(caller.ndb, "_evmenu", None) if hasattr(caller, "ndb") else None
    if menu and hasattr(menu, "close_menu"):
        try:
            menu.close_menu()
        except Exception:
            pass
            
    caller.msg("\n|y>> Forging a new vessel... Dispatching to the Rite.|n\n")
    
    try:
        new_char.db._suppress_become_message = True  
        caller.puppet_object(session, new_char)
    except RuntimeError:
        caller.msg("\n|r[!] Critical error. You remain at the registry.|n\n")
        return "node_start"
        
    return None 


def node_rules(caller, raw_string, **kwargs):
    """Short server directives."""
    if _is_blocked_menu_escape(raw_string):
        caller.msg("\n|r[!] Sign-out is only available via the menu option.|n\n")
        return "node_start"

    text_body = (
        "|w1. PERMANENCE:|n Death is final. When you flatline and time runs out — "
        "or someone ends you — you are gone. Your body becomes a corpse. You may "
        "have a shard stored, or you may go to the light and forge a new soul.\n\n"
        "|w2. IMMERSION:|n Stay in character. The world is harsh; play it straight.\n\n"
        "|w3. INTEGRITY:|n Do not exploit. Report anomalies; do not abuse them."
    )
    text = _registry_panel("REGISTRY DIRECTIVES", text_body, status="READ CAREFULLY")
    options = [{"desc": "Back to Soul Registry", "goto": "node_start"}]
    return text, options


def node_quit(caller, raw_string, **kwargs):
    """Disconnect from the game."""
    sessions = caller.sessions.get() if hasattr(caller, "sessions") else []
    caller.msg("\n|x>> Terminating connection. Goodbye.|n\n")
    
    for session in sessions:
        try:
            if getattr(session, "sessionhandler", None):
                session.sessionhandler.disconnect(session, reason="Signed out from Soul Registry")
            elif hasattr(session, "disconnect"):
                session.disconnect("Signed out from Soul Registry")
        except Exception:
            pass
    return None


def start_main_menu(caller):
    """Launch the Soul Registry menu after login."""
    EvMenu(caller, "world.main_menu", startnode="node_start", cmd_on_exit=None, auto_quit=False)