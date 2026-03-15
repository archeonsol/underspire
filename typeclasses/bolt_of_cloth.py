"""
Bolt of cloth: customizable draft that tailors can turn into clothing.
Set name, aliases, desc (with $N/$P/$S tokens), tease message, and coverage, then finalize.
"""
from typeclasses.items import Item


class BoltOfCloth(Item):
    """
    A bolt of cloth. Customize with the tailor command, then finalize to produce
    a Clothing item.     Draft attributes: draft_name, draft_aliases, draft_desc, draft_worn_desc,
    draft_tease, draft_covered_parts.
    """
    def at_object_creation(self):
        super().at_object_creation()
        self.db.draft_name = "unfinished garment"
        self.db.draft_aliases = []
        self.db.draft_desc = ""
        self.db.draft_worn_desc = ""
        self.db.draft_tease = ""
        self.db.draft_covered_parts = []

    def is_draft(self):
        return True

    def get_draft_status(self):
        """Return a short summary of current draft settings for tailor command."""
        name = getattr(self.db, "draft_name", None) or "unfinished garment"
        aliases = getattr(self.db, "draft_aliases", None) or []
        desc = getattr(self.db, "draft_desc", None) or ""
        worn_desc = getattr(self.db, "draft_worn_desc", None) or ""
        tease = getattr(self.db, "draft_tease", None) or ""
        parts = getattr(self.db, "draft_covered_parts", None) or []
        return {
            "name": name,
            "aliases": aliases,
            "desc": desc,
            "worn_desc": worn_desc,
            "tease": tease,
            "covered_parts": parts,
        }


def resolve_coverage_args(args_list):
    """
    Convert a list of short or full body part names to canonical BODY_PARTS keys.
    Returns (list of canonical names, list of invalid strings).
    """
    from world.medical import BODY_PARTS, BODY_PART_ALIASES
    valid = []
    invalid = []
    for a in args_list:
        a = a.strip().lower()
        if a in BODY_PARTS:
            valid.append(a)
        elif a in BODY_PART_ALIASES:
            valid.append(BODY_PART_ALIASES[a])
        else:
            invalid.append(a)
    return valid, invalid
