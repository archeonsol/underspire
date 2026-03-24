"""
Cosmetic commands: tattooing and makeup application.

Commands:
    ink <body part> on <character>              — tattoo another character
    remove tattoo <n> from <part> on <target>   — remove/scar a tattoo
    tattoos [<target>]                          — view tattoos on a character
    apply <item> [to <target>]                  — apply makeup
    wipe <type|all>                             — remove own makeup
    color <item> <color>                        — set color on a changeable makeup item
    colors <item>                               — list available colors for an item

handle_pending_cosmetic_input() is called from CmdNoMatch in roleplay_cmds.py
to intercept multi-step tattoo and makeup color-pick flows.
"""

import re
import time

from evennia.utils import delay

from commands.base_cmds import Command
from world.cosmetics import MAKEUP_TYPES, TATTOO_QUALITY_TIERS
from world.cosmetics.tattoos import TATTOO_RP_MESSAGES

INK_CMD_COOLDOWN = 3
REMOVE_TATTOO_COOLDOWN = 4
TATTOOS_CMD_COOLDOWN = 2
TATTOO_ACTION_TOTAL_DELAY = 28

REMOVE_TATTOO_RP_MESSAGES = [
    "{artist} sterilizes the needle array and studies {target}'s {part}.",
    "{artist} begins breaking up old pigment from {target}'s {part}.",
    "{artist} works in careful passes, wiping away fluid and ink traces.",
    "{artist} leans in, refining the removal around the edges of the mark.",
    "{artist} pauses to inspect the skin before making a final pass.",
]


# ── Helpers ───────────────────────────────────────────────────────────────

def _check_cooldown(caller, key, seconds, msg):
    """
    Shared cooldown gate for cosmetic commands.
    Returns True if command should stop due to cooldown.
    """
    if not hasattr(caller, "cooldowns"):
        return False
    if not caller.cooldowns.ready(key):
        left = int(caller.cooldowns.time_left(key))
        caller.msg(msg.format(seconds=left))
        return True
    caller.cooldowns.add(key, int(seconds))
    return False

def _find_inkwriter(character):
    """Return the first inkwriter in the character's inventory, or None."""
    for obj in character.contents:
        if getattr(obj.db, "is_inkwriter", False):
            return obj
    return None


def _find_makeup_item(character, item_name):
    """Find a makeup item in the character's inventory by name."""
    item_name = item_name.strip().lower()
    for obj in character.contents:
        if not getattr(obj.db, "is_makeup", False):
            continue
        if item_name in obj.key.lower():
            return obj
        mtype = getattr(obj.db, "makeup_type", "") or ""
        type_display = MAKEUP_TYPES.get(mtype, {}).get("name", "").lower()
        if item_name == type_display or item_name == mtype.replace("_", " "):
            return obj
    return None


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


def _target_display_name(target, viewer):
    if hasattr(target, "get_display_name"):
        return target.get_display_name(viewer)
    return target.key


def _possessive_pronoun(character, capitalize=False):
    """
    Return a possessive pronoun based on character.db.gender.
    male -> his, female -> her, neutral/other -> their
    """
    gender = (getattr(character.db, "gender", None) or "neutral").lower()
    poss = {"male": "his", "female": "her", "neutral": "their"}.get(gender, "their")
    return poss.capitalize() if capitalize else poss


# ── Pending input handler ─────────────────────────────────────────────────

def handle_pending_cosmetic_input(caller, raw):
    """
    Handle pending tattoo or makeup color-pick input.
    Called from CmdNoMatch. Returns True if the input was consumed.
    """
    raw = (raw or "").strip()

    pending = getattr(caller.ndb, "_pending_tattoo", None)
    if pending:
        _handle_tattoo_input(caller, raw, pending)
        return True

    pending_makeup = getattr(caller.ndb, "_pending_makeup_color", None)
    if pending_makeup:
        _handle_makeup_color_input(caller, raw, pending_makeup)
        return True

    return False


# ── Tattoo pending input stages ───────────────────────────────────────────

def _handle_tattoo_input(caller, raw, pending):
    """Process multi-stage tattoo text entry and confirmation."""
    stage = pending.get("stage", "text")

    if raw.lower() == "cancel":
        try:
            del caller.ndb._pending_tattoo
        except Exception:
            pass
        caller.msg("|xTattooing cancelled.|n")
        return

    if stage == "text":
        _tattoo_stage_text(caller, raw, pending)
    elif stage == "confirm":
        _tattoo_stage_confirm(caller, raw, pending)


