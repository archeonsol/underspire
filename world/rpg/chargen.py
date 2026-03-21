# world/chargen.py
#
# Gutterpunk / arcanepunk character generation.
# Occult Rite, blood-signs, marks. Dark / red UI.
# Skills awarded via marks. No XP spend at chargen.

import random

from evennia.objects.models import ObjectDB
from evennia.utils.evtable import EvTable
from evennia.utils import delay
from evennia.utils.evmenu import EvMenu
from evennia.utils.ansi import ANSIString
from evennia.utils.utils import wrap  # The secret to perfect ANSI-safe wrapping

from world.levels import MAX_LEVEL, MAX_STAT_LEVEL, level_to_letter
from world.skills import SKILL_KEYS, SKILL_DISPLAY_NAMES
from world.ui_utils import fade_rule

# ══════════════════════════════════════════════════════════════════════════════
# STAT DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════

STAT_KEYS = [
    "strength", "perception", "endurance",
    "charisma", "intelligence", "agility", "luck",
]
STAT_ABBREVS = {
    "str": "strength", "per": "perception", "end": "endurance",
    "cha": "charisma",  "int": "intelligence", "agi": "agility",
    "lck": "luck",
}
STAT_DISPLAY_NAMES = {
    "strength":     "Strength",
    "perception":   "Perception",
    "endurance":    "Endurance",
    "charisma":     "Charisma",
    "intelligence": "Intelligence",
    "agility":      "Agility",
    "luck":         "Luck",
}

# ══════════════════════════════════════════════════════════════════════════════
# GAME BALANCE CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

MARKS_LADDER = [
    (1, 105, "Job"),      # Grade E — primary skill
    (2,  81, "Hobbies"),  # Grade H — secondary skills
    (3,  52, "Basics"),   # Grade L — foundational skills
]
CHARGEN_MARKS_TOTAL = sum(n for n, _, _ in MARKS_LADDER)

STAT_RANDOM_RANGES_BY_PRIORITY = [
    (35, 50), (25, 35), (15, 25), (10, 15), (5, 10), (2, 5), (0, 2),
]
STAT_CAP_RANGES_BY_PRIORITY = [
    (270, 300), (263, 275), (240, 262), (220, 239),
    (200, 219), (180, 199), (160, 179),
]

# ══════════════════════════════════════════════════════════════════════════════
# FLAVOR COPY
# ══════════════════════════════════════════════════════════════════════════════

STAT_PRIORITY_BLURB = {
    "strength":     "|wstr|n  Load-muscle. Carrying what breaks others. The tunnels, the floods, the dead weight.",
    "perception":   "|wper|n  Exits first, hands second, eyes third. The gap between a sound and a threat.",
    "endurance":    "|wend|n  The undercity specializes in attrition. You outlasted things that ended others.",
    "charisma":     "|wcha|n  Weight, not charm. People stop before they've decided to. Sometimes that's enough.",
    "intelligence": "|wint|n  The right question at the wrong time kills you. You learned when not to ask.",
    "agility":      "|wagi|n  The maintenance ducts aren't built for bodies. You learned to use them anyway.",
    "luck":         "|wlck|n  The ceiling held. The Inquisitor's eyes slid past. You've never learned to rely on it.",
}

MARKS_TIER_INTRO = {
    "Job": (
        "|R\"What kept you fed. The skill you showed up with when the shift changed "
        "and you needed a reason to be there. Not ambition — practice. "
        "What you were.\"|n\n\n"
        "|xChoose |Rone|x skill. This mark cuts deepest.|n"
    ),
    "Hobbies": (
        "|R\"The work you did when no one was counting. What you kept doing "
        "after the quota was met — in the maintenance corridors, in the hours "
        "between. Two marks. The Rite reads repetition.\"|n\n\n"
        "|xChoose |Rtwo|x skills.|n"
    ),
    "Basics": (
        "|R\"What the undercity eventually teaches everyone. How to move without "
        "sound. How to close a wound with what's available. How to make a face "
        "that doesn't say what you're thinking. Three marks. The floor.\"|n\n\n"
        "|xChoose |Rthree|x skills.|n"
    ),
}

HEIGHT_RANGES_CM = {"short": (152, 165), "average": (166, 178), "tall": (180, 195)}
WEIGHT_RANGES_KG = {"thin": (45, 58), "average": (59, 82), "heavy": (83, 110)}
# Player characters must be adults; upper bound keeps input plausible.
CHARGEN_MIN_AGE = 18
CHARGEN_MAX_AGE = 120

_CHARGEN_TEMP_ATTRS = (
    "stat_points", "skill_points", "chargen_xp", "skill_chargen_xp",
    "chargen_marks_used", "chargen_mark_tier_index", "chargen_mark_tier_picks_left",
    "stat_priority_order",
)

_BLOCKED_MENU_ESCAPES = {"q", "quit", "exit", "@quit", "@q", "logout", "disconnect"}


def _is_blocked_menu_escape(raw_string: str) -> bool:
    return (raw_string or "").strip().lower() in _BLOCKED_MENU_ESCAPES


