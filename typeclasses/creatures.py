"""
Creature framework for PvE. Creatures use raw combat stats (max_hp, base_attack, armor_rating)
and a moves dict (instant or telegraph) instead of the human stat/skill curves.
"""
import random
from typeclasses.characters import Character


# ----- Move spec format (for reference) -----
# Each move is a dict with:
#   weight (int): chance to pick this move (e.g. 50 = 50% when total weights sum to 100)
#   type (str): "instant" or "telegraph"
#   damage (int): HP damage on hit
#   msg (str): format with {name} and {target} for instant moves
#   execute_msg (str): for telegraph, message when the hit lands (also used as hit message if no msg_hit)
#   msg_hit (str): optional; message when attack hits (defaults to execute_msg or msg)
#   msg_miss (str): optional; message when target evades (default: generic dodge line)
#   telegraph_msg (str): for telegraph, message when wind-up starts
#   ticks (int): for telegraph, number of ticks before execute
#   weapon_key (str): for trauma/damage type (e.g. claws, bite, saw, fists); uses world.damage_types
#   unblockable (bool): if True, forces dodge not block (flavor / future use)
#   stamina_drain (int): optional stamina cost on target (e.g. block-crush)


class Creature(Character):
    """
    Base class for PvE monsters and bosses. Uses raw combat math (max_hp, base_attack,
    armor_rating) and a moves dict. Override get_moves() in subclasses to define attacks.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.is_creature = True
        self.db.is_npc = True
        self.db.needs_chargen = False

        # Raw combat math (no 0-300 stat curves)
        self.db.max_hp = 100
        self.db.current_hp = 100
        self.db.armor_rating = 10
        self.db.base_attack = 50

        # AI state
        self.db.ai_state = "idle"
        self.db.current_target = None
        self.db.queued_attack = None
        self.db.ticks_to_strike = 0

    def get_moves(self):
        """Override in subclasses to return a dict of move_key -> move_spec."""
        return getattr(self.db, "creature_moves", None) or {}

    # ---- Stats for combat integration (players attacking creatures) ----

    @property
    def max_hp(self):
        if getattr(self.db, "is_creature", False):
            return int(self.db.max_hp or 100)
        return super().max_hp

    @property
    def hp(self):
        if getattr(self.db, "is_creature", False):
            if self.db.current_hp is None:
                self.db.current_hp = self.max_hp
            return self.db.current_hp
        return super().hp

    def get_display_stat(self, stat_name):
        if getattr(self.db, "is_creature", False):
            # Single effective "level" so formulas don't break; derived from base_attack/armor
            base = getattr(self.db, "base_attack", 50) or 50
            return min(max(base, 0), 150)
        return super().get_display_stat(stat_name)

    def get_skill_level(self, skill_key):
        if getattr(self.db, "is_creature", False):
            base = getattr(self.db, "base_attack", 50) or 50
            return min(max(base, 0), 150)
        return super().get_skill_level(skill_key)

    def roll_check(self, stat_list, skill_name, difficulty=0, modifier=0):
        if getattr(self.db, "is_creature", False):
            base = int(getattr(self.db, "base_attack", 50) or 50)
            armor = int(getattr(self.db, "armor_rating", 10) or 10)
            raw = random.randint(1, 100)
            ceiling = min(100, base + 10)
            effective = min(raw, ceiling)
            final = effective + armor + modifier - difficulty
            if final > 90:
                return "Critical Success", final
            if final > 60:
                return "Full Success", final
            if final > 35:
                return "Marginal Success", final
            return "Failure", final
        return super().roll_check(stat_list, skill_name, difficulty=difficulty, modifier=modifier)

    def at_damage(self, attacker, damage, body_part=None, weapon_key=None, weapon_obj=None):
        if not getattr(self.db, "is_creature", False):
            super().at_damage(attacker, damage, body_part=body_part, weapon_key=weapon_key, weapon_obj=weapon_obj)
            return
        self.db.current_hp = (self.db.current_hp or self.max_hp) - damage
        if self.db.current_hp < 0:
            self.db.current_hp = 0
        if self.db.current_hp <= 0:
            self.db.combat_ended = True
            try:
                from world.creature_combat import stop_creature_ai_ticker
                stop_creature_ai_ticker(self)
            except Exception:
                pass
            try:
                from world.combat import remove_both_combat_tickers
                remove_both_combat_tickers(self, attacker)
            except Exception:
                pass
            if self.location:
                self.location.msg_contents("|r%s falls dead.|n" % self.name, exclude=(self,))
            if attacker and attacker != self and hasattr(attacker, "msg"):
                attacker.msg("|y%s goes down. It's dead.|n" % self.name)


# ----- Example creatures -----

class GutterHulk(Creature):
    """Heavy mutant with claw swipes and a telegraphed rad-beam."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.key = "Gutter Hulk"
        self.db.max_hp = 500
        self.db.current_hp = 500
        self.db.armor_rating = 20
        self.db.base_attack = 65
        self.db.room_pose = "lumbering here, claws dragging."

    def get_moves(self):
        return {
            "swipe": {
                "weight": 50,
                "type": "instant",
                "damage": 25,
                "weapon_key": "claws",
                "msg": "|r{name} violently swipes a massive claw at {target}!|n",
            },
            "rad_beam": {
                "weight": 20,
                "type": "telegraph",
                "ticks": 1,
                "telegraph_msg": "|r{name} inhales deeply, its throat glowing a blinding, toxic green!|n",
                "execute_msg": "|R{name} unleashes a torrent of radioactive fire at {target}!|n",
                "damage": 120,
                "weapon_key": "fire",
                "unblockable": True,
                "stamina_drain": 40,
            },
            "crush": {
                "weight": 30,
                "type": "instant",
                "damage": 45,
                "weapon_key": "fists",
                "msg": "|r{name} slams both fists down on {target}!|n",
            },
        }


