"""
Matrix Avatars

Virtual representations of characters diving the Matrix.

MatrixAvatar - Virtual character object created when jacking into the Matrix
"""

from evennia import DefaultCharacter
from typeclasses.mixins import FurnitureMixin, RoleplayMixin

# Jack-out severity levels
JACKOUT_NORMAL = 0      # Clean logout, no penalties
JACKOUT_EMERGENCY = 1   # Uncontrolled disconnect, minor penalties
JACKOUT_FORCED = 2      # Violent disconnect, physical damage
JACKOUT_FATAL = 3       # Unsurvivable... Sorry


class MatrixAvatar(RoleplayMixin, FurnitureMixin, DefaultCharacter):
    """
    Virtual representation of a character diving the Matrix.

    Created when a character jacks in through a device. Persists in the Matrix
    until destroyed.

    Mixins:
    - RoleplayMixin: Recognition, display names, say/whisper, movement announcements
    - FurnitureMixin: Sitting/lying on virtual furniture (nodes, consoles, etc.)

    Unlike physical Characters, avatars have NO:
    - Body parts, organs, medical systems
    - Hunger, thirst, or survival needs
    - Sleep/wake messages
    - XP earning
    - Clothing/worn items
    - Stats/skills (uses controlling character's stats for checks)

    The DiveRig owns the connection state - avatars are just puppets.

    Attributes:
        entry_device (DiveRig): The rig this avatar is connected through
        dead (bool): Whether this avatar has been killed
        proxy_router (Router): Optional proxy tunnel router (persists across sessions)
    """

    def at_post_puppet(self, **kwargs):
        """Same as DefaultCharacter puppet feedback but no room-wide 'has entered the game' line."""
        from typeclasses.characters import _puppet_become_and_look_no_room_broadcast

        _puppet_become_and_look_no_room_broadcast(self)

    def at_object_creation(self):
        """Called when avatar is first created."""
        super().at_object_creation()
        self.db.entry_device = None
        self.db.dead = False
        self.db.proxy_router = None  # Persistent proxy tunnel location
        self.db.matrix_id = None     # Matrix ID of the identity this avatar operates as
        self.db.matrix_alias = None  # Cached alias; updated on jack-in and on set_alias()

    def sync_alias(self):
        """
        Sync db.matrix_alias from the active identity on this avatar's rig.

        Goes through the rig rather than the character directly, so the same
        path will work for jailbroken handset identities in the future.
        """
        rig = self.db.entry_device
        if not rig:
            return
        alias = rig.get_active_alias()
        if alias is not None:
            self.db.matrix_alias = alias
        self._sync_matrix_aliases()

    def _sync_matrix_aliases(self):
        """
        Rebuild Evennia search aliases from matrix_id and matrix_alias so players can
        target this avatar by handle (jazzy, ^N7AIK4, N7AIK4, etc.) without the @ prefix.
        """
        self.aliases.clear()
        mid = self.db.matrix_id or ""
        alias = self.db.matrix_alias or ""
        if mid:
            self.aliases.add(mid)
            stripped = mid.lstrip("^")
            if stripped and stripped != mid:
                self.aliases.add(stripped)
        if alias:
            self.aliases.add(alias)

    def get_display_name(self, looker, **kwargs):
        """
        Display name for this avatar. Checks recog first (so manually set recogs still
        work), then shows @alias or @matrixid. Identity in the Matrix is public — no
        introduction needed.
        """
        if looker and looker != self:
            if hasattr(looker, "recog") and callable(getattr(looker.recog, "get", None)):
                recog = looker.recog.get(self)
                if recog:
                    return recog
        if self.db.matrix_alias:
            return f"|431@{self.db.matrix_alias}|n"
        if self.db.matrix_id:
            return f"|431@{self.db.matrix_id}|n"
        return f"|431{self.key}|n"

    def get_controlling_character(self):
        """
        Get the physical character controlling this avatar.

        Returns:
            Character: The meatspace character jacked into this avatar, or None
        """
        rig = self.db.entry_device
        if not rig or not hasattr(rig, 'db'):
            return None
        conn = rig.db.active_connection
        if not conn:
            return None
        return conn.get('character')

    def get_stat_level(self, stat_key):
        """Delegate to controlling character's stats."""
        char = self.get_controlling_character()
        if char and hasattr(char, 'get_stat_level'):
            return char.get_stat_level(stat_key)
        return 0

    def get_display_stat(self, stat_name):
        """Delegate to controlling character's display stats (with buffs)."""
        char = self.get_controlling_character()
        if char and hasattr(char, 'get_display_stat'):
            return char.get_display_stat(stat_name)
        return 0

    def handle_proxy_disconnect(self):
        """
        Called when the proxy router goes offline.

        Triggers emergency jackout with specific message about proxy tunnel collapse.
        """
        rig = self.db.entry_device
        if not rig or not hasattr(rig, 'disconnect'):
            return

        char = self.get_controlling_character()
        if not char:
            return

        # Clear the proxy since it's no longer valid
        self.db.proxy_router = None

        # Emergency jackout
        rig.disconnect(char, severity=JACKOUT_EMERGENCY, reason="Proxy tunnel collapsed")

    def get_skill_level(self, skill_key):
        """Delegate to controlling character's skills."""
        char = self.get_controlling_character()
        if char and hasattr(char, 'get_skill_level'):
            return char.get_skill_level(skill_key)
        return 0

    def get_stat_grade_adjective(self, grade_letter, stat_key):
        """Delegate to controlling character's stat grade adjectives."""
        char = self.get_controlling_character()
        if char and hasattr(char, 'get_stat_grade_adjective'):
            return char.get_stat_grade_adjective(grade_letter, stat_key)
        return grade_letter

    def get_skill_grade_adjective(self, grade_letter):
        """Delegate to controlling character's skill grade adjectives."""
        char = self.get_controlling_character()
        if char and hasattr(char, 'get_skill_grade_adjective'):
            return char.get_skill_grade_adjective(grade_letter)
        return grade_letter

    def get_stat_cap(self, stat_key):
        """Delegate to controlling character's stat caps."""
        char = self.get_controlling_character()
        if char and hasattr(char, 'get_stat_cap'):
            return char.get_stat_cap(stat_key)
        return 0

    def get_skill_cap(self, skill_key):
        """Delegate to controlling character's skill caps."""
        char = self.get_controlling_character()
        if char and hasattr(char, 'get_skill_cap'):
            return char.get_skill_cap(skill_key)
        return 0

    def roll_check(self, stat_list, skill_name, difficulty=0, modifier=0):
        """Delegate to controlling character's roll system."""
        char = self.get_controlling_character()
        if char and hasattr(char, 'roll_check'):
            return char.roll_check(stat_list, skill_name, difficulty, modifier)
        return "Failure", 0

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