def _parse_skintone_menu_input(raw_string: str):
    """
    If input mirrors the @skintone command (EvMenu does not run cmdsets on nodes),
    return ("palette",) to show the list, or ("choose", arg) to set from arg.
    Otherwise return None.
    """
    s = (raw_string or "").strip()
    if not s:
        return None
    parts = s.split(None, 1)
    head = parts[0].lower()
    if head not in ("@skintone", "skintone"):
        return None
    if len(parts) == 1:
        return ("palette",)
    return ("choose", parts[1].strip())


# ══════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ══════════════════════════════════════════════════════════════════════════════

_UI_WIDTH  = 72
_BAR_WIDTH = 14  

_GRADE_COLORS = {
    "S": "|Y", "A": "|G", "B": "|g", "C": "|c",
    "D": "|w", "E": "|W", "F": "|x", "H": "|w", "L": "|x", "-": "|x",
}

def _grade_color(letter: str) -> str:
    return _GRADE_COLORS.get(letter.upper(), "|w")

def _bar(value: int, max_val: int = MAX_STAT_LEVEL, width: int = 10) -> str:
    """Flexible width progress bar."""
    if max_val <= 0:
        return "|x" + "░" * width + "|n"
    filled = max(0, min(width, int(round(value / max_val * width))))
    empty  = width - filled
    ratio  = filled / width if width else 0
    color  = "|r" if ratio > 0.65 else ("|R" if ratio > 0.30 else "|x")
    return color + "▓" * filled + "|x" + "░" * empty + "|n"

def _shorten_skill(name: str) -> str:
    """Safely abbreviates long skill names to prevent table line-wrapping."""
    name = name.replace("Mechanical Engineering", "Mech Engineer")
    name = name.replace("Electrical Engineering", "Elec Engineer")
    name = name.replace("Systems Security", "Sys Security")
    name = name.replace("Arms & Armor Tech", "Arms & Armor")
    return name[:13] # Force truncation at 13 characters just to be safe


def _slab(title: str, text: str, status: str = None, width: int = _UI_WIDTH) -> str:
    """
    Auto-wrapping bordered narrative panel. Passes text through Evennia's 
    ANSI-aware wrap function so it never bleeds out of the box, while respecting
    explicit manual line breaks and preserving indentations on short lines.
    """
    inner = width - 4 
    out   = []

    raw_title = f" [ {title} ] "
    pad_total = width - 2 - len(raw_title)
    pad_l     = pad_total // 2
    pad_r     = pad_total - pad_l
    # Render only the left border of the panel to avoid right-panel misalignment.
    out.append(f"|r╔{'═' * pad_l}|R{raw_title}|r{fade_rule(pad_r, '═')}|n")

    # Split by SINGLE newline to respect explicit manual line breaks
    explicit_lines = text.split("\n")
    for line in explicit_lines:
        if not line.strip():
            # Preserve intentional blank lines
            empty_pad = ANSIString("  ").ljust(inner + 2)
            out.append(f"|r║|n{empty_pad}")
        else:
            ansi_line = ANSIString(line)
            if len(ansi_line) <= inner:
                # THE SECRET SAUCE: If it fits perfectly, SKIP wrapping to keep your exact spaces!
                padded = ANSIString(f"  {line}").ljust(inner + 2)
                out.append(f"|r║|n{padded}")
            else:
                # If it's too long, wrap it, and SPLIT THE STRING into a list!
                wrapped_string = wrap(line, width=inner)
                for w_line in wrapped_string.split("\n"):
                    padded = ANSIString(f"  {w_line}").ljust(inner + 2)
                    out.append(f"|r║|n{padded}")

    if status:
        out.append(f"|r╠{fade_rule(width - 2, '─')}|n")
        status_padded = ANSIString(f"  |r>>|n |x{status}|n").ljust(inner + 2)
        out.append(f"|r║|n{status_padded}")

    out.append(f"|r╚{fade_rule(width - 2, '═')}|n")
    return "\n".join(out)


def _render_ladder(caller) -> str:
    tier_idx   = int(getattr(caller.db, "chargen_mark_tier_index",    0) or 0)
    picks_left = int(getattr(caller.db, "chargen_mark_tier_picks_left", 0) or 0)
    rows = []
    for i, (total_picks, _level, label) in enumerate(MARKS_LADDER):
        if i < tier_idx:
            made = total_picks
        elif i == tier_idx:
            made = total_picks - picks_left
        else:
            made = 0
        blocks = []
        for p in range(total_picks):
            blocks.append("|R▓▓▓▓|n" if p < made else "|x░░░░|n")
        rows.append(f"  |w{label:<9}|n {' '.join(blocks)}")
    return "\n".join(rows)


# We shrink the bar slightly so two columns can comfortably fit side-by-side in a 72-char terminal
_BAR_WIDTH = 10  

# Shrunk slightly to give the text columns enough room to fit long words
_BAR_WIDTH = 7  

