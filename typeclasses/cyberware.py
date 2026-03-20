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

import time
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
        damage_model = "none"      # Optional durability routing model.

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
    vulnerabilities = {}  # {"arc": 0.0, ...}
    # Deterministic combat durability routing:
    # - "armor":      loses chrome_hp when it absorbs incoming damage.
    # - "collateral": loses chrome_hp from organ-trauma collateral on its body part.
    # - "arc_only":   loses chrome_hp only from high arc spikes.
    # - "none":       no direct combat chrome_hp routing.
    damage_model = "none"
    required_implants = []  # class names that must already be installed
    required_implants_any = []  # at least one of these class names must be installed
    conflicts_with = []  # class names that cannot coexist

    # Surgery defaults: wound recorded when installed/removed via surgery.
    # Override surgery_body_part to target a specific part; otherwise the first
    # locked body_mods part is chosen automatically.
    surgery_wound_hp = 8         # severity 2 wound (needs treatment + time to heal)
    surgery_body_part = None     # auto-detect from body_mods if None
    surgery_difficulty = 15
    surgery_duration_steps = 4
    surgery_blood_loss = "moderate"
    surgery_rejection_risk = 0.05
    surgery_narrative_key = None
    surgery_requires_sedation = True
    surgery_category = "implant"
    surgery_prep_tools = []
    chrome_replacement_for = None
    chrome_max_hp = 100

    def at_object_creation(self):
        super().at_object_creation()
        self.db.installed = False
        self.db.installed_on = None  # dbref of owning character when installed
        self.db.chrome_max_hp = int(getattr(self, "chrome_max_hp", 100) or 100)
        self.db.chrome_hp = int(getattr(self.db, "chrome_hp", self.db.chrome_max_hp) or self.db.chrome_max_hp)
        self.db.malfunctioning = bool(getattr(self.db, "malfunctioning", False))

    def on_install(self, character):
        """
        Called by Character.install_cyberware(). Applies buff and body modifications.
        Override to add extra effects, calling super() first.
        """
        self.db.installed = True
        self.db.installed_on = character.dbref
        self.locks.add("get:false()")
        # Installed chrome is internal and should no longer exist in inventory.
        self.location = None

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
        if getattr(self.db, "malfunctioning", False):
            return
        if self.buff_class:
            character.buffs.add(self.buff_class)

    def get_recovery_modifier(self, character):
        """
        Return current effectiveness scalar based on surgery recovery phase.
        """
        now = time.time()
        for injury in (character.db.injuries or []):
            if injury.get("cyberware_dbref") != self.id:
                continue
            started = float(injury.get("recovery_started", now) or now)
            elapsed = now - started
            if elapsed < 24 * 3600:
                return 0.5
            if elapsed < 72 * 3600:
                return 0.8
            return 1.0
        return 1.0

    def set_malfunction(self, character, value=True):
        self.db.malfunctioning = bool(value)
        if self.buff_class and value:
            character.buffs.remove(self.buff_class.key)
        elif self.buff_class and not value:
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

    def _apply_surgery_wound(self, character):
        """Create and immediately treat a surgical wound on the primary body part."""
        part = self._get_surgery_part()
        if not part or self.surgery_wound_hp <= 0:
            return
        from world.medical import add_injury
        add_injury(character, self.surgery_wound_hp, body_part=part,
                   weapon_key="surgery")
        # Mark treated immediately — surgery was performed by a professional.
        injuries = character.db.injuries or []
        for inj in reversed(injuries):
            if inj.get("body_part") == part and not inj.get("treated"):
                inj["treated"] = True
                break
        character.db.injuries = injuries

    def on_surgery_install(self, character, surgeon=None):
        """
        Medical footprint of surgical installation. Creates a treated wound
        on the primary body part. Called by Character.install_cyberware()
        after on_install() unless skip_surgery=True.

        Override for custom surgical effects (e.g. heavier wounds for major
        implants, lighter wounds for subdermal injections).
        """
        self._apply_surgery_wound(character)

    def on_surgery_removal(self, character, surgeon=None):
        """
        Medical footprint of surgical removal. Creates a treated wound.
        Called by Character.remove_cyberware() before on_uninstall()
        unless skip_surgery=True.
        """
        self._apply_surgery_wound(character)


