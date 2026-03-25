"""
Rune carving commands.

Commands:
    carve <rune> onto <character> <body part>   — carve a rune onto a character

handle_pending_rune_input() is called from pending_dispatch.py to intercept
the multi-step description entry and confirmation flow.
"""

import random
import re

from evennia.utils import delay
from evennia.utils.search import search_object

from commands.base_cmds import Command
from world.runes.rune_data import (
    CARVE_FAIL_MESSAGES,
    CARVE_NARRATIVE,
    RUNES,
)

CARVE_CMD_COOLDOWN = 10


# ── Helpers ───────────────────────────────────────────────────────────────

def _check_cooldown(caller, key, seconds, msg):
    if not hasattr(caller, "cooldowns"):
        return False
    if not caller.cooldowns.ready(key):
        left = int(caller.cooldowns.time_left(key))
        caller.msg(msg.format(seconds=left))
        return True
    caller.cooldowns.add(key, int(seconds))
    return False


def _target_display_name(target, viewer):
    if hasattr(target, "get_display_name"):
        return target.get_display_name(viewer)
    return target.key


def _find_athame(character):
    """Return the first athame in the character's inventory, or None."""
    for obj in character.contents:
        if getattr(obj.db, "is_athame", False):
            return obj
    return None


def _find_lit_incense(character, incense_type):
    """
    Return the first lit incense of the given type in the character's inventory,
    or None.
    """
    for obj in character.contents:
        if not getattr(obj.db, "is_incense", False):
            continue
        if getattr(obj.db, "incense_type", None) != incense_type:
            continue
        if not getattr(obj.db, "is_lit", False):
            continue
        return obj
    return None


def _consume_incense(incense_obj):
    """Consume (delete) an incense item after use."""
    try:
        incense_obj.delete()
    except Exception:
        pass


def _resolve_body_part(part_str, target):
    """Resolve a body part string (with alias support) for a target character."""
    from world.body import get_character_body_parts
    from world.medical import BODY_PART_ALIASES

    parts = get_character_body_parts(target)
    part_str = part_str.strip().lower()

    if part_str in parts:
        return part_str

    resolved = BODY_PART_ALIASES.get(part_str)
    if resolved and resolved in parts:
        return resolved

    return None


def _sanitize_rune_text(text, rune_key):
    """
    Validate and sanitize rune description text.

    - Strips background color codes and raw ANSI.
    - Requires the rune name to appear somewhere in the text (case-insensitive).
    - Restricts color codes to the rune's permitted color only.
    - Returns (cleaned_text, error_string). error_string is empty on success.
    """
    if not text:
        return "", "Description cannot be empty."

    rune = RUNES[rune_key]
    rune_display = rune["display"]

    # Strip background color codes
    text = re.sub(r'\|\[[^\s]', '', text)
    # Strip raw ANSI escape sequences
    text = re.sub(r'\x1b\[[^m]*m', '', text)
    text = text.strip()

    if len(text) < 5:
        return "", "Description too short. Minimum 5 characters."
    if len(text) > 400:
        return "", f"Description too long ({len(text)} chars). Maximum 400 characters."

    # Rune name must be present
    if not re.search(re.escape(rune_display), text, re.IGNORECASE):
        return "", (
            f"The description must include the rune name '{rune_display}' "
            f"(case does not matter)."
        )

    # Strip any color codes that are NOT the rune's permitted color.
    # Permitted: the rune's own color code (e.g. |500), |n (reset), skin tone codes
    # are added at render time — we only allow the rune color here.
    permitted_color = rune["color"].lstrip("|")  # e.g. "500"
    # Remove all color codes except |n and the permitted one
    def _strip_unpermitted(m):
        code = m.group(1)
        if code == "n":
            return m.group(0)
        if code == permitted_color:
            return m.group(0)
        return ""
    text = re.sub(r'\|([a-zA-Z0-9=]{1,3})', _strip_unpermitted, text)
    text = text.strip()

    # Ensure color codes are closed
    has_color = bool(re.search(r'\|[a-zA-Z0-9=]{1,3}', text))
    if has_color and not text.endswith("|n"):
        text = f"{text}|n"

    return text, ""


# ── Pending input handler ─────────────────────────────────────────────────

