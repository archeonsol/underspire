# D:\moo\mootest\typeclasses\broadcast.py
"""
Recording and broadcast system: Camera, Television, Cassette.

- Camera: set to 'live' (broadcast to a linked TV in real time) or 'record'
  (buffer room messages). Stop recording produces a Cassette.
- Television: displays live feed from a linked camera, or plays a Cassette
  when one is inside it (use 'tune television' to play).
- Cassette: holds a recording (list of timestamped lines). Persists with the object.
"""
import time
from evennia.utils.ansi import strip_ansi
from evennia.utils.create import create_object

from .objects import Object

# Prefix added by Television.display_broadcast; if we see it (after stripping ANSI),
# do not re-feed to cameras or we get infinite "On the television you see: ..." nesting.
_TV_PREFIX = "On the television you see:"


def _is_television_output(text):
    """True if text is already TV output (possibly with leading ANSI)."""
    if not text or not isinstance(text, str):
        return False
    return strip_ansi(text).strip().startswith(_TV_PREFIX)


def _get_object_by_id(dbref):
    """Resolve dbref to object. Returns None if invalid."""
    if dbref is None:
        return None
    from evennia.utils.search import search_object
    try:
        ref = "#%s" % int(dbref)
        result = search_object(ref)
        return result[0] if result else None
    except (TypeError, ValueError):
        return None


def feed_cameras_in_location(location, text):
    """
    Send a room message to all cameras in this location: objects in the room
    and objects held by characters in the room (so a camera in someone's hands
    still captures). Call this whenever room traffic should be recorded/broadcast.
    """
    if not text or not isinstance(text, str) or not text.strip():
        return
    if not location:
        return
    if _is_television_output(text):
        return
    from evennia.utils.utils import make_iter
    # Cameras (and any object with capture_room_message) in the room
    for obj in make_iter(getattr(location, "contents", []) or []):
        capture = getattr(obj, "capture_room_message", None)
        if callable(capture):
            try:
                capture(text)
            except Exception:
                pass
    # Objects held by characters in the room (e.g. camera in hands)
    chars = getattr(location, "contents_get", None)
    if chars:
        for char in make_iter(chars(content_type="character") or []):
            for obj in make_iter(getattr(char, "contents", []) or []):
                capture = getattr(obj, "capture_room_message", None)
                if callable(capture):
                    try:
                        capture(text)
                    except Exception:
                        pass


# --- Camera ---


class Camera(Object):
    """
    Captures what happens in the room. Modes:
    - off: does nothing
    - live: sends each room message to a linked Television in real time
    - record: buffers messages; 'stop recording' creates a Cassette
    """
    def at_object_creation(self):
        self.db.mode = "off"  # off | live | record
        self.db.linked_tv = None   # dbref of Television for live feed
        self.db.recording_buffer = []  # list of {"t": offset_secs, "text": "..."}
        self.db.record_start_time = None  # time.time() when recording started

    def msg(self, text=None, from_obj=None, **kwargs):
        """
        Evennia hook: this object 'hears' room traffic when msg_contents runs.
        Pass what we hear to capture_room_message so live/record works.
        """
        super().msg(text=text, from_obj=from_obj, **kwargs)
        if isinstance(text, tuple):
            text = text[0]
        if not text or not isinstance(text, str):
            return
        if _is_television_output(text):
            return
        if from_obj == self:
            return
        self.capture_room_message(text)

    def capture_room_message(self, text):
        """Called by the room when msg_contents is used. text is the message string."""
        if not text or not isinstance(text, str):
            return
        if _is_television_output(text):
            return
        mode = getattr(self.db, "mode", "off")
        if mode == "off":
            return
        if mode == "live":
            tv_id = getattr(self.db, "linked_tv", None)
            tv = _get_object_by_id(tv_id) if tv_id else None
            if tv and hasattr(tv, "display_broadcast"):
                tv.display_broadcast(text)
            return
        if mode == "record":
            buf = getattr(self.db, "recording_buffer", None)
            if buf is None:
                self.db.recording_buffer = []
                buf = self.db.recording_buffer
            start = getattr(self.db, "record_start_time", None)
            if start is None:
                start = time.time()
                self.db.record_start_time = start
            offset = time.time() - start
            buf.append({"t": round(offset, 2), "text": text})

    def stop_recording_and_make_cassette(self, holder=None):
        """
        Stop recording and create a Cassette with the current buffer.

        Cassette is created in `holder` if given (for example, the character
        operating the camera, so it appears in their inventory). If no holder
        is given, it is created in the camera's own location.

        Returns the new Cassette or None.
        """
        self.db.mode = "off"
        buf = getattr(self.db, "recording_buffer", [])
        self.db.recording_buffer = []
        self.db.record_start_time = None
        if not buf:
            return None
        # holder is preferred (so e.g. camera stop puts cassette into their inventory);
        # otherwise fall back to the camera's room/location.
        loc = holder or self.location
        if not loc:
            return None
        try:
            cassette = create_object(
                "typeclasses.broadcast.Cassette",
                key="recording cassette",
                location=loc,
            )
            cassette.db.recording = list(buf)  # persistent copy
            cassette.db.desc = "A cassette containing a recording."
            return cassette
        except Exception:
            return None

    def take_photograph(self, caller):
        """
        Capture a still of the caller's current room and hand them a Photograph object.
        The snapshot preserves the room's full colored look output.
        """
        if not caller or not getattr(caller, "location", None):
            return None
        room = caller.location
        # Use the room's appearance as seen by the caller so colors and formatting match 'look'.
        try:
            text = room.return_appearance(caller)
        except Exception:
            text = str(room)
        room_name = getattr(room, "key", "somewhere")
        try:
            photo = create_object(
                "typeclasses.broadcast.Photograph",
                key=f"photograph of {room_name}",
                location=caller,
            )
        except Exception:
            return None
        photo.db.snapshot_text = text
        photo.db.room_name = room_name
        if not getattr(photo.db, "desc", None):
            photo.db.desc = (
                f"A glossy photograph of {room_name}. "
                "You can |wlook|n at it to see a frozen moment from that place."
            )
        return photo


