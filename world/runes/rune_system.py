"""
Rune system: application, buff management, ambient settling, and cleanup.

Runes are spiritual modifications that grant stat boosts stored on
character.db.runes. They reset on permanent death and cloning.

db.runes structure:
    {
        "ansuz": {
            "body_part": "left forearm",
            "description": "<pre-colored text>",
            "color_code": "|305",
            "applied_at": 1234567890.0,
            "settled": False,
            "current_buff_value": 2,
            "artist_id": 42,
            "artist_name": "Mira",
        },
        ...
    }
"""

import time

from evennia.contrib.rpg.buffs.buff import Mod
from evennia.utils import delay, logger

from world.buffs import GameBuffBase
from world.runes.rune_data import (
    RUNE_BUFF_SCHEDULE,
    RUNE_FULL_BUFF_VALUE,
    RUNES,
    SETTLE_MESSAGES,
    SETTLE_OFFSETS,
)


# ── Buff classes ──────────────────────────────────────────────────────────

def _build_rune_buff_class(rune_key, stat, value):
    """
    Dynamically build a GameBuffBase subclass for a rune at a given value.
    Class is registered on this module so pickle can resolve it.
    """
    import sys
    cls_name = f"RuneBuff_{rune_key}_{value}"
    existing = getattr(sys.modules[__name__], cls_name, None)
    if existing:
        return existing
    cls = type(
        cls_name,
        (GameBuffBase,),
        {
            "key": f"rune_{rune_key}",
            "name": f"Rune of {RUNES[rune_key]['display']}",
            "flavor": RUNES[rune_key]["flavor"].capitalize(),
            "duration": -1,
            "maxstacks": 1,
            "stacks": 1,
            "mods": [Mod(stat=f"{stat}_display", modifier="add", value=int(value))],
        },
    )
    setattr(sys.modules[__name__], cls_name, cls)
    return cls


def _register_all_rune_buff_classes():
    """Pre-register all rune buff classes at import time for pickle safety."""
    for rune_key, rune in RUNES.items():
        stat = rune["stat"]
        for _, value in RUNE_BUFF_SCHEDULE:
            _build_rune_buff_class(rune_key, stat, value)


_register_all_rune_buff_classes()


# ── Core buff helpers ─────────────────────────────────────────────────────

def _apply_rune_buff(character, rune_key, value):
    """Add or replace the rune buff on a character at the given value."""
    rune = RUNES.get(rune_key)
    if not rune:
        return
    stat = rune["stat"]
    buff_cls = _build_rune_buff_class(rune_key, stat, value)
    buff_key = f"rune_{rune_key}"
    try:
        if hasattr(character, "buffs"):
            character.buffs.remove(buff_key)
            character.buffs.add(buff_cls, key=buff_key)
    except Exception as e:
        logger.log_err(f"rune_system._apply_rune_buff: {e}")


def _remove_rune_buff(character, rune_key):
    """Remove the rune buff from a character."""
    buff_key = f"rune_{rune_key}"
    try:
        if hasattr(character, "buffs"):
            character.buffs.remove(buff_key)
    except Exception:
        pass


# ── Settle scheduler ──────────────────────────────────────────────────────

def _schedule_rune_settle(character_id, rune_key, applied_at):
    """
    Schedule the buff ramp-up and ambient messages for a freshly carved rune.
    Uses evennia.utils.delay with persistent=True so server restarts don't
    lose pending steps (Evennia re-fires persistent delays after reload).
    """
    from evennia.utils.search import search_object

    # Buff progression steps (skip step 0 — already applied at carve time)
    for i, (offset, value) in enumerate(RUNE_BUFF_SCHEDULE):
        if i == 0:
            continue
        delay(
            offset,
            _settle_buff_step,
            character_id,
            rune_key,
            value,
            persistent=True,
        )

    # Ambient messages
    rune = RUNES.get(rune_key, {})
    for i, offset in enumerate(SETTLE_OFFSETS):
        delay(
            offset,
            _settle_ambient_step,
            character_id,
            rune_key,
            i,
            persistent=True,
        )


def _settle_buff_step(character_id, rune_key, value):
    """Callback: advance rune buff to next value."""
    from evennia.utils.search import search_object

    results = search_object(f"#{character_id}")
    if not results:
        return
    character = results[0]
    runes = dict(getattr(character.db, "runes", None) or {})
    if rune_key not in runes:
        return
    runes[rune_key]["current_buff_value"] = value
    if value >= RUNE_FULL_BUFF_VALUE:
        runes[rune_key]["settled"] = True
    character.db.runes = runes
    _apply_rune_buff(character, rune_key, value)


def _settle_ambient_step(character_id, rune_key, message_index):
    """Callback: send an ambient settling message to the character."""
    from evennia.utils.search import search_object

    results = search_object(f"#{character_id}")
    if not results:
        return
    character = results[0]
    runes = dict(getattr(character.db, "runes", None) or {})
    if rune_key not in runes:
        return

    rune = RUNES.get(rune_key, {})
    rune_entry = runes[rune_key]
    body_part = rune_entry.get("body_part", "body")

    try:
        template = SETTLE_MESSAGES[message_index]
    except IndexError:
        return

    msg = template.format(
        rune=rune.get("display", rune_key.capitalize()),
        stat=rune.get("stat", ""),
        part=body_part,
        flavor=rune.get("flavor", ""),
    )
    character.msg(msg)


# ── Description helpers ───────────────────────────────────────────────────

