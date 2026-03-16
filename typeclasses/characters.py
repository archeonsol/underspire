from evennia import DefaultCharacter
from evennia.utils.utils import compress_whitespace
import random


def _multi_puppet_relay(self, text, session=None, **kwargs):
    """
    If this character is in an account's multi-puppet set, send the message to that
    account's session(s) with "P1 Name: " prefix. When they are temporarily the current
    puppet with no sessions (e.g. p2 look, p3 attack), we relay and return True so the
    caller passes session=None to the parent (user sees only the prefixed feed).
    """
    account_id = getattr(self.db, "_multi_puppet_account_id", None)
    slot = getattr(self.db, "_multi_puppet_slot", None)
    if not account_id or not slot:
        return False

    # Use standard Django/Evennia ORM to get the account (get_account_from_uid is not on all manager setups)
    try:
        from evennia.accounts.models import AccountDB
        account = AccountDB.objects.get(id=int(account_id))
    except Exception:
        # Catches AccountDB.DoesNotExist, ValueError if ID is invalid, etc.
        # Stale link: clear local markers so we don't keep trying.
        try:
            if hasattr(self.db, "_multi_puppet_account_id"):
                del self.db["_multi_puppet_account_id"]
            if hasattr(self.db, "_multi_puppet_slot"):
                del self.db["_multi_puppet_slot"]
        except Exception:
            pass
        return False

    # If this character is no longer in the account's multi_puppets list, treat link as stale.
    try:
        mp_ids = list(getattr(account.db, "multi_puppets", None) or [])
        if getattr(self, "id", None) not in mp_ids:
            try:
                if hasattr(self.db, "_multi_puppet_account_id"):
                    del self.db["_multi_puppet_account_id"]
                if hasattr(self.db, "_multi_puppet_slot"):
                    del self.db["_multi_puppet_slot"]
            except Exception:
                pass
            return False
    except Exception:
        pass

    if not hasattr(account, "sessions"):
        return False
    sess_list = account.sessions.get()
    if not sess_list:
        return False

    main_sess = sess_list[0]
    # If the player is currently puppeting THIS character AND it has its own sessions, no relay needed
    own_list = (getattr(self, "sessions", None) or [])
    if hasattr(own_list, "get"):
        own_list = own_list.get() or (own_list.all() if hasattr(own_list, "all") else [])
    has_own_sessions = bool(own_list)
    if getattr(main_sess, "puppet", None) == self and has_own_sessions:
        return False

    # Evennia often passes text as a tuple like ("Message", {"type": "say"})
    raw = text[0] if isinstance(text, (tuple, list)) and text else text
    if not raw or not isinstance(raw, str) or not raw.strip():
        return False
    raw = str(raw)

    prefix = "|cP%s %s|n: " % (slot, self.name)
    try:
        account.msg(prefix + raw, session=sess_list)
    except Exception:
        pass
    # When we relayed for a slot puppet (current puppet with no sessions), don't also send via parent
    return getattr(main_sess, "puppet", None) == self and not has_own_sessions

# Body-part groups for merging descriptions into three paragraphs (head/face, upper body, lower body)
def _body_parts():
    from world.medical import BODY_PARTS
    return BODY_PARTS


def _body_part_groups():
    """Return (head_face, upper_body, lower_body) lists of body part keys."""
    parts = _body_parts()
    head_face = ["head", "face", "neck"]
    upper_body = ["left shoulder", "right shoulder", "left arm", "right arm", "left hand", "right hand", "torso", "back", "abdomen"]
    lower_body = ["groin", "left thigh", "right thigh", "left foot", "right foot"]
    return head_face, upper_body, lower_body


# When you look at a character: name = orange (match room look), sdesc in parens = white
LOOK_CHARACTER_NAME_COLOR = "|520"   # warm orange/amber (same as room character list)
LOOK_SDESC_COLOR = "|w"              # white for (a tall man wearing...)


