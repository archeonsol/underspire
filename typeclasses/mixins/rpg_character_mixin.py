"""
RPG character mixin: stats, skills, grades, and the roll-check (dice) system.
"""
import random


class RPGCharacterMixin:
    """Stats 0-300, skills 0-150; letter tiers; roll_check (the simulation engine)."""

    def get_grade_adjective(self, grade_letter):
        """Legacy: use get_stat_grade_adjective or get_skill_grade_adjective. Falls back to skill adjective."""
        from world.grades import get_skill_grade_adjective
        return get_skill_grade_adjective(grade_letter)

    def get_stat_level(self, stat_key):
        """Return stored stat level 0-300 (used for XP spending and letter lookup)."""
        from world.rpg.xp import _stat_level
        return _stat_level(self, stat_key)

    def get_display_stat(self, stat_name):
        """
        Return effective display level 0-150 for a stat.

        Base: stored_level // 2 from world.rpg.xp (0-300 -> 0-150).
        Buffs: routed through Evennia's BuffHandler (obj.buffs) using a
        '<stat>_display' identifier, e.g. 'charisma_display'.

        Note: buffs.check() can push the result above 150. This is
        intentional — cyberware and other buffs are allowed to exceed
        the natural cap.
        """
        from world.rpg.xp import _stat_level

        stored = int(_stat_level(self, stat_name) or 0)
        base_display = min(max(stored // 2, 0), 150)
        if hasattr(self, "buffs"):
            try:
                return int(self.buffs.check(base_display, f"{stat_name}_display"))
            except Exception:
                return base_display
        return base_display

    def get_skill_level(self, skill_key):
        """
        Return effective skill level as int 0-150 (normalizes legacy letters and
        applies buffs via BuffHandler using 'skill:<key>' identifiers).
        """
        from world.rpg.xp import _skill_level

        base = int(_skill_level(self, skill_key) or 0)
        if hasattr(self, "buffs"):
            try:
                return int(self.buffs.check(base, f"skill:{skill_key}"))
            except Exception:
                return base
        return base

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
        from world.rpg.xp import _stat_cap_level
        return _stat_cap_level(self, stat_key)

    def get_skill_cap(self, skill_key):
        """Return cap level for this skill (int 0-150)."""
        from world.rpg.xp import _skill_cap_level
        return _skill_cap_level(self, skill_key)

    def roll_check(self, stat_list, skill_name, difficulty=0, modifier=0):
        """
        Core contested-roll system used for combat and skills.

        - Skill sets the roll ceiling: random(0, skill_level).
        - Relevant stats provide the flat strength term (sum of display stats).
        - Final result is compared directly in opposed checks (attack vs parry/evasion).

        final_result = random(0, skill_level) + sum(relevant_stats) + modifier - difficulty
        """
        if isinstance(stat_list, str):
            stat_list = [stat_list]

        # 1. STAT STRENGTH: sum of relevant display stats
        total_display = sum(self.get_display_stat(s) for s in stat_list)
        stat_strength = int(total_display)

        # 2. SKILL CEILING: 0–skill_level
        from world.levels import MAX_LEVEL

        raw_skill_level = self.get_skill_level(skill_name)
        skill_level = max(0, min(int(raw_skill_level or 0), MAX_LEVEL))

        if skill_level <= 0:
            roll = 0
        else:
            # random(0, skill)
            roll = random.randint(0, skill_level)

        # 3. FINAL RESULT
        final_result = roll + stat_strength + modifier - difficulty

        # 4. SUCCESS TIER: based on how well you rolled relative to your skill ceiling
        if skill_level <= 0:
            return "Failure", final_result

        ratio = roll / float(skill_level) if skill_level > 0 else 0.0
        if ratio >= 0.9:
            return "Critical Success", final_result
        if ratio >= 0.6:
            return "Full Success", final_result
        if ratio >= 0.35:
            return "Marginal Success", final_result
        return "Failure", final_result
