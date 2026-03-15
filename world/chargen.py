# D:\moo\mootest\world\chargen.py
# Gutterpunk/arcanepunk chargen: occult Rite, blood-signs, marks. Dark/red UI. No XP spend; skills by marks.
import random

from world.levels import MAX_LEVEL, MAX_STAT_LEVEL, level_to_letter, xp_cost_for_next_level

STAT_KEYS = ["strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"]
STAT_ABBREVS = {"str": "strength", "per": "perception", "end": "endurance", "cha": "charisma", "int": "intelligence", "agi": "agility", "lck": "luck"}
STAT_DISPLAY_NAMES = {
    "strength": "Strength", "perception": "Perception", "endurance": "Endurance",
    "charisma": "Charisma", "intelligence": "Intelligence", "agility": "Agility", "luck": "Luck",
}
from world.skills import SKILL_KEYS, SKILL_DISPLAY_NAMES

# UI column widths
CHARGEN_NAME_W = 24
CHARGEN_LETTER_W = 5
CHARGEN_ADJ_W = 20
CHARGEN_FLAVOR_W = 42

# Marks: each mark raises one skill to this level (E tier). No XP pool in chargen.
CHARGEN_MARKS = 3
CHARGEN_MARK_SKILL_LEVEL = (14 * MAX_LEVEL) // 17   # ~123 = high E / low D

# Stat random ranges per priority slot (1=highest priority, 7=lowest). (min, max) stored value 0-300; kept well below caps.
# Higher priority = higher cap later, and a bit higher starting range so you're "naturally" better there but still beginner.
STAT_RANDOM_RANGES_BY_PRIORITY = [
    (50, 120),   # 1st: best cap, decent starting spread
    (40, 100),
    (30, 85),
    (25, 70),
    (20, 55),
    (15, 45),
    (10, 35),    # 7th: lowest cap, lowest start
]


def _compute_stat_caps(order):
    """Generate 7 random stat caps (160-280 on 0-300 scale) sorted by priority order. Not shown to player."""
    caps = sorted([random.randint(160, 280) for _ in range(7)], reverse=True)
    return {stat: caps[i] for i, stat in enumerate(order)}


def _randomize_stats_from_priority(order):
    """Set starting stats from priority order: each stat gets a random value in its slot's range (beginner spread)."""
    stats = {}
    for i, stat in enumerate(order):
        lo, hi = STAT_RANDOM_RANGES_BY_PRIORITY[i]
        stats[stat] = random.randint(lo, hi)
    return stats


def _compute_skill_caps():
    """Random level cap per skill (80-150). Not shown to player."""
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
# INTRO — the Rite (occult / gutterpunk)
# ==========================================

def node_start(caller):
    text = (
        "|x|n\n"
        "|r╔══════════════════════════════════════════════════════════════╗|n\n"
        "|r║|n  |RTHE RITE|n\n"
        "|r╚══════════════════════════════════════════════════════════════╝|n\n\n"
        "|xDarkness. Then the smell of |rblood|n and rust and something older.|n\n\n"
        "You are on your back. Stone beneath you — cold, carved with grooves that catch the light like |rveins|n. "
        "Above, a low ceiling. Candles or coils; the air shimmers. This is not a clinic. This is |ra binding|n.\n\n"
        "A figure leans over you. You cannot see the face. A hand touches your brow. The voice is not a machine:\n\n"
        "|r\"You are empty. The Pact will fill you. Your past will become the sigil. Your name will become the key.\"|n\n\n"
        "You have no choice. The Rite has already begun.\n\n"
        "|rAccept.|n"
    )
    options = [{"desc": "|rI accept. Begin the Rite.|n", "goto": "node_name"}]
    return text, options


def node_name(caller, raw_string, **kwargs):
    text = (
        "|r── BLOOD-SIGN ──|n\n\n"
        "The figure waits. No file. No tag. Only the name you will wear when you rise.\n\n"
        "|R\"Speak the name. The one the Below will know.\"|n\n\n"
        "|xEnter the name you will bear|n (2–30 characters; letters, numbers, spaces, hyphens, apostrophes):"
    )
    options = [{"key": "_default", "goto": "node_apply_name"}]
    return text, options