def build_rune_description(rune_key, artist_text, character):
    """
    Build the colored description string stored in appended_descriptions.

    The rune name is wrapped in its color code; the rest of the text uses
    the character's skin tone. The rune name must appear somewhere in
    artist_text (validated before this is called).
    """
    rune = RUNES[rune_key]
    color = rune["color"]
    rune_display = rune["display"]
    skin_code = getattr(character.db, "skin_tone_code", None) or ""

    # Replace the rune name (case-insensitive) with the colored version.
    import re
    pattern = re.compile(re.escape(rune_display), re.IGNORECASE)
    colored_name = f"{color}{rune_display}|n"
    colored_text = pattern.sub(colored_name, artist_text, count=1)

    # Wrap non-colored segments in skin tone if available.
    if skin_code:
        # Prepend skin tone; after each |n reset, re-inject skin tone so
        # plain text segments read against skin rather than terminal default.
        colored_text = skin_code + colored_text.replace("|n", f"|n{skin_code}") + "|n"

    return colored_text


def _set_rune_description(character, rune_key, body_part, desc_text):
    """Write the rune description into appended_descriptions."""
    appended = dict(getattr(character.db, "appended_descriptions", None) or {})
    if body_part not in appended:
        appended[body_part] = {}
    appended[body_part][f"rune:{rune_key}"] = desc_text
    character.db.appended_descriptions = appended


def _clear_rune_description(character, rune_key, body_part):
    """Remove a rune description from appended_descriptions."""
    appended = dict(getattr(character.db, "appended_descriptions", None) or {})
    part_dict = appended.get(body_part, {})
    part_dict.pop(f"rune:{rune_key}", None)
    if not part_dict:
        appended.pop(body_part, None)
    else:
        appended[body_part] = part_dict
    character.db.appended_descriptions = appended


# ── Public API ────────────────────────────────────────────────────────────

def apply_rune(carver, target, rune_key, body_part, artist_text):
    """
    Carve a rune onto the target character.

    Stores rune data, applies initial partial buff, writes the description,
    deals damage, and schedules the settle sequence.

    Returns (success: bool, message: str).
    """
    rune = RUNES.get(rune_key)
    if not rune:
        return False, "Unknown rune."

    runes = dict(getattr(target.db, "runes", None) or {})
    if rune_key in runes:
        return False, f"The rune {rune['display']} is already carved on {target.key}."

    # Check body part not already occupied by any rune
    for existing_key, existing_data in runes.items():
        if existing_data.get("body_part") == body_part:
            existing_rune = RUNES.get(existing_key, {})
            return False, (
                f"{target.key}'s {body_part} already bears the rune "
                f"{existing_rune.get('display', existing_key)}."
            )

    carver_display = (
        carver.get_display_name(target)
        if hasattr(carver, "get_display_name")
        else carver.key
    )

    # Build and store description
    desc_text = build_rune_description(rune_key, artist_text, target)
    _set_rune_description(target, rune_key, body_part, desc_text)

    # Store rune data
    initial_value = RUNE_BUFF_SCHEDULE[0][1]
    runes[rune_key] = {
        "body_part": body_part,
        "description": desc_text,
        "color_code": rune["color"],
        "applied_at": time.time(),
        "settled": False,
        "current_buff_value": initial_value,
        "artist_id": carver.id,
        "artist_name": carver_display,
    }
    target.db.runes = runes

    # Apply initial partial buff
    _apply_rune_buff(target, rune_key, initial_value)

    # Deal damage (the ritual is painful)
    try:
        target.at_damage(None, 15)
    except Exception:
        try:
            current = int(getattr(target.db, "current_hp", 0) or 0)
            target.db.current_hp = max(1, current - 15)
        except Exception:
            pass

    # Schedule settle steps
    _schedule_rune_settle(target.id, rune_key, time.time())

    return True, ""


def remove_rune(character, rune_key):
    """
    Remove a rune from a character (staff/admin use).

    Clears the buff, description, and stored data.
    Returns (success: bool, message: str).
    """
    runes = dict(getattr(character.db, "runes", None) or {})
    if rune_key not in runes:
        rune = RUNES.get(rune_key, {})
        return False, f"No rune {rune.get('display', rune_key)} found on {character.key}."

    body_part = runes[rune_key].get("body_part", "")
    _remove_rune_buff(character, rune_key)
    _clear_rune_description(character, rune_key, body_part)
    del runes[rune_key]
    character.db.runes = runes
    rune = RUNES.get(rune_key, {})
    return True, f"Rune {rune.get('display', rune_key)} removed from {character.key}."


def clear_all_runes(character):
    """
    Remove all runes from a character (called on death / cloning).
    Clears buffs and appended_descriptions entries with 'rune:' prefix.
    """
    runes = dict(getattr(character.db, "runes", None) or {})
    for rune_key, rune_data in runes.items():
        _remove_rune_buff(character, rune_key)
        body_part = rune_data.get("body_part", "")
        if body_part:
            _clear_rune_description(character, rune_key, body_part)
    character.db.runes = {}

    # Belt-and-suspenders: strip any remaining rune: keys from appended_descriptions
    appended = dict(getattr(character.db, "appended_descriptions", None) or {})
    changed = False
    for part, part_dict in list(appended.items()):
        rune_keys = [k for k in list(part_dict.keys()) if k.startswith("rune:")]
        for k in rune_keys:
            del part_dict[k]
            changed = True
        if not part_dict:
            del appended[part]
    if changed:
        character.db.appended_descriptions = appended


def reapply_rune_buffs(character):
    """
    Re-apply all rune buffs after a server restart.
    Called from character.at_server_start().
    """
    runes = dict(getattr(character.db, "runes", None) or {})
    for rune_key, rune_data in runes.items():
        value = rune_data.get("current_buff_value", RUNE_BUFF_SCHEDULE[0][1])
        _apply_rune_buff(character, rune_key, value)
