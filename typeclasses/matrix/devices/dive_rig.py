"""
Matrix Devices

Physical devices that provide Matrix connectivity and interfaces.

DiveRig - Reclined chair for jacking into the Matrix (combines Seat + NetworkedObject)
"""

from evennia.utils.create import create_object
from evennia.utils import delay
from typeclasses.seats import Seat
from typeclasses.matrix.objects import NetworkedObject
from typeclasses.matrix.avatars import MatrixAvatar, JACKOUT_FORCED, JACKOUT_EMERGENCY, JACKOUT_FATAL, JACKOUT_NORMAL


class DiveRig(Seat, NetworkedObject):
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

        # DiveRig specific attributes
        self.db.device_type = "dive_rig"
        self.db.ephemeral_node = False  # Rigs connect to persistent nodes
        self.db.active_connection = None  # The connection state

        # Messages
        self.db.jack_in_message = "jacks into the Matrix"
        self.db.jack_out_message = "disconnects from the Matrix"
        self.db.jack_in_transition_msg = "|cThe room seems to be sucked out of existence...|n"
        self.db.normal_jackout_msg = "|cYou feel your awareness being drawn back through the Matrix and into your body.|n"
        self.db.emergency_jackout_msg = "|yYou feel your awareness being urgently pulled back through the Matrix...|n"
        self.db.forced_jackout_msg = "|rYou feel your consciousness being violently ripped back through the Matrix!|n"
        self.db.fatal_jackout_msg = "|rThe world fractures. Your avatar is dying. The Matrix ejects your consciousness like poison—|n"

        # Room display message when someone is jacked in (diving)
        # Placeholder: {name} = character display name, {obj} = rig display name
        if getattr(self.db, "diving_msg", None) is None:
            self.db.diving_msg = "{name} is jacked into the Matrix, diving through {obj}."

    # ========================================
    # Connection Management (Primary API)
    # ========================================

    def jack_in(self, character):
        """
        Jack a character into the Matrix.

        Creates an avatar at the router's location and switches the player's puppet.

        Args:
            character (Character): The character jacking in

        Returns:
            bool: True if successful, False otherwise
        """
        # Verify character is sitting in the rig
        if character.db.sitting_on != self:
            if hasattr(character, 'msg'):
                character.msg("You must be sitting in the rig first.")
            return False

        # Validate connection requirements
        router = self.get_relay()
        if not router:
            if hasattr(character, 'msg'):
                character.msg("No Matrix connection available. Room not linked to a router.")
            return False

        if not router.db.online:
            if hasattr(character, 'msg'):
                character.msg("Router is offline. No Matrix connection available.")
            return False

        target_node = router.location
        if not target_node:
            if hasattr(character, 'msg'):
                character.msg("Router is not properly configured (no Matrix location).")
            return False

        # Get or create the avatar
        avatar = self._get_or_create_avatar(character, target_node)
        if not avatar:
            if hasattr(character, 'msg'):
                character.msg("Failed to establish connection.")
            return False

        # Link avatar back to rig
        avatar.db.entry_device = self

        # Establish active connection
        from evennia.utils import gametime
        self.db.active_connection = {
            'character': character,
            'avatar': avatar,
            'connected_at': gametime.gametime()
        }

        # Staged jack-in sequence
        character.msg("|gConnecting...|n")
        character.location.msg_contents(
            f"{character.name} {self.db.jack_in_message}.",
            exclude=character
        )

        # Stage 1: After 1 second, character loses consciousness
        delay(1, self._jack_in_stage1, character, avatar)

        return True

    def disconnect(self, character, severity=JACKOUT_NORMAL, reason="Disconnecting"):
        """
        Disconnect a character from the Matrix.

        This is the primary disconnect method - all disconnect scenarios call this.

        Args:
            character (Character): The meatspace character
            severity (int): Disconnect severity (JACKOUT_NORMAL, JACKOUT_EMERGENCY, JACKOUT_FORCED, JACKOUT_FATAL)
            reason (str): Reason for disconnect
        """
        conn = self.db.active_connection
        if not conn or conn.get('character') != character:
            return  # No active connection for this character

        avatar = conn.get('avatar')
        if not avatar or not avatar.pk:
            self.db.active_connection = None
            return

        # Apply consequences immediately (even if player is linkdead)
        self._apply_disconnect_consequences(character, severity)

        # Get account from avatar (since that's what's currently puppeted)
        account = avatar.account if hasattr(avatar, 'account') else None

        # Send initial DISCO message to avatar
        avatar.msg(f"|rDISCO:|n {reason}")

        # Clear connection immediately to prevent reconnection loop
        self.db.active_connection = None

        # If player is online, do staged puppet-out sequence
        if account and avatar.sessions.get():
            delay(1, self._disconnect_stage1, character, avatar, severity, account)
        else:
            # Player is linkdead - just mark avatar as disconnected
            # They'll wake up in their body on reconnect
            pass

    def validate_and_reconnect(self, character):
        """
        Called when character is puppeted while sitting in rig.

        Validates the connection and redirects to avatar if still valid.

        Args:
            character (Character): The character being puppeted

        Returns:
            bool: True if redirected to avatar, False if staying in body
        """
        conn = self.db.active_connection

        if not conn or conn.get('character') != character:
            return False  # No connection for this character

        avatar = conn.get('avatar')
        if not avatar or not avatar.pk:
            self.db.active_connection = None
            return False

        if getattr(avatar.db, 'dead', False):
            self.db.active_connection = None
            return False

        if not self.is_connected():
            self.db.active_connection = None
            return False

        # Connection valid - redirect to avatar
        account = character.account
        session = character.sessions.all()[0] if character.sessions.all() else None
        if account and session:
            character.msg("|cYour consciousness flows back into the Matrix...|n")
            account.puppet_object(session, avatar)
            avatar.msg("|gYou wake up in the Matrix.|n")
            return True

        return False

    def validate_connection(self):
        """
        Validate that the active connection is still valid.

        Called by the connection check script as a failsafe.

        Returns:
            bool: True if connection is valid, False if disconnected
        """
        conn = self.db.active_connection
        if not conn:
            return True  # No connection to validate

        character = conn.get('character')
        avatar = conn.get('avatar')

        # Check if character still exists
        if not character or not character.pk:
            self.db.active_connection = None
            return False

        # Check if avatar still exists
        if not avatar or not avatar.pk:
            self.disconnect(character, severity=JACKOUT_FORCED, reason="Avatar lost")
            return False

        # Check if character is still sitting in rig
        if character.db.sitting_on != self:
            self.disconnect(character, severity=JACKOUT_FORCED, reason="Physical connection severed")
            return False

        # Check if rig is still connected to Matrix
        if not self.is_connected():
            self.disconnect(character, severity=JACKOUT_EMERGENCY, reason="Network connection lost")
            return False

        return True

    # ========================================
    # Event Handlers
    # ========================================

    def at_object_delete(self):
        """Clean up when rig is destroyed."""
        # Force disconnect anyone using the rig
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
        if conn and conn.get('character') == character:
            self.disconnect(character, severity=JACKOUT_FORCED, reason="Forcibly disconnected!")

    # ========================================
    # Display/Query Methods
    # ========================================

    def is_character_diving(self, character):
        """
        Check if a character is currently jacked into the Matrix via this rig.

        Args:
            character (Character): The character to check

        Returns:
            bool: True if character is jacked in and puppeting their avatar
        """
        conn = self.db.active_connection
        if not conn or conn.get('character') != character:
            return False

        # Character must be sitting on this rig
        if character.db.sitting_on != self:
            return False

        # Check if character has no sessions (meaning they're puppeting the avatar)
        if hasattr(character, 'sessions'):
            return not character.sessions.get()

        return False

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

        # Get the sitter
        sitter = self.get_sitter()

        obj_name = self.get_display_name(looker, **kwargs)

        if not sitter:
            # Empty rig
            template = self.get_empty_template()
            return template.format(obj=f"{ROOM_DESC_OBJECT_NAME_COLOR}{obj_name}|n", name="")

        # Check visibility - always show looker
        if sitter != looker:
            location = self.location
            if location and hasattr(location, 'filter_visible'):
                if not location.filter_visible([sitter], looker, **kwargs):
                    # Not visible, show as empty
                    template = self.get_empty_template()
                    return template.format(obj=f"{ROOM_DESC_OBJECT_NAME_COLOR}{obj_name}|n", name="")

        # Check if sitter is diving (jacked into Matrix)
        is_diving = self.is_character_diving(sitter)

        # Format name
        if sitter == looker:
            char_name = f"{ROOM_DESC_CHARACTER_NAME_COLOR}You|n"
            verb = "are"
        else:
            char_name = sitter.get_display_name(looker, **kwargs)
            char_name = f"{ROOM_DESC_CHARACTER_NAME_COLOR}{char_name}|n"
            verb = "is"

        if is_diving:
            # Use special diving message
            template = getattr(self.db, "diving_msg", None) or "{name} is jacked into the Matrix, diving through {obj}."
        else:
            # Use standard sitting message
            template = self.get_occupied_template()

        # Replace verb
        template = template.replace(" is ", f" {verb} ")

        return template.format(
            name=char_name,
            obj=f"{ROOM_DESC_OBJECT_NAME_COLOR}{obj_name}|n"
        )

    # ========================================
    # Internal Helper Methods
    # ========================================

    def _get_or_create_avatar(self, character, target_node):
        """
        Get or create the Matrix avatar for this character.

        Args:
            character (Character): The character jacking in
            target_node: The Matrix node to spawn at

        Returns:
            MatrixAvatar: The avatar object, or None if creation failed
        """
        # Check if there's an existing avatar in our connection
        conn = self.db.active_connection
        if conn and conn.get('character') == character:
            avatar = conn.get('avatar')
            if avatar and avatar.pk and not getattr(avatar.db, 'dead', False):
                return avatar

        # Try to find existing avatar by searching all avatars
        # and checking their entry_device attribute
        from typeclasses.matrix.avatars import MatrixAvatar
        all_avatars = MatrixAvatar.objects.all()
        avatar = None

        for candidate in all_avatars:
            if getattr(candidate.db, 'entry_device', None) == self:
                if not getattr(candidate.db, 'dead', False):
                    avatar = candidate
                    break

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

            # Set initial avatar description
            avatar.db.desc = "A formless blob of data with limitless potential, waiting to be shaped into something interesting."

            if needs_respawn:
                character.msg("|yYour previous avatar was lost. Respawning...|n")

        return avatar

    def _apply_disconnect_consequences(self, character, severity):
        """
        Apply immediate consequences based on disconnect severity.

        Args:
            character (Character): The character to apply consequences to
            severity (int): Severity level
        """
        if severity >= JACKOUT_FATAL:
            # Fatal jackout - kill the character immediately
            # TODO: Hook into death system
            # For now, just send a message if they're connected
            if character.sessions.get():
                character.msg("|rYour consciousness is violently ejected. Your body dies.|n")

        elif severity >= JACKOUT_FORCED:
            # Violent disconnect - apply physical damage immediately
            # TODO: Apply actual physical damage using damage system
            # For now, just send a message if they're connected
            if character.sessions.get():
                character.msg("|rViolent pain wracks your body as you're torn from the Matrix.|n")

        elif severity >= JACKOUT_EMERGENCY:
            # Uncontrolled disconnect - apply minor penalties immediately
            # TODO: Apply minor penalties (disorientation, stamina loss, etc.)
            # For now, just send a message if they're connected
            if character.sessions.get():
                character.msg("|yYou feel disoriented as the connection fails.|n")

    def _jack_in_stage1(self, character, avatar):
        """Stage 1: Character loses consciousness."""
        character.db.conscious = False
        transition_msg = self.db.jack_in_transition_msg or "|cThe room seems to be sucked out of existence...|n"
        character.msg(transition_msg)

        # Stage 2: After another second, puppet swap
        delay(1, self._jack_in_stage2, character, avatar)

    def _jack_in_stage2(self, character, avatar):
        """Stage 2: Switch puppet to avatar."""
        account = character.account
        if account:
            session = character.sessions.all()[0] if character.sessions.all() else None
            if session:
                account.puppet_object(session, avatar)

    def _disconnect_stage1(self, character, avatar, severity, account):
        """Stage 1: Avatar becomes unconscious, show transition message."""
        avatar.db.conscious = False

        # Different messages based on severity
        if severity >= JACKOUT_FATAL:
            msg = self.db.fatal_jackout_msg or "|rThe world fractures. The Matrix ejects your consciousness like poison—|n"
        elif severity >= JACKOUT_FORCED:
            msg = self.db.forced_jackout_msg or "|rYou feel your consciousness being violently ripped back!|n"
        elif severity >= JACKOUT_EMERGENCY:
            msg = self.db.emergency_jackout_msg or "|yYou feel your awareness being urgently pulled back...|n"
        else:
            msg = self.db.normal_jackout_msg or "|cYou feel your awareness being drawn back into your body.|n"

        avatar.msg(msg)

        # Stage 2: After another second, puppet swap
        delay(1, self._disconnect_stage2, character, avatar, severity, account)

    def _disconnect_stage2(self, character, avatar, severity, account):
        """Stage 2: Switch puppet back to character."""
        if account:
            sessions = avatar.sessions.all()
            session = sessions[0] if sessions else None
            if session:
                account.puppet_object(session, character)

                # Stage 3: After another second, regain consciousness (or die)
                delay(1, self._disconnect_stage3, character, severity)

    def _disconnect_stage3(self, character, severity):
        """Stage 3: Character regains consciousness (or dies)."""
        if severity >= JACKOUT_FATAL:
            # Fatal jackout - character dies
            # TODO: Implement death system
            character.msg("|rDISCO.|n")
            character.msg("|r....|n")
            # For now, just regain consciousness with severe warning
            character.db.conscious = True
            character.msg("|rYou shouldn't be alive.|n")
        else:
            character.db.conscious = True
            character.msg("|cDisconnected...|n")

        # Show message to room where character's body is
        if character.location:
            jack_out_msg = self.db.jack_out_message or 'disconnects from the system'
            character.location.msg_contents(
                f"{character.name} {jack_out_msg}.",
                exclude=character
            )
