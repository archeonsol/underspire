"""
Helpers for keeping the Evennia TraitHandler mirrors in sync with legacy db dicts.

These are called at every write site (chargen, cloning, npc_templates, staff commands,
player XP confirm) so that trait_stats / trait_skills always reflect the current values.

Usage:
    from world.rpg.trait_sync import sync_stats_to_traits, sync_skills_to_traits

    sync_stats_to_traits(character, stats_dict, caps_dict=None)
    sync_skills_to_traits(character, skills_dict)
"""


def sync_stats_to_traits(character, stats_dict, caps_dict=None):
    """
    Write a stats dict to character.trait_stats TraitHandler.

    Args:
        character: the Character (or NPC) instance.
        stats_dict (dict): {stat_key: int_value 0-300}.
        caps_dict (dict|None): {stat_key: int_value 0-300} for stat caps.
            If None, caps are left unchanged.
    """
    handler = getattr(character, "trait_stats", None)
    if handler is None:
        return
    for key, val in stats_dict.items():
        trait = handler.get(key)
        if trait is not None:
            trait.base = int(val or 0)
        else:
            # Trait missing (e.g. NPC created before migration) — add it on the fly.
            from world.levels import MAX_STAT_LEVEL
            handler.add(key, key.title(), trait_type="static", base=int(val or 0))
    if caps_dict:
        for key, val in caps_dict.items():
            cap_key = f"cap_{key}"
            trait = handler.get(cap_key)
            if trait is not None:
                trait.base = int(val or 0)
            else:
                from world.levels import MAX_STAT_LEVEL
                handler.add(cap_key, f"{key.title()} Cap", trait_type="static", base=int(val or 0))


def sync_skills_to_traits(character, skills_dict):
    """
    Write a skills dict to character.trait_skills TraitHandler.

    Args:
        character: the Character (or NPC) instance.
        skills_dict (dict): {skill_key: int_value 0-150}.
    """
    handler = getattr(character, "trait_skills", None)
    if handler is None:
        return
    for key, val in skills_dict.items():
        # Backward-compat: renamed skill key
        if key == "tailoring":
            key = "artistry"
        trait = handler.get(key)
        if trait is not None:
            trait.base = int(val or 0)
        else:
            # Trait missing — add it on the fly.
            from world.levels import MAX_LEVEL
            handler.add(key, key.replace("_", " ").title(), trait_type="static", base=int(val or 0))


def sync_single_stat(character, stat_key, value):
    """
    Sync a single stat value to the trait handler.
    Convenience wrapper for XP confirm (which updates one key at a time).
    """
    handler = getattr(character, "trait_stats", None)
    if handler is None:
        return
    trait = handler.get(stat_key)
    if trait is not None:
        trait.base = int(value or 0)
    else:
        from world.levels import MAX_STAT_LEVEL
        handler.add(stat_key, stat_key.title(), trait_type="static", base=int(value or 0))


def sync_single_skill(character, skill_key, value):
    """
    Sync a single skill value to the trait handler.
    Convenience wrapper for XP confirm (which updates one key at a time).
    """
    handler = getattr(character, "trait_skills", None)
    if handler is None:
        return
    if skill_key == "tailoring":
        skill_key = "artistry"
    trait = handler.get(skill_key)
    if trait is not None:
        trait.base = int(value or 0)
    else:
        from world.levels import MAX_LEVEL
        handler.add(skill_key, skill_key.replace("_", " ").title(), trait_type="static", base=int(value or 0))