def _tattoo_stage_text(caller, raw, pending):
    """Receive the tattoo description text and show a preview."""
    from world.cosmetics.tattoos import _sanitize_tattoo_text

    cleaned = _sanitize_tattoo_text(raw)

    if len(cleaned) < 5:
        caller.msg("|rToo short. Minimum 5 characters. Try again or type |wcancel|r.|n")
        return

    if len(cleaned) > 300:
        caller.msg(f"|rToo long ({len(cleaned)} chars). Maximum 300. Try again or type |wcancel|r.|n")
        return

    from evennia.utils.search import search_object
    target_id = pending.get("target_id")
    results = search_object(f"#{target_id}")
    target = results[0] if results else None

    if not target:
        caller.msg("|rTarget no longer found. Tattooing cancelled.|n")
        try:
            del caller.ndb._pending_tattoo
        except Exception:
            pass
        return

    body_part = pending.get("body_part", "")
    from world.cosmetics import TATTOO_QUALITY_TIERS

    target_name = _target_display_name(target, caller)

    caller.msg(
        f"|x{'═' * 48}|n\n"
        f"  |wPREVIEW — {body_part.upper()} on {target_name}|n\n"
        f"|x{'═' * 48}|n\n"
        f"  {cleaned}\n"
        f"|x{'═' * 48}|n\n"
        f"  Type |wyes|n to confirm, |wno|n to rewrite, |wcancel|n to abort."
    )

    pending["tattoo_text"] = cleaned
    pending["stage"] = "confirm"
    caller.ndb._pending_tattoo = pending


def _tattoo_stage_confirm(caller, raw, pending):
    """Handle yes/no/rewrite on the tattoo confirmation prompt."""
    answer = raw.strip().lower()

    if answer in ("no", "n", "rewrite"):
        pending["stage"] = "text"
        pending.pop("tattoo_text", None)
        caller.ndb._pending_tattoo = pending
        caller.msg("|xWrite the tattoo description again. Type |wcancel|n to abort.|n")
        return

    if answer not in ("yes", "y"):
        caller.msg("|xType |wyes|n to confirm, |wno|n to rewrite, or |wcancel|n to abort.|n")
        return

    # Confirmed — start the delayed RP sequence
    from evennia.utils.search import search_object

    target_id = pending.get("target_id")
    inkwriter_id = pending.get("inkwriter_id")
    body_part = pending.get("body_part", "")
    tattoo_text = pending.get("tattoo_text", "")

    results = search_object(f"#{target_id}")
    target = results[0] if results else None
    iw_results = search_object(f"#{inkwriter_id}")
    inkwriter = iw_results[0] if iw_results else None

    try:
        del caller.ndb._pending_tattoo
    except Exception:
        pass

    if not target or not inkwriter:
        caller.msg("|rTarget or inkwriter no longer found. Tattooing cancelled.|n")
        return

    target_name = _target_display_name(target, caller)
    caller_name = _target_display_name(caller, target)

    # Broadcast RP messages with delays
    room = caller.location
    rp_step = max(1, int(TATTOO_ACTION_TOTAL_DELAY / max(1, len(TATTOO_RP_MESSAGES))))
    for i, msg_template in enumerate(TATTOO_RP_MESSAGES):
        msg = msg_template.format(
            artist=caller_name,
            target=target_name,
            part=body_part,
        )
        delay(i * rp_step, _broadcast_rp_msg, room, msg)

    # After all RP messages, apply the tattoo
    delay(
        TATTOO_ACTION_TOTAL_DELAY,
        _do_apply_tattoo,
        caller.id,
        target.id,
        body_part,
        tattoo_text,
        inkwriter.id,
    )


def _broadcast_rp_msg(room, msg):
    """Broadcast a single RP message to a room."""
    if room:
        room.msg_contents(msg)


