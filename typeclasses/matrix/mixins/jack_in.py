"""
JackInMixin

Core Matrix jack-in/disconnect logic, shared by any device that can establish
a Matrix connection for a diving character.

Current users:
    DiveRig — physical recliner; requires character to be seated

Planned users:
    NeuralImplant — cyberware; requires implant to be in character's inventory

Subclasses override _get_jack_in_errors() and _get_connection_errors() to add
their own preconditions. All other logic is generic.
"""

from evennia.utils.create import create_object
from evennia.utils import delay
from typeclasses.matrix.avatars import MatrixAvatar, JACKOUT_FORCED, JACKOUT_EMERGENCY, JACKOUT_FATAL, JACKOUT_NORMAL
from typeclasses.matrix.mixins.networked import NetworkedMixin


class JackInMixin(NetworkedMixin):
    """
    Mixin providing Matrix jack-in/disconnect logic for devices.

    Call setup_jack_in_attrs() from at_object_creation() to initialize attributes.
    """

    def setup_jack_in_attrs(self):
        """
        Initialize jack-in attributes.

        Call this from at_object_creation() after super().
        """
        self.db.active_connection = None

        self.db.jack_in_message = "jacks into the Matrix"
        self.db.jack_out_message = "disconnects from the Matrix"
        self.db.jack_in_transition_msg = "|cThe room seems to be sucked out of existence...|n"
        self.db.normal_jackout_msg = "|cYou feel your awareness being drawn back through the Matrix and into your body.|n"
        self.db.emergency_jackout_msg = "|yYou feel your awareness being urgently pulled back through the Matrix...|n"
        self.db.forced_jackout_msg = "|rYou feel your consciousness being violently ripped back through the Matrix!|n"
        self.db.fatal_jackout_msg = "|rThe world fractures. Your avatar is dying. The Matrix ejects your consciousness like poison—|n"

    # ========================================
    # Hooks (override in subclasses)
    # ========================================

    def _get_jack_in_errors(self, character):
        """
        Return a list of error strings blocking jack-in. Empty list = clear to proceed.

        Base implementation checks router existence and online status.
        Subclasses should call super() and prepend their own checks:

            def _get_jack_in_errors(self, character):
                errors = []
                if <subclass precondition fails>:
                    errors.append("...")
                return errors + super()._get_jack_in_errors(character)
        """
        router = self.get_relay()
        if not router:
            return ["No Matrix connection available. Room not linked to a router."]
        if not router.db.online:
            return ["Router is offline. No Matrix connection available."]
        if not router.location:
            return ["Router is not properly configured (no Matrix location)."]
        return []

    def _get_connection_errors(self, character):
        """
        Return reasons why an active connection is no longer valid. Empty = still valid.

        Returns a list of (reason, severity) tuples. The first entry is used if
        validate_connection() needs to disconnect.

        Base implementation checks network coverage.
        Subclasses should call super() and prepend their own checks:

            def _get_connection_errors(self, character):
                errors = []
                if <subclass condition fails>:
                    errors.append(("Reason", JACKOUT_FORCED))
                return errors + super()._get_connection_errors(character)
        """
        if not self.has_network_coverage():
            return [("Network connection lost", JACKOUT_EMERGENCY)]
        return []

    # ========================================
    # Identity
    # ========================================

    def get_active_matrix_id(self, character=None):
        """
        Return the Matrix ID of the identity currently active on this device.

        Currently returns the diving character's own Matrix ID. In the future,
        if a jailbroken handset is slotted, this will return the handset's ID
        instead — making this device the single point of change for identity spoofing.

        Args:
            character: The diving character. If None, reads from active_connection.
                       Must be passed explicitly during jack-in before active_connection
                       is established.
        """
        if character is None:
            conn = self.db.active_connection
            character = conn.get('character') if conn else None
        if not character:
            return None
        # Future: if self.db.slotted_handset: return self.db.slotted_handset.get_matrix_id()
        return character.get_matrix_id()

    def get_active_alias(self, character=None):
        """
        Return the alias of the identity currently active on this device.

        Mirrors get_active_matrix_id — currently derives from the character,
        future will derive from a slotted handset if present.

        Args:
            character: The diving character. If None, reads from active_connection.
        """
        if character is None:
            conn = self.db.active_connection
            character = conn.get('character') if conn else None
        if not character:
            return None
        # Future: if self.db.slotted_handset: return get_alias_for_handset(...)
        from world.matrix_accounts import get_alias
        return get_alias(character)

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
        errors = self._get_jack_in_errors(character)
        if errors:
            character.msg(errors[0])
            return False

        router = self.get_relay()
        target_node = router.location

        avatar = self._get_or_create_avatar(character, target_node)
        if not avatar:
            character.msg("Failed to establish connection.")
            return False

        # Link avatar back to device
        avatar.db.entry_device = self

        # Establish active connection
        from evennia.utils import gametime, logger
        self.db.active_connection = {
            'character': character,
            'avatar': avatar,
            'connected_at': gametime.gametime()
        }

        # Sync alias now that active_connection is set
        avatar.sync_alias()

        # Log the connection
        logger.log_info(f"Matrix jack-in: {character.key} -> {avatar.key}")

        # Staged jack-in sequence
        character.msg("|gConnecting...|n")
        character.location.msg_contents(
            f"{character.name} {self.db.jack_in_message}.",
            exclude=character
        )

        delay(1, self._jack_in_stage1, character, avatar)

        return True

    def disconnect(self, character, severity=JACKOUT_NORMAL, reason="Disconnecting"):
        """
        Disconnect a character from the Matrix.

        This is the primary disconnect method — all disconnect scenarios call this.

        Args:
            character (Character): The meatspace character
            severity (int): Disconnect severity constant (JACKOUT_*)
            reason (str): Reason for disconnect
        """
        conn = self.db.active_connection
        if not conn:
            return

        conn_character = conn.get('character')
        if not conn_character or conn_character.pk != character.pk:
            return

        avatar = conn.get('avatar')
        if not avatar or not avatar.pk:
            self.db.active_connection = None
            return

        self._apply_disconnect_consequences(character, severity)

        account = avatar.account if hasattr(avatar, 'account') else None

        avatar.msg(f"|rDISCO:|n {reason}")

        from evennia.utils import logger
        severity_names = {0: "NORMAL", 1: "EMERGENCY", 2: "FORCED", 3: "FATAL"}
        logger.log_info(
            f"Matrix disconnect: {character.key} "
            f"severity={severity_names.get(severity, severity)} reason='{reason}'"
        )

        self.db.active_connection = None

        if account and avatar.sessions.get():
            delay(1, self._disconnect_stage1, character, avatar, severity, account)

    def validate_and_reconnect(self, character):
        """
        Called when character is puppeted while still associated with this device.

        Validates the connection and redirects to avatar if still valid.

        Args:
            character (Character): The character being puppeted

        Returns:
            bool: True if redirected to avatar, False if staying in body
        """
        conn = self.db.active_connection
        if not conn:
            return False

        conn_character = conn.get('character')
        if not conn_character or conn_character.pk != character.pk:
            return False

        avatar = conn.get('avatar')
        if not avatar or not avatar.pk:
            self.db.active_connection = None
            return False

        if getattr(avatar.db, 'dead', False):
            self.db.active_connection = None
            return False

        if self._get_connection_errors(character):
            self.db.active_connection = None
            return False

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
            bool: True if connection is valid (or no connection), False if disconnected
        """
        conn = self.db.active_connection
        if not conn:
            return True

        character = conn.get('character')
        avatar = conn.get('avatar')

        if not character or not hasattr(character, 'pk') or not character.pk:
            self.db.active_connection = None
            return False

        if not avatar or not avatar.pk:
            self.disconnect(character, severity=JACKOUT_FORCED, reason="Avatar lost")
            return False

        errors = self._get_connection_errors(character)
        if errors:
            reason, severity = errors[0]
            self.disconnect(character, severity=severity, reason=reason)
            return False

        return True

    def is_character_diving(self, character):
        """
        Check if a character is currently jacked into the Matrix via this device.

        Args:
            character (Character): The character to check

        Returns:
            bool: True if character is jacked in and puppeting their avatar
        """
        conn = self.db.active_connection
        if not conn:
            return False

        conn_character = conn.get('character')
        if not conn_character or conn_character.pk != character.pk:
            return False

        if hasattr(character, 'sessions'):
            return not character.sessions.get()

        return False

    # ========================================
    # Internal Helpers
    # ========================================

    def _get_or_create_avatar(self, character, target_node):
        """
        Get or create the Matrix avatar for a character.

        Args:
            character (Character): The character jacking in
            target_node: The Matrix node to spawn at

        Returns:
            MatrixAvatar: The avatar object, or None if creation failed
        """
        # Check if there's an existing avatar in our connection
        conn = self.db.active_connection
        conn_character = conn.get('character') if conn else None
        if conn and conn_character and conn_character.pk == character.pk:
            avatar = conn.get('avatar')
            if avatar and avatar.pk and not getattr(avatar.db, 'dead', False):
                return avatar

        # Resolve the effective matrix ID for this jack-in (character's ID, or
        # future override from a slotted jailbroken handset).
        char_matrix_id = self.get_active_matrix_id(character)
        if not char_matrix_id:
            from evennia.utils import logger
            logger.log_err(f"Cannot create avatar for {character}: no Matrix ID.")
            return None

        # Search for an existing avatar belonging to this character.
        # We key on character.key, not matrix_id — the key is stable and character-scoped.
        # Avatar keys always follow "{character.key} (Avatar)" (enforced at creation),
        # so we can use an indexed db_key lookup instead of a full table scan.
        avatar = MatrixAvatar.objects.filter(db_key=f"{character.key} (Avatar)").first()
        if avatar and getattr(avatar.db, 'dead', False):
            avatar = None

        needs_respawn = False
        if avatar:
            if getattr(avatar.db, 'dead', False):
                needs_respawn = True
                if avatar.location:
                    for item in avatar.contents:
                        item.move_to(avatar.location, quiet=True)
                avatar.delete()
                avatar = None
            elif not avatar.location or not avatar.location.pk:
                needs_respawn = True
                avatar.location = target_node

        if not avatar:
            avatar = create_object(
                MatrixAvatar,
                key=f"{character.key} (Avatar)",
                location=target_node
            )

            if not avatar:
                return None

            avatar.db.matrix_id = char_matrix_id
            avatar.db.desc = (
                "A formless blob of data with limitless potential, "
                "waiting to be shaped into something interesting."
            )

            if needs_respawn:
                character.msg("|yYour previous avatar was lost. Respawning...|n")

        # Sync targeting aliases whenever we get or create an avatar, so matrix_id
        # and alias are always searchable even if the avatar predates this system.
        avatar._sync_matrix_aliases()
        return avatar

    def _apply_disconnect_consequences(self, character, severity):
        """Apply immediate consequences based on disconnect severity."""
        if severity >= JACKOUT_FATAL:
            if character.sessions.get():
                character.msg("|rYour consciousness is violently ejected. Your body dies.|n")
        elif severity >= JACKOUT_FORCED:
            if character.sessions.get():
                character.msg("|rViolent pain wracks your body as you're torn from the Matrix.|n")
        elif severity >= JACKOUT_EMERGENCY:
            if character.sessions.get():
                character.msg("|yYou feel disoriented as the connection fails.|n")

    def _jack_in_stage1(self, character, avatar):
        """Stage 1: Character loses consciousness."""
        character.db.conscious = False
        transition_msg = self.db.jack_in_transition_msg or "|cThe room seems to be sucked out of existence...|n"
        character.msg(transition_msg)
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

        if severity >= JACKOUT_FATAL:
            msg = self.db.fatal_jackout_msg or "|rThe world fractures. The Matrix ejects your consciousness like poison—|n"
            avatar.msg("|rYour avatar dissolves into static and void.|n")
            avatar.msg("|rFor a brief, terrible moment, you see reality again—|n")
            avatar.msg("|rYour body in the rig, convulsing—|n")
            avatar.msg("|rThen nothing.|n")
        elif severity >= JACKOUT_FORCED:
            msg = self.db.forced_jackout_msg or "|rYou feel your consciousness being violently ripped back!|n"
        elif severity >= JACKOUT_EMERGENCY:
            msg = self.db.emergency_jackout_msg or "|yYou feel your awareness being urgently pulled back...|n"
        else:
            msg = self.db.normal_jackout_msg or "|cYou feel your awareness being drawn back into your body.|n"

        avatar.msg(msg)
        delay(1, self._disconnect_stage2, character, avatar, severity, account)

    def _disconnect_stage2(self, character, avatar, severity, account):
        """Stage 2: Switch puppet back to character."""
        if account:
            sessions = avatar.sessions.all()
            session = sessions[0] if sessions else None
            if session:
                account.puppet_object(session, character)
                delay(1, self._disconnect_stage3, character, severity)

    def _disconnect_stage3(self, character, severity):
        """Stage 3: Character regains consciousness (or dies)."""
        if severity >= JACKOUT_FATAL:
            # TODO: Implement death system
            character.msg("|rOuch....|n")
            character.msg("|r....|n")
            character.db.conscious = True
            character.msg("|rYou shouldn't be alive.|n")
        else:
            character.db.conscious = True
            character.msg("|cDisconnected...|n")

        if character.location:
            jack_out_msg = self.db.jack_out_message or 'disconnects from the system'
            character.location.msg_contents(
                f"{character.name} {jack_out_msg}.",
                exclude=character
            )