def node_apply_name(caller, raw_string, **kwargs):
    from evennia.utils.evmenu import EvMenuGotoAbortMessage
    name = (raw_string or "").strip()
    if len(name) < 2:
        raise EvMenuGotoAbortMessage("|rName must be at least 2 characters.|n")
    if len(name) > 30:
        raise EvMenuGotoAbortMessage("|rName must be 30 characters or fewer.|n")
    for c in name:
        if not (c.isalnum() or c in " -'"):
            raise EvMenuGotoAbortMessage("|rOnly letters, numbers, spaces, hyphens, apostrophes.|n")
    caller.key = name
    if hasattr(caller, "aliases") and caller.aliases:
        try:
            caller.aliases.add(name)
        except Exception:
            pass
    return node_intro_lore(caller, raw_string, **kwargs)


def node_intro_lore(caller, raw_string, **kwargs):
    text = (
        "|r── THE PACT ──|n\n\n"
        "The colony is |xunderground|n. Above: a world of poison, mutation, and things that have forgotten the shape of man. "
        "The city survives because it |rsends people out|n — scavengers, runners, blood for the machine.\n\n"
        "Below, the |RAuthority|n holds the only law. Its Guards carry mag-steel. Its |rInquisitors|n burn what they call heresy. "
        "Most keep their heads down. You didn't. Or you couldn't. Or you were born in the wrong trench.\n\n"
        "The Rite will etch you into something the system can |ruse|n — or something that uses the system.\n\n"
        "|R\"Your origin. Where did you come from?\"|n"
    )
    options = [{"desc": "|rContinue|n", "goto": "node_background"}]
    return text, options


# ==========================================
# BACKGROUND
# ==========================================

def node_background(caller):
    text = (
        "|r── ORIGIN ──|n\n\n"
        "|R\"Where did you come from? The sigil needs an anchor. A story written in bone.\"|n\n\n"
        "Choose |ronce|n. There is no going back."
    )
    options = []
    for disp_name, _bg_key, _points, _flavor in BACKGROUNDS:
        options.append({
            "desc": "|x%s|n" % disp_name,
            "goto": ("node_apply_background", {"bg_index": BACKGROUNDS.index((disp_name, _bg_key, _points, _flavor))}),
        })
    return text, options


def node_apply_background(caller, raw_string, **kwargs):
    idx = kwargs.get("bg_index", 0)
    if idx < 0 or idx >= len(BACKGROUNDS):
        idx = 0
    disp_name, bg_key, points, flavor = BACKGROUNDS[idx]
    caller.db.background = bg_key
    text = (
        "|r'ORIGIN LOCKED.'|n\n\n"
        "%s\n\n"
        "|R\"The sigil reads you. Now — the traits that kept you alive. In order.\"|n"
    ) % flavor
    options = [{"desc": "|rContinue|n", "goto": "node_priority_intro"}]
    return text, options


# ==========================================
# STAT PRIORITY (7 choices → cap order + random spread)
# ==========================================

def node_priority_intro(caller, raw_string, **kwargs):
    caller.db.stat_priority_order = []
    text = (
        "|r── TRAIT EXTRACTION ──|n\n\n"
        "The Rite is not reading words. It is reading |rinstinct|n. The things that kept you alive when the Below tried to break you.\n\n"
        "You will choose, in order, the traits that defined you. The |Rorder|n matters. The sigil will weight your potential.\n\n"
        "|R\"First survival trait. What was it?\"|n"
    )
    options = [{"desc": "|rI'm ready.|n", "goto": "node_priority_choose"}]
    return text, options


