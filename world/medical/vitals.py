"""
HT/vitals summary split from world.medical.__init__.
"""

HT_CONDITION_FULL_HP_TIERS = [
    (115, "excellent"),
    (130, "spectacular"),
    (152, "magnificent"),
    (9999, "miraculous"),
]
HT_CONDITION_INJURED_TIERS = [
    (95, "lightly injured"),
    (85, "injured"),
    (70, "fairly injured"),
    (50, "badly injured"),
    (35, "severely injured"),
    (20, "critically injured"),
    (10, "mortally injured and struggling to remain conscious"),
    (0, "on the verge of collapse"),
]
HT_CONDITION_DEAD = "beyond help"
HT_RESTED_TIERS = [
    (90, "very well rested"),
    (70, "well rested"),
    (50, "moderately rested"),
    (25, "tired"),
    (0, "exhausted"),
]


def get_ht_summary(character, first_person=True):
    from world.rpg.emote import PRONOUN_MAP
    from world.death import is_flatlined, is_permanently_dead
    mx_hp = getattr(character, "max_hp", 100) or 100
    cur_hp = character.db.current_hp
    if cur_hp is None:
        character.db.current_hp = mx_hp
        cur_hp = mx_hp
    percent_hp = (cur_hp / mx_hp) * 100 if mx_hp > 0 else 0
    if cur_hp <= 0:
        try:
            if is_permanently_dead(character):
                condition = HT_CONDITION_DEAD
            elif is_flatlined(character):
                condition = HT_CONDITION_INJURED_TIERS[7][1]
            else:
                condition = HT_CONDITION_DEAD
        except Exception:
            condition = HT_CONDITION_DEAD
    elif percent_hp >= 100:
        condition = "miraculous"
        for threshold, label in HT_CONDITION_FULL_HP_TIERS:
            if mx_hp < threshold:
                condition = label
                break
    else:
        condition = HT_CONDITION_INJURED_TIERS[0][1]
        for min_pct, label in HT_CONDITION_INJURED_TIERS:
            if percent_hp >= min_pct:
                condition = label
                break

    mx_stam = getattr(character, "max_stamina", 100) or 100
    cur_stam = character.db.current_stamina
    if cur_stam is None and hasattr(character, "max_stamina"):
        character.db.current_stamina = character.max_stamina
        cur_stam = character.db.current_stamina or mx_stam
    percent_stam = (cur_stam / mx_stam) * 100 if mx_stam > 0 else 0
    rested = "exhausted"
    for min_pct, label in HT_RESTED_TIERS:
        if percent_stam >= min_pct:
            rested = label
            break
    if not first_person:
        key = (getattr(character.db, "pronoun", None) or "neutral").lower()
        sub, _, _ = PRONOUN_MAP.get(key, PRONOUN_MAP["neutral"])
        sub_cap = (sub or "they").capitalize()
        verb = "is" if (sub or "they").lower() in ("he", "she") else "are"
        return f"{sub_cap} {verb} in {condition} condition."
    try:
        from world.rpg.stamina import get_stamina_recovery_label
        recovering = get_stamina_recovery_label(character)
    except Exception:
        recovering = "recovering moderately"
    return f"You are in {condition} condition, are physically {rested} and {recovering}."
