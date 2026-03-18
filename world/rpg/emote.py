import re
from collections import defaultdict

PRONOUN_MAP = {
    "male": ("he", "his", "him"),
    "female": ("she", "her", "her"),
    "neutral": ("they", "their", "them"),
    "nonbinary": ("they", "their", "them"),
}

FIRST_TO_SECOND_MAP = [
    (r"\bI'm\b", "you're"), (r"\bI am\b", "you are"),
    (r"\bI've\b", "you've"), (r"\bI have\b", "you have"),
    (r"\bI\b", "you"), (r"\bmy\b", "your"), (r"\bme\b", "you"),
]

IRREGULAR_VERBS = {
    "have": "has", "do": "does", "go": "goes", "be": "is", "am": "is", "are": "is"
}


def first_to_second(text):
    """Convert first-person text to second person for the emitter's echo (I→you, my→your, etc.)."""
    if not text:
        return text
    result = text
    for pattern, replacement in FIRST_TO_SECOND_MAP:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def _conjugate(word):
    lower = word.lower()
    if lower in IRREGULAR_VERBS: return IRREGULAR_VERBS[lower]
    if lower.endswith(("s", "sh", "ch", "x", "z")): return word + "es"
    if lower.endswith("y") and len(lower) > 1 and lower[-2] not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"

def first_to_third(text, character):
    # 1. Quote protection: content in "..." is character speech, leave verbatim
    quotes = re.findall(r'"([^"]*)"', text)
    quote_map = {f"__Q{i}__": f'"{q}"' for i, q in enumerate(quotes)}
    for placeholder, original in quote_map.items():
        text = text.replace(original, placeholder)

    # 2. Pronoun Conversion
    key = (getattr(character.db, "pronoun", "neutral") or "neutral").lower()
    sub, poss, obj = PRONOUN_MAP.get(key, PRONOUN_MAP["neutral"])
    text = re.sub(r"\bI'm\b", f"{sub}'s", text, flags=re.IGNORECASE)
    text = re.sub(r"\bI\b", sub, text, flags=re.IGNORECASE)
    text = re.sub(r"\bmy\b", poss, text, flags=re.IGNORECASE)
    text = re.sub(r"\bme\b", obj, text, flags=re.IGNORECASE)

    # 3. Conjugation: leading "," = don't conjugate first word; ".word" = verb, conjugate
    skip_first_conjugate = False
    if text.lstrip().startswith(","):
        text = text.lstrip()[1:].lstrip()
        skip_first_conjugate = True
    # Leading ".word" (dot-verb): strip the dot so first-word conjugation runs; handles ".grin" -> "grins"
    if not skip_first_conjugate and text.lstrip().startswith("."):
        text = text.lstrip().lstrip(".").lstrip()
    def conjugate_dot_verb(match):
        return " " + _conjugate(match.group(1))
    text = re.sub(r" \.\s*(\w+)", conjugate_dot_verb, text)
    # Mid-string ".word" already handled above; leading was stripped so first word gets conjugated below
    words = text.split()
    pronouns = {sub, poss, obj, "they", "their", "them"}
    if not skip_first_conjugate and words:
        first = words[0]
        # First token may have trailing punctuation (e.g. "grin," from ".grin, looking at Bob")
        alpha_part = first.rstrip(".,;:!?") or first
        if alpha_part and alpha_part.isalpha() and "__Q" not in alpha_part and alpha_part.lower() not in pronouns:
            words[0] = _conjugate(alpha_part) + first[len(alpha_part):]
    text = " ".join(words)

    # 4. Restore Quotes
    for placeholder, original in quote_map.items():
        text = text.replace(placeholder, original)
    return text

def split_emote_segments(text):
    """Split on ' . ' (space dot space) so '.look' in the middle stays part of the pose."""
    return [s.strip() for s in re.split(r" \.\s+", text) if s.strip()]

def _normalize_sdesc_for_match(name):
    """Strip leading article and lowercase for matching in emotes."""
    if not name:
        return ""
    s = name.strip().lower()
    for prefix in ("the ", "a ", "an "):
        if s.startswith(prefix):
            s = s[len(prefix):].strip()
            break
    return s


