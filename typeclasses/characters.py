from collections.abc import Mapping

from evennia import DefaultCharacter
from evennia.contrib.game_systems.cooldowns import CooldownHandler
from evennia.contrib.rpg.buffs.buff import BuffHandler
from evennia.contrib.rpg.traits import TraitHandler
from evennia.utils import logger
from evennia.utils.utils import compress_whitespace, dbref, lazy_property

from world.multipuppet import multi_puppet_relay
from world.theme_colors import ROOM_COLORS
from typeclasses.mixins import FurnitureMixin, MedicalMixin, RPGCharacterMixin, RoleplayMixin
from typeclasses.matrix.mixins.matrix_id import MatrixIdMixin


def _body_parts(character):
    from world.body import get_character_body_parts

    return get_character_body_parts(character)


# When you look at a character: name = orange (match room list), sdesc in parens = white
LOOK_CHARACTER_NAME_COLOR = ROOM_COLORS["character_name"]
LOOK_SDESC_COLOR = "|w"              # white for (a tall man wearing...)


def _resolve_buff_handler_owner(handler):
    """
    Resolve BuffHandler.owner without storing a live object reference on the
    handler. A strong ``Character`` reference breaks pickling of persistent
    ``utils.delay(..., handler.cleanup, persistent=True)`` (e.g. timed drug buffs).
    """
    o = BuffHandler.owner.fget(handler)
    if o is not None:
        return o
    ref = getattr(handler, "ownerref", None)
    if not ref:
        return None
    try:
        from evennia.objects.models import ObjectDB

        oid = dbref(ref, reqhash=True)
        if oid:
            return ObjectDB.objects.get(id=oid)
    except Exception:
        pass
    return None


class _BuffCacheDict(dict):
    """
    Evennia Attribute values unpickle on every read; in-place mutation of the
    dict returned by ``attributes.get`` does not write back. Route mutations
    through ``attributes.add`` so BuffHandler writes persist.
    """

    __slots__ = ("_handler",)

    def __init__(self, handler, *args, **kwargs):
        self._handler = handler
        super().__init__(*args, **kwargs)

    def _persist(self):
        h = self._handler
        if h.owner is not None:
            h.owner.attributes.add(h.dbkey, dict(self))

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._persist()

    def __delitem__(self, key):
        super().__delitem__(key)
        self._persist()

    def clear(self):
        super().clear()
        self._persist()

    def pop(self, *args, **kwargs):
        result = super().pop(*args, **kwargs)
        self._persist()
        return result

    def popitem(self):
        result = super().popitem()
        self._persist()
        return result

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._persist()

    def setdefault(self, key, default=None):
        if key in self:
            return self[key]
        self[key] = default
        return default


class _SafeBuffHandler(BuffHandler):
    """
    Ensures the persisted buff cache is always a dict. If db.buffs was ever
    overwritten with a string or other type, Evennia's BuffHandler.get_all()
    does dict(self.buffcache) and raises ValueError.

    Evennia's BuffHandler.owner uses search_object(dbref); if that misses,
    we fall back to ObjectDB.objects.get so buffcache writes still target the
    character. We do not store a live owner reference on the handler so
    ``utils.delay(..., self.cleanup, persistent=True)`` can pickle the handler.
    """

    def __init__(self, owner, dbkey="buffs", autopause=True):
        self._buffcache_dict = None
        super().__init__(owner, dbkey=dbkey, autopause=autopause)

    @property
    def owner(self):
        return _resolve_buff_handler_owner(self)

    @property
    def buffcache(self):
        if not self.owner:
            return {}
        if self._buffcache_dict is None:
            if not self.owner.attributes.has(self.dbkey):
                self.owner.attributes.add(self.dbkey, {})
            cache = self.owner.attributes.get(self.dbkey)
            # Evennia returns db-backed dicts as _SaverDict (MutableMapping), not plain dict.
            # Treating that as invalid used to reset db.buffs to {} and wipe all buffs on load.
            if not isinstance(cache, Mapping):
                logger.log_warn(
                    "buffs cache on {owner} was {cache!r} ({typ}); reset to empty dict",
                    owner=self.owner,
                    cache=cache,
                    typ=type(cache).__name__,
                )
                self.owner.attributes.add(self.dbkey, {})
                cache = {}
            else:
                cache = dict(cache)
            self._buffcache_dict = _BuffCacheDict(self)
            self._buffcache_dict.update(cache)
        return self._buffcache_dict


def _puppet_become_and_look_no_room_broadcast(character):
    """
    Match Evennia DefaultCharacter.at_post_puppet (You become + look + _last_puppet) without
    telling the room that someone has entered the game — that is noise on every @puppet switch.
    """
    from django.utils.translation import gettext as _

    character.msg(_("\nYou become |c{name}|n.\n").format(name=character.key))
    if character.location:
        character.msg((character.at_look(character.location), {"type": "look"}), options=None)
    if hasattr(character, "account") and character.account:
        character.account.db._last_puppet = character