# --- Television ---


class Television(Object):
    """
    Displays broadcast content. Either:
    - Live: linked to a Camera (db.linked_camera); shows what the camera sees.
    - Playback: a Cassette in contents; use 'tune television' to play the recording.
    """
    def at_object_creation(self):
        self.db.linked_camera = None  # dbref of Camera for live feed

    def display_broadcast(self, text):
        """Show a line of broadcast to everyone in the same room as the TV."""
        loc = self.location
        if not loc or not hasattr(loc, "msg_contents"):
            return
        # Bold white header, lighter gray for the content so it stands out from regular text
        loc.msg_contents("|wOn the television you see:|n |250%s|n" % text, exclude=(self,))

    def get_cassettes(self):
        """Return all Cassettes in this TV's contents."""
        objs = []
        try:
            from typeclasses.broadcast import Cassette
            for obj in self.contents:
                if isinstance(obj, Cassette):
                    objs.append(obj)
        except ImportError:
            return []
        return objs

    def get_cassette(self):
        """Return the first Cassette in this TV's contents, if any."""
        cassettes = self.get_cassettes()
        return cassettes[0] if cassettes else None

    def play_recording(self, cassette=None, callback=None):
        """
        Play the cassette's recording in this room, with delays between lines.
        callback() is called when playback finishes (optional).
        """
        cassette = cassette or self.get_cassette()
        if not cassette:
            if callback:
                callback()
            return False
        recording = list(getattr(cassette.db, "recording", []) or [])
        if not recording:
            if callback:
                callback()
            return True
        from evennia.utils import delay
        loc = self.location
        if not loc:
            if callback:
                callback()
            return True
        tv_id = self.id

        def _tv_msg(loc_now, text, tv_obj):
            if loc_now and hasattr(loc_now, "msg_contents"):
                loc_now.msg_contents("|wOn the television you see:|n |250%s|n" % text, exclude=(tv_obj,) if tv_obj else ())

        def _send_line(idx):
            tv = _get_object_by_id(tv_id)
            loc_now = tv.location if tv else None
            if idx >= len(recording):
                if callback:
                    callback()
                return
            if idx == 0:
                _tv_msg(loc_now, "--RECORDING START--", tv)
            entry = recording[idx]
            line = entry.get("text", "")
            if line:
                _tv_msg(loc_now, line, tv)
            next_idx = idx + 1
            if next_idx < len(recording):
                t_cur = entry.get("t", 0)
                t_next = recording[next_idx].get("t", t_cur + 2)
                secs = max(0.5, min(10.0, t_next - t_cur))
                delay(secs, _send_line, next_idx)
            else:
                _tv_msg(loc_now, "--RECORDING END--", tv)
                if callback:
                    callback()

        delay(0.5, _send_line, 0)
        return True


# --- Cassette ---


class Cassette(Object):
    """
    Holds a single recording. The recording persists in db.recording
    for as long as the cassette exists. Put the cassette in a Television
    and use 'tune television' to play it.
    """
    def at_object_creation(self):
        self.db.recording = []  # list of {"t": offset_secs, "text": "..."}
        self.db.label = None
        self.db.desc = "A cassette. Put it in a television and tune in to play."

    def set_label(self, label):
        """Assign a label to this cassette and update its name."""
        label = (label or "").strip()
        self.db.label = label or None
        base = "recording cassette"
        if self.db.label:
            self.key = f"{base} labelled as {self.db.label}"
        else:
            self.key = base


class Photograph(Object):
    """
    A still image captured by a Camera. Stores a snapshot of a room's appearance
    (full colored look output) at the time of capture.
    """

    def at_object_creation(self):
        self.db.snapshot_text = ""
        self.db.room_name = ""
        self.db.label = None
        if not getattr(self.db, "desc", None):
            self.db.desc = "A glossy photograph. You can look at it to see what it captured."

    def set_label(self, label):
        """Assign a label to this photograph and update its name."""
        label = (label or "").strip()
        self.db.label = label or None
        room_name = getattr(self.db, "room_name", "somewhere")
        base = f"photograph of {room_name}"
        if self.db.label:
            self.key = f"{base} labelled as {self.db.label}"
        else:
            self.key = base

    def return_appearance(self, looker, **kwargs):
        """
        When looked at, show the stored snapshot as though the viewer were
        standing in that room, preserving colors and formatting.
        """
        snap = getattr(self.db, "snapshot_text", None)
        room_name = getattr(self.db, "room_name", "somewhere")
        label = getattr(self.db, "label", None)
        if not snap:
            return super().return_appearance(looker, **kwargs)
        header = f"|wPhotograph of {room_name}|n"
        if label:
            header += f" (labelled as {label})"
        return f"{header}\n{snap}"