def _stat_table(caller, stats: dict) -> str:
    tbl = EvTable(
        "|xTrait|n", "|xGr|n", "|xPower|n",
        "|xTrait|n", "|xGr|n", "|xPower|n", 
        border="cells", border_color="r",
    )
    tbl.reformat_column(0, width=14, align="l") 
    tbl.reformat_column(1, width=4,  align="c") 
    tbl.reformat_column(2, width=14, align="l") # 10 char bar + 4 padding
    tbl.reformat_column(3, width=14, align="l") 
    tbl.reformat_column(4, width=4,  align="c") 
    tbl.reformat_column(5, width=14, align="l") 
    
    items = list(STAT_DISPLAY_NAMES.items())
    
    for i in range(0, len(items), 2):
        row_data = []
        
        # --- LEFT COLUMN DATA ---
        k1, n1 = items[i]
        cur1   = stats.get(k1, 0) or 0
        let1   = level_to_letter(cur1, MAX_STAT_LEVEL)
        row_data.extend([f"|w{n1}|n", f"{_grade_color(let1)}{let1}|n", _bar(cur1, MAX_STAT_LEVEL, width=10)])
        
        # --- RIGHT COLUMN DATA ---
        if i + 1 < len(items):
            k2, n2 = items[i + 1]
            cur2   = stats.get(k2, 0) or 0
            let2   = level_to_letter(cur2, MAX_STAT_LEVEL)
            row_data.extend([f"|w{n2}|n", f"{_grade_color(let2)}{let2}|n", _bar(cur2, MAX_STAT_LEVEL, width=10)])
        else:
            row_data.extend(["", "", ""])
            
        tbl.add_row(*row_data)
        
    return str(tbl)


def _skill_table(skills: dict) -> str:
    """
    8-Column grid that includes selection numbers, completely eliminating 
    the need for EvMenu to print a massive list at the bottom.
    """
    def _compact_line(idx: int, skey: str) -> str:
        name = _shorten_skill(SKILL_DISPLAY_NAMES.get(skey, skey.replace("_", " ").title()))
        cur = skills.get(skey, 0) or 0
        letter = level_to_letter(cur, MAX_LEVEL) if cur else "-"
        bar = _bar(cur, MAX_LEVEL, width=5) if cur else "|x░░░░░|n"
        return f"|y{idx:>2}|n |w{name:<15}|n {_grade_color(letter)}{letter}|n {bar}"

    try:
        tbl = EvTable(
            "|x#|n", "|xSkill|n", "|xGr|n", "|xProf|n",
            "|x#|n", "|xSkill|n", "|xGr|n", "|xProf|n",
            border="cells", border_color="r",
        )
        # The math here totals exactly 72 characters wide with borders included
        tbl.reformat_column(0, width=4, align="r")
        tbl.reformat_column(1, width=15, align="l")
        tbl.reformat_column(2, width=4,  align="c")
        tbl.reformat_column(3, width=9,  align="l")  # 5 char bar + 4 padding
        tbl.reformat_column(4, width=4, align="r")
        tbl.reformat_column(5, width=15, align="l")
        tbl.reformat_column(6, width=4,  align="c")
        tbl.reformat_column(7, width=9,  align="l")

        for i in range(0, len(SKILL_KEYS), 2):
            row_data = []

            # --- LEFT COLUMN ---
            sk1 = SKILL_KEYS[i]
            id1 = i + 1
            name1 = _shorten_skill(SKILL_DISPLAY_NAMES.get(sk1, sk1.replace("_", " ").title()))
            cur1 = skills.get(sk1, 0) or 0
            let1 = level_to_letter(cur1, MAX_LEVEL) if cur1 else "-"
            bar1 = _bar(cur1, MAX_LEVEL, width=5) if cur1 else f"|x░░░░░|n"
            row_data.extend([f"|y{id1}|n", f"|w{name1}|n", f"{_grade_color(let1)}{let1}|n", bar1])

            # --- RIGHT COLUMN ---
            if i + 1 < len(SKILL_KEYS):
                sk2 = SKILL_KEYS[i + 1]
                id2 = i + 2
                name2 = _shorten_skill(SKILL_DISPLAY_NAMES.get(sk2, sk2.replace("_", " ").title()))
                cur2 = skills.get(sk2, 0) or 0
                let2 = level_to_letter(cur2, MAX_LEVEL) if cur2 else "-"
                bar2 = _bar(cur2, MAX_LEVEL, width=5) if cur2 else f"|x░░░░░|n"
                row_data.extend([f"|y{id2}|n", f"|w{name2}|n", f"{_grade_color(let2)}{let2}|n", bar2])
            else:
                row_data.extend(["", "", "", ""])

            tbl.add_row(*row_data)

        return str(tbl)
    except Exception:
        # Narrow clients can force EvTable to collapse below minimum cell width.
        # Fall back to a simple, non-tabular renderer instead of crashing chargen.
        lines = ["|x# Skill            Gr Prof|n"]
        for idx, skey in enumerate(SKILL_KEYS, start=1):
            lines.append(_compact_line(idx, skey))
        return "\n".join(lines)
# ──────────────────────────────────────────────────────────────────────────────
# Stat generation
# ──────────────────────────────────────────────────────────────────────────────

def _compute_stat_caps(order: list) -> dict:
    caps = [random.randint(lo, hi) for lo, hi in STAT_CAP_RANGES_BY_PRIORITY]
    return {stat: caps[i] for i, stat in enumerate(order)}

