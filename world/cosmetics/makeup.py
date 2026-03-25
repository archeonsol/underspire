"""
Makeup application, wear-off logic, and color catalogs.

Makeup is temporary: stored on db.active_makeup as a list of entries.
Each entry expires after a duration (seconds) or room transition count.
Makeup does NOT persist through death/cloning.
"""

import time

from world.cosmetics import MAKEUP_TYPES


# ── Color catalogs ────────────────────────────────────────────────────────

LIPSTICK_COLORS = {
    # Reds
    "siren":        {"name": "siren red",    "code": "|R"},
    "bloodmoon":    {"name": "bloodmoon",    "code": "|r"},
    "brick":        {"name": "brick",        "code": "|300"},
    "scarlet":      {"name": "scarlet",      "code": "|500"},
    "cherry":       {"name": "cherry",       "code": "|400"},
    "wine":         {"name": "wine",         "code": "|200"},
    "crimson":      {"name": "crimson",      "code": "|510"},
    # Pinks
    "blush":        {"name": "blush",        "code": "|513"},
    "rose":         {"name": "rose",         "code": "|412"},
    "petal":        {"name": "petal",        "code": "|524"},
    "bubblegum":    {"name": "bubblegum",    "code": "|515"},
    "flamingo":     {"name": "flamingo",     "code": "|514"},
    "coral":        {"name": "coral",        "code": "|520"},
    # Darks
    "black_cherry": {"name": "black cherry", "code": "|100"},
    "venom":        {"name": "venom",        "code": "|x"},
    "nightshade":   {"name": "nightshade",   "code": "|101"},
    "bruise":       {"name": "bruise",       "code": "|201"},
    "oxblood":      {"name": "oxblood",      "code": "|200"},
    # Nudes / Neutrals
    "bare":         {"name": "bare",         "code": "|321"},
    "dust":         {"name": "dust",         "code": "|332"},
    "tawny":        {"name": "tawny",        "code": "|420"},
    "fawn":         {"name": "fawn",         "code": "|321"},
    "cinnamon":     {"name": "cinnamon",     "code": "|310"},
    # Unconventional
    "rust":         {"name": "rust",         "code": "|310"},
    "copper":       {"name": "copper",       "code": "|530"},
    "gold_leaf":    {"name": "gold leaf",    "code": "|Y"},
    "chrome":       {"name": "chrome",       "code": "|W"},
    "void":         {"name": "void",         "code": "|x"},
}

EYE_SHADOW_COLORS = {
    # Smoky / Dark
    "smoke":        {"name": "smoke",        "code": "|=h"},
    "charcoal":     {"name": "charcoal",     "code": "|=d"},
    "soot":         {"name": "soot",         "code": "|x"},
    "ash":          {"name": "ash",          "code": "|=j"},
    "graphite":     {"name": "graphite",     "code": "|=f"},
    "thunder":      {"name": "thunder",      "code": "|=e"},
    # Warm / Earth
    "bronze":       {"name": "bronze",       "code": "|530"},
    "copper":       {"name": "copper",       "code": "|520"},
    "rust":         {"name": "rust",         "code": "|310"},
    "cinnamon":     {"name": "cinnamon",     "code": "|420"},
    "sienna":       {"name": "sienna",       "code": "|310"},
    "amber":        {"name": "amber",        "code": "|Y"},
    "honey":        {"name": "honey",        "code": "|530"},
    "toffee":       {"name": "toffee",       "code": "|320"},
    "clay":         {"name": "clay",         "code": "|210"},
    # Cool / Jewel
    "sapphire":     {"name": "sapphire",     "code": "|004"},
    "cobalt":       {"name": "cobalt",       "code": "|013"},
    "slate":        {"name": "slate",        "code": "|=i"},
    "plum":         {"name": "plum",         "code": "|201"},
    "amethyst":     {"name": "amethyst",     "code": "|303"},
    "orchid":       {"name": "orchid",       "code": "|413"},
    "verdigris":    {"name": "verdigris",    "code": "|031"},
    "jade":         {"name": "jade",         "code": "|030"},
    "moss":         {"name": "moss",         "code": "|120"},
    "peacock":      {"name": "peacock",      "code": "|024"},
    # Shimmer / Metallic
    "gold":         {"name": "gold",         "code": "|Y"},
    "silver":       {"name": "silver",       "code": "|W"},
    "pearl":        {"name": "pearl",        "code": "|=v"},
    "champagne":    {"name": "champagne",    "code": "|543"},
    "gunmetal":     {"name": "gunmetal",     "code": "|=g"},
}

