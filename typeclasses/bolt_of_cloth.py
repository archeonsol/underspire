"""
Bolt of cloth (or silk, satin, velvet): customizable draft that tailors turn into clothing.
Material type gates required tailoring skill; finalize rolls tailoring for success and quality.
"""
from typeclasses.items import Item


class BoltOfCloth(Item):
    """
    A bolt of material (cloth, silk, satin, velvet). Customize with the tailor command,
    then finalize to produce a Clothing item. db.material_type sets required tailoring skill.
    """
    def at_object_creation(self):
        super().at_object_creation()
        if getattr(self.db, "material_type", None) is None:
            self.db.material_type = "cloth"
        self.db.draft_name = "unfinished garment"
        self.db.draft_aliases = []
        self.db.draft_desc = ""
        self.db.draft_worn_desc = ""
        self.db.draft_tease = ""
        self.db.draft_covered_parts = []

    def is_draft(self):
        return True

    def get_material_display_name(self):
        """Display name for this bolt's material (e.g. 'bolt of silk')."""
        from world.rpg.tailoring import get_material_info
        return get_material_info(self).get("name", "bolt of cloth")

    def get_draft_status(self):
        """Return a short summary of current draft settings for tailor command."""
        from world.rpg.tailoring import get_material_info
        name = getattr(self.db, "draft_name", None) or "unfinished garment"
        aliases = getattr(self.db, "draft_aliases", None) or []
        desc = getattr(self.db, "draft_desc", None) or ""
        worn_desc = getattr(self.db, "draft_worn_desc", None) or ""
        tease = getattr(self.db, "draft_tease", None) or ""
        parts = getattr(self.db, "draft_covered_parts", None) or []
        mat = get_material_info(self)
        return {
            "name": name,
            "aliases": aliases,
            "desc": desc,
            "worn_desc": worn_desc,
            "tease": tease,
            "covered_parts": parts,
            "material": mat.get("name", "bolt of cloth"),
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
        elif a == "tail":
            valid.append("tail")
        elif a in BODY_PART_ALIASES:
            valid.append(BODY_PART_ALIASES[a])
        else:
            invalid.append(a)
    return valid, invalid
