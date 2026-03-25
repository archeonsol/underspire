"""
Base commands: Command (flatline/dead blocking), _command_character, CmdLook, CmdExamine, CmdGet, CmdPut.
"""

import re
from evennia.utils import logger
from evennia.commands.command import Command as BaseCommand
from evennia.commands.default.general import CmdLook as DefaultCmdLook

try:
    from evennia.commands.default.general import CmdGet as DefaultCmdGet
except ImportError:
    DefaultCmdGet = None

# Lock string for admin-only commands (Builder and Admin accounts)
ADMIN_LOCK = "cmd:perm(Builder) or perm(Admin)"


def _command_character(self):
    """Resolve to the puppeted character when command runs with Account as caller (e.g. Session cmdset)."""
    caller = self.caller
    if getattr(self, "session", None) and getattr(self.session, "puppet", None):
        puppet = self.session.puppet
        if puppet and (getattr(caller, "db", None) is None or not hasattr(caller.db, "current_hp")):
            return puppet
    return caller


def _stealth_and_hide_at_pre_cmd(cmd_self):
    """
    Hide-cancel + stealth reveal. Used by Command and by CmdLook (which must stay
    DefaultCmdLook-only so Evennia's parse/func chain is not replaced by Command.parse).
    Returns True if the command should abort (caller blocked).
    """
    caller = cmd_self.caller
    if not caller:
        return False
    char = _command_character(cmd_self)
    try:
        from world.rpg import stealth

        if getattr(char.ndb, "hide_pending", False):
            cmd_key = (getattr(cmd_self, "key", None) or "").strip().lower()
            if not cmd_key:
                raw = getattr(cmd_self, "raw_string", "") or ""
                part = raw.strip().split(None, 1)
                cmd_key = (part[0] if part else "").lower()
            if cmd_key != "hide":
                stealth.cancel_hide_pending(char, None)
                return True
        if getattr(char.db, "stealth_hidden", False) and stealth.command_breaks_stealth(cmd_self):
            stealth.reveal(char, reason="action")
    except Exception:
        pass
    return False


class Command(BaseCommand):
    # Flatline/dead blocking lives in at_pre_cmd (character_can_act). Subclasses must
    # define their own docstring for help; __doc__ is empty so Evennia's CommandMeta does
    # not copy this class's text onto children that omit one (see _init_command in
    # evennia.commands.command).
    __doc__ = ""

    def parse(self):
        """Extract switches and args from raw_string. Sets self.switches (list) and self.args (str)."""
        raw = self.raw_string or ""
        try:
            import ftfy
            raw = ftfy.fix_text(raw)
            self.raw_string = raw
        except Exception:
            pass
        self.switches = []
        parts = raw.split(None, 1)
        if parts:
            segments = parts[0].split("/")
            if len(segments) > 1:
                self.switches = [s.lower() for s in segments[1:] if s]
            self.args = parts[1].strip() if len(parts) > 1 else ""
        else:
            self.args = ""

    def at_pre_cmd(self):
        """Block commands if character is flatlined (dying) or permanently dead."""
        from world.profiling import record_command_start
        record_command_start(self)
        caller = self.caller
        if not caller:
            return super().at_pre_cmd()
        char = _command_character(self)
        from world.death import character_can_act
        can_act, msg = character_can_act(char, allow_builders=True)
        if not can_act and msg:
            caller.msg(msg)
            return True
        if _stealth_and_hide_at_pre_cmd(self):
            return True
        return super().at_pre_cmd()

    def at_post_cmd(self):
        from world.profiling import record_command_end
        record_command_end(self)
        return super().at_post_cmd()