def _randomize_stats(order: list) -> dict:
    stats = {}
    for i, stat in enumerate(order):
        lo, hi = STAT_RANDOM_RANGES_BY_PRIORITY[i]
        stats[stat] = random.randint(lo, hi)
    return stats

def _count_marks_placed(skills: dict) -> int:
    return sum(1 for v in (skills or {}).values() if isinstance(v, int) and v > 0)


# ══════════════════════════════════════════════════════════════════════════════
# CINEMATIC LAUNCHER 
# ══════════════════════════════════════════════════════════════════════════════

def start_cinematic_chargen(caller):
    def _send(msg):
        caller.msg(msg)

    caller.msg(play_music="/static/media/thegrid.ogg")

    caller.msg("\033[2J\033[H")

    delay(0.5,  lambda: _send("\n|xThe stone holds heat it should not have.|n"))
    delay(3.0,  lambda: _send(
        "\n|xYou were not brought here. You arrived.|n\n"
        "|xThere is a difference — the Rite already knows which.|n"
    ))
    delay(6.5,  lambda: _send(
        "\n|xAbove you: something burning that is not a candle.|n\n"
        "|xAround you: grooves cut into the rock in a pattern you almost recognize.|n"
    ))
    delay(10.0, lambda: _send(
        "\n|xA hand enters your field of vision. Waiting. Not reaching.|n\n"
        "|xIt has done this before. Many times.|n"
    ))
    delay(13.5, lambda: _send(
        "\n|R\"The name the Authority gave you is already ash.|n\n"
        "|R Speak the other one.\"|n"
    ))
    delay(17.0, lambda: _send(
        "\n|xYou have been in this room before.|n\n"
        "|xYou just don't remember it yet.|n\n"
    ))
    # Keep the ritual non-escapable from menu commands like `quit`.
    delay(19.5, lambda: EvMenu(caller, "world.chargen", startnode="node_name", auto_quit=False))


# ══════════════════════════════════════════════════════════════════════════════
# CHARGEN MENU NODES
# ══════════════════════════════════════════════════════════════════════════════

def node_start(caller, raw_string="", **kwargs):
    return node_name(caller, raw_string=raw_string, **kwargs)

def node_name(caller, raw_string="", **kwargs):
    text_body = (
        "|xThe figure doesn't ask. It waits — which implies certainty.\n"
        "That a name is coming. That you have one ready.\n"
        "That the only question is when you'll say it out loud.|n\n\n"
        "|xYour ration-card name is already gone. That one belonged to the system.\n"
        "This one belongs to the blood.|n\n\n"
        "|R\"Speak the name. The one the Below will know.\"|n\n\n"
        "|x(2–30 characters: letters, numbers, spaces, hyphens, apostrophes)|n"
    )
    text    = _slab("BLOOD-SIGN", text_body, status="INPUT REQUIRED")
    options = [{"key": "_default", "goto": "node_apply_name"}]
    return text, options

def node_apply_name(caller, raw_string, **kwargs):
    if _is_blocked_menu_escape(raw_string):
        caller.msg("\n|r[!] You cannot leave during the Rite. Complete character creation.|n\n")
        return node_name(caller)

    name = (raw_string or "").strip().title()

    if len(name) < 2:
        caller.msg("\n|r[!] The sigil rejects this — too short. Speak a true name.|n\n")
        return node_name(caller)
    if len(name) > 30:
        caller.msg("\n|r[!] The sigil rejects this — too long. Thirty characters or fewer.|n\n")
        return node_name(caller)
    for ch in name:
        if not (ch.isalnum() or ch in " -'"):
            caller.msg("\n|r[!] The sigil rejects those characters. Letters, numbers, spaces, hyphens, apostrophes.|n\n")
            return node_name(caller)

    existing = ObjectDB.objects.filter(
        db_key__iexact=name,
        db_typeclass_path="typeclasses.characters.Character",
    ).exclude(id=caller.id)
    if existing.exists():
        caller.msg("\n|r[!] That name is already claimed. Choose another.|n\n")
        return node_name(caller)

    caller.key = name
    if hasattr(caller, "aliases") and caller.aliases:
        try:
            caller.aliases.add(name)
        except Exception:
            pass

    return node_intro_lore(caller, raw_string, **kwargs)

def node_intro_lore(caller, raw_string="", **kwargs):
    text_body = (
        "|xThe colony runs on recycled air and the bodies of people "
        "who didn't make it through the filters. The Authority manages both.|n\n\n"
        "|xAbove the sealed gates: the Scar. What the Collapse made of the surface — "
        "topsoil that metabolized the wrong way, a sky that poisons on contact, "
        "things that adapted to conditions no longer called living.|n\n\n"
        "|xDown here, the law is a uniform and a willingness to use it "
        "before you've finished asking. The |RInquisition|x is quieter. "
        "They don't carry weapons to the door. The ones they take "
        "don't have time to see what they carry instead.|n\n\n"
        "|xYou are here because you ran out of other rooms. "
        "Or because something found you that you haven't named yet.|n\n\n"
        "|R\"Continue. The next mark is not where you came from. It's what you are.\"|n"
    )
    text    = _slab("THE PACT", text_body, status=f"IDENTITY LOGGED: {caller.key.upper()}")
    options = [{"desc": "|rContinue|n", "goto": "node_race"}]
    return text, options