def _do_apply_tattoo(artist_id, target_id, body_part, tattoo_text, inkwriter_id):
    """Deferred callback: perform the actual tattoo roll and storage."""
    from evennia.utils.search import search_object
    from world.cosmetics.tattoos import apply_tattoo

    artist_results = search_object(f"#{artist_id}")
    target_results = search_object(f"#{target_id}")
    iw_results = search_object(f"#{inkwriter_id}")

    artist = artist_results[0] if artist_results else None
    target = target_results[0] if target_results else None
    inkwriter = iw_results[0] if iw_results else None

    if not artist or not target or not inkwriter:
        if artist:
            artist.msg("|rSomething went wrong. Tattooing failed.|n")
        return

    success, quality, err_msg = apply_tattoo(artist, target, body_part, tattoo_text, inkwriter)

    target_name = _target_display_name(target, artist)
    artist_name = _target_display_name(artist, target)

    if not success:
        artist.msg(f"|rTattooing failed: {err_msg}|n")
        return

    quality_info = TATTOO_QUALITY_TIERS.get(quality, TATTOO_QUALITY_TIERS["crude"])
    quality_note = quality_info.get("color_note", "")

    artist.msg(
        f"|gTattoo complete.|n {quality_note}\n"
        f"Quality: |w{quality}|n"
    )
    target.msg(
        f"|g{artist_name} finishes tattooing your {body_part}.|n {quality_note}"
    )

    room = artist.location
    if room:
        room.msg_contents(
            f"{artist_name} sets down the inkwriter. The work is done.",
            exclude=[artist, target],
        )


# ── Makeup color-pick pending input ───────────────────────────────────────

def _handle_makeup_color_input(caller, raw, pending):
    """Process color selection for a color-changeable makeup item."""
    try:
        del caller.ndb._pending_makeup_color
    except Exception:
        pass

    if raw.lower() == "cancel":
        caller.msg("|xColor selection cancelled.|n")
        return

    from evennia.utils.search import search_object
    from world.cosmetics.makeup import MAKEUP_COLOR_CATALOGS

    item_id = pending.get("item_id")
    target_id = pending.get("target_id")
    apply_after = pending.get("apply_after", False)

    iw_results = search_object(f"#{item_id}")
    item = iw_results[0] if iw_results else None

    if not item:
        caller.msg("|rItem no longer found.|n")
        return

    makeup_type = getattr(item.db, "makeup_type", "") or ""
    catalog = MAKEUP_COLOR_CATALOGS.get(makeup_type, {})

    color_key = raw.strip().lower().replace(" ", "_")
    color_data = catalog.get(color_key)

    if not color_data:
        # Try matching by display name
        for k, v in catalog.items():
            if v["name"].lower() == raw.strip().lower():
                color_key = k
                color_data = v
                break

    if not color_data:
        caller.msg(
            f"|rUnknown color '{raw}'.|n Type |wcolors {item.key}|n to see available colors."
        )
        return

    item.db.makeup_color_key = color_key
    item.db.makeup_color_name = color_data["name"]
    item.db.makeup_color_code = color_data["code"]
    caller.msg(f"Color set to {color_data['code']}{color_data['name']}|n.")

    if apply_after and target_id:
        t_results = search_object(f"#{target_id}")
        target = t_results[0] if t_results else None
        if target:
            _do_apply_makeup(caller, target, item)


# ── CmdInk ────────────────────────────────────────────────────────────────