class CmdLook(DefaultCmdLook):
    """
    Look at location, object, or a directional exit.

    Usage:
      look
      look <obj>
      look <direction>   (e.g. look north, look n)
    """

    def at_pre_cmd(self):
        """Flatline/dead, hide-pending cancel, stealth break — keep DefaultCmdLook.parse."""
        from world.profiling import record_command_start

        record_command_start(self)
        caller = self.caller
        if not caller:
            return super().at_pre_cmd() if hasattr(super(), "at_pre_cmd") else None
        char = _command_character(self)
        from world.death import character_can_act

        can_act, msg = character_can_act(char, allow_builders=True)
        if not can_act and msg:
            caller.msg(msg)
            return True
        if _stealth_and_hide_at_pre_cmd(self):
            return True
        return super().at_pre_cmd() if hasattr(super(), "at_pre_cmd") else None

    def at_post_cmd(self):
        from world.profiling import record_command_end

        record_command_end(self)

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()

        # Look at a character *in* a printed photograph:
        #   look <target> in <photograph>
        # This proxies to target.return_appearance(caller) and also allows recog from a photo.
        if args and " in " in args:
            left, _, right = args.partition(" in ")
            target_spec = (left or "").strip()
            photo_spec = (right or "").strip()
            if target_spec and photo_spec:
                # Search for the photograph in inventory first, then room.
                candidates = list(getattr(caller, "contents", []) or [])
                if getattr(caller, "location", None):
                    candidates += list(getattr(caller.location, "contents", []) or [])
                photo = caller.search(photo_spec, candidates=candidates)
                if photo:
                    try:
                        from typeclasses.broadcast import Photograph
                    except Exception:
                        Photograph = None
                    if Photograph and isinstance(photo, Photograph):
                        # Resolve which characters were captured in the photo.
                        snap_chars = getattr(getattr(photo, "db", None), "snapshot_chars", None) or {}
                        char_objs = []
                        try:
                            from evennia.utils.search import search_object
                            for cid in snap_chars.keys():
                                try:
                                    ref = "#%s" % int(cid)
                                    result = search_object(ref)
                                    if result:
                                        char_objs.append(result[0])
                                except Exception:
                                    continue
                        except Exception:
                            char_objs = []

                        if not char_objs:
                            caller.msg("That photograph doesn't seem to have anyone in it.")
                            return

                        # Allow matching by sdesc/recog (viewer-aware), including 1- / 2- prefixes.
                        target = None
                        try:
                            from world.rpg.emote import resolve_sdesc_to_characters
                            matches = resolve_sdesc_to_characters(caller, char_objs, target_spec)
                            if matches:
                                if len(matches) > 1:
                                    caller.msg("Multiple people in the photo match that. Be more specific (use 1-<sdesc> or <sdesc>-1, etc).")
                                    return
                                target = matches[0]
                        except Exception:
                            target = None

                        # Fallback: try plain substring match against display names.
                        if not target:
                            low = target_spec.lower()
                            hits = []
                            for c in char_objs:
                                try:
                                    dn = c.get_display_name(caller)
                                except Exception:
                                    dn = getattr(c, "key", "")
                                if low and dn and low in dn.lower():
                                    hits.append(c)
                            if len(hits) == 1:
                                target = hits[0]
                            elif len(hits) > 1:
                                caller.msg("Multiple people in the photo match that. Be more specific.")
                                return

                        if not target:
                            caller.msg("You can't find anyone in that photograph matching '%s'." % target_spec)
                            return

                        # Show their (snapshot) appearance captured at photo time, not their current state.
                        try:
                            cid = str(getattr(target, "id", ""))
                        except Exception:
                            cid = ""
                        detail = ""
                        try:
                            detail = (snap_chars.get(cid, {}) or {}).get("detail") or ""
                        except Exception:
                            detail = ""
                        if not detail:
                            caller.msg("That photograph doesn't have a detailed close-up for them (it may be an older photo).")
                            return
                        # Resolve placeholders in the stored detail to the viewer's display names.
                        try:
                            pattern = re.compile(r"<<CHAR:(\d+)>>")
                            viewer_tags = {}
                            try:
                                viewer_id = str(getattr(caller, "id", ""))
                                viewer_tags = (getattr(getattr(photo, "db", None), "photo_recogs", None) or {}).get(viewer_id, {}) or {}
                            except Exception:
                                viewer_tags = {}

                            def _sub(match):
                                oid = match.group(1)
                                try:
                                    tagged = (viewer_tags or {}).get(str(oid))
                                except Exception:
                                    tagged = None
                                if tagged:
                                    return tagged
                                from evennia.utils.search import search_object
                                try:
                                    ref = "#%s" % int(oid)
                                    result = search_object(ref)
                                    obj = result[0] if result else None
                                except Exception:
                                    obj = None
                                if obj and hasattr(obj, "get_display_name"):
                                    try:
                                        return obj.get_display_name(caller)
                                    except Exception:
                                        pass
                                try:
                                    fallback = (snap_chars or {}).get(str(oid), {}).get("sdesc")
                                except Exception:
                                    fallback = None
                                return fallback or "someone"

                            detail = pattern.sub(_sub, detail)
                        except Exception:
                            pass
                        caller.msg(detail)

                        return

        # Directional look: look north / look n, etc.
        if args:
            lower = args.lower()
            dir_map = {
                "n": "north",
                "s": "south",
                "e": "east",
                "w": "west",
                "ne": "northeast",
                "nw": "northwest",
                "se": "southeast",
                "sw": "southwest",
                "u": "up",
                "d": "down",
            }
            direction = dir_map.get(lower, lower)
            loc = getattr(caller, "location", None)
            if loc:
                # Find an exit in this room whose key or alias matches the direction
                exits = [obj for obj in loc.contents if getattr(obj, "destination", None)]
                target_exit = None
                for ex in exits:
                    key = (getattr(ex, "key", "") or "").lower()
                    # ex.aliases is an AliasHandler; use .all() to get strings
                    aliases = []
                    if hasattr(ex, "aliases"):
                        try:
                            aliases = [a.lower() for a in ex.aliases.all()]
                        except Exception as e:
                            logger.log_trace("base_cmds.CmdLook exit aliases: %s" % e)
                            aliases = []
                    if direction == key or direction in aliases:
                        target_exit = ex
                        break
                if target_exit and target_exit.destination:
                    # Door check: if the exit has a door, handle closed/open messaging.
                    if getattr(target_exit.db, "door", None):
                        if not getattr(target_exit.db, "door_open", None):
                            # Determine what kind of door it is for the hint suffix.
                            try:
                                from world.rpg.rentable_doors import is_rentable, is_paired_with_rentable
                                _is_keypad = is_rentable(target_exit) or is_paired_with_rentable(target_exit)
                            except Exception:
                                _is_keypad = False
                            _is_bioscan = bool(getattr(target_exit.db, "bioscan", None))

                            if _is_bioscan:
                                suffix = " It requires a biometric scan to open."
                            elif _is_keypad:
                                suffix = " It requires a code to open."
                            else:
                                suffix = ""

                            caller.msg(f"The door to the {direction} is |wclosed|n.{suffix}")
                            return
                        # Door is open — fall through to peek-through logic below.

                    dest = target_exit.destination
                    # Collect visible characters in the destination room (players and NPCs, but not corpses).
                    contents = getattr(dest, "contents", [])
                    try:
                        from typeclasses.corpse import Corpse
                        def _is_char(o):
                            if isinstance(o, Corpse):
                                return False
                            if getattr(o, "has_account", False):
                                return True
                            return bool(getattr(getattr(o, "db", None), "is_npc", False))
                        chars = [o for o in contents if _is_char(o)]
                    except Exception:
                        chars = [
                            o for o in contents
                            if getattr(o, "has_account", False) or bool(getattr(getattr(o, "db", None), "is_npc", False))
                        ]
                    try:
                        from world.rpg import stealth

                        chars = [c for c in chars if not (stealth.is_hidden(c) and not stealth.has_spotted(caller, c))]
                    except Exception:
                        pass
                    if not chars:
                        caller.msg(f"To the {direction} you see |wnothing of note|n.")
                        return
                    # Build a natural-language list: John, Bob and James
                    names = [obj.get_display_name(caller) for obj in chars]
                    if len(names) == 1:
                        who = names[0]
                    elif len(names) == 2:
                        who = f"{names[0]} and {names[1]}"
                    else:
                        who = ", ".join(names[:-1]) + f" and {names[-1]}"
                    caller.msg(f"To the {direction} you see {who}.")
                    return

        # Fallback to default look behavior (objects, room, etc.)
        super().func()


