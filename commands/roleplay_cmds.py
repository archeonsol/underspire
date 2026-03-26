"""
Roleplay commands: pose, emote, no-match emote, tease, body part/place/voice/sdesc/pending, sit/lie/getup, pronoun.
"""

import re
from commands.base_cmds import Command
from evennia.commands.cmdhandler import CMD_NOMATCH
from evennia.utils import logger


def _resolve_body_part(name, caller=None):
    """Resolve short alias or full name to canonical body part key, or None."""
    from world.body import get_character_body_parts
    from world.medical import BODY_PARTS, BODY_PART_ALIASES
    raw = name.strip().lower()
    if raw in BODY_PARTS:
        return raw
    resolved = BODY_PART_ALIASES.get(raw)
    if resolved:
        return resolved
    if raw == "tail" and caller is not None and "tail" in get_character_body_parts(caller):
        return "tail"
    return None


def _body_parts_usage_list(caller=None):
    """Head-to-feet list with short names where available (for usage line)."""
    from world.body import get_character_body_parts
    from world.medical import BODY_PARTS_HEAD_TO_FEET, BODY_PART_ALIASES
    rev = {}
    for alias, full in BODY_PART_ALIASES.items():
        chosen = rev.get(full)
        if not chosen:
            rev[full] = alias
            continue
        # Prefer compact aliases without spaces for cleaner usage text.
        current_score = (len(chosen), 1 if " " in chosen else 0)
        new_score = (len(alias), 1 if " " in alias else 0)
        if new_score < current_score:
            rev[full] = alias
    out = [rev.get(p, p) for p in BODY_PARTS_HEAD_TO_FEET]
    if caller is not None and "tail" in get_character_body_parts(caller):
        out.append("tail")
    return out


def _set_body_part_description(caller, args):
    """Set one body-part line from args like '<part> = <text>'. Returns True if handled (set or error msg)."""
    if not hasattr(caller, "get_body_descriptions"):
        caller.msg("You cannot set body descriptions.")
        return True
    if not args or "=" not in args:
        caller.msg("Usage: @body <body part> = <text>")
        caller.msg("Body parts: " + ", ".join(_body_parts_usage_list(caller)))
        return True
    raw, _, rest = args.partition("=")
    rest = rest.strip()
    if not rest:
        caller.msg("Provide a description after the =.")
        return True
    from world.body import get_character_body_parts

    part = _resolve_body_part(raw, caller=caller)
    if not part:
        caller.msg("Unknown body part. Use: " + ", ".join(_body_parts_usage_list(caller)))
        return True
    if part not in get_character_body_parts(caller):
        caller.msg("You don't have that body part.")
        return True
    locked = getattr(caller.db, "locked_descriptions", None) or {}
    if part in locked:
        caller.msg(f"|r{part.title()} is locked by installed cyberware and cannot be edited.|n")
        return True
    if not caller.check_permstring("Builder"):
        from world.skin_tones import strip_color_codes

        race = (getattr(caller.db, "race", None) or "human").lower()
        allow_markup = race == "splicer" and part in ("tail", "left ear", "right ear")
        if not allow_markup:
            stripped = strip_color_codes(rest)
            if stripped != rest:
                caller.msg(
                    "Color codes are not allowed in body descriptions. Your skin tone provides the coloring."
                )
            rest = stripped
    caller.get_body_descriptions()
    caller.db.body_descriptions[part] = rest
    caller.msg(f"Set your |w{part}|n description: {rest}")
    return True


