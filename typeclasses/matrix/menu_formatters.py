"""
Matrix Menu Formatters

Provides consistent cyberpunk-themed formatting for all matrix-related EvMenus.
These formatters style the automatic menu generation with appropriate colors
and layout for the matrix aesthetic.
"""


def matrix_options_formatter(optionlist, caller=None):
    """
    Format menu options with cyberpunk styling.

    Args:
        optionlist (list): List of (key, description) tuples from EvMenu
        caller: The object using the menu

    Returns:
        str: Formatted option text
    """
    if not optionlist:
        return ""

    # Filter out hidden options
    visible_options = [
        (key, desc) for key, desc in optionlist
        if key != "_default" and desc is not None
    ]

    if not visible_options:
        return ""

    # Add blank line before options, then format each option
    text = "\n"
    for key, desc in visible_options:
        text += f"|w{key}|n. {desc}\n"

    return text


def matrix_node_formatter(nodetext, optionstext, caller=None):
    """
    Format the complete node display (text + options).

    This combines the node's custom text with the formatted options,
    suppressing the default node name display.

    Args:
        nodetext (str): The text returned by the node function
        optionstext (str): The formatted options text
        caller: The object using the menu

    Returns:
        str: Complete formatted node display
    """
    # Ensure node text ends with exactly one newline before options
    if nodetext and not nodetext.endswith('\n'):
        nodetext += '\n'

    return nodetext + optionstext


def matrix_helptext_formatter(helptext, caller=None):
    """
    Format help text with matrix styling.

    Args:
        helptext (str): The help text to format
        caller: The object using the menu

    Returns:
        str: Formatted help text
    """
    if not helptext:
        return ""

    return f"\n|c[HELP]|n\n{helptext}\n"


# Convenience function to get all formatters at once
def get_matrix_formatters():
    """
    Get all matrix menu formatters as a dict for easy unpacking into EvMenu.

    Returns:
        dict: Dictionary with formatter function assignments

    Example:
        EvMenu(caller, module, startnode="start", **get_matrix_formatters())
    """
    return {
        "options_formatter": matrix_options_formatter,
        "node_formatter": matrix_node_formatter,
        "helptext_formatter": matrix_helptext_formatter,
    }
