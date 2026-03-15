"""
Examine: player-usable command hints for objects. Used by the examine command.
Hints are discovered from commands that declare usage_typeclasses + usage_hint—
so when you add a new command, set those on the command class and it will show up automatically.
"""
# Registry: list of (typeclass_path, hint_string). Built lazily from command classes.
_USAGE_REGISTRY = None


def _build_usage_registry():
    """Scan command module for Command classes with usage_typeclasses and usage_hint; fill registry."""
    from evennia.utils import logger
    global _USAGE_REGISTRY
    if _USAGE_REGISTRY is not None:
        return
    _USAGE_REGISTRY = []
    try:
        import commands.command as cmdmod
        from evennia.commands.command import Command as BaseCommand
        for name in dir(cmdmod):
            try:
                C = getattr(cmdmod, name)
                if not (isinstance(C, type) and issubclass(C, BaseCommand)):
                    continue
                typeclasses = getattr(C, "usage_typeclasses", None)
                hint = getattr(C, "usage_hint", None)
                if not typeclasses or not hint:
                    continue
                for tc in typeclasses:
                    if tc and hint:
                        _USAGE_REGISTRY.append((tc, hint))
            except Exception as e:
                logger.log_trace("examine._build_usage_registry: command %s: %s" % (name, e))
    except Exception as e:
        logger.log_trace("examine._build_usage_registry: %s" % e)


def get_usage_hints(obj):
    """
    Return a list of command hints for this object. Discovered from commands that
    declare usage_typeclasses (list of typeclass paths) and usage_hint (string).
    """
    from evennia.utils import logger
    if obj is None:
        return []
    _build_usage_registry()
    hints = []
    seen = set()
    for typeclass_path, hint in _USAGE_REGISTRY:
        try:
            if obj.is_typeclass(typeclass_path):
                if hint not in seen:
                    seen.add(hint)
                    hints.append(hint)
        except Exception as e:
            logger.log_trace("examine.get_usage_hints: is_typeclass(%s): %s" % (typeclass_path, e))
    # Medical tools: use <tool> on <target>, medical [target]
    try:
        if getattr(obj, "db", None) and getattr(obj.db, "medical_tool_type", None):
            key = getattr(obj, "key", "tool")
            hints.append(f"|wuse {key} on <target>|n, |wmedical [target]|n")
    except Exception as e:
        logger.log_trace("examine.get_usage_hints: medical_tool_type: %s" % e)
    # Defibrillator: defib <target> or use on dead target
    try:
        from typeclasses.medical_tools import Defibrillator
        if isinstance(obj, Defibrillator):
            key = getattr(obj, "key", "defibrillator")
            hints.append(f"|wdefib <target>|n, |wuse {key} on <target>|n (target must be in arrest)")
    except Exception as e:
        logger.log_trace("examine.get_usage_hints: Defibrillator: %s" % e)

    # Generic fallback for portable objects
    try:
        if not hints and hasattr(obj, "location") and getattr(obj, "location", None) is not None:
            if not obj.is_typeclass("typeclasses.rooms.Room") and not getattr(obj, "destination", None):
                hints.append("|wget|n, |wdrop|n, |wgive|n")
    except Exception as e:
        logger.log_trace("examine.get_usage_hints: fallback: %s" % e)
    return hints