class CmdInk(Command):
    """
    Tattoo a body part on another character. Requires an inkwriter in your
    inventory and the target's trust (tattoo category).

    Usage:
        ink <body part> on <character>
        tattoo <body part> on <character>

    You will be prompted to write the tattoo description. Color codes are
    allowed for colored ink (e.g. |rred|n, |cblue|n).

    Examples:
        ink left arm on Jake
        ink back on Maria
        ink neck on Dust
    """
    key = "ink"
    aliases = ["tattoo"]
    locks = "cmd:all()"
    help_category = "Cosmetics"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if _check_cooldown(
            caller,
            "tattoo_ink",
            INK_CMD_COOLDOWN,
            "|yYou need a moment before using the inkwriter again ({seconds}s).|n",
        ):
            return

        if not args or " on " not in args:
            caller.msg("Usage: |wink <body part> on <character>|n")
            return

        part_str, _, target_str = args.rpartition(" on ")
        part_str = part_str.strip().lower()
        target_str = target_str.strip()

        inkwriter = _find_inkwriter(caller)
        if not inkwriter:
            caller.msg("You need an inkwriter to tattoo someone.")
            return

        target = caller.search(target_str, location=caller.location)
        if not target:
            return

        if target == caller:
            caller.msg("You can't tattoo yourself.")
            return

        part = _resolve_body_part(part_str, target)
        if not part:
            from world.body import get_character_body_parts
            parts = get_character_body_parts(target)
            caller.msg(
                f"They don't have a '{part_str}'.\n"
                f"Valid parts: {', '.join(parts)}"
            )
            return

        from world.body import is_part_present, is_part_chrome
        if not is_part_present(target, part):
            caller.msg(f"Their {part} is missing.")
            return

        if is_part_chrome(target, part):
            caller.msg(f"Their {part} is fully chrome. Ink doesn't take.")
            return

        from world.rpg.trust import check_trust
        if not check_trust(target, caller, "tattoo"):
            target_name = _target_display_name(target, caller)
            caller.msg(
                f"{target_name} doesn't trust you to tattoo them. "
                f"They need to |w@trust|n you for tattoo."
            )
            return

        target_name = _target_display_name(target, caller)
        from world.cosmetics import INKWRITER_TIERS
        tier = int(inkwriter.db.inkwriter_tier or 1)
        tier_info = INKWRITER_TIERS.get(tier, INKWRITER_TIERS[1])

        caller.msg(
            f"|x{'═' * 48}|n\n"
            f"  |wINKWRITER — {part.upper()} on {target_name}|n\n"
            f"|x{'═' * 48}|n\n"
            f"  Tool: {tier_info['name']} (max quality: |w{tier_info['max_quality']}|n)\n"
            f"  Write the tattoo description. Color codes allowed:\n"
            f"  |rred|n |ggreen|n |cblue|n |mmag|n |yyellow|n |wwht|n\n"
            f"  Max 300 characters. Type |wcancel|n to abort.\n"
            f"|x{'═' * 48}|n"
        )

        caller.ndb._pending_tattoo = {
            "target_id": target.id,
            "body_part": part,
            "inkwriter_id": inkwriter.id,
            "stage": "text",
        }


# ── CmdRemoveTattoo ───────────────────────────────────────────────────────

class CmdRemoveTattoo(Command):
    """
    Remove a tattoo from a character's body part. Requires an inkwriter and
    the target's trust. Failure leaves a scar instead of clean removal.

    Usage:
        remove tattoo <number> from <body part> on <character>

    The number refers to the tattoo's position in the list (see: tattoos <character>).

    Examples:
        remove tattoo 1 from left arm on Jake
        remove tattoo 2 from back on Maria
    """
    key = "remove tattoo"
    locks = "cmd:all()"
    help_category = "Cosmetics"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if _check_cooldown(
            caller,
            "tattoo_remove",
            REMOVE_TATTOO_COOLDOWN,
            "|yYour hands need to steady before another removal attempt ({seconds}s).|n",
        ):
            return

        # Parse (robust): "[tattoo] <n> from <part> on <target>"
        if " from " not in args or " on " not in args:
            caller.msg("Usage: |wremove tattoo <number> from <body part> on <character>|n")
            return

        m = re.match(
            r"^(?:tattoo\s+)?(?P<num>\S+)\s+from\s+(?P<part>.+?)\s+on\s+(?P<target>.+)$",
            args,
            flags=re.IGNORECASE,
        )
        if not m:
            caller.msg("Usage: |wremove tattoo <number> from <body part> on <character>|n")
            return

        num_str = (m.group("num") or "").strip()
        part_str = (m.group("part") or "").strip().lower()
        target_str = (m.group("target") or "").strip()

        try:
            tattoo_index = int(num_str) - 1
        except ValueError:
            caller.msg("|rTattoo number must be a number.|n")
            return

        inkwriter = _find_inkwriter(caller)
        if not inkwriter:
            caller.msg("You need an inkwriter to remove tattoos.")
            return

        target = caller.search(target_str, location=caller.location)
        if not target:
            return

        part = _resolve_body_part(part_str, target)
        if not part:
            caller.msg(f"They don't have a '{part_str}'.")
            return

        tattoos = getattr(target.db, "tattoos", None) or {}
        part_tattoos = tattoos.get(part) or []

        if not part_tattoos:
            caller.msg(f"They have no tattoos on their {part}.")
            return

        if tattoo_index < 0 or tattoo_index >= len(part_tattoos):
            caller.msg(f"Invalid tattoo number. They have {len(part_tattoos)} tattoo(s) on their {part}.")
            return

        from world.rpg.trust import check_trust
        if not check_trust(target, caller, "tattoo"):
            target_name = _target_display_name(target, caller)
            caller.msg(f"{target_name} doesn't trust you for that.")
            return

        target_name = _target_display_name(target, caller)
        artist_name = _target_display_name(caller, target)
        room = caller.location

        caller.msg(f"You begin carefully removing the tattoo from {target_name}'s {part}.")
        target.msg(f"{artist_name} begins working on the tattoo on your {part}.")

        rp_step = max(1, int(TATTOO_ACTION_TOTAL_DELAY / max(1, len(REMOVE_TATTOO_RP_MESSAGES))))
        for i, msg_template in enumerate(REMOVE_TATTOO_RP_MESSAGES):
            msg = msg_template.format(artist=artist_name, target=target_name, part=part)
            delay(i * rp_step, _broadcast_rp_msg, room, msg)

        delay(
            TATTOO_ACTION_TOTAL_DELAY,
            _do_remove_tattoo,
            caller.id,
            target.id,
            part,
            tattoo_index,
            inkwriter.id,
        )


