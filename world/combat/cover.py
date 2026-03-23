"""
Cover and suppression logic for combat.
"""

from __future__ import annotations

import random
import time

from world.theme_colors import COMBAT_COLORS as CC

COVER_EXPOSED = 0
COVER_LIGHT = 1
COVER_HEAVY = 2
COVER_FORTIFIED = 3

COVER_LABELS = {
    COVER_EXPOSED: "exposed",
    COVER_LIGHT: "light",
    COVER_HEAVY: "heavy",
    COVER_FORTIFIED: "fortified",
}

COVER_DEFENSE_BONUS = {
    COVER_EXPOSED: 0,
    COVER_LIGHT: 8,
    COVER_HEAVY: 18,
    COVER_FORTIFIED: 28,
}

COVER_AUTOMATIC_DEFENSE_BONUS = {
    COVER_EXPOSED: 0,
    COVER_LIGHT: 0,
    COVER_HEAVY: 5,
    COVER_FORTIFIED: 12,
}

COVER_DAMAGE_REDUCTION = {
    COVER_EXPOSED: 0.0,
    COVER_LIGHT: 0.15,
    COVER_HEAVY: 0.35,
    COVER_FORTIFIED: 0.55,
}

COVER_HP_BY_QUALITY = {
    COVER_LIGHT: 40,
    COVER_HEAVY: 80,
    COVER_FORTIFIED: 150,
}

SUPPRESSION_DURATION = 5.0
SUPPRESSED_ATTACK_PENALTY_EXPOSED = -8
SUPPRESSED_FLEE_PENALTY = -10
SUPPRESSED_COVER_BONUS_MULTIPLIER = 0.5


def _clamp_quality(value):
    return max(COVER_EXPOSED, min(COVER_FORTIFIED, int(value or 0)))


def _room_cover_default_flavors(quality):
    if quality >= COVER_FORTIFIED:
        return ["a fortified position"]
    if quality >= COVER_HEAVY:
        return ["solid cover nearby"]
    return ["whatever cover is available"]


def _iter_room_characters(room):
    if not room or not hasattr(room, "contents_get"):
        return []
    return list(room.contents_get(content_type="character"))


def _cover_room_quality(room):
    return _clamp_quality(getattr(room.db, "cover_quality", COVER_LIGHT) or COVER_LIGHT)


def _cover_room_available(room):
    if not room:
        return False
    return bool(getattr(room.db, "cover_available", True))


def _cover_room_capacity(room):
    return max(0, int(getattr(room.db, "cover_capacity", 4) or 4))


def _cover_room_flavors(room):
    quality = _cover_room_quality(room)
    flavors = getattr(room.db, "cover_flavor", None)
    if isinstance(flavors, (list, tuple)) and flavors:
        return [str(f).strip() for f in flavors if str(f).strip()]
    return _room_cover_default_flavors(quality)


def _pick_cover_flavor(room, quality, degraded=False):
    """
    Pick flavor text for current cover quality.
    Supports room.db.cover_flavor as either:
      - list[str] (shared pool)
      - dict[quality -> list[str]]
    """
    flavors = getattr(getattr(room, "db", None), "cover_flavor", None)
    if isinstance(flavors, dict):
        raw = flavors.get(quality) or flavors.get(str(quality)) or []
        options = [str(f).strip() for f in raw if str(f).strip()]
        if options:
            return random.choice(options)
        if degraded:
            return "the remains of your cover"
    base = _cover_room_flavors(room)
    if base:
        return random.choice(base)
    return "the remains of your cover" if degraded else "whatever cover is available"


def _vulnerability_multiplier(room, damage_type):
    vulns = getattr(room.db, "cover_damage_vulnerabilities", None) or {}
    try:
        return float(vulns.get(damage_type, 1.0))
    except Exception:
        return 1.0


def ensure_room_cover_state(room):
    if not room:
        return
    quality = _cover_room_quality(room)
    room.db.cover_quality = quality
    if getattr(room.db, "cover_available", None) is None:
        room.db.cover_available = True
    if getattr(room.db, "cover_capacity", None) is None:
        room.db.cover_capacity = 4
    # Room does not track durability pool; per-character cover HP is used.


def mark_room_combat_activity(room):
    return


def maybe_reset_room_cover(room):
    return


def in_cover_count(room):
    return sum(1 for c in _iter_room_characters(room) if getattr(c.db, "in_cover", False))


def clear_cover_state(character, reset_pose=True):
    if not character or not getattr(character, "db", None):
        return
    character.db.in_cover = False
    character.db.cover_quality = COVER_EXPOSED
    character.db.cover_flavor_text = ""
    character.db.cover_hp = 0
    pose = getattr(character.db, "room_pose", None) or ""
    if reset_pose and pose.startswith("crouching behind "):
        character.db.room_pose = "standing here"


def force_leave_cover(character, reason_msg=None):
    if not character or not getattr(character.db, "in_cover", False):
        return False
    clear_cover_state(character, reset_pose=True)
    if reason_msg and hasattr(character, "msg"):
        character.msg(reason_msg)
    return True


def can_take_cover(character):
    if not character or not getattr(character, "location", None):
        return False, "You can't find cover here."
    room = character.location
    ensure_room_cover_state(room)
    maybe_reset_room_cover(room)
    if not _cover_room_available(room):
        return False, "There's nowhere to take cover here."
    if getattr(character.db, "in_cover", False):
        return False, "You're already in cover."
    if in_cover_count(room) >= _cover_room_capacity(room):
        return False, "There's no cover left - every position is taken."
    return True, None