class Character(DefaultCharacter):
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
        # How this character appears in room look: "standing here", "sitting by the fire", etc.
        self.db.room_pose = "standing here"
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
        from world.xp import XP_CAP
        self.db.xp_cap = int(getattr(self.db, "xp_cap", XP_CAP) or XP_CAP)
        # PC vs NPC: NPCs do not show as "sleeping" when unpuppeted; set True for staff-created NPCs
        self.db.is_npc = False
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
                except Exception:
                    pass
        except Exception:
            pass

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

    def announce_move_from(self, destination, msg=None, mapping=None, move_type="move", **kwargs):
        """Announce departure as 'X leaves (direction).' for normal movement."""
        if not self.location:
            return
        if move_type not in ("move", "traverse") or not destination:
            super().announce_move_from(destination, msg=msg, mapping=mapping, move_type=move_type, **kwargs)
            return
        location = self.location
        exits = [
            o for o in (getattr(location, "contents", None) or [])
            if getattr(o, "destination", None) is destination
        ]
        if not exits:
            super().announce_move_from(destination, msg=msg, mapping=mapping, move_type=move_type, **kwargs)
            return
        direction = exits[0].key.strip()
        name = self.get_display_name(self)
        string = "%s leaves %s." % (name, direction)
        location.msg_contents(string, exclude=(self,), from_obj=self)

    def announce_move_to(self, source_location, msg=None, mapping=None, move_type="move", **kwargs):
        """Announce arrival as 'X walks in from the north' (or the exit key) for normal movement."""
        if not self.location:
            return
        if move_type not in ("move", "traverse") or not source_location:
            super().announce_move_to(source_location, msg=msg, mapping=mapping, move_type=move_type, **kwargs)
            return
        # Exit from source to here is in source's contents
        exits = [
            o for o in (getattr(source_location, "contents", None) or [])
            if getattr(o, "destination", None) is self.location
        ]
        if not exits:
            super().announce_move_to(source_location, msg=msg, mapping=mapping, move_type=move_type, **kwargs)
            return
        direction = exits[0].key.strip()
        name = self.get_display_name(self)
        string = "%s walks in from the %s." % (name, direction)
        self.location.msg_contents(string, exclude=(self,), from_obj=self)

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
            from world.tailoring import get_outfit_quality_line
            outfit_line = get_outfit_quality_line(self, looker)
        except Exception:
            pass
        parts = [general]
        if merged:
            parts.append(merged)
        if outfit_line:
            parts.append(outfit_line)
        return "\n\n".join(parts)

    def get_extra_display_name_info(self, looker=None, **kwargs):
        """Short desc next to name: (a tall man wearing a silk shirt and carrying a blade)."""
        try:
            from world.sdesc import get_short_desc
            sdesc = get_short_desc(self, looker)
            if sdesc:
                return " (" + sdesc + ")"
        except Exception:
            pass
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

    def at_say(self, message, msg_self=None, msg_location=None, receivers=None, msg_receivers=None, **kwargs):
        """
        Say (and whisper) hook. For room say, optionally show voice to listeners who pass perception check.
        """
        from evennia.utils.utils import make_iter
        from world.voice import get_voice_phrase, get_speaking_tag, voice_perception_check

        # Whisper or explicit receivers: use default behavior (no voice)
        if kwargs.get("whisper", False) or receivers:
            return super().at_say(
                message, msg_self=msg_self, msg_location=msg_location,
                receivers=receivers, msg_receivers=msg_receivers, **kwargs
            )

        custom_mapping = kwargs.get("mapping", {})
        location = self.location
        msg_type = "say"
        voice_phrase = get_voice_phrase(self)

        if msg_self:
            self_mapping = {
                "self": "You",
                "object": self.get_display_name(self),
                "location": location.get_display_name(self) if location else None,
                "receiver": None,
                "all_receivers": None,
                "speech": message,
            }
            self_mapping.update(custom_mapping)
            template = msg_self if isinstance(msg_self, str) else 'You say, "|n{speech}|n"'
            self.msg(text=(template.format_map(self_mapping), {"type": msg_type}), from_obj=self)

        if not location:
            return

        # Room say: send to each character in location (except self) with optional voice
        chars_here = location.contents_get(content_type="character")
        for viewer in make_iter(chars_here):
            if viewer == self:
                continue
            obj_name = self.get_display_name(viewer)
            if voice_phrase and voice_perception_check(viewer, self):
                tag = get_speaking_tag(self)
                speech_with_tag = tag + message
                line = '%s says in a %s, "*speaking in a %s* %s"' % (obj_name, voice_phrase, voice_phrase, message)
            else:
                line = '%s says, "%s"' % (obj_name, message)
            viewer.msg(text=(line, {"type": msg_type}), from_obj=self)
        # Feed cameras in room or held by anyone here (say does not use msg_contents)
        say_line = '%s says, "%s"' % (self.get_display_name(self), message)
        try:
            from typeclasses.broadcast import feed_cameras_in_location
            feed_cameras_in_location(location, say_line)
        except Exception:
            pass

    def get_grade_adjective(self, grade_letter):
        """Legacy: use get_stat_grade_adjective or get_skill_grade_adjective. Falls back to skill adjective."""
        from world.grades import get_skill_grade_adjective
        return get_skill_grade_adjective(grade_letter)

    def get_stat_level(self, stat_key):
        """Return stored stat level 0-300 (used for XP spending and letter lookup)."""
        from world.xp import _stat_level
        return _stat_level(self, stat_key)

    def get_display_stat(self, stat_name):
        """
        Return display level 0-150 for a stat (stored_level // 2). Use for all RPG mechanics and HP.
        No external code should perform // 2 on stored stats; use this method instead.
        """
        stored = self.get_stat_level(stat_name) or 0
        return min(int(stored) // 2, 150)

    def get_skill_level(self, skill_key):
        """Return skill level as int 0-150 (normalizes legacy letter to mid-tier)."""
        from world.xp import _skill_level
        return _skill_level(self, skill_key)

    def get_stat_grade_adjective(self, grade_letter, stat_key):
        """Adjective for this stat at this grade (letter-matched, per-stat)."""
        from world.grades import get_stat_grade_adjective as _get
        return _get(grade_letter, stat_key)

    def get_skill_grade_adjective(self, grade_letter):
        """Adjective for skills at this grade (letter-matched, shared set)."""
        from world.grades import get_skill_grade_adjective as _get
        return _get(grade_letter)

    def get_stat_cap(self, stat_key):
        """Return stored stat cap 0-300 (display as //2 for 0-150 scale)."""
        from world.xp import _stat_cap_level
        return _stat_cap_level(self, stat_key)

    def get_skill_cap(self, skill_key):
        """Return cap level for this skill (int 0-150)."""
        from world.xp import _skill_cap_level
        return _skill_cap_level(self, skill_key)

    def msg(self, text=None, from_obj=None, session=None, **kwargs):
        """Send message to this character; if in multi-puppet set, relay to account with 'P1 Name: ' prefix so feed and slot-command output are visible."""
        relayed_only = _multi_puppet_relay(self, text, session=session, **kwargs)
        # When we relayed for a slot puppet (p2 look, p3 attack, etc.), don't also send to session so user sees only the prefixed feed
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
                del self.db["_suppress_become_message"]
            except Exception:
                pass
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
        # Normal post-puppet: grant pending XP and wake-up message
        from world.xp import grant_pending_xp
        xp_granted, drops = grant_pending_xp(self)
        if xp_granted > 0 and drops > 0:
            self.msg("|gYou gain {} XP from {} neural-link sync(s) (max 4 per 24h).|n".format(xp_granted, drops))
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
            except Exception:
                pass

    def at_post_unpuppet(self, account=None, session=None, **kwargs):
        """
        When you stop controlling this character (e.g. log off, @ic another), they stay in the room.
        PCs: room sees fall-asleep message and "sleeping here" on look. NPCs: no sleep state.
        """
        if not self.sessions.count():
            if getattr(self.db, "is_npc", False):
                # NPCs do not go to logged-off/sleep state; they stay "present" with room_pose
                return
            import time
            self.db.last_logout_time = time.time()  # for 30-min rule: get/strip from logged-off only after this
            try:
                from world.grapple import release_grapple_forced
                victim = getattr(self.db, "grappling", None)
                if victim:
                    release_grapple_forced(
                        self,
                        room_message="As %s falls asleep, their grip releases %s." % (self.name, victim.name),
                    )
            except Exception:
                pass
            if self.location:
                try:
                    from world.crafting import substitute_clothing_desc
                    msg = getattr(self.db, "fall_asleep_message", None) or "$N falls asleep."
                    msg = substitute_clothing_desc(msg, self)
                    if msg:
                        self.location.msg_contents(msg, exclude=[self])
                except Exception:
                    pass
                self.db.prelogout_location = self.location
            # Do NOT set self.location = None; character stays in the room.

    # ==========================================
    # DERIVED STATS (Dynamic Calculation)
    # ==========================================

    # Miraculous benchmark: 114 display Endurance + 123 display Strength = 152 HP (str_bonus 11.5; base + end must = 140.5)
    BASE_HP = 26.5
    ENDURANCE_MULTIPLIER = 1.0

    @property
    def max_hp(self):
        """HP = BASE_HP + (endurance_display * ENDURANCE_MULTIPLIER) + str_hp_bonus. All stats via get_display_stat."""
        end_display = self.get_display_stat("endurance")
        str_display = self.get_display_stat("strength")
        str_hp_bonus = max(0, (str_display - 100) * 0.5)  # strength only contributes above 100 display
        total = self.BASE_HP + (end_display * self.ENDURANCE_MULTIPLIER) + str_hp_bonus
        return max(1, int(total))

    @property
    def hp(self):
        if self.db.current_hp is None:
            self.db.current_hp = self.max_hp
        return self.db.current_hp

    @property
    def max_stamina(self):
        """Stamina pool tied to endurance display level."""
        end_display = self.get_display_stat("endurance")
        return 20 + (end_display * 5)

    @property
    def stamina(self):
        if self.db.current_stamina is None:
            self.db.current_stamina = self.max_stamina
        return self.db.current_stamina

    @property
    def carry_capacity(self):
        """Carry capacity from strength display level."""
        str_display = self.get_display_stat("strength")
        return 10 + (str_display * 10)

    # ==========================================
    # THE SIMULATION ENGINE (The Roll)
    # ==========================================

    def roll_check(self, stat_list, skill_name, difficulty=0, modifier=0):
        """
        modifier: A hidden raw number added to the final result
                  (from stances, gear, or temporary states).
        Uses display level for stats (get_display_stat); skill level as-is. Both scaled to 1-21 (U–A).
        """
        if isinstance(stat_list, str):
            stat_list = [stat_list]

        from world.levels import level_to_effective_grade, MAX_LEVEL
        total_display = sum(self.get_display_stat(s) for s in stat_list)
        stat_val = level_to_effective_grade(int(total_display / len(stat_list)), MAX_LEVEL)

        skill_level = self.get_skill_level(skill_name)
        skill_val = level_to_effective_grade(skill_level, MAX_LEVEL)

        # 1. THE CEILING (Skill-based technical cap)
        ceiling = (skill_val * 6) + 10
        ceiling = min(100, ceiling)

        # 2. THE STRENGTH (Stat-based bonus)
        strength_bonus = stat_val * 2

        # 3. THE ROLL
        raw_roll = random.randint(1, 100)
        effective_roll = min(raw_roll, ceiling)
        final_result = effective_roll + strength_bonus + modifier - difficulty

        if final_result > 90:
            return "Critical Success", final_result
        if final_result > 60:
            return "Full Success", final_result
        if final_result > 35:
            return "Marginal Success", final_result
        return "Failure", final_result

    def at_damage(self, attacker, damage, body_part=None, weapon_key=None, weapon_obj=None):
        """Apply HP loss. At 0 HP enter flatlined state (dying). Records injury for natural regen."""
        self.db.current_hp -= damage
        if self.db.current_hp < 0:
            self.db.current_hp = 0
        try:
            from world.medical import add_injury
            add_injury(self, damage, body_part=body_part, weapon_key=weapon_key or "fists", weapon_obj=weapon_obj)
        except Exception:
            pass

        if self.db.current_hp <= 0:
            try:
                from world.death import make_flatlined, is_flatlined
                if not is_flatlined(self):
                    make_flatlined(self, attacker)
            except Exception:
                self.db.combat_ended = True
                self.msg("|rYour legs give. The ground comes up. You are done.|n")
                if attacker and attacker != self:
                    attacker.msg(f"|y{self.name} goes down and does not get up.|n")
                try:
                    from world.combat import remove_both_combat_tickers
                    remove_both_combat_tickers(self, attacker)
                except Exception:
                    pass

    def get_medical_summary(self):
        """Short trauma summary (organs, fractures, bleeding) for status lines."""
        from world.medical import get_medical_summary
        return get_medical_summary(self)

    def get_health_description(self, include_trauma=False):
        """
        Returns a narrative string based on the current HP percentage (outward appearance only).
        7 Layers: Unscathed -> Dead. Trauma (fractures, organs, bleeding) is only shown if
        include_trauma=True or via scanner/medical menu.
        """
        percent = (self.hp / self.max_hp) * 100 if self.max_hp > 0 else 0

        if percent >= 100:
            desc = "|gUnscathed.|n They stand tall, their skin and armor untouched by brutality."
        elif percent >= 85:
            desc = "|gScuffed.|n A few shallow grazes and cooling sweat; the damage is purely superficial."
        elif percent >= 65:
            desc = "|yBruised.|n Dark contusions are forming. A thin trickle of crimson escapes a split lip."
        elif percent >= 45:
            desc = "|yWounded.|n They are favoring one side, their breath coming in ragged, wet wheezes."
        elif percent >= 25:
            desc = "|rMangled.|n Deep lacerations reveal glimpses of pale muscle. They are struggling to maintain their footing."
        elif percent >= 5:
            desc = "|rNear Death.|n A ruin of a human being. Blood is pooling at their feet; their eyes are glazed and vacant."
        else:
            try:
                from world.death import is_flatlined
                if is_flatlined(self):
                    desc = "|rDying.|n Unconscious. No pulse. Flatline. They might still be brought back. Or time might run out."
                else:
                    desc = "|RDead.|n A heap of broken meat and shattered bone. The spark of life has long since flickered out."
            except Exception:
                desc = "|RDead.|n A heap of broken meat and shattered bone. The spark of life has long since flickered out."

        if include_trauma:
            medical = self.get_medical_summary()
            if medical and "No significant trauma" not in medical:
                desc = desc + "\n\n" + medical
        return desc