def find_targets_in_text(text, character_list, emitter):
    """
    Find character targets mentioned in emote text. Matches by key (name), by full sdesc,
    or by any word in the sdesc (e.g. "grin at average" matches "an average naked person").
    When multiple characters share the same sdesc/word, use 1-average, 2-average etc.;
    if no number is given, default to the first in room order.
    Returns list of (matched_string, char) for pronoun resolution and viewer replacement.
    """
    from world.rp_features import get_display_name_for_viewer
    targets = []
    if not text or not character_list:
        return targets
    # Build (char, display_name, norm) in room order (character_list order)
    candidates = []
    for char in character_list:
        if char == emitter:
            continue
        name = get_display_name_for_viewer(char, emitter)
        if not name:
            continue
        norm = _normalize_sdesc_for_match(name)
        if norm:
            candidates.append((char, name, norm))
    if not candidates:
        return targets
    # Group by full phrase (for "average naked person") and build word->chars for partial match
    by_phrase = defaultdict(list)
    word_to_chars = defaultdict(list)
    for char, name, norm in candidates:
        phrase = norm
        words = phrase.split()
        by_phrase[phrase].append((char, name))
    # word_to_chars[word] = [(char, phrase, idx_in_phrase_group), ...] in room order
    for phrase, char_list in by_phrase.items():
        for idx, (char, name) in enumerate(char_list):
            for word in phrase.split():
                word_to_chars[word].append((char, phrase, idx))
    # Build match specs: full phrase + each word. For multiples, default to first (num=None), and 1-, 2- for explicit
    match_specs = []
    for phrase, char_list in by_phrase.items():
        if len(char_list) == 1:
            (char, _) = char_list[0]
            match_specs.append((phrase, char, None))
        else:
            for idx, (char, _) in enumerate(char_list):
                match_specs.append((phrase, char, idx + 1))
    for word, group in word_to_chars.items():
        if len(group) == 1:
            (char, _, _) = group[0]
            match_specs.append((word, char, None))
        else:
            first_char = group[0][0]
            match_specs.append((word, first_char, None))
            for char, phrase, idx in group:
                match_specs.append((word, char, idx + 1))
    # Sort so longer patterns match first; numbered (1-word) before unnumbered so "1-average" beats "average"
    def _spec_sort_key(spec):
        phrase_or_word, _char, num = spec
        if num is not None:
            effective_len = len("%d-%s" % (num, phrase_or_word))
        else:
            effective_len = len(phrase_or_word)
        return (-effective_len, phrase_or_word, num or 0)
    match_specs.sort(key=_spec_sort_key)
    _RE_FLAGS = re.IGNORECASE | re.UNICODE
    seen_positions = set()

    def _overlaps(s, e):
        for (a, b) in seen_positions:
            if not (e <= a or s >= b):
                return True
        return False

    # Use (?<!\w)(?!\w) instead of \b so numbered refs like "1-average" match (Python \b is unreliable with digits+hyphen)
    for phrase_or_word, char, num in match_specs:
        esc = re.escape(phrase_or_word)
        if num is not None:
            pattern = r"(?<!\w)(%d-\s*(?:the\s+|a\s+|an\s+)?%s)(?!\w)" % (num, esc)
        else:
            pattern = r"(?<!\w)(?:the\s+|a\s+|an\s+)?(%s)(?!\w)" % esc
        for m in re.finditer(pattern, text, _RE_FLAGS):
            start, end = m.start(), m.end()
            if _overlaps(start, end):
                continue
            seen_positions.add((start, end))
            matched = m.group(0)
            targets.append((matched, char))
    # NOTE: We intentionally do NOT match by the character's internal key/name here.
    # Targeting should only work via sdesc/recog-visible names, not builder object keys.
    def pos_key(t):
        pos = text.lower().find(t[0].lower())
        return (pos, -len(t[0]))
    targets.sort(key=pos_key)
    return targets


