"""
Roleplay mixin: recog, display names, say/whisper (with voice and cameras), move announcements.
"""
from evennia.utils import logger
from evennia.utils.utils import make_iter


def _feed_room_cameras(location, speaker, message, improvise):
    """
    Feed say line to cameras in the room (or held by anyone here) and, if improvising,
    trigger audience echo. Call from at_say after room say loop.
    """
    say_line = '%s says, "%s"' % (speaker.get_display_name(speaker), message)
    if improvise:
        say_line = "|w%s|n" % say_line
    try:
        from typeclasses.broadcast import feed_cameras_in_location
        feed_cameras_in_location(location, say_line)
    except Exception as err:
        logger.log_trace("roleplay_mixin._feed_room_cameras: %s" % err)
    if improvise:
        try:
            from commands.performance_cmds import _audience_echo_improvise
            _audience_echo_improvise(location)
        except Exception as err:
            logger.log_trace("roleplay_mixin._feed_room_cameras improvise echo: %s" % err)


def _at_say_whisper_overhear(location, speaker, message, receivers):
    """Send whisper overhear to other characters; they hear it in speaker's language (garbled by their skill)."""
    if not location or not receivers:
        return
    try:
        from world.rpg.language import get_speaker_language, process_language_for_viewer
        exclude = make_iter(receivers)
        exclude = list(exclude) + [speaker]
        chars_here = location.contents_get(content_type="character")
        lang_key = get_speaker_language(speaker)
        for viewer in chars_here:
            if viewer in exclude or viewer == speaker:
                continue
            heard = process_language_for_viewer(speaker, message, lang_key, viewer)
            from world.rp_features import get_display_name_for_viewer
            from world.skin_tones import format_ic_character_name

            plain = get_display_name_for_viewer(speaker, viewer)
            obj_name = format_ic_character_name(speaker, viewer, plain)
            line = '%s whispers something to someone... "%s"' % (obj_name, heard)
            viewer.msg(text=(line, {"type": "whisper"}), from_obj=speaker)
    except Exception as err:
        logger.log_trace("roleplay_mixin._at_say_whisper_overhear: %s" % err)