def _do_remove_tattoo(artist_id, target_id, body_part, tattoo_index, inkwriter_id):
    """Deferred callback: perform tattoo removal after narrated delay."""
    from evennia.utils.search import search_object
    from world.cosmetics.tattoos import remove_tattoo

    artist_results = search_object(f"#{artist_id}")
    target_results = search_object(f"#{target_id}")
    iw_results = search_object(f"#{inkwriter_id}")

    artist = artist_results[0] if artist_results else None
    target = target_results[0] if target_results else None
    inkwriter = iw_results[0] if iw_results else None

    if not artist or not target or not inkwriter:
        if artist:
            artist.msg("|rSomething interrupted the procedure. Tattoo removal failed.|n")
        return

    success, msg = remove_tattoo(artist, target, body_part, tattoo_index, inkwriter)
    artist_name = _target_display_name(artist, target)

    if success:
        artist.msg(f"|g{msg}|n")
        target.msg(f"|g{artist_name} finishes removing the tattoo from your {body_part}. {msg}|n")
    else:
        artist.msg(f"|r{msg}|n")


# ── CmdTattoos ────────────────────────────────────────────────────────────

class CmdTattoos(Command):
    """
    View the tattoos on a character.

    Usage:
        tattoos              — view your own tattoos (full detail)
        tattoos <character>  — staff only, or inkwriter holders see a working
                               view: exposed parts only, no artist/date metadata

    Lists all tattoos by body part with quality and text.
    """
    key = "tattoos"
    locks = "cmd:all()"
    help_category = "Cosmetics"

    def func(self):
        import datetime
        caller = self.caller
        args = (self.args or "").strip()
        if _check_cooldown(
            caller,
            "tattoo_list",
            TATTOOS_CMD_COOLDOWN,
            "|yGive it a second before checking tattoos again ({seconds}s).|n",
        ):
            return

        if not args or args.lower() in ("me", "self", "myself"):
            target = caller
        else:
            target = caller.search(args, location=caller.location)
            if not target:
                return

        is_self = target == caller
        is_staff = caller.check_permstring("Builder")
        has_inkwriter = bool(_find_inkwriter(caller))

        if not is_self and not is_staff and not has_inkwriter:
            caller.msg("You can only view your own tattoos.")
            return

        # Inkwriter working view: exposed parts only, no artist/date.
        inkwriter_view = not is_self and not is_staff and has_inkwriter

        tattoos = getattr(target.db, "tattoos", None) or {}

        if not tattoos or not any(tattoos.values()):
            if is_self:
                caller.msg("You have no tattoos.")
            else:
                target_name = _target_display_name(target, caller)
                caller.msg(f"{target_name} has no visible tattoos.")
            return

        # For inkwriter view, filter to exposed (uncovered) parts only.
        if inkwriter_view:
            from world.clothing import get_covered_parts_set
            covered = get_covered_parts_set(target)
            visible_parts = {p: t for p, t in tattoos.items() if p not in covered and t}
            if not visible_parts:
                target_name = _target_display_name(target, caller)
                caller.msg(f"{target_name}'s tattoos are all covered by clothing.")
                return
            tattoos_to_show = visible_parts
        else:
            tattoos_to_show = {p: t for p, t in tattoos.items() if t}

        target_name = _target_display_name(target, caller)
        header = f"|w{'═' * 48}|n\n  Tattoos on {target_name}\n|w{'═' * 48}|n"
        lines = [header]

        for part, part_tattoos in tattoos_to_show.items():
            lines.append(f"\n  |w{part.upper()}|n")
            for i, tattoo in enumerate(part_tattoos, 1):
                quality = tattoo.get("quality", "crude")
                artist = tattoo.get("artist_name", "unknown")
                is_scar = tattoo.get("is_scar", False)
                text = tattoo.get("text", "")
                applied_at = tattoo.get("applied_at", 0)

                if inkwriter_view:
                    # Minimal working list: number, quality tag, text only.
                    if is_scar:
                        lines.append(f"    {i}. |x[scar]|n {text}")
                    else:
                        lines.append(f"    {i}. |w[{quality}]|n {text}")
                else:
                    if applied_at:
                        dt = datetime.datetime.fromtimestamp(applied_at)
                        date_str = dt.strftime("%Y-%m-%d")
                    else:
                        date_str = "unknown"

                    if is_scar:
                        lines.append(f"    {i}. |x[scar]|n {text}")
                    else:
                        lines.append(
                            f"    {i}. |w[{quality}]|n by {artist} ({date_str})\n"
                            f"       {text}"
                        )

        lines.append(f"|w{'═' * 48}|n")
        caller.msg("\n".join(lines))