def resolve_sdesc_to_characters(emitter, character_list, search_string):
    """
    Resolve a search string like "tall man" or "1-tall man" to a list of matching characters.
    Used by recog command and by look/search. Returns empty list if no match, [char] or [c1, c2, ...] if match.
    """
    from world.rp_features import get_display_name_for_viewer
    if not search_string or not character_list or not emitter:
        return []
    search_string = search_string.strip()
    if not search_string:
        return []
    # Parse optional "N-" prefix
    num = None
    phrase = search_string
    import re
    m = re.match(r"^(\d+)[-\s]+(.+)$", search_string, re.IGNORECASE)
    if m:
        num = int(m.group(1))
        phrase = m.group(2).strip()
    phrase_norm = _normalize_sdesc_for_match(phrase)
    if not phrase_norm:
        return []
    candidates = []
    for char in character_list:
        if char == emitter:
            continue
        name = get_display_name_for_viewer(char, emitter)
        if not name:
            continue
        norm = _normalize_sdesc_for_match(name)
        if not norm:
            continue
        if phrase_norm in norm or norm == phrase_norm:
            candidates.append((char, norm))
    if not candidates:
        return []
    # If phrase matches multiple, we need num to disambiguate
    by_phrase = defaultdict(list)
    for char, norm in candidates:
        by_phrase[norm].append(char)
    matches = []
    for norm, chars in by_phrase.items():
        if phrase_norm == norm or phrase_norm in norm:
            matches.extend(chars)
    if num is not None:
        if 1 <= num <= len(matches):
            return [matches[num - 1]]
        return []
    return matches

def _pronoun_set(char):
    return (getattr(char.db, "pronoun", "neutral") or "neutral").lower()


def _get_name_mention_timeline(text, targets):
    """Return list of (end_pos, char) for each name mention in order (by position)."""
    events = []
    for name, char in targets:
        for m in re.finditer(r"\b" + re.escape(name) + r"\b", text, re.IGNORECASE):
            events.append((m.end(), char))
    events.sort(key=lambda x: x[0])
    return events


# Patterns in order: more specific first. (pattern, pronoun_key, form_type, has_capture_for_next_word)
# form_type: 'sub' -> you, 'obj' -> you, 'poss_det' -> your, 'poss_stand' -> yours
_PRONOUN_PATTERNS = [
    (r"\bher\s+(\w+)", "female", "poss_det", True),
    (r"\bhers\b", "female", "poss_stand", False),
    (r"\bhis\s+(\w+)", "male", "poss_det", True),
    (r"\bhis\b", "male", "poss_stand", False),
    (r"\btheir\s+(\w+)", "neutral", "poss_det", True),
    (r"\btheirs\b", "neutral", "poss_stand", False),
    (r"\bher\b", "female", "obj", False),
    (r"\bhim\b", "male", "obj", False),
    (r"\bthem\b", "neutral", "obj", False),
    (r"\bshe\b", "female", "sub", False),
    (r"\bhe\b", "male", "sub", False),
    (r"\bthey\b", "neutral", "sub", False),
]


def _get_pronoun_referents(text, targets):
    """
    Find each pronoun occurrence and resolve to the last-mentioned character with that pronoun set.
    Returns list of (start, end, referent_char, form_type, original_text, suffix_or_None).
    """
    timeline = _get_name_mention_timeline(text, targets)
    if not timeline:
        return []
    char_pronoun_set = {char: _pronoun_set(char) for _, char in targets}
    covered = []
    pronoun_occurrences = []

    for pattern, pset, form_type, has_capture in _PRONOUN_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            s, e = m.start(), m.end()
            if any(s < end and e > start for start, end in covered):
                continue
            covered.append((s, e))
            referent = None
            for end_pos, char in timeline:
                if end_pos <= s and char_pronoun_set.get(char) == pset:
                    referent = char
            suffix = m.group(1) if has_capture and m.lastindex else None
            pronoun_occurrences.append((s, e, referent, form_type, m.group(0), suffix))
    pronoun_occurrences.sort(key=lambda x: x[0])
    return pronoun_occurrences


def _second_person_form(form_type):
    if form_type in ("sub", "obj"):
        return "you"
    if form_type == "poss_det":
        return "your"
    return "yours"