def node_race(caller, raw_string="", **kwargs):
    text_body = (
        "|xThe sigil deepens. The grooves in the stone are reading "
        "something older than skill or origin — the shape of the body "
        "itself. What was built. What was modified. What was inherited "
        "from a program that ended before you were born.|n\n\n"
        "|R\"What are you? Not who. What.\"|n"
    )
    text = _slab("THE VESSEL", text_body, status="VESSEL CLASSIFICATION REQUIRED")
    options = [
        {"desc": "  |wHuman|n\n     Unmodified baseline. The template the colony was built for.", "goto": ("node_apply_race", {"race": "human"})},
        {
            "desc": "  |wSplicer|n\n     Gene-spliced with animal DNA. The program ended.\n     The modifications didn't.",
            "goto": ("node_apply_race", {"race": "splicer"}),
        },
    ]
    return text, options


def node_apply_race(caller, raw_string="", **kwargs):
    race = (kwargs.get("race") or "human").strip().lower()
    if race not in ("human", "splicer"):
        race = "human"
    caller.db.race = race
    if race == "human":
        caller.db.splicer_animal = None
        return node_priority_intro(caller)
    bd = dict(getattr(caller.db, "body_descriptions", None) or {})
    bd.setdefault("tail", "")
    caller.db.body_descriptions = bd
    caller.msg(
        "|xWhen you set your short description (|w@sdesc|x), consider including your "
        "splice features. The world sees them before it sees you.|n"
    )
    return node_splicer_animal(caller)


def node_splicer_animal(caller, raw_string="", **kwargs):
    text_body = (
        "|xThe Rite reads the other helix — the one that wasn't human "
        "to begin with. Somewhere in the sequence, a donor species. "
        "The program's records are sealed. The body remembers anyway.|n\n\n"
        "|R\"What did they put in you? Name the animal.\"|n\n\n"
        "|x(Type the animal name. One word or two. Examples: wolf, cat, "
        "crow, shark, gecko, rat, mantis, octopus)|n"
    )
    text = _slab("SPLICE ORIGIN", text_body, status="SPLICE DONOR SPECIES REQUIRED")
    options = [{"key": "_default", "goto": "node_apply_splicer_animal"}]
    return text, options


def node_apply_splicer_animal(caller, raw_string, **kwargs):
    if _is_blocked_menu_escape(raw_string):
        caller.msg("\n|r[!] You cannot leave during the Rite. Complete character creation.|n\n")
        return node_splicer_animal(caller)
    raw = (raw_string or "").strip()
    if len(raw) < 2:
        caller.msg("\n|r[!] Too short. Two characters minimum.|n\n")
        return node_splicer_animal(caller)
    if len(raw) > 30:
        caller.msg("\n|r[!] Too long. Thirty characters maximum.|n\n")
        return node_splicer_animal(caller)
    for ch in raw:
        if not (ch.isalpha() or ch == " "):
            caller.msg("\n|r[!] Letters and spaces only.|n\n")
            return node_splicer_animal(caller)
    caller.db.splicer_animal = " ".join(raw.lower().split())
    return node_priority_intro(caller)


def node_priority_intro(caller, raw_string="", **kwargs):
    # --- THE FIX: We changed "\n" to "\n\n" right here ---
    blurb_lines = "\n\n".join([f"|x{b}|n" for b in STAT_PRIORITY_BLURB.values()])
    
    text_body = (
        "|xThe Rite doesn't ask what you know. Knowledge is catalogueable, "
        "transferable, drillable. The Rite asks what you survived. "
        "Survival leaves a different mark — the kind that moves before thought, "
        "that's already decided before you know you're deciding.|n\n\n"
        "|xRank them. Not what you hope you are. What the last decade already proved.|n\n\n"
        f"{blurb_lines}\n\n"
        "|R\"Speak them in order. Greatest to least. All seven.\"|n\n\n"
        "|x  Example:|n  |wstr end agi per cha int lck|n\n"
        "|x  (Full names or abbreviations accepted.)|n"
    )
    text    = _slab("TRAIT EXTRACTION", text_body, status="AWAITING SEVEN-POINT SEQUENCE")
    options = [{"key": "_default", "goto": "node_apply_priority_order"}]
    return text, options