class Character(MatrixIdMixin, RoleplayMixin, MedicalMixin, RPGCharacterMixin, FurnitureMixin, DefaultCharacter):
    """
    The 'Colony' Core Engine.
    Uses a Qualitative Grade system (U through A, 21 letters) where:
    - Skill = The success ceiling (Technical precision)
    - Stat = The roll weight/floor (Raw power)
    """

    # Look-at-character header: name + optional (sdesc) are pre-colored in return_appearance / helpers
    appearance_template = """
{header}
{name}{extra_name_info}
{desc}
{exits}
{characters}
{things}
{footer}
"""

    # Stats 0-300, skills 0-150; letter tiers from world.levels (21 letters U–A)

    @lazy_property
    def trait_stats(self):
        """
        TraitHandler for stats (0-300 stored) and stat caps.
        Key: db_attribute_key="trait_stats" avoids collision with legacy db.stats dict.
        Read via character.trait_stats["strength"].base (stored 0-300).
        Effective display value still flows through get_display_stat() -> xp._stat_level().
        """
        return TraitHandler(self, db_attribute_key="trait_stats", db_attribute_category="traits")

    @lazy_property
    def trait_skills(self):
        """
        TraitHandler for skills (0-150 stored = display).
        Key: db_attribute_key="trait_skills" avoids collision with legacy db.skills dict.
        Read via character.trait_skills["unarmed"].base (stored 0-150).
        Effective value still flows through get_skill_level() -> xp._skill_level().
        """
        return TraitHandler(self, db_attribute_key="trait_skills", db_attribute_category="traits")

    @lazy_property
    def cooldowns(self):
        """
        Rate-limiting handler for actions (bioscan, flee, pay, etc.).
        Backed by Evennia's CooldownHandler; persists across reboots.
        Usage: character.cooldowns.add("action_name", seconds)
               character.cooldowns.ready("action_name")  -> bool
               character.cooldowns.time_left("action_name")  -> float seconds
        """
        return CooldownHandler(self, db_attribute="cooldowns")

    @lazy_property
    def buffs(self):
        """
        Timed/permanent modifiers (perfume, bad smells, cybernetics, traits).
        Backed by Evennia's generic BuffHandler; all mechanical effects flow
        through stat/skill helpers rather than touching stored values directly.
        """
        # Use a dedicated dbkey so buffs live on character.db.buffs.
        return _SafeBuffHandler(self, dbkey="buffs", autopause=True)

    @property
    def death_fsm(self):
        """
        Return the DeathStateMachine for this character (created on first access).
        Stored in ndb._death_fsm (non-persistent; recreated on reload).
        Use this to trigger validated death state transitions:
            self.death_fsm.go_flatline()
            self.death_fsm.revive()
            self.death_fsm.go_permanent()
        """
        from world.death import get_death_fsm
        return get_death_fsm(self)

    def at_object_creation(self):
        """Called only once, when the character is first created."""
        super().at_object_creation()

        # --- SPECIAL: levels 0-300 (letter displayed by tier; 300 = A)
        self.db.stats = {
            "strength": 0,
            "perception": 0,
            "endurance": 0,
            "charisma": 0,
            "intelligence": 0,
            "agility": 0,
            "luck": 0,
        }

        # --- SKILLS: levels 0-150; canonical list in world.skills
        from world.skills import SKILL_KEYS
        self.db.skills = {sk: 0 for sk in SKILL_KEYS}

        # --- TRAIT MIRRORS: authoritative storage post-migration; xp.py reads these first.
        # Stats: static traits, base=0-300, cap traits stored alongside as "cap_<key>".
        # Skills: static traits, base=0-150.
        from world.rpg.chargen import STAT_KEYS
        from world.levels import MAX_STAT_LEVEL, MAX_LEVEL
        for _sk in STAT_KEYS:
            self.trait_stats.add(_sk, _sk.title(), trait_type="static", base=0)
            self.trait_stats.add(f"cap_{_sk}", f"{_sk.title()} Cap", trait_type="static", base=MAX_STAT_LEVEL)
        for _sk in SKILL_KEYS:
            self.trait_skills.add(_sk, _sk.replace("_", " ").title(), trait_type="static", base=0)

        self.db.current_hp = None
        self.db.current_stamina = None
        self.db.race = "human"
        self.db.splicer_animal = None
        self.db.traits = []
        self.db.needs_chargen = True
        # General "describe me as" line (shown first when someone looks at you; short one-liner)
        self.db.general_desc = "This is a character."
        # Per-body-part descriptions for look/appearance (keys from world.medical.BODY_PARTS)
        self.db.body_descriptions = {part: "" for part in _body_parts(self)}
        # Medical / trauma (organs, fractures, bleeding) - see world.medical
        self.db.injuries = []  # HP-occupancy wound list; see world.medical.add_injury
        self.db.organ_damage = {}
        self.db.limb_damage = {}
        self.db.fractures = []
        self.db.bleeding_level = 0
        # Worn clothing/armor (list of objects); order = bottom to top layer
        self.db.worn = []
        # How this character appears when logged off (persistent world): "sleeping here", etc.
        self.db.sleep_place = "sleeping here"
        # Room message when you log off (others see this); $N = your name. Default: "$N falls asleep."
        self.db.fall_asleep_message = "$N falls asleep."
        # Room message when you log on; $N = your name. Default: "$N wakes up."
        self.db.wake_up_message = "$N wakes up."
        # Hands: what is held in each hand (for wield/unwield). None = free.
        self.db.left_hand_obj = None
        self.db.right_hand_obj = None
        # Voice: optional short phrase (e.g. "British accented") shown rarely when speaking, based on listeners' perception
        self.db.voice = ""
        # Pronouns for emotes: "male" (he/his/him), "female" (she/her/her), "neutral"/"they" (they/their/them)
        self.db.pronoun = "neutral"
        # Age in years (set at chargen; optional for legacy NPCs)
        self.db.age_years = None
        # XP: gained every 6h while eligible (max 4 drops/24h); cap enforced so you stop earning after XP_CAP
        self.db.xp = 0
        from world.rpg.xp import XP_CAP
        self.db.xp_cap = int(XP_CAP)
        # PC vs NPC: NPCs do not show as "sleeping" when unpuppeted; set True for staff-created NPCs
        self.db.is_npc = False
        # Survival: hunger/thirst (0-100, higher = better) and intoxication state
        self.db.hunger = 100
        self.db.thirst = 100
        # Drunk level: 0 = sober, 1 = tipsy, 2 = drunk, 3 = wasted
        self.db.drunk_level = 0
        self.db.blood_alcohol = 0.0
        # Amputations / severed limbs (body part keys from world.medical.BODY_PARTS)
        self.db.missing_body_parts = []
        # Cyberware-added anatomy (e.g. chrome tail on a human); merged in world.body.get_character_body_parts
        self.db.extra_body_parts = []
        # Installed cyberware: list of CyberwareBase objects (location=None while installed)
        self.db.cyberware = []
        # Cyberware body description overrides — managed by CyberwareBase, not user-editable
        self.db.locked_descriptions = {}   # {part: text} — replaces user naked entirely
        self.db.appended_descriptions = {}  # {part: {typeclass_path: text}} — appended after user naked
        # Carved runes: {rune_key: {body_part, description, color_code, applied_at, settled, current_buff_value, artist_id, artist_name}}
        self.db.runes = {}
        # Skin tone (xterm256); set once via @skintone or chargen — colors IC name + biological body text
        self.db.skin_tone = None
        self.db.skin_tone_code = None
        self.db.skin_tone_set = False
        # Alchemy / drugs (see world.alchemy)
        self.db.addictions = {}
        self.db.active_drugs = {}
        self.db.known_recipes = []
        self.db.cyberpsychosis_score = 0
        self.db.trust = {}
        self.db.tattoos = {}
        self.db.active_makeup = []
        self.db.comedown_drugs = {}
        self.db.alchemy_analysis = {}
        # Stealth (see world.rpg.stealth)
        self.db.stealth_hidden = False
        self.db.stealth_roll_result = 0
        self.db.stealth_spotted_by = []

    def at_pre_move(self, destination, **kwargs):
        if getattr(self.ndb, "_break_in_started", False):
            self.ndb._break_in_started = False
            self.ndb._break_in_vehicle = None
            self.msg("|rBreak-in attempt interrupted.|n")
        if getattr(self.ndb, "_hotwire_started", False):
            self.ndb._hotwire_started = False
            self.ndb._hotwire_vehicle = None
            self.msg("|rHotwire attempt interrupted.|n")
        # Evennia: move_to aborts if `not at_pre_move(...)` — implicit None is falsy and blocks all moves.
        return super().at_pre_move(destination, **kwargs)

    def at_after_move(self, source_location, **kwargs):
        """Decrement makeup room counters on each room transition."""
        super().at_after_move(source_location, **kwargs)
        try:
            from world.cosmetics.makeup import decrement_makeup_room_count
            decrement_makeup_room_count(self)
        except Exception:
            pass

    def search(self, searchdata, **kwargs):
        """Exclude hidden characters the searcher has not spotted."""
        skip_stealth = kwargs.pop("skip_stealth_filter", False)
        res = super().search(searchdata, **kwargs)
        if skip_stealth:
            return res
        if not res:
            return res
        try:
            from world.rpg import stealth

            def _visible(obj):
                if obj is self:
                    return True
                if stealth.is_hidden(obj) and not stealth.has_spotted(self, obj):
                    return False
                return True

            quiet = kwargs.get("quiet", False)

            if isinstance(res, (list, tuple)):
                filtered = [o for o in res if _visible(o)]
                if quiet:
                    return filtered
                return filtered if filtered else None
            if not _visible(res):
                return None
            return res
        except Exception:
            return res

    def return_appearance(self, looker, **kwargs):
        """Same as DefaultObject but pass IC-colored name into the template."""
        if not looker:
            return ""
        from world.skin_tones import format_ic_character_name

        plain_name = super().get_display_name(looker, **kwargs)
        ic_name = format_ic_character_name(self, looker, plain_name)
        return self.format_appearance(
            self.appearance_template.format(
                name=ic_name,
                extra_name_info=self.get_extra_display_name_info(looker, **kwargs),
                desc=self.get_display_desc(looker, **kwargs),
                header=self.get_display_header(looker, **kwargs),
                footer=self.get_display_footer(looker, **kwargs),
                exits=self.get_display_exits(looker, **kwargs),
                characters=self.get_display_characters(looker, **kwargs),
                things=self.get_display_things(looker, **kwargs),
            ),
            looker,
            **kwargs,
        )

    def trusts(self, actor, category):
        """True if this character trusts actor for the given trust category (recog-based)."""
        from world.rpg.trust import check_trust

        return check_trust(self, actor, category)

    def trusts_or_incapacitated(self, actor, category, operate_strict=False):
        """(allowed, reason) — trust or sedated/restrained/flatlined/unconscious."""
        from world.rpg.trust import check_trust_or_incapacitated

        return check_trust_or_incapacitated(self, actor, category, operate_strict=operate_strict)

    def at_server_start(self):
        """Re-apply cyberware buffs after a server restart (BuffHandler is non-persistent)."""
        super().at_server_start()
        # Backfill any body parts added since last login (e.g. new cyberware anatomy).
        try:
            self._sync_body_descriptions()
        except Exception as err:
            logger.log_trace(f"characters.at_server_start _sync_body_descriptions: {err}")
        # Clear stale procedure lock on startup and reconcile unconscious timers/cmdset.
        self.db.surgery_in_progress = False
        try:
            from world.combat.grapple import reconcile_unconscious_state, reconcile_grapple_cmdsets_after_reload

            reconcile_unconscious_state(self)
            reconcile_grapple_cmdsets_after_reload(self)
        except Exception as err:
            logger.log_trace(f"characters.at_server_start reconcile_unconscious_state: {err}")
        for obj in (self.db.cyberware or []):
            try:
                obj.reapply_buffs(self)
            except Exception as err:
                logger.log_trace(f"characters.at_server_start reapply_buffs ({obj}): {err}")
        try:
            from world.alchemy.effects import reconcile_active_drugs_after_reload

            reconcile_active_drugs_after_reload(self)
        except Exception as err:
            logger.log_trace(f"characters.at_server_start reconcile_active_drugs: {err}")
        try:
            from world.runes.rune_system import reapply_rune_buffs

            reapply_rune_buffs(self)
        except Exception as err:
            logger.log_trace(f"characters.at_server_start reapply_rune_buffs: {err}")

    def install_cyberware(self, cyberware_obj, skip_surgery=False):
        """
        Install a piece of cyberware onto this character.

        Conflict checks:
          - Typeclass uniqueness: only one instance of each subclass allowed.
          - Locked body part overlap: two items cannot lock the same body part.

        If skip_surgery is False (default), on_surgery_install() is called after
        on_install() to record a surgical wound. Pass skip_surgery=True to bypass
        (e.g. for staff-only instant installs or narrative reasons).

        Returns True on success, or an error string on failure.
        """
        from typeclasses.cyberware import CyberwareBase
        if not isinstance(cyberware_obj, CyberwareBase):
            return "That is not a cyberware object."
        installed = list(self.db.cyberware or [])
        if any(type(c) is type(cyberware_obj) for c in installed):
            return f"{type(cyberware_obj).__name__} is already installed."
        installed_types = {type(c).__name__ for c in installed}
        for conflict_name in (getattr(cyberware_obj, "conflicts_with", None) or []):
            if conflict_name in installed_types:
                return f"Conflicts with installed {conflict_name}."
        for req_name in (getattr(cyberware_obj, "required_implants", None) or []):
            if req_name not in installed_types:
                return f"Requires {req_name} to be installed first."
        req_any = list(getattr(cyberware_obj, "required_implants_any", None) or [])
        if req_any and not any(name in installed_types for name in req_any):
            return f"Requires one of: {', '.join(req_any)}."
        adds = list(getattr(cyberware_obj, "adds_body_parts", None) or [])
        if adds or cyberware_obj.body_mods:
            from world.body import (
                commit_adds_body_parts,
                preview_body_parts_for_cyberware_install,
            )

            preview = preview_body_parts_for_cyberware_install(self, cyberware_obj)
            if cyberware_obj.body_mods:
                for part, (mode, _) in cyberware_obj.body_mods.items():
                    if part not in preview:
                        return f"Body part '{part}' is not part of your anatomy."
                locked = self.db.locked_descriptions or {}
                for part, (mode, _) in cyberware_obj.body_mods.items():
                    if mode == "lock" and part in locked:
                        return f"Body part '{part}' is already locked by installed cyberware."
            extras_before = list(getattr(self.db, "extra_body_parts", None) or [])
            try:
                commit_adds_body_parts(self, cyberware_obj)
                cyberware_obj.on_install(self)
            except Exception:
                self.db.extra_body_parts = extras_before
                raise
        else:
            cyberware_obj.on_install(self)
        if not skip_surgery:
            try:
                cyberware_obj.on_surgery_install(self)
            except Exception as err:
                logger.log_trace(f"install_cyberware on_surgery_install: {err}")
        installed.append(cyberware_obj)
        self.db.cyberware = installed
        self.ndb._max_stamina_cardio = None  # invalidate max_stamina cache
        self._sync_body_descriptions()       # backfill any new anatomy added by this implant
        return True

    def remove_cyberware(self, obj_or_name, skip_surgery=False):
        """
        Remove an installed piece of cyberware.

        Accepts a cyberware object or a name string (matched case-insensitively).
        The object materialises in the room regardless — staff disposes as needed.

        If skip_surgery is False (default), on_surgery_removal() is called before
        on_uninstall() to record a surgical wound.

        Returns True on success, or an error string on failure.
        """
        installed = list(self.db.cyberware or [])
        if isinstance(obj_or_name, str):
            matches = [c for c in installed if c.key.lower() == obj_or_name.lower()]
            if not matches:
                return f"No cyberware named '{obj_or_name}' is installed."
            obj = matches[0]
        else:
            if obj_or_name not in installed:
                return "That cyberware is not installed on this character."
            obj = obj_or_name
        if not skip_surgery:
            try:
                obj.on_surgery_removal(self)
            except Exception as err:
                logger.log_trace(f"remove_cyberware on_surgery_removal: {err}")
        obj.on_uninstall(self)
        installed.remove(obj)
        self.db.cyberware = installed
        self.ndb._max_stamina_cardio = None  # invalidate max_stamina cache
        from world.body import cleanup_adds_body_parts_on_remove

        cleanup_adds_body_parts_on_remove(self, obj, installed)
        # Re-check eye-dependent modules after removals.
        from typeclasses.cyberware_catalog import TargetingReticle
        for cw in installed:
            if not isinstance(cw, TargetingReticle):
                continue
            try:
                if hasattr(cw, "_has_eye_dependency") and not cw._has_eye_dependency(self):
                    if getattr(cw, "buff_class", None):
                        self.buffs.remove(cw.buff_class.key)
            except Exception:
                pass
        return True

    def get_cyberware(self):
        """Return a list of all installed cyberware objects."""
        return list(self.db.cyberware or [])

    def has_cyberware(self, obj):
        """Return True if the given cyberware object is installed on this character."""
        return obj in (self.db.cyberware or [])

    def get_arc_vulnerability(self):
        """Sum additional incoming arc damage multiplier from installed cyberware."""
        total = 0.0
        for cw in (self.db.cyberware or []):
            if getattr(cw.db, "malfunctioning", False):
                continue
            buff = getattr(cw, "buff_class", None)
            if buff:
                vulns = getattr(buff, "vulnerabilities", None) or {}
            else:
                vulns = getattr(cw, "vulnerabilities", None) or {}
            total += float(vulns.get("arc", 0.0))
        return total

    def at_server_reload(self):
        """
        After a @reload, re-apply transient command locks.

        Flatlined characters lose their non-persistent FlatlinedCmdSet on reload;
        re-add it so they remain fully locked in the dying state.
        """
        try:
            from world.death import is_flatlined
            if is_flatlined(self):
                try:
                    self.cmdset.add("commands.default_cmdsets.FlatlinedCmdSet", persistent=False)
                except Exception as err:
                    logger.log_trace("characters.at_server_reload FlatlinedCmdSet: %s" % err)
        except Exception as err:
            logger.log_trace("characters.at_server_reload is_flatlined: %s" % err)
        # Reload should never leave a stale surgery lock behind.
        self.db.surgery_in_progress = False
        try:
            from world.combat.grapple import reconcile_unconscious_state
            reconcile_unconscious_state(self)
        except Exception as err:
            logger.log_trace("characters.at_server_reload reconcile_unconscious_state: %s" % err)



    def at_init(self):
        """Ensure character uses the game's CharacterCmdSet (stats, heal, etc.). Fixes old chars with wrong path.
        We only fix persisted cmdset_storage here; we do not call cmdset.update(init_mode=True) because a failed
        load would leave cmdset.current None and break the cmdset merger (AttributeError: 'NoneType' no_objs).
        Correct path will be used on next server reload when the handler re-inits from storage.
        """
        from django.conf import settings
        want_path = getattr(settings, "CMDSET_CHARACTER", "commands.default_cmdsets.CharacterCmdSet")
        storage = getattr(self, "cmdset_storage", None)
        if storage is None:
            return
        current = storage[0] if isinstance(storage, (list, tuple)) and storage else None
        if current != want_path:
            self.cmdset_storage = [want_path] if isinstance(storage, (list, tuple)) else [want_path]

    def get_cmdsets(self, caller, current, **kwargs):
        """Return cmdsets for merger. Never return None for current so the merger never hits 'NoneType' no_objs."""
        cur = self.cmdset.current
        stack = list(self.cmdset.cmdset_stack)
        if cur is None:
            from evennia.commands.cmdset import CmdSet
            cur = CmdSet()  # empty fallback so merger does not crash
        return cur, stack

    def _sync_body_descriptions(self):
        """
        Ensure db.body_descriptions contains an entry for every current body part.
        Writes to DB only when new parts are actually missing. Call this from
        at_server_start and install_cyberware rather than on every look.
        """
        current = dict(getattr(self.db, "body_descriptions", None) or {})
        added = False
        for part in _body_parts(self):
            if part not in current:
                current[part] = ""
                added = True
        if added:
            self.db.body_descriptions = current

    def get_body_descriptions(self):
        """
        Return dict of body part -> description string (for appearance/look).
        Full pipeline: naked → missing → cyberware → injuries → treatment → clothing.
        Does not write to DB; call _sync_body_descriptions() to backfill missing parts.
        """
        from world.appearance import get_effective_body_descriptions
        return get_effective_body_descriptions(self)

    def format_body_appearance(self):
        """
        Merge body-part descriptions into three paragraphs: head/face, upper body, lower body.
        Identical descriptions in a region are shown once (first occurrence order), so one
        garment covering e.g. torso and shoulders doesn't repeat even with arms in between.
        Returns the full string (one or more paragraphs) or "" if nothing set.
        """
        from world.appearance import format_body_appearance

        return format_body_appearance(self.get_body_descriptions(), character=self)

    def format_appearance(self, appearance, looker, **kwargs):
        """Allow one blank line between paragraphs (Evennia default collapses to single newline)."""
        return compress_whitespace(appearance, max_linebreaks=2).strip()

    def get_display_desc(self, looker, **kwargs):
        """
        Look description order: general "describe me as" line first, then body-part paragraphs.
        """
        general = (getattr(self.db, "general_desc", None) or "This is a character.").strip()
        try:
            from world.skin_tones import format_ic_sdesc_fragment

            general = format_ic_sdesc_fragment(self, looker, general)
        except Exception as err:
            logger.log_trace("characters.get_display_desc skin tone: %s" % err)
        merged = self.format_body_appearance()
        outfit_line = ""
        try:
            from world.rpg.tailoring import get_outfit_quality_line
            outfit_line = get_outfit_quality_line(self, looker)
        except Exception as err:
            logger.log_trace("characters.get_display_desc outfit_line: %s" % err)
        parts = [general]
        if merged:
            parts.append(merged)
        if outfit_line:
            parts.append(outfit_line)
        return "\n\n".join(parts)

    def get_extra_display_name_info(self, looker=None, **kwargs):
        """Short desc next to name when they see your name/recog: (a tall man wearing...)."""
        if looker == self:
            try:
                from world.rpg.sdesc import get_short_desc
                sdesc = get_short_desc(self, looker)
                if sdesc:
                    return " (" + sdesc + ")"
            except Exception as err:
                logger.log_trace("characters.get_extra_display_name_info self sdesc: %s" % err)
            return ""
        # Only show (sdesc) when looker sees our name/recog, not when they only see sdesc
        try:
            from world.rp_features import get_character_sdesc_for_viewer
            from world.skin_tones import format_ic_sdesc_fragment

            sdesc_shown = get_character_sdesc_for_viewer(self, looker)
            name_shown = self.get_display_name(looker, **kwargs)
            if name_shown != sdesc_shown and sdesc_shown:
                col = format_ic_sdesc_fragment(self, looker, sdesc_shown)
                return " (" + col + ")"
        except Exception as err:
            logger.log_trace("characters.get_extra_display_name_info sdesc_for_viewer: %s" % err)
        return ""

    def get_display_things(self, looker, **kwargs):
        """Show what is held in each hand when looking at a character; pronoun-aware."""
        left = getattr(self.db, "left_hand_obj", None)
        right = getattr(self.db, "right_hand_obj", None)
        if right and getattr(right, "location", None) != self:
            right = None
        if left and getattr(left, "location", None) != self:
            left = None
        if left is right and right is None:
            return ""
        from world.medical import _pronoun_sub_poss
        sub_cap, poss = _pronoun_sub_poss(self)
        verb = "are" if sub_cap.lower() == "they" else "is"

        def _article(name):
            n = (name or "").strip()
            if not n:
                return "a "
            n_lower = n.lower()
            # Don't add article for plural-looking names (e.g. bandages, knives)
            if n_lower.endswith(("es", "ies", "ves")) or (n_lower.endswith("s") and not n_lower.endswith("ss")):
                return ""
            return "an " if n_lower[0] in "aeiou" else "a "

        def _name(obj):
            return obj.get_display_name(looker, **kwargs) if hasattr(obj, "get_display_name") else str(obj)

        if right and left is right:
            name = _name(right)
            return "%s %s holding %s in %s hands." % (sub_cap, verb, _article(name) + name, poss)
        if right and left:
            rname = _name(right)
            lname = _name(left)
            return "%s %s holding %s in %s right hand and %s in %s left." % (
                sub_cap, verb, _article(rname) + rname, poss, _article(lname) + lname, poss
            )
        if right:
            name = _name(right)
            return "%s %s holding %s in %s right hand." % (sub_cap, verb, _article(name) + name, poss)
        if left:
            name = _name(left)
            return "%s %s holding %s in %s left hand." % (sub_cap, verb, _article(name) + name, poss)
        return ""

    def msg(self, text=None, from_obj=None, session=None, **kwargs):
        """Send message to this character; if in multi-puppet set, relay to account with 'P1 Name: ' prefix so feed and slot-command output are visible."""
        relayed_only = multi_puppet_relay(self, text, session=session, **kwargs)
        if relayed_only:
            session = None
        if isinstance(text, str) and getattr(self.db, "drug_color_shift", False):
            try:
                from world.alchemy.effects import apply_msg_color_shift

                text = apply_msg_color_shift(self, text)
            except Exception as err:
                logger.log_trace(f"characters.msg drug_color_shift: {err}")
        return super().msg(text=text, from_obj=from_obj, session=session, **kwargs)

    def at_post_puppet(self, **kwargs):
        # Only the go shard (clone awakening) pipeline sets this; no other puppet flow should set it.
        # When set, we skip *only* the default "You become X" message from the parent, then run
        # our normal post-puppet logic (last_puppet, XP, awake line, room wake_up_message). All other puppeting keeps "You become".
        go_shard_awakening = getattr(self.db, "_suppress_become_message", False)
        if go_shard_awakening:
            try:
                # DbHolder supports attribute-style deletion, not item-style.
                if hasattr(self.db, "_suppress_become_message"):
                    del self.db._suppress_become_message
            except Exception as err:
                logger.log_trace("characters.at_post_puppet suppress_become_message: %s" % err)
            # Do what DefaultObject.at_post_puppet does except the msg("You become ...")
            if hasattr(self, "account") and self.account:
                self.account.db._last_puppet = self
            # Fall through to our normal logic below (no return here)
        else:
            _puppet_become_and_look_no_room_broadcast(self)
        # Never run chargen for NPCs (e.g. when staff puppet an NPC then puppet back to PC).
        if getattr(self.db, "is_npc", False):
            return
        # If needs_chargen is True but character clearly already completed chargen (stale/corrupted flag),
        # e.g. after puppet-switching, avoid forcing them back into the pipeline.
        if getattr(self.db, "needs_chargen", False):
            stats = getattr(self.db, "stats", None)
            priority = getattr(self.db, "stat_priority_order", None)
            if priority or (stats and any((v or 0) for v in stats.values())):
                self.db.needs_chargen = False
            else:
                from world.rpg.chargen import start_cinematic_chargen
                start_cinematic_chargen(self)
                return
        # CHECK: Are we jacked into the Matrix? Ask the rig to reconnect if valid.
        # Use db.matrix_rig (set by the jack-in pipeline) rather than db.sitting_on
        # so we don't accidentally treat any seat with a validate_and_reconnect method as a rig.
        rig = getattr(self.db, "matrix_rig", None) or (
            self.db.sitting_on
            if self.db.sitting_on and hasattr(self.db.sitting_on, "validate_and_reconnect")
            else None
        )
        if rig and hasattr(rig, 'validate_and_reconnect'):
            # Rig will validate connection and redirect to avatar if still valid
            if rig.validate_and_reconnect(self):
                return  # Successfully redirected to avatar

        # Normal post-puppet: grant pending XP, personal line, room wake-up (not Evennia's "entered the game")
        from world.rpg.xp import grant_pending_xp
        xp_granted, drops = grant_pending_xp(self)
        if xp_granted > 0 and drops > 0:
            self.msg("|gYou got {} XP.|n".format(int(xp_granted) if xp_granted == int(xp_granted) else xp_granted))
        self.msg("|cYou open your eyes and return to the world, awake.|n")
        if self.location:
            try:
                from world.rpg.crafting import substitute_clothing_desc
                msg = getattr(self.db, "wake_up_message", None) or "$N wakes up."
                msg = substitute_clothing_desc(msg, self)
                if msg:
                    self.location.msg_contents(msg, exclude=[self])
            except Exception as err:
                logger.log_trace("characters.at_post_puppet wake_up_message: %s" % err)

        try:
            from world.rpg.artistry_specialization import (
                needs_artistry_specialization_choice,
                open_artistry_specialization_menu,
            )

            if needs_artistry_specialization_choice(self) and not getattr(
                self.ndb, "artistry_spec_menu_prompted_session", False
            ):
                self.ndb.artistry_spec_menu_prompted_session = True
                open_artistry_specialization_menu(self)
        except Exception as err:
            logger.log_trace("characters.at_post_puppet artistry_specialization: %s" % err)

    def at_post_unpuppet(self, account=None, session=None, **kwargs):
        """
        When you stop controlling this character (e.g. log off, @ic another), they stay in the room.
        PCs: room sees fall-asleep message and "sleeping here" on look. NPCs: no sleep state.
        """
        if not self.sessions.count():
            if getattr(self.db, "is_npc", False):
                # NPCs do not go to logged-off/sleep state; they stay "present" with room_pose
                return
            try:
                from commands.performance_cmds import stop_performance_if_active
                stop_performance_if_active(self)
            except Exception as err:
                logger.log_trace("characters.at_post_unpuppet stop_performance: %s" % err)
            import time
            self.db.last_logout_time = time.time()  # for 30-min rule: get/strip from logged-off only after this
            try:
                from world.combat.grapple import release_grapple_forced
                victim = getattr(self.db, "grappling", None)
                if victim:
                    def _sleep_grapple_msg(v):
                        cname = self.get_display_name(v) if hasattr(self, "get_display_name") else self.name
                        vname = victim.get_display_name(v) if hasattr(victim, "get_display_name") else victim.name
                        return "As %s falls asleep, their grip releases %s." % (cname, vname)
                    release_grapple_forced(self, room_message=_sleep_grapple_msg)
            except Exception as err:
                logger.log_trace("characters.at_post_unpuppet release_grapple: %s" % err)
            if self.location:
                skip_fall_asleep_broadcast = False
                try:
                    from world.death import is_flatlined, is_permanently_dead

                    if is_flatlined(self) or is_permanently_dead(self):
                        skip_fall_asleep_broadcast = True
                except ImportError:
                    pass
                going_ooc = getattr(self.db, "_ooc_going_ooc", False)
                try:
                    self.attributes.remove("_ooc_going_ooc")
                except Exception:
                    pass
                if not skip_fall_asleep_broadcast and not going_ooc:
                    try:
                        from world.rpg.crafting import substitute_clothing_desc
                        msg = getattr(self.db, "fall_asleep_message", None) or "$N falls asleep."
                        msg = substitute_clothing_desc(msg, self)
                        if msg:
                            self.location.msg_contents(msg, exclude=[self])
                    except Exception as err:
                        logger.log_trace("characters.at_post_unpuppet fall_asleep_message: %s" % err)
                self.db.prelogout_location = self.location
            # Do NOT set self.location = None; character stays in the room.

    @property
    def carry_capacity(self):
        """Carry capacity from strength display level (uses get_display_stat from RPGCharacterMixin)."""
        str_display = self.get_display_stat("strength")
        return 10 + (str_display * 10)

    def get_factions(self):
        """Return list of faction dicts this character belongs to."""
        from world.rpg.factions import get_character_factions

        return get_character_factions(self)

    def get_faction_rank(self, faction_key):
        """Return rank number in a faction, or 0 if not a member."""
        from world.rpg.factions.membership import get_member_rank

        return get_member_rank(self, faction_key)

    def is_faction_member(self, faction_key):
        """Check faction membership."""
        from world.rpg.factions import is_faction_member

        return is_faction_member(self, faction_key)

    def get_faction_display(self):
        """Formatted faction memberships for @sheet display."""
        factions = self.get_factions()
        if not factions:
            return "None"
        from world.rpg.factions.ranks import get_rank_name
        ranks = self.db.faction_ranks or {}
        parts = []
        for fdata in factions:
            rank = ranks.get(fdata["key"], 1)
            rank_name = get_rank_name(fdata["ranks"], rank)
            parts.append(f"{fdata['color']}{fdata['short_name']}|n ({rank_name})")
        return ", ".join(parts)

    def at_post_move(self, source_location, move_type="move", **kwargs):
        """
        After moving to a new room, clear any temporary place (@tp) so it only applies
        in the room where it was set. Persistent @lp (room_pose) is not touched.
        """
        # Let parent hooks run first
        try:
            super().at_post_move(source_location, move_type=move_type, **kwargs)
        except Exception:
            # Be defensive in case a parent doesn't implement at_post_move
            pass

        try:
            from world.rpg import stealth

            sneak = False
            if hasattr(self.ndb, "_stealth_move_sneak"):
                sneak = bool(getattr(self.ndb, "_stealth_move_sneak", False))
                del self.ndb._stealth_move_sneak
            loc = getattr(self, "location", None)
            if loc and hasattr(loc, "contents_get"):
                if sneak:
                    stealth.sneak_arrival(self, loc)
                stealth.run_arrival_detection(self, loc)
                if sneak:
                    if stealth.sneak_breaks_stealth_combat(self):
                        stealth.reveal(self, "combat")
                elif stealth.is_hidden(self):
                    stealth.reveal(self, "action")
        except Exception:
            pass

        if self.attributes.has("temp_room_pose"):
            try:
                del self.db.temp_room_pose
            except Exception:
                self.db.temp_room_pose = None