def _run_emote(caller, text, improvise=False):
    """Shared emote logic for CmdEmote and CmdNoMatch. If improvise=True (or caller.ndb.performance_improvising), messages are wrapped in bright white and an audience reaction is echoed."""
    improvise = improvise or bool(getattr(getattr(caller, "ndb", None), "performance_improvising", False))
    from world.rpg.emote import (
        first_to_third,
        first_to_second,
        split_emote_segments,
        find_targets_in_text,
        build_emote_for_viewer,
        format_emote_message,
        replace_first_pronoun_with_name,
    )

    text = (text or "").strip()
    if not text:
        caller.msg("Usage: . <first-person text>")
        return

    location = caller.location
    if not location:
        return

    segments = split_emote_segments(text)
    # Comma-start = no "You " prefix in echo (scene-setting style)
    starts_with_comma = bool(segments and segments[0].strip().startswith(","))
    chars_here = location.filter_visible(location.contents_get(content_type="character"), caller)
    viewers = [c for c in chars_here if c != caller] + [caller]
    debug_on = getattr(caller.db, "emote_debug", False) and caller.account
    if debug_on:
        debug_on = caller.account.permissions.check("Builder") or caller.account.permissions.check("Admin")
    debug_lines = [] if debug_on else None
    room_line = None  # one canonical third-person line for cameras

    for viewer in viewers:
        if viewer == caller:
            # --- Improved: handle quote protection, echo to caller cleanly ---
            echo_parts = []
            caller_targets = []  # (matched_name, char) from third-person segments
            for i, seg in enumerate(segments):
                # Strip leading comma (no-conjugate marker) so it doesn't appear in echo
                seg = seg.lstrip().lstrip(",").lstrip() if seg.strip().startswith(",") else seg
                # Treat '.word' as a verb marker for the caller's echo only:
                # - At the start of the segment: '.grin at the crowd' -> 'grin at the crowd'
                # - In the middle of a segment: 'I .look at them' -> 'I look at them'
                seg = re.sub(r"^\.\s*(\w+)", r"\1", seg)
                seg = re.sub(r" \.\s*(\w+)", r" \1", seg)
                # Quoted text is character speech: protect from transformation and restore verbatim
                quotes = re.findall(r'"([^"]*)"', seg)
                quote_map = {f"__Q{i}_{j}__": f'"{q}"' for j, q in enumerate(quotes)}
                temp_seg = seg
                for placeholder, original in quote_map.items():
                    temp_seg = temp_seg.replace(original, placeholder)
                converted = first_to_second(temp_seg)
                for placeholder, original in quote_map.items():
                    converted = converted.replace(placeholder, original)
                # Capitalization rules
                if i == 0:
                    converted = converted[0].upper() + converted[1:] if converted else converted
                else:
                    converted = converted[0].lower() + converted[1:] if converted else converted
                echo_parts.append(converted)
                # Resolve sdesc/target refs for caller's echo (same targets as third-person)
                third = first_to_third(segments[i].strip(), caller)
                try:
                    from world.rpg.language import parse_quoted_speech
                    third, _ = parse_quoted_speech(third)
                except Exception:
                    pass
                seg_targets = find_targets_in_text(third, location.contents_get(content_type="character"), caller)
                caller_targets.extend(seg_targets)
            # Join and ensure trailing punctuation
            full_echo = ". ".join(echo_parts).strip()
            if not full_echo.endswith((".", "!", "?", '"')):
                full_echo += "."
            # Capitalize first letter after each ". " (e.g. "calm. you" -> "calm. You")
            full_echo = re.sub(r"\.\s+(\w)", lambda m: ". " + m.group(1).upper(), full_echo)
            # Replace target refs in caller's echo (sdesc/recog from emitter's perspective)
            try:
                from world.rp_features import get_display_name_for_viewer
                from world.skin_tones import format_ic_character_name, format_ic_character_name_possessive
            except ImportError:
                get_display_name_for_viewer = lambda c, v: getattr(c, "key", str(c))
                format_ic_character_name = lambda c, v, p: p
                format_ic_character_name_possessive = lambda c, v, p: (p or "") + "'s"
            for matched_name, char in sorted(caller_targets, key=lambda x: -len(x[0])):
                if char == caller:
                    replacement = "you"
                    full_echo = re.sub(r"(?<!\w)" + re.escape(matched_name) + r"'s(?!\w)", "your", full_echo, flags=re.IGNORECASE)
                    full_echo = re.sub(r"(?<!\w)" + re.escape(matched_name) + r"(?!\w)", replacement, full_echo, flags=re.IGNORECASE)
                else:
                    pln = get_display_name_for_viewer(char, caller)
                    replacement = format_ic_character_name(char, caller, pln)
                    repl_poss = format_ic_character_name_possessive(char, caller, pln)
                    full_echo = re.sub(r"(?<!\w)" + re.escape(matched_name) + r"'s(?!\w)", repl_poss, full_echo, flags=re.IGNORECASE)
                    full_echo = re.sub(r"(?<!\w)" + re.escape(matched_name) + r"(?!\w)", replacement, full_echo, flags=re.IGNORECASE)
            # Comma-start: no "You " prefix; else template adds "You " and we avoid double capital
            if starts_with_comma:
                body = full_echo
                msg = (body[0].upper() + body[1:]) if body and body[0].islower() else (body or "")
            else:
                if full_echo.lower().startswith("you "):
                    body = full_echo[4:].strip()
                else:
                    body = (full_echo[0].lower() + full_echo[1:]) if full_echo and full_echo[0].isupper() else full_echo
                msg = f"|cYou|n {body}" if body else "|cYou|n"
            # Slur for drunk callers (level 2+).
            try:
                from world.rpg.survival import slur_text_if_drunk
                msg = slur_text_if_drunk(caller, msg)
            except Exception as e:
                logger.log_trace("roleplay_cmds._run_emote slur (you): %s" % e)
            if debug_lines is not None:
                debug_lines.append(("you", msg))
            if improvise:
                msg = "|w%s|n" % msg
            caller.msg(msg)
        else:
            # --- THIRD PERSON VIEWERS ---
            body_parts = []
            for seg in segments:
                # Keep " .word" so first_to_third can conjugate those verbs (dot = verb tell)
                third = first_to_third(seg.strip(), caller)
                try:
                    from world.rpg.language import parse_quoted_speech, process_language_for_viewer, get_speaker_language
                    third, lang_bits = parse_quoted_speech(third)
                except Exception:
                    lang_bits = []
                targets = find_targets_in_text(third, location.contents_get(content_type="character"), caller)
                body_part = build_emote_for_viewer(third, viewer, targets)
                lang_key = get_speaker_language(caller)
                for ph, quote_text in lang_bits:
                    try:
                        from world.rpg.language import process_language_for_viewer
                        processed = process_language_for_viewer(caller, quote_text, lang_key, viewer)
                        body_part = body_part.replace(ph, processed)
                    except Exception:
                        body_part = body_part.replace(ph, quote_text)
                body_parts.append(body_part)
            full_body = ". ".join(p.strip() for p in body_parts if p.strip())
            # Capitalize first letter after each ". " (e.g. "clear. he" -> "clear. He")
            full_body = re.sub(r"\.\s+(\w)", lambda m: ". " + m.group(1).upper(), full_body)
            # Optional voice tag in quoted speech (perception check, rare)
            try:
                from world.rpg.voice import get_voice_phrase, get_speaking_tag, voice_perception_check
                if get_voice_phrase(caller) and voice_perception_check(viewer, caller) and '"' in full_body:
                    idx = full_body.index('"')
                    full_body = full_body[: idx + 1] + get_speaking_tag(caller) + full_body[idx + 1 :]
            except Exception as e:
                logger.log_trace("roleplay_cmds._run_emote voice tag: %s" % e)
            if starts_with_comma:
                pronoun_key = getattr(caller.db, "pronoun", "neutral")
                full_body = replace_first_pronoun_with_name(full_body, pronoun_key, caller, viewer)
                msg = full_body
            else:
                msg = format_emote_message(caller, viewer, full_body)
            # Slur emote output for drunk callers (level 2+) for other viewers as well.
            try:
                from world.rpg.survival import slur_text_if_drunk
                msg = slur_text_if_drunk(caller, msg)
            except Exception:
                pass
            if debug_lines is not None:
                debug_lines.append((viewer.get_display_name(viewer), msg))
            if improvise:
                msg = "|w%s|n" % msg
            viewer.msg(msg)

    # Build one neutral third-person line for cameras (viewer=None so no "you", all names)
    if segments:
        body_parts = []
        for seg in segments:
            third = first_to_third(seg.strip(), caller)
            try:
                from world.rpg.language import parse_quoted_speech, process_language_for_viewer, get_speaker_language
                third, lang_bits = parse_quoted_speech(third)
            except Exception:
                lang_bits = []
            targets = find_targets_in_text(third, location.contents_get(content_type="character"), caller)
            body_part = build_emote_for_viewer(third, None, targets)
            lang_key = get_speaker_language(caller)
            for ph, quote_text in lang_bits:
                try:
                    from world.rpg.language import process_language_for_viewer
                    processed = process_language_for_viewer(caller, quote_text, lang_key, None)
                    body_part = body_part.replace(ph, processed)
                except Exception:
                    body_part = body_part.replace(ph, quote_text)
            body_parts.append(body_part)
        full_body = ". ".join(p.strip() for p in body_parts if p.strip()).strip()
        full_body = re.sub(r"\.\s+(\w)", lambda m: ". " + m.group(1).upper(), full_body)
        if starts_with_comma:
            pronoun_key = getattr(caller.db, "pronoun", "neutral")
            full_body = replace_first_pronoun_with_name(full_body, pronoun_key, caller, None)
            room_line = (full_body[0].upper() + full_body[1:]) if full_body and full_body[0].islower() else (full_body or "")
        else:
            room_line = format_emote_message(caller, None, full_body)
    else:
        room_line = None
    if room_line:
        try:
            from typeclasses.broadcast import feed_cameras_in_location
            feed_cameras_in_location(location, room_line)
        except Exception as e:
            logger.log_trace("roleplay_cmds._run_emote feed_cameras: %s" % e)
        try:
            from typeclasses.vehicles import relay_to_parked_vehicle_interiors
            relay_to_parked_vehicle_interiors(location, room_line)
        except Exception as e:
            logger.log_trace("roleplay_cmds._run_emote relay_vehicle: %s" % e)

    if improvise and location:
        try:
            from commands.performance_cmds import _audience_echo_improvise
            _audience_echo_improvise(location)
        except Exception:
            pass

    if debug_lines:
        caller.msg("|w--- Emote debug ---|n")
        for who, line in debug_lines:
            if who == "you":
                caller.msg(f"|yTo you:|n {line}")
            else:
                caller.msg(f"|yTo {who}:|n {line}")
        caller.msg("|w---|n")


