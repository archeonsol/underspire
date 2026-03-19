from __future__ import annotations

from datetime import datetime

import re
import shlex

from commands.base_cmds import Command


def _ts():
    return datetime.now().strftime("%b %d %H:%M")

def _clock():
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
        return None
    obj = lookup_matrix_id(matrix_id)
    if not obj:
        return None
    # Avoid circular import; rely on device_type marker.
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
        hname = holder.get_display_name(holder) if hasattr(holder, "get_display_name") else holder.key
        # Observers: "X's handset rings."
        try:
            room.msg_contents(f"{hname}'s handset rings.", exclude=holder)
        except Exception:
            pass


def _beep_text_message(receiver_handset, sender_id: str, msg: str):
    display = receiver_handset.display_alias_or_id(sender_id)
    ts = _ts()
    # Persist on the handset itself (and prune to last 24h).
    if hasattr(receiver_handset, "add_text_message"):
        receiver_handset.add_text_message(_as_matrix_id(sender_id) or sender_id, msg, ts_display=ts)
    else:
        # Legacy fallback (no 24h pruning).
        receiver_handset.db.texts = list(getattr(receiver_handset.db, "texts", []) or []) + [
            {"ts": ts, "from": _as_matrix_id(sender_id), "msg": msg}
        ]
    holder, _room = _holder_and_room(receiver_handset)
    if holder:
        holder.msg("Your handset beeps.")
        holder.msg(f"[{ts}]{display}: {msg}")


def _unread_notifications(handset) -> int:
    """
    Count unread text messages since the last time messages were viewed.
    """
    last_view = getattr(getattr(handset, "db", None), "last_texts_viewed_t", None)
    try:
        last_view = float(last_view) if last_view is not None else 0.0
    except Exception:
        last_view = 0.0

    try:
        msgs = handset.get_text_messages() if hasattr(handset, "get_text_messages") else list(getattr(handset.db, "texts", []) or [])
    except Exception:
        msgs = []

    count = 0
    for entry in msgs or []:
        if not isinstance(entry, dict):
            continue
        t = entry.get("t", None)
        # Legacy entries without timestamps count as unread until first view.
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


def _clear_call(handset):
    try:
        handset.ndb.call_state = "idle"
        handset.ndb.call_peer = None
    except Exception:
        pass


def _get_peer(handset):
    peer_dbref = getattr(handset.ndb, "call_peer", None)
    if not peer_dbref:
        return None
    try:
        from evennia import search_object

        results = search_object(f"#{int(peer_dbref)}")
        return results[0] if results else None
    except Exception:
        return None


