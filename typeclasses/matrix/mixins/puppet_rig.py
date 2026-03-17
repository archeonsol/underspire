"""
Puppet Rig Mixin

Shared functionality for rigs that puppet characters into other objects/avatars.

PuppetRigMixin - Handles staged puppet transitions and connection validation
"""

from evennia.utils import delay


class PuppetRigMixin:
    """
    Mixin for rigs that switch a character's puppet to another object.

    Provides staged transitions with delays and consciousness changes for
    immersive jack-in/out sequences. Subclasses must implement methods to
    get/create the target puppet object.

    Required methods to implement:
        get_puppet_target(character): Get or create the object to puppet into
        validate_connection(character): Check if connection requirements are met
        cleanup_on_disconnect(character): Clean up when forcibly disconnected

    Optional attributes to set:
        jack_in_message (str): Message shown to room when jacking in
        jack_out_message (str): Message shown to room when jacking out
        jack_in_transition_msg (str): Message shown to character during jack in
        normal_jackout_msg (str): Message for clean disconnect
        emergency_jackout_msg (str): Message for emergency disconnect
        forced_jackout_msg (str): Message for forced disconnect
    """

    def puppet_in(self, character):
        """
        Puppet a character into the target object.

        Uses a staged sequence with delays:
        1. Initial message
        2. 1s delay -> character loses consciousness + transition message
        3. 1s delay -> puppet swap + look

        Args:
            character (Character): The character puppeting in

        Returns:
            bool: True if successful, False otherwise
        """
        # Verify character is sitting in the rig
        if character.db.sitting_on != self:
            if hasattr(character, 'msg'):
                character.msg("You must be sitting in the rig first.")
            return False

        # Let subclass validate connection requirements
        if not self.validate_connection(character):
            return False

        # Get the target object to puppet into
        target = self.get_puppet_target(character)
        if not target:
            if hasattr(character, 'msg'):
                character.msg("Failed to establish connection.")
            return False

        # Link target back to character and rig
        target.db.real_character = character
        target.db.entry_device = self
        target.db.idle = False

        # Staged puppet-in sequence
        jack_in_msg = getattr(self.db, 'jack_in_message', 'connects to the system')
        character.msg("|gConnecting...|n")
        character.location.msg_contents(
            f"{character.name} {jack_in_msg}.",
            exclude=character
        )

        # Stage 1: After 1 second, character loses consciousness
        delay(1, self._puppet_in_stage1, character, target)

        return True

    def _puppet_in_stage1(self, character, target):
        """Stage 1: Character loses consciousness."""
        character.db.conscious = False
        transition_msg = getattr(self.db, 'jack_in_transition_msg',
                                "|cThe room seems to be sucked out of existence...|n")
        character.msg(transition_msg)

        # Stage 2: After another second, puppet swap
        delay(1, self._puppet_in_stage2, character, target)

    def _puppet_in_stage2(self, character, target):
        """Stage 2: Switch puppet to target."""
        account = character.account
        if account:
            session = character.sessions.all()[0] if character.sessions.all() else None
            if session:
                account.puppet_object(session, target)
                target.execute_cmd("look")

    def puppet_out(self, character, severity=0, reason="Disconnecting"):
        """
        Puppet a character back to their body.

        Uses a staged sequence with delays:
        1. Initial DISCO message
        2. 1s delay -> target loses consciousness + severity-based message
        3. 1s delay -> puppet swap
        4. 1s delay -> character regains consciousness + final message + look

        Args:
            character (Character): The meatspace character
            severity (int): Disconnect severity (0=normal, 1=emergency, 2=forced)
            reason (str): Reason for disconnect
        """
        # Get the puppet target
        target = self.get_current_puppet(character)
        if not target:
            return

        # Get account from target (since that's what's currently puppeted)
        account = target.account if hasattr(target, 'account') else None

        # Send initial DISCO message to target
        target.msg(f"|rDISCO:|n {reason}")

        # Staged puppet-out sequence
        delay(1, self._puppet_out_stage1, character, target, severity, account)

    def _puppet_out_stage1(self, character, target, severity, account):
        """Stage 1: Target becomes unconscious, show transition message."""
        target.db.conscious = False

        # Different messages based on severity
        if severity >= 2:  # FORCED
            msg = getattr(self.db, 'forced_jackout_msg',
                         "|rYou feel your consciousness being violently ripped back!|n")
        elif severity >= 1:  # EMERGENCY
            msg = getattr(self.db, 'emergency_jackout_msg',
                         "|yYou feel your awareness being urgently pulled back...|n")
        else:  # NORMAL
            msg = getattr(self.db, 'normal_jackout_msg',
                         "|cYou feel your awareness being drawn back into your body.|n")

        target.msg(msg)

        # Stage 2: After another second, puppet swap
        delay(1, self._puppet_out_stage2, character, target, account)

    def _puppet_out_stage2(self, character, target, account):
        """Stage 2: Switch puppet back to character."""
        if account:
            sessions = target.sessions.all()
            session = sessions[0] if sessions else None
            if session:
                account.puppet_object(session, character)

                # Stage 3: After another second, regain consciousness
                delay(1, self._puppet_out_stage3, character)

    def _puppet_out_stage3(self, character):
        """Stage 3: Character regains consciousness."""
        character.db.conscious = True
        character.msg("|rDISCO.|n")

        # Show message to room where character's body is
        if character.location:
            jack_out_msg = getattr(self.db, 'jack_out_message', 'disconnects from the system')
            character.location.msg_contents(
                f"{character.name} {jack_out_msg}.",
                exclude=character
            )

        character.execute_cmd("look")

    # Methods that subclasses must implement

    def get_puppet_target(self, character):
        """
        Get or create the object to puppet into.

        Args:
            character (Character): The character connecting

        Returns:
            Object: The target object, or None if creation failed
        """
        raise NotImplementedError("Subclass must implement get_puppet_target()")

    def get_current_puppet(self, character):
        """
        Get the currently puppeted object for this character.

        Args:
            character (Character): The meatspace character

        Returns:
            Object: The puppeted object, or None if not connected
        """
        raise NotImplementedError("Subclass must implement get_current_puppet()")

    def validate_connection(self, character):
        """
        Validate that connection requirements are met.

        Args:
            character (Character): The character attempting to connect

        Returns:
            bool: True if connection is allowed, False otherwise
        """
        raise NotImplementedError("Subclass must implement validate_connection()")

    def cleanup_on_disconnect(self, character):
        """
        Clean up when connection is forcibly broken.

        Args:
            character (Character): The character being disconnected
        """
        raise NotImplementedError("Subclass must implement cleanup_on_disconnect()")
