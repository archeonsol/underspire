"""
Cyberware Customization Station — in-room fixture for chromework.
Put cyberware in the station, then use the station to customize color and descriptions.
Requires Electrical Engineering 75. Unmovable, unpickable.
"""

from typeclasses.objects import Object


# Default description for the station (set at creation if not customized)
DEFAULT_STATION_DESC = (
    "A heavy workbench with a laser engraver, calibration screens, and chrome fixtures. "
    "The machinery hums faintly, ready for customization work."
)


class CyberwareCustomizationStation(Object):
    """
    A stationary workstation for customizing cyberware before installation.
    Players put cyberware in the station, then use it to run the chromework menu.
    """

    # CmdPut allows insert when get:false(); see commands.base_cmds.CmdPut
    fixture_allows_put_without_get = True

    def at_object_creation(self):
        super().at_object_creation()
        self.locks.add("get:false();move:false()")
        if self.db.desc is None:
            self.db.desc = DEFAULT_STATION_DESC

    def at_pre_object_receive(self, arriving_object, source_location, **kwargs):
        """Only accept uninstalled CyberwareBase. One piece at a time.

        Signature must match Evennia DefaultObject (move_to passes move_type=... etc.).
        """
        from typeclasses.cyberware import CyberwareBase

        who = source_location
        if not isinstance(arriving_object, CyberwareBase):
            if who and hasattr(who, "msg"):
                who.msg("You can only put cyberware in the customization station.")
            return False
        if getattr(arriving_object.db, "installed", False):
            if who and hasattr(who, "msg"):
                who.msg("Chromework must be done before installation. Uninstall it first.")
            return False
        contents = self.contents or []
        if any(isinstance(c, CyberwareBase) for c in contents):
            if who and hasattr(who, "msg"):
                who.msg("There is already a piece of chrome in the station. Retrieve it first.")
            return False
        return True

    def at_object_receive(self, moved_obj, source_location, move_type="move", **kwargs):
        """Called after cyberware is placed in the station."""
        pass
