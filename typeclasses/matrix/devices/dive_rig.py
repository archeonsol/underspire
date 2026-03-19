"""
Matrix Devices

Physical devices that provide Matrix connectivity and interfaces.

DiveRig - Reclined chair for jacking into the Matrix (combines Seat + NetworkedObject)
"""

from typeclasses.seats import Seat
from typeclasses.matrix.objects import NetworkedObject
from typeclasses.matrix.mixins.jack_in import JackInMixin
from typeclasses.matrix.avatars import JACKOUT_FORCED, JACKOUT_EMERGENCY


class DiveRig(JackInMixin, Seat, NetworkedObject):
    """
    Reclined chair for jacking into the Matrix.

    Combines seating functionality with Matrix connectivity. When a character
    sits in the rig and jacks in, their avatar appears in the linked Matrix node
    and the player's puppet switches to control the avatar.

    The character's body remains vulnerable in meatspace while diving.

    The rig owns the connection state between character and avatar.

    Attributes:
        active_connection (dict): {
            'character': Character ref,
            'avatar': MatrixAvatar ref,
            'connected_at': timestamp
        } or None when disconnected
        jack_in_message (str): Custom message shown when jacking in
        jack_out_message (str): Custom message shown when jacking out normally
    """

    def at_object_creation(self):
        """Called when the rig is first created."""
        super().at_object_creation()
        self.setup_networked_attrs()
        self.setup_jack_in_attrs()

        # DiveRig specific attributes
        self.db.device_type = "dive_rig"
        self.db.ephemeral_node = False  # Rigs connect to persistent nodes

        # Room display message when someone is jacked in (diving)
        # Placeholder: {name} = character display name, {obj} = rig display name
        if self.db.diving_msg is None:
            self.db.diving_msg = "{name} is jacked into the Matrix, diving through {obj}."

    # ========================================
    # Hook overrides — rig-specific preconditions
    # ========================================

    def _get_jack_in_errors(self, character):
        """Require character to be seated in the rig before passing to base checks."""
        if character.db.sitting_on != self:
            return ["You must be sitting in the rig first."]
        return super()._get_jack_in_errors(character)

    def _get_connection_errors(self, character):
        """Connection breaks if character is no longer seated in the rig."""
        sitting_on = character.db.sitting_on
        if not sitting_on or sitting_on.pk != self.pk:
            return [("Physical connection severed", JACKOUT_FORCED)]
        return super()._get_connection_errors(character)

    # ========================================
    # Event Handlers
    # ========================================

    def at_object_delete(self):
        """Clean up when rig is destroyed."""
        conn = self.db.active_connection
        if conn:
            character = conn.get('character')
            if character:
                self.disconnect(character, severity=JACKOUT_FORCED, reason="Dive rig destroyed")
        return super().at_object_delete()

    def handle_disconnect(self):
        """
        Called when the rig loses Matrix connectivity (router goes down, etc.).

        Emergency jacks out anyone currently diving.
        """
        conn = self.db.active_connection
        if conn:
            character = conn.get('character')
            if character:
                self.disconnect(character, severity=JACKOUT_EMERGENCY, reason="Connection lost")

    def handle_forced_removal(self, character):
        """
        Called when someone is forcibly removed from the rig (grappled, etc.).

        Forces violent jack-out with physical consequences.

        Args:
            character (Character): Character being removed
        """
        conn = self.db.active_connection
        if not conn:
            return
        conn_character = conn.get('character')
        if conn_character and conn_character.pk == character.pk:
            self.disconnect(character, severity=JACKOUT_FORCED, reason="Forcibly disconnected!")

    # ========================================
    # Display / Query
    # ========================================

    def get_room_appearance(self, looker, **kwargs):
        """
        Return how this dive rig appears in the room description.
        Shows special diving message when character is jacked into the Matrix.

        Args:
            looker: The character looking at the room
            **kwargs: Additional options

        Returns:
            str: The formatted display string, or empty string if nothing to show
        """
        from typeclasses.rooms import ROOM_DESC_CHARACTER_NAME_COLOR, ROOM_DESC_OBJECT_NAME_COLOR

        sitter = self.get_sitter()
        obj_name = self.get_display_name(looker, **kwargs)

        if not sitter:
            template = self.get_empty_template()
            return template.format(obj=f"{ROOM_DESC_OBJECT_NAME_COLOR}{obj_name}|n", name="")

        if sitter != looker:
            location = self.location
            if location and hasattr(location, 'filter_visible'):
                if not location.filter_visible([sitter], looker, **kwargs):
                    template = self.get_empty_template()
                    return template.format(obj=f"{ROOM_DESC_OBJECT_NAME_COLOR}{obj_name}|n", name="")

        is_diving = self.is_character_diving(sitter)

        if sitter == looker:
            char_name = f"{ROOM_DESC_CHARACTER_NAME_COLOR}You|n"
            verb = "are"
        else:
            char_name = sitter.get_display_name(looker, **kwargs)
            char_name = f"{ROOM_DESC_CHARACTER_NAME_COLOR}{char_name}|n"
            verb = "is"

        if is_diving:
            template = self.db.diving_msg or "{name} is jacked into the Matrix, diving through {obj}."
        else:
            template = self.get_occupied_template()

        template = template.replace(" is ", f" {verb} ")

        return template.format(
            name=char_name,
            obj=f"{ROOM_DESC_OBJECT_NAME_COLOR}{obj_name}|n"
        )
