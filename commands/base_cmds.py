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


class Command(BaseCommand):
    """
    Base command. Blocks all commands when character is flatlined (dying) or dead except for Admins/Builders.
    """
    def at_pre_cmd(self):
        """Block commands if character is flatlined (dying) or permanently dead."""
        caller = self.caller
        if not caller:
            return super().at_pre_cmd()
        char = _command_character(self)
        from world.death import character_can_act
        can_act, msg = character_can_act(char, allow_builders=True)
        if not can_act and msg:
            caller.msg(msg)
            return True
        return super().at_pre_cmd()


class CmdLook(DefaultCmdLook):
    """
    Look at location, object, or a directional exit.

    Usage:
      look
      look <obj>
      look <direction>   (e.g. look north, look n)
    """

    def at_pre_cmd(self):
        """Block look when flatlined/dead so state-specific cmdset message can show."""
        caller = self.caller
        if not caller:
            return super().at_pre_cmd() if hasattr(super(), "at_pre_cmd") else None
        char = _command_character(self)
        from world.death import character_can_act
        can_act, msg = character_can_act(char, allow_builders=True)
        if not can_act and msg:
            caller.msg(msg)
            return True
        return super().at_pre_cmd() if hasattr(super(), "at_pre_cmd") else None

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
                                    caller.msg("Multiple people in the photo match that. Be more specific (use 1-<sdesc>, 2-<sdesc>, etc).")
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
    Stop a pending staggered walk before it completes.

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
        # Mark the next delayed walk to be cancelled; the delayed callback
        # in `world.staggered_movement` will honour this flag.
        already_set = bool(getattr(caller.db, "cancel_walking", False))
        caller.db.cancel_walking = True
        if already_set:
            self.caller.msg("You steady yourself, keeping from walking off anywhere.")
        else:
            self.caller.msg("You stop walking.")


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
    """Get: supports 'get <item> from <container>'; from logged-off/corpse only when allowed."""
    key = "get"
    aliases = ["take", "pick up"]

    def at_pre_cmd(self):
        """Block when flatlined/dead (CmdGet does not inherit from Command)."""
        char = _command_character(self)
        from world.death import character_can_act
        can_act, msg = character_can_act(char, allow_builders=True)
        if not can_act and msg:
            self.caller.msg(msg)
            return True
        return super().at_pre_cmd() if hasattr(super(), "at_pre_cmd") else None

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            if DefaultCmdGet:
                super().func()
            else:
                caller.msg("Get what?")
            return
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
                if not is_character_logged_off(container):
                    caller.msg("You can't take from someone who's wide awake!")
                    return
                if not character_logged_off_long_enough(container):
                    caller.msg("They haven't been gone long enough. You can only take from someone who's been logged off at least half an hour.")
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
