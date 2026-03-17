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
        self.db.jack_in_message = "jacks into the Matrix"
        self.db.jack_out_message = "disconnects from the Matrix"

    def jack_in(self, character):
        """
        Jack a character into the Matrix.

        Creates an avatar at the router's location and switches the player's puppet.
        The router must exist in a Matrix node for this to work.

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

        # Find or create persistent avatar using stored dbref
        from typeclasses.matrix.avatars import MatrixAvatar
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
            from evennia.utils.create import create_object
            avatar = create_object(
                MatrixAvatar,
                key=avatar_name,
                location=target_node
            )

            if not avatar:
                if hasattr(character, 'msg'):
                    character.msg("Failed to create Matrix avatar.")
                return False

            # Link avatar and character
            avatar.db.real_character = character
            avatar.db.entry_device = self
            # Store avatar's dbref (not the object itself)
            character.db.matrix_avatar_dbref = avatar.pk

            # Set initial avatar description
            avatar.db.desc = "A formless blob of data with limitless potential, waiting to be shaped into something interesting."

            if needs_respawn:
                character.msg("|yYour previous avatar was lost. Respawning...|n")
        else:
            # Avatar exists and is valid, just reconnecting at current location
            avatar.db.entry_device = self
            avatar.db.idle = False

        # Show jack-in message to character and room
        character.msg("|gJacking in...|n")
        character.location.msg_contents(
            f"{character.name} {self.db.jack_in_message}.",
            exclude=character
        )

        # Switch puppet to avatar
        account = character.account
        if account:
            session = character.sessions.all()[0] if character.sessions.all() else None
            if session:
                account.puppet_object(session, avatar)

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
        # Look up avatar by dbref
        from typeclasses.matrix.avatars import MatrixAvatar
        avatar_dbref = character.db.matrix_avatar_dbref
        if not avatar_dbref:
            return

        try:
            avatar = MatrixAvatar.objects.get(pk=avatar_dbref)
        except MatrixAvatar.DoesNotExist:
            # Avatar was deleted
            character.db.matrix_avatar_dbref = None
            return

        # Get the account and session from avatar (since that's what's currently puppeted)
        account = avatar.account if hasattr(avatar, 'account') else None

        # Jack out the avatar (handles consequences based on severity)
        avatar.jack_out(reason=reason, severity=severity)

        # Don't clear the reference - avatar persists for reconnection
        # character.db.matrix_avatar stays set

        # Switch puppet back to character
        # Session is attached to avatar, not character
        if account:
            sessions = avatar.sessions.all()
            session = sessions[0] if sessions else None
            if session:
                account.puppet_object(session, character)
                character.msg("|rJacked out.|n")
                character.execute_cmd("look")

        # Show message to meatspace room where character's body is
        if character.location:
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
