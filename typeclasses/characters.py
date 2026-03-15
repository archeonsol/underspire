from evennia import DefaultCharacter
from evennia.utils.utils import compress_whitespace
import random

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


class Character(DefaultCharacter):
    """
    The 'Colony' Core Engine. 
    Uses a Qualitative Grade system (Q through A) where:
    - Skill = The success ceiling (Technical precision)
    - Stat = The roll weight/floor (Raw power)
    """

    # Stats 0-300, skills 0-150; letter tiers from world.levels (all 17 letters Q–A)

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
        # Pronouns for emotes: "male" (he/his/him), "female" (she/her/her), "neutral"/"they" (they/their/them)
        self.db.pronoun = "neutral"
        # XP: gained every 6h while eligible (max 4 drops/24h); cap enforced so you stop earning after XP_CAP
        self.db.xp = 0
        from world.xp import XP_CAP
        self.db.xp_cap = int(getattr(self.db, "xp_cap", XP_CAP) or XP_CAP)
        # PC vs NPC: NPCs do not show as "sleeping" when unpuppeted; set True for staff-created NPCs
        self.db.is_npc = False

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
        """Use merged body-paragraphs as the main description, replacing the default."""
        merged = self.format_body_appearance()
        if merged:
            return merged
        return super().get_display_desc(looker, **kwargs) or "This is a character."

    def get_extra_display_name_info(self, looker=None, **kwargs):
        """Hide character dbref (#id) from look so names stay clean."""
        return ""

    def get_display_things(self, looker, **kwargs):
        """Show what is held in each hand when looking at a character; hide rest of inventory."""
        left = getattr(self.db, "left_hand_obj", None)
        right = getattr(self.db, "right_hand_obj", None)
        parts = []
        if right and right.location == self:
            parts.append(right.get_display_name(looker, **kwargs) if hasattr(right, "get_display_name") else str(right))
        if left and left.location == self and left is not right:
            parts.append(left.get_display_name(looker, **kwargs) if hasattr(left, "get_display_name") else str(left))
        if parts:
            return "|wCarrying:|n " + ", ".join(parts)
        return ""

    def get_grade_adjective(self, grade_letter):
        """Legacy: use get_stat_grade_adjective or get_skill_grade_adjective. Falls back to skill adjective."""
        from world.grades import get_skill_grade_adjective
        return get_skill_grade_adjective(grade_letter)

    def get_stat_level(self, stat_key):
        """Return stored stat level 0-300 (used for letter/formulas; display as //2 for 0-150 scale)."""
        from world.xp import _stat_level
        return _stat_level(self, stat_key)

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

    @property
    def max_hp(self):
        from world.levels import level_to_effective_grade, MAX_STAT_LEVEL
        end = level_to_effective_grade(self.get_stat_level("endurance"), MAX_STAT_LEVEL)
        str_ = level_to_effective_grade(self.get_stat_level("strength"), MAX_STAT_LEVEL)
        return 50 + (end * 5) + (str_ * 3)

    @property
    def hp(self):
        if self.db.current_hp is None:
            self.db.current_hp = self.max_hp
        return self.db.current_hp

    @property
    def max_stamina(self):
        """Stamina pool is directly tied to endurance only."""
        from world.levels import level_to_effective_grade, MAX_STAT_LEVEL
        end = level_to_effective_grade(self.get_stat_level("endurance"), MAX_STAT_LEVEL)
        return 20 + (end * 5)

    @property
    def stamina(self):
        if self.db.current_stamina is None:
            self.db.current_stamina = self.max_stamina
        return self.db.current_stamina

    @property
    def carry_capacity(self):
        from world.levels import level_to_effective_grade, MAX_STAT_LEVEL
        str_ = level_to_effective_grade(self.get_stat_level("strength"), MAX_STAT_LEVEL)
        return 10 + (str_ * 10)

    # ==========================================
    # THE SIMULATION ENGINE (The Roll)
    # ==========================================

    def roll_check(self, stat_list, skill_name, difficulty=0, modifier=0):
        """
        modifier: A hidden raw number added to the final result
                  (from stances, gear, or temporary states).
        Stats 0-300, skills 0-150; both scaled to 1-17 for formula.
        """
        if isinstance(stat_list, str):
            stat_list = [stat_list]

        from world.levels import level_to_effective_grade, MAX_STAT_LEVEL, MAX_LEVEL
        total_stat = sum(self.get_stat_level(s) for s in stat_list)
        stat_val = level_to_effective_grade(int(total_stat / len(stat_list)), MAX_STAT_LEVEL)

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

    def at_damage(self, attacker, damage, body_part=None, weapon_key=None):
        """Apply HP loss. At 0 HP enter flatlined state (dying). Records injury for natural regen."""
        self.db.current_hp -= damage
        if self.db.current_hp < 0:
            self.db.current_hp = 0
        try:
            from world.medical import add_injury
            add_injury(self, damage, body_part=body_part, weapon_key=weapon_key or "fists")
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