def handle_pending_rune_input(caller, raw):
    """
    Handle pending rune carve input (description text + confirmation).
    Called from pending_dispatch. Returns True if input was consumed.
    """
    pending = getattr(caller.ndb, "_pending_rune_carve", None)
    if not pending:
        return False

    raw = (raw or "").strip()

    if raw.lower() == "cancel":
        try:
            del caller.ndb._pending_rune_carve
        except Exception:
            pass
        caller.msg("|xRune carving cancelled.|n")
        return True

    stage = pending.get("stage", "text")
    if stage == "text":
        _rune_stage_text(caller, raw, pending)
    elif stage == "confirm":
        _rune_stage_confirm(caller, raw, pending)

    return True


def _rune_stage_text(caller, raw, pending):
    """Receive the rune description text and show a preview."""
    rune_key = pending["rune_key"]
    rune = RUNES[rune_key]

    cleaned, err = _sanitize_rune_text(raw, rune_key)
    if err:
        caller.msg(f"|r{err}|n\nTry again or type |wcancel|n to abort.")
        return

    target_id = pending["target_id"]
    results = search_object(f"#{target_id}")
    target = results[0] if results else None
    if not target:
        caller.msg("|rTarget no longer found. Ritual cancelled.|n")
        try:
            del caller.ndb._pending_rune_carve
        except Exception:
            pass
        return

    body_part = pending["body_part"]
    target_name = _target_display_name(target, caller)
    color = rune["color"]

    caller.msg(
        f"|x{'═' * 52}|n\n"
        f"  |wPREVIEW — {rune['display'].upper()} on {target_name}'s {body_part}|n\n"
        f"|x{'═' * 52}|n\n"
        f"  {cleaned}\n"
        f"|x{'═' * 52}|n\n"
        f"  Rune color: {color}{rune['display']}|n  (only this color is permitted)\n"
        f"  Type |wyes|n to confirm, |wno|n to rewrite, |wcancel|n to abort."
    )

    pending["rune_text"] = cleaned
    pending["stage"] = "confirm"
    caller.ndb._pending_rune_carve = pending


def _rune_stage_confirm(caller, raw, pending):
    """Handle yes/no/rewrite on the confirmation prompt."""
    answer = raw.strip().lower()

    if answer in ("no", "n", "rewrite"):
        pending["stage"] = "text"
        pending.pop("rune_text", None)
        caller.ndb._pending_rune_carve = pending
        rune_key = pending["rune_key"]
        rune = RUNES[rune_key]
        caller.msg(
            f"|xRewrite the description for |w{rune['display']}|n|x. "
            f"It must include the word '{rune['display']}'. Type |wcancel|n to abort.|n"
        )
        return

    if answer not in ("yes", "y"):
        caller.msg("|xType |wyes|n to confirm, |wno|n to rewrite, or |wcancel|n to abort.|n")
        return

    # Confirmed — validate everything is still in place, then begin ritual
    rune_key = pending["rune_key"]
    target_id = pending["target_id"]
    body_part = pending["body_part"]
    rune_text = pending.get("rune_text", "")

    try:
        del caller.ndb._pending_rune_carve
    except Exception:
        pass

    results = search_object(f"#{target_id}")
    target = results[0] if results else None
    if not target:
        caller.msg("|rTarget no longer found. Ritual cancelled.|n")
        return

    rune = RUNES[rune_key]

    # Re-validate incense (must still be present and lit)
    incense = _find_lit_incense(caller, rune["incense"])
    if not incense:
        caller.msg(
            f"|rYou no longer have a lit {rune['incense_display']} incense. "
            f"The ritual cannot proceed.|n"
        )
        return

    # Re-validate athame
    athame = _find_athame(caller)
    if not athame:
        caller.msg("|rYour athame is gone. The ritual cannot proceed.|n")
        return

    # Re-validate room tag
    room = caller.location
    if not room or not room.tags.has("ceremony"):
        caller.msg("|rThis is no longer a ceremony space. The ritual cannot proceed.|n")
        return

    # Re-validate rune uniqueness
    runes = dict(getattr(target.db, "runes", None) or {})
    if rune_key in runes:
        caller.msg(
            f"|r{_target_display_name(target, caller)} already bears the rune "
            f"{rune['display']}.|n"
        )
        return

    for existing_key, existing_data in runes.items():
        if existing_data.get("body_part") == body_part:
            existing_rune = RUNES.get(existing_key, {})
            caller.msg(
                f"|rTheir {body_part} already bears the rune "
                f"{existing_rune.get('display', existing_key)}.|n"
            )
            return

    # Consume incense now
    _consume_incense(incense)

    # Perform skill roll
    tier, final_score = caller.roll_check(
        ["perception", "intelligence"], "occultism", difficulty=15
    )
    roll_failed = tier in ("Failure", "Critical Failure") or int(final_score or 0) < 0

    # Begin narrative sequence (room lines use msg_contents mapping so each
    # viewer sees recog-aware names via get_display_name(looker=receiver).)
    _begin_carve_narrative(
        room=room,
        carver=caller,
        target=target,
        rune_key=rune_key,
        body_part=body_part,
        rune_text=rune_text,
        roll_failed=roll_failed,
    )