def node_apply_priority_order(caller, raw_string, **kwargs):
    if _is_blocked_menu_escape(raw_string):
        caller.msg("\n|r[!] You cannot leave during the Rite. Complete character creation.|n\n")
        return node_priority_intro(caller)

    raw    = (raw_string or "").lower().replace(",", " ")
    tokens = [t for t in raw.split() if t]
    order  = []
    for tok in tokens:
        full = STAT_ABBREVS.get(tok) or (tok if tok in STAT_KEYS else None)
        if full and full not in order:
            order.append(full)

    if not order:
        caller.msg("\n|r[!] No valid stats found. Use: str per end cha int agi lck|n\n")
        return node_priority_intro(caller)

    if len(order) != len(STAT_KEYS) or set(order) != set(STAT_KEYS):
        missing     = [s for s in STAT_KEYS if s not in order]
        miss_abbrev = [k for k, v in STAT_ABBREVS.items() if v in missing]
        caller.msg(f"\n|r[!] All seven required. Missing: {', '.join(miss_abbrev)}|n\n")
        return node_priority_intro(caller)

    caller.db.stat_priority_order = order
    caller.db.stat_caps           = _compute_stat_caps(order)
    caller.db.stats               = _randomize_stats(order)

    text_body = (
        "|xSequence accepted. The blood has settled.|n\n\n"
        "|xProceeding to readout.|n"
    )
    text    = _slab("SEQUENCE ACCEPTED", text_body, status="CALCULATING POTENTIAL")
    options = [{"desc": "|rView Readout|n", "goto": "node_stats"}]
    return text, options

def node_stats(caller, raw_string="", **kwargs):
    stats = caller.db.stats or {}
    
    text_body = (
        "|xThe Rite reads, not assigns. These are not figures the system invented. "
        "This is what you've already become, rendered back to you.|n"
    )
    header = _slab("SIGIL READOUT", text_body, status="AWAITING CONFIRMATION")
    table  = _stat_table(caller, stats)

    text    = f"{header}\n\n{table}"
    options = [{"desc": "|rConfirm — proceed to marks|n", "goto": "node_skills_intro"}]
    return text, options

def node_skills_intro(caller, raw_string="", **kwargs):
    caller.db.skills                       = caller.db.skills or {}
    caller.db.chargen_mark_tier_index      = 0
    caller.db.chargen_mark_tier_picks_left = MARKS_LADDER[0][0]

    text_body = (
        "|xSkills aren't trained in the Rite. They're recovered. "
        "The blood-memory reads what you already did — the years before "
        "this room, the work and the survival and the things you did "
        "when there was no other option.|n\n\n"
        "|xThe Rite doesn't teach you. It remembers for you.|n\n\n"
        f"|xYou will place |R{CHARGEN_MARKS_TOTAL} marks|x in three steps. "
        "Each step locks a layer of who you were.|n"
    )
    text    = _slab("THE LADDER OF MARKS", text_body, status="ETCHING ROUTINE STANDBY")
    options = [{"desc": "|rBegin Etching|n", "goto": "node_skills"}]
    return text, options

def node_skills(caller, raw_string="", **kwargs):
    tier_index = int(getattr(caller.db, "chargen_mark_tier_index",    0) or 0)
    picks_left = int(getattr(caller.db, "chargen_mark_tier_picks_left", 0) or 0)
    skills     = caller.db.skills or {}

    if picks_left <= 0:
        tier_index += 1
        caller.db.chargen_mark_tier_index = tier_index
        if tier_index < len(MARKS_LADDER):
            caller.db.chargen_mark_tier_picks_left = MARKS_LADDER[tier_index][0]
            picks_left = MARKS_LADDER[tier_index][0]
        else:
            return node_skills_done(caller, raw_string, **kwargs)

    if tier_index >= len(MARKS_LADDER):
        return node_skills_done(caller, raw_string, **kwargs)

    count, tier_level, tier_label = MARKS_LADDER[tier_index]
    
    if picks_left == count:
        intro_text = MARKS_TIER_INTRO.get(tier_label, "") + "\n\n"
    else:
        intro_text = ""

    ladder = _render_ladder(caller)
    tbl    = _skill_table(skills)
    
    # Custom prompt instead of EvMenu options
    pick_num = count - picks_left + 1
    prompt_action = f"your job" if tier_label == "Job" else f"skill {pick_num} of {count}"
    pick_prompt = f"  |r>>|n Choose {prompt_action}. Type a number |w(1-{len(SKILL_KEYS)})|n or |w'skip'|n."
    
    header = f"{intro_text}{ladder}"
    text   = f"{header}\n\n{tbl}\n\n{pick_prompt}"

    # We return a single default option to suppress the massive EvMenu list
    options = [{"key": "_default", "goto": "node_apply_mark"}]
    return text, options


def node_apply_mark(caller, raw_string="", **kwargs):
    if _is_blocked_menu_escape(raw_string):
        caller.msg("\n|r[!] You cannot leave during the Rite. Complete character creation.|n\n")
        return node_skills(caller, raw_string, **kwargs)

    raw = (raw_string or "").strip().lower()
    tier_index = int(getattr(caller.db, "chargen_mark_tier_index",    0) or 0)
    picks_left = int(getattr(caller.db, "chargen_mark_tier_picks_left", 0) or 0)

    # Handle skipping
    if raw in ("skip", "done", "continue", "0"):
        if picks_left <= 0:
            return node_skills(caller, raw_string, **kwargs)
        else:
            caller.db.chargen_mark_tier_picks_left = 0
            return node_skills(caller, raw_string, **kwargs)

    # Parse the typed number
    try:
        choice = int(raw)
        if choice < 1 or choice > len(SKILL_KEYS):
            raise ValueError
        skill_key = SKILL_KEYS[choice - 1]
    except ValueError:
        caller.msg("\n|r[!] Invalid choice. Enter a number from the table, or 'skip'.|n\n")
        return node_skills(caller, raw_string, **kwargs)

    count, tier_level, tier_label = MARKS_LADDER[tier_index]
    skills = caller.db.skills or {}
    cur    = skills.get(skill_key, 0) or 0

    if cur >= tier_level:
        caller.msg("\n|r[!] That skill is already etched to this depth.|n\n")
        return node_skills(caller, raw_string, **kwargs)

    if not caller.db.skills:
        caller.db.skills = {}
        
    caller.db.skills[skill_key] = tier_level
    caller.db.chargen_mark_tier_picks_left = picks_left - 1
    return node_skills(caller, raw_string, **kwargs)

