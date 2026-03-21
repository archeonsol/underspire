"""
Evennia xterm256 skin tone palette — CORRECTED.

Evennia color syntax:
  |RGB  = 6x6x6 color cube, each digit 0-5
          Actual RGB = (0, 95, 135, 175, 215, 255) per channel
  |=a-z = 24-step greyscale (a=near-black, z=near-white)
  |w    = bold white (used for chrome)
  |n    = reset

Example: |321 = R=3(175), G=2(135), B=1(95) = a warm brown

Color is applied at render time; stored body/general descriptions are plain text.
"""

import re
from evennia.utils.ansi import strip_ansi

from world.theme_colors import CHROME_COLORS, ROOM_COLORS

# Default IC colors when no skin tone is set (match rooms / look header)
DEFAULT_IC_NAME_COLOR = ROOM_COLORS["character_name"]
DEFAULT_IC_SDESC_COLOR = "|w"

CHROME_DESC_COLOR = "|w"

SKIN_TONES = {
    # ══════════════════════════════════════════════════════════
    #  DEEP
    # ══════════════════════════════════════════════════════════
    "black": {"code": "|=d", "group": "deep"},
    "dark brown": {"code": "|210", "group": "deep"},
    "deep brown": {"code": "|211", "group": "deep"},
    "dark reddish brown": {"code": "|310", "group": "deep"},
    "dark cool brown": {"code": "|=f", "group": "deep"},
    "very dark brown": {"code": "|100", "group": "deep"},
    # ══════════════════════════════════════════════════════════
    #  DEEP-MEDIUM
    # ══════════════════════════════════════════════════════════
    "brown": {"code": "|321", "group": "deep-medium"},
    "warm brown": {"code": "|320", "group": "deep-medium"},
    "reddish brown": {"code": "|311", "group": "deep-medium"},
    "golden brown": {"code": "|420", "group": "deep-medium"},
    "copper brown": {"code": "|310", "group": "deep-medium"},
    "cool brown": {"code": "|=h", "group": "deep-medium"},
    "red-brown": {"code": "|411", "group": "deep-medium"},
    # ══════════════════════════════════════════════════════════
    #  MEDIUM
    # ══════════════════════════════════════════════════════════
    "medium brown": {"code": "|421", "group": "medium"},
    "warm tan": {"code": "|431", "group": "medium"},
    "tan": {"code": "|332", "group": "medium"},
    "light brown": {"code": "|432", "group": "medium"},
    "rosy brown": {"code": "|322", "group": "medium"},
    "olive brown": {"code": "|331", "group": "medium"},
    "dusty brown": {"code": "|=k", "group": "medium"},
    # ══════════════════════════════════════════════════════════
    #  MEDIUM-LIGHT
    # ══════════════════════════════════════════════════════════
    "light tan": {"code": "|432", "group": "medium-light"},
    "warm beige": {"code": "|531", "group": "medium-light"},
    "beige": {"code": "|442", "group": "medium-light"},
    "peach": {"code": "|532", "group": "medium-light"},
    "sandy": {"code": "|521", "group": "medium-light"},
    "light olive": {"code": "|332", "group": "medium-light"},
    "rosy beige": {"code": "|433", "group": "medium-light"},
    # ══════════════════════════════════════════════════════════
    #  LIGHT
    # ══════════════════════════════════════════════════════════
    "fair": {"code": "|543", "group": "light"},
    "light": {"code": "|443", "group": "light"},
    "cream": {"code": "|553", "group": "light"},
    "warm ivory": {"code": "|542", "group": "light"},
    "pale": {"code": "|=t", "group": "light"},
    "very pale": {"code": "|554", "group": "light"},
    "cool pale": {"code": "|=v", "group": "light"},
    # ══════════════════════════════════════════════════════════
    #  WARM UNDERTONE VARIANTS
    # ══════════════════════════════════════════════════════════
    "golden": {"code": "|430", "group": "warm"},
    "warm yellow-brown": {"code": "|530", "group": "warm"},
    "warm golden": {"code": "|541", "group": "warm"},
    "amber": {"code": "|520", "group": "warm"},
    # ══════════════════════════════════════════════════════════
    #  COOL UNDERTONE VARIANTS
    # ══════════════════════════════════════════════════════════
    "cool grey-brown": {"code": "|=l", "group": "cool"},
    "grey-brown": {"code": "|222", "group": "cool"},
    "cool beige": {"code": "|=n", "group": "cool"},
    "grey-fair": {"code": "|=q", "group": "cool"},
}

