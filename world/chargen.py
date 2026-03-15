# D:\moo\mootest\world\chargen.py
# Arcanepunk / grimdark chargen: immersive CYOA, same stat/skill mechanics.
import random

from world.levels import MAX_LEVEL, MAX_STAT_LEVEL, level_to_letter

STAT_KEYS = ["strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"]
STAT_ABBREVS = {"str": "strength", "per": "perception", "end": "endurance", "cha": "charisma", "int": "intelligence", "agi": "agility", "lck": "luck"}
# Display names for stat allocation screen (reused in node_stats)
STAT_DISPLAY_NAMES = {
    "strength": "Strength", "perception": "Perception", "endurance": "Endurance",
    "charisma": "Charisma", "intelligence": "Intelligence", "agility": "Agility", "luck": "Luck",
}
from world.skills import SKILL_KEYS, SKILL_DISPLAY_NAMES


def _compute_stat_caps(priority_order):
    """Generate 7 random stat caps (160-280 on 0-300 scale), sort descending by priority. Allows 3-4 stats to reach D-E over time."""
    caps = sorted([random.randint(160, 280) for _ in range(7)], reverse=True)
    return {stat: caps[i] for i, stat in enumerate(priority_order)}


def _compute_skill_caps():
    """Random level cap per skill (80-150) so most can reach D-C with play."""
    return {sk: random.randint(80, 150) for sk in SKILL_KEYS}


# Flavor for stat priority CYOA (what defined you)
STAT_PRIORITY_FLAVOR = {
    "strength": "|wBrute force|n — You carried what others couldn't. The tunnels, the pits, the loads that break backs.",
    "perception": "|wAwareness|n — You learned to see the threat before it saw you. A flicker in the dark, a wrong step.",
    "endurance": "|wEndurance|n — You outlasted. Hunger, cold, the long shifts. The undercity takes; you didn't break.",
    "charisma": "|wCharisma|n — You talked your way through. Deals, lies, or a moment of trust when it mattered.",
    "intelligence": "|wCunning|n — You thought when others swung. The right wire, the right word, the right moment.",
    "agility": "|wReflexes|n — You moved when standing still meant death. The ducts, the patrols, the things in the deep.",
    "luck": "|wLuck|n — You were there when the ceiling didn't fall. The bullet missed. The Inquisitor looked the other way.",
}

# Flavor for stat allocation (short in-world description)
STAT_ALLOC_FLAVOR = {
    "strength": "Raw power. The mines and the pits reward it.",
    "perception": "Eyes in the dark. You notice what others miss.",
    "endurance": "Stamina. The long haul, the long night.",
    "charisma": "Presence. You sway people — or fool them.",
    "intelligence": "Wits. Systems, patterns, the edge of thought.",
    "agility": "Speed and grace. The undercity favors the quick.",
    "luck": "Fortune. Sometimes the only thing between you and the end.",
}

# Backgrounds: (display_name, db.background value, stat_points, flavor paragraph)
BACKGROUNDS = [
    (
        "Corporate Hab-Sector",
        "Corporate Hab-Sector",
        5,
        "You grew up in the sealed sectors where the Authority's clerks and contractors live. Clean air, rations, and the constant hum of compliance. You learned to speak their language — and to want more than the script allowed.",
    ),
    (
        "The Smog-Lungs (Labour)",
        "Smog-Lungs",
        5,
        "The lower levels. Factories, refineries, the breath that tastes of metal and soot. You worked. You carried. You survived the shifts that grind people into the floor. The undercity runs on your back.",
    ),
    (
        "Undercity Rat",
        "Undercity Rat",
        5,
        "You had no sector. You had the ducts, the black markets, and the things that move when the lights flicker. You stole, you ran, you made a life in the cracks the Authority hasn't sealed.",
    ),
    (
        "Barracks-Child",
        "Barracks-Child",
        5,
        "You were raised in the shadow of the Guard. Maybe a parent wore the uniform; maybe you just lived close enough to learn the weight of a mag-weapon and the look of someone who has permission to use it.",
    ),
    (
        "Apostate Sympathizer",
        "Apostate Sympathizer",
        5,
        "Heresy is whatever the Inquisition says it is. You grew up in a cell, a safe house, or a family that whispered. You know what it costs to believe something the Authority forbids.",
    ),
    (
        "Inquisitorial Servant",
        "Inquisitorial Servant",
        5,
        "You served the Inquisition — scribe, runner, or something darker. You've seen how they root out dissent. You know the forms, the procedures. You know what they do to the ones they take.",
    ),
]


# ==========================================
# INTRO
# ==========================================

