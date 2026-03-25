"""
Tattoo application, removal, and display logic.

Tattoos are permanent marks stored on db.tattoos as:
    {body_part: [{"text", "artist_id", "artist_name", "applied_at", "quality", "is_scar"}, ...]}

They persist through death and cloning (included in clone snapshot).
Chrome (locked) parts cannot be tattooed. Augmented (appended) parts can.
"""

import random
import re
import time

from world.cosmetics import COLOR_SURVIVAL_CHANCE, resolve_tattoo_quality_from_score
from world.rpg.artistry_specialization import SPECIALIZATION_VISUAL, get_specialization_roll_bonus


# ── RP messages broadcast during the 8-second tattooing delay ────────────

TATTOO_RP_MESSAGES = [
    "{artist} prepares the inkwriter. The needles buzz to life.",
    "{artist} presses the inkwriter to {target}'s {part}. The needles bite.",
    "{artist} works steadily, the buzz of the needle constant. Ink flows into skin.",
    "{artist} wipes away excess ink. The design takes shape.",
]


def _sanitize_tattoo_text(text):
    """
    Allow foreground color codes; strip background codes and raw ANSI escapes.

    Kept:  |r |R |g |G |c |C |m |M |b |B |y |Y |w |W |x |n
           |=a through |=z  (greyscale xterm256)
           |RGB  (xterm256 foreground, digits 0-5)
    Stripped: |[x background codes, raw ESC sequences.
    Safety: if any foreground color code is present and text does not end in
    |n, append |n automatically to prevent color bleed in appearance output.
    """
    if not text:
        return ""
    # Strip background color codes (|[r, |[R, |[0-5][0-5][0-5], etc.)
    text = re.sub(r'\|\[[^\s]', '', text)
    # Strip raw ANSI escape sequences
    text = re.sub(r'\x1b\[[^m]*m', '', text)
    text = text.strip()

    # Prevent color bleed: auto-close colored tattoo text.
    has_color = bool(re.search(r"\|(?:[rgbcmywbxRGCBMYWBX]|=[a-z]|[0-5]{3})", text))
    if has_color and not text.endswith("|n"):
        text = f"{text}|n"
    return text


_COLOR_CODE_RE = re.compile(r"\|(?:[rgbcmywbxRGCBMYWBX]|=[a-z]|[0-5]{3})")


def _apply_color_degradation(text, quality):
    """
    Probabilistically strip color codes from tattoo text based on quality.

    Each color code is tested independently with a span-weighted survival
    chance: longer colored runs are harder to preserve at low quality.

    Formula per code:
        effective_chance = base_survival ** max(1, len(colored_span) / 4)

    where colored_span is the text between this code and the next code or |n.

    masterwork always returns text unchanged.
    After stripping, the |n safety check is re-applied.
    """
    if quality == "masterwork":
        return text

    base = COLOR_SURVIVAL_CHANCE.get(quality, 0.30)

    # Split text into a list of tokens: alternating plain text and color codes.
    # We need to know what span each code colors, so we parse sequentially.
    tokens = _COLOR_CODE_RE.split(text)
    codes = _COLOR_CODE_RE.findall(text)

    # Rebuild, deciding for each code whether it survives.
    result_parts = [tokens[0]]
    for i, code in enumerate(codes):
        # The span this code colors is the plain-text token that follows it.
        span = tokens[i + 1] if i + 1 < len(tokens) else ""
        # Strip |n from span length — it's a reset, not colored content.
        visible_span = span.replace("|n", "")
        span_len = len(visible_span)
        effective_chance = base ** max(1.0, span_len / 4.0)
        if random.random() < effective_chance:
            result_parts.append(code)
        result_parts.append(span)

    result = "".join(result_parts)

    # Re-apply |n safety: if any color codes survived, ensure terminator.
    has_color = bool(_COLOR_CODE_RE.search(result))
    if has_color and not result.endswith("|n"):
        result = f"{result}|n"
    elif not has_color and result.endswith("|n"):
        result = result[:-2]
    return result


