"""
MobileDiveRig

Cyberware implant that lets a character jack into the Matrix without a physical dive rig.
Must be in the character's inventory to use. All core jack-in logic lives in JackInMixin;
this class only adds the inventory precondition.
"""

from typeclasses.matrix.objects import NetworkedObject
from typeclasses.matrix.mixins.jack_in import JackInMixin
from typeclasses.matrix.avatars import JACKOUT_FORCED, JACKOUT_EMERGENCY


class MobileDiveRig(JackInMixin, NetworkedObject):
    """
    Neural implant providing Matrix connectivity.

    Functions identically to a DiveRig but requires no seat — the character just
    needs the implant in their inventory. Coverage detection works automatically
    since get_containing_room() walks implant → character → room.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.setup_networked_attrs()
        self.setup_jack_in_attrs()
        self.db.device_type = "implant"

    # ========================================
    # Hook overrides — implant-specific preconditions
    # ========================================

    def _get_jack_in_errors(self, character):
        """Require implant to be in the character's inventory."""
        if self.location != character:
            return ["The implant must be in your possession to jack in."]
        return super()._get_jack_in_errors(character)

    def _get_connection_errors(self, character):
        """Connection breaks if implant leaves the character's inventory."""
        if self.location != character:
            return [("Neural implant removed from possession", JACKOUT_FORCED)]
        return super()._get_connection_errors(character)

    # ========================================
    # Event Handlers
    # ========================================

    def handle_disconnect(self):
        """Called when the implant loses Matrix connectivity (router goes down, etc.)."""
        conn = self.db.active_connection
        if conn:
            character = conn.get('character')
            if character:
                self.disconnect(character, severity=JACKOUT_EMERGENCY, reason="Connection lost")
