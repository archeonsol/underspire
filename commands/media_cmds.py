"""
Media commands: camera, tune television, tvapp, label (cassette/photograph).
"""

from commands.base_cmds import Command, _command_character


def _find_camera(caller):
    """Return a Camera in caller's location or in caller's inventory, or None."""
    try:
        from typeclasses.broadcast import Camera
    except ImportError:
        return None
    loc = caller.location
    if loc:
        for obj in loc.contents:
            if isinstance(obj, Camera):
                return obj
    for obj in (caller.contents if hasattr(caller, "contents") else []):
        if isinstance(obj, Camera):
            return obj
    return None


def _find_television(caller):
    """Return a Television in caller's location, or None."""
    try:
        from typeclasses.broadcast import Television
    except ImportError:
        return None
    loc = caller.location
    if not loc:
        return None
    for obj in loc.contents:
        if isinstance(obj, Television):
            return obj
    return None


def _get_object_by_id(dbref):
    if dbref is None:
        return None
    from evennia.utils.search import search_object
    try:
        ref = "#%s" % int(dbref)
        result = search_object(ref)
        return result[0] if result else None
    except (TypeError, ValueError):
        return None


class CmdLabel(Command):
    """
    Label a recording cassette or photograph, updating its name accordingly.

    Usage:
      label <item> = <text>

    Examples:
      label cassette = First Expedition Log
      label photograph = Limbo, pre-collapse
    """

    key = "label"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller:
            return
        args = (self.args or "").strip()
        if "=" not in args:
            self.caller.msg("Usage: label <item> = <text>")
            return
        item_spec, _, label_text = args.partition("=")
        item_spec = item_spec.strip()
        label_text = label_text.strip()
        if not item_spec or not label_text:
            self.caller.msg("Usage: label <item> = <text>")
            return
        # Search in inventory first, then room.
        candidates = list(getattr(caller, "contents", []) or [])
        if getattr(caller, "location", None):
            candidates += list(caller.location.contents or [])
        obj = caller.search(item_spec, candidates=candidates)
        if not obj:
            return
        from typeclasses.broadcast import Cassette, Photograph
        if isinstance(obj, Cassette):
            obj.set_label(label_text)
            self.caller.msg(f"You carefully label the cassette as |w{label_text}|n.")
            if caller.location:
                caller.location.msg_contents(
                    f"{caller.get_display_name(caller)} labels a cassette as |w{label_text}|n.",
                    exclude=caller,
                )
        elif isinstance(obj, Photograph):
            obj.set_label(label_text)
            room_name = getattr(obj.db, "room_name", "somewhere")
            self.caller.msg(f"You write a neat label on the back of the photograph of {room_name}: |w{label_text}|n.")
            if caller.location:
                caller.location.msg_contents(
                    f"{caller.get_display_name(caller)} labels a photograph with the words |w{label_text}|n.",
                    exclude=caller,
                )
        else:
            self.caller.msg("You can only label recording cassettes and photographs.")