# ── Narrative sequence ────────────────────────────────────────────────────

def _broadcast_rune_room_message(room_id, text_template, carver_id, target_id, rune_display, body_part):
    """
    Broadcast one line to the room with per-viewer recog names.

    Uses Evennia msg_contents mapping: {carver} and {target} are resolved via
    get_display_name(looker=receiver) for each recipient. {rune} and {part} are
    plain strings.
    """
    results = search_object(f"#{room_id}")
    if not results:
        return
    room = results[0]
    carver_results = search_object(f"#{carver_id}")
    target_results = search_object(f"#{target_id}")
    carver = carver_results[0] if carver_results else None
    target = target_results[0] if target_results else None
    if not carver or not target:
        return
    mapping = {
        "carver": carver,
        "target": target,
        "rune": rune_display,
        "part": body_part,
    }
    room.msg_contents(text_template, mapping=mapping)


def _begin_carve_narrative(
    room, carver, target, rune_key, body_part, rune_text, roll_failed,
):
    """Schedule all narrative delay steps for the carving ritual."""
    rune = RUNES[rune_key]
    room_id = room.id
    carver_id = carver.id
    target_id = target.id
    rune_display = rune["display"]

    for delay_secs, msg_template in CARVE_NARRATIVE:
        delay(
            delay_secs,
            _broadcast_rune_room_message,
            room_id,
            msg_template,
            carver_id,
            target_id,
            rune_display,
            body_part,
        )

    # After narrative: apply or fail
    narrative_end = CARVE_NARRATIVE[-1][0] + 2
    if roll_failed:
        fail_template = random.choice(CARVE_FAIL_MESSAGES)
        delay(
            narrative_end,
            _broadcast_rune_room_message,
            room_id,
            fail_template,
            carver_id,
            target_id,
            rune_display,
            body_part,
        )
    else:
        delay(
            narrative_end,
            _do_apply_rune,
            carver.id,
            target.id,
            rune_key,
            body_part,
            rune_text,
            room_id,
        )


def _do_apply_rune(carver_id, target_id, rune_key, body_part, rune_text, room_id):
    """Deferred callback: apply the rune after the narrative completes."""
    from world.runes.rune_system import apply_rune

    carver_results = search_object(f"#{carver_id}")
    target_results = search_object(f"#{target_id}")
    room_results = search_object(f"#{room_id}")

    carver = carver_results[0] if carver_results else None
    target = target_results[0] if target_results else None
    room = room_results[0] if room_results else None

    if not target:
        if carver:
            carver.msg("|rThe ritual failed: target could not be found.|n")
        return

    success, err = apply_rune(carver, target, rune_key, body_part, rune_text)

    rune = RUNES.get(rune_key, {})
    rune_display = rune.get("display", rune_key.capitalize())
    color = rune.get("color", "|w")

    if not success:
        if carver:
            carver.msg(f"|rRune application failed: {err}|n")
        return

    target_name_for_carver = (
        _target_display_name(target, carver) if carver else target.key
    )

    if carver:
        carver.msg(
            f"|=mThe ritual is complete. The mark of {color}{rune_display}|n|=m "
            f"rests on {target_name_for_carver}'s {body_part}.|n"
        )
    target.msg(
        f"|=mThe mark of {color}{rune_display}|n|=m has been carved into your "
        f"astral body. It burns with a cold, sourceless fire. "
        f"You will feel its full power settle over the next day.|n"
    )
    if room and carver:
        room.msg_contents(
            "|=m{carver} lowers the athame. The ritual is complete.|n",
            mapping={"carver": carver},
            exclude=[carver, target],
        )


