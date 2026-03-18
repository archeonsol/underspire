"""
Tailoring system: bolt materials, skill-gated finalization, and clothing quality.

Bolt materials (cloth, silk, satin, velvet) require increasing tailoring skill.
On finalize, a tailoring roll determines success and the garment's quality adjective
(tacky, cheap, shoddy, makeshift, austere, basic, fashionable, trendy, fancy).
Quality is stored on the clothing and shown when looking at a character:
"Their outfit is fancy." (averaged over all worn items).
"""
from world.skills import SKILL_STATS
from world.clothing import infer_clothing_layer

# Bolt material types: key = material_type on bolt, display name, min skill, roll difficulty, quality_bonus (added to roll for adjective)
BOLT_MATERIALS = {
    "cloth": {"name": "bolt of cloth", "min_skill": 0, "difficulty": 0, "quality_bonus": 0},
    "silk": {"name": "bolt of silk", "min_skill": 25, "difficulty": 5, "quality_bonus": 8},
    "satin": {"name": "bolt of satin", "min_skill": 50, "difficulty": 10, "quality_bonus": 15},
    "velvet": {"name": "bolt of velvet", "min_skill": 75, "difficulty": 15, "quality_bonus": 22},
}

# Quality tiers by final roll result (min_result, adjective); higher = more fashionable
# quality_score 0-100 is stored on clothing for averaging outfit quality
QUALITY_TIERS = [
    (0, "ragged", 0),
    (10, "tattered", 10),
    (20, "shoddy", 20),
    (30, "cheap", 30),
    (40, "plain", 40),
    (50, "decent", 50),
    (60, "well-made", 60),
    (70, "stylish", 70),
    (80, "fashionable", 80),
    (90, "designer", 90),
    (100, "luxurious", 100),
]

TAILORING_SKILL = "tailoring"


def get_material_info(bolt):
    """Return BOLT_MATERIALS entry for this bolt's material_type; default cloth."""
    mat = getattr(bolt.db, "material_type", None) or "cloth"
    return BOLT_MATERIALS.get(mat, BOLT_MATERIALS["cloth"])


def get_quality_for_result(result):
    """
    Map a tailoring roll result (int) to (adjective, quality_score 0-100).
    quality_score is used to average outfit quality when displaying "Their outfit is X."
    """
    result = max(0, min(100, int(result)))
    adjective = "basic"
    score = 70
    for min_result, adj, qscore in reversed(QUALITY_TIERS):
        if result >= min_result:
            adjective = adj
            score = qscore
            break
    return adjective, score


def roll_tailoring(caller, difficulty=0):
    """
    Perform a tailoring skill roll. Uses intelligence + charisma per SKILL_STATS.
    Returns (success: bool, result: int, adjective: str, quality_score: int).
    """
    if not hasattr(caller, "roll_check"):
        return False, 0, "shoddy", 25
    stats = SKILL_STATS.get(TAILORING_SKILL, ["intelligence", "charisma"])
    outcome, result = caller.roll_check(stats, TAILORING_SKILL, difficulty=difficulty, modifier=-difficulty)
    # result is the final_result from roll_check (effective_roll + strength_bonus + modifier - difficulty)
    adjective, quality_score = get_quality_for_result(result)
    success = outcome in ("Critical Success", "Full Success", "Marginal Success")
    return success, result, adjective, quality_score