for _name, _data in SKIN_TONES.items():
    _data["preview"] = f"{_data['code']}{_name}|n"

SKIN_TONE_GROUPS = [
    ("DEEP", "deep"),
    ("DEEP-MEDIUM", "deep-medium"),
    ("MEDIUM", "medium"),
    ("MEDIUM-LIGHT", "medium-light"),
    ("LIGHT", "light"),
    ("WARM UNDERTONES", "warm"),
    ("COOL UNDERTONES", "cool"),
]

# Alias for existing imports (e.g. commands)
SKIN_TONE_GROUP_ORDER = SKIN_TONE_GROUPS


def format_skintone_display(caller=None):
    """Build the formatted skin tone palette for the @skintone command."""
    lines = [
        "",
        "|x==========================================================|n",
        "  |cS K I N   T O N E|n",
        "|x==========================================================|n",
        "",
    ]
    for group_label, group_key in SKIN_TONE_GROUPS:
        tones = [(name, data) for name, data in SKIN_TONES.items() if data["group"] == group_key]
        if not tones:
            continue
        lines.append(f"  |w{group_label}|n")
        row = []
        for name, data in tones:
            row.append(data["preview"])
            if len(row) >= 4:
                lines.append("    " + "  ".join(row))
                row = []
        if row:
            lines.append("    " + "  ".join(row))
        lines.append("")
    if caller is not None and hasattr(caller, "db"):
        cur = getattr(caller.db, "skin_tone", None)
        if cur:
            lines.append(f"  Your current tone: {SKIN_TONES.get(cur, {}).get('preview', cur)}")
        else:
            lines.append("  You have not set a skin tone yet.")
        lines.append("")
    lines.append("  Usage: |w@skintone <name>|n")
    lines.append("  Example: |w@skintone warm brown|n")
    lines.append("")
    return "\n".join(lines)


def strip_color_codes(text):
    """Remove Evennia ANSI/color codes from text."""
    if not text:
        return text
    return strip_ansi(text)


def _text_has_markup(text):
    """True if string appears to contain Evennia | color codes."""
    if not text or "|" not in text:
        return False
    return bool(re.search(r"\|[^|]", text))


def format_ic_character_name_possessive(character, viewer, plain_name):
    """Like format_ic_character_name but for possessive (Name's)."""
    if not plain_name:
        return plain_name or ""
    poss = f"{plain_name}'s"
    if viewer is None or viewer == character:
        return poss
    if _text_has_markup(plain_name):
        return poss
    skin = getattr(character.db, "skin_tone_code", None) if hasattr(character, "db") else None
    if skin:
        return f"{skin}{plain_name}'s|n"
    return f"{DEFAULT_IC_NAME_COLOR}{plain_name}'s|n"


def format_ic_character_name(character, viewer, plain_name):
    """
    Wrap plain display name for IC contexts (room, say, emote targets).
    No color when viewer is None, self, or when plain_name already has codes.
    """
    if not plain_name:
        return plain_name or ""
    if viewer is None or viewer == character:
        return plain_name
    if _text_has_markup(plain_name):
        return plain_name
    skin = getattr(character.db, "skin_tone_code", None) if hasattr(character, "db") else None
    if skin:
        return f"{skin}{plain_name}|n"
    return f"{DEFAULT_IC_NAME_COLOR}{plain_name}|n"


def format_ic_sdesc_fragment(character, viewer, plain_sdesc):
    """
    Color for sdesc text (parenthetical line). Same rules as format_ic_character_name.
    """
    if not plain_sdesc:
        return plain_sdesc or ""
    if viewer is None or viewer == character:
        return plain_sdesc
    if _text_has_markup(plain_sdesc):
        return plain_sdesc
    skin = getattr(character.db, "skin_tone_code", None) if hasattr(character, "db") else None
    if skin:
        return f"{skin}{plain_sdesc}|n"
    return f"{DEFAULT_IC_SDESC_COLOR}{plain_sdesc}|n"


def format_ic_move_line(character, viewer, plain_line):
    """
    Wrap full move announcement line (capitalized sdesc + optional recog) in skin tone when set.
    """
    if not plain_line:
        return plain_line or ""
    if viewer is None or viewer == character:
        return plain_line
    if _text_has_markup(plain_line):
        return plain_line
    skin = getattr(character.db, "skin_tone_code", None) if hasattr(character, "db") else None
    if skin:
        return f"{skin}{plain_line}|n"
    return plain_line