# ── CmdIgnite ─────────────────────────────────────────────────────────────

def _find_ignite_target(caller, name):
    """Resolve an object by name in inventory, then in the room."""
    if not name:
        return None
    obj = caller.search(name, location=caller, quiet=True)
    if not obj and caller.location:
        obj = caller.search(name, location=caller.location, quiet=True)
    if not obj:
        return None
    return obj[0] if isinstance(obj, (list, tuple)) else obj


class CmdIgnite(Command):
    """
    Light ritual incense from your inventory (or from the ground at your feet).

    Incense must be lit before you begin a rune carving; the carve flow
    consumes the stick at confirmation time.

    Usage:
        ignite <incense>
        light incense <incense>

    Note: A bare |wlight|n command is not used here — it would conflict with
    skin tone and other phrases. Use |wignite|n or |wlight incense|n.

    Examples:
        ignite dragon
        light incense benzoin
    """

    key = "ignite"
    aliases = ["light incense"]
    locks = "cmd:all()"
    help_category = "Runes"

    def func(self):
        caller = self.caller
        raw = (self.args or "").strip()
        if not raw:
            caller.msg("Usage: |wignite <incense>|n or |wlight incense <incense>|n")
            return

        obj = _find_ignite_target(caller, raw)
        if not obj:
            caller.msg(f"You don't see '{raw}' here or in your inventory.")
            return

        if not getattr(obj.db, "is_incense", False):
            caller.msg("You can only |wignite|n sticks of ritual incense.")
            return

        if getattr(obj.db, "is_lit", False):
            caller.msg(f"{obj.get_display_name(caller) if hasattr(obj, 'get_display_name') else obj.key} is already lit.")
            return

        obj.db.is_lit = True
        display = obj.get_display_name(caller) if hasattr(obj, "get_display_name") else obj.key
        caller.msg(
            f"You touch flame to {display}. A thin thread of smoke rises, "
            f"carrying a scent that seems to linger at the edge of sense."
        )
        loc = caller.location
        if loc:
            cname = caller.get_display_name(caller) if hasattr(caller, "get_display_name") else caller.key
            loc.msg_contents(
                f"{cname} lights {display}. Smoke curls upward in a slow spiral.",
                exclude=caller,
            )


# ── CmdCarve ──────────────────────────────────────────────────────────────