def node_start(caller):
    text = (
        "|c[ NEURAL-LINK INITIALIZATION ]|n\n\n"
        "Cold. The first thing you feel is |ccold|n.\n\n"
        "You are suspended in fluid. Above you, a curved ceiling of metal and cabling. The light is sterile, unforgiving. "
        "Somewhere a pump thrums. You are in a |wreclamation vat|n — one of the facilities where the Authority "
        "processes those who are brought in from the sectors, the tunnels, or the wrong side of an Inquisitor's gaze.\n\n"
        "A robotic arm descends. A lens focuses on your face. A voice, synthetic and flat:\n\n"
        "|y'SUBJECT DETECTED. NEURAL-LINK SEQUENCE PENDING. CALIBRATION WILL EXTRACT GENETIC AND COGNITIVE MARKERS.'|n\n\n"
        "You have no choice but to comply. The link will read your past and shape what you can become.\n\n"
        "|wAccept the link.|n"
    )
    options = [{"desc": "I accept. Begin calibration.", "goto": "node_intro_lore"}]
    return text, options


def node_intro_lore(caller, raw_string, **kwargs):
    text = (
        "|c[ CONTEXT LOAD ]|n\n\n"
        "The colony is |wunderground|n. Above the sealed roof: a world of mutated wildlife, toxic winds, and things that have forgotten the shape of humanity. "
        "The city survives behind walls and filters. It survives because it |wsends people out|n — scavengers, runners, cannon fodder — to bring back what the machinery needs.\n\n"
        "Inside, the |wAuthority|n holds the only real power. Its Guards carry mag-weapons; its |rInquisitors|n root out heresy and rebellion with an iron fist. "
        "Most people keep their heads down. You didn't, or you couldn't, or you were born in the wrong place.\n\n"
        "The vat is your reset. When you step out, you will be someone the system can |wuse|n — or someone who learns to use the system.\n\n"
        "The link is ready. It will now read your |worigin|n."
    )
    options = [{"desc": "Continue", "goto": "node_background"}]
    return text, options


# ==========================================
# BACKGROUND
# ==========================================

def node_background(caller):
    text = (
        "|y'ORIGIN POINT: SELECT SUBJECT BACKGROUND.'|n\n\n"
        "Where did you come from? The link will use this to anchor your genetic and behavioural profile.\n\n"
        "Choose |wonce|n. There is no going back."
    )
    options = []
    for disp_name, _bg_key, _points, _flavor in BACKGROUNDS:
        options.append({
            "desc": disp_name,
            "goto": ("node_apply_background", {"bg_index": BACKGROUNDS.index((disp_name, _bg_key, _points, _flavor))}),
        })
    return text, options


def node_apply_background(caller, raw_string, **kwargs):
    idx = kwargs.get("bg_index", 0)
    if idx < 0 or idx >= len(BACKGROUNDS):
        idx = 0
    disp_name, bg_key, points, flavor = BACKGROUNDS[idx]
    caller.db.background = bg_key
    caller.db.stat_points = points
    text = (
        "|g'ORIGIN LOCKED.'|n\n\n"
        "{}\n\n"
        "|y'GENETIC MARKERS CONFIRMED. PROCEEDING TO TRAIT EXTRACTION.'|n"
    ).format(flavor)
    options = [{"desc": "Continue", "goto": "node_priority_intro"}]
    return text, options


# ==========================================
# STAT PRIORITY (CYOA: 7 choices)
# ==========================================

def node_priority_intro(caller, raw_string, **kwargs):
    caller.db.stat_priority_order = []
    text = (
        "|c[ TRAIT EXTRACTION ]|n\n\n"
        "The link is probing your memories. Not words — |winstincts|n. The things that kept you alive when the undercity tried to break you.\n\n"
        "You will choose, in order, the traits that defined you. The |worder|n matters: the link will weight your potential accordingly. "
        "There are no right answers. Only what was true.\n\n"
        "|y'EXTRACT FIRST SURVIVAL TRAIT.'|n"
    )
    options = [{"desc": "I'm ready.", "goto": "node_priority_choose"}]
    return text, options


