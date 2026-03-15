# D:\ColonyGame\mootest\typeclasses\npc.py
from typeclasses.characters import Character
import random

class NPC(Character):
    def at_object_creation(self):
        super().at_object_creation()
        # Stats 0-300, skills 0-150: random low-mid range
        for stat in self.db.stats:
            self.db.stats[stat] = random.randint(30, 140)
        for skill in self.db.skills:
            self.db.skills[skill] = random.randint(15, 70)
        self.db.needs_chargen = False 
        self.db.combat_stance = "balanced"
        
        # Wake up the vitals
        _ = self.hp
        _ = self.stamina

    def at_damage(self, attacker, damage, **kwargs):
        """NPC takes damage; update stance. Combat round ticker already gives us an attack each round."""
        super().at_damage(attacker, damage, **kwargs)
        
        if self.db.current_hp > 0:
            if self.db.current_hp < (self.max_hp * 0.3):
                self.db.combat_stance = "defensive"
            else:
                self.db.combat_stance = "aggressive"