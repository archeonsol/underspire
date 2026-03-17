"""
Matrix Devices

Physical devices that provide Matrix connectivity and interfaces.

DiveRig - Reclined chair for jacking into the Matrix (combines Seat + NetworkedObject)
"""

from evennia.utils.create import create_object
from typeclasses.seats import Seat
from typeclasses.matrix.objects import NetworkedObject
from typeclasses.matrix.mixins import PuppetRigMixin
from typeclasses.matrix.avatars import MatrixAvatar, JACKOUT_FORCED, JACKOUT_EMERGENCY


class DiveRig(PuppetRigMixin, Seat, NetworkedObject):
    """
    Reclined chair for jacking into the Matrix.

    Combines seating functionality with Matrix connectivity. When a character
    sits in the rig and jacks in, their avatar appears in the linked Matrix node
    and the player's puppet switches to control the avatar.

    The character's body remains vulnerable in meatspace while diving.

    Attributes:
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
        self.db.jack_in_message = "jacks into the Matrix"
        self.db.jack_out_message = "disconnects from the Matrix"
        self.db.jack_in_transition_msg = "|cThe room seems to be sucked out of existence...|n"
        self.db.normal_jackout_msg = "|cYou feel your awareness being drawn back through the Matrix and into your body.|n"
        self.db.emergency_jackout_msg = "|yYou feel your awareness being urgently pulled back through the Matrix...|n"
        self.db.forced_jackout_msg = "|rYou feel your consciousness being violently ripped back through the Matrix!|n"

    def jack_in(self, character):
        """
        Jack a character into the Matrix.

        Creates an avatar at the router's location and switches the player's puppet.

        Args:
            character (Character): The character jacking in

        Returns:
            bool: True if successful, False otherwise
        """
        return self.puppet_in(character)

    def jack_out_character(self, character, severity=0, reason="Disconnecting"):
        """
        Jack out a character from the Matrix.

        Called when the character needs to disconnect (voluntary or forced).

        Args:
            character (Character): The meatspace character
            severity (int): Jack-out severity level
            reason (str): Reason for disconnect
        """
        # Look up avatar and tell it to jack out (applies consequences)
        avatar = self.get_current_puppet(character)
        if avatar and hasattr(avatar, 'jack_out'):
            avatar.jack_out(reason=reason, severity=severity)

        # Puppet back to character
        self.puppet_out(character, severity=severity, reason=reason)

    # PuppetRigMixin required methods

    def validate_connection(self, character):
        """
        Validate that Matrix connection is available.

        Returns:
            bool: True if connection is valid, False otherwise
        """
        # Get the router
        router = self.get_relay()
        if not router:
            if hasattr(character, 'msg'):
                character.msg("No Matrix connection available. Room not linked to a router.")
            return False

        # Check if router is online
        if not router.db.online:
            if hasattr(character, 'msg'):
                character.msg("Router is offline. No Matrix connection available.")
            return False

        # Get target node from router's location
        target_node = router.location
        if not target_node:
            if hasattr(character, 'msg'):
                character.msg("Router is not properly configured (no Matrix location).")
            return False

        return True

    def get_puppet_target(self, character):
        """
        Get or create the Matrix avatar for this character.

        Returns:
            MatrixAvatar: The avatar object, or None if creation failed
        """
        # Get the router to determine spawn location
        router = self.get_relay()
        target_node = router.location if router else None

        if not target_node:
            return None

        # Find or create persistent avatar using stored dbref
        avatar_dbref = character.db.matrix_avatar_dbref
        avatar = None

        # Look up avatar by dbref if we have one
        if avatar_dbref:
            try:
                avatar = MatrixAvatar.objects.get(pk=avatar_dbref)
            except MatrixAvatar.DoesNotExist:
                # Avatar was deleted
                character.db.matrix_avatar_dbref = None

        # Determine if we need to respawn avatar
        needs_respawn = False
        if avatar:
            # Check if avatar is dead
            if getattr(avatar.db, 'dead', False):
                needs_respawn = True
                # Dump inventory into the room before deleting
                if avatar.location:
                    for item in avatar.contents:
                        item.move_to(avatar.location, quiet=True)
                # Clean up old dead avatar
                avatar.delete()
                avatar = None
            # Check if avatar's location still exists
            elif not avatar.location or not avatar.location.pk:
                needs_respawn = True
                # Location vanished, respawn at entry point
                avatar.location = target_node

        # Create avatar if it doesn't exist or needs respawn
        if not avatar:
            avatar_name = f"{character.key} (Avatar)"
            avatar = create_object(
                MatrixAvatar,
                key=avatar_name,
                location=target_node
            )

            if not avatar:
                return None

            # Link avatar and character
            avatar.db.real_character = character
            # Store avatar's dbref (not the object itself)
            character.db.matrix_avatar_dbref = avatar.pk

            # Set initial avatar description
            avatar.db.desc = "A formless blob of data with limitless potential, waiting to be shaped into something interesting."

            if needs_respawn:
                character.msg("|yYour previous avatar was lost. Respawning...|n")

        return avatar

    def get_current_puppet(self, character):
        """
        Get the currently puppeted avatar for this character.

        Returns:
            MatrixAvatar: The avatar object, or None if not connected
        """
        avatar_dbref = character.db.matrix_avatar_dbref
        if not avatar_dbref:
            return None

        try:
            return MatrixAvatar.objects.get(pk=avatar_dbref)
        except MatrixAvatar.DoesNotExist:
            # Avatar was deleted
            character.db.matrix_avatar_dbref = None
            return None

    def cleanup_on_disconnect(self, character):
        """
        Clean up when connection is forcibly broken.

        For DiveRig, avatar persists in the Matrix - no cleanup needed.
        """
        pass

    # Rig lifecycle methods

    def at_object_delete(self):
        """Clean up when rig is destroyed."""
        # Force disconnect anyone using the rig
        sitter = self.get_sitter()
        if sitter and hasattr(sitter.db, 'matrix_avatar_dbref') and sitter.db.matrix_avatar_dbref:
            self.jack_out_character(sitter, severity=JACKOUT_FORCED, reason="Dive rig destroyed")

        return super().at_object_delete()

    def handle_disconnect(self):
        """
        Called when the rig loses Matrix connectivity.

        Emergency jacks out anyone currently diving.
        """
        sitter = self.get_sitter()
        if sitter and hasattr(sitter.db, 'matrix_avatar_dbref') and sitter.db.matrix_avatar_dbref:
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
        if hasattr(character.db, 'matrix_avatar_dbref') and character.db.matrix_avatar_dbref:
            self.jack_out_character(
                character,
                severity=JACKOUT_FORCED,
                reason="Forcibly disconnected!"
            )