def build_emote_for_viewer(text, viewer, targets, emitter_name):
    # 1. Resolve pronouns to referents (last-mentioned character with that pronoun set)
    pronoun_occurrences = _get_pronoun_referents(text, targets)
    # Replace from end to start so positions don't shift; poss_det keeps following word (e.g. " hand")
    placeholders = []
    for i, (start, end, referent, form_type, original, suffix) in enumerate(reversed(pronoun_occurrences)):
        idx = len(pronoun_occurrences) - 1 - i
        ph = f"__PRON_{idx}__"
        placeholders.append((ph, referent, form_type, original, suffix))
        tail = (" " + suffix if suffix else "")
        text = text[:start] + ph + tail + text[end:]
    # 2. Name replacement: each target's matched string -> "you" for viewer, else viewer's display name for that char
    try:
        from world.rp_features import get_display_name_for_viewer
    except ImportError:
        get_display_name_for_viewer = lambda c, v: getattr(c, "key", str(c))
    # Use (?<!\w)(?!\w) instead of \b so "1-average" etc. are replaced correctly (Python \b + digits+hyphen is unreliable)
    for matched_name, char in sorted(targets, key=lambda t: -len(t[0])):
        if char == viewer:
            replacement = "you"
            text = re.sub(r"(?<!\w)" + re.escape(matched_name) + r"'s(?!\w)", "your", text, flags=re.IGNORECASE)
            text = re.sub(r"(?<!\w)" + re.escape(matched_name) + r"(?!\w)", replacement, text, flags=re.IGNORECASE)
        else:
            replacement = get_display_name_for_viewer(char, viewer)
            text = re.sub(r"(?<!\w)" + re.escape(matched_name) + r"'s(?!\w)", replacement + "'s", text, flags=re.IGNORECASE)
            text = re.sub(r"(?<!\w)" + re.escape(matched_name) + r"(?!\w)", replacement, text, flags=re.IGNORECASE)
    # 3. Replace placeholders: you/your/yours if referent is viewer, else original (suffix " hand" already in text for poss_det)
    for ph, referent, form_type, original, suffix in placeholders:
        if referent is not None and referent == viewer:
            replacement = _second_person_form(form_type)
        else:
            # For poss_det original was "her hand"; we only replace the pronoun part, " hand" is already in text
            replacement = original.split()[0] if suffix and form_type == "poss_det" else original
        text = text.replace(ph, replacement)
    return text

def format_emote_message(emitter_name, body):
    return f"|c{emitter_name}|n {body}"


def replace_first_pronoun_with_name(body, pronoun_key, emitter_name, color_name=True):
    """
    Replace the first occurrence of the emitter's third-person pronoun with their name.
    Used for comma-start emotes so the name appears in the pose (e.g. "He looks" -> "TS looks").
    """
    key = (pronoun_key or "neutral").lower()
    sub, poss, obj = PRONOUN_MAP.get(key, PRONOUN_MAP["neutral"])
    name = f"|c{emitter_name}|n" if color_name else emitter_name
    name_poss = f"|c{emitter_name}|n's" if color_name else emitter_name + "'s"
    candidates = []  # (start, end, replacement)
    for pattern, repl in [
        (r"\b" + re.escape(sub) + r"\b", name),
        (r"\b" + re.escape(obj) + r"\b", name),
        (r"\b" + re.escape(poss) + r"\b", name_poss),
    ]:
        m = re.search(pattern, body, re.IGNORECASE)
        if m:
            candidates.append((m.start(), m.end(), repl))
    # "her" is both poss and obj: prefer possessive "her word" -> "Name's word"
    if poss == "her" and obj == "her":
        m = re.search(r"\bher\s+(\w)", body, re.IGNORECASE)
        if m:
            end = m.start() + len(m.group(0)) - len(m.group(1))
            candidates.append((m.start(), end, name_poss + " "))
    if not candidates:
        return body
    # Earliest position first; at same position prefer longer span (e.g. "her hand" over "her")
    candidates.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    start, end, repl = candidates[0]
    return body[:start] + repl + body[end:]