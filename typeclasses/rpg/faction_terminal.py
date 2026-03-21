"""
Faction registry terminal — in-world EvMenu for enlistment, roster, pay, etc.
"""

from typeclasses.objects import Object


class RegistryTerminal(Object):
    """
    A faction registry terminal. In-world object bound to db.faction_key.

    Attributes:
        db.faction_key (str): Faction abbreviation (e.g. IMP).
        db.terminal_name (str): Display name override.
        db.allow_public_info (bool): If True, non-members see faction blurb only.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.faction_key = None
        self.db.terminal_name = "Registry Terminal"
        self.db.allow_public_info = False
        self.locks.add("get:false()")
        self.locks.add("delete:false()")

    def get_display_name(self, looker, **kwargs):
        from world.rpg.factions import get_faction

        fdata = get_faction(self.db.faction_key)
        if fdata:
            return f"{fdata['color']}{fdata['short_name']} Registry Terminal|n"
        return "|wRegistry Terminal|n"

    def return_appearance(self, looker, **kwargs):
        from world.rpg.factions import get_faction

        fdata = get_faction(self.db.faction_key)
        if not fdata:
            return "A registry terminal. It appears to be offline."

        desc = (
            f"{fdata['color']}{'=' * 52}|n\n"
            f"  {fdata['color']}{fdata['name'].upper()} — REGISTRY TERMINAL|n\n"
            f"{fdata['color']}{'=' * 52}|n\n\n"
            f"  {fdata['description']}\n\n"
            f"  |xUse |wuse terminal|x or |wuse registry|x to access.|n\n"
        )
        return desc

    def use(self, caller):
        """Open the faction terminal EvMenu."""
        from world.rpg.factions.terminal_menu import start_faction_terminal

        start_faction_terminal(caller, self)

    def at_use(self, caller):
        """CmdUse dispatches here."""
        self.use(caller)