class CmdDescribeMeAs(Command):
    """
    Set the short "describe me as" line shown when someone looks at you (first line after your name).

    Usage:
      @dmas              - show your current general description
      @dmas = <text>     - set it (e.g. @dmas = A grizzled veteran with a permanent scowl.)
    """
    key = "@dmas"
    aliases = ["@describe me as", "@describe_me_as"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not hasattr(caller, "db"):
            return
        args = (self.args or "").strip()
        if "=" in args:
            _, _, rest = args.partition("=")
            rest = rest.strip()
            if not caller.check_permstring("Builder"):
                from world.skin_tones import strip_color_codes

                stripped = strip_color_codes(rest)
                if stripped != rest:
                    caller.msg(
                        "Color codes are not allowed in your general description. Your skin tone provides the coloring."
                    )
                rest = stripped
            caller.db.general_desc = rest if rest else "This is a character."
            if rest:
                caller.msg("When someone looks at you, they will see: |w%s|n" % rest)
            else:
                caller.msg("Reset to default: |wThis is a character.|n")
            return
        current = getattr(caller.db, "general_desc", None) or "This is a character."
        caller.msg("|wYour general description|n (the first line when someone looks at you):")
        caller.msg("  %s" % current)
        caller.msg("To change: |w@dmas = <text>|n")


class CmdVoice(Command):
    """
    Set the optional voice description shown rarely when you speak (say/emote), based on listeners' perception.

    Usage:
      @voice           - show your current voice setting
      @voice = <text>  - set it (e.g. @voice = British accented). Affixed with " voice" automatically.
      @voice clear     - clear your voice (stop showing)
    """
    key = "@voice"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not hasattr(caller, "db"):
            return
        args = (self.args or "").strip()
        if args.lower() == "clear" or args == "" and "=" not in (self.args or ""):
            if args.lower() == "clear":
                caller.db.voice = ""
                caller.msg("Voice cleared. Your speech will no longer show a voice description.")
                return
            current = getattr(caller.db, "voice", None) or ""
            if current:
                caller.msg("|wYour voice|n (shown rarely to listeners who pass a perception check): |w%s voice|n" % current)
            else:
                caller.msg("|wYour voice|n: not set. Use |w@voice = <text>|n (e.g. @voice = British accented).")
            return
        if "=" in args:
            _, _, rest = args.partition("=")
            rest = rest.strip()
            caller.db.voice = rest
            if rest:
                caller.msg("Voice set. Listeners may occasionally see you |wspeaking in a %s voice|n." % rest)
            else:
                caller.msg("Voice cleared.")
            return
        current = getattr(caller.db, "voice", None) or ""
        if current:
            caller.msg("|wYour voice|n: |w%s voice|n" % current)
        else:
            caller.msg("|wYour voice|n: not set. Use |w@voice = <text>|n.")


class CmdSmellSet(Command):
    """
    Set or view your personal scent description, used when others smell you.

    Usage:
      @smell                 - show your current personal scent
      @smell = <text>        - set it (e.g. @smell = He smells like roses and oil, a stark contrast but quite intoxicating anyway.)
      @smell clear           - clear your personal scent

    This text is a full sentence or short paragraph used when someone runs
    'smell <you>'. It does NOT change your short description (sdesc); that is
    reserved for perfume/room effects.
    """
    key = "@smell"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not hasattr(caller, "db"):
            return
        raw = (self.args or "").strip()
        # @smell clear
        if raw.lower() == "clear":
            if hasattr(caller.db, "smell_text"):
                try:
                    del caller.db.smell_text
                except Exception:
                    caller.db.smell_text = ""
            caller.msg("You clear your personal scent message. Others will no longer see a custom line when they smell you.")
            return
        # @smell (no '=') – show current
        if "=" not in raw:
            text = (getattr(caller.db, "smell_text", None) or "").strip()
            if not text:
                caller.msg("|wYour personal scent line|n: not set.")
                caller.msg("Set one with |w@smell = <text>|n (e.g. @smell = He smells like roses and oil, a stark contrast but quite intoxicating anyway.)")
                return
            caller.msg("|wYour personal scent line (shown when someone smells you):|n")
            caller.msg(f"  {text}")
            return
        # @smell = <text>
        _, _, rest = raw.partition("=")
        rest = (rest or "").strip()
        if not rest:
            caller.msg("Provide a short sentence or line after '=' (e.g. @smell = He smells like roses and oil...).")
            return
        if len(rest) > 400:
            caller.msg("That scent description is a bit too long. Keep it to 400 characters or fewer.")
            return
        caller.db.smell_text = rest
        caller.msg(f"Set your personal scent line to:\n|w{rest}|n")


class CmdLanguage(Command):
    """
    Set which language you speak (say/whisper/emotes). Only languages you know (have invested XP in) can be selected.

    Usage:
      language              - show current speaking language and languages you know
      language <language>   - set speaking language (e.g. language gutter)
    """
    key = "language"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.rpg.language import (
            resolve_language_key, get_speaker_language, get_language_percent,
            LEARNABLE_LANGUAGE_KEYS, get_language_level_name,
        )
        caller = self.caller
        if not hasattr(caller, "db"):
            return
        args = (self.args or "").strip()
        # Languages this character knows: English always, plus any learnable with percent > 0
        known = ["english"]
        for k in LEARNABLE_LANGUAGE_KEYS:
            if get_language_percent(caller, k) > 0:
                known.append(k)
        if not args:
            current = get_speaker_language(caller)
            # If current is not in known, reset to english (e.g. lost XP or data change)
            if current not in known:
                current = "english"
                caller.db.speaking_language = "english"
            display = current.replace("_", " ").title()
            caller.msg("You are currently speaking |w%s|n." % display)
            if len(known) <= 1:
                caller.msg("Languages you know: English. Use |w@xp advance language <name>|n to learn another.")
            else:
                opts = [k.replace("_", " ").title() + " (" + get_language_level_name(get_language_percent(caller, k)) + ")" for k in known if k != "english"]
                caller.msg("Use |wlanguage <name>|n to change. Languages you know: English, %s." % ", ".join(opts))
            return
        key = resolve_language_key(args)
        if key is None:
            caller.msg("Unknown language.")
            return
        if key not in known:
            caller.msg("You don't know that language. Learn it with |w@xp advance language <name>|n.")
            return
        caller.db.speaking_language = key
        display = key.replace("_", " ").title()
        caller.msg("You will now speak |w%s|n. Say, whisper, and quoted speech in emotes will be heard in that language by those who know it." % display)


def _count_pluralize(name):
    """Return a simple plural for count output (e.g. 'pod' -> 'pods')."""
    if not name:
        return "things"
    n = (name or "").strip()
    if not n:
        return "things"
    if " " in n:
        return "things matching '%s'" % name
    if n.endswith("s") or n.endswith("x") or n.endswith("ch") or n.endswith("sh"):
        return n + "es"
    return n + "s"


def _get_memory_slots(caller):
    """
    Return how many short strings this character can memorize.
    Minimum of 5, scaling with intelligence display stat (0–150).
    """
    base = 5
    if not hasattr(caller, "get_display_stat"):
        return base
    try:
        intel = caller.get_display_stat("intelligence") or 0
    except Exception:
        intel = 0
    # +1 slot per 3 intelligence display levels, up to +45 at 150 (max 50 total).
    extra = max(0, int(intel) // 3)
    return base + min(extra, 45)


class CmdMemorize(Command):
    """
    Memorize a short string you can recall later with the memory command.

    Usage:
      memorize <text>

    You can store at least five strings; the maximum grows with your Intelligence stat.
    Each stored string is limited to 120 characters.
    """

    key = "memorize"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        text = (self.args or "").strip()
        if not text:
            caller.msg("Usage: memorize <text>  (e.g. memorize door code 4917)")
            return
        if len(text) > 120:
            caller.msg("That is too long to keep straight in your head. Keep it to 120 characters or fewer.")
            return

        max_slots = _get_memory_slots(caller)
        memories = list(getattr(caller.db, "memories", None) or [])

        if len(memories) >= max_slots:
            # Drop the oldest memory to make room for the new one.
            memories.pop(0)

        memories.append(text)
        caller.db.memories = memories
        slot_num = len(memories)
        caller.msg(
            f"|gYou fix that thought in your mind.|n "
            f"(Memory {slot_num}/{max_slots})"
        )


class CmdMemory(Command):
    """
    Recall or remove the strings you've memorized.

    Usage:
      memory                    - list everything you currently remember
      memory <number>           - recall a specific entry (as listed)
      memory delete <number>    - forget that specific entry and free a slot
    """

    key = "memory"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        memories = list(getattr(caller.db, "memories", None) or [])

        # memory delete <number> – forget a specific entry
        low = args.lower()
        if low.startswith("delete ") or low.startswith("forget ") or low.startswith("remove "):
            _, _, rest = args.partition(" ")
            rest = rest.strip()
            if not rest or not rest.isdigit():
                caller.msg("Usage: memory delete <number>  (e.g. memory delete 2)")
                return
            index = int(rest)
            if index < 1 or index > len(memories):
                caller.msg("You don't have a memory with that number.")
                return
            removed = memories.pop(index - 1)
            caller.db.memories = memories
            caller.msg(f"|yYou let go of memory {index}:|n {removed}")
            return

        if not args:
            if not memories:
                max_slots = _get_memory_slots(caller)
                caller.msg(
                    f"You are not currently holding anything specific in memory. "
                    f"(You can remember up to {max_slots} memories; use |wmemorize <text>|n.)"
                )
                return

            max_slots = _get_memory_slots(caller)
            caller.msg(f"|wMemories ({len(memories)}/{max_slots}):|n")
            for i, text in enumerate(memories, start=1):
                caller.msg(f"  |w{i}.|n {text}")
            caller.msg("Use |wmemory <number>|n to recall one, |wmemory delete <number>|n to forget one, or |wmemorize <text>|n to store another.")
            return

        # memory <number> – recall a specific entry
        if not args.isdigit():
            caller.msg("Usage: memory [number]  (e.g. memory 2, or just memory to list all)")
            return

        index = int(args)
        if index < 1 or index > len(memories):
            caller.msg("You don't have a memory with that number.")
            return

        text = memories[index - 1]
        caller.msg(f"|wMemory {index}:|n {text}")


class CmdCount(Command):
    """
    Count how many things or people matching a name are in the room. When
    there are multiples, shows 1st, 2nd so you can target them in poses.

    Also used to check how much cash you're carrying. Use with no arguments,
    or with 'money' / 'cash', to count your on-hand funds.

    Usage:
      count              -- show your on-hand cash
      count money        -- show your on-hand cash
      count <name>       -- count matching objects/people in the room
    """
    key = "count"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from collections import defaultdict
        caller = self.caller
        location = caller.location
        if not location:
            caller.msg("You are not in a location.")
            return
        name_arg = (self.args or "").strip()

        # No args or money/cash keywords → show on-hand cash
        if not name_arg or name_arg.lower() in ("money", "cash", "funds", "credits"):
            from world.rpg.economy import get_balance, format_currency, CURRENCY_NAME
            amount = get_balance(caller)
            if amount == 0:
                caller.msg(f"You count your {CURRENCY_NAME}. You have nothing on hand.")
            else:
                caller.msg(
                    f"You count your {CURRENCY_NAME}. "
                    f"You have {format_currency(amount)} on hand."
                )
            return
        search = name_arg.lower()
        ordinals = ("1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th")

        def name_matches(display_name):
            if not display_name:
                return False
            dn = (display_name or "").strip().lower()
            return search in dn or dn in search

        # Characters in room (excluding caller)
        try:
            from evennia.utils.utils import inherits_from
            all_chars = [
                c for c in location.contents_get(content_type="character")
                if c != caller and location.filter_visible([c], caller) and inherits_from(c, "typeclasses.characters.Character")
            ]
        except Exception:
            all_chars = [c for c in location.contents_get(content_type="character") if c != caller and location.filter_visible([c], caller)]
        matching_chars = []
        for c in all_chars:
            name = c.get_display_name(caller) if hasattr(c, "get_display_name") else getattr(c, "key", str(c))
            if name_matches(name):
                matching_chars.append((name, c))

        # Objects in room (exclude exits, characters, vehicles)
        try:
            from typeclasses.rooms import _is_vehicle, _is_corpse
        except ImportError:
            _is_vehicle = lambda o: False
        all_objs = [
            o for o in location.contents
            if o not in all_chars and o != caller
            and not (getattr(o, "destination", None) is not None)
            and location.filter_visible([o], caller)
        ]
        all_objs = [o for o in all_objs if not _is_vehicle(o)]
        matching_objs = []
        for o in all_objs:
            name = o.get_display_name(caller) if hasattr(o, "get_display_name") else getattr(o, "key", str(o))
            if name_matches(name):
                matching_objs.append((name, o))

        lines = []
        # Report characters that matched
        if matching_chars:
            n = len(matching_chars)
            if n == 1:
                lines.append("There is 1 person matching |w%s|n here." % name_arg)
            else:
                ord_strs = [ordinals[i] if i < len(ordinals) else "%dth" % (i + 1) for i in range(n)]
                lines.append("There are %d people matching |w%s|n here (|w%s|n)." % (n, name_arg, ", ".join(ord_strs)))

        # Report objects that matched
        if matching_objs:
            n = len(matching_objs)
            plural = _count_pluralize(name_arg)
            if n == 1:
                lines.append("There is 1 |w%s|n here." % name_arg)
            else:
                ord_strs = [ordinals[i] if i < len(ordinals) else "%dth" % (i + 1) for i in range(n)]
                lines.append("There are %d %s here (|w%s|n)." % (n, plural, ", ".join(ord_strs)))

        if not lines:
            caller.msg("No one and nothing here matches |w%s|n." % name_arg)
        else:
            caller.msg(" ".join(lines))


class CmdRecog(Command):
    """
    Recognize someone by their description (sdesc) and give them a name you'll see.
    Until you recog them, you see their short description (e.g. 'a tall man'); after
    recog tall man as Bob you see 'Bob'. Use |wcount <sdesc>|n to see how many and 1st/2nd when there are multiples.

    Usage:
      recog                          - list who you've recognized
      recog <sdesc> as <name>        - remember this person as <name>
      forget <name>                  - stop recognizing them (you'll see sdesc again)
    """
    key = "recog"
    aliases = ["recognize", "forget"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.rpg.emote import resolve_sdesc_to_characters
        from world.rp_features import (
            get_display_name_for_viewer,
            get_character_sdesc_for_viewer,
            get_helmet_recog_for_viewer,
            set_helmet_recog_for_viewer,
            clear_helmet_recog_for_viewer,
        )
        try:
            from world.rpg.sdesc import character_has_mask_or_helmet
        except ImportError:
            character_has_mask_or_helmet = lambda c: False
        caller = self.caller
        location = caller.location
        args = (self.args or "").strip()
        if not location:
            caller.msg("You need to be in a room.")
            return
        chars_here = location.contents_get(content_type="character")
        chars_here = [c for c in chars_here if c != caller and location.filter_visible([c], caller)]
        if self.cmdstring == "forget":
            # forget <name> - clear recog by alias (permanent or helmet-only)
            if not args:
                caller.msg("Usage: forget <name>")
                return
            found = None
            for c in chars_here:
                perm = caller.recog.get(c) if hasattr(caller, "recog") else None
                temp = get_helmet_recog_for_viewer(caller, c)
                perm_match = perm and args.lower() in (perm or "").lower()
                temp_match = temp and args.lower() in (temp or "").lower()
                if perm_match or temp_match:
                    found = (c, perm_match, temp_match)
                    break
            if not found:
                caller.msg("You don't recognize anyone by that name.")
                return
            target, perm_match, temp_match = found
            perm = caller.recog.get(target) if hasattr(caller, "recog") else None
            temp = get_helmet_recog_for_viewer(caller, target)
            if perm_match:
                from world.rpg.trust import forget_trust_for_name

                caller.recog.remove(target)
                if perm:
                    forget_trust_for_name(caller, perm)
            if temp_match:
                from world.rpg.trust import forget_trust_for_name

                clear_helmet_recog_for_viewer(caller, target)
                if temp:
                    forget_trust_for_name(caller, temp)
            sdesc = get_display_name_for_viewer(target, caller)
            caller.msg("You no longer recognize them. You'll see them as: |w%s|n" % sdesc)
            return
        if not args:
            # list recogs (show both permanent and any active helmet-only ones)
            all_recogs = caller.recog.all()
            lines = []
            if all_recogs:
                for recog_name, obj in all_recogs.items():
                    if obj not in chars_here:
                        continue
                    seen = get_display_name_for_viewer(obj, caller)
                    lines.append("  %s (you see: %s)" % (recog_name, seen))
            # Helmet-only recogs for people here that don't have a permanent recog entry
            for c in chars_here:
                temp = get_helmet_recog_for_viewer(caller, c)
                if not temp:
                    continue
                # Skip if this same string is already a permanent recog entry
                if any(name == temp for name in all_recogs.keys()):
                    continue
                seen = get_display_name_for_viewer(c, caller)
                lines.append("  %s (helmeted; you see: %s)" % (temp, seen))
            if not lines:
                caller.msg("You haven't recognized anyone here. Use |wrecog <sdesc> as <name>|n (e.g. recog tall man as Bob).")
            else:
                caller.msg("|wRecognized here|n:\n" + "\n".join(lines))
            return
        if " as " not in args:
            caller.msg("Usage: recog <sdesc> as <name>   (e.g. recog tall man as Bob)")
            return
        sdesc_part, name_part = [x.strip() for x in args.split(" as ", 1)]
        if not sdesc_part or not name_part:
            caller.msg("Usage: recog <sdesc> as <name>")
            return
        name_part = name_part.rstrip(".,?!")
        matches = resolve_sdesc_to_characters(caller, chars_here, sdesc_part)
        if not matches:
            caller.msg("No one here matches |w%s|n. Use |wlook|n to see who's here and |wcount <sdesc>|n for 1st/2nd when there are duplicates." % sdesc_part)
            return
        if len(matches) > 1:
            caller.msg("Multiple people match. Be specific: |w1-%s as %s|n or |w2-%s as %s|n etc." % (sdesc_part, name_part, sdesc_part, name_part))
            return
        target = matches[0]
        # Matrix avatars have public identities — no recog needed or allowed.
        from typeclasses.matrix.avatars import MatrixAvatar
        if isinstance(target, MatrixAvatar):
            caller.msg("In the Matrix, identities are public. You already know who that is.")
            return
        # Decide whether this is a normal or helmet-only recog based on target's current appearance.
        if character_has_mask_or_helmet(target):
            # Helmet/mask on: set a temporary overlay that only applies while their face is hidden.
            before = get_character_sdesc_for_viewer(target, caller)
            set_helmet_recog_for_viewer(caller, target, name_part)
        else:
            # Normal recog: permanent name tied to their uncovered face; message should use the
            # *current* visible description (sdesc) before recog is applied.
            before = get_character_sdesc_for_viewer(target, caller)
            old_perm = caller.recog.get(target) if hasattr(caller, "recog") else None
            caller.recog.add(target, name_part)
            if old_perm and old_perm.strip().lower() != name_part.strip().lower():
                from world.rpg.trust import migrate_trust_rename

                migrate_trust_rename(caller, old_perm, name_part)
        caller.msg("You'll now see |w%s|n as |w%s|n." % (before, name_part))


class CmdBody(Command):
    """
    List or set body-part descriptions (shown when someone looks at you).
    You can use tokens $N (your name), $P/$p (possessive), $S/$s (subject). See help tokens.

    Usage:
      @body
      @body <body part> = <text>
      @body head = scarred and crooked
      @body lshoulder = $S has an old burn mark on $p shoulder

    Body parts (head to feet): head, face, leye, reye, lear, rear, neck, lshoulder,
    rshoulder, torso, back, abdomen, larm, rarm, lhand, rhand, groin, lthigh,
    rthigh, lfoot, rfoot
    """
    key = "@body"
    aliases = ["@describe_bodypart", "@descpart"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.body import body_part_groups_for_character
        caller = self.caller
        args = (self.args or "").strip()
        if "=" in args:
            _set_body_part_description(caller, args)
            return
        if not hasattr(caller, "db") or not hasattr(caller.db, "body_descriptions"):
            caller.msg("You cannot view body descriptions.")
            return
        # Show raw descriptions you set, not clothing-overridden (look uses effective desc)
        parts = caller.db.body_descriptions or {}
        caller.msg("|wYour body part descriptions|n (use |w@body <part> = <text>|n to set)")
        caller.msg("")
        order = []
        for group in body_part_groups_for_character(caller):
            order.extend(group)
        for part in order:
            text = (parts.get(part) or "").strip()
            if text:
                caller.msg(f"  |w{part}|n: {text}")
            else:
                caller.msg(f"  |w{part}|n: |x(not set)|n")


class CmdSdesc(Command):
    """
    View or customize your short description (the phrase in parentheses next to your name in the room).

    Usage:
      @sdesc                    - show your current sdesc and gender term
      @sdesc customize          - list choices for your gender; pick by number
      @sdesc set <term>         - set the gender term (e.g. @sdesc set lad, @sdesc set bloke)
      @sdesc custom <word>      - request a custom one-word term (staff approval required; max 15 chars)
    """
    key = "@sdesc"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.rpg.sdesc import get_short_desc, get_gender_term, get_gender_terms_list, _article_for
        from world.staff_pending import add_pending, get_pending
        caller = self.caller
        args = (self.args or "").strip().lower()
        # sdesc custom <word> - submit for staff approval
        if args.startswith("custom "):
            word = args[6:].strip()
            if not word:
                caller.msg("Usage: @sdesc custom <word>")
                caller.msg("Request a custom one-word gender term (max 15 characters). Staff must approve.")
                return
            if len(word) > 15:
                caller.msg("Custom term must be 15 characters or fewer.")
                return
            if len(word.split()) != 1:
                caller.msg("Custom term must be a single word.")
                return
            # One pending sdesc_gender_term per character
            for job in get_pending("sdesc_gender_term"):
                if job.get("requester_id") == getattr(caller, "id", None) or job.get("requester_id") == getattr(caller, "dbref", None):
                    caller.msg("You already have a pending custom term request. Wait for staff to approve or deny it.")
                    return
            job_id, ok = add_pending("sdesc_gender_term", caller, {"term": word})
            if not ok:
                caller.msg("The approval queue is unavailable. Try again later.")
                return
            caller.msg("|gYour request for the custom sdesc term |w%s|g has been submitted for staff approval. You will be notified when it is approved or denied.|n" % word)
            return
        # sdesc set <term>
        if args.startswith("set "):
            term = args[4:].strip()
            allowed = get_gender_terms_list(caller)
            if not term:
                caller.msg("Usage: @sdesc set <term>")
                caller.msg("Options: %s" % ", ".join(allowed))
                return
            if term not in [t.lower() for t in allowed]:
                caller.msg("That term isn't valid for your gender. Use |w@sdesc customize|n to see options.")
                return
            caller.db.sdesc_gender_term = term
            caller.db.sdesc_gender_term_custom = False  # clear custom flag when picking from list
            caller.msg("Your short description will now use |w%s|n (e.g. \"a rangy %s\")." % (term, term))
            return
        # sdesc customize: show numbered list
        if args == "customize" or args == "customise":
            allowed = get_gender_terms_list(caller)
            current = get_gender_term(caller)
            caller.msg("|wCurrent term:|n %s" % current)
            caller.msg("")
            caller.msg("|wChoose a term (use |w@sdesc set <term>|n):|n")
            for i, t in enumerate(allowed, 1):
                mark = " |y(current)|n" if t.lower() == current else ""
                caller.msg("  %2d: %s%s" % (i, t, mark))
            caller.msg("")
            caller.msg("Or request a custom one-word term (staff approval required, max 15 chars): |w@sdesc custom <word>|n")
            return
        # sdesc (no args): show current sdesc and term
        full = get_short_desc(caller, caller)
        current_term = get_gender_term(caller)
        caller.msg("|wYour short description:|n")
        caller.msg("  %s" % full)
        caller.msg("")
        article = _article_for(current_term)
        caller.msg("|wCurrently appearing as|n %s %s." % (article, current_term))
        caller.msg("Use |w@sdesc customize|n to see options, |w@sdesc set <term>|n to change, or |w@sdesc custom <word>|n to request a custom term.")


class CmdPending(Command):
    """
    View and resolve the staff pending-approval queue (custom sdesc terms, etc.).
    Use @pending so it is not overridden by the staff_pending channel nick.

    Usage:
      @pending              - list all pending jobs
      @pending approve <id> - approve (id = short id from channel, e.g. b841ccfc)
      @pending deny <id>     - deny
    """
    key = "@pending"
    aliases = ["staffpending", "approvals"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        from world.staff_pending import get_pending, get_by_id, resolve, _format_job_summary
        args = (self.args or "").strip().split()
        if len(args) >= 2 and args[0].lower() in ("approve", "deny"):
            action = args[0].lower()
            job_id = args[1].strip()
            if not job_id:
                self.caller.msg("Usage: @pending %s <id>   (id = short id from channel, e.g. b841ccfc)" % action)
                return
            success, msg = resolve(job_id, approved=(action == "approve"), staff_member=self.caller)
            self.caller.msg(msg)
            return
        pending = get_pending()
        if not pending:
            self.caller.msg("No pending approval requests.")
            return
        self.caller.msg("|wPending approval requests:|n")
        for job in pending:
            summary = _format_job_summary(job)
            if summary:
                self.caller.msg("  " + summary)
        self.caller.msg("Use |w@pending approve <id>|n or |w@pending deny <id>|n (id = short id from channel).")


class CmdLookPlace(Command):
    """
    Set how you appear in the room when someone looks (e.g. "standing here", "sitting by the fire").
    You can use tokens $N (your name), $P/$p (possessive), $S/$s (subject). See help tokens.

    Usage:
      @lp <text>
      @look_place <text>
      @lp                    (show current)
    """
    key = "@lp"
    aliases = ["@look_place", "@standing", "@roompose"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            # No args: clear any custom look-place so you fall back to the default.
            if hasattr(caller.db, "room_pose"):
                try:
                    del caller.db.room_pose
                except Exception:
                    caller.db.room_pose = None
            # Default fallback text matches room display: "is standing here"
            current = getattr(caller.db, "room_pose", None) or "is standing here"
            caller.msg(f"You clear your custom look-place. You now appear in the room as: |w{current}|n.")
            caller.msg("Use |w@lp <text>|n to set one again (e.g. @lp leaning against the wall).")
            return
        caller.db.room_pose = args
        pose = args.rstrip(".")
        caller.msg(f"When people look here, they will see: |w{caller.name} {pose}.|n")


class CmdTempPlace(Command):
    """
    Set a temporary look-place for your character that only lasts until you move rooms.
    This overrides your normal @lp while you remain in the current room.

    Usage:
      @tp <text>
      @tp                    (clear your temporary place)
    """

    key = "@tp"
    aliases = ["@temp_place"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            # Clear any temporary place; fall back to normal @lp / default.
            if hasattr(caller.db, "temp_room_pose"):
                try:
                    del caller.db.temp_room_pose
                except Exception:
                    caller.db.temp_room_pose = None
            # Show what they'll appear as now (using the same fallback as room look).
            base = getattr(caller.db, "room_pose", None)
            if not base or base.strip().lower() == "standing here":
                base = "is standing here"
            caller.msg(f"You clear your temporary place. You now appear in the room as: |w{caller.name} {base.rstrip('.')}|n.")
            caller.msg("Use |w@tp <text>|n to set a temporary one again (e.g. @tp leaning against the wall).")
            return
        caller.db.temp_room_pose = args
        pose = args.rstrip(".")
        caller.msg(f"For now (until you move rooms), people will see: |w{caller.name} {pose}.|n")


class CmdSleepPlace(Command):
    """
    Set how you appear when logged off (look line) and/or the message the room sees when you log off.
    Use $N $P $S in the text. See help tokens. The text you set is used directly in the room line
    (no automatic 'is' is added), so include a verb if you want one (e.g. "is sleeping here").

    Usage:
      @sp                         - show current appearance and log-off message
      @sp <text>                   - set how you appear when logged off (e.g. "sleeping here")
      @sp msg <text>               - set the message the room sees when you log off (e.g. "$N falls asleep.")
    """
    key = "@sleepplace"
    aliases = ["@sleep place", "@sleep_place", "@logout_pose"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            place = getattr(caller.db, "sleep_place", None) or "sleeping here"
            fall = getattr(caller.db, "fall_asleep_message", None) or "$N falls asleep."
            caller.msg(f"When logged off, you appear: |w{place}|n.")
            caller.msg(f"When you log off, the room sees: |w{fall}|n")
            caller.msg("Use |w@sleepplace <text>|n to set how you appear when logged off.")
            caller.msg("Use |w@sleepplace msg <text>|n to set the message the room sees when you log off.")
            return
        # @sleepplace msg <text> or @sleepplace message <text> -> set fall_asleep_message only
        if args.lower().startswith("msg ") or args.lower().startswith("message "):
            prefix = "msg " if args.lower().startswith("msg ") else "message "
            text = args[len(prefix):].strip()
            caller.db.fall_asleep_message = text if text else "$N falls asleep."
            caller.msg(f"When you log off, the room will see: |w{caller.db.fall_asleep_message}|n")
            return
        # @sleepplace <text> -> set sleep_place only (how you appear when logged off)
        caller.db.sleep_place = args
        pose = args.rstrip(".")
        caller.msg(f"When logged off, others will see you as: |w{caller.name} {pose}.|n")


class CmdWakeMsg(Command):
    """
    Set the message the room sees when you log on (e.g. "wakes up").
    Use $N for your name. See help tokens.

    Usage:
      @wakemsg <text>
      @wakemsg                 (show current)
    """
    key = "@wakemsg"
    aliases = ["@wake_up", "@wakeupmsg", "@loginmsg"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            current = getattr(caller.db, "wake_up_message", None) or "$N wakes up."
            caller.msg(f"When you log on, the room sees: |w{current}|n")
            caller.msg("Use |w@wakemsg <text>|n (e.g. @wakemsg $N stirs and opens $p eyes.).")
            return
        caller.db.wake_up_message = args
        caller.msg(f"Set. When you log on, the room will see: |w{args}|n")


class CmdFlatlineMsg(Command):
    """
    Set the message the room sees when you fall flatlined (dying). Use {name} for your name.

    Usage:
      @flatlinemsg <text>
      @flatlinemsg              (show current; clear to use default)
    """
    key = "@flatlinemsg"
    aliases = ["@flatline", "@deathmsg", "@dyingmsg"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            current = getattr(caller.db, "flatline_room_msg", None)
            if current:
                caller.msg(f"When you flatline, the room will see: |w{current}|n")
                caller.msg("Use |w@flatlinemsg <text>|n to change, or |w@flatlinemsg default|n to clear and use the default.")
            else:
                from world.death import DEFAULT_FLATLINE_ROOM_MSG
                caller.msg(f"Currently using the default: |w{DEFAULT_FLATLINE_ROOM_MSG}|n")
                caller.msg("Use |w@flatlinemsg <text>|n to customize (use {{name}} for your name).")
            return
        if args.lower() == "default":
            if hasattr(caller.db, "flatline_room_msg"):
                del caller.db.flatline_room_msg
            caller.msg("Cleared. The default flatline message will be used.")
            return
        caller.db.flatline_room_msg = args
        caller.msg(f"Set. When you flatline, the room will see: |w{args}|n")


class CmdSetPlace(Command):
    """
    Set how an object/item appears in the room when someone looks (e.g. "on the ground", "leaning against the wall").
    Only works on items and objects—you cannot set the place for characters (they use |w@lp|n).

    Usage:
      @sp <item> = <text>
      @sp <item>     (show current; clear with empty text)
    """
    key = "@sp"
    aliases = ["@setplace"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from evennia import DefaultCharacter
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: |w@sp <item> = <text>|n (e.g. @sp knife = lying in a pool of blood)")
            return
        if "=" in args:
            raw_name, _, text = args.partition("=")
            item_name = raw_name.strip()
            text = text.strip()
        else:
            item_name = args
            text = None
        if not item_name:
            caller.msg("Name an item: |w@sp <item> = <text>|n")
            return
        location = caller.location
        if not location:
            caller.msg("You are not in a room.")
            return
        obj = caller.search(item_name, location=location)
        if not obj:
            return
        # Optional per-object toggle: only allow @sp on items that explicitly opt in,
        # unless the caller has Builder+ permissions.
        # Builders can set obj.db.allow_setplace = True on templates or individual objects.
        if not getattr(obj.db, "allow_setplace", False):
            if not caller.check_permstring("Builder"):
                caller.msg("You cannot set the place for that.")
                return
        if isinstance(obj, DefaultCharacter):
            caller.msg("You can only set the place for objects and items, not for characters. Characters use |w@lp|n.")
            return
        try:
            from typeclasses.vehicles import Vehicle
            if isinstance(obj, Vehicle):
                caller.msg("You cannot set the place for vehicles; they appear as parked or idling based on the engine.")
                return
        except ImportError:
            pass
        if getattr(obj.db, "original_name", None):
            caller.msg("You cannot set the place for corpses.")
            return
        if text is None:
            current = getattr(obj.db, "room_pose", None) or "on the ground"
            caller.msg(f"|w{obj.get_display_name(caller)}|n appears here as: {current}.")
            caller.msg("To change: |w@sp {name} = <text>|n. To clear back to default: |w@sp {name} = |n".format(name=obj.get_display_name(caller)))
            return
        if not text:
            if obj.db.room_pose:
                del obj.db.room_pose
            caller.msg(f"Cleared. |w{obj.get_display_name(caller)}|n will now appear as: on the ground.")
            return
        obj.db.room_pose = text
        pose = text.rstrip(".")
        caller.msg(f"When people look here, they will see: |w{obj.get_display_name(caller)} {pose}.|n")


class CmdPronoun(Command):
    """Set your gender/pronouns for poses: male, female, or nonbinary (set in chargen; change here if needed)."""
    key = "@pronoun"
    locks = "cmd:all()"
    help_category = "Roleplay"

    def func(self):
        from world.rpg.emote import PRONOUN_MAP
        caller = self.caller
        arg = (self.args or "").strip().lower()
        if not arg:
            current = getattr(caller.db, "pronoun", None) or getattr(caller.db, "gender", None) or "nonbinary"
            caller.msg(f"Your gender/pronouns: |w{current}|n. Options: male, female, nonbinary.")
            return
        if arg not in PRONOUN_MAP:
            caller.msg("Choose one: male (he/his/him), female (she/her), nonbinary (they/their/them).")
            return
        caller.db.pronoun = arg
        caller.db.gender = arg
        caller.msg(f"Gender/pronouns set to |w{arg}|n.")


class CmdNoMatch(Command):
    """
    When no command matches, check if the line starts with '.' or ',' and run as emote.
    '.wave at Cairn.' and ',The stage is clear. I .look at Cairn.' work without typing 'emote'.
    """
    key = CMD_NOMATCH
    locks = "cmd:all()"

    def parse(self):
        # The entire raw input is the args — no command key to strip.
        self.args = (self.raw_string or "").strip()
        self.switches = []

    def func(self):
        raw = (self.args or "").strip()

        # Route through the universal pending-input dispatcher.
        # All multi-step flows (rent, food wizard, cosmetic, wire, etc.) are
        # registered in commands.pending_dispatch and checked here in one call.
        try:
            from commands.pending_dispatch import dispatch_pending_input
            if dispatch_pending_input(self.caller, raw):
                return
        except Exception:
            pass

        if raw.startswith("."):
            emote_text = raw[1:].strip()
            if emote_text:
                improvise = getattr(self.caller.ndb, "performance_improvising", False)
                _run_emote(self.caller, emote_text, improvise=improvise)
                return
        if raw.startswith(","):
            # Comma-start = emote with no-conjugate first segment (pass full string so comma is kept)
            if len(raw) > 1:
                improvise = getattr(self.caller.ndb, "performance_improvising", False)
                _run_emote(self.caller, raw, improvise=improvise)
                return
        self.caller.msg(
            "Command '%s' is not available. Type \"help\" for help." % (raw or "(empty)")
        )


class CmdPose(Command):
    """
    First-person roleplay pose. You write as yourself; the room sees third person.
    Targets in the pose (e.g. "at Cairn") see "you" instead of their name.

    Usage:
      .<first-person text>   (no space needed)
      pose <first-person text>

    Markers:
      .word  = verb (conjugated in third person: .look -> looks)
      ,      = no conjugation for this segment's first word (start with scene-setting)

    Examples:
      .wave my hand.
      pose ,The stage is calm. I .look at Cairn.
      pose nod to Kase and step back.
    """
    key = "pose"
    aliases = ["."]
    locks = "cmd:all()"
    help_category = "Roleplay"

    def parse(self):
        """If line starts with '.', treat everything after the dot as args."""
        raw = (self.raw_string or "").strip()
        if raw.startswith("."):
            self.args = raw[1:].strip()

    def func(self):
        improvise = getattr(self.caller.ndb, "performance_improvising", False)
        _run_emote(self.caller, self.args, improvise=improvise)


class CmdEmote(Command):
    """
    Simple emote: your name plus the exact text. No targeting, no pronoun/name replacement.
    Everyone in the room sees the same line.

    Usage:
      emote <text>

    Example:
      emote waves his hand at Cairn.
      Everyone sees: Bob waves his hand at Cairn.
    """
    key = "emote"
    locks = "cmd:all()"
    help_category = "Roleplay"

    def func(self):
        caller = self.caller
        text = (self.args or "").strip()
        if not text:
            caller.msg("Usage: emote <text>  (e.g. emote waves his hand at Cairn)")
            return
        name = caller.get_display_name(caller)
        msg = f"{name} {text.rstrip('.')}." if text and not text.endswith((".", "!", "?")) else f"{name} {text}"
        if getattr(caller.ndb, "performance_improvising", False):
            msg = "|w%s|n" % msg
            if caller.location:
                caller.location.msg_contents(msg)
                try:
                    from commands.performance_cmds import _audience_echo_improvise
                    _audience_echo_improvise(caller.location)
                except Exception:
                    pass
        elif caller.location:
            caller.location.msg_contents(msg)


class CmdTease(Command):
    """
    Use a clothing item's tease message.

    Two styles are supported:

      1) Token mode (legacy):
         - Wearer/doer: $N/$n name, $P/$p possessive, $S/$s subject.
         - Target (tease at): $T/$t name, $R/$r possessive, $U/$u subject.
         - Item (garment): $I/$i = item's display name (e.g. 't-shirt').
         Use .verb so it conjugates, e.g.:
           '$N .lift $p $I and .flash $p chest at $T.'

      2) Pose-style mode (simpler):
         - Write a normal first-person emote and use just $T for the target
           (and optionally $I/$i for the item), with no $N/$P/$S/$R/$U tokens.
         - Example template on the clothing:
             'I lift my shirt and show my chest to $T.'
         - When you run |wtease shirt at Bob|n:
             You see:   'I lift my shirt and show my chest to Bob.'
             Bob sees:  'He lifts his shirt and shows his chest to you.'
             Others:    'He lifts his shirt and shows his chest to Bob.'

    Same tokens work in |w@body|n part lines, lp/pose, and worndesc. See |whelp tokens|n.

    Usage:
      tease <clothing> [at <target>]
    """
    key = "tease"
    aliases = ["flaunt"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Usage: tease <clothing> [at <target>]")
            return
        args = self.args.strip()
        target = None
        if " at " in args:
            part, _, target_spec = args.partition(" at ")
            args = part.strip()
            target = caller.search(target_spec.strip())
            if not target:
                return
        clothing_spec = args
        worn = getattr(caller.db, "worn", None) or []
        # Prefer matching worn item by name or alias
        item = None
        for w in worn:
            if not hasattr(w, "key"):
                continue
            if clothing_spec.lower() in (w.key or "").lower():
                item = w
                break
            if hasattr(w, "aliases"):
                for a in w.aliases.all():
                    if clothing_spec.lower() in str(a).lower():
                        item = w
                        break
                if item:
                    break
        if not item:
            item = caller.search(clothing_spec, location=caller)
        if not item:
            caller.msg("You don't have or aren't wearing '%s'." % clothing_spec)
            return
        if item not in worn:
            caller.msg("You need to be wearing it to tease with it.")
            return
        template = getattr(item.db, "tease_message", None) or ""
        if not template:
            caller.msg("That item has no tease message set.")
            return
        from world.rpg.crafting import substitute_tease_for_viewer
        from world.rpg.emote import format_emote_message
        room = caller.location
        if not room:
            return
        for viewer in room.contents:
            if not hasattr(viewer, "msg"):
                continue
            body = substitute_tease_for_viewer(template, caller, target, viewer, item=item)
            if body:
                if viewer == caller:
                    viewer.msg(body)
                else:
                    from world.rpg.emote import format_emote_message

                    viewer.msg(format_emote_message(caller, viewer, body))
        return


class CmdSmell(Command):
    """
    Smell the room, yourself, someone else, or an object.

    Usage:
      smell               - smell the current room/area
      smell me            - smell yourself
      smell <target>      - smell a person or object here

    Characters and objects can define a 'smell' (and perfumes/rooms can
    override or add to a character's scent). If nothing special is set,
    you'll be told you don't notice anything particular.
    """

    key = "smell"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.smell import get_smell_for, format_smell_line
        from world.rpg.emote import resolve_sdesc_to_characters

        caller = self.caller
        args = (self.args or "").strip()

        # smell (no args) -> smell the room
        if not args:
            loc = caller.location
            if not loc:
                caller.msg("You are nowhere in particular; you don't smell anything noteworthy.")
                return
            smell = get_smell_for(loc)
            if not smell:
                caller.msg("You take a cautious sniff of the air but don't notice anything in particular.")
                return
            # Rooms: show their own line
            name = getattr(loc, "key", None) or "here"
            caller.msg(f"The air here smells {smell}.")
            return

        low = args.lower()
        # smell me / smell self
        if low in ("me", "self", "myself"):
            # First, echo the action.
            caller.msg("You discreetly smell yourself.")
            loc = caller.location
            if loc:
                try:
                    from world.rp_features import get_display_name_for_viewer
                    from world.rpg.emote import PRONOUN_MAP
                except ImportError:
                    get_display_name_for_viewer = None
                    PRONOUN_MAP = {}
                for viewer in loc.contents_get(content_type="character"):
                    if viewer == caller:
                        continue
                    if get_display_name_for_viewer:
                        name = get_display_name_for_viewer(caller, viewer)
                    else:
                        name = caller.get_display_name(viewer) if hasattr(caller, "get_display_name") else caller.key
                    pron_key = (getattr(caller.db, "pronoun", None) or getattr(caller.db, "gender", "neutral") or "neutral").lower()
                    sub, poss, obj = PRONOUN_MAP.get(pron_key, PRONOUN_MAP.get("neutral", ("they", "their", "them")))
                    reflexive = {"he": "himself", "she": "herself", "they": "themself"}.get(sub, "themself")
                    viewer.msg(f"{name} discreetly sniffs {reflexive}.")
            # Then show the actual smell result to the caller only.
            line = format_smell_line(caller, viewer=caller, prefix_name="You")
            if not line:
                caller.msg("You don't notice any particular scent on yourself.")
            else:
                # Replace "You smells" with "You smell" in case of grammar
                line = line.replace("You smells", "You smell")
                caller.msg(line)
            return

        location = caller.location
        if not location:
            caller.msg("You are not in a room to smell anyone or anything.")
            return

        # First try to resolve a character in the room by sdesc/recog
        chars_here = location.contents_get(content_type="character")
        chars_here = [c for c in chars_here if location.filter_visible([c], caller)]
        matches = resolve_sdesc_to_characters(caller, chars_here, args)
        target = None
        if matches:
            if len(matches) > 1:
                caller.msg("Multiple people match that. Be more specific (use 1-<sdesc> or <sdesc>-1, etc).")
                return
            target = matches[0]
        else:
            # Fallback: normal search for any object/exit/character
            target = caller.search(args, location=location)
            if not target:
                return

        # Now build the smell line for the target
        line = format_smell_line(target, viewer=caller)
        if not line:
            # Distinguish characters vs objects a bit
            try:
                from evennia import DefaultCharacter

                is_char = isinstance(target, DefaultCharacter)
            except Exception:
                is_char = getattr(target, "has_account", False) or bool(
                    getattr(getattr(target, "db", None), "is_npc", False)
                )
            if is_char:
                name = target.get_display_name(caller) if hasattr(target, "get_display_name") else getattr(target, "key", "They")
                caller.msg(f"You don't notice any particular scent on {name}.")
            else:
                name = target.get_display_name(caller) if hasattr(target, "get_display_name") else getattr(target, "key", "it")
                caller.msg(f"You don't notice any particular scent from {name}.")
            return

        caller.msg(line)
        return

class CmdSit(Command):
    """
    Sit on a seat (chair, couch, bench, etc.).
    Usage: sit <seat> / sit on <seat>
    """
    key = "sit"
    aliases = ["sit on"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if args.lower().startswith("on "):
            args = args[3:].strip()
        if getattr(caller.db, "grappled_by", None):
            caller.msg("You can't sit down while grappled. Use |wresist|n to break free.")
            return
        if not args:
            caller.msg("Sit on what? Usage: sit <seat>")
            return
        from typeclasses.seats import Seat, Bed
        obj = caller.search(args, location=caller.location)
        if not obj:
            return
        # Can sit on Seat or Bed
        if not isinstance(obj, (Seat, Bed)):
            caller.msg("You can only sit on furniture like chairs, couches, or beds.")
            return
        # Check capacity (sitting takes 1 slot)
        if not obj.has_room(posture="sitting"):
            caller.msg("There's no room left to sit there.")
            return
        # Clear any other seating/lying state
        if caller.db.lying_on:
            del caller.db.lying_on
        if caller.db.lying_on_table:
            del caller.db.lying_on_table
        caller.db.sitting_on = obj
        sname = obj.get_display_name(caller)
        cname = caller.get_display_name(caller) if hasattr(caller, "get_display_name") else caller.name

        # Use customizable transition messages from furniture
        sit_msg = getattr(obj.db, "sit_msg", None) or "You sit down on {obj}."
        sit_msg_room = getattr(obj.db, "sit_msg_room", None) or "{name} sits down on {obj}."

        caller.msg("|w%s|n" % sit_msg.format(name=cname, obj=sname))
        if caller.location and hasattr(caller.location, "contents_get"):
            for v in caller.location.contents_get(content_type="character"):
                if v == caller:
                    continue
                vname = caller.get_display_name(v) if hasattr(caller, "get_display_name") else caller.name
                v.msg(sit_msg_room.format(name=vname, obj=sname))


class CmdLieOnTable(Command):
    """
    Lie down on an operating table (for surgery) or a bed/cot (for rest).
    Usage: lie on <table|bed> / lie down on <table|bed>
    """
    key = "lie"
    aliases = ["lie down", "lie on"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if args.lower().startswith("on "):
            args = args[3:].strip()
        if getattr(caller.db, "grappled_by", None):
            caller.msg("You can't lie down while grappled. Use |wresist|n to break free.")
            return
        if not args:
            caller.msg("Lie on what? Usage: lie on <operating table|bed>")
            return
        from typeclasses.medical_tools import OperatingTable
        from typeclasses.seats import Bed
        obj = caller.search(args, location=caller.location)
        if not obj:
            return
        if isinstance(obj, OperatingTable):
            if obj.get_patient():
                caller.msg("Someone is already on the table. Wait for them to get up.")
                return
            caller.db.lying_on_table = obj
            caller.msg("|wYou lie down on the operating table. The metal is cold.|n")
            if caller.location and hasattr(caller.location, "contents_get"):
                for v in caller.location.contents_get(content_type="character"):
                    if v == caller:
                        continue
                    v.msg("%s lies down on the operating table." % (caller.get_display_name(v) if hasattr(caller, "get_display_name") else caller.name))
        elif isinstance(obj, Bed):
            # Check capacity (lying takes 3 slots)
            if not obj.has_room(posture="lying"):
                caller.msg("There's no room left on that bed.")
                return
            # Clear any other seating/lying state
            if caller.db.sitting_on:
                del caller.db.sitting_on
            if caller.db.lying_on_table:
                del caller.db.lying_on_table
            caller.db.lying_on = obj
            bname = obj.get_display_name(caller)
            cname = caller.get_display_name(caller) if hasattr(caller, "get_display_name") else caller.name

            # Use customizable transition messages from furniture
            lie_msg = getattr(obj.db, "lie_msg", None) or "You lie down on {obj}."
            lie_msg_room = getattr(obj.db, "lie_msg_room", None) or "{name} lies down on {obj}."

            caller.msg("|w%s|n" % lie_msg.format(name=cname, obj=bname))
            if caller.location and hasattr(caller.location, "contents_get"):
                for v in caller.location.contents_get(content_type="character"):
                    if v == caller:
                        continue
                    vname = caller.get_display_name(v) if hasattr(caller, "get_display_name") else caller.name
                    v.msg(lie_msg_room.format(name=vname, obj=bname))
        else:
            caller.msg("You can only lie on an operating table or a bed.")


class CmdGetOffTable(Command):
    """
    Get up from a seat, bed, or operating table.
    Usage: getup / stand (avoid 'get' prefix so 'get <item>' is not stolen)
    """
    key = "getup"
    aliases = ["stand up", "stand", "getoff", "getofftable"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if getattr(caller.db, "grappled_by", None):
            caller.msg("You can't get up while grappled. Use |wresist|n to break free.")
            return
        cleared = []
        if getattr(caller.db, "lying_on_table", None):
            cleared.append("operating table")
            del caller.db.lying_on_table
        if getattr(caller.db, "sitting_on", None):
            cleared.append("seat")
            del caller.db.sitting_on
        if getattr(caller.db, "lying_on", None):
            cleared.append("bed")
            del caller.db.lying_on
        if not cleared:
            caller.msg("You are not sitting or lying on anything.")
            return
        caller.msg("|wYou get up.|n")
        if caller.location and hasattr(caller.location, "contents_get"):
            for v in caller.location.contents_get(content_type="character"):
                if v == caller:
                    continue
                v.msg("%s gets up." % (caller.get_display_name(v) if hasattr(caller, "get_display_name") else caller.name))