# ── CmdApply (unified dispatcher) ────────────────────────────────────────

class CmdApply(Command):
    """
    Apply a makeup item or a medical tool to yourself or another character.

    Cosmetic usage:
        apply <makeup item>              — apply to yourself
        apply <makeup item> to <target>  — apply to another character

    Medical usage:
        apply to <target> [body part]
        apply <medical item> to <target> [body part]

    The command checks your inventory for a matching makeup item first. If
    none is found it falls through to the medical apply logic.

    Cosmetic examples:
        apply lipstick
        apply lipstick to Maria
        apply eye shadow to me
        apply nail polish to Jake

    Medical examples:
        apply to Bob
        apply bandage to Bob
        apply splint to Bob arm
    """
    key = "apply"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()

        # ── Cosmetic path ─────────────────────────────────────────────────
        # Determine item string: everything before " to " (or the whole arg
        # if there is no " to ").
        if " to " in args:
            item_str = args.rpartition(" to ")[0].strip()
            target_str = args.rpartition(" to ")[2].strip()
        else:
            item_str = args
            target_str = "me"

        if item_str:
            makeup_item = _find_makeup_item(caller, item_str)
            if makeup_item:
                uses = int(getattr(makeup_item.db, "uses_remaining", 0) or 0)
                if uses <= 0:
                    caller.msg(f"The {makeup_item.key} is empty.")
                    return

                if target_str.lower() in ("me", "self", "myself"):
                    target = caller
                else:
                    target = caller.search(target_str, location=caller.location)
                    if not target:
                        return

                color_changeable = getattr(makeup_item.db, "color_changeable", False)
                color_name = (getattr(makeup_item.db, "makeup_color_name", None) or "").strip()

                if color_changeable and not color_name:
                    _prompt_color_pick(caller, makeup_item, target, apply_after=True)
                    return

                _do_apply_makeup(caller, target, makeup_item)
                return

        # ── Medical path ──────────────────────────────────────────────────
        from commands.medical_cmds import do_medical_apply
        handled = do_medical_apply(caller, args)
        if not handled:
            caller.msg(
                "Usage:\n"
                "  |wapply <makeup item> [to <target>]|n  — cosmetics\n"
                "  |wapply [medical item] to <target> [body part]|n  — medical"
            )


def _prompt_color_pick(caller, item, target, apply_after=False):
    """Show color list and set pending color-pick state."""
    from world.cosmetics.makeup import MAKEUP_COLOR_CATALOGS

    makeup_type = getattr(item.db, "makeup_type", "") or ""
    catalog = MAKEUP_COLOR_CATALOGS.get(makeup_type, {})

    if not catalog:
        caller.msg(f"|rNo colors available for {item.key}.|n")
        return

    lines = [
        f"|x{'═' * 48}|n",
        f"  |wCOLOR SELECTION — {item.key}|n",
        f"|x{'═' * 48}|n",
    ]

    # Group colors in rows of 4
    color_items = list(catalog.items())
    for i in range(0, len(color_items), 4):
        row = color_items[i:i + 4]
        row_str = "  " + "  ".join(
            f"{v['code']}{v['name']}|n ({k})" for k, v in row
        )
        lines.append(row_str)

    lines.append(f"|x{'═' * 48}|n")
    lines.append("  Type the color key or name. Type |wcancel|n to abort.")
    caller.msg("\n".join(lines))

    caller.ndb._pending_makeup_color = {
        "item_id": item.id,
        "target_id": target.id if target else None,
        "apply_after": apply_after,
    }


