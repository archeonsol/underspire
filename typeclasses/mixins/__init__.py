"""
Character mixins: thematic pieces split off from the main Character class.
Import from here or from the specific module.
"""
from typeclasses.mixins.furniture_mixin import FurnitureMixin
from typeclasses.mixins.medical_mixin import MedicalMixin
from typeclasses.mixins.rpg_character_mixin import RPGCharacterMixin
from typeclasses.mixins.roleplay_mixin import RoleplayMixin

__all__ = ["FurnitureMixin", "MedicalMixin", "RPGCharacterMixin", "RoleplayMixin"]