def apply_tattoo(artist, target, body_part, tattoo_text, inkwriter):
    """
    Apply a tattoo to a target character's body part.

    Performs trust, body part, and text validation; rolls artistry skill;
    stores the result on target.db.tattoos.

    Returns (success: bool, quality: str, message: str).
    """
    from world.rpg.trust import check_trust
    from world.body import get_character_body_parts, is_part_present, is_part_chrome

    if not check_trust(target, artist, "tattoo"):
        return False, "", "They don't trust you to tattoo them."

    parts = get_character_body_parts(target)
    if body_part not in parts:
        return False, "", f"They don't have a '{body_part}'."

    if not is_part_present(target, body_part):
        return False, "", "That body part is missing."

    if is_part_chrome(target, body_part):
        return False, "", "That part is fully chrome. Ink doesn't bind to metal."

    cleaned = _sanitize_tattoo_text(tattoo_text)
    if len(cleaned) < 5:
        return False, "", "Tattoo text too short. Minimum 5 characters."
    if len(cleaned) > 300:
        return False, "", "Tattoo text too long. Maximum 300 characters."

    inkwriter_tier = int(getattr(inkwriter.db, "inkwriter_tier", 1) or 1)
    spec_mod = get_specialization_roll_bonus(artist, SPECIALIZATION_VISUAL)
    _, final_score = artist.roll_check(
        ["agility", "charisma"], "artistry", difficulty=10, modifier=spec_mod
    )

    quality = resolve_tattoo_quality_from_score(final_score, inkwriter_tier)
    cleaned = _apply_color_degradation(cleaned, quality)

    tattoos = dict(getattr(target.db, "tattoos", None) or {})
    part_tattoos = list(tattoos.get(body_part) or [])

    artist_display = (
        artist.get_display_name(target)
        if hasattr(artist, "get_display_name")
        else artist.key
    )

    part_tattoos.append({
        "text": cleaned,
        "artist_id": artist.id,
        "artist_name": artist_display,
        "applied_at": time.time(),
        "quality": quality,
        "is_scar": False,
    })

    tattoos[body_part] = part_tattoos
    target.db.tattoos = tattoos

    return True, quality, ""


def remove_tattoo(artist, target, body_part, tattoo_index, inkwriter):
    """
    Attempt to remove a tattoo by index from a body part.

    On success (sufficient score), the tattoo is cleanly removed.
    On failure, the entry is replaced with a scar description.

    Returns (success: bool, message: str).
    """
    from world.rpg.trust import check_trust

    if not check_trust(target, artist, "tattoo"):
        return False, "They don't trust you for that."

    tattoos = dict(getattr(target.db, "tattoos", None) or {})
    part_tattoos = list(tattoos.get(body_part) or [])

    if tattoo_index < 0 or tattoo_index >= len(part_tattoos):
        return False, "Invalid tattoo number."

    spec_mod = get_specialization_roll_bonus(artist, SPECIALIZATION_VISUAL)
    _, final_score = artist.roll_check(
        ["agility", "charisma"], "artistry", difficulty=15, modifier=spec_mod
    )

    selected = part_tattoos[tattoo_index]
    was_scar = bool(selected.get("is_scar", False))

    # Score-based removal: higher final scores cleanly remove marks/scars.
    success_score = int(final_score or 0) >= 70
    if success_score:
        part_tattoos.pop(tattoo_index)
        tattoos[body_part] = part_tattoos
        target.db.tattoos = tattoos
        if was_scar:
            return True, "You carefully work the scar tissue until it smooths out. The mark fades away."
        return True, "The tattoo is cleanly removed. No trace remains."
    else:
        old_entry = selected
        if not was_scar:
            scar_artist_display = (
                artist.get_display_name(target)
                if hasattr(artist, "get_display_name")
                else artist.key
            )
            part_tattoos[tattoo_index] = {
                "text": "A patch of scarred, discolored skin where a tattoo used to be.",
                "artist_id": artist.id,
                "artist_name": scar_artist_display,
                "applied_at": old_entry.get("applied_at", time.time()),
                "quality": "crude",
                "is_scar": True,
            }
            tattoos[body_part] = part_tattoos
            target.db.tattoos = tattoos
            return True, "The removal is rough. Scar tissue replaces the ink."

        # Failed attempt on an existing scar: keep it as-is (still recoverable later).
        tattoos[body_part] = part_tattoos
        target.db.tattoos = tattoos
        return True, "You work at the scar, but it doesn't give this time. You can try again."


def get_tattoo_display_for_part(character, body_part):
    """
    Return the assembled tattoo description text for a body part, or empty string.
    Called by the appearance pipeline after the clothing layer.
    """
    tattoos = getattr(character.db, "tattoos", None) or {}
    part_tattoos = tattoos.get(body_part) or []

    if not part_tattoos:
        return ""

    skin_code = (
        getattr(character.db, "skin_tone_code", None)
        if hasattr(character, "db") else None
    )

    lines = []
    for tattoo in part_tattoos:
        text = tattoo.get("text", "")
        if text and skin_code:
            # Wrap the whole text in skin tone so plain segments read against
            # skin rather than terminal default.  Where artist color codes
            # survive, they override their spans; after each |n reset we
            # re-inject the skin tone so the baseline stays skin-colored.
            text = skin_code + text.replace("|n", f"|n{skin_code}") + "|n"
        lines.append(text)

    return " ".join(lines)