def _do_apply_makeup(caller, target, item):
    """Execute makeup application and broadcast echoes."""
    from world.cosmetics.makeup import apply_makeup

    success, err_msg = apply_makeup(caller, target, item)

    if not success:
        caller.msg(f"|r{err_msg}|n")
        return

    makeup_type = getattr(item.db, "makeup_type", "") or ""
    type_info = MAKEUP_TYPES.get(makeup_type, {})
    color_name = (getattr(item.db, "makeup_color_name", None) or "").strip()
    color_code = (getattr(item.db, "makeup_color_code", None) or "").strip()

    caller_name = _target_display_name(caller, target)
    target_name = _target_display_name(target, caller)

    color_text = f"{color_code}{color_name}|n" if color_code else color_name
    target_poss = _possessive_pronoun(target)
    caller_poss = _possessive_pronoun(caller)

    # Type-specific language so pronouns and self-messaging read naturally.
    if makeup_type == "lipstick":
        room_echo = f"{caller_name} uncaps the lipstick and carefully traces {target_poss} lips in {color_text}."
        self_echo = f"You uncap the lipstick and carefully trace your lips in {color_text}."
    elif makeup_type == "nail_polish":
        room_echo = f"{caller_name} carefully paints {target_poss} nails in {color_text}, one at a time."
        self_echo = f"You carefully paint your nails in {color_text}, one at a time."
    elif makeup_type == "eye_shadow":
        room_echo = f"{caller_name} sweeps {color_text} shadow across {target_poss} eyelids with a soft brush."
        self_echo = f"You sweep {color_text} shadow across your eyelids with a soft brush."
    elif makeup_type == "eyeliner":
        room_echo = f"{caller_name} draws a steady line of {color_text} along {target_poss} lash line."
        self_echo = f"You draw a steady line of {color_text} along your lash line."
    else:
        type_name = type_info.get("name", makeup_type).lower()
        room_echo = f"{caller_name} applies {type_name} to {target_poss} features."
        self_echo = f"You apply {type_name} to your own features."

    if caller.location:
        if target == caller:
            caller.location.msg_contents(room_echo, exclude=caller)
            caller.msg(self_echo)
        else:
            caller.location.msg_contents(room_echo)

    if target != caller:
        target.msg(f"|g{caller_name} applies {type_info.get('name', makeup_type).lower()} to you.|n")

    uses_left = int(getattr(item.db, "uses_remaining", 0) or 0)
    if uses_left > 0:
        caller.msg(f"|g{item.key.capitalize()} applied.|n ({uses_left} use{'s' if uses_left != 1 else ''} left)")
    else:
        caller.msg(f"|g{item.key.capitalize()} applied.|n |x(Used up.)|n")


# ── CmdWipe ───────────────────────────────────────────────────────────────

class CmdWipe(Command):
    """
    Remove your own makeup.

    Usage:
        wipe <type>   — lipstick, nail polish, eye shadow, eyeliner
        wipe all      — remove all makeup

    Examples:
        wipe lipstick
        wipe nail polish
        wipe all
    """
    key = "wipe"
    aliases = ["remove makeup"]
    locks = "cmd:all()"
    help_category = "Cosmetics"

    def func(self):
        caller = self.caller
        arg = (self.args or "").strip().lower()

        if not arg:
            caller.msg("Wipe what? Usage: |wwipe <type>|n or |wwipe all|n")
            return

        active = list(getattr(caller.db, "active_makeup", None) or [])
        if not active:
            caller.msg("You're not wearing any makeup.")
            return

        caller_name = _target_display_name(caller, caller)

        if arg == "all":
            caller.db.active_makeup = []
            # Remove all makeup buffs
            _remove_all_makeup_buffs(caller)
            caller.msg("You wipe away all your makeup.")
            if caller.location:
                caller.location.msg_contents(
                    f"{caller_name} wipes off their makeup.",
                    exclude=caller,
                )
            return

        type_key = arg.replace(" ", "_")
        matching = [m for m in active if m.get("makeup_type") == type_key]
        if not matching:
            caller.msg(f"You're not wearing {arg}.")
            return

        remaining = [m for m in active if m.get("makeup_type") != type_key]
        caller.db.active_makeup = remaining

        # Remove the specific buff
        _remove_makeup_buff(caller, type_key)

        type_info = MAKEUP_TYPES.get(type_key, {})
        type_name = type_info.get("name", arg)
        caller.msg(f"You wipe off your {type_name.lower()}.")
        if caller.location:
            caller.location.msg_contents(
                f"{caller_name} wipes off their {type_name.lower()}.",
                exclude=caller,
            )