class CmdStopWalking(Command):
    """
    Stop a pending staggered walk and clear any queued compass steps.

    Usage:
      stop walking
    """

    key = "stop walking"
    aliases = ["stop walk", "halt walking", "halt walk"]
    locks = "cmd:all()"
    help_category = "Movement"

    def func(self):
        caller = _command_character(self)
        if not getattr(caller, "db", None):
            self.caller.msg("You must be in character to do that.")
            return
        # Same as interrupt_staggered_walk (combat/grapple use that helper too).
        try:
            from world.rpg.staggered_movement import interrupt_staggered_walk

            already_set = bool(getattr(caller.db, "cancel_walking", False))
            interrupt_staggered_walk(caller, notify_msg=None)
        except ImportError:
            already_set = bool(getattr(caller.db, "cancel_walking", False))
            try:
                from world.rpg.staggered_movement import clear_stagger_walk_pending, clear_walk_queue

                clear_stagger_walk_pending(caller)
                clear_walk_queue(caller)
            except ImportError:
                pass
            caller.db.cancel_walking = True
        if already_set:
            self.caller.msg("You steady yourself, keeping from walking off anywhere.")
        else:
            self.caller.msg("You stop walking.")


class CmdStop(Command):
    """
    Stop one specific thing you are doing. Bare |wstop|n does nothing.

    Usage:
      stop following   — end follow/shadow
      stop escorting   — end escort (leading or being led)
      stop hiding      — cancel trying to hide, or step out if hidden
      stop sneaking    — abort a pending sneak move
      stop attacking   — stop combat swings (|wstop attacking <name>|n optional)
      cease            — same as |wstop attacking|n with your current target
    """

    key = "stop"
    aliases = ["cease"]
    locks = "cmd:all()"
    help_category = "General"

    def at_pre_cmd(self):
        """Let |wstop hiding|n reach func without hide-pending cancel (that would abort the command)."""
        raw_l = (self.raw_string or "").strip().lower()
        if raw_l.startswith("stop hiding") or raw_l.startswith("stop hide"):
            from world.profiling import record_command_start

            record_command_start(self)
            caller = self.caller
            if not caller:
                return super().at_pre_cmd()
            char = _command_character(self)
            from world.death import character_can_act

            can_act, msg = character_can_act(char, allow_builders=True)
            if not can_act and msg:
                caller.msg(msg)
                return True
            return False
        return super().at_pre_cmd()

    def func(self):
        caller = _command_character(self)
        if not getattr(caller, "db", None):
            self.caller.msg("You must be in character to do that.")
            return

        raw = (self.raw_string or "").strip()
        parts = raw.split(None, 1)
        verb = (parts[0] or "").lower() if parts else ""
        tail = parts[1].strip() if len(parts) > 1 else ""

        usage = (
            "Stop what? Specify: |wstop following|n, |wstop escorting|n, |wstop hiding|n, "
            "|wstop sneaking|n, or |wstop attacking|n (|wcease|n = stop attacking)."
        )

        if verb == "cease":
            self._stop_attacking(caller, tail)
            return

        if verb != "stop":
            return

        if not tail:
            caller.msg(usage)
            return

        mode = tail.split(None, 1)[0].lower()
        rest = ""
        tsplit = tail.split(None, 1)
        if len(tsplit) > 1:
            rest = tsplit[1].strip()

        if mode in ("following", "follow"):
            from commands.follow_cmds import stop_following_activity

            stop_following_activity(caller)
        elif mode in ("escorting", "escort"):
            from commands.follow_cmds import stop_escorting_activity

            stop_escorting_activity(caller)
        elif mode in ("hiding", "hide"):
            self._stop_hiding(caller)
        elif mode in ("sneaking", "sneak"):
            self._stop_sneaking(caller)
        elif mode == "attacking":
            self._stop_attacking(caller, rest)
        else:
            caller.msg(usage)

    def _stop_hiding(self, caller):
        from world.rpg import stealth

        if getattr(caller.ndb, "hide_pending", False):
            stealth.cancel_hide_pending(caller, "|xYou stop trying to hide.|n")
            return
        if stealth.is_hidden(caller):
            stealth.reveal(caller, reason="action")
            return
        caller.msg("|xYou are not hiding.|n")

    def _stop_sneaking(self, caller):
        if not getattr(caller.ndb, "_stealth_move_sneak", False):
            caller.msg("|xYou are not sneaking anywhere.|n")
            return
        try:
            from world.rpg.staggered_movement import interrupt_staggered_walk

            was = interrupt_staggered_walk(caller, notify_msg="|xYou abort your sneaking move.|n")
        except ImportError:
            was = False
        try:
            if hasattr(caller.ndb, "_stealth_move_sneak"):
                del caller.ndb._stealth_move_sneak
        except Exception:
            pass
        if not was:
            caller.msg("|xYou are not sneaking anywhere.|n")

    def _stop_attacking(self, caller, target_name: str):
        from world.combat import stop_combat_ticker, _get_combat_target

        tn = (target_name or "").strip()
        if not tn:
            current = _get_combat_target(caller)
            if not current:
                caller.msg("You're not in combat.")
                return
            stop_combat_ticker(caller, current)
            return
        target = caller.search(tn)
        if not target:
            return
        stop_combat_ticker(caller, target)


