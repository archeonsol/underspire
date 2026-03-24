from __future__ import annotations

from datetime import datetime

import re

try:
    import arrow as _arrow
    _ARROW_AVAILABLE = True
except ImportError:
    _ARROW_AVAILABLE = False
import shlex

from commands.base_cmds import Command
import world.matrix_groups as mg
from world.handset_call_utils import (
    RINGTONE_MAX_LEN,
    clear_call as _clear_call,
    get_call_peer as _get_peer,
    ringtone_suffix,
    schedule_call_ring_timers,
)


def _ts():
    if _ARROW_AVAILABLE:
        return _arrow.now().format("MMM DD HH:mm")
    return datetime.now().strftime("%b %d %H:%M")


def _clock():
    if _ARROW_AVAILABLE:
        return _arrow.now().format("HH:mm")
    return datetime.now().strftime("%H:%M")


def _as_matrix_id(raw: str) -> str | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    return raw if raw.startswith("^") else "^" + raw


def _lookup_handset_by_matrix_id(matrix_id: str):
    try:
        from world.matrix_ids import lookup_matrix_id
    except Exception:
        from evennia.utils import logger
        logger.log_trace("handset_cmds: could not import lookup_matrix_id")
        return None
    obj = lookup_matrix_id(matrix_id)
    if not obj:
        return None
    if getattr(getattr(obj, "db", None), "device_type", None) != "handset":
        return None
    return obj


def _holder_and_room(handset):
    holder = None
    room = None
    try:
        holder = handset.get_authenticated_user()
        room = holder.location if holder else None
    except Exception:
        holder = None
        room = None
    return holder, room


def _ring_room_messages(handset):
    holder, room = _holder_and_room(handset)
    if not holder:
        return
    holder.msg("Your handset rings.")
    if room:
        hname = holder.get_display_name(room) if hasattr(holder, "get_display_name") else holder.key
        try:
            room.msg_contents(f"{hname}'s handset rings.", exclude=holder)
        except Exception:
            pass


def _beep_text_message(receiver_handset, sender_id: str, msg: str, msg_kind: str | None = None):
    display = receiver_handset.display_alias_or_id(sender_id)
    ts = _ts()
    if hasattr(receiver_handset, "add_text_message"):
        receiver_handset.add_text_message(
            _as_matrix_id(sender_id) or sender_id, msg, ts_display=ts, msg_kind=msg_kind
        )
    else:
        entry = {"ts": ts, "from": _as_matrix_id(sender_id), "msg": msg}
        if msg_kind:
            entry["kind"] = msg_kind
        receiver_handset.db.texts = list(getattr(receiver_handset.db, "texts", []) or []) + [entry]
    holder, room = _holder_and_room(receiver_handset)
    if holder:
        holder.msg("Your handset beeps.")
        if room:
            hname = holder.get_display_name(room) if hasattr(holder, "get_display_name") else holder.key
            try:
                room.msg_contents(f"{hname}'s handset beeps.", exclude=holder)
            except Exception:
                pass
        tag = " [voicemail]" if (msg_kind or "").lower() == "voicemail" else ""
        holder.msg(f"[{ts}]{tag}{display}: {msg}")


def _unread_notifications(handset) -> int:
    last_view = getattr(getattr(handset, "db", None), "last_texts_viewed_t", None)
    try:
        last_view = float(last_view) if last_view is not None else 0.0
    except Exception:
        last_view = 0.0

    try:
        msgs = (
            handset.get_text_messages()
            if hasattr(handset, "get_text_messages")
            else list(getattr(handset.db, "texts", []) or [])
        )
    except Exception:
        from evennia.utils import logger
        logger.log_trace("handset_cmds: failed to read text messages from handset")
        msgs = []

    count = 0
    for entry in msgs or []:
        if not isinstance(entry, dict):
            continue
        t = entry.get("t", None)
        if t is None:
            if last_view <= 0:
                count += 1
            continue
        try:
            if float(t) > last_view:
                count += 1
        except Exception:
            continue
    return count


