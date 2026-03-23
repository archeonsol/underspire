"""
NPC templates for @npc/summon. Stats 0-300, skills 0-150.
Role templates use letter-grade ranges (e.g. high = stats D-A, skills C-A) and randomize within those.
'random' template: fully random stats/skills within cap (300/150).
"""
import random
from world.skills import SKILL_KEYS
from world.levels import MAX_STAT_LEVEL, MAX_LEVEL, letter_to_level_range

STAT_KEYS = ["strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"]

# Letter-range tiers for randomized role templates: (stat_lo, stat_hi, skill_lo, skill_hi) for specialists;
# base (non-specialist) uses (base_stat_lo, base_stat_hi, base_skill_lo, base_skill_hi).
# low = upper-mid range; med = high-mid; high = upper end (D-A stats, C-A skills).
TIER_LOW_SPEC = ("M", "F", "N", "G")   # specialist stats M-F, specialist skills N-G
TIER_LOW_BASE = ("Q", "L", "Q", "M")   # base stats Q-L, base skills Q-M
TIER_MED_SPEC = ("G", "D", "H", "C")   # specialist G-D, skills H-C
TIER_MED_BASE = ("L", "G", "M", "H")   # base L-G, skills M-H
TIER_HIGH_SPEC = ("D", "A", "C", "A")  # specialist stats D-A, skills C-A
TIER_HIGH_BASE = ("G", "D", "H", "C")  # base stats G-D, skills H-C


def _letter_range_to_min_max(lo_letter, hi_letter, max_level):
    """Return (min_level, max_level) for a letter range. lo_letter and hi_letter are e.g. 'D' and 'A'."""
    lo_letter = (lo_letter or "U").strip().upper()
    hi_letter = (hi_letter or "A").strip().upper()
    lo_min, _ = letter_to_level_range(lo_letter, max_level)
    _, hi_max = letter_to_level_range(hi_letter, max_level)
    return lo_min, hi_max


def _random_in_letter_range(lo_letter, hi_letter, max_level):
    """Return a random level in the given letter range (inclusive). max_level is 300 for stats, 150 for skills."""
    lo, hi = _letter_range_to_min_max(lo_letter, hi_letter, max_level)
    return random.randint(lo, hi) if lo <= hi else lo


# Combat: unarmed, short_blades, long_blades, blunt_weaponry, sidearms, longarms, automatics, evasion, gunnery, stealth
COMBAT_SKILLS = ["unarmed", "short_blades", "long_blades", "blunt_weaponry", "sidearms", "longarms", "automatics", "evasion", "gunnery", "stealth"]
COMBAT_STATS = ["strength", "agility", "perception", "endurance"]

# Mechanic: mechanical_engineering, arms_tech, electrical_engineering
MECHANIC_SKILLS = ["mechanical_engineering", "arms_tech", "electrical_engineering"]
MECHANIC_STATS = ["intelligence", "perception", "strength"]

# Doctor: medicine, cyber_surgery
DOCTOR_SKILLS = ["medicine", "cyber_surgery"]
DOCTOR_STATS = ["intelligence", "perception", "agility"]

# Techie: cyberdecking, systems_security, electrical_engineering
TECHIE_SKILLS = ["cyberdecking", "systems_security", "electrical_engineering"]
TECHIE_STATS = ["intelligence", "agility", "perception"]


def _build_template_randomized(role_name, specialist_skills, specialist_stats,
                                spec_stat_lo, spec_stat_hi, spec_skill_lo, spec_skill_hi,
                                base_stat_lo, base_stat_hi, base_skill_lo, base_skill_hi):
    """Build a template with stats/skills randomized within the given letter ranges. Specialist keys get spec range; rest get base range."""
    stats = {}
    skills = {}
    for st in STAT_KEYS:
        if st in specialist_stats:
            stats[st] = _random_in_letter_range(spec_stat_lo, spec_stat_hi, MAX_STAT_LEVEL)
        else:
            stats[st] = _random_in_letter_range(base_stat_lo, base_stat_hi, MAX_STAT_LEVEL)
    for sk in SKILL_KEYS:
        if sk in specialist_skills:
            skills[sk] = _random_in_letter_range(spec_skill_lo, spec_skill_hi, MAX_LEVEL)
        else:
            skills[sk] = _random_in_letter_range(base_skill_lo, base_skill_hi, MAX_LEVEL)
    return {
        "name": role_name,
        "stats": stats,
        "skills": skills,
    }


def _build_random_template():
    """Build a template with completely random stats (0-300) and skills (0-150) within max cap."""
    return {
        "name": "Random",
        "stats": {st: random.randint(0, MAX_STAT_LEVEL) for st in STAT_KEYS},
        "skills": {sk: random.randint(0, MAX_LEVEL) for sk in SKILL_KEYS},
    }


# Template key -> template dict (name, stats, skills). Role templates are built at call time so each summon gets new random values.
def _make_combat_low():
    return _build_template_randomized("Combatant (low)", COMBAT_SKILLS, COMBAT_STATS,
        *TIER_LOW_SPEC, *TIER_LOW_BASE)


