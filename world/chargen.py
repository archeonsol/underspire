# D:\moo\mootest\world\chargen.py
# Gutterpunk/arcanepunk chargen: occult Rite, blood-signs, marks. Dark/red UI. No XP spend; skills by marks.
import random

from world.levels import MAX_LEVEL, MAX_STAT_LEVEL, level_to_letter

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

# Ladder of 6 Marks: tiered by what defined them (~240 XP total, realistic distribution).
# (count, level, tier_label) — Job = one strong skill, Hobbies = two solid, Basics = three foundational.
MARKS_LADDER = [
    (1, 105, "Job"),      # Grade E — "Their Job" (~80 XP)
    (2, 81, "Hobbies"),   # Grade H — "Their Hobbies" (~40 XP each)
    (3, 52, "Basics"),    # Grade L — "Their Basics" (~26 XP each)
]
CHARGEN_MARKS_TOTAL = sum(n for n, _, _ in MARKS_LADDER)  # 6

# Revised for 2.0 XP per level math to target ~450 XP starting power
STAT_RANDOM_RANGES_BY_PRIORITY = [
    (35, 50),   # 1st: (70-100 XP)
    (25, 35),   # 2nd
    (15, 25),   # 3rd
    (10, 15),   # 4th
    (5, 10),    # 5th
    (2, 5),     # 6th
    (0, 2),     # 7th
]

# HP design: max_hp = BASE_HP (26.5) + end_display + max(0, (str_display-100)*0.5). Display = get_display_stat (stored//2).
# Tiers: excellent <115, spectacular 115-129, magnificent 130-151, miraculous 152+.
# XP from 0 (endurance only): Spectacular 356 (end 89 display / 178 stored), Magnificent 473 (104/208), Miraculous 1131 (126/252).
# XP from cgen (end 50): Spectacular ~256, Magnificent ~373, Miraculous ~1031.
XP_FOR_SPECTACULAR_HP = 256   # end 50 → 178 stored (89 display) = 115 HP
XP_FOR_MAGNIFICENT_HP = 373   # end 50 → 208 stored (104 display) = 130 HP
XP_FOR_MIRACULOUS_HP = 1031   # end 50 → 252 stored (126 display) = 152 HP (end-only)
AVG_CGEN_HP = 50              # ~23 end display average across priority slots (no str bonus at cgen)
MAX_CGEN_HP = 68              # end 1st (85→42 display), str 2nd; no str bonus below 100

# Stat cap (min, max) per priority slot (1st = highest cap band, 7th = lowest). Narrow ranges so priority
# choice isn't invalidated by a bad roll; tanks (end+str 1st/2nd) are guaranteed to reach miraculous.
STAT_CAP_RANGES_BY_PRIORITY = [
    (270, 300),   # 1st: high band, 300 max available
    (263, 275),   # 2nd: high enough for miraculous with 1st
    (240, 262),   # 3rd
    (220, 239),   # 4th
    (200, 219),   # 5th
    (180, 199),   # 6th
    (160, 179),   # 7th: low narrow band
]


def _compute_stat_caps(order):
    """Generate 7 stat caps from priority-based ranges (0-300 scale). Not shown to player."""
    caps = [random.randint(lo, hi) for lo, hi in STAT_CAP_RANGES_BY_PRIORITY]
    return {stat: caps[i] for i, stat in enumerate(order)}


def _randomize_stats_from_priority(order):
    """Set starting stats from priority order: each stat gets a random value in its slot's range (beginner spread)."""
    stats = {}
    for i, stat in enumerate(order):
        lo, hi = STAT_RANDOM_RANGES_BY_PRIORITY[i]
        stats[stat] = random.randint(lo, hi)
    return stats




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
    name = (raw_string or "").strip()
    if len(name) < 2:
        caller.msg("|rName must be at least 2 characters.|n")
        return node_name(caller, "", **kwargs)
    if len(name) > 30:
        caller.msg("|rName must be 30 characters or fewer.|n")
        return node_name(caller, "", **kwargs)
    for c in name:
        if not (c.isalnum() or c in " -'"):
            caller.msg("|rOnly letters, numbers, spaces, hyphens, apostrophes are allowed in names.|n")
            return node_name(caller, "", **kwargs)
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
    text = (
        "|r── TRAIT EXTRACTION ──|n\n\n"
        "The Rite is not reading words. It is reading |rinstinct|n. The things that kept you alive when the Below tried to break you.\n\n"
        "You will give, in order, the traits that defined you — from most defining to least. The |Rorder|n matters.\n\n"
        "Stats (long → short): strength (str), perception (per), endurance (end), charisma (cha), intelligence (int), agility (agi), luck (lck).\n\n"
        "|R\"Speak them in order. Greatest to least. All seven.\"|n\n"
        "|xExample:|n str end agi per cha int lck"
    )
    options = [{"key": "_default", "goto": "node_apply_priority_order"}]
    return text, options