EYELINER_COLORS = {
    "pitch":        {"name": "pitch black",  "code": "|x"},
    "kohl":         {"name": "kohl",         "code": "|=c"},
    "charcoal":     {"name": "charcoal",     "code": "|=e"},
    "smoke":        {"name": "smoke",        "code": "|=h"},
    "brown":        {"name": "dark brown",   "code": "|210"},
    "espresso":     {"name": "espresso",     "code": "|100"},
    "navy":         {"name": "navy",         "code": "|003"},
    "hunter":       {"name": "hunter green", "code": "|020"},
    "plum":         {"name": "plum",         "code": "|201"},
    "bronze":       {"name": "bronze",       "code": "|530"},
    "copper":       {"name": "copper",       "code": "|520"},
    "gold":         {"name": "gold",         "code": "|Y"},
    "silver":       {"name": "silver",       "code": "|W"},
    "white":        {"name": "white",        "code": "|w"},
    "crimson":      {"name": "crimson",      "code": "|R"},
}

NAIL_POLISH_COLORS = {
    # Classic
    "siren":        {"name": "siren red",    "code": "|R"},
    "scarlet":      {"name": "scarlet",      "code": "|500"},
    "cherry":       {"name": "cherry",       "code": "|400"},
    "wine":         {"name": "wine",         "code": "|200"},
    "bloodmoon":    {"name": "bloodmoon",    "code": "|r"},
    # Pink
    "blush":        {"name": "blush",        "code": "|513"},
    "rose":         {"name": "rose",         "code": "|412"},
    "coral":        {"name": "coral",        "code": "|520"},
    "flamingo":     {"name": "flamingo",     "code": "|514"},
    "bubblegum":    {"name": "bubblegum",    "code": "|515"},
    # Dark
    "obsidian":     {"name": "obsidian",     "code": "|x"},
    "nightshade":   {"name": "nightshade",   "code": "|101"},
    "bruise":       {"name": "bruise",       "code": "|201"},
    "oxblood":      {"name": "oxblood",      "code": "|200"},
    "tar":          {"name": "tar",          "code": "|=b"},
    "ink":          {"name": "ink",          "code": "|003"},
    # Neutral
    "nude":         {"name": "nude",         "code": "|321"},
    "fawn":         {"name": "fawn",         "code": "|432"},
    "sand":         {"name": "sand",         "code": "|543"},
    "bone":         {"name": "bone",         "code": "|=u"},
    "clear":        {"name": "clear coat",   "code": "|=v"},
    # Bold
    "electric":     {"name": "electric blue","code": "|015"},
    "acid":         {"name": "acid green",   "code": "|050"},
    "ultraviolet":  {"name": "ultraviolet",  "code": "|305"},
    "neon_orange":  {"name": "neon orange",  "code": "|530"},
    "canary":       {"name": "canary",       "code": "|550"},
    # Metallic
    "chrome":       {"name": "chrome",       "code": "|W"},
    "gold":         {"name": "gold",         "code": "|Y"},
    "copper":       {"name": "copper",       "code": "|520"},
    "gunmetal":     {"name": "gunmetal",     "code": "|=g"},
    "rust":         {"name": "rust",         "code": "|310"},
}

MAKEUP_COLOR_CATALOGS = {
    "lipstick": LIPSTICK_COLORS,
    "eye_shadow": EYE_SHADOW_COLORS,
    "eyeliner": EYELINER_COLORS,
    "nail_polish": NAIL_POLISH_COLORS,
}


# ── Application ───────────────────────────────────────────────────────────

def apply_makeup(applier, target, makeup_item):
    """
    Apply a makeup item to the target character.

    Handles trust check (skipped for self-application), body part resolution,
    description building, active_makeup storage, use consumption, and buff application.

    Returns (success: bool, message: str).
    """
    from world.body import is_part_present

    makeup_type = getattr(makeup_item.db, "makeup_type", None) or ""
    type_info = MAKEUP_TYPES.get(makeup_type)
    if not type_info:
        return False, "Unknown makeup type."

    if applier != target:
        from world.rpg.trust import check_trust
        if not check_trust(target, applier, "makeup"):
            return False, "They don't trust you to apply cosmetics."

    color_name = (getattr(makeup_item.db, "makeup_color_name", None) or "").strip()
    color_code = (getattr(makeup_item.db, "makeup_color_code", None) or "").strip()

    if not color_name or not color_code:
        return False, "This makeup has no color set. Use |wcolor <item> <color>|n first."

    target_parts = list(type_info["target_parts"])
    applied_parts = _resolve_target_parts(target, target_parts, type_info.get("fallback_rule"))

    if not applied_parts:
        return False, "No valid body parts to apply to."

    gender = getattr(target.db, "gender", None) or "neutral"
    pronoun = {"male": "His", "female": "Her", "neutral": "Their"}.get(gender, "Their")

    desc_text = type_info["desc_template"].format(
        pronoun=pronoun,
        color_name=color_name,
        color_code=color_code,
    )

    active_makeup = list(getattr(target.db, "active_makeup", None) or [])

    # Reapplication of same type on same parts replaces existing entry
    active_makeup = [
        m for m in active_makeup
        if not (
            m.get("makeup_type") == makeup_type
            and set(m.get("parts", [])) & set(applied_parts)
        )
    ]

    now = time.time()
    active_makeup.append({
        "makeup_type": makeup_type,
        "parts": applied_parts,
        "desc_text": desc_text,
        "color_name": color_name,
        "color_code": color_code,
        "applied_at": now,
        "wear_until": now + type_info.get("wear_duration", 7200),
        "wear_rooms_left": type_info.get("wear_rooms", 100),
        "applied_by": applier.id,
    })

    target.db.active_makeup = active_makeup

    # Apply charisma buff (same-type buff key prevents stacking)
    _apply_makeup_buff(target, makeup_type, type_info.get("wear_duration", 7200))

    # Consume a use
    uses = int(getattr(makeup_item.db, "uses_remaining", 0) or 0)
    if uses <= 1:
        applier.msg(f"|xThe {makeup_item.key} is used up.|n")
        makeup_item.delete()
    else:
        makeup_item.db.uses_remaining = uses - 1

    return True, ""


