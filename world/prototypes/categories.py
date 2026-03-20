"""
Names for |wspawnitem list <category> [subtag]|n — must match |wprototype_tags|n on dicts.

Single word: prototypes must include that tag. Two words: must include both tags.
"""

# Shown after a full |wspawnitem list|n
LIST_CATEGORY_HELP = (
    "|wCategories|n (use |wspawnitem list <category>|n or |wspawnitem list <cat> <subtag>|n): "
    "|wcombat|n, |wweapon|n, |warmor|n, |wsurvival|n, |wfood|n, |wdrink|n, |walcohol|n, "
    "|wmedical|n, |wtailoring|n, |wperformance|n, |wconsumable|n"
)

# Valid filter tokens (lowercase). Used only for friendlier errors; unknown tags still filter to empty.
KNOWN_LIST_TAGS = frozenset(
    {
        "combat",
        "weapon",
        "armor",
        "survival",
        "food",
        "drink",
        "alcohol",
        "medical",
        "tailoring",
        "performance",
        "consumable",
    }
)
