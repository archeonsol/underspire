"""
Matrix Devices

Physical devices that provide Matrix connectivity and interfaces.

DiveRig - Reclined chair for jacking into the Matrix (combines Seat + NetworkedObject)
"""

from typeclasses.seats import Seat
from typeclasses.matrix.objects import NetworkedObject
from typeclasses.matrix.avatars import MatrixAvatar, JACKOUT_FORCED, JACKOUT_EMERGENCY


class DiveRig(Seat, NetworkedObject):
    """
    Reclined chair for jacking into the Matrix.

    Combines seating functionality with Matrix connectivity. When a character
    sits in the rig and jacks in, their avatar appears in the linked Matrix node
    and the player's puppet switches to control the avatar.

    The character's body remains vulnerable in meatspace while diving.

    Attributes:
        target_node (MatrixNode): The Matrix node this rig connects to
        jack_in_message (str): Custom message shown when jacking in
        jack_out_message (str): Custom message shown when jacking out normally
    """

    def at_object_creation(self):
        """Called when the rig is first created."""
        super().at_object_creation()
        self.setup_networked_attrs()

        # DiveRig specific attributes
        self.db.device_type = "dive_rig"
        self.db.ephemeral_node = False  # Rigs connect to persistent nodes
        self.db.target_node = None
        self.db.jack_in_message = "jacks into the Matrix"
        self.db.jack_out_message = "disconnects from the Matrix"

    def jack_in(self, character):
        """
        Jack a character into the Matrix.

        Creates an avatar in the target node and switches the player's puppet.

        Args:
            character (Character): The character jacking in

        Returns:
            bool: True if successful, False otherwise
        """
        # Verify character is sitting in the rig
        if character.db.sitting_on != self:
            if hasattr(character, 'msg'):
                character.msg("You must be sitting in the dive rig first.")
            return False

        # Verify rig has a target node
        if not self.db.target_node:
            if hasattr(character, 'msg'):
                character.msg("This dive rig is not linked to a Matrix node.")
            return False

        # Verify rig is connected to the Matrix
        if not self.is_connected():
            if hasattr(character, 'msg'):
                character.msg("No Matrix connection available.")
            return False

        # Check if character already has an avatar (shouldn't happen, but safety check)
        if hasattr(character.db, 'matrix_avatar') and character.db.matrix_avatar:
            if hasattr(character, 'msg'):
                character.msg("You are already jacked in.")
            return False

        # Create the avatar
        avatar_name = f"{character.key} (Avatar)"
        avatar = MatrixAvatar.create(
            key=avatar_name,
            location=self.db.target_node
        )

        if not avatar:
            if hasattr(character, 'msg'):
                character.msg("Failed to create Matrix avatar.")
            return False

        # Link avatar and character
        avatar.db.real_character = character
        avatar.db.entry_device = self
        character.db.matrix_avatar = avatar

        # Copy appearance/description if desired
        if hasattr(character.db, 'matrix_desc'):
            avatar.db.desc = character.db.matrix_desc

        # Show jack-in message to room
        character.location.msg_contents(
            f"{character.name} {self.db.jack_in_message}.",
            exclude=character
        )

        # Switch puppet to avatar
        account = character.account
        if account:
            account.puppet_object(character.sessions.get(), avatar)
            avatar.msg("|gJacking in...|n")
            avatar.execute_cmd("look")

        return True

    def jack_out_character(self, character, severity=0, reason="Disconnecting"):
        """
        Jack out a character from the Matrix.

        Called when the character needs to disconnect (voluntary or forced).

        Args:
            character (Character): The meatspace character
            severity (int): Jack-out severity level
            reason (str): Reason for disconnect
        """
        avatar = character.db.matrix_avatar
        if not avatar:
            return

        # Get the account before we do anything else
        account = character.account

        # Jack out the avatar (handles consequences based on severity)
        avatar.jack_out(reason=reason, severity=severity)

        # Clean up character's reference
        character.db.matrix_avatar = None

        # Switch puppet back to character
        if account:
            account.puppet_object(character.sessions.get(), character)
            character.msg("|rJacked out.|n")
            character.execute_cmd("look")

        # Show message to room
        character.location.msg_contents(
            f"{character.name} {self.db.jack_out_message}.",
            exclude=character
        )

    def at_object_delete(self):
        """Clean up when rig is destroyed."""
        # Force disconnect anyone using the rig
        sitter = self.get_sitter()
        if sitter and hasattr(sitter.db, 'matrix_avatar') and sitter.db.matrix_avatar:
            self.jack_out_character(sitter, severity=JACKOUT_FORCED, reason="Dive rig destroyed")

        return super().at_object_delete()

    def handle_disconnect(self):
        """
        Called when the rig loses Matrix connectivity.

        Emergency jacks out anyone currently diving.
        """
        sitter = self.get_sitter()
        if sitter and hasattr(sitter.db, 'matrix_avatar') and sitter.db.matrix_avatar:
            self.jack_out_character(
                sitter,
                severity=JACKOUT_EMERGENCY,
                reason="Connection lost"
            )

    def handle_forced_removal(self, character):
        """
        Called when someone is forcibly removed from the rig (grappled, etc.).

        Forces violent jack-out with physical consequences.

        Args:
            character (Character): Character being removed
        """
        if hasattr(character.db, 'matrix_avatar') and character.db.matrix_avatar:
            self.jack_out_character(
                character,
                severity=JACKOUT_FORCED,
                reason="Forcibly disconnected!"
            )