def node_apply_priority_order(caller, raw_string, **kwargs):
    """
    Free-input stat priority: user must enter all seven stats in order, e.g. 'str end agi per cha int lck'.
    We map abbrevs/long names to STAT_KEYS and preserve order. All seven must be given; no partial input.
    """
    raw = (raw_string or "").lower().replace(",", " ")
    tokens = [tok for tok in raw.split() if tok]
    if not tokens:
        caller.msg("|rEnter all seven stats from most important to least, e.g.: str end agi per cha int lck.|n")
        return node_priority_intro(caller, "", **kwargs)
    order = []
    for tok in tokens:
        full = STAT_ABBREVS.get(tok, tok)
        if full in STAT_KEYS and full not in order:
            order.append(full)
    if not order:
        caller.msg("|rNo valid stats found. Use stat names or abbrevs: str, per, end, cha, int, agi, lck.|n")
        return node_priority_intro(caller, "", **kwargs)
    if len(order) != len(STAT_KEYS) or set(order) != set(STAT_KEYS):
        missing = [s for s in STAT_KEYS if s not in order]
        abbrevs = [k for k, v in STAT_ABBREVS.items() if v in missing]
        caller.msg("|rYou must list all seven stats in order, greatest to least. Missing: %s. Example: str end agi per cha int lck|n" % ", ".join(abbrevs))
        return node_priority_intro(caller, "", **kwargs)
    caller.db.stat_caps = _compute_stat_caps(order)
    caller.db.stats = _randomize_stats_from_priority(order)
    text = "|r'SIGIL SEQUENCE COMPLETE.'|n\n\nProceeding to readout — then the |Rladder of marks|n."
    options = [{"desc": "|rContinue|n", "goto": "node_stats"}]
    return text, options


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
        "Confirm. Then the sigil will etch the |Rladder of marks|n — what you were, in order."
    ) % "\n".join(lines)
    options = [{"desc": "|rConfirm|n", "goto": "node_skills_intro"}]
    return text, options


# ==========================================
# SKILL ALLOCATION — Ladder of 6 Marks (Job / Hobbies / Basics)
# ==========================================

# Narrative copy for each tier (in-character; "grade" is background-type framing).
MARKS_TIER_INTRO = {
    "Job": (
        "|r── YOUR JOB ──|n\n\n"
        "|R\"The sigil reads what put food on the table. The thing you did when the shifts changed. "
        "Your |rjob|n — the skill that kept you in the system, or outside it.\"|n\n\n"
        "Choose |rone|n skill. This will be etched deepest."
    ),
    "Hobbies": (
        "|r── YOUR HOBBIES ──|n\n\n"
        "|R\"Next: what you did when nobody was watching. The things that kept you |rsane|n — "
        "or sharp. Side work. Fixes. The range. The deck. Two marks.\"|n\n\n"
        "Choose |rtwo|n skills. The sigil remembers what you did to stay human."
    ),
    "Basics": (
        "|r── THE BASICS ──|n\n\n"
        "|R\"Last: what everyone learns to survive down here. How to move. How to patch a wound. "
        "How to talk your way past a checkpoint. |rThree|n marks. The foundation.\"|n\n\n"
        "Choose |rthree|n skills. The minimum the undercity demands."
    ),
}


def node_skills_intro(caller, raw_string, **kwargs):
    caller.db.skills = getattr(caller.db, "skills", None) or {}
    caller.db.chargen_mark_tier_index = 0
    count, level, label = MARKS_LADDER[0]
    caller.db.chargen_mark_tier_picks_left = count
    text = (
        "|r── THE LADDER OF MARKS ──|n\n\n"
        "|R\"The sigil can etch |rskills|n into you. Not study — |rblood-memory|n. What you were, "
        "before the Rite. In order: the thing that defined your days, then what you did to stay alive in the gaps, "
        "then the basics every rat learns.\"|n\n\n"
        "You will place |R%d|n marks in three steps. Each step locks a layer of who you were.\n\n"
        "|R\"First: what was your job?\"|n"
    ) % CHARGEN_MARKS_TOTAL
    options = [{"desc": "|rContinue|n", "goto": "node_skills"}]
    return text, options


def node_skills(caller, raw_string, **kwargs):
    tier_index = int(getattr(caller.db, "chargen_mark_tier_index", 0) or 0)
    picks_left = int(getattr(caller.db, "chargen_mark_tier_picks_left", 0) or 0)
    skills = caller.db.skills or {}

    if tier_index >= len(MARKS_LADDER):
        return node_skills_done(caller, raw_string, **kwargs)

    count, tier_level, tier_label = MARKS_LADDER[tier_index]
    tier_level = min(tier_level, MAX_LEVEL)
    intro_text = MARKS_TIER_INTRO.get(tier_label, "")

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

    if picks_left <= 0:
        caller.db.chargen_mark_tier_index = tier_index + 1
        if tier_index + 1 < len(MARKS_LADDER):
            _, _, next_label = MARKS_LADDER[tier_index + 1]
            next_count = MARKS_LADDER[tier_index + 1][0]
            caller.db.chargen_mark_tier_picks_left = next_count
        return node_skills(caller, raw_string, **kwargs)

    pick_prompt = "Choose the skill that was |ryour job|n." if tier_label == "Job" else (
        "Choose skill %d of %d for |r%s|n." % (count - picks_left + 1, count, tier_label.lower())
    )
    text = (
        "%s\n\n"
        "Current etchings:\n"
        "%s\n\n"
        "%s"
    ) % (intro_text, "\n".join(skill_lines), pick_prompt)
    options = []
    for skill_key in SKILL_KEYS:
        cur = skills.get(skill_key, 0)
        if not isinstance(cur, int):
            cur = 0
        if cur < tier_level:
            name = SKILL_DISPLAY_NAMES.get(skill_key, skill_key.replace("_", " ").title())
            options.append({
                "desc": "|r%s|n" % name,
                "goto": ("node_apply_mark", {"skill": skill_key}),
            })
    options.append({
        "desc": "|xSkip to identity|n" if picks_left > 0 else "|rContinue to identity|n",
        "goto": "node_gender",
    })
    return text, options


