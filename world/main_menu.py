"""
Main menu (soul registry) after login. Account-level: choose to return to a body or forge a new one.
Matches death-lobby tone: bureaucratic, faintly grim, no auto-puppet.
"""
from django.conf import settings
from evennia.utils.evmenu import EvMenu
from evennia.utils.create import create_object


def node_start(caller, raw_string, **kwargs):
    """Soul registry — the first thing you see after logging in."""
    text = (
        "|ySOUL REGISTRY|n\n\n"
        "No body. No pain. Just you and the terminal. The same soft light, the same hum.\n"
        "A sign on the wall says |wPLEASE WAIT. A representative will assist you shortly.|n\n"
        "Nobody has ever seen a representative. You have time.\n\n"
        "|cSelect an option below:|n\n"
    )
    
    # Check if the account has any bound characters
    chars = list(caller.characters.all()) if hasattr(caller, "characters") else []
    
    # Start with an empty list of options
    options = []
    
    # Conditionally add the first option
    if chars:
        # They have at least one character, so they can play.
        options.append({"desc": "Return to your body", "goto": "node_select_character"})
    else:
        # They have no characters, so they must create one.
        options.append({"desc": "Forge a new soul", "goto": "node_create_character"})
        
    # Always add the rules and sign out options at the bottom
    options.append({"desc": "Read the directives", "goto": "node_rules"})
    options.append({"desc": "Sign out", "goto": "node_quit"})
    
    return text, options


def node_select_character(caller, raw_string, **kwargs):
    """List the account's characters."""
    chars = list(caller.characters.all()) if hasattr(caller, "characters") else []

    if not chars:
        text = (
            "|rNo vessel on file.|n\n"
            "Your soul is not bound to any body. You went to the light, or you have never forged one.\n"
            "Choose |wForge a new soul|n from the main menu to create a character and enter the world.\n"
        )
        options = [{"desc": "Back to Soul Registry", "goto": "node_start"}]
        return text, options

    text = "|ySouls bound to your account:|n\n"
    options = []
    for char in chars:
        options.append({"desc": char.key, "goto": ("node_puppet_character", {"char": char})})
    options.append({"desc": "Back to Soul Registry", "goto": "node_start"})
    return text, options


def node_puppet_character(caller, raw_string, **kwargs):
    """Puppets the chosen character and cleanly closes the menu."""
    char = kwargs.get("char")

    if not char:
        caller.msg("|rError: No character selected.|n")
        return "node_start"

    sessions = caller.sessions.get() if hasattr(caller, "sessions") else []
    if not sessions:
        return "node_start"
    session = sessions[0]

    caller.msg("\n|gReturning to your body...|n\n")

    try:
        char.db._suppress_become_message = True
        caller.puppet_object(session, char)
    except RuntimeError:
        caller.msg("|rThat body is no longer available.|n")
        return "node_start"

    return "", None


def node_create_character(caller, raw_string, **kwargs):
    """Create a new character (forges a vessel and runs chargen). One per account."""
    chars = list(caller.characters.all()) if hasattr(caller, "characters") else []
    max_chars = getattr(settings, "MAX_NR_CHARACTERS", 1)
    if len(chars) >= max_chars:
        text = (
            "|rYou already have a vessel on file.|n\n"
            "One soul per account. Return to your body from the main menu, or go to the light and forge again.\n"
        )
        options = [{"desc": "Back to Soul Registry", "goto": "node_start"}]
        return text, options

    sessions = caller.sessions.get() if hasattr(caller, "sessions") else []
    if not sessions:
        return "node_start"
    session = sessions[0]

    # Create a blank character; at_post_puppet will run chargen (world.chargen)
    start_loc = getattr(settings, "DEFAULT_HOME", None)
    temp_name = "NewSoul_%s" % caller.id
    new_char = create_object(
        "typeclasses.characters.Character",
        key=temp_name,
        location=start_loc,
        home=start_loc,
    )
    if not new_char:
        caller.msg("|rThe registry could not forge a vessel. Try again or contact staff.|n")
        return "node_start"

    caller.characters.add(new_char)
    # Close the menu first so it doesn't stay stuck on screen after we puppet
    menu = getattr(caller.ndb, "_evmenu", None) if hasattr(caller, "ndb") else None
    if menu and hasattr(menu, "close_menu"):
        try:
            menu.close_menu()
        except Exception:
            pass
    caller.msg("\n|gForging a new vessel...|n\n")
    try:
        new_char.db._suppress_become_message = True  # no "You become NewSoul_..." before Rite
        caller.puppet_object(session, new_char)
    except RuntimeError:
        caller.msg("|rSomething went wrong. You remain at the registry.|n")
        return "node_start"
    return None  # Menu already closed; chargen runs in Character.at_post_puppet


def node_rules(caller, raw_string, **kwargs):
    """Short server directives."""
    text = (
        "|y*** DIRECTIVES ***|n\n"
        "1. Death is permanent. When you flatline and time runs out — or someone ends you — you are gone. Your body becomes a corpse. You may have a shard (clone) stored, or you may go to the light and forge a new soul.\n"
        "2. Stay in character. The world is harsh; play it straight.\n"
        "3. Do not exploit. Report bugs; do not abuse them.\n"
    )
    options = [{"desc": "Back to Soul Registry", "goto": "node_start"}]
    return text, options


def node_quit(caller, raw_string, **kwargs):
    """Disconnect from the game."""
    sessions = caller.sessions.get() if hasattr(caller, "sessions") else []
    caller.msg("|ySigning out. Goodbye.|n")
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
    # Don't run "look" on exit: after choosing a character we puppet and don't want any OOC/menu text re-sent.
    EvMenu(caller, "world.main_menu", startnode="node_start", cmd_on_exit=None)