def _remove_makeup_buff(character, makeup_type):
    """Remove the buff for a specific makeup type."""
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
            character.buffs.remove(buff_cls.key)
    except Exception:
        pass


def _remove_all_makeup_buffs(character):
    """Remove all makeup-related buffs."""
    for mtype in ("lipstick", "nail_polish", "eye_shadow", "eyeliner"):
        _remove_makeup_buff(character, mtype)


# ── CmdColor ─────────────────────────────────────────────────────────────

class CmdColor(Command):
    """
    Set the active color on a color-changeable makeup item.

    Usage:
        color <item> <color key or name>

    Examples:
        color lipstick siren
        color eye shadow smoke
        color eyeliner kohl
    """
    key = "color"
    locks = "cmd:all()"
    help_category = "Cosmetics"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()

        if not args:
            caller.msg("Usage: |wcolor <item> <color>|n")
            return

        # Split: first token(s) match item, remainder is color
        # Try splitting on first word, then two words, etc.
        parts = args.split()
        item = None
        color_str = ""

        for split_at in range(1, len(parts)):
            item_str = " ".join(parts[:split_at])
            color_str = " ".join(parts[split_at:])
            item = _find_makeup_item(caller, item_str)
            if item:
                break

        if not item:
            caller.msg(f"You don't have that makeup item.")
            return

        if not getattr(item.db, "color_changeable", False):
            caller.msg(f"The {item.key} color is fixed.")
            return

        from world.cosmetics.makeup import MAKEUP_COLOR_CATALOGS
        makeup_type = getattr(item.db, "makeup_type", "") or ""
        catalog = MAKEUP_COLOR_CATALOGS.get(makeup_type, {})

        color_key = color_str.strip().lower().replace(" ", "_")
        color_data = catalog.get(color_key)

        if not color_data:
            for k, v in catalog.items():
                if v["name"].lower() == color_str.strip().lower():
                    color_key = k
                    color_data = v
                    break

        if not color_data:
            caller.msg(
                f"|rUnknown color '{color_str}'.|n "
                f"Type |wcolors {item.key}|n to see available colors."
            )
            return

        item.db.makeup_color_key = color_key
        item.db.makeup_color_name = color_data["name"]
        item.db.makeup_color_code = color_data["code"]
        caller.msg(
            f"Color of {item.key} set to {color_data['code']}{color_data['name']}|n."
        )


# ── CmdColors ─────────────────────────────────────────────────────────────

class CmdColors(Command):
    """
    List the available colors for a color-changeable makeup item.

    Usage:
        colors <item>

    Examples:
        colors lipstick
        colors eye shadow
        colors eyeliner
    """
    key = "colors"
    locks = "cmd:all()"
    help_category = "Cosmetics"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()

        if not args:
            caller.msg("Usage: |wcolors <item>|n")
            return

        item = _find_makeup_item(caller, args)
        if not item:
            caller.msg(f"You don't have a '{args}' in your inventory.")
            return

        from world.cosmetics.makeup import MAKEUP_COLOR_CATALOGS
        makeup_type = getattr(item.db, "makeup_type", "") or ""
        catalog = MAKEUP_COLOR_CATALOGS.get(makeup_type, {})

        if not catalog:
            caller.msg(f"No color catalog for {item.key}.")
            return

        lines = [
            f"|x{'═' * 52}|n",
            f"  |wColors for {item.key}|n",
            f"|x{'═' * 52}|n",
        ]

        color_items = list(catalog.items())
        for i in range(0, len(color_items), 3):
            row = color_items[i:i + 3]
            row_parts = []
            for k, v in row:
                row_parts.append(f"  {v['code']}{v['name']}|n |x({k})|n")
            lines.append("".join(row_parts))

        lines.append(f"|x{'═' * 52}|n")
        lines.append("  Use: |wcolor <item> <key>|n to set a color.")
        caller.msg("\n".join(lines))