def node_skills_done(caller, raw_string, **kwargs):
    """All 6 marks placed; show summary and go to identity."""
    skills = caller.db.skills or {}
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
        "|r'SIGIL ETCHING COMPLETE.'|n\n\n"
        "The ladder is fixed. Your job, your hobbies, your basics — locked in blood-memory.\n\n"
        "%s\n\n"
        "|R\"Now. How will the world name you?\"|n"
    ) % "\n".join(skill_lines)
    options = [{"desc": "|rContinue|n", "goto": "node_gender"}]
    return text, options


def node_apply_mark(caller, raw_string, **kwargs):
    """Apply one mark at the current tier level; advance picks; next tier if tier exhausted."""
    skill_key = kwargs.get("skill")
    if skill_key not in SKILL_KEYS:
        return node_skills(caller, raw_string, **kwargs)
    tier_index = int(getattr(caller.db, "chargen_mark_tier_index", 0) or 0)
    picks_left = int(getattr(caller.db, "chargen_mark_tier_picks_left", 0) or 0)
    if tier_index >= len(MARKS_LADDER) or picks_left <= 0:
        return node_skills(caller, raw_string, **kwargs)
    count, tier_level, tier_label = MARKS_LADDER[tier_index]
    tier_level = min(tier_level, MAX_LEVEL)
    skills = caller.db.skills or {}
    cur = skills.get(skill_key, 0)
    if not isinstance(cur, int):
        cur = 0
    if cur >= tier_level:
        return node_skills(caller, raw_string, **kwargs)
    if not caller.db.skills:
        caller.db.skills = {}
    caller.db.skills[skill_key] = tier_level
    caller.db.chargen_mark_tier_picks_left = picks_left - 1
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
    text = "|r'IDENTITY LOCKED.'|n\n\n|R\"How do you stand? Speak height and frame.\"|n\n\n" \
           "Examples: |x'tall heavy'|n, |x'short average'|n, |x'average thin'|n."
    options = [{"key": "_default", "goto": "node_apply_build_and_weight"}]
    return text, options


# Height category -> (min_cm, max_cm) for random assignment. Narrative choice only.
HEIGHT_RANGES_CM = {
    "short": (152, 165),
    "average": (166, 178),
    "tall": (180, 195),
}

# Weight category -> (min_kg, max_kg) for random assignment. Narrative choice only.
WEIGHT_RANGES_KG = {
    "thin": (45, 58),
    "average": (59, 82),
    "heavy": (83, 110),
}


def node_apply_build_and_weight(caller, raw_string, **kwargs):
    """
    Free-input build: player types e.g. 'tall heavy' or 'short average'.
    We parse height and weight words; any missing part defaults to 'average'.
    """
    import random

    raw = (raw_string or "").lower()
    tokens = [tok for tok in raw.replace(",", " ").split() if tok]
    height = None
    weight = None
    for tok in tokens:
        if tok in HEIGHT_RANGES_CM and height is None:
            height = tok
        if tok in WEIGHT_RANGES_KG and weight is None:
            weight = tok
    if not height and not weight:
        caller.msg("|rDescribe height and/or frame using: short/average/tall and thin/average/heavy.|n")
        caller.msg("|xExamples:|n tall heavy   short average   average thin")
        # Re-present prompt
        return node_apply_gender(caller, "", **kwargs)

    height_category = height or "average"
    weight_category = weight or "average"

    h_min, h_max = HEIGHT_RANGES_CM.get(height_category, (166, 178))
    w_min, w_max = WEIGHT_RANGES_KG.get(weight_category, (59, 82))

    caller.db.height_category = height_category
    caller.db.height_cm = random.randint(h_min, h_max)
    caller.db.weight_category = weight_category
    caller.db.weight_kg = random.randint(w_min, w_max)

    text = "|r'BUILD LOCKED.'|n\n\n|R\"The Rite is complete. Rise.\"|n"
    options = [{"desc": "|rFinalize|n", "goto": "node_finish"}]
    return text, options


# ==========================================
# FINISH
# ==========================================

def node_finish(caller, raw_string, **kwargs):
    caller.db.needs_chargen = False
    for attr in ("stat_points", "skill_points", "chargen_xp", "skill_chargen_xp", "chargen_marks_used", "chargen_mark_tier_index", "chargen_mark_tier_picks_left",):
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