def try_take_cover(character, difficulty=10):
    ok, err = can_take_cover(character)
    if not ok:
        return False, err, None
    if getattr(character.db, "grappled_by", None):
        return False, "You're locked in a grapple.", None
    if not hasattr(character, "roll_check"):
        return False, "You fail to find a good position.", None
    _res, val = character.roll_check(["agility"], "evasion", modifier=0)
    if int(val or 0) <= int(difficulty):
        return False, "You fail to find a good position this round.", None
    room = character.location
    flavor = _pick_cover_flavor(room, _cover_room_quality(room), degraded=False)
    quality = _cover_room_quality(room)
    character.db.in_cover = True
    character.db.cover_quality = quality
    character.db.cover_hp = int(COVER_HP_BY_QUALITY.get(quality, 0))
    character.db.cover_flavor_text = flavor
    character.db.room_pose = f"crouching behind {flavor}"
    return True, flavor, quality


def character_in_cover(character):
    """True when the character has taken a cover action this fight (handles odd DB truthiness)."""
    if not character or not getattr(character, "db", None):
        return False
    v = getattr(character.db, "in_cover", False)
    if v is True:
        return True
    try:
        return int(v) == 1
    except (TypeError, ValueError):
        return False


def get_cover_status_text(character):
    if not character or not getattr(character, "db", None):
        return "exposed"
    if not character_in_cover(character):
        return "exposed"
    quality = _clamp_quality(getattr(character.db, "cover_quality", COVER_LIGHT))
    label = COVER_LABELS.get(quality, "cover")
    flavor = (getattr(character.db, "cover_flavor_text", None) or "").strip()
    if flavor:
        return f"in cover ({flavor})"
    return f"in cover ({label})"


def set_suppressed(character, duration=SUPPRESSION_DURATION):
    if character and getattr(character, "db", None):
        character.db.suppressed_until = time.time() + float(duration)


def clear_suppression(character):
    if character and getattr(character, "db", None):
        character.db.suppressed_until = 0.0


def is_suppressed(character):
    if not character or not getattr(character, "db", None):
        return False
    return float(getattr(character.db, "suppressed_until", 0.0) or 0.0) > time.time()


def get_suppressed_attack_penalty(attacker):
    if is_suppressed(attacker) and not getattr(attacker.db, "in_cover", False):
        return SUPPRESSED_ATTACK_PENALTY_EXPOSED
    return 0


def get_suppressed_flee_penalty(character):
    return SUPPRESSED_FLEE_PENALTY if is_suppressed(character) else 0


def is_pinned_by_suppression(character):
    return is_suppressed(character) and not getattr(character.db, "in_cover", False)


def get_cover_defense_bonus(defender, weapon_key):
    """Defense bonus from cover quality only (no nominal range or damage-type split)."""
    if not defender or not getattr(defender.db, "in_cover", False):
        return 0
    quality = _clamp_quality(getattr(defender.db, "cover_quality", COVER_EXPOSED))
    if quality <= COVER_EXPOSED:
        return 0
    base = COVER_DEFENSE_BONUS[quality]
    if weapon_key == "automatic":
        base += COVER_AUTOMATIC_DEFENSE_BONUS[quality]
    if is_suppressed(defender):
        base = int(round(base * SUPPRESSED_COVER_BONUS_MULTIPLIER))
    return base


def _broadcast_room(room, line):
    if not room or not hasattr(room, "contents_get"):
        return
    for viewer in room.contents_get(content_type="character"):
        viewer.msg(line)


def apply_cover_damage_reduction(attacker, defender, damage, damage_type):
    """
    Apply post-armor cover reduction and per-character cover degradation.
    Returns final_damage.
    """
    if damage <= 0 or not defender or not getattr(defender, "location", None):
        return damage
    room = defender.location
    mark_room_combat_activity(room)
    if not getattr(defender.db, "in_cover", False):
        return damage
    quality = _clamp_quality(getattr(defender.db, "cover_quality", COVER_EXPOSED))
    if quality <= COVER_EXPOSED:
        return damage
    pct = COVER_DAMAGE_REDUCTION.get(quality, 0.0)
    absorbed = int(round(damage * pct))
    if absorbed <= 0:
        return damage
    current_hp = int(getattr(defender.db, "cover_hp", 0) or 0)
    if current_hp <= 0:
        current_hp = int(COVER_HP_BY_QUALITY.get(quality, 0))
    mult = _vulnerability_multiplier(room, damage_type)
    pool_damage = max(1, int(round(absorbed * mult)))
    defender.db.cover_hp = current_hp - pool_damage
    _handle_cover_degradation(defender)
    return max(0, damage - absorbed)


def _handle_cover_degradation(defender):
    if not defender or not getattr(defender, "db", None):
        return
    room = getattr(defender, "location", None)
    quality = _clamp_quality(getattr(defender.db, "cover_quality", COVER_EXPOSED))
    hp = int(getattr(defender.db, "cover_hp", 0) or 0)
    if quality <= COVER_EXPOSED:
        return
    while quality > COVER_EXPOSED and hp <= 0:
        quality -= 1
        if quality > COVER_EXPOSED:
            hp = int(COVER_HP_BY_QUALITY.get(quality, 0))
            defender.db.cover_quality = quality
            defender.db.cover_hp = hp
            defender.db.cover_flavor_text = _pick_cover_flavor(room, quality, degraded=True)
            defender.msg(CC["miss"] + "Your cover is shot to pieces. You scramble to what's left.|n")
            if defender.db.cover_flavor_text:
                defender.db.room_pose = f"crouching behind {defender.db.cover_flavor_text}"
        else:
            defender.db.cover_quality = COVER_EXPOSED
            defender.db.cover_hp = 0
            force_leave_cover(defender, reason_msg=CC["miss"] + "The last of your cover disintegrates. You're exposed.|n")
            break