class CmdCarve(Command):
    """
    Carve a rune onto another character's body. Requires:
      - A ritual athame in your inventory.
      - A lit incense of the correct type for the chosen rune.
      - Both you and the target must be in a room tagged 'ceremony'.
      - The target's trust (runecarve category).

    The rune name must appear in the description you write.
    A rune can only be applied once per body (no duplicates).
    Different runes may be applied to different body parts, but no two
    runes may share the same body part.

    Usage:
        carve <rune> onto <character> <body part>

    Runes and their required incense:
        thurisaz  (strength)     — Dragon's Blood incense
        ansuz     (charisma)     — Benzoin incense
        raidho    (agility)      — Peppermint incense
        mannaz    (intelligence) — Frankincense incense
        nauthiz   (endurance)    — Myrrh incense
        kenaz     (perception)   — Sage incense
        jera      (luck)         — Cinnamon incense

    Examples:
        carve ansuz onto Mira left forearm
        carve thurisaz onto Dex chest
        carve jera onto Sable right hand
    """

    key = "carve"
    locks = "cmd:all()"
    help_category = "Runes"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()

        if _check_cooldown(
            caller,
            "rune_carve",
            CARVE_CMD_COOLDOWN,
            "|yYou need a moment before attempting another ritual ({seconds}s).|n",
        ):
            return

        if not args or " onto " not in args:
            caller.msg("Usage: |wcarve <rune> onto <character> <body part>|n")
            return

        rune_part, _, rest = args.partition(" onto ")
        rune_key = rune_part.strip().lower()
        rest = rest.strip()

        if rune_key not in RUNES:
            rune_list = ", ".join(sorted(RUNES.keys()))
            caller.msg(
                f"|rUnknown rune '{rune_key}'.|n\n"
                f"Valid runes: |w{rune_list}|n"
            )
            return

        rune = RUNES[rune_key]

        # Parse "<character name> <body part>"
        # Try progressively shorter target names (greedy left match) until we
        # find a target AND a valid body part for the remainder.
        words = rest.split()
        if len(words) < 2:
            caller.msg(
                "Usage: |wcarve <rune> onto <character> <body part>|n\n"
                "You must specify both a character and a body part."
            )
            return

        target = None
        body_part = None
        for split_at in range(len(words) - 1, 0, -1):
            target_str = " ".join(words[:split_at])
            part_str = " ".join(words[split_at:]).lower()
            found = caller.search(target_str, location=caller.location, quiet=True)
            if not found:
                continue
            t = found[0] if isinstance(found, list) else found
            bp = _resolve_body_part(part_str, t)
            if bp:
                target = t
                body_part = bp
                break
            # Found target but body part didn't resolve — keep for error reporting
            if target is None:
                target = t
                body_part = part_str

        if not target:
            caller.msg(f"|rCould not find a character matching '{words[0]}' here.|n")
            return

        if target == caller:
            caller.msg("|rYou cannot carve runes onto yourself.|n")
            return

        if not body_part or _resolve_body_part(body_part, target) is None:
            from world.body import get_character_body_parts
            parts = get_character_body_parts(target)
            caller.msg(
                f"|rThey don't have a body part matching '{body_part}'.|n\n"
                f"Valid parts: {', '.join(sorted(parts))}"
            )
            return

        # ── Validate room ──────────────────────────────────────────────────
        room = caller.location
        if not room or not room.tags.has("ceremony"):
            caller.msg(
                "|rThis place is not consecrated for the ritual. "
                "You must be in a ceremony space to carve runes.|n"
            )
            return

        # ── Validate athame ────────────────────────────────────────────────
        athame = _find_athame(caller)
        if not athame:
            caller.msg(
                "|rYou need a ritual athame to carve runes.|n"
            )
            return

        # ── Validate incense ───────────────────────────────────────────────
        incense = _find_lit_incense(caller, rune["incense"])
        if not incense:
            caller.msg(
                f"|rYou need a lit {rune['incense_display']} incense to carve "
                f"{rune['display']}. Make sure it is lit before beginning the ritual.|n"
            )
            return

        # ── Validate trust ─────────────────────────────────────────────────
        from world.rpg.trust import check_trust
        if not check_trust(target, caller, "runecarve"):
            target_name = _target_display_name(target, caller)
            caller.msg(
                f"{target_name} does not trust you to carve runes onto them. "
                f"They must |w@trust|n you for the 'runecarve' category."
            )
            return

        # ── Validate rune uniqueness ───────────────────────────────────────
        existing_runes = dict(getattr(target.db, "runes", None) or {})
        if rune_key in existing_runes:
            target_name = _target_display_name(target, caller)
            caller.msg(
                f"|r{target_name} already bears the rune {rune['display']}. "
                f"A rune cannot be carved twice onto the same body.|n"
            )
            return

        for existing_key, existing_data in existing_runes.items():
            if existing_data.get("body_part") == body_part:
                existing_rune = RUNES.get(existing_key, {})
                caller.msg(
                    f"|rTheir {body_part} already bears the rune "
                    f"{existing_rune.get('display', existing_key)}. "
                    f"Each body part may only hold one rune.|n"
                )
                return

        # ── Prompt for description ─────────────────────────────────────────
        target_name = _target_display_name(target, caller)
        color = rune["color"]

        caller.msg(
            f"|x{'═' * 56}|n\n"
            f"  |wCARVING {rune['display'].upper()} — {body_part.upper()} on {target_name}|n\n"
            f"|x{'═' * 56}|n\n"
            f"  Rune: {color}{rune['display']}|n — {rune['flavor'].capitalize()}\n"
            f"  Required incense: {rune['incense_display']}\n"
            f"\n"
            f"  Write a description of how the rune appears on {target_name}'s {body_part}.\n"
            f"  The word '{rune['display']}' MUST appear somewhere in the text.\n"
            f"  Only the rune's color ({color}{rune['display']}|n) may be used.\n"
            f"  Maximum 400 characters.\n"
            f"\n"
            f"  Type |wcancel|n to abort.\n"
            f"|x{'═' * 56}|n"
        )

        caller.ndb._pending_rune_carve = {
            "target_id": target.id,
            "body_part": body_part,
            "rune_key": rune_key,
            "stage": "text",
        }
