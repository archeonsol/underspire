"""
Cyberware system — base typeclass.

Cyberware objects live with location=None until installed. Once installed, they
are tracked in character.db.cyberware (a list of objects). Installation is a
deliberate act via the medical system or the @cyberware staff command.

Conflict detection at install time:
  - Typeclass uniqueness: only one instance of each CyberwareBase subclass per character.
  - Locked body part overlap: if any body_mods "lock" a part already locked, install fails.

Stat modifications route through the existing BuffHandler on Character so they
flow through get_display_stat() / get_skill_level() like every other modifier.
BuffHandler is non-persistent, so CyberwareBase.reapply_buffs() is called by
Character.at_server_start() to restore effects after a reload.

Armor contribution: set armor_values = {damage_type: protection_score} for
cyberware that provides passive damage resistance (e.g. subdermal plating).
Queried by world.combat.armor.get_armor_protection_for_location().
"""

from evennia import DefaultObject
from evennia.utils import logger


class CyberwareBase(DefaultObject):
    """
    Base typeclass for all cyberware.

    Subclass this and set:
        buff_class = MyCyberbuff   # Optional. Applied to character via BuffHandler.
        body_mods = {              # Optional. Keys are body part strings from BODY_PARTS.
            "left thigh": ("lock", "A chrome prosthetic leg."),
            "abdomen": ("append", "Faint lines of subdermal plating are visible."),
        }
        armor_values = {}          # Optional. {damage_type: protection_score}

    mode "lock"   — fully replaces the character's naked for that body part.
                    The user cannot edit it while installed.
    mode "append" — appended after the user's own naked text for that part.
                    Multiple pieces of chrome can append to the same part independently.

    body_mods is independent of the installed cyberware list. The character's
    locked_descriptions / appended_descriptions are the source of truth for
    what's displayed. There is no slot concept — conflict detection is handled
    by typeclass uniqueness and locked-part overlap.

    Override on_install / on_uninstall for extra effects, calling super() first.
    """

    buff_class = None
    body_mods = {}
    armor_values = {}  # {damage_type: protection_score} for passive resistance

    # Surgery defaults: wound recorded when installed/removed via surgery.
    # Override surgery_body_part to target a specific part; otherwise the first
    # locked body_mods part is chosen automatically.
    surgery_wound_hp = 8         # severity 2 wound (needs treatment + time to heal)
    surgery_body_part = None     # auto-detect from body_mods if None

    def at_object_creation(self):
        super().at_object_creation()
        self.db.installed = False
        self.db.installed_on = None  # dbref of owning character when installed

    def on_install(self, character):
        """
        Called by Character.install_cyberware(). Applies buff and body modifications.
        Override to add extra effects, calling super() first.
        """
        self.db.installed = True
        self.db.installed_on = character.dbref
        self.locks.add("get:false()")

        if self.buff_class:
            character.buffs.add(self.buff_class)

        for part, (mode, text) in self.body_mods.items():
            if mode == "lock":
                locked = dict(character.db.locked_descriptions or {})
                locked[part] = text
                character.db.locked_descriptions = locked
            elif mode == "append":
                appended = dict(character.db.appended_descriptions or {})
                if part not in appended:
                    appended[part] = {}
                appended[part][self.typeclass_path] = text
                character.db.appended_descriptions = appended
            else:
                logger.log_warn(
                    f"CyberwareBase.on_install: unknown body_mods mode '{mode}' "
                    f"on {type(self).__name__} for part '{part}'"
                )

    def on_uninstall(self, character):
        """
        Called by Character.remove_cyberware(). Clears install state, removes
        buff, reverts body modifications, and moves the object to the character's
        location so it materialises in the room (surgical removal or ripping).
        Override to undo extra effects, calling super() first.
        """
        self.db.installed = False
        self.db.installed_on = None
        self.locks.remove("get")

        if self.buff_class:
            character.buffs.remove(self.buff_class.key)

        for part, (mode, _) in self.body_mods.items():
            if mode == "lock":
                locked = dict(character.db.locked_descriptions or {})
                locked.pop(part, None)
                character.db.locked_descriptions = locked
            elif mode == "append":
                appended = dict(character.db.appended_descriptions or {})
                if part in appended:
                    appended[part].pop(self.typeclass_path, None)
                character.db.appended_descriptions = appended

        self.location = character.location

    def reapply_buffs(self, character):
        """
        Re-apply this cyberware's buff after a server restart (BuffHandler is
        non-persistent). Called by Character.at_server_start().
        """
        if self.buff_class:
            character.buffs.add(self.buff_class)

    # ── Surgery hooks ────────────────────────────────────────────────────

    def _get_surgery_part(self):
        """Return the body part to wound during surgery, or None."""
        if self.surgery_body_part:
            return self.surgery_body_part
        if not self.body_mods:
            return None
        # Prefer the first locked part; fall back to first appended.
        for part, (mode, _) in self.body_mods.items():
            if mode == "lock":
                return part
        return next(iter(self.body_mods))

    def on_surgery_install(self, character, surgeon=None):
        """
        Medical footprint of surgical installation. Creates a treated wound
        on the primary body part. Called by Character.install_cyberware()
        after on_install() unless skip_surgery=True.

        Override for custom surgical effects (e.g. heavier wounds for major
        implants, lighter wounds for subdermal injections).
        """
        part = self._get_surgery_part()
        if not part or self.surgery_wound_hp <= 0:
            return
        from world.medical import add_injury
        add_injury(character, self.surgery_wound_hp, body_part=part,
                   weapon_key="surgery")
        # Mark treated immediately — surgery was just performed by a professional.
        injuries = character.db.injuries or []
        for inj in reversed(injuries):
            if inj.get("body_part") == part and not inj.get("treated"):
                inj["treated"] = True
                break
        character.db.injuries = injuries

    def on_surgery_removal(self, character, surgeon=None):
        """
        Medical footprint of surgical removal. Creates a treated wound.
        Called by Character.remove_cyberware() before on_uninstall()
        unless skip_surgery=True.
        """
        part = self._get_surgery_part()
        if not part or self.surgery_wound_hp <= 0:
            return
        from world.medical import add_injury
        add_injury(character, self.surgery_wound_hp, body_part=part,
                   weapon_key="surgery")
        injuries = character.db.injuries or []
        for inj in reversed(injuries):
            if inj.get("body_part") == part and not inj.get("treated"):
                inj["treated"] = True
                break
        character.db.injuries = injuries
