"""
Cyberware system — base typeclass and slot conventions.

Cyberware objects are physical items that exist in the world before installation
(they can be bought, carried, traded). Installation is a deliberate act via the
medical system or the @cyberware staff command. Once installed, the object moves
into the character's inventory with db.installed = True and a get:false() lock.

Slot values are free strings. If a slot matches an entry in world.medical.BODY_PARTS
it maps to a known body location (e.g. "left arm", "head"). Abstract slots like
"nervous system" or "spine" are also valid — they just don't map to a trauma zone.

Stat modifications route through the existing BuffHandler on Character so they
flow through get_display_stat() / get_skill_level() like every other modifier.
BuffHandler is non-persistent, so CyberwareBase.reapply_buffs() is called by
Character.at_server_start() to restore effects after a reload.
"""

from evennia import DefaultObject
from evennia.utils import logger


class CyberwareBase(DefaultObject):
    """
    Base typeclass for all cyberware.

    Subclass this and set:
        slot = "left arm"         # Required. Free string; body part or abstract.
        buff_class = MyCyberbuff  # Optional. Applied to character via BuffHandler.

    Override on_install / on_uninstall for appearance changes or extra effects.
    """

    slot = None
    buff_class = None

    def at_object_creation(self):
        super().at_object_creation()
        if not self.slot:
            logger.log_err(
                f"CyberwareBase subclass {type(self).__name__} created without a slot. "
                "Set the 'slot' class attribute."
            )
        self.db.installed = False
        self.db.installed_on = None  # dbref of owning character when installed

    def on_install(self, character):
        """
        Called by Character.install_cyberware(). Move the object into the
        character, lock it, and apply any buff.

        Override to add appearance or other effects, calling super() first.
        """
        self.db.installed = True
        self.db.installed_on = character.dbref
        self.location = character
        self.locks.add("get:false()")
        if self.buff_class:
            character.buffs.add(self.buff_class)

    def on_uninstall(self, character):
        """
        Called by Character.remove_cyberware(). Clears install state, removes
        the get lock, removes the buff, and moves the object to the character's
        location so it materialises in the room (surgical removal or ripping).

        Override to undo appearance or other effects, calling super() first.
        """
        self.db.installed = False
        self.db.installed_on = None
        self.locks.remove("get")
        if self.buff_class:
            character.buffs.remove(self.buff_class.key)
        # Materialise in the room regardless of rip vs surgical — staff disposes as needed.
        self.location = character.location

    def reapply_buffs(self, character):
        """
        Re-apply this cyberware's buff after a server restart (BuffHandler is
        non-persistent). Called by Character.at_server_start().
        """
        if self.buff_class:
            character.buffs.add(self.buff_class)
