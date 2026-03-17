"""
Matrix Avatars

Virtual representations of characters diving the Matrix.

MatrixAvatar - Virtual character object created when jacking into the Matrix
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

    Created when a character jacks in through a device. Persists in the Matrix
    until destroyed. Simpler than physical characters - no body parts, injuries,
    or complex inventory.

    The DiveRig owns the connection state - avatars are just puppets.

    Attributes:
        entry_device (DiveRig): The rig this avatar is connected through
        dead (bool): Whether this avatar has been killed
    """

    def at_object_creation(self):
        """Called when avatar is first created."""
        super().at_object_creation()
        self.db.entry_device = None
        self.db.dead = False

    def at_object_delete(self):
        """
        Called before avatar is deleted.

        Triggers disconnection if the avatar is being destroyed while connected.
        """
        rig = self.db.entry_device
        if rig and hasattr(rig, 'db') and rig.db.active_connection:
            conn = rig.db.active_connection
            if conn and conn.get('avatar') == self:
                character = conn.get('character')
                if character:
                    # Avatar being destroyed - force disconnect
                    rig.disconnect(character, severity=JACKOUT_FORCED, reason="Avatar destroyed")

        return super().at_object_delete()

    def at_post_unpuppet(self, account=None, session=None, **kwargs):
        """
        When unpuppeting the avatar (jacking out), keep it in its current location.
        Do NOT set location to None - avatar stays where it is in the Matrix.
        """
        # Avatar stays in place - location is preserved for reconnection
        pass

    def at_pre_death(self):
        """
        Called when avatar is about to die.

        Triggers FATAL jack-out - character body dies too.
        """
        rig = self.db.entry_device
        if rig and hasattr(rig, 'db') and rig.db.active_connection:
            conn = rig.db.active_connection
            if conn and conn.get('avatar') == self:
                character = conn.get('character')
                if character:
                    # Mark avatar as dead
                    self.db.dead = True
                    # Fatal disconnect - character dies too
                    rig.disconnect(character, severity=JACKOUT_FATAL, reason="Avatar killed")

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