def _make_combat_med():
    return _build_template_randomized("Combatant (med)", COMBAT_SKILLS, COMBAT_STATS,
        *TIER_MED_SPEC, *TIER_MED_BASE)


def _make_combat_high():
    return _build_template_randomized("Combatant (high)", COMBAT_SKILLS, COMBAT_STATS,
        *TIER_HIGH_SPEC, *TIER_HIGH_BASE)


def _make_mechanic_low():
    return _build_template_randomized("Mechanic (low)", MECHANIC_SKILLS, MECHANIC_STATS,
        *TIER_LOW_SPEC, *TIER_LOW_BASE)


def _make_mechanic_med():
    return _build_template_randomized("Mechanic (med)", MECHANIC_SKILLS, MECHANIC_STATS,
        *TIER_MED_SPEC, *TIER_MED_BASE)


def _make_mechanic_high():
    return _build_template_randomized("Mechanic (high)", MECHANIC_SKILLS, MECHANIC_STATS,
        *TIER_HIGH_SPEC, *TIER_HIGH_BASE)


def _make_doctor_low():
    return _build_template_randomized("Doctor (low)", DOCTOR_SKILLS, DOCTOR_STATS,
        *TIER_LOW_SPEC, *TIER_LOW_BASE)


def _make_doctor_med():
    return _build_template_randomized("Doctor (med)", DOCTOR_SKILLS, DOCTOR_STATS,
        *TIER_MED_SPEC, *TIER_MED_BASE)


def _make_doctor_high():
    return _build_template_randomized("Doctor (high)", DOCTOR_SKILLS, DOCTOR_STATS,
        *TIER_HIGH_SPEC, *TIER_HIGH_BASE)


def _make_techie_low():
    return _build_template_randomized("Techie (low)", TECHIE_SKILLS, TECHIE_STATS,
        *TIER_LOW_SPEC, *TIER_LOW_BASE)


def _make_techie_med():
    return _build_template_randomized("Techie (med)", TECHIE_SKILLS, TECHIE_STATS,
        *TIER_MED_SPEC, *TIER_MED_BASE)


def _make_techie_high():
    return _build_template_randomized("Techie (high)", TECHIE_SKILLS, TECHIE_STATS,
        *TIER_HIGH_SPEC, *TIER_HIGH_BASE)


# Key -> callable that returns a fresh template dict (name, stats, skills)
NPC_TEMPLATE_BUILDERS = {
    "combat_low": _make_combat_low,
    "combat_med": _make_combat_med,
    "combat_high": _make_combat_high,
    "mechanic_low": _make_mechanic_low,
    "mechanic_med": _make_mechanic_med,
    "mechanic_high": _make_mechanic_high,
    "doctor_low": _make_doctor_low,
    "doctor_med": _make_doctor_med,
    "doctor_high": _make_doctor_high,
    "techie_low": _make_techie_low,
    "techie_med": _make_techie_med,
    "techie_high": _make_techie_high,
    "random": _build_random_template,
}

# For listing: key -> display name (get_npc_template builds the full dict on demand)
NPC_TEMPLATES = {k: {"name": v()["name"]} for k, v in NPC_TEMPLATE_BUILDERS.items()}


def get_npc_template(key):
    """Return template dict (name, stats, skills) for key, or None. Randomized templates are built fresh each call."""
    k = (key or "").strip().lower()
    builder = NPC_TEMPLATE_BUILDERS.get(k)
    if builder:
        return builder()
    return None


def apply_npc_template(npc, template_key, template=None):
    """Apply a template's stats and skills to an existing NPC. Sets needs_chargen = False. If template dict is provided, use it; else build from template_key."""
    if template is None:
        template = get_npc_template(template_key)
    if not template or not npc or not hasattr(npc, "db"):
        return False
    npc.db.stats = dict(template["stats"])
    npc.db.skills = dict(template["skills"])
    npc.db.needs_chargen = False
    # Wake vitals so max_hp/stamina are computed
    _ = getattr(npc, "hp", None)
    _ = getattr(npc, "stamina", None)
    if hasattr(npc, "max_hp"):
        npc.db.current_hp = npc.max_hp
    if hasattr(npc, "max_stamina"):
        npc.db.current_stamina = npc.max_stamina
    return True


def create_npc_from_template(template_key, name=None, location=None):
    """
    Create an NPC from a template. If name is provided, use it as the object key.
    Returns the created NPC or None.
    """
    template = get_npc_template(template_key)
    if not template:
        return None
    from evennia import create_object
    display_name = (name or template["name"]).strip()
    if not display_name:
        display_name = template["name"]
    try:
        npc = create_object(
            "typeclasses.npc.NPC",
            key=display_name,
            location=location,
            nohome=True,
        )
    except Exception:
        return None
    if not npc:
        return None
    apply_npc_template(npc, template_key, template=template)
    return npc