def node_skills_done(caller, raw_string="", **kwargs):
    ladder = _render_ladder(caller)
    tbl    = _skill_table(caller.db.skills or {})

    text_body = (
        "|xThe ladder is fixed. Your job, your hobbies, your basics — locked in blood-memory.\n"
        "The Rite doesn't forget. Neither will you.|n"
    )
    header  = _slab("ETCHING COMPLETE", text_body, status="SAVING NEURAL PATHWAYS")
    text    = f"{header}\n\n{ladder}\n\n{tbl}\n"
    options = [{"desc": "|rProceed to Identity|n", "goto": "node_gender"}]
    return text, options

# ─── Identity ─────────────────────────────────────────────────────────────────

def node_gender(caller, raw_string="", **kwargs):
    text_body = (
        "|R\"How will the world name you? The sigil needs a pronoun — not a definition. "
        "A handle. The word the logs will use when they find you.\"|n\n\n"
        "  |wMale|n      →  he / his / him\n"
        "  |wFemale|n    →  she / her / her\n"
        "  |wNonbinary|n →  they / their / them"
    )
    text    = _slab("THE HANDLE", text_body, status="PRONOUN IDENTIFIER REQUIRED")
    options = [
        {"desc": "  |wMale|n",      "goto": ("node_apply_gender", {"gender": "male"})},
        {"desc": "  |wFemale|n",    "goto": ("node_apply_gender", {"gender": "female"})},
        {"desc": "  |wNonbinary|n", "goto": ("node_apply_gender", {"gender": "nonbinary"})},
    ]
    return text, options

def node_apply_gender(caller, raw_string="", **kwargs):
    caller.db.gender  = kwargs.get("gender", "nonbinary")
    caller.db.pronoun = caller.db.gender
    return node_age(caller)


def node_age(caller, raw_string="", **kwargs):
    text_body = (
        "|R\"The Rite marks time. How many years has this body walked the world?\"|n\n\n"
        f"|xEnter your age in |wyears|x (whole number). Minimum age is |w{CHARGEN_MIN_AGE}|x.|n"
    )
    text = _slab("THE MEASURE", text_body, status="AGE REQUIRED")
    options = [{"key": "_default", "goto": "node_apply_age"}]
    return text, options


def node_apply_age(caller, raw_string, **kwargs):
    if _is_blocked_menu_escape(raw_string):
        caller.msg("\n|r[!] You cannot leave during the Rite. Complete character creation.|n\n")
        return node_age(caller)
    raw = (raw_string or "").strip()
    if not raw.isdigit():
        caller.msg("\n|r[!] Enter a whole number of years (e.g. 28).|n\n")
        return node_age(caller)
    age = int(raw)
    if age < CHARGEN_MIN_AGE:
        caller.msg(f"\n|r[!] Minimum age is {CHARGEN_MIN_AGE}.|n\n")
        return node_age(caller)
    if age > CHARGEN_MAX_AGE:
        caller.msg(f"\n|r[!] Enter a believable age ({CHARGEN_MIN_AGE}–{CHARGEN_MAX_AGE} years).|n\n")
        return node_age(caller)
    caller.db.age_years = age
    return node_build_prompt(caller)


def node_build_prompt(caller, raw_string="", **kwargs):
    text_body = (
        "|R\"Last entry. The physical record. "
        "What the world sees before it decides what you are.\"|n\n\n"
        "  Height:  |wshort|n   |waverage|n   |wtall|n\n"
        "  Frame:   |wthin|n    |waverage|n   |wheavy|n\n\n"
        "  |xExample:|n  tall heavy  ·  short average  ·  average thin"
    )
    text    = _slab("PHYSICALITY", text_body, status="AWAITING BUILD PARAMETERS")
    options = [{"key": "_default", "goto": "node_apply_build"}]
    return text, options