def node_priority_choose(caller, raw_string, **kwargs):
    order = getattr(caller.db, "stat_priority_order", None) or []
    remaining = [s for s in STAT_KEYS if s not in order]
    if not remaining:
        caller.db.stat_caps = _compute_stat_caps(order)
        caller.db.stats = _randomize_stats_from_priority(order)
        if getattr(caller.db, "skill_caps", None) is None:
            caller.db.skill_caps = _compute_skill_caps()
        del caller.db.stat_priority_order
        text = "|r'SIGIL SEQUENCE COMPLETE.'|n\n\nProceeding to readout — then |Rmarks|n."
        options = [{"desc": "|rContinue|n", "goto": "node_stats"}]
        return text, options
    slot = len(order) + 1
    if slot == 1:
        prompt = "What was the |rfirst|n thing the undercity taught you?"
    elif slot == 7:
        prompt = "One trait remains. The |rlast|n thread that held you together."
    else:
        prompt = "What came |rnext|n?"
    text = (
        "|r── TRAIT — SLOT %s ──|n\n\n"
        "%s\n\n"
        "|R\"SELECT.\"|n"
    ) % (slot, prompt)
    options = []
    for stat in remaining:
        options.append({
            "desc": "|x%s|n" % STAT_PRIORITY_FLAVOR.get(stat, stat.replace("_", " ").title()),
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
# STAT READOUT
# ==========================================

def node_stats(caller, raw_string, **kwargs):
    stats = caller.db.stats or {}
    lines = []
    for key, name in STAT_DISPLAY_NAMES.items():
        cur = stats.get(key, 0)
        if not isinstance(cur, int):
            cur = 0
        letter = level_to_letter(cur, MAX_STAT_LEVEL)
        adj = caller.get_stat_grade_adjective(letter, key)
        flav = STAT_ALLOC_FLAVOR.get(key, "")
        name_pad = "|x" + name.ljust(CHARGEN_NAME_W) + "|n"
        letter_part = "|r" + ("[%s] " % letter).ljust(CHARGEN_LETTER_W) + "|n"
        adj_pad = adj.ljust(CHARGEN_ADJ_W)
        flav_str = flav[:CHARGEN_FLAVOR_W] if len(flav) > CHARGEN_FLAVOR_W else flav
        lines.append("  %s %s %s  %s" % (name_pad, letter_part, adj_pad, flav_str))
    text = (
        "|r── SIGIL READOUT ──|n\n\n"
        "The Rite has mapped you. Current profile:\n\n"
        "%s\n\n"
        "Confirm. Then you will receive |Rmarks|n — skills etched into the sigil."
    ) % "\n".join(lines)
    options = [{"desc": "|rConfirm|n", "goto": "node_skills_intro"}]
    return text, options


# ==========================================
# SKILL ALLOCATION — marks (no XP; each mark raises one skill to E/D tier)
# ==========================================

def node_skills_intro(caller, raw_string, **kwargs):
    caller.db.chargen_marks_used = 0
    caller.db.skills = getattr(caller.db, "skills", None) or {}
    text = (
        "|r── MARKS ──|n\n\n"
        "|R\"The sigil can etch |rskills|n into you. Not study — |rblood-memory|n. Instinct.\"|n\n\n"
        "You have |R%s|n mark(s). Each mark raises one skill to a set tier — enough to survive the first cut. "
        "Choose which skills receive a mark. No take-backs.\n\n"
        "|R\"Choose the first mark.\"|n"
    ) % CHARGEN_MARKS
    options = [{"desc": "|rContinue|n", "goto": "node_skills"}]
    return text, options


def node_skills(caller, raw_string, **kwargs):
    marks_used = int(getattr(caller.db, "chargen_marks_used", 0) or 0)
    marks_left = CHARGEN_MARKS - marks_used
    skills = caller.db.skills or {}
    caps = getattr(caller.db, "skill_caps", None) or {}
    mark_level = min(CHARGEN_MARK_SKILL_LEVEL, MAX_LEVEL)
    skill_lines = []
    for sk in SKILL_KEYS:
        name = SKILL_DISPLAY_NAMES.get(sk, sk.replace("_", " ").title())
        cur = skills.get(sk, 0)
        if not isinstance(cur, int):
            cur = 0
        letter = level_to_letter(cur, MAX_LEVEL)
        name_pad = "|x" + name.ljust(CHARGEN_NAME_W) + "|n"
        letter_part = "|r[%s]|n" % letter
        skill_lines.append("  %s  %s" % (name_pad, letter_part))
    text = (
        "|r── MARKS (%s remaining) ──|n\n\n"
        "Current etchings:\n"
        "%s\n\n"
        "%s"
    ) % (
        marks_left,
        "\n".join(skill_lines),
        "Choose a skill to mark." if marks_left > 0 else "All marks placed."
    )
    options = []
    if marks_left > 0:
        for skill_key in SKILL_KEYS:
            cur = skills.get(skill_key, 0)
            if not isinstance(cur, int):
                cur = 0
            cap = caps.get(skill_key, MAX_LEVEL)
            if not isinstance(cap, int):
                cap = MAX_LEVEL
            target = min(mark_level, cap)
            if cur < target:
                name = SKILL_DISPLAY_NAMES.get(skill_key, skill_key.replace("_", " ").title())
                options.append({
                    "desc": "|rMark: %s|n" % name,
                    "goto": ("node_apply_mark", {"skill": skill_key}),
                })
    options.append({"desc": "|rContinue to identity|n" if marks_left == 0 else "|xSkip remaining marks|n", "goto": "node_gender"})
    return text, options


def node_apply_mark(caller, raw_string, **kwargs):
    """Apply one mark to the chosen skill; then back to node_skills or node_gender."""
    skill_key = kwargs.get("skill")
    if skill_key not in SKILL_KEYS:
        return node_skills(caller, raw_string, **kwargs)
    caps = getattr(caller.db, "skill_caps", None) or {}
    skills = caller.db.skills or {}
    cur = skills.get(skill_key, 0)
    if not isinstance(cur, int):
        cur = 0
    cap = caps.get(skill_key, MAX_LEVEL)
    if not isinstance(cap, int):
        cap = MAX_LEVEL
    target = min(CHARGEN_MARK_SKILL_LEVEL, cap)
    if cur >= target:
        return node_skills(caller, raw_string, **kwargs)
    if not caller.db.skills:
        caller.db.skills = {}
    caller.db.skills[skill_key] = target
    caller.db.chargen_marks_used = int(getattr(caller.db, "chargen_marks_used", 0) or 0) + 1
    return node_skills(caller, raw_string, **kwargs)


# ==========================================
# GENDER / IDENTITY
# ==========================================

def node_gender(caller, raw_string, **kwargs):
    text = (
        "|r── IDENTITY ──|n\n\n"
        "|R\"How will the world name you? The sigil needs a pronoun — how others will see you in the logs.\"|n\n\n"
        "  |xMale|n → he, his, him\n"
        "  |xFemale|n → she, her, her\n"
        "  |xNonbinary|n → they, their, them"
    )
    options = [
        {"desc": "|rMale|n", "goto": ("node_apply_gender", {"gender": "male"})},
        {"desc": "|rFemale|n", "goto": ("node_apply_gender", {"gender": "female"})},
        {"desc": "|rNonbinary|n", "goto": ("node_apply_gender", {"gender": "nonbinary"})},
    ]
    return text, options


def node_apply_gender(caller, raw_string, **kwargs):
    gender = kwargs.get("gender", "nonbinary")
    caller.db.gender = gender
    caller.db.pronoun = gender
    text = "|r'IDENTITY LOCKED.'|n\n\n|R\"The Rite is complete. Rise.\"|n"
    options = [{"desc": "|rFinalize|n", "goto": "node_finish"}]
    return text, options


# ==========================================
# FINISH
# ==========================================

def node_finish(caller, raw_string, **kwargs):
    caller.db.needs_chargen = False
    for attr in ("stat_points", "skill_points", "chargen_xp", "skill_chargen_xp", "chargen_marks_used",):
        if hasattr(caller.db, attr) and getattr(caller, "attributes", None) and caller.attributes.has(attr):
            try:
                caller.attributes.remove(attr)
            except Exception:
                pass
    text = (
        "|r╔══════════════════════════════════════════════════════════════╗|n\n"
        "|r║|n  |RTHE RITE IS COMPLETE|n\n"
        "|r╚══════════════════════════════════════════════════════════════╝|n\n\n"
        "The candles gutter. The grooves in the stone no longer glow. You are no longer empty.\n\n"
        "You stand. The figure is gone. Somewhere a door opens onto |xdarkness|n — the undercity, the ducts, "
        "the first step of the rest of your life. The Authority will tag you. The Inquisitors will hunt. "
        "And in the deep, something that was never human waits.\n\n"
        "|RYou are in the world.|n"
    )
    return text, []
