import re

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
    def conjugate_dot_verb(match):
        return " " + _conjugate(match.group(1))
    text = re.sub(r" \.\s*(\w+)", conjugate_dot_verb, text)
    if text.lstrip().startswith("."):
        text = re.sub(r"^\.\s*(\w+)", lambda m: _conjugate(m.group(1)), text, count=1)
    words = text.split()
    pronouns = {sub, poss, obj, "they", "their", "them"}
    if not skip_first_conjugate and words and words[0].isalpha() and "__Q" not in words[0] and words[0].lower() not in pronouns:
        words[0] = _conjugate(words[0])
    text = " ".join(words)

    # 4. Restore Quotes
    for placeholder, original in quote_map.items():
        text = text.replace(placeholder, original)
    return text

def split_emote_segments(text):
    """Split on ' . ' (space dot space) so '.look' in the middle stays part of the pose."""
    return [s.strip() for s in re.split(r" \.\s+", text) if s.strip()]

def find_targets_in_text(text, character_list, emitter):
    targets = []
    for char in character_list:
        if char != emitter and re.search(r"\b" + re.escape(char.key) + r"\b", text, re.IGNORECASE):
            targets.append((char.key, char))
    return targets

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
    # 2. Name replacement for viewer (you/your when viewer is that target)
    for name, char in targets:
        if char == viewer:
            text = re.sub(r"\b" + re.escape(name) + r"'s\b", "your", text, flags=re.IGNORECASE)
            text = re.sub(r"\b" + re.escape(name) + r"\b", "you", text, flags=re.IGNORECASE)
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