def _apply_makeup_buff(character, makeup_type, duration):
    """Apply the appropriate charisma buff for this makeup type."""
    try:
        from typeclasses.cosmetic_items import (
            LipstickBuff, NailPolishBuff, EyeShadowBuff, EyelinerBuff
        )
        buff_map = {
            "lipstick": LipstickBuff,
            "nail_polish": NailPolishBuff,
            "eye_shadow": EyeShadowBuff,
            "eyeliner": EyelinerBuff,
        }
        buff_cls = buff_map.get(makeup_type)
        if buff_cls and hasattr(character, "buffs"):
            character.buffs.add(buff_cls, stacks=1, duration=duration)
    except Exception:
        pass


def _resolve_target_parts(character, target_parts, fallback_rule):
    """
    Determine which body parts the makeup actually applies to,
    accounting for missing/severed parts and fallback rules.
    """
    from world.body import is_part_present

    available = [p for p in target_parts if is_part_present(character, p)]

    if available:
        return available

    if fallback_rule == "left_then_right":
        if is_part_present(character, "right hand"):
            return ["right hand"]
        return []

    if fallback_rule == "both_or_available":
        result = []
        for part in ("left eye", "right eye"):
            if is_part_present(character, part):
                result.append(part)
        return result

    return []


# ── Display ───────────────────────────────────────────────────────────────

def get_makeup_display_for_part(character, body_part):
    """
    Return the active makeup description text for a body part, or empty string.
    Skips expired entries (time or room-count based).
    Called by the appearance pipeline after the tattoo layer.
    """
    active = getattr(character.db, "active_makeup", None) or []
    if not active:
        return ""

    now = time.time()
    lines = []

    for entry in active:
        if now >= entry.get("wear_until", 0):
            continue
        if entry.get("wear_rooms_left", 1) <= 0:
            continue
        if body_part in entry.get("parts", []):
            text = entry.get("desc_text", "")
            if text:
                lines.append(text)

    return " ".join(lines)


# ── Wear-off tick ─────────────────────────────────────────────────────────

def tick_makeup_expiry(character):
    """
    Remove expired makeup entries from a character. Notifies the character
    for each type that fades. Called from a global tick or scheduled delay.
    """
    active = list(getattr(character.db, "active_makeup", None) or [])
    if not active:
        return

    now = time.time()
    expired = []
    remaining = []

    for entry in active:
        if now >= entry.get("wear_until", 0) or entry.get("wear_rooms_left", 1) <= 0:
            expired.append(entry)
        else:
            remaining.append(entry)

    if expired:
        character.db.active_makeup = remaining
        for entry in expired:
            mtype = entry.get("makeup_type", "cosmetic")
            type_info = MAKEUP_TYPES.get(mtype, {})
            type_name = type_info.get("name", mtype)
            character.msg(f"|xYour {type_name.lower()} has worn off.|n")


def decrement_makeup_room_count(character):
    """
    Decrement the room-transition counter for all active makeup entries.
    Call this whenever the character moves to a new room.
    """
    active = list(getattr(character.db, "active_makeup", None) or [])
    if not active:
        return

    changed = False
    for entry in active:
        rooms_left = entry.get("wear_rooms_left", 0)
        if rooms_left > 0:
            entry["wear_rooms_left"] = rooms_left - 1
            changed = True

    if changed:
        character.db.active_makeup = active
        tick_makeup_expiry(character)