def finalize_bolt_to_clothing(bolt, caller):
    """
    Check material skill gate, roll tailoring, then convert bolt to Clothing and set quality.
    Returns (clothing_or_None, message_str).
    """
    from typeclasses.clothing import Clothing

    material = get_material_info(bolt)
    min_skill = material["min_skill"]
    difficulty = material["difficulty"]
    skill_level = getattr(caller, "get_skill_level", lambda s: 0)(TAILORING_SKILL)

    if skill_level < min_skill:
        return None, "You lack the skill to work with this material."

    success, result, _, _ = roll_tailoring(caller, difficulty)

    if not success:
        return None, (
            "You work the material but the result falls apart or looks too bad to wear. "
            "You need more practice with tailoring (or an easier material)."
        )

    # Better materials add a bonus to the roll result for quality (same roll, better adjective bias)
    quality_bonus = material.get("quality_bonus", 0)
    adjective, quality_score = get_quality_for_result(result + quality_bonus)

    name = (getattr(bolt.db, "draft_name", None) or "").strip() or "garment"
    if not getattr(bolt.db, "draft_covered_parts", None):
        return None, "Set coverage before finalizing (e.g. tailor [bolt] coverage torso lshoulder rshoulder)."

    try:
        bolt.swap_typeclass("typeclasses.clothing.Clothing")
    except Exception as e:
        return None, "Could not finalize: %s" % e

    bolt.key = name
    bolt.aliases.clear()
    for a in (getattr(bolt.db, "draft_aliases", None) or []):
        bolt.aliases.add(a)
    bolt.db.desc = getattr(bolt.db, "draft_desc", None) or ""
    bolt.db.worn_desc = getattr(bolt.db, "draft_worn_desc", None) or ""
    bolt.db.tease_message = getattr(bolt.db, "draft_tease", None) or ""
    bolt.db.covered_parts = list(getattr(bolt.db, "draft_covered_parts", None) or [])
    # Set clothing_layer based on name keywords (bra, jacket, coat, boots, etc.)
    bolt.db.clothing_layer = infer_clothing_layer(name)
    # See-through garments (jewelry, mesh, etc.) let underlying body/clothing show through.
    bolt.db.see_thru = bool(getattr(bolt.db, "draft_see_thru", False))
    bolt.db.quality_adjective = adjective
    bolt.db.quality_score = quality_score

    # Optional two-state configuration for stateful garments (zips, hoods, etc.)
    draft_state_a = getattr(bolt.db, "draft_state_a", None)
    draft_state_b = getattr(bolt.db, "draft_state_b", None)

    # If only an alternate (B) draft exists, derive primary (A) from the main draft
    # fields so that state A = "normal" and state B = "alternate".
    if draft_state_b and not draft_state_a:
        base_cfg = {}
        if getattr(bolt.db, "draft_covered_parts", None):
            base_cfg["covered_parts"] = list(getattr(bolt.db, "draft_covered_parts") or [])
        if getattr(bolt.db, "draft_worn_desc", None):
            base_cfg["worn_desc"] = getattr(bolt.db, "draft_worn_desc") or ""
        if hasattr(bolt.db, "draft_see_thru"):
            base_cfg["see_thru"] = bool(getattr(bolt.db, "draft_see_thru", False))
        draft_state_a = base_cfg or None

    if draft_state_a and draft_state_b:
        try:
            # Store on finished clothing; Clothing helpers know how to use these.
            bolt.db.state_a = dict(draft_state_a)
            bolt.db.state_b = dict(draft_state_b)
            # Default initial state is "a".
            bolt.db.state = "a"
        except Exception:
            # If anything goes wrong, fail silently; garment remains non-stateful.
            pass

    for k in (
        "draft_name",
        "draft_aliases",
        "draft_desc",
        "draft_worn_desc",
        "draft_tease",
        "draft_covered_parts",
        "draft_see_thru",
        "draft_state_a",
        "draft_state_b",
        "material_type",
    ):
        if bolt.attributes.has(k):
            bolt.attributes.remove(k)

    return bolt, "You finalize the bolt into: %s (quality: %s)." % (bolt.get_display_name(caller), adjective)


def get_outfit_quality_line(character, looker=None):
    """
    Return a line like "Their outfit is fancy." based on averaged quality of worn clothing.
    If looker is the same as character, could say "Your outfit is fancy." — here we keep
    third person: when you look at someone you see "Their outfit is X."
    Uses character's possessive pronoun (their/his/her).
    """
    from world.clothing import get_worn_items
    from world.medical import _pronoun_sub_poss

    worn = get_worn_items(character)
    if not worn:
        return ""

    scores = []
    for item in worn:
        s = getattr(item.db, "quality_score", None)
        if s is not None:
            scores.append(int(s))

    if not scores:
        return ""

    avg = sum(scores) / len(scores)
    adjective = "basic"
    for _min, adj, qscore in reversed(QUALITY_TIERS):
        if avg >= qscore:
            adjective = adj
            break

    _, poss = _pronoun_sub_poss(character)
    poss_cap = (poss or "their").capitalize()
    return "%s outfit is %s." % (poss_cap, adjective)


# Parse args for tailor command (migrated from command.py for one place to edit)
TAILOR_SUBCMDS = [
    "name",
    "aliases",
    "worn",
    "worndesc",
    "desc",
    "tease",
    "coverage",
    "seethru",
    "see-thru",
    "statea",
    "stateb",
    "altstate",
    "finalize",
]


def tailor_parse_args(args):
    """Return (bolt_spec, subcmd, value) or (None, None, None) if no subcmd found."""
    if not args or not args.strip():
        return None, None, None
    args = args.strip()
    best_pos = len(args)
    found_sub = None
    for sub in TAILOR_SUBCMDS:
        pos = args.find(sub)
        if pos == 0 or (pos > 0 and args[pos - 1].isspace()):
            if pos < best_pos:
                best_pos = pos
                found_sub = sub
    if found_sub is None:
        return args.strip(), None, None
    bolt_spec = args[:best_pos].strip()
    rest = args[best_pos + len(found_sub) :].strip()
    return bolt_spec, found_sub, rest