def node_apply_build(caller, raw_string, **kwargs):
    if _is_blocked_menu_escape(raw_string):
        caller.msg("\n|r[!] You cannot leave during the Rite. Complete character creation.|n\n")
        return node_build_prompt(caller)

    raw    = (raw_string or "").lower()
    tokens = [t for t in raw.replace(",", " ").split() if t]
    height = next((t for t in tokens if t in HEIGHT_RANGES_CM), None)
    weight = next((t for t in tokens if t in WEIGHT_RANGES_KG), None)

    if not height and not weight:
        caller.msg("\n|r[!] Use height (short/average/tall) and/or frame (thin/average/heavy).|n\n")
        return node_build_prompt(caller)

    h_cat = height or "average"
    w_cat = weight or "average"
    h_min, h_max = HEIGHT_RANGES_CM[h_cat]
    w_min, w_max = WEIGHT_RANGES_KG[w_cat]

    caller.db.height_category = h_cat
    caller.db.height_cm       = random.randint(h_min, h_max)
    caller.db.weight_category = w_cat
    caller.db.weight_kg       = random.randint(w_min, w_max)

    text_body = (
        "|R\"The Rite is complete. Rise.\"|n\n\n"
        f"  |x{h_cat.capitalize()} · {w_cat}|n  →  |w{caller.db.height_cm} cm  /  {caller.db.weight_kg} kg|n"
    )
    text    = _slab("BUILD LOCKED", text_body, status="RITUAL FINALIZATION READY")
    options = [{"desc": "|rContinue|n", "goto": "node_skin_tone"}]
    return text, options


def node_skin_tone(caller, raw_string="", **kwargs):
    text_body = (
        "|xThe last thing the Rite remembers is flesh — what color the blood paints under light.|n\n\n"
        "|xSpeak your skin tone |Ronce|x (see |w@skintone|x for the full palette), "
        "or type |wskip|x to choose later with |w@skintone|x.|n"
    )
    text = _slab("FLESH", text_body, status="SKIN TONE")
    options = [{"key": "_default", "goto": "node_apply_skin_tone"}]
    return text, options


def node_apply_skin_tone(caller, raw_string, **kwargs):
    if _is_blocked_menu_escape(raw_string):
        caller.msg("\n|r[!] You cannot leave during the Rite. Complete character creation.|n\n")
        return node_skin_tone(caller)

    raw = (raw_string or "").strip().lower()
    if raw in ("skip", "none", ""):
        return node_finish(caller)

    from world.skin_tones import (
        format_skintone_display,
        resolve_skin_tone_key,
        set_character_skin_tone,
    )

    sk = _parse_skintone_menu_input(raw_string)
    if sk:
        if sk[0] == "palette":
            caller.msg(format_skintone_display(caller))
            return node_skin_tone(caller)
        raw_string = sk[1]

    key = resolve_skin_tone_key(raw_string.strip())
    if not key:
        caller.msg("\n|r[!] That tone is not in the list. Use @skintone to see names, or type skip.|n\n")
        return node_skin_tone(caller)
    err = set_character_skin_tone(caller, key)
    if err:
        caller.msg("\n|r[!] That tone is not available.|n\n")
        return node_skin_tone(caller)
    return node_finish(caller)


# ─── Finish ───────────────────────────────────────────────────────────────────

def node_finish(caller, raw_string="", **kwargs):
    caller.msg(stop_music=True)
    caller.db.needs_chargen = False
    for attr in _CHARGEN_TEMP_ATTRS:
        if getattr(caller, "attributes", None) and caller.attributes.has(attr):
            try:
                caller.attributes.remove(attr)
            except Exception:
                pass

    stats         = caller.db.stats or {}
    skills        = caller.db.skills or {}
    race_key      = (getattr(caller.db, "race", None) or "human").lower()
    if race_key == "splicer":
        animal = (getattr(caller.db, "splicer_animal", None) or "unknown").title()
        race_label = f"Splicer ({animal})"
    else:
        race_label = "Human"
    etched        = [SKILL_DISPLAY_NAMES.get(sk, sk) for sk in SKILL_KEYS if (skills.get(sk) or 0) > 0]
    skill_summary = ", ".join(etched) if etched else "none"
    stat_summary  = "  ".join(
        f"|x{name[:3].upper()}|n |R{level_to_letter(stats.get(k, 0) or 0, MAX_STAT_LEVEL)}|n"
        for k, name in STAT_DISPLAY_NAMES.items()
    )
    divider = fade_rule(47, "─")

    text_body = (
        "|xThe burning thing above you goes out in stages. "
        "The grooves in the stone are just grooves again. "
        "Whatever made this a ritual is already somewhere else.|n\n\n"
        "|xThe figure is not gone. It was never quite there.|n\n\n"
        "|xThe door opened at some point without you noticing. "
        "The undercity is on the other side — the tunnels, the grey-market "
        "corridors, the Authority's blind spots. Your file exists in their "
        "system. A number. A face. Some things omitted that would change "
        "the context of the rest.|n\n\n"
        "|xIn the old sections — the tunnels the maps don't mark, "
        "the collapsed sectors where the Inquisition doesn't patrol — "
        "something has been waiting since before the colony was built. "
        "It doesn't know your name yet.|n\n\n"
        "|xYou don't know yet what you became in that room. "
        "You'll find out.|n\n\n"
        f"|x{divider}|n\n"
        f"  |xRace|n    {race_label}\n"
        f"  |xAge|n     {getattr(caller.db, 'age_years', None) or '?'} years\n"
        f"  |xStats|n   {stat_summary}\n"
        f"  |xMarks|n   {skill_summary}\n"
        f"|x{divider}|n"
    )
    text = _slab("THE RITE IS COMPLETE", text_body, status="CONNECTION ESTABLISHED")
    return text, []