class SporeRunner(Creature):
    """Fast, spore-spewing runner that prefers hit-and-run."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.key = "Spore Runner"
        self.db.max_hp = 120
        self.db.current_hp = 120
        self.db.armor_rating = 5
        self.db.base_attack = 55
        self.db.room_pose = "crouched here, spores puffing from its back."

    def get_moves(self):
        return {
            "bite": {
                "weight": 45,
                "type": "instant",
                "damage": 18,
                "weapon_key": "bite",
                "msg": "|y{name} darts in and sinks its teeth into {target}!|n",
            },
            "spore_burst": {
                "weight": 35,
                "type": "instant",
                "damage": 12,
                "weapon_key": "fists",
                "msg": "|y{name} releases a cloud of choking spores at {target}!|n",
            },
            "lunge": {
                "weight": 20,
                "type": "telegraph",
                "ticks": 1,
                "telegraph_msg": "|y{name} coils back, legs tensing!|n",
                "execute_msg": "|r{name} launches itself at {target} in a full-body lunge!|n",
                "damage": 55,
                "weapon_key": "bite",
            },
        }


class RustStalker(Creature):
    """Mechanical predator with a telegraphed saw-blade and quick slashes."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.key = "Rust Stalker"
        self.db.max_hp = 280
        self.db.current_hp = 280
        self.db.armor_rating = 25
        self.db.base_attack = 70
        self.db.room_pose = "hunched here, blades clicking."

    def get_moves(self):
        return {
            "slash": {
                "weight": 50,
                "type": "instant",
                "damage": 22,
                "weapon_key": "claws",
                "msg": "|c{name}'s blade arm whirs and slashes at {target}!|n",
            },
            "saw_charge": {
                "weight": 25,
                "type": "telegraph",
                "ticks": 2,
                "telegraph_msg": "|c{name}'s saw-blade spins up with a piercing whine!|n",
                "execute_msg": "|R{name} drives its spinning saw into {target}!|n",
                "msg_miss": "|y{target} dives aside — {name}'s saw tears through empty air!|n",
                "damage": 95,
                "weapon_key": "saw",
                "stamina_drain": 25,
            },
            "gouge": {
                "weight": 25,
                "type": "instant",
                "damage": 38,
                "weapon_key": "gouge",
                "msg": "|r{name} rams its claw into {target}!|n",
            },
        }
