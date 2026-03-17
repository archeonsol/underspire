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
JACKOUT_FATAL = 3       # Unsurvivable... Sorry


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
        self.db.idle = False

    def at_post_unpuppet(self, account=None, session=None, **kwargs):
        """
        When unpuppeting the avatar (jacking out), keep it in its current location.
        Do NOT set location to None - avatar stays where it is in the Matrix.
        """
        # Avatar stays in place - location is preserved for reconnection
        pass

    def check_connection(self):
        """
        Verify the physical connection to meatspace is still valid.

        Checks if:
        - Character still exists
        - Character is still sitting in the rig
        - Rig is still connected to the Matrix

        Returns:
            bool: True if connection is valid, False if disconnected
        """
        # Skip check if idle (not actively connected)
        if self.db.idle:
            return True

        character = self.db.real_character
        if not character or not character.pk:
            # Character deleted/invalid
            self.jack_out(reason="Physical body lost", severity=JACKOUT_FORCED)
            return False

        rig = self.db.entry_device
        if not rig or not rig.pk:
            # Rig deleted/invalid
            self.jack_out(reason="Connection device lost", severity=JACKOUT_FORCED)
            return False

        # Is character still sitting in the rig?
        if character.db.sitting_on != rig:
            self.jack_out(reason="Physical connection severed", severity=JACKOUT_FORCED)
            return False

        # Is the rig still connected to the Matrix?
        if not rig.is_connected():
            self.jack_out(reason="Network connection lost", severity=JACKOUT_EMERGENCY)
            return False

        return True

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
            self.msg(f"|rDISCO:|n {reason}")

            # Apply consequences based on severity
            if severity >= JACKOUT_FATAL:
                # Fatal jackout - avatar death causes real death
                # The dying consciousness is violently shoved back into the body
                self.msg("|rYour avatar dissolves into static and void.|n")
                self.msg("|rFor a brief, terrible moment, you see reality again—|n")
                self.msg("|rYour body in the rig, convulsing—|n")
                self.msg("|rThen nothing.|n")
                # TODO: Kill the real character
                # TODO: Apply fatal consequences (permadeath or severe penalty)
                pass
            elif severity >= JACKOUT_FORCED:
                # Violent disconnect - physical damage
                # TODO: Apply physical damage to real character
                pass
            elif severity >= JACKOUT_EMERGENCY:
                # Uncontrolled disconnect - minor penalties
                # TODO: Apply minor penalties (disorientation, stamina loss, etc.)
                pass

            # TODO: Return control to real character

        # Mark as idle for cleanup later
        self.db.idle = True
        self.db.idle_since = None  # TODO: Set timestamp when we implement grace period

    def get_display_desc(self, looker, **kwargs):
        """
        Get the description for this Matrix avatar.

        Uses the general_desc attribute (set via @dmas command) if set, otherwise falls back to desc.

        Args:
            looker: The object looking at this avatar

        Returns:
            str: The description text
        """
        return self.db.general_desc or self.db.desc or "A generic Matrix avatar."
