"""
Roleplay commands: pose, emote, no-match emote, tease, body part/place/voice/sdesc/pending, sit/lie/getup, pronoun.
"""

import re
from commands.base_cmds import Command
from evennia.commands.cmdhandler import CMD_NOMATCH
from evennia.utils import logger


def _resolve_body_part(name):
    """Resolve short alias or full name to canonical body part key, or None."""
    from world.medical import BODY_PARTS, BODY_PART_ALIASES
    raw = name.strip().lower()
    if raw in BODY_PARTS:
        return raw
    return BODY_PART_ALIASES.get(raw)


def _body_parts_usage_list():
    """Head-to-feet list with short names where available (for usage line)."""
    from world.medical import BODY_PARTS_HEAD_TO_FEET, BODY_PART_ALIASES
    rev = {v: k for k, v in BODY_PART_ALIASES.items()}
    return [rev.get(p, p) for p in BODY_PARTS_HEAD_TO_FEET]


def _run_emote(caller, text):
    """Shared emote logic for CmdEmote and CmdNoMatch."""
    from world.emote import (
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
    emitter_name = caller.get_display_name(caller)
    chars_here = location.filter_visible(location.contents_get(content_type="character"), caller)
    viewers = list(chars_here) + [caller]
    debug_on = getattr(caller.db, "emote_debug", False) and caller.account
    if debug_on:
        debug_on = caller.account.permissions.check("Builder") or caller.account.permissions.check("Admin")
    debug_lines = [] if debug_on else None
    room_line = None  # one canonical third-person line for cameras

    for viewer in viewers:
        if viewer == caller:
            # --- Improved: handle quote protection, echo to caller cleanly ---
            echo_parts = []
            for i, seg in enumerate(segments):
                # Strip leading comma (no-conjugate marker) so it doesn't appear in echo
                seg = seg.lstrip().lstrip(",").lstrip() if seg.strip().startswith(",") else seg
                # Treat '.word' in the middle of a pose as plain 'word' (e.g. '.look' -> 'look')
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
            # Join and ensure trailing punctuation
            full_echo = ". ".join(echo_parts).strip()
            if not full_echo.endswith((".", "!", "?", '"')):
                full_echo += "."
            # Capitalize first letter after each ". " (e.g. "calm. you" -> "calm. You")
            full_echo = re.sub(r"\.\s+(\w)", lambda m: ". " + m.group(1).upper(), full_echo)
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
                from world.survival import slur_text_if_drunk
                msg = slur_text_if_drunk(caller, msg)
            except Exception as e:
                logger.log_trace("roleplay_cmds._run_emote slur (you): %s" % e)
            if debug_lines is not None:
                debug_lines.append(("you", msg))
            caller.msg(msg)
        else:
            # --- THIRD PERSON VIEWERS ---
            body_parts = []
            for seg in segments:
                # Keep " .word" so first_to_third can conjugate those verbs (dot = verb tell)
                third = first_to_third(seg.strip(), caller)
                targets = find_targets_in_text(third, location.contents_get(content_type="character"), caller)
                body_parts.append(build_emote_for_viewer(third, viewer, targets, emitter_name))
            full_body = ". ".join(p.strip() for p in body_parts if p.strip())
            # Capitalize first letter after each ". " (e.g. "clear. he" -> "clear. He")
            full_body = re.sub(r"\.\s+(\w)", lambda m: ". " + m.group(1).upper(), full_body)
            # Optional voice tag in quoted speech (perception check, rare)
            try:
                from world.voice import get_voice_phrase, get_speaking_tag, voice_perception_check
                if get_voice_phrase(caller) and voice_perception_check(viewer, caller) and '"' in full_body:
                    idx = full_body.index('"')
                    full_body = full_body[: idx + 1] + get_speaking_tag(caller) + full_body[idx + 1 :]
            except Exception as e:
                logger.log_trace("roleplay_cmds._run_emote voice tag: %s" % e)
            if starts_with_comma:
                pronoun_key = getattr(caller.db, "pronoun", "neutral")
                full_body = replace_first_pronoun_with_name(full_body, pronoun_key, emitter_name)
                msg = full_body
            else:
                msg = format_emote_message(emitter_name, full_body)
            # Slur emote output for drunk callers (level 2+) for other viewers as well.
            try:
                from world.survival import slur_text_if_drunk
                msg = slur_text_if_drunk(caller, msg)
            except Exception:
                pass
            if debug_lines is not None:
                debug_lines.append((viewer.get_display_name(viewer), msg))
            viewer.msg(msg)

    # Build one neutral third-person line for cameras (viewer=None so no "you", all names)
    if segments:
        body_parts = []
        for seg in segments:
            third = first_to_third(seg.strip(), caller)
            targets = find_targets_in_text(third, location.contents_get(content_type="character"), caller)
            body_parts.append(build_emote_for_viewer(third, None, targets, emitter_name))
        full_body = ". ".join(p.strip() for p in body_parts if p.strip()).strip()
        full_body = re.sub(r"\.\s+(\w)", lambda m: ". " + m.group(1).upper(), full_body)
        if starts_with_comma:
            pronoun_key = getattr(caller.db, "pronoun", "neutral")
            full_body = replace_first_pronoun_with_name(full_body, pronoun_key, emitter_name)
            room_line = (full_body[0].upper() + full_body[1:]) if full_body and full_body[0].islower() else (full_body or "")
        else:
            room_line = format_emote_message(emitter_name, full_body)
    else:
        room_line = None
    if room_line:
        try:
            from typeclasses.broadcast import feed_cameras_in_location
            feed_cameras_in_location(location, room_line)
        except Exception as e:
            logger.log_trace("roleplay_cmds._run_emote feed_cameras: %s" % e)

    if debug_lines:
        caller.msg("|w--- Emote debug ---|n")
        for who, line in debug_lines:
            if who == "you":
                caller.msg(f"|yTo you:|n {line}")
            else:
                caller.msg(f"|yTo {who}:|n {line}")
        caller.msg("|w---|n")


class CmdDescribeBodypart(Command):
    """
    Set a body-part description for your character (shown when someone looks at you).
    You can use tokens $N (your name), $P/$p (possessive), $S/$s (subject). See help tokens.

    Usage:
      @describe_bodypart <body part> = <text>
      @describe_bodypart head = scarred and crooked
      @descpart lshoulder = $S has an old burn mark on $p shoulder

    Body parts (head to feet): head, face, neck, lshoulder, rshoulder, torso, back,
    abdomen, larm, rarm, lhand, rhand, groin, lthigh, rthigh, lfoot, rfoot
    """
    key = "@describe_bodypart"
    aliases = ["@descpart"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not hasattr(caller, "get_body_descriptions"):
            caller.msg("You cannot set body descriptions.")
            return
        if not self.args or "=" not in self.args:
            caller.msg("Usage: @describe_bodypart <body part> = <text>")
            caller.msg("Body parts: " + ", ".join(_body_parts_usage_list()))
            return
        raw, _, rest = self.args.partition("=")
        rest = rest.strip()
        if not rest:
            caller.msg("Provide a description after the =.")
            return
        part = _resolve_body_part(raw)
        if not part:
            caller.msg("Unknown body part. Use: " + ", ".join(_body_parts_usage_list()))
            return
        caller.get_body_descriptions()
        caller.db.body_descriptions[part] = rest
        caller.msg(f"Set your |w{part}|n description: {rest}")


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


class CmdBody(Command):
    """
    List all body parts and their current descriptions (head to feet).

    Usage:
      @body
    """
    key = "@body"
    help_category = "General"

    def func(self):
        from world.medical import BODY_PARTS_HEAD_TO_FEET
        caller = self.caller
        if not hasattr(caller, "db") or not hasattr(caller.db, "body_descriptions"):
            caller.msg("You cannot view body descriptions.")
            return
        # Show raw descriptions you set, not clothing-overridden (look uses effective desc)
        parts = caller.db.body_descriptions or {}
        caller.msg("|wYour body part descriptions|n (use |w@describe_bodypart <part> = <text>|n to set)")
        caller.msg("")
        for part in BODY_PARTS_HEAD_TO_FEET:
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
        from world.sdesc import get_short_desc, get_gender_term, get_gender_terms_list, _article_for
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
            current = getattr(caller.db, "room_pose", None) or "standing here"
            caller.msg(f"You appear in the room as: |w{current}|n.")
            caller.msg("Use |w@lp <text>|n to change it (e.g. @lp leaning against the wall).")
            return
        caller.db.room_pose = args
        pose = args.rstrip(".")
        caller.msg(f"When people look here, they will see: |w{caller.name} is {pose}.|n")


class CmdSleepPlace(Command):
    """
    Set how you appear when logged off (look line) and/or the message the room sees when you log off.
    Use $N $P $S in the text. See help tokens.

    Usage:
      @sp                         - show current appearance and log-off message
      @sp <text>                   - set how you appear when logged off (e.g. "sleeping here")
      @sp msg <text>               - set the message the room sees when you log off (e.g. "$N falls asleep.")
    """
    key = "@sp"
    aliases = ["@sleep place", "@sleep_place", "@sleepplace", "@logout_pose"]
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
            caller.msg("Use |w@sp <text>|n to set how you appear when logged off.")
            caller.msg("Use |w@sp msg <text>|n to set the message the room sees when you log off.")
            return
        # @sp msg <text> or @sp message <text> -> set fall_asleep_message only
        if args.lower().startswith("msg ") or args.lower().startswith("message "):
            prefix = "msg " if args.lower().startswith("msg ") else "message "
            text = args[len(prefix):].strip()
            caller.db.fall_asleep_message = text if text else "$N falls asleep."
            caller.msg(f"When you log off, the room will see: |w{caller.db.fall_asleep_message}|n")
            return
        # @sp <text> -> set sleep_place only (how you appear when logged off)
        caller.db.sleep_place = args
        caller.msg(f"When logged off, others will see you as: |w{caller.name} is {args.rstrip('.')}.|n")


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
      @setplace <item> = <text>
      @setplace <item>     (show current; clear with empty text)
    """
    key = "@setplace"
    aliases = []
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from evennia import DefaultCharacter
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: |w@setplace <item> = <text>|n (e.g. @setplace knife = lying in a pool of blood)")
            return
        if "=" in args:
            raw_name, _, text = args.partition("=")
            item_name = raw_name.strip()
            text = text.strip()
        else:
            item_name = args
            text = None
        if not item_name:
            caller.msg("Name an item: |w@setplace <item> = <text>|n")
            return
        location = caller.location
        if not location:
            caller.msg("You are not in a room.")
            return
        obj = caller.search(item_name, location=location)
        if not obj:
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
            caller.msg("To change: |w@setplace {name} = <text>|n. To clear back to default: |w@setplace {name} = |n".format(name=obj.get_display_name(caller)))
            return
        if not text:
            if obj.db.room_pose:
                del obj.db.room_pose
            caller.msg(f"Cleared. |w{obj.get_display_name(caller)}|n will now appear as: on the ground.")
            return
        obj.db.room_pose = text
        pose = text.rstrip(".")
        caller.msg(f"When people look here, they will see: |w{obj.get_display_name(caller)} is {pose}.|n")


class CmdPronoun(Command):
    """Set your gender/pronouns for poses: male, female, or nonbinary (set in chargen; change here if needed)."""
    key = "@pronoun"
    locks = "cmd:all()"
    help_category = "Roleplay"

    def func(self):
        from world.emote import PRONOUN_MAP
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

    def func(self):
        raw = (self.args or "").strip()
        if raw.startswith("."):
            emote_text = raw[1:].strip()
            if emote_text:
                _run_emote(self.caller, emote_text)
                return
        if raw.startswith(","):
            # Comma-start = emote with no-conjugate first segment (pass full string so comma is kept)
            if len(raw) > 1:
                _run_emote(self.caller, raw)
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
        _run_emote(self.caller, self.args)


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
        if caller.location:
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

    Same tokens work in describe_bodypart, lp/pose, and worndesc. See |whelp tokens|n.

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
        from world.crafting import substitute_tease_for_viewer
        from world.emote import format_emote_message
        room = caller.location
        if not room:
            return
        doer_name = caller.get_display_name(caller)
        for viewer in room.contents:
            if not hasattr(viewer, "msg"):
                continue
            body = substitute_tease_for_viewer(template, caller, target, viewer, item=item)
            if body:
                if viewer == caller:
                    viewer.msg(body)
                else:
                    viewer.msg(format_emote_message(doer_name, body))
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
        if not args:
            caller.msg("Sit on what? Usage: sit <seat>")
            return
        from typeclasses.seats import Seat
        seat = caller.search(args, location=caller.location)
        if not seat:
            return
        if not isinstance(seat, Seat):
            caller.msg("You can only sit on a chair, couch, or similar seat.")
            return
        if seat.get_sitter():
            caller.msg("Someone is already sitting there.")
            return
        caller.db.sitting_on = seat
        sname = seat.get_display_name(caller)
        caller.msg("|wYou sit down on %s.|n" % sname)
        if caller.location:
            caller.location.msg_contents(
                "%s sits down on %s." % (caller.name, sname),
                exclude=caller,
            )


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
            if caller.location:
                caller.location.msg_contents(
                    "%s lies down on the operating table." % caller.name,
                    exclude=caller,
                )
        elif isinstance(obj, Bed):
            if obj.get_occupant():
                caller.msg("Someone is already lying there.")
                return
            caller.db.lying_on = obj
            bname = obj.get_display_name(caller)
            caller.msg("|wYou lie down on %s.|n" % bname)
            if caller.location:
                caller.location.msg_contents(
                    "%s lies down on %s." % (caller.name, bname),
                    exclude=caller,
                )
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
        if caller.location:
            caller.location.msg_contents(
                "%s gets up." % caller.name,
                exclude=caller,
            )