class CmdHandset(Command):
    """
    Use your handset to call, speak, hang up, save contacts, and text.

    Usage:
      hs call <ID|alias>
      hs contacts
      hs photo <ID|alias>
      hs selfie <ID|alias> "<title>" "<text>"
      hs selfie <ID|alias> <text>                (no title; title defaults to 'selfie')
      hs speak <message>
      hs hangup
      hs save <ID> as <alias>
      hs text <ID|alias> <message>
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
        # Fallback: look for a handset in inventory.
        for obj in list(getattr(caller, "contents", []) or []):
            if getattr(getattr(obj, "db", None), "device_type", None) == "handset":
                return obj
        return None

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
        if action == "speak":
            self._do_speak(handset, rest)
            return
        if action == "hangup":
            self._do_hangup(handset)
            return
        if action == "text":
            self._do_text(handset, rest)
            return

        caller.msg("|rUnknown handset command.|n Usage: hs call, contacts, photo, selfie, speak, hangup, save, text ...")

    def _do_save(self, handset, rest: str):
        caller = self.caller
        if " as " not in rest:
            caller.msg("Usage: hs save <ID> as <alias>")
            return
        id_part, _, alias = rest.partition(" as ")
        matrix_id = handset.resolve_contact_or_id(id_part.strip())
        ok, msg = handset.save_contact(matrix_id, alias.strip())
        caller.msg(msg)

    def _do_contacts(self, handset):
        caller = self.caller
        contacts = handset.get_contacts()
        if not contacts:
            caller.msg("You have no handset contacts saved.")
            return
        # Display sorted by alias.
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
        target_id = handset.resolve_contact_or_id(target_token)
        if not target_id:
            caller.msg("|rInvalid number/contact.|n")
            return
        # If sending to your own handset, avoid registry lookup ambiguity.
        try:
            if hasattr(handset, "get_matrix_id") and handset.get_matrix_id() and handset.get_matrix_id().upper() == str(target_id).upper():
                target_handset = handset
            else:
                target_handset = _lookup_handset_by_matrix_id(target_id)
        except Exception:
            target_handset = _lookup_handset_by_matrix_id(target_id)
        if not target_handset:
            caller.msg("|rThat number can't be reached.|n")
            return
        if not target_handset.has_network_coverage():
            caller.msg("|rNot delivered. That handset has no signal.|n")
            return

        room = caller.location
        try:
            # Handset photos should match the taker's actual `look` output as closely as possible.
            snap = room.return_appearance(caller)
        except Exception:
            snap = str(room)

        # Handset photos should look like a room "look" snapshot and preserve perspective:
        # viewers should see *their* own recog/sdesc for people in the image.
        #
        # But handset photos should NOT support:
        # - tagging/recogging people *from* the photo (that's the Photograph system)
        # - close-up inspection of individuals
        #
        # Implementation: store placeholders (<<CHAR:<id>>>) so the viewer can resolve
        # names via their own get_display_name(), and store only sdesc fallbacks.
        snapshot_chars = {}
        try:
            from evennia.utils.utils import inherits_from
            from world.rpg.sdesc import get_short_desc
            from typeclasses.rooms import ROOM_DESC_CHARACTER_NAME_COLOR

            visible = room.filter_visible(room.contents_get(content_type="character"), caller)
            visible = [c for c in visible if inherits_from(c, "evennia.objects.objects.DefaultCharacter")]
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
                    # Fallback if something emitted the name without the expected color wrapper.
                    snap = snap.replace(name_for_photographer, placeholder)

                # Store ONLY sdesc fallback (no detailed close-ups for handset photos).
                snapshot_chars[str(cid)] = {"sdesc": get_short_desc(char, looker=caller)}
        except Exception:
            snapshot_chars = {}
        room_name = getattr(room, "key", "somewhere")
        ts = _ts()
        title = f"photograph of {room_name}"
        photo_id = None
        if hasattr(target_handset, "add_photo"):
            photo_id = target_handset.add_photo("photo", title=title, snapshot_text=snap, ts_display=ts, snapshot_chars=snapshot_chars)
        caller.msg(f"You depress the shutter and send a photo to {handset.display_alias_or_id(target_id)}.")
        caller.msg(f"|gDelivered to:|n {handset.display_alias_or_id(target_id)}")
        try:
            room.msg_contents(
                f"{caller.get_display_name(caller)} takes a photo with their handset.",
                exclude=caller,
            )
        except Exception:
            pass
        holder, _room = _holder_and_room(target_handset)
        if holder:
            holder.msg("Your handset beeps.")
            holder.msg(f"|gYou receive a photo|n: {title}" + (f" |x(stored as photo #{photo_id})|n" if photo_id else ""))

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

        # Allow quoted multi-word title/text:
        #   hs selfie ^ID "my cool title" "some longer message"
        # Back-compat: if only one chunk, treat it as text and default title to "selfie".
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

        target_id = handset.resolve_contact_or_id(target_token)
        if not target_id:
            caller.msg("|rInvalid number/contact.|n")
            return
        # If sending to your own handset, avoid registry lookup ambiguity.
        try:
            if hasattr(handset, "get_matrix_id") and handset.get_matrix_id() and handset.get_matrix_id().upper() == str(target_id).upper():
                target_handset = handset
            else:
                target_handset = _lookup_handset_by_matrix_id(target_id)
        except Exception:
            target_handset = _lookup_handset_by_matrix_id(target_id)
        if not target_handset:
            caller.msg("|rThat number can't be reached.|n")
            return
        if not target_handset.has_network_coverage():
            caller.msg("|rNot delivered. That handset has no signal.|n")
            return

        # Build a "snapshot" of the character: general line + merged body appearance.
        general = (getattr(getattr(caller, "db", None), "general_desc", None) or "This is a character.").strip()
        merged = ""
        if hasattr(caller, "format_body_appearance"):
            try:
                merged = caller.format_body_appearance().strip()
            except Exception:
                merged = ""
        parts = [intro, ""]
        if general:
            parts.append(general)
        if merged:
            parts.append(merged)
        snap = "\n\n".join(p for p in parts if p is not None)
        ts = _ts()
        photo_id = None
        if hasattr(target_handset, "add_photo"):
            photo_id = target_handset.add_photo("selfie", title=title, snapshot_text=snap, ts_display=ts)
        caller.msg(f"You take a selfie and send it to {handset.display_alias_or_id(target_id)}.")
        caller.msg(f"|gDelivered to:|n {handset.display_alias_or_id(target_id)}")
        if getattr(caller, "location", None):
            try:
                caller.location.msg_contents(
                    f"{caller.get_display_name(caller)} takes a selfie with their handset.",
                    exclude=caller,
                )
            except Exception:
                pass
        holder, _room = _holder_and_room(target_handset)
        if holder:
            holder.msg("Your handset beeps.")
            tdisp = f": {title}" if title else "."
            holder.msg(f"|gYou receive a photo|n{tdisp}" + (f" |x(stored as photo #{photo_id})|n" if photo_id else ""))

    def _do_call(self, handset, rest: str):
        caller = self.caller
        if not rest:
            caller.msg("Usage: hs call <ID|alias>")
            return

        state = handset._call_state()
        if state in ("dialing", "ringing", "in_call"):
            caller.msg("|yYou're already on a line. Use|n |whs hangup|n |yto end it.|n")
            return

        target_id = handset.resolve_contact_or_id(rest)
        if not target_id:
            caller.msg("|rInvalid number/contact.|n")
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

        # Establish ringing state.
        handset._set_call_state("dialing", peer_dbref=target_handset.id)
        target_handset._set_call_state("ringing", peer_dbref=handset.id)

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
        # Move both to in_call.
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

    def _do_hangup(self, handset, quiet_peer: bool = False):
        caller = self.caller
        state = handset._call_state()
        if state == "idle":
            caller.msg("You're not in a call.")
            return

        peer = _get_peer(handset)
        _clear_call(handset)
        caller.msg("You hang up.")

        if peer:
            _clear_call(peer)
            if not quiet_peer:
                peer_holder, _ = _holder_and_room(peer)
                if peer_holder:
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

        target_id = handset.resolve_contact_or_id(target_token.strip())
        if not target_id:
            caller.msg("|rInvalid number/contact.|n")
            return

        target_handset = _lookup_handset_by_matrix_id(target_id)
        if not target_handset:
            caller.msg("|rThat number can't be reached.|n")
            return

        if not target_handset.has_network_coverage():
            caller.msg("|rMessage not delivered. That handset has no signal.|n")
            return

        sender_id = handset.get_phone_number() or ""
        _beep_text_message(target_handset, sender_id, msg.strip())
        caller.msg(f"|gSent|n to {handset.display_alias_or_id(target_id)}.")