class CmdGo(Command):
    """
    Queue multiple compass steps (same staggered pacing as using exits).
    If a walk is already in progress, new directions are appended to the queue.

    Usage:
      go w w w
      go north east
    """

    key = "go"
    aliases = ["walk", "queue walk", "walkqueue"]
    locks = "cmd:all()"
    help_category = "Movement"

    def func(self):
        caller = _command_character(self)
        if not getattr(caller, "db", None):
            self.caller.msg("You must be in character to do that.")
            return
        try:
            from world.rpg.staggered_movement import (
                extend_walk_queue,
                is_staggered_walk_pending,
                is_valid_compass_token,
                normalize_move_direction,
                seed_walk_queue_and_start_first,
            )
        except ImportError:
            self.caller.msg("Movement queue is unavailable.")
            return
        parts = (self.args or "").strip().split()
        if not parts:
            self.caller.msg("Usage: |wgo <direction> [<direction> ...]|n  e.g. |wgo w w w|n")
            return
        norms = []
        for tok in parts:
            if not is_valid_compass_token(tok):
                self.caller.msg(f"Unknown direction: {tok}")
                return
            norms.append(normalize_move_direction(tok))
        if is_staggered_walk_pending(caller):
            extend_walk_queue(caller, norms)
            self.caller.msg(
                "You add " + ", ".join(parts) + " to your route after your current step."
            )
            return
        ok, err = seed_walk_queue_and_start_first(caller, norms)
        if not ok:
            self.caller.msg(err or "You can't go that way.")
            return