def node_priority_choose(caller, raw_string, **kwargs):
    order = getattr(caller.db, "stat_priority_order", None) or []
    remaining = [s for s in STAT_KEYS if s not in order]
    if not remaining:
        # All seven chosen; compute caps and go to stat allocation
        caller.db.stat_caps = _compute_stat_caps(order)
        caller.db.skill_caps = _compute_skill_caps()
        del caller.db.stat_priority_order
        text = "|g'TRAIT SEQUENCE COMPLETE. CAPS CALCULATED.'|n\n\nProceeding to genetic calibration."
        options = [{"desc": "Continue", "goto": "node_stats"}]
        return text, options
    slot = len(order) + 1
    if slot == 1:
        prompt = "What was the |wfirst|n thing the undercity taught you? What kept you alive before anything else?"
    elif slot == 7:
        prompt = "One trait remains. What was the |wlast|n thread that held you together?"
    else:
        prompt = "What came |wnext|n? Which trait defined you after that?"
    text = (
        "|cTRAIT EXTRACTION — SLOT {}|n\n\n"
        "{}\n\n"
        "|y'SELECT.'|n"
    ).format(slot, prompt)
    options = []
    for stat in remaining:
        options.append({
            "desc": STAT_PRIORITY_FLAVOR.get(stat, stat.replace("_", " ").title()),
            "goto": ("node_priority_pick", {"stat": stat}),
        })
    return text, options


def node_priority_pick(caller, raw_string, **kwargs):
    stat = kwargs.get("stat")
    if stat not in STAT_KEYS:
        return node_priority_choose(caller, raw_string, **kwargs)
    order = getattr(caller.db, "stat_priority_order", None) or []
    if stat in order:
        return node_priority_choose(caller, raw_string, **kwargs)
    order = list(order) + [stat]
    caller.db.stat_priority_order = order
    return node_priority_choose(caller, raw_string, **kwargs)


# ==========================================
# STAT ALLOCATION (unchanged logic, flavor text)
# ==========================================

def node_stats(caller, raw_string, **kwargs):
    stats = caller.db.stats or {}
    points = getattr(caller.db, "stat_points", 0)
    caps = getattr(caller.db, "stat_caps", None) or {}
    stat_lines = []
    for key, name in STAT_DISPLAY_NAMES.items():
        cur = stats.get(key, 0)
        if not isinstance(cur, int):
            cur = 0
        cap = caps.get(key, MAX_STAT_LEVEL)
        if not isinstance(cap, int):
            cap = MAX_STAT_LEVEL
        letter = level_to_letter(cur, MAX_STAT_LEVEL)
        cap_letter = level_to_letter(cap, MAX_STAT_LEVEL)
        adj = caller.get_stat_grade_adjective(letter, key)
        flav = STAT_ALLOC_FLAVOR.get(key, "")
        stat_lines.append(f"  |c{name}|n: |w[{letter}]|n / [{cap_letter}] — {adj} — {flav}")
    text = (
        "|c[ GENETIC CALIBRATION ]|n\n\n"
        "The link has mapped your potential. You have |w{}|n calibration point(s) to allocate. "
        "Each shift reinforces one aspect of your genetic profile.\n\n"
        "Current profile:\n"
        "{}\n\n"
        "Choose a marker to improve, or confirm to proceed."
    ).format(points, "\n".join(stat_lines))
    options = []
    if points > 0:
        for stat_key, name in STAT_DISPLAY_NAMES.items():
            options.append({
                "desc": f"Improve {name}",
                "goto": ("node_increase_stat", {"stat": stat_key}),
            })
    options.append({"desc": "|gConfirm profile|n", "goto": "node_skills_intro"})
    return text, options


def node_increase_stat(caller, raw_string, **kwargs):
    stat_to_increase = kwargs.get("stat")
    caps = getattr(caller.db, "stat_caps", None) or {}
    cap = caps.get(stat_to_increase, MAX_STAT_LEVEL)
    if not isinstance(cap, int):
        cap = MAX_STAT_LEVEL
    current = caller.db.stats.get(stat_to_increase, 0)
    if not isinstance(current, int):
        current = 0
    # 1 calibration point = +1 displayed point = +2 stored (same scale as skills)
    add = min(2, cap - current) if current < cap else 0
    if getattr(caller.db, "stat_points", 0) > 0 and add > 0:
        caller.db.stats[stat_to_increase] = current + add
        caller.db.stat_points -= 1
    return node_stats(caller, raw_string, **kwargs)


# ==========================================
# SKILL ALLOCATION (unchanged logic, flavor)
# ==========================================

def node_skills_intro(caller, raw_string, **kwargs):
    text = (
        "|c[ NEURAL-LINK: SKILL PROTOCOLS ]|n\n\n"
        "Genetic calibration is complete. The link will now inject |wskill protocols|n — combat, survival, and technical templates "
        "that your neural profile can support. You have a limited number of injections; choose where you want to be competent.\n\n"
        "|y'INITIATE SKILL INJECTION.'|n"
    )
    options = [{"desc": "Continue", "goto": "node_skills"}]
    return text, options