class CmdCamera(Command):
    """
    Operate a camera: set live (link to a TV), record, stop, or unlink from TV.
    Usage:
      camera live <television>   - broadcast this room to that TV in real time
      camera unlink             - unlink camera from TV and turn off live
      camera record             - start recording (stop with 'camera stop')
      camera stop               - stop recording and create a cassette here
      camera                    - show camera status
    """
    key = "camera"
    aliases = ["operate camera"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller or not caller.location:
            return
        args = (self.args or "").strip().lower()
        camera = _find_camera(caller)
        if not camera:
            self.caller.msg("There's no camera here or in your inventory.")
            return
        if not args:
            mode = getattr(camera.db, "mode", "off")
            tv_id = getattr(camera.db, "linked_tv", None)
            tv = _get_object_by_id(tv_id) if tv_id else None
            tv_name = tv.get_display_name(caller) if tv else "none"
            self.caller.msg("Camera is |w%s|n. Linked TV: %s." % (mode, tv_name))
            if mode == "record":
                buf = getattr(camera.db, "recording_buffer", []) or []
                self.caller.msg("Recording: %s lines so far." % len(buf))
            return
        parts = args.split(None, 1)
        sub = parts[0]
        rest = (parts[1] if len(parts) > 1 else "").strip()
        if sub == "live":
            if not rest:
                self.caller.msg("Usage: camera live <television>")
                return
            tv = caller.search(rest, location=caller.location)
            if not tv:
                return
            try:
                from typeclasses.broadcast import Television
                if not isinstance(tv, Television):
                    self.caller.msg("That's not a television.")
                    return
            except ImportError:
                self.caller.msg("That's not a television.")
                return
            camera.db.mode = "live"
            camera.db.linked_tv = tv.id
            self.caller.msg("Camera is now |wlive|n, broadcasting to %s." % tv.get_display_name(caller))
            return
        if sub in ("unlink", "off"):
            was_live = getattr(camera.db, "mode", "off") == "live"
            camera.db.mode = "off"
            camera.db.linked_tv = None
            if was_live:
                self.caller.msg("Camera unlinked from the television and turned off.")
            else:
                self.caller.msg("Camera is off. (It wasn't linked to a TV.)")
            return
        if sub in ("photo", "photograph"):
            photo = camera.take_photograph(caller)
            if not photo:
                self.caller.msg("The camera fails to capture anything. Maybe it's not pointed at a room you can see.")
                return
            pname = photo.get_display_name(caller) if hasattr(photo, "get_display_name") else photo.key
            room_name = getattr(photo.db, "room_name", "somewhere")
            self.caller.msg(f"You depress the shutter. {pname} develops in your hands — a frozen moment of {room_name}.")
            caller.location.msg_contents(
                f"{caller.get_display_name(caller)} takes a photograph with the camera; a glossy print develops in their hands.",
                exclude=caller,
            )
            return
        if sub == "record":
            camera.db.mode = "record"
            camera.db.recording_buffer = []
            camera.db.record_start_time = None
            self.caller.msg("Camera is now |wrecording|n. Use |wcamera stop|n to finish and create a cassette.")
            return
        if sub == "stop":
            if getattr(camera.db, "mode", "off") != "record":
                self.caller.msg("The camera isn't recording.")
                return
            cassette = camera.stop_recording_and_make_cassette(holder=caller)
            if cassette:
                self.caller.msg("Recording stopped. A |wrecording cassette|n rests in your hands.")
                caller.location.msg_contents(
                    "%s stops the camera and tucks a recording cassette away." % caller.get_display_name(caller),
                    exclude=caller,
                )
            else:
                self.caller.msg("Recording stopped. (Nothing was recorded.)")
            return
        self.caller.msg("Usage: camera live <tv> | camera unlink | camera record | camera stop")


class CmdPhotoRecog(Command):
    """
    Tag someone in a photograph with a name, for you only.

    This does NOT affect global recog. It only changes how *you* see names in that photo.

    Usage:
      photo recog <sdesc> as <name>
      photo recog <sdesc> as <name> in <photo>

    Example:
      photo recog short man as John
      photo recog short as John in photograph of Lobby
    """

    key = "photo recog"
    aliases = ["photorecog", "photo tag", "photo label person"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller:
            return
        raw = (self.args or "").strip()
        if not raw or " as " not in raw:
            self.caller.msg("Usage: photo recog <sdesc> as <name> [in <photo>]")
            return

        # Parse optional "in <photo>" suffix.
        left = raw
        photo_spec = ""
        if " in " in raw:
            before_in, _, after_in = raw.rpartition(" in ")
            if before_in and after_in:
                left = before_in.strip()
                photo_spec = after_in.strip()

        sdesc_part, _, name_part = left.partition(" as ")
        sdesc_part = (sdesc_part or "").strip()
        name_part = (name_part or "").strip().rstrip(".,?!")
        if not sdesc_part or not name_part:
            self.caller.msg("Usage: photo recog <sdesc> as <name> [in <photo>]")
            return

        # Find the Photograph: explicit "in <photo>" wins; otherwise use last viewed photo.
        photo = None
        if photo_spec:
            candidates = list(getattr(caller, "contents", []) or [])
            if getattr(caller, "location", None):
                candidates += list(getattr(caller.location, "contents", []) or [])
            photo = caller.search(photo_spec, candidates=candidates)
        else:
            try:
                photo = getattr(getattr(caller, "ndb", None), "last_photograph", None)
            except Exception:
                photo = None

        try:
            from typeclasses.broadcast import Photograph
        except Exception:
            Photograph = None
        if not photo or not Photograph or not isinstance(photo, Photograph):
            self.caller.msg("You need to specify a photograph (or look at one first).")
            return

        snap_chars = getattr(getattr(photo, "db", None), "snapshot_chars", None) or {}
        if not snap_chars:
            self.caller.msg("That photograph doesn't seem to have anyone in it.")
            return

        # Resolve captured characters as objects.
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
            self.caller.msg("That photograph doesn't seem to have anyone in it.")
            return

        # Match the target within the photo by sdesc/recog matching.
        target = None
        try:
            from world.rpg.emote import resolve_sdesc_to_characters
            matches = resolve_sdesc_to_characters(caller, char_objs, sdesc_part)
            if not matches:
                self.caller.msg(f"No one in the photo matches |w{sdesc_part}|n.")
                return
            if len(matches) > 1:
                self.caller.msg("Multiple people match that in the photo. Be more specific (use 1-<sdesc>, 2-<sdesc>, etc).")
                return
            target = matches[0]
        except Exception:
            self.caller.msg("Couldn't match that person in the photo.")
            return

        try:
            tid = str(getattr(target, "id", None))
        except Exception:
            tid = None
        if not tid:
            self.caller.msg("Couldn't tag that.")
            return

        # Store per-viewer per-photo tag.
        viewer_id = str(getattr(caller, "id", ""))
        if not viewer_id:
            self.caller.msg("Couldn't tag that.")
            return
        all_tags = dict(getattr(photo.db, "photo_recogs", None) or {})
        viewer_tags = dict(all_tags.get(viewer_id, {}) or {})
        viewer_tags[tid] = name_part
        all_tags[viewer_id] = viewer_tags
        photo.db.photo_recogs = all_tags

        # Feedback: show what you previously saw them as in this photo.
        try:
            before = target.get_display_name(caller)
        except Exception:
            before = "them"
        self.caller.msg(f"You tag {before} in the photo as |w{name_part}|n.")


class CmdTuneTelevision(Command):
    """
    Play the cassette that's inside a television in the room.
    Usage: tune television   or   tune tv
    Put a cassette in the TV first with: put <cassette> in <television>
    """
    key = "tune"
    aliases = ["tune television", "tune tv", "play television", "play tv"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller or not caller.location:
            return
        tv = _find_television(caller)
        if not tv:
            self.caller.msg("There's no television here.")
            return
        cassette = tv.get_cassette()
        if not cassette:
            self.caller.msg("There's no cassette in the television. Put one in first.")
            return
        self.caller.msg("You tune the television; the recording begins to play.")
        caller.location.msg_contents(
            "%s tunes the television; the recording begins to play." % caller.get_display_name(caller),
            exclude=caller,
        )
        tv.play_recording(cassette=cassette)


class CmdTelevisionApp(Command):
    """
    Browse and play recordings from all cassettes inside a television.

    Usage:
      tvapp            - list all cassettes currently in the television
      tvapp <number>   - play the numbered cassette from the list
    """

    key = "tvapp"
    aliases = ["tv app", "tvmenu", "tv menu"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller or not caller.location:
            return
        tv = _find_television(caller)
        if not tv:
            self.caller.msg("There's no television here.")
            return
        cassettes = getattr(tv, "get_cassettes", lambda: [])()
        if not cassettes:
            self.caller.msg("The television's queue is empty. Put some cassettes inside first.")
            return
        args = (self.args or "").strip()
        if not args:
            lines = ["|wTelevision queue:|n"]
            for idx, cas in enumerate(cassettes, start=1):
                label = getattr(cas.db, "label", None)
                name = cas.get_display_name(caller) if hasattr(cas, "get_display_name") else cas.key
                extra = f" (labelled as {label})" if label else ""
                lines.append(f"  |w{idx}.|n {name}{extra}")
            lines.append("Use |wtvapp <number>|n to select which cassette to play.")
            self.caller.msg("\n".join(lines))
            return
        if not args.isdigit():
            self.caller.msg("Usage: tvapp <number>   (see 'tvapp' for the list).")
            return
        choice = int(args)
        if choice < 1 or choice > len(cassettes):
            self.caller.msg("There's no cassette with that number. Use 'tvapp' to see valid choices.")
            return
        cassette = cassettes[choice - 1]
        cname = cassette.get_display_name(caller) if hasattr(cassette, "get_display_name") else cassette.key
        self.caller.msg(f"You browse the television's queue and select |w{cname}|n to play.")
        caller.location.msg_contents(
            f"{caller.get_display_name(caller)} scrolls through the television's menu and selects |w{cname}|n to play.",
            exclude=caller,
        )
        tv.play_recording(cassette=cassette)