class CmdExamine(Command):
    """
    Player examine: look at an object and see what commands you can use with it.

    Usage:
      examine <object>
      ex <object>
    """
    # Player-facing examine (no @). Staff continue to use Evennia's default
    # '@examine' from the base cmdset for builder/staff-style inspection.
    key = "examine"
    aliases = ["ex"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Examine what? Usage: examine <object>")
            return
        obj = caller.search(self.args.strip(), location=caller.location)
        if not obj:
            # Try inventory
            obj = caller.search(self.args.strip(), location=caller)
        if not obj:
            return
        # Description (same as look)
        try:
            appearance = obj.return_appearance(caller)
            if appearance:
                caller.msg(appearance)
        except Exception:
            desc = obj.get_display_desc(caller) if hasattr(obj, "get_display_desc") else getattr(obj.db, "desc", None)
            if desc:
                caller.msg(desc)
        # Player-usable command hints
        try:
            from world.examine import get_usage_hints
            hints = get_usage_hints(obj)
            if hints:
                caller.msg("\n|wYou can use:|n " + ", ".join(hints))
            else:
                caller.msg("\n|wYou can use:|n Nothing special (get, drop, give if portable).")
        except Exception as e:
            logger.log_trace("base_cmds.CmdExamine usage: %s" % e)
            caller.msg(f"\n|y(Could not determine usage: {e})|n")


class CmdGet(DefaultCmdGet if DefaultCmdGet else BaseCommand):
    """Get: supports 'get <item> from <container>'; from corpse, unconscious, or logged-off (30+ min) when allowed."""
    key = "get"
    aliases = ["take", "pick up"]

    def at_pre_cmd(self):
        """Block when flatlined/dead (CmdGet does not inherit from Command)."""
        from world.profiling import record_command_start
        record_command_start(self)
        char = _command_character(self)
        from world.death import character_can_act
        can_act, msg = character_can_act(char, allow_builders=True)
        if not can_act and msg:
            self.caller.msg(msg)
            return True
        return super().at_pre_cmd() if hasattr(super(), "at_pre_cmd") else None

    def at_post_cmd(self):
        from world.profiling import record_command_end
        record_command_end(self)

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            if DefaultCmdGet:
                super().func()
            else:
                caller.msg("Get what?")
            return

        # Cash pile interception: if the target is a cash pile, convert it to
        # wallet funds instead of moving it to inventory.
        if " from " not in args:
            try:
                obj = caller.search(args, location=caller.location, quiet=True)
                if obj:
                    import evennia.utils.utils as _utils
                    obj_list = _utils.make_iter(obj)
                    if obj_list:
                        candidate = obj_list[0]
                        if candidate.tags.get("cash_pile", category="economy"):
                            from world.rpg.economy import add_funds, format_currency, CURRENCY_NAME
                            amount = int(getattr(candidate.db, "cash_amount", 0) or 0)
                            if amount > 0:
                                add_funds(caller, amount, party="ground", reason="picked up cash")
                                caller.msg(
                                    f"You scoop up {format_currency(amount)}."
                                )
                                caller.location.msg_contents(
                                    f"|w{caller.key}|n picks up a pile of {CURRENCY_NAME}.",
                                    exclude=[caller],
                                )
                            else:
                                caller.msg("The pile is empty.")
                            candidate.delete()
                            return
            except Exception:
                pass

        if " from " not in args:
            if DefaultCmdGet:
                super().func()
            return
        # Parse "get <item> from <container>" — default CmdGet does NOT support this, so we handle it fully
        item_spec, _, container_spec = args.partition(" from ")
        item_spec = item_spec.strip()
        container_spec = container_spec.strip()
        if not item_spec or not container_spec:
            caller.msg("Usage: get <item> from <container>")
            return
        container = caller.search(container_spec, location=caller.location)
        if not container:
            return
        try:
            from typeclasses.corpse import Corpse
            from evennia import DefaultCharacter
            from world.death import is_character_logged_off, character_logged_off_long_enough
            if isinstance(container, DefaultCharacter) and not isinstance(container, Corpse):
                try:
                    from world.medical import is_unconscious as _is_unconscious

                    target_is_unconscious = _is_unconscious(container)
                except ImportError as e:
                    logger.log_trace("base_cmds.CmdGet is_unconscious: %s" % e)
                    target_is_unconscious = False

                if is_character_logged_off(container):
                    if not character_logged_off_long_enough(container):
                        caller.msg(
                            "They haven't been gone long enough. You can only take from someone who's been logged off at least half an hour."
                        )
                        return
                elif not target_is_unconscious:
                    caller.msg("You can't take from someone who's wide awake!")
                    return
        except ImportError as e:
            logger.log_trace("base_cmds.CmdGet get-from-container check: %s" % e)
        # Search for the item inside the container (contents, not location=caller.location)
        obj = caller.search(item_spec, location=container)
        if not obj:
            return
        from evennia.utils import utils
        objs = utils.make_iter(obj)
        if len(objs) == 1 and objs[0] == caller:
            caller.msg("You can't get yourself.")
            return
        for o in objs:
            if not o.access(caller, "get"):
                err = getattr(getattr(o, "db", None), "get_err_msg", None)
                caller.msg(err if err else "You can't get that.")
                return
            if not o.at_pre_get(caller):
                return
        moved = []
        for o in objs:
            if o.move_to(caller, quiet=True, move_type="get"):
                moved.append(o)
                o.at_get(caller)
        if not moved:
            caller.msg("That can't be picked up.")
        else:
            obj_name = moved[0].get_numbered_name(len(moved), caller, return_string=True)
            caller.msg("You get %s from %s." % (obj_name, container.get_display_name(caller)))
            caller.location.msg_contents(
                "%s gets %s from %s." % (caller.get_display_name(caller), obj_name, container.get_display_name(caller)),
                exclude=caller,
            )


class CmdPut(Command):
    """Put an object you're holding into a container (e.g. put cassette in television)."""
    key = "put"
    aliases = ["insert"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller or not caller.location:
            return
        args = (self.args or "").strip()
        if " in " not in args and " into " not in args:
            self.caller.msg("Usage: put <item> in <container>")
            return
        for sep in (" in ", " into "):
            if sep in args:
                item_spec, _, container_spec = args.partition(sep)
                break
        else:
            item_spec = container_spec = ""
        item_spec = item_spec.strip()
        container_spec = container_spec.strip()
        if not item_spec or not container_spec:
            self.caller.msg("Usage: put <item> in <container>")
            return
        obj = caller.search(item_spec, location=caller)
        if not obj:
            return
        container = caller.search(container_spec, location=caller.location)
        if not container:
            return
        if container == caller:
            self.caller.msg("You can't put something into yourself.")
            return
        if obj == container:
            self.caller.msg("You can't put something into itself.")
            return
        if not hasattr(obj, "move_to"):
            self.caller.msg("You can't put that anywhere.")
            return
        if obj.location != caller:
            self.caller.msg("You're not holding that.")
            return
        # Immovable fixtures use get:false() so they can't be picked up; they may still accept items.
        if not container.access(caller, "get"):
            allow_put = getattr(container.db, "allow_put_while_get_false", False) or getattr(
                type(container), "fixture_allows_put_without_get", False
            )
            if not allow_put:
                self.caller.msg("You can't put anything in that.")
                return
        if hasattr(container, "at_pre_object_receive") and not container.at_pre_object_receive(obj, caller):
            return
        if obj.move_to(container, quiet=True):
            if hasattr(container, "at_object_receive"):
                container.at_object_receive(obj, caller)
            obj_name = obj.get_numbered_name(1, caller, return_string=True)
            cont_name = container.get_display_name(caller)
            self.caller.msg("You put %s in %s." % (obj_name, cont_name))
            caller.location.msg_contents(
                "%s puts %s in %s." % (caller.get_display_name(caller), obj_name, cont_name),
                exclude=caller,
            )
        else:
            self.caller.msg("You can't put that in there.")


class CmdEnter(Command):
    """
    Enter a vehicle, arena, or any other enterable object.

    Usage:
      enter <object>
    """

    key = "enter"
    aliases = ["ride", "board"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Enter what? Usage: enter <object>")
            return
        target = caller.search(self.args.strip(), location=caller.location)
        if not target:
            return
        from typeclasses.mixins.enterable import EnterableMixin
        if not isinstance(target, EnterableMixin):
            caller.msg("You can't enter that.")
            return
        target.at_enter(caller)