class RoleplayMixin:
    """Recog, get_display_name, get_search_result, announce_move_*, at_say (say/whisper/voice/cameras)."""

    @property
    def recog(self):
        """Per-viewer recognition: who you've been introduced to (see world.rp_features)."""
        from world.rp_features import RecogHandler
        if not hasattr(self, "_recog_handler"):
            self._recog_handler = RecogHandler(self)
        return self._recog_handler

    def get_display_name(self, looker=None, **kwargs):
        """
        Viewer-aware name: sdesc until introduced, then recog or key.
        When they wear a mask/helmet, others see sdesc only (recog hidden until they remove it).
        """
        from world.rp_features import get_display_name_for_viewer
        return get_display_name_for_viewer(self, looker, **kwargs)

    def get_search_result(self, searchdata, attribute_name=None, typeclass=None, candidates=None, exact=False, use_dbref=None, tags=None, **kwargs):
        """
        Allow search/look by sdesc or recog (e.g. 'look average naked person', 'look Bob').
        When candidates are in the same location, try matching by display name (sdesc/recog) first.
        You cannot find a character by their actual key/name unless you have them recog'd.
        """
        if candidates is not None and searchdata and isinstance(searchdata, str):
            try:
                from evennia.utils.utils import inherits_from
                from world.rpg.emote import resolve_sdesc_to_characters
                cand_list = list(candidates)
                char_candidates = [c for c in cand_list if inherits_from(c, "typeclasses.characters.Character")]
                if char_candidates:
                    matches = resolve_sdesc_to_characters(self, char_candidates, searchdata.strip())
                    if matches:
                        return list(matches)
            except Exception as err:
                logger.log_trace("roleplay_mixin.get_search_result resolve_sdesc: %s" % err)
        results = super().get_search_result(
            searchdata,
            attribute_name=attribute_name,
            typeclass=typeclass,
            candidates=candidates,
            exact=exact,
            use_dbref=use_dbref,
            tags=tags,
            **kwargs,
        )
        # Don't allow finding a character by key/alias unless the caller has recog'd them (dbref search still works)
        if candidates is not None and searchdata and isinstance(searchdata, str) and not (searchdata.strip().startswith("#")):
            try:
                result_list = list(results)
                filtered = []
                for obj in result_list:
                    if hasattr(obj, "recog") and getattr(obj, "recog", None) is not None:
                        if self.recog.get(obj):
                            filtered.append(obj)
                    else:
                        filtered.append(obj)
                return filtered
            except Exception as err:
                logger.log_trace("roleplay_mixin.get_search_result filter recog: %s" % err)
        return results

    def announce_move_from(self, destination, msg=None, mapping=None, move_type="move", **kwargs):
        """Announce departure: each viewer sees recog name or sdesc only (no 'sdesc (key)' — respects recog)."""
        if not self.location:
            return
        if move_type not in ("move", "traverse") or not destination:
            super().announce_move_from(destination, msg=msg, mapping=mapping, move_type=move_type, **kwargs)
            return
        location = self.location
        viewers = [c for c in location.contents_get(content_type="character") if c != self]
        if getattr(destination, "db", None) and getattr(destination.db, "pod", None):
            for viewer in viewers:
                from world.rp_features import get_move_display_for_viewer
                display = get_move_display_for_viewer(self, viewer)
                viewer.msg("%s enters the splinter pod." % display)
            return
        exits = [
            o for o in (getattr(location, "contents", None) or [])
            if getattr(o, "destination", None) is destination
        ]
        if not exits:
            super().announce_move_from(destination, msg=msg, mapping=mapping, move_type=move_type, **kwargs)
            return
        exi = exits[0]
        direction = exi.key.strip()
        custom_depart = getattr(getattr(exi, "db", None), "move_depart_others", None)
        if custom_depart and str(custom_depart).strip():
            from world.rp_features import format_exit_move_line_for_viewer

            action = str(custom_depart).strip()
            for viewer in viewers:
                line = format_exit_move_line_for_viewer(action, self, viewer)
                if line:
                    viewer.msg(line)
            return
        from world.rp_features import get_move_display_for_viewer
        for viewer in viewers:
            display = get_move_display_for_viewer(self, viewer)
            viewer.msg(f"{display} goes {direction}.")

    def announce_move_to(self, source_location, msg=None, mapping=None, move_type="move", **kwargs):
        """Announce arrival: each viewer sees recog name or sdesc only (no 'sdesc (key)' — respects recog)."""
        if not self.location:
            return
        if move_type not in ("move", "traverse") or not source_location:
            super().announce_move_to(source_location, msg=msg, mapping=mapping, move_type=move_type, **kwargs)
            return
        exits = [
            o for o in (getattr(source_location, "contents", None) or [])
            if getattr(o, "destination", None) is self.location
        ]
        if not exits:
            super().announce_move_to(source_location, msg=msg, mapping=mapping, move_type=move_type, **kwargs)
            return
        exi = exits[0]
        direction = exi.key.strip()
        viewers = [c for c in self.location.contents_get(content_type="character") if c != self]
        custom_arrive = getattr(getattr(exi, "db", None), "move_arrive_others", None)
        if custom_arrive and str(custom_arrive).strip():
            from world.rp_features import format_exit_move_line_for_viewer

            action = str(custom_arrive).strip()
            for viewer in viewers:
                line = format_exit_move_line_for_viewer(action, self, viewer)
                if line:
                    viewer.msg(line)
        else:
            from world.rp_features import get_move_display_for_viewer
            for viewer in viewers:
                display = get_move_display_for_viewer(self, viewer)
                viewer.msg(f"{display} arrives from the {direction}.")
        arr_self = getattr(getattr(exi, "db", None), "move_arrive_self", None)
        if arr_self and str(arr_self).strip():
            try:
                self.msg(str(arr_self).strip().format(direction=direction))
            except Exception:
                self.msg(str(arr_self).strip())

    def at_say(self, message, msg_self=None, msg_location=None, receivers=None, msg_receivers=None, **kwargs):
        """
        Say (and whisper) hook. For room say, optionally show voice; language garbling applied per viewer.
        """
        from world.rpg.voice import get_voice_phrase, get_speaking_tag, voice_perception_check

        # Whisper or explicit receivers: send per-receiver with language processing, then overhear
        if kwargs.get("whisper", False) or receivers:
            from world.rpg.language import get_speaker_language, process_language_for_viewer
            custom_mapping = kwargs.get("mapping", {})
            location = self.location
            msg_type = "say"
            lang_key = get_speaker_language(self)
            msg_receivers = msg_receivers or '{object} whispers: "|n{speech}|n"'
            if msg_self:
                self_mapping = {
                    "self": "You",
                    "object": self.get_display_name(self),
                    "location": location.get_display_name(self) if location else None,
                    "receiver": None,
                    "all_receivers": None,
                    "speech": message,
                }
                self_mapping.update(custom_mapping)
                template = msg_self if isinstance(msg_self, str) else 'You whisper: "|n{speech}|n"'
                self.msg(text=(template.format_map(self_mapping), {"type": msg_type}), from_obj=self)
            if receivers and msg_receivers:
                all_recv_names = ", ".join(r.get_display_name(r) for r in make_iter(receivers))
                for receiver in make_iter(receivers):
                    speech = process_language_for_viewer(self, message, lang_key, receiver)
                    receiver_mapping = {
                        "self": "You",
                        "object": self.get_display_name(receiver),
                        "location": location.get_display_name(receiver) if location else None,
                        "receiver": receiver.get_display_name(receiver),
                        "all_receivers": all_recv_names,
                        "speech": speech,
                    }
                    receiver_mapping.update(custom_mapping)
                    receiver.msg(
                        text=(msg_receivers.format_map(receiver_mapping), {"type": msg_type}),
                        from_obj=self,
                    )
            if kwargs.get("whisper", False) and receivers and location:
                _at_say_whisper_overhear(location, self, message, receivers)
            return

        custom_mapping = kwargs.get("mapping", {})
        location = self.location
        msg_type = "say"
        voice_phrase = get_voice_phrase(self)
        improvise = getattr(self.ndb, "performance_improvising", False)
        from world.rpg.language import get_speaker_language, process_language_for_viewer

        if msg_self:
            self_mapping = {
                "self": "You",
                "object": self.get_display_name(self),
                "location": location.get_display_name(self) if location else None,
                "receiver": None,
                "all_receivers": None,
                "speech": message,
            }
            self_mapping.update(custom_mapping)
            template = msg_self if isinstance(msg_self, str) else 'You say, "|n{speech}|n"'
            line_self = template.format_map(self_mapping)
            if improvise:
                line_self = "|w%s|n" % line_self
            self.msg(text=(line_self, {"type": msg_type}), from_obj=self)

        if not location:
            return

        lang_key = get_speaker_language(self)
        # Room say: send to each character in location (except self) with language per viewer
        chars_here = location.contents_get(content_type="character")
        for viewer in make_iter(chars_here):
            if viewer == self:
                continue
            speech = process_language_for_viewer(self, message, lang_key, viewer)
            from world.rp_features import get_display_name_for_viewer
            from world.skin_tones import format_ic_character_name

            plain = self.get_display_name(viewer)
            obj_name = format_ic_character_name(self, viewer, plain)
            if voice_phrase and voice_perception_check(viewer, self):
                line = '%s says in a %s, "*speaking in a %s* %s"' % (obj_name, voice_phrase, voice_phrase, speech)
            else:
                line = '%s says, "%s"' % (obj_name, speech)
            if improvise:
                line = "|w%s|n" % line
            viewer.msg(text=(line, {"type": msg_type}), from_obj=self)

        _feed_room_cameras(location, self, message, improvise)
        try:
            from world.rp_features import get_display_name_for_viewer
            from world.skin_tones import format_ic_character_name
            plain_neutral = self.get_display_name(None)
            obj_neutral = format_ic_character_name(self, None, plain_neutral)
            if voice_phrase:
                relay_line = '%s says in a %s, "*speaking in a %s* %s"' % (obj_neutral, voice_phrase, voice_phrase, message)
            else:
                relay_line = '%s says, "%s"' % (obj_neutral, message)
            if improvise:
                relay_line = "|w%s|n" % relay_line
            from typeclasses.vehicles import relay_to_parked_vehicle_interiors
            relay_to_parked_vehicle_interiors(location, relay_line)
        except Exception:
            pass
