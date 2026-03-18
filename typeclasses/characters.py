from evennia import DefaultCharacter
from evennia.utils import logger
from evennia.utils.utils import compress_whitespace, lazy_property

from world.multipuppet import multi_puppet_relay
from typeclasses.mixins import FurnitureMixin, MedicalMixin, RPGCharacterMixin, RoleplayMixin


# Body-part groups for merging descriptions into three paragraphs (head/face, upper body, lower body)
def _body_parts():
    from world.medical import BODY_PARTS
    return BODY_PARTS


def _body_part_groups():
    """Return (head_face, upper_body, lower_body) lists of body part keys."""
    parts = _body_parts()
    head_face = ["head", "face", "left eye", "right eye", "neck"]
    upper_body = ["left shoulder", "right shoulder", "left arm", "right arm", "left hand", "right hand", "torso", "back", "abdomen"]
    lower_body = ["groin", "left thigh", "right thigh", "left foot", "right foot"]
    return head_face, upper_body, lower_body


# When you look at a character: name = orange (match room look), sdesc in parens = white
LOOK_CHARACTER_NAME_COLOR = "|520"   # warm orange/amber (same as room character list)
LOOK_SDESC_COLOR = "|w"              # white for (a tall man wearing...)


class Character(RoleplayMixin, MedicalMixin, RPGCharacterMixin, FurnitureMixin, DefaultCharacter):
    """
    The 'Colony' Core Engine.
    Uses a Qualitative Grade system (U through A, 21 letters) where:
    - Skill = The success ceiling (Technical precision)
    - Stat = The roll weight/floor (Raw power)
    """

    # Look-at-character header: orange name + white sdesc in parentheses (default Evennia uses cyan)
    appearance_template = """
{header}
""" + LOOK_CHARACTER_NAME_COLOR + """{name}|n""" + LOOK_SDESC_COLOR + """{extra_name_info}|n
{desc}
{exits}
{characters}
{things}
{footer}
"""

    # Stats 0-300, skills 0-150; letter tiers from world.levels (21 letters U–A)

    @lazy_property
    def buffs(self):
        """
        Timed/permanent modifiers (perfume, bad smells, cybernetics, traits).
        Backed by Evennia's generic BuffHandler; all mechanical effects flow
        through stat/skill helpers rather than touching stored values directly.
        """
        from evennia.contrib.rpg.buffs.buff import BuffHandler

        # Use a dedicated dbkey so buffs live on character.db.buffs.
        return BuffHandler(self, dbkey="buffs", autopause=True)

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

        self.db.current_hp = None
        self.db.current_stamina = None
        self.db.background = "Unknown"
        self.db.traits = []
        self.db.needs_chargen = True
        # General "describe me as" line (shown first when someone looks at you; short one-liner)
        self.db.general_desc = "This is a character."
        # Per-body-part descriptions for look/appearance (keys from world.medical.BODY_PARTS)
        self.db.body_descriptions = {part: "" for part in _body_parts()}
        # Medical / trauma (organs, fractures, bleeding) - see world.medical
        self.db.organ_damage = {}
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
        # XP: gained every 6h while eligible (max 4 drops/24h); cap enforced so you stop earning after XP_CAP
        self.db.xp = 0
        from world.rpg.xp import XP_CAP
        self.db.xp_cap = int(getattr(self.db, "xp_cap", XP_CAP) or XP_CAP)
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

    def get_body_descriptions(self):
        """
        Return dict of body part -> description string (for appearance/look).
        Uses worn clothing/armor to override parts they cover; uncovered parts use body_descriptions.
        """
        from world.clothing import get_effective_body_descriptions
        return get_effective_body_descriptions(self)

    def format_body_appearance(self):
        """
        Merge body-part descriptions into three paragraphs: head/face, upper body, lower body.
        Identical descriptions in a region are shown once (first occurrence order), so one
        garment covering e.g. torso and shoulders doesn't repeat even with arms in between.
        Returns the full string (one or more paragraphs) or "" if nothing set.
        """
        parts = self.get_body_descriptions()
        head_face, upper_body, lower_body = _body_part_groups()
        paragraphs = []
        for group in (head_face, upper_body, lower_body):
            bits = [(parts.get(p) or "").strip() for p in group]
            bits = [b for b in bits if b]
            # Unique in order of first appearance (no repeated phrase in this region)
            bits = list(dict.fromkeys(bits))
            if bits:
                paragraphs.append(" ".join(bits))
        return "\n\n".join(paragraphs) if paragraphs else ""

    def format_appearance(self, appearance, looker, **kwargs):
        """Allow one blank line between paragraphs (Evennia default collapses to single newline)."""
        return compress_whitespace(appearance, max_linebreaks=2).strip()

    def get_display_desc(self, looker, **kwargs):
        """
        Look description order: general "describe me as" line first, then body-part paragraphs.
        """
        general = (getattr(self.db, "general_desc", None) or "This is a character.").strip()
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
                from world.sdesc import get_short_desc
                sdesc = get_short_desc(self, looker)
                if sdesc:
                    return " (" + sdesc + ")"
            except Exception as err:
                logger.log_trace("characters.get_extra_display_name_info self sdesc: %s" % err)
            return ""
        # Only show (sdesc) when looker sees our name/recog, not when they only see sdesc
        try:
            from world.rp_features import get_character_sdesc_for_viewer
            sdesc_shown = get_character_sdesc_for_viewer(self, looker)
            name_shown = self.get_display_name(looker, **kwargs)
            if name_shown != sdesc_shown and sdesc_shown:
                return " (" + sdesc_shown + ")"
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
            return "%s %s holding %s in %s hands." % (sub_cap, verb, _article(name) + name, poss)
        if left:
            name = _name(left)
            return "%s %s holding %s in %s hands." % (sub_cap, verb, _article(name) + name, poss)
        return ""

    def msg(self, text=None, from_obj=None, session=None, **kwargs):
        """Send message to this character; if in multi-puppet set, relay to account with 'P1 Name: ' prefix so feed and slot-command output are visible."""
        relayed_only = multi_puppet_relay(self, text, session=session, **kwargs)
        if relayed_only:
            session = None
        return super().msg(text=text, from_obj=from_obj, session=session, **kwargs)

    def at_post_puppet(self, **kwargs):
        # Only the go shard (clone awakening) pipeline sets this; no other puppet flow should set it.
        # When set, we skip *only* the default "You become X" message from the parent, then run
        # our normal post-puppet logic (last_puppet, XP, wake-up). All other puppeting keeps "You become".
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
            super().at_post_puppet(**kwargs)
        # Never run chargen for NPCs (e.g. when staff puppet an NPC then puppet back to PC).
        if getattr(self.db, "is_npc", False):
            return
        # If needs_chargen is True but character clearly already completed chargen (stale/corrupted flag),
        # e.g. after puppet-switching, avoid forcing them back into the pipeline.
        if getattr(self.db, "needs_chargen", False):
            bg = getattr(self.db, "background", None)
            stats = getattr(self.db, "stats", None)
            if (bg and str(bg) != "Unknown") or (stats and any(stats.values())):
                self.db.needs_chargen = False
            else:
                from evennia.utils.evmenu import EvMenu
                EvMenu(self, "world.chargen", startnode="node_start")
                return
        # CHECK: Are we jacked into the Matrix? Ask the rig to reconnect if valid.
        rig = self.db.sitting_on
        if rig and hasattr(rig, 'validate_and_reconnect'):
            # Rig will validate connection and redirect to avatar if still valid
            if rig.validate_and_reconnect(self):
                return  # Successfully redirected to avatar

        # Normal post-puppet: grant pending XP and wake-up message
        from world.rpg.xp import grant_pending_xp
        xp_granted, drops = grant_pending_xp(self)
        if xp_granted > 0 and drops > 0:
            self.msg("|gYou got {} XP.|n".format(int(xp_granted) if xp_granted == int(xp_granted) else xp_granted))
        # Personal login message (only to the player)
        self.msg("|cYou open your eyes and return to the world, awake.|n")
        # Wake-up message to room when logging in (not during first-time chargen)
        if self.location:
            try:
                from world.crafting import substitute_clothing_desc
                msg = getattr(self.db, "wake_up_message", None) or "$N wakes up."
                msg = substitute_clothing_desc(msg, self)
                if msg:
                    self.location.msg_contents(msg, exclude=[self])
            except Exception as err:
                logger.log_trace("characters.at_post_puppet wake_up_message: %s" % err)

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
                from world.grapple import release_grapple_forced
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
                try:
                    from world.crafting import substitute_clothing_desc
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
        if hasattr(self.db, "temp_room_pose"):
            try:
                del self.db.temp_room_pose
            except Exception:
                self.db.temp_room_pose = None
