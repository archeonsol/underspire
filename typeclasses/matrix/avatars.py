"""
Matrix Avatars

Virtual representations of characters diving the Matrix.

MatrixAvatar - Temporary character object created when jacking into the Matrix
"""

from evennia import DefaultCharacter

# Jack-out severity levels
JACKOUT_NORMAL = 0      # Clean logout, no penalties
JACKOUT_EMERGENCY = 1   # Uncontrolled disconnect, minor penalties
JACKOUT_FORCED = 2      # Violent disconnect, physical damage


class MatrixAvatar(DefaultCharacter):
    """
    Virtual representation of a character diving the Matrix.

    Created when a character jacks in through a device, destroyed when they jack out.
    Simpler than physical characters - no body parts, injuries, or complex inventory.

    Attributes:
        real_character (Character): Link back to the meatspace character
        entry_device (NetworkedObject/NetworkedItem): Device used to jack in
    """

    def at_object_creation(self):
        """Called when avatar is first created."""
        super().at_object_creation()
        self.db.real_character = None
        self.db.entry_device = None

    def jack_out(self, reason="Disconnecting", severity=JACKOUT_NORMAL):
        """
        Disconnect from the Matrix and return to meatspace.

        Marks the avatar as idle rather than deleting immediately.
        Cleanup happens later via the cleanup script.

        Args:
            reason (str): Why the disconnect happened (shown to user)
            severity (int): Severity level (JACKOUT_NORMAL, JACKOUT_EMERGENCY, JACKOUT_FORCED)
        """
        if self.db.real_character:
            self.msg(f"|rJacking out:|n {reason}")

            # Apply consequences based on severity
            if severity >= JACKOUT_FORCED:
                # TODO: Apply physical damage to real character
                pass
            elif severity >= JACKOUT_EMERGENCY:
                # TODO: Apply minor penalties (disorientation, stamina loss, etc.)
                pass

            # TODO: Transfer collected data items back to real character
            # TODO: Return control to real character

        # Mark as idle for cleanup later
        self.db.idle = True
        self.db.idle_since = None  # TODO: Set timestamp when we implement grace period