def node_skills(caller, raw_string, **kwargs):
    if getattr(caller.db, "skill_points", None) is None:
        caller.db.skill_points = 10
    skills = caller.db.skills or {}
    caps = getattr(caller.db, "skill_caps", None) or {}
    points = caller.db.skill_points
    skill_lines = []
    for sk in SKILL_KEYS:
        name = SKILL_DISPLAY_NAMES.get(sk, sk.replace("_", " ").title())
        cur = skills.get(sk, 0)
        if not isinstance(cur, int):
            cur = 0
        cap = caps.get(sk, MAX_LEVEL)
        if not isinstance(cap, int):
            cap = MAX_LEVEL
        letter = level_to_letter(cur, MAX_LEVEL)
        cap_letter = level_to_letter(cap, MAX_LEVEL)
        adj = caller.get_skill_grade_adjective(letter)
        skill_lines.append(f"  |c{name}|n: |w[{letter}]|n / [{cap_letter}] — {adj}")
    text = (
        "|cSKILL PROTOCOL INJECTION|n\n\n"
        "You have |w{}|n injection(s) remaining. Each reinforces one protocol.\n\n"
        "Current protocols:\n"
        "{}\n\n"
        "Select a protocol to reinforce, or continue to identity lock."
    ).format(points, "\n".join(skill_lines))
    options = []
    if points > 0:
        for skill_key in SKILL_KEYS:
            name = SKILL_DISPLAY_NAMES.get(skill_key, skill_key.replace("_", " ").title())
            options.append({
                "desc": f"Reinforce {name}",
                "goto": ("node_increase_skill", {"skill": skill_key}),
            })
    options.append({"desc": "|gContinue|n", "goto": "node_gender"})
    return text, options


def node_increase_skill(caller, raw_string, **kwargs):
    skill_to_increase = kwargs.get("skill")
    caps = getattr(caller.db, "skill_caps", None) or {}
    cap = caps.get(skill_to_increase, MAX_LEVEL)
    if not isinstance(cap, int):
        cap = MAX_LEVEL
    current = (caller.db.skills or {}).get(skill_to_increase, 0)
    if not isinstance(current, int):
        current = 0
    if getattr(caller.db, "skill_points", 0) > 0 and current < cap and current < MAX_LEVEL:
        caller.db.skills[skill_to_increase] = current + 1
        caller.db.skill_points -= 1
    return node_skills(caller, raw_string, **kwargs)


# ==========================================
# GENDER / IDENTITY
# ==========================================

def node_gender(caller, raw_string, **kwargs):
    text = (
        "|c[ IDENTITY CALIBRATION ]|n\n\n"
        "The link needs to lock your |widentity marker|n — how you will be referred to in logs and in the field. "
        "This affects how others see you in poses and reports.\n\n"
        "  |wMale|n → he, his, him\n"
        "  |wFemale|n → she, her, her\n"
        "  |wNonbinary|n → they, their, them"
    )
    options = [
        {"desc": "Male (he/his/him)", "goto": ("node_apply_gender", {"gender": "male"})},
        {"desc": "Female (she/her/her)", "goto": ("node_apply_gender", {"gender": "female"})},
        {"desc": "Nonbinary (they/their/them)", "goto": ("node_apply_gender", {"gender": "nonbinary"})},
    ]
    return text, options


def node_apply_gender(caller, raw_string, **kwargs):
    gender = kwargs.get("gender", "nonbinary")
    caller.db.gender = gender
    caller.db.pronoun = gender
    text = "|g'IDENTITY LOCKED.'|n\n\nProceeding to finalization."
    options = [{"desc": "Finalize", "goto": "node_finish"}]
    return text, options


# ==========================================
# FINISH
# ==========================================

def node_finish(caller, raw_string, **kwargs):
    caller.db.needs_chargen = False
    for attr in ("stat_points", "skill_points", "stat_caps", "skill_caps"):
        if hasattr(caller.db, attr) and caller.attributes.has(attr):
            caller.attributes.remove(attr)
    text = (
        "|g'CALIBRATION COMPLETE. NEURAL LINK STABLE.'|n\n\n"
        "The fluid drains. The vat opens. You step out onto the cold floor of the reclamation facility — "
        "one more body the Authority has processed, tagged, and released into the undercity.\n\n"
        "Outside, the walls hold. The Guards watch. The Inquisitors hunt. And somewhere in the dark, "
        "the city waits to see what you do next.\n\n"
        "|wYou are in the world.|n"
    )
    return text, []
