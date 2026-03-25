"""
Medical character mixin: HP/stamina, damage application, flatline, and health description.
Depends on RPGCharacterMixin for get_display_stat (used by max_hp / max_stamina).
"""
from evennia.utils import logger


class MedicalMixin:
    """HP, stamina, at_damage, get_medical_summary, get_health_description."""

    # Miraculous benchmark: 114 display Endurance + 123 display Strength = 152 HP
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
        if self.db.current_hp > self.max_hp:
            self.db.current_hp = self.max_hp
        return self.db.current_hp

    @property
    def max_stamina(self):
        """Stamina pool tied to endurance display level.

        The cyberware scan is cached on ndb._max_stamina_cardio (bool) so repeated
        calls within the same server session don't re-deserialise the cyberware list.
        The cache is invalidated by install_cyberware / remove_cyberware via
        ndb._max_stamina_cardio = None.
        """
        end_display = self.get_display_stat("endurance")
        base = 20 + (end_display * 5)
        # Use cached result if available; None means "not yet computed".
        has_cardio = getattr(self.ndb, "_max_stamina_cardio", None)
        if has_cardio is None:
            cyber = list(getattr(self.db, "cyberware", None) or [])
            has_cardio = any(
                type(cw).__name__ == "CardioPulmonaryBooster"
                and not bool(getattr(cw.db, "malfunctioning", False))
                for cw in cyber
            )
            self.ndb._max_stamina_cardio = has_cardio
        if has_cardio:
            base += 15
        return base

    @property
    def stamina(self):
        if self.db.current_stamina is None:
            self.db.current_stamina = self.max_stamina
        if self.db.current_stamina > self.max_stamina:
            self.db.current_stamina = self.max_stamina
        return self.db.current_stamina

    def at_damage(self, attacker, damage, body_part=None, weapon_key=None, weapon_obj=None):
        """Apply HP loss. At 0 HP enter flatlined state (dying). Records injury for natural regen."""
        try:
            dmg = int(damage or 0)
        except Exception:
            dmg = 0
        if dmg > 0:
            try:
                from world.rpg import stealth

                if stealth.is_hidden(self):
                    stealth.reveal(self, reason="damage")
            except Exception:
                pass
            try:
                from world.vehicle_mounts import check_motorcycle_dismount_on_damage

                check_motorcycle_dismount_on_damage(self, dmg)
            except Exception:
                pass
            try:
                from world.combat.mounted_combat import biker_hit_splash

                biker_hit_splash(self, dmg, weapon_key)
            except Exception:
                pass
            try:
                from world.rpg.staggered_movement import interrupt_staggered_walk

                interrupt_staggered_walk(
                    self,
                    notify_msg="|yThe hit breaks your stride.|n"
                    if attacker
                    else "|yYou stop moving.|n",
                )
            except Exception:
                pass
            # Apply HP loss using the sanitised integer value.
            self.db.current_hp = (self.db.current_hp or self.max_hp) - dmg
            if self.db.current_hp < 0:
                self.db.current_hp = 0

            # Drug sustain: keep character conscious at 1 HP even when they should flatline.
            # Check before add_injury so injury severity is recorded at the correct HP.
            if self.db.current_hp <= 0 and getattr(self.db, "drug_consciousness_sustain", False):
                self.db.current_hp = 1
                self.msg("|rYou should be unconscious. Why aren't you?|n")
                return

            try:
                from world.medical import add_injury
                add_injury(self, dmg, body_part=body_part, weapon_key=weapon_key or "fists", weapon_obj=weapon_obj)
            except Exception as err:
                logger.log_trace("medical_mixin.at_damage add_injury: %s" % err)

            if self.db.current_hp <= 0:
                try:
                    from world.death import make_flatlined, is_flatlined
                    if not is_flatlined(self):
                        make_flatlined(self, attacker)
                except Exception as err:
                    logger.log_trace("medical_mixin.at_damage make_flatlined: %s" % err)
                    self.db.combat_ended = True
                    self.msg("|rYour legs give. The ground comes up. You are done.|n")
                    if attacker and attacker != self:
                        attacker.msg(f"|y{self.get_display_name(attacker)} goes down and does not get up.|n")
                    try:
                        from world.combat import remove_both_combat_tickers
                        remove_both_combat_tickers(self, attacker)
                    except Exception as combat_err:
                        logger.log_trace("medical_mixin.at_damage remove_both_combat_tickers: %s" % combat_err)

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
        # Read current_hp directly to avoid the property's DB-write side effect in a display path.
        current_hp = self.db.current_hp
        if current_hp is None:
            current_hp = self.max_hp
        percent = (current_hp / self.max_hp) * 100 if self.max_hp > 0 else 0

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
            except Exception as err:
                logger.log_trace("medical_mixin.get_health_description is_flatlined: %s" % err)
                desc = "|RDead.|n A heap of broken meat and shattered bone. The spark of life has long since flickered out."

        if include_trauma:
            medical = self.get_medical_summary()
            if medical and "No significant trauma" not in medical:
                desc = desc + "\n\n" + medical
        return desc