def resolve_skin_tone_key(name):
    """
    Resolve user input to a canonical SKIN_TONES key, or None.
    Case-insensitive; strips whitespace.
    """
    if not name:
        return None
    n = " ".join(name.strip().lower().split())
    if n in SKIN_TONES:
        return n
    for key in SKIN_TONES:
        if key.lower() == n:
            return key
    return None


def get_skin_tone(name):
    """Look up a skin tone by name (case-insensitive). Returns dict or None."""
    key = resolve_skin_tone_key(name)
    if not key:
        return None
    return SKIN_TONES.get(key)


def get_skin_tone_code_for_key(key):
    """Return color code for a tone key, or None."""
    if not key:
        return None
    entry = SKIN_TONES.get(key)
    if not entry:
        return None
    return entry.get("code")


def set_character_skin_tone(character, key):
    """Set db.skin_tone, db.skin_tone_code, db.skin_tone_set. Returns error string or None."""
    key = resolve_skin_tone_key(key)
    if not key:
        return "invalid"
    code = get_skin_tone_code_for_key(key)
    character.db.skin_tone = key
    character.db.skin_tone_code = code
    character.db.skin_tone_set = True
    return None


def get_chrome_desc_text(cyberware_obj, body_part):
    """Description text for chrome on a body part (custom instance override or class body_mods)."""
    custom = getattr(cyberware_obj.db, "custom_descriptions", None) or {}
    if body_part in custom and (custom.get(body_part) or "").strip():
        return custom.get(body_part).strip()
    mods = getattr(cyberware_obj, "body_mods", {}) or {}
    entry = mods.get(body_part)
    if entry:
        return entry[1]
    return None


def get_chrome_desc_color(cyberware_obj):
    """ANSI color code for this chrome's descriptions."""
    custom = getattr(cyberware_obj.db, "custom_color", None)
    if custom:
        return custom
    return CHROME_DESC_COLOR


def render_chrome_description(cyberware_obj, body_part):
    """Single chrome fragment with color + |n."""
    text = get_chrome_desc_text(cyberware_obj, body_part)
    if not text:
        return ""
    color = get_chrome_desc_color(cyberware_obj)
    return f"{color}{text}|n"


def cyberware_by_typeclass_path(character, path):
    """Find installed cyberware object matching typeclass_path string."""
    for cw in getattr(character.db, "cyberware", None) or []:
        if getattr(cw, "typeclass_path", None) == path:
            return cw
    return None


def locking_cyberware_for_part(character, part):
    """Installed cyberware that locks this body part, if any."""
    from world.body import get_cyberware_for_part as _gfp

    for cw in _gfp(character, part):
        mods = getattr(cw, "body_mods", None) or {}
        ent = mods.get(part)
        if ent and ent[0] == "lock":
            return cw
    return None


def apply_skin_tone_to_bio_text(character, raw_text, part=None):
    """Wrap biological description text in skin tone color."""
    if not raw_text or not str(raw_text).strip():
        return raw_text
    race = (getattr(character.db, "race", None) or "human") if hasattr(character, "db") else "human"
    if (
        race == "splicer"
        and part in ("tail", "left ear", "right ear")
        and _text_has_markup(raw_text)
    ):
        return raw_text
    code = getattr(character.db, "skin_tone_code", None) if hasattr(character, "db") else None
    if not code:
        return raw_text
    return f"{code}{raw_text}|n"


# ── Quick reference: Evennia xterm256 color cube ─────────────────────────────
#
#  |RGB where R, G, B are digits 0-5
#  Actual values per digit: 0→0, 1→95, 2→135, 3→175, 4→215, 5→255
#
#  Skin tone sweet spots:
#    Deep:         |210 |211 |310 |100
#    Brown:        |321 |320 |311 |420 |411
#    Medium:       |421 |431 |432 |332 |322 |331
#    Light:        |532 |531 |443 |543 |542 |554
#    Greyscale:    |=d(dark) |=f |=h |=k |=n |=q |=t |=v(light)
#
#  Avoid: pure greens (|0X0), pure blues (|00X), saturated reds (|500)
#  Best: R > G >= B with small differences between channels