class CmdHandset(Command):
    """
    Use your handset to call, speak, hang up, save contacts, and text.

    Usage:
      hs call <ID|alias>
      hs redial
      hs contacts
      hs photo <ID|alias>
      hs selfie <ID|alias> "<title>" "<text>"
      hs selfie <ID|alias> <text>                (no title; title defaults to 'selfie')
      hs speak <message>
      hs hangup / hs decline
      hs save <ID> as <alias>
      hs remove <alias>
      hs text <ID|alias> <message>
      hs voicemail <message>
      hs group <name>  (set primary) | create | invite | msg | list | view | leave | ...
      hs ringtone <text>   — custom ring line (|whs ringtone|n alone clears)
    """

    key = "hs"
    aliases = ["handset", "phone"]
    locks = "cmd:all()"
    help_category = "Matrix"

    def _get_handset(self):
        handset = getattr(self, "obj", None)
        caller = self.caller
        if handset and getattr(handset, "location", None) == caller:
            return handset
        for obj in list(getattr(caller, "contents", []) or []):
            if getattr(getattr(obj, "db", None), "device_type", None) == "handset":
                return obj
        return None

    def _resolve_target_handset(self, handset, target_token: str):
        """
        Resolve a target token to a handset object.
        Returns (target_handset, target_id, error_msg). error_msg is None on success.
        """
        target_id = handset.resolve_contact_or_id((target_token or "").strip())
        if not target_id:
            return None, None, "|rInvalid number/contact.|n"
        try:
            own_id = handset.get_matrix_id() if hasattr(handset, "get_matrix_id") else None
            if own_id and own_id.upper() == str(target_id).upper():
                return handset, target_id, None
        except Exception:
            pass
        target_handset = _lookup_handset_by_matrix_id(target_id)
        if not target_handset:
            return None, target_id, "|rThat number can't be reached.|n"
        if not target_handset.has_network_coverage():
            return None, target_id, "|rNot delivered. That handset has no signal.|n"
        return target_handset, target_id, None

    def _capture_room_snapshot(self, handset, caller, room):
        """Capture room snapshot with character placeholders. Returns (snap_text, snapshot_chars)."""
        try:
            snap = room.return_appearance(caller)
        except Exception:
            snap = str(room)

        snapshot_chars = {}
        try:
            from evennia.utils.utils import inherits_from
            from world.rpg.sdesc import get_short_desc
            from typeclasses.rooms import ROOM_DESC_CHARACTER_NAME_COLOR

            visible = room.filter_visible(room.contents_get(content_type="character"), caller)
            visible = [
                c
                for c in visible
                if inherits_from(c, "evennia.objects.objects.DefaultCharacter") and c is not caller
            ]
            for char in visible:
                try:
                    cid = int(char.id)
                except Exception:
                    continue
                name_for_photographer = (char.get_display_name(caller) or "").strip()
                if not name_for_photographer:
                    continue
                placeholder = f"<<CHAR:{cid}>>"
                colored = f"{ROOM_DESC_CHARACTER_NAME_COLOR}{name_for_photographer}|n"
                replacement = f"{ROOM_DESC_CHARACTER_NAME_COLOR}{placeholder}|n"
                if colored in snap:
                    snap = snap.replace(colored, replacement)
                else:
                    snap = snap.replace(name_for_photographer, placeholder)
                snapshot_chars[str(cid)] = {"sdesc": get_short_desc(char, looker=caller)}
        except Exception:
            from evennia.utils import logger
            logger.log_trace("handset_cmds: failed to build character snapshot")
            snapshot_chars = {}

        try:
            from typeclasses.rooms import ROOM_DESC_CHARACTER_NAME_COLOR

            names = set()
            if hasattr(caller, "get_display_name"):
                n = (caller.get_display_name(caller) or "").strip()
                if n:
                    names.add(n)
            k = (getattr(caller, "key", None) or "").strip()
            if k:
                names.add(k)
            for n in names:
                if not n:
                    continue
                colored = f"{ROOM_DESC_CHARACTER_NAME_COLOR}{n}|n"
                snap = snap.replace(colored, "")
                snap = snap.replace(n, "")
            snap = re.sub(r"\n{3,}", "\n\n", snap).strip()
        except Exception:
            pass

        return snap, snapshot_chars

    def _deliver_photo(self, handset, caller, target_handset, target_id, kind: str, title: str, snap: str, snapshot_chars: dict):
        ts = _ts()
        photo_id = None
        if hasattr(target_handset, "add_photo"):
            photo_id = target_handset.add_photo(
                kind, title=title, snapshot_text=snap, ts_display=ts, snapshot_chars=snapshot_chars or {}
            )
        if kind == "photo":
            caller.msg(f"You depress the shutter and send a photo to {handset.display_alias_or_id(target_id)}.")
        else:
            caller.msg(f"You take a selfie and send it to {handset.display_alias_or_id(target_id)}.")
        caller.msg(f"|gDelivered to:|n {handset.display_alias_or_id(target_id)}")
        room = getattr(caller, "location", None)
        if room:
            try:
                verb = "takes a photo" if kind == "photo" else "takes a selfie"
                room.msg_contents(
                    f"{caller.get_display_name(room)} {verb} with their handset.",
                    exclude=caller,
                )
            except Exception:
                pass
        holder, room = _holder_and_room(target_handset)
        if holder:
            holder.msg("Your handset beeps.")
            if room:
                hname = holder.get_display_name(room) if hasattr(holder, "get_display_name") else holder.key
                try:
                    room.msg_contents(f"{hname}'s handset beeps.", exclude=holder)
                except Exception:
                    pass
            if kind == "photo":
                holder.msg(
                    f"|gYou receive a photo|n: {title}" + (f" |x(stored as photo #{photo_id})|n" if photo_id else "")
                )
            else:
                tdisp = f": {title}" if title else "."
                holder.msg(
                    f"|gYou receive a photo|n{tdisp}" + (f" |x(stored as photo #{photo_id})|n" if photo_id else "")
                )

    def func(self):
        caller = self.caller
        handset = self._get_handset()
        if not handset:
            caller.msg("|rYou don't have a handset to use.|n")
            return
        if not handset.has_network_coverage():
            caller.msg("|rNo signal. Your handset is offline.|n")
            return

        raw = (self.args or "").strip()
        if not raw:
            mid = None
            try:
                mid = handset.get_matrix_id() if hasattr(handset, "get_matrix_id") else None
            except Exception:
                mid = None
            mid = mid or "^??????"
            n = _unread_notifications(handset)
            notif = "notification" if n == 1 else "notifications"
            caller.msg(f"|cHandset {mid} :: {_clock()} :: {n} {notif}|n")
            return

        action, _, rest = raw.partition(" ")
        action = action.strip().lower()
        rest = rest.strip()

        if action == "save":
            self._do_save(handset, rest)
            return
        if action == "remove":
            self._do_remove(handset, rest)
            return
        if action == "contacts":
            self._do_contacts(handset)
            return
        if action == "photo":
            self._do_photo(handset, rest)
            return
        if action == "selfie":
            self._do_selfie(handset, rest)
            return
        if action == "call":
            self._do_call(handset, rest)
            return
        if action == "redial":
            self._do_call(handset, "")
            return
        if action == "speak":
            self._do_speak(handset, rest)
            return
        if action in ("hangup", "decline"):
            self._do_hangup(handset)
            return
        if action == "text":
            self._do_text(handset, rest)
            return
        if action == "voicemail":
            self._do_voicemail(handset, rest)
            return
        if action == "group":
            self._do_group(handset, rest)
            return
        if action == "ringtone":
            self._do_ringtone(handset, rest)
            return

        caller.msg(
            "|rUnknown handset command.|n Usage: hs call, redial, contacts, group, ringtone, photo, selfie, speak, hangup, decline, save, remove, text, voicemail ..."
        )

    def _do_ringtone(self, handset, rest: str):
        """Set or clear custom ring line after 'Your handset rings, …'."""
        caller = self.caller
        text = (rest or "").strip()
        if not text:
            handset.db.ringtone = None
            caller.msg("|wRingtone cleared.|n Default: |xYour handset rings.|n")
            return
        text = " ".join(text.replace("\r", " ").replace("\n", " ").split())
        if len(text) > RINGTONE_MAX_LEN:
            text = text[:RINGTONE_MAX_LEN].rstrip()
            caller.msg(f"|y(Truncated to {RINGTONE_MAX_LEN} characters.)|n")
        handset.db.ringtone = text
        suf = ringtone_suffix(handset)
        caller.msg(f"|wRingtone set.|n Incoming calls will show: |xYour handset rings, {suf}.|n")

    def _do_save(self, handset, rest: str):
        caller = self.caller
        if " as " not in rest:
            caller.msg("Usage: hs save <ID> as <alias>")
            return
        id_part, _, alias = rest.partition(" as ")
        matrix_id = handset.resolve_contact_or_id(id_part.strip())
        ok, msg = handset.save_contact(matrix_id, alias.strip())
        caller.msg(msg)

    def _do_remove(self, handset, rest: str):
        caller = self.caller
        alias = (rest or "").strip()
        if not alias:
            caller.msg("Usage: hs remove <alias>")
            return
        ok, msg = handset.remove_contact(alias)
        caller.msg(msg)

    def _do_contacts(self, handset):
        caller = self.caller
        contacts = handset.get_contacts()
        if not contacts:
            caller.msg("You have no handset contacts saved.")
            return
        lines = ["|c=== Handset Contacts (max 15) ===|n"]
        for alias in sorted(contacts.keys()):
            mid = contacts[alias]
            lines.append(f"|w{alias}|n: {mid}")
        caller.msg("\n".join(lines))

    def _do_photo(self, handset, target_token: str):
        caller = self.caller
        target_token = (target_token or "").strip()
        if not target_token:
            caller.msg("Usage: hs photo <ID|alias>")
            return
        if not getattr(caller, "location", None):
            caller.msg("|rYou can't take a photo here.|n")
            return
        target_handset, target_id, err = self._resolve_target_handset(handset, target_token)
        if err:
            caller.msg(err)
            return
        room = caller.location
        snap, snapshot_chars = self._capture_room_snapshot(handset, caller, room)
        room_name = getattr(room, "key", "somewhere")
        title = f"photograph of {room_name}"
        self._deliver_photo(handset, caller, target_handset, target_id, "photo", title, snap, snapshot_chars)

    def _do_selfie(self, handset, rest: str):
        caller = self.caller
        rest = (rest or "").strip()
        if not rest:
            caller.msg('Usage: hs selfie <ID|alias> "<title>" "<text>"')
            return
        target_token, _, remainder = rest.partition(" ")
        target_token = (target_token or "").strip()
        remainder = (remainder or "").strip()
        if not target_token or not remainder:
            caller.msg('Usage: hs selfie <ID|alias> "<title>" "<text>"')
            return

        try:
            parts = shlex.split(remainder)
        except ValueError:
            caller.msg('|rInvalid quoting.|n Usage: hs selfie <ID|alias> "<title>" "<text>"')
            return
        if not parts:
            caller.msg('Usage: hs selfie <ID|alias> "<title>" "<text>"')
            return
        if len(parts) == 1:
            title = "selfie"
            intro = parts[0]
        else:
            title = parts[0]
            intro = " ".join(parts[1:])

        target_handset, target_id, err = self._resolve_target_handset(handset, target_token)
        if err:
            caller.msg(err)
            return

        general = (getattr(getattr(caller, "db", None), "general_desc", None) or "This is a character.").strip()
        merged = ""
        if hasattr(caller, "format_body_appearance"):
            try:
                merged = caller.format_body_appearance().strip()
            except Exception:
                merged = ""

        try:
            cid = int(caller.id)
        except Exception:
            cid = None
        placeholder = f"<<CHAR:{cid}>>" if cid is not None else ""
        snapshot_chars = {}
        if cid is not None:
            try:
                from world.rpg.sdesc import get_short_desc

                snapshot_chars[str(cid)] = {"sdesc": get_short_desc(caller, looker=caller)}
            except Exception:
                snapshot_chars[str(cid)] = {"sdesc": "someone"}

        def _sub_self(s: str) -> str:
            if not s or not placeholder:
                return s
            out = s
            if hasattr(caller, "get_display_name"):
                n = (caller.get_display_name(caller) or "").strip()
                if n:
                    out = out.replace(n, placeholder)
            k = (getattr(caller, "key", None) or "").strip()
            if k:
                out = out.replace(k, placeholder)
            return out

        intro = _sub_self(intro)
        general = _sub_self(general)
        merged = _sub_self(merged)
        parts_body = [intro, ""]
        if general:
            parts_body.append(general)
        if merged:
            parts_body.append(merged)
        snap = "\n\n".join(p for p in parts_body if p is not None)
        self._deliver_photo(handset, caller, target_handset, target_id, "selfie", title, snap, snapshot_chars)

    def _do_call(self, handset, rest: str):
        caller = self.caller
        rest = (rest or "").strip()
        if not rest:
            rest = (getattr(handset.db, "last_dialed", None) or "").strip()
            if not rest:
                caller.msg("Usage: hs call <ID|alias>, or |whs redial|n after a call.")
                return
            caller.msg(f"|xRedialing {handset.display_alias_or_id(rest)}...|n")

        state = handset._call_state()
        if state in ("dialing", "ringing", "in_call"):
            caller.msg("|yYou're already on a line. Use|n |whs hangup|n |yto end it.|n")
            return

        target_id = handset.resolve_contact_or_id(rest)
        if not target_id:
            caller.msg("|rInvalid number/contact.|n")
            return

        own_id = handset.get_matrix_id() if hasattr(handset, "get_matrix_id") else None
        if own_id and own_id.upper() == str(target_id).upper():
            caller.msg("|rYou can't call yourself.|n")
            return

        target_handset = _lookup_handset_by_matrix_id(target_id)
        if not target_handset:
            caller.msg("|rThat number can't be reached.|n")
            return

        if not target_handset.has_network_coverage():
            caller.msg("|rNo answer. That handset has no signal.|n")
            return

        target_holder, _room = _holder_and_room(target_handset)
        if not target_holder:
            caller.msg("|rNo answer.|n")
            return

        handset._set_call_state("dialing", peer_dbref=target_handset.id)
        target_handset._set_call_state("ringing", peer_dbref=handset.id)
        try:
            handset.ndb.call_outbound = True
            target_handset.ndb.call_outbound = False
        except Exception:
            pass
        try:
            handset.db.last_dialed = str(target_id).strip()
        except Exception:
            pass

        schedule_call_ring_timers(handset, target_handset)
        caller.msg(f"You dial {handset.display_alias_or_id(target_id)}.")
        _ring_room_messages(target_handset)

    def _answer_if_ringing(self, handset):
        caller = self.caller
        state = handset._call_state()
        if state != "ringing":
            return False
        peer = _get_peer(handset)
        if not peer:
            _clear_call(handset)
            caller.msg("|rThe call drops.|n")
            return False

        def _mid(h):
            try:
                return h.get_matrix_id() if hasattr(h, "get_matrix_id") else ""
            except Exception:
                return ""

        p_mid = _mid(peer)
        h_mid = _mid(handset)
        if hasattr(handset, "log_call_event"):
            try:
                handset.log_call_event(p_mid, "in", "answered")
            except Exception:
                pass
        if hasattr(peer, "log_call_event"):
            try:
                peer.log_call_event(h_mid, "out", "answered")
            except Exception:
                pass

        handset._set_call_state("in_call", peer_dbref=peer.id)
        peer._set_call_state("in_call", peer_dbref=handset.id)

        caller.msg("You answer the call.")
        peer_holder, _ = _holder_and_room(peer)
        if peer_holder:
            peer_holder.msg("They pick up.")
        return True

    def _do_speak(self, handset, rest: str):
        caller = self.caller
        if not rest:
            caller.msg("Usage: hs speak <message>")
            return

        state = handset._call_state()
        if state == "ringing":
            self._answer_if_ringing(handset)
            state = handset._call_state()

        if state != "in_call":
            caller.msg("|rYou're not in a call.|n Use |whs call <ID|alias>|n first.")
            return

        peer = _get_peer(handset)
        if not peer:
            _clear_call(handset)
            caller.msg("|rThe line is dead.|n")
            return

        peer_holder, _ = _holder_and_room(peer)
        if not peer_holder:
            caller.msg("|rNo answer.|n")
            self._do_hangup(handset, quiet_peer=True)
            return

        me_id = handset.get_phone_number() or ""
        display = peer.display_alias_or_id(me_id) if hasattr(peer, "display_alias_or_id") else me_id
        caller.msg(f'You say into the handset: "{rest}"')
        peer_holder.msg(f'[{_ts()}]{display}: {rest}')
        if caller.location:
            try:
                caller.location.msg_contents(
                    f"{caller.get_display_name(caller.location)} speaks quietly into their handset.",
                    exclude=caller,
                )
            except Exception:
                pass

    def _do_hangup(self, handset, quiet_peer: bool = False):
        caller = self.caller
        state = handset._call_state()
        if state == "idle":
            caller.msg("You're not in a call.")
            return

        peer = _get_peer(handset)

        def _mid(h):
            if not h:
                return ""
            try:
                return h.get_matrix_id() if hasattr(h, "get_matrix_id") else ""
            except Exception:
                return ""

        p_mid = _mid(peer)
        h_mid = _mid(handset)

        if peer:
            if state == "ringing":
                if hasattr(handset, "log_call_event"):
                    try:
                        handset.log_call_event(p_mid, "in", "declined")
                    except Exception:
                        pass
                if hasattr(peer, "log_call_event"):
                    try:
                        peer.log_call_event(h_mid, "out", "declined")
                    except Exception:
                        pass
            elif state == "dialing":
                if hasattr(handset, "log_call_event"):
                    try:
                        handset.log_call_event(p_mid, "out", "declined")
                    except Exception:
                        pass
                if hasattr(peer, "log_call_event"):
                    try:
                        peer.log_call_event(h_mid, "in", "missed")
                    except Exception:
                        pass
            elif state == "in_call":
                outb = bool(getattr(handset.ndb, "call_outbound", False))
                if hasattr(handset, "log_call_event"):
                    try:
                        handset.log_call_event(p_mid, "out" if outb else "in", "ended")
                    except Exception:
                        pass
                if hasattr(peer, "log_call_event"):
                    try:
                        peer.log_call_event(h_mid, "in" if outb else "out", "ended")
                    except Exception:
                        pass

        _clear_call(handset)

        if state == "ringing":
            caller.msg("You decline the call.")
        else:
            caller.msg("You hang up.")

        if peer:
            _clear_call(peer)
            if not quiet_peer:
                peer_holder, _ = _holder_and_room(peer)
                if peer_holder:
                    if state == "ringing":
                        peer_holder.msg("|rNo answer. They declined.|n")
                    else:
                        peer_holder.msg("The line goes dead.")

    def _do_text(self, handset, rest: str):
        caller = self.caller
        if not rest:
            caller.msg("Usage: hs text <ID|alias> <message>")
            return
        target_token, _, msg = rest.partition(" ")
        if not msg.strip():
            caller.msg("Usage: hs text <ID|alias> <message>")
            return

        target_handset, target_id, err = self._resolve_target_handset(handset, target_token.strip())
        if err:
            caller.msg(err)
            return

        sender_id = handset.get_phone_number() or ""
        _beep_text_message(target_handset, sender_id, msg.strip())
        caller.msg(f"|gSent|n to {handset.display_alias_or_id(target_id)}.")

    def _do_voicemail(self, handset, rest: str):
        caller = self.caller
        rest = (rest or "").strip()
        if not rest:
            caller.msg("Usage: hs voicemail <message>")
            return
        target_id = (getattr(handset.db, "last_dialed", None) or "").strip()
        if not target_id:
            caller.msg("|rNo recent number to leave voicemail for.|n Use |whs call <ID|alias>|n first.")
            return
        target_handset, target_id, err = self._resolve_target_handset(handset, target_id)
        if err:
            caller.msg(err)
            return
        sender_id = handset.get_phone_number() or ""
        _beep_text_message(target_handset, sender_id, rest, msg_kind="voicemail")
        caller.msg(f"|gVoicemail sent|n to {handset.display_alias_or_id(target_id)}.")

    def _do_group(self, handset, rest: str):
        caller = self.caller
        rest = (rest or "").strip()
        if not rest:
            caller.msg(
                "|yUsage:|n hs group <name>  (set primary) | create <name> | invite <group> <contact|ID> | "
                "accept <id> | decline <id> | msg <message>  (to primary) | msg <group> <message> | "
                "list | view <group> | leave <group> | rename <group> = <new> | kick/promote/members/mute/unmute ..."
            )
            return
        sub, _, tail = rest.partition(" ")
        sub = sub.strip().lower()
        tail = tail.strip()

        # Known subcommands
        KNOWN_SUBS = frozenset(
            {"create", "invite", "accept", "decline", "msg", "message", "list", "view",
             "leave", "rename", "kick", "promote", "members", "mute", "unmute"}
        )
        if sub not in KNOWN_SUBS:
            # Not a subcommand: treat full rest as group name to set as primary
            self._do_group_set_primary(handset, rest.strip())
            return

        if sub == "message":
            sub = "msg"
        if sub == "create":
            self._do_group_create(handset, tail)
        elif sub == "invite":
            self._do_group_invite(handset, tail)
        elif sub == "accept":
            self._do_group_accept(handset, tail)
        elif sub == "decline":
            self._do_group_decline(handset, tail)
        elif sub == "msg":
            self._do_group_msg(handset, tail)
        elif sub == "list":
            self._do_group_list(handset)
        elif sub == "view":
            self._do_group_view(handset, tail)
        elif sub == "leave":
            self._do_group_leave(handset, tail)
        elif sub == "rename":
            self._do_group_rename(handset, tail)
        elif sub == "kick":
            self._do_group_kick(handset, tail)
        elif sub == "promote":
            self._do_group_promote(handset, tail)
        elif sub == "members":
            self._do_group_members(handset, tail)
        elif sub == "mute":
            self._do_group_mute(handset, tail, True)
        elif sub == "unmute":
            self._do_group_mute(handset, tail, False)
        else:
            caller.msg("|rUnknown hs group subcommand.|n")

    def _do_group_set_primary(self, handset, rest: str):
        """Set primary group by name or ID (accepts names with spaces)."""
        caller = self.caller
        name = (rest or "").strip()
        if not name:
            caller.msg("Usage: hs group <group name|ID>  (sets primary group for hs group msg)")
            return
        # Try by ID first if it looks like a 6-char group ID
        if len(name) == 6 and name.upper().isalnum():
            gid, data, err = mg.resolve_group_by_id(handset, name)
        else:
            gid, data, err = mg.resolve_group_by_name(handset, name)
        if err:
            caller.msg(f"|r{err}|n")
            return
        handset.db.primary_group_id = gid
        gname = (data or {}).get("name", gid)
        caller.msg(f"Primary group set to |w{gname}|n ({gid}).")

    def _do_group_create(self, handset, rest: str):
        caller = self.caller
        name = (rest or "").strip()
        if not name:
            caller.msg("Usage: hs group create <name>")
            return
        ok, msg, _gid = mg.create_group(handset, name)
        caller.msg(msg)

    def _do_group_invite(self, handset, rest: str):
        caller = self.caller
        if not rest.strip():
            caller.msg('Usage: hs group invite <group name> <contact|ID>  (quote multi-word group names)')
            return
        try:
            parts = shlex.split(rest)
        except ValueError:
            caller.msg("|rInvalid quoting.|n")
            return
        if len(parts) < 2:
            caller.msg('Usage: hs group invite <group name> <contact|ID>')
            return
        gq, target_tok = parts[0], parts[1]
        gid, _data, err = mg.resolve_group_by_name(handset, gq)
        if err:
            caller.msg(f"|r{err}|n")
            return
        mid = handset.resolve_contact_or_id(target_tok)
        if not mid:
            caller.msg("|rInvalid contact or ID.|n")
            return
        ok, msg = mg.invite_to_group(handset, gid, mid)
        caller.msg(msg)

    def _do_group_accept(self, handset, rest: str):
        caller = self.caller
        gid = (rest or "").strip().upper()
        if not gid:
            caller.msg("Usage: hs group accept <group_id>")
            return
        ok, msg = mg.accept_group_invite(handset, gid)
        caller.msg(msg)

    def _do_group_decline(self, handset, rest: str):
        caller = self.caller
        gid = (rest or "").strip().upper()
        if not gid:
            caller.msg("Usage: hs group decline <group_id>")
            return
        ok, msg = mg.decline_group_invite(handset, gid)
        caller.msg(msg)

    def _do_group_msg(self, handset, rest: str):
        caller = self.caller
        if not rest.strip():
            caller.msg(
                'Usage: hs group msg <message>  (uses primary group)\n'
                '       hs group msg <group name> <message>  (or specify group; quote multi-word names)'
            )
            return
        primary_gid = getattr(handset.db, "primary_group_id", None)
        try:
            parts = shlex.split(rest)
        except ValueError:
            caller.msg("|rInvalid quoting.|n")
            return
        if len(parts) >= 2:
            # Try first token as group name; if it fails and we have a primary, send full line to primary
            gq = parts[0]
            message = " ".join(parts[1:])
            gid, _d, err = mg.resolve_group_by_name(handset, gq)
            if err and primary_gid:
                gid, _d, err = mg.resolve_group_by_id(handset, primary_gid)
                if err:
                    handset.db.primary_group_id = None
                    caller.msg(f"|r{err}|n Set a primary group with |whs group <name>|n.")
                    return
                message = rest.strip()
            elif err:
                caller.msg(f"|r{err}|n")
                return
        elif primary_gid:
            # Use primary group; rest is the message
            gid, _d, err = mg.resolve_group_by_id(handset, primary_gid)
            if err:
                handset.db.primary_group_id = None
                caller.msg(f"|r{err}|n Set a primary group with |whs group <name>|n.")
                return
            message = rest.strip()
        else:
            caller.msg(
                "|rSet a primary group first with |whs group <name>|n, "
                "or use |whs group msg <group name> <message>|n"
            )
            return
        d, tot = mg.send_group_message(handset, gid, message)
        # d = handsets that received the line; tot = roster size (includes you)
        caller.msg(f"|gSent|n |x({d}/{tot} members)|n.")

    def _do_group_list(self, handset):
        caller = self.caller
        chats = getattr(handset.db, "group_chats", None) or {}
        if not isinstance(chats, dict) or not chats:
            caller.msg("You're not in any group chats.")
            return
        lines = ["|c=== Group Chats ===|n"]
        for gid, data in sorted(chats.items(), key=lambda x: str((x[1] or {}).get("name", x[0])).lower()):
            if not isinstance(data, dict):
                continue
            name = data.get("name", gid)
            members = data.get("members") or []
            n = len(members) if isinstance(members, list) else 0
            unread = mg.get_unread_group_count(handset, gid)
            role = (data.get("role") or "member").strip().lower()
            lines.append(f"  |w{name}|n ({n} members, {unread} unread) [{role}]  |x{gid}|n")
        caller.msg("\n".join(lines))

    def _do_group_view(self, handset, rest: str):
        caller = self.caller
        gq = (rest or "").strip()
        if not gq:
            caller.msg("Usage: hs group view <group name>")
            return
        gid, gdata, err = mg.resolve_group_by_name(handset, gq)
        if err:
            caller.msg(f"|r{err}|n")
            return
        msgs = mg.get_group_messages(handset, gid, limit=30)
        mg.mark_group_read(handset, gid)
        if not msgs:
            caller.msg("|xNo messages in that group yet.|n")
            return
        lines = [f"|c=== {(gdata or {}).get('name', gid)} ===|n"]
        for entry in msgs:
            if isinstance(entry, dict):
                lines.append(mg.format_inbox_line(handset, entry))
        caller.msg("\n".join(lines))

    def _do_group_leave(self, handset, rest: str):
        caller = self.caller
        gq = (rest or "").strip()
        if not gq:
            caller.msg("Usage: hs group leave <group name>")
            return
        gid, _d, err = mg.resolve_group_by_name(handset, gq)
        if err:
            caller.msg(f"|r{err}|n")
            return
        if getattr(handset.db, "primary_group_id", None) == gid:
            handset.db.primary_group_id = None
        ok, msg = mg.leave_group(handset, gid)
        caller.msg(msg)

    def _do_group_rename(self, handset, rest: str):
        caller = self.caller
        if " = " not in rest:
            caller.msg("Usage: hs group rename <group name> = <new name>")
            return
        left, _, right = rest.partition(" = ")
        gq = left.strip()
        new_name = right.strip()
        if not gq or not new_name:
            caller.msg("Usage: hs group rename <group name> = <new name>")
            return
        gid, _d, err = mg.resolve_group_by_name(handset, gq)
        if err:
            caller.msg(f"|r{err}|n")
            return
        ok, msg = mg.rename_group_local(handset, gid, new_name)
        caller.msg(msg)

    def _do_group_kick(self, handset, rest: str):
        caller = self.caller
        if not rest.strip():
            caller.msg('Usage: hs group kick <group name> <contact|ID>')
            return
        try:
            parts = shlex.split(rest)
        except ValueError:
            caller.msg("|rInvalid quoting.|n")
            return
        if len(parts) < 2:
            caller.msg('Usage: hs group kick <group name> <contact|ID>')
            return
        gq, tok = parts[0], parts[1]
        gid, _d, err = mg.resolve_group_by_name(handset, gq)
        if err:
            caller.msg(f"|r{err}|n")
            return
        mid = handset.resolve_contact_or_id(tok)
        if not mid:
            caller.msg("|rInvalid contact or ID.|n")
            return
        ok, msg = mg.kick_member(handset, gid, mid)
        caller.msg(msg)

    def _do_group_promote(self, handset, rest: str):
        caller = self.caller
        if not rest.strip():
            caller.msg('Usage: hs group promote <group name> <contact|ID>')
            return
        try:
            parts = shlex.split(rest)
        except ValueError:
            caller.msg("|rInvalid quoting.|n")
            return
        if len(parts) < 2:
            caller.msg('Usage: hs group promote <group name> <contact|ID>')
            return
        gq, tok = parts[0], parts[1]
        gid, _d, err = mg.resolve_group_by_name(handset, gq)
        if err:
            caller.msg(f"|r{err}|n")
            return
        mid = handset.resolve_contact_or_id(tok)
        if not mid:
            caller.msg("|rInvalid contact or ID.|n")
            return
        ok, msg = mg.promote_member(handset, gid, mid)
        caller.msg(msg)

    def _do_group_members(self, handset, rest: str):
        caller = self.caller
        gq = (rest or "").strip()
        if not gq:
            caller.msg("Usage: hs group members <group name>")
            return
        gid, data, err = mg.resolve_group_by_name(handset, gq)
        if err:
            caller.msg(f"|r{err}|n")
            return
        members = data.get("members") or []
        admins = set(mg.normalize_matrix_id(str(a)) for a in (data.get("admins") or []))
        lines = [f"|c=== {data.get('name', gid)} members ===|n"]
        if not isinstance(members, list):
            members = []
        for m in members:
            mid = mg.normalize_matrix_id(str(m))
            disp = handset.display_alias_or_id(mid)
            role = "admin" if mid in admins else "member"
            h = mg.lookup_handset(mid)
            if h and h.has_network_coverage():
                sig = "|gonline|n"
            elif h:
                sig = "|yoffline|n"
            else:
                sig = "|xno handset|n"
            lines.append(f"  {disp}  [{role}]  {sig}")
        caller.msg("\n".join(lines))

    def _do_group_mute(self, handset, rest: str, muted: bool):
        caller = self.caller
        gq = (rest or "").strip()
        if not gq:
            caller.msg("Usage: hs group mute <group name>  /  hs group unmute <group name>")
            return
        gid, _d, err = mg.resolve_group_by_name(handset, gq)
        if err:
            caller.msg(f"|r{err}|n")
            return
        ok, msg = mg.set_group_muted(handset, gid, muted)
        caller.msg(msg)
