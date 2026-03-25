# D:\ColonyGame\mootest\typeclasses\npc.py
from typeclasses.characters import Character
import random

class NPC(Character):
    """Staff-created character. Same stats/skills as PC but does not show as sleeping when unpuppeted."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.is_npc = True
        # Stats 0-300, skills 0-150: random low-mid range.
        # Build both dicts in one pass each, then write once and sync traits together.
        _stats = {stat: random.randint(30, 140) for stat in (self.db.stats or {})}
        _skills = {skill: random.randint(15, 70) for skill in (self.db.skills or {})}
        self.db.stats = _stats
        self.db.skills = _skills

        from world.rpg.trait_sync import sync_stats_to_traits, sync_skills_to_traits
        sync_stats_to_traits(self, _stats)
        sync_skills_to_traits(self, _skills)
        self.db.needs_chargen = False 
        self.db.combat_stance = "balanced"
        
        # Initialise current_hp / current_stamina in DB via the property side-effect.
        _ = self.hp
        _ = self.stamina

    def at_damage(self, attacker, damage, **kwargs):
        """NPC takes damage; update stance. Combat round ticker already gives us an attack each round."""
        super().at_damage(attacker, damage, **kwargs)

        current = self.db.current_hp or 0
        if current <= 0:
            return
        max_hp = self.max_hp or 1
        if current < (max_hp * 0.3):
            self.db.combat_stance = "defensive"
        else:
            self.db.combat_stance = "aggressive"