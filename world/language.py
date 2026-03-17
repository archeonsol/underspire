"""
Language handling for says in emotes: set your speaking language with the 'language' command;
all quoted speech in emotes uses that language and is garbled for viewers who don't know it.
Uses Evennia's rplanguage for obfuscation.

Languages are stored as 0-400%: four tiers of 100% each (basic, learning, fluent, native).
db.languages = {"english": 400, "gutter": 150} — percent per language. English is native (400) by default.
Spend XP via @xp advance language <name>; cost is 10 XP per purchase; % gained per purchase scales with intelligence.
Number of non-English languages you can learn is limited by intelligence (average = 1, smarter = more).

ensure_lore_languages() runs at server start (server/conf/at_server_startstop.py). To run manually:
  In-game: @py from world.language import ensure_lore_languages; ensure_lore_languages()
  Evennia shell: from world.language import ensure_lore_languages; ensure_lore_languages()
"""

import re

# Canonical list of lore language keys (for help, validation, defaults)
LORE_LANGUAGE_KEYS = ("english", "gutter", "high_imperial", "cant", "trade", "rite")

# Learnable languages (non-English; these count toward the int-based slot limit)
LEARNABLE_LANGUAGE_KEYS = ("gutter", "high_imperial", "cant", "trade", "rite")

# 0-99 = basic, 100-199 = learning, 200-299 = fluent, 300-400 = native
LANGUAGE_MAX_PERCENT = 400
LANGUAGE_LEVEL_NAMES = ("basic", "learning", "fluent", "native")

# Flat 10 XP per language advance purchase
LANGUAGE_XP_COST = 10

# Friendly aliases for lore languages (input -> canonical key)
LANGUAGE_ALIASES = {
    "high imperial": "high_imperial",
    "highimperial": "high_imperial",
    "imperial": "high_imperial",
}


def get_speaker_language(speaker):
    """
    Return the canonical language key the speaker is currently using.
    Defaults to "english" if unset. Uses LANGUAGE_ALIASES for normalization.
    """
    raw = getattr(speaker.db, "speaking_language", None) or "english"
    if not raw:
        return "english"
    key = str(raw).strip().lower()
    if key == "default":
        return "english"
    return LANGUAGE_ALIASES.get(key, key)


def resolve_language_key(arg):
    """
    Resolve a command argument to a canonical language key, or None if invalid.
    """
    if not arg or not str(arg).strip():
        return None
    key = str(arg).strip().lower()
    key = LANGUAGE_ALIASES.get(key, key)
    return key if key in LORE_LANGUAGE_KEYS else None


def language_percent_to_understanding(percent):
    """
    Convert stored language percent (0-400) to obfuscation understanding (0.0-1.0).
    Backward compat: if percent <= 1.0, treat as legacy 0-1 fraction and return as-is.
    """
    try:
        p = float(percent)
    except (TypeError, ValueError):
        return 0.0
    if p <= 1.0:
        return max(0.0, min(1.0, p))
    return min(1.0, max(0.0, p / float(LANGUAGE_MAX_PERCENT)))


def get_language_level_name(percent):
    """Return 'basic', 'learning', 'fluent', or 'native' for 0-400%."""
    try:
        p = int(percent)
    except (TypeError, ValueError):
        return LANGUAGE_LEVEL_NAMES[0]
    p = max(0, min(LANGUAGE_MAX_PERCENT, p))
    idx = min(3, p // 100)
    return LANGUAGE_LEVEL_NAMES[idx]


def max_other_languages(character):
    """
    Max number of non-English languages the character can learn, based on intelligence.
    Average (Middling, ~45 display) = 1; smarter = more. Uses get_display_stat(0-150).
    """
    if not hasattr(character, "get_display_stat"):
        return 1
    int_display = character.get_display_stat("intelligence") or 0
    # 1 at 45, +1 per 30 display above 45, cap 5
    n = 1 + max(0, (int_display - 45) // 30)
    return min(5, max(1, n))


def language_xp_percent_gain(character):
    """
    Percentage points added to a language per 10 XP spend. Scales with intelligence (display 0-150).
    """
    if not hasattr(character, "get_display_stat"):
        return 10
    int_display = character.get_display_stat("intelligence") or 0
    # int/5 so 50 -> 10%, 90 -> 18%, 150 -> 30%; clamp 5-30
    gain = max(5, min(30, int_display // 5))
    return gain


def get_language_percent(character, lang_key):
    """Return stored percent (0-400) for a language; 0 if not set. English defaults to 400."""
    if not character or not hasattr(character, "db"):
        return 400 if lang_key == "english" else 0
        
    # Safely extract the _SaverDict as a standard dictionary
    skills = dict(getattr(character.db, "languages", None) or {})
    
    if lang_key == "english":
        return skills.get("english", LANGUAGE_MAX_PERCENT)
        
    val = skills.get(lang_key, 0)
    try:
        return max(0, min(LANGUAGE_MAX_PERCENT, int(val)))
    except (TypeError, ValueError):
        if isinstance(val, (int, float)) and 0 <= val <= 1.0:
            return int(val * LANGUAGE_MAX_PERCENT)
        return 0


def ensure_lore_languages():
    """
    Register all lore-fitting languages so lang"..." in emotes works.
    Call once at server startup (e.g. in server/conf/at_server_start.py or a startup hook).
    """
    try:
        from evennia.contrib.rpg.rpsystem.rplanguage import add_language
    except ImportError:
        return
    # English – common tongue; standard phoneme set (garbled = generic foreign)
    # Use force=True so repeated startup calls don't raise LanguageExistsError and instead
    # safely re-sync the language definition with our canonical settings.
    add_language(key="english", force=True)
    # Grammar/phonemes must include v, vv, c, cc (single/double vowel, single/double consonant)
    _v = "a e i o u y"
    _vv = "ea oh ae aa ou ey oi"
    _c = "p t k b d g f s m n l r w"
    _cc = "sh ch ng th zh"
    # Gutter – undercity/tunnel street speech; harsh, clipped
    add_language(
        key="gutter",
        phonemes="%s %s %s k g t d p b f s z sh kh r l n m ng" % (_v, _vv, _c),
        grammar="v c vc cv cvc vcc cvcc ccv cvcv",
        vowels="aeiouy",
        word_length_variance=0,
        force=True,
    )
    # High Imperial – Authority/formal; Latin-ish, longer words
    add_language(
        key="high_imperial",
        phonemes="%s %s %s %s p t k b d g f s th v z m n l r w y" % (_v, _vv, _c, _cc),
        grammar="v cv vc cvv vcc cvc cvvc vccv cvcvc cvccvc",
        vowels="aeiouy",
        word_length_variance=1,
        noun_translate=False,
        force=True,
    )
    # Cant – underworld/thieves' slang; sharp, short
    add_language(
        key="cant",
        phonemes="%s %s %s %s k t p s z f th g d b r l n m" % (_v, _vv, _c, _cc),
        grammar="v c cv vc cvc ccv cvcv",
        vowels="aeiouy",
        word_length_variance=0,
        force=True,
    )
    # Trade – mixed trade tongue; simple, merchant creole
    add_language(
        key="trade",
        phonemes="%s %s %s %s p t k b d g s z m n l r w y" % (_v, _vv, _c, _cc),
        grammar="v cv vc cvc cvv vcc cvcv",
        vowels="aeiouy",
        word_length_variance=0,
        force=True,
    )
    # Rite – ritual/occult (the Rite, the Below); archaic, ritualistic
    add_language(
        key="rite",
        phonemes="%s %s %s %s th dh kh gh s z m n l r v" % (_v, _vv, _c, _cc),
        grammar="v cv vc cvv vcc cvc cvvc vccv cvcvc",
        vowels="aeiouy",
        word_length_variance=1,
        noun_translate=False,
        force=True,
    )


def ensure_default_language():
    """Call once at startup to ensure default/English exists. Prefer ensure_lore_languages() instead."""
    ensure_lore_languages()


def process_language_for_viewer(speaker, quote_text, lang_key, viewer):
    """
    Return the quote text as the viewer hears it (possibly garbled).
    speaker: who said it; viewer: who hears it; lang_key: language id or None for English.
    If viewer is None (e.g. camera feed), return clear text.
    Viewer's skill is stored as 0-400%; converted to 0.0-1.0 understanding for obfuscation.
    """
    if not quote_text:
        return quote_text
    if viewer is None:
        return quote_text
    lang_key = (lang_key or "english").strip().lower() or "english"
    if lang_key == "default":
        lang_key = "english"
    lang_key = LANGUAGE_ALIASES.get(lang_key, lang_key)
    try:
        from evennia.contrib.rpg.rpsystem.rplanguage import obfuscate_language
    except ImportError:
        return quote_text
    # English is always fully understood
    if lang_key == "english":
        return quote_text
    percent = get_language_percent(viewer, lang_key)
    level = language_percent_to_understanding(percent)
    obfuscate_level = 1.0 - max(0.0, min(1.0, level))
    if obfuscate_level <= 0:
        return quote_text
    try:
        # Cap obfuscation so we get gibberish instead of empty (rplanguage can return "." at 1.0)
        obfuscate_level = min(0.85, obfuscate_level)
        result = obfuscate_language(quote_text, level=obfuscate_level, language=lang_key)
        # If still empty or only punctuation, retry at lower level so we get actual gibberish
        if not result or not result.strip() or all(c in '.,;:!? \t\n' for c in result.strip()):
            result = obfuscate_language(quote_text, level=0.5, language=lang_key)
        return result if (result and result.strip()) else quote_text
    except Exception:
        return quote_text


def parse_quoted_speech(text):
    """
    Find "..." in text. Replace with placeholders __LANG_0__, __LANG_1__, ...
    Returns (text_with_placeholders, [(placeholder_id, quote_text), ...]).
    Language for each quote is determined by the speaker's current language (get_speaker_language).
    """
    out = []
    result = []
    pattern = re.compile(r'"([^"]*)"', re.UNICODE)
    last_end = 0
    n = 0
    for m in pattern.finditer(text):
        quote = m.group(1)
        placeholder = "__LANG_%d__" % n
        n += 1
        result.append((placeholder, quote))
        out.append(text[last_end:m.start()])
        out.append(placeholder)
        last_end = m.end()
    out.append(text[last_end:])
    return ("".join(out), result)
