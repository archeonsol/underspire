"""
Room

Rooms are simple containers that has no location of their own.
Look output: room name (colored), desc, "You see a X, a Y and a Z.", character poses, exits.
"""

import re
from evennia.objects.objects import DefaultRoom, DefaultExit
from evennia.utils import delay
from evennia.utils.utils import compress_whitespace, iter_to_str
from evennia.contrib.grid.xyzgrid.xyzroom import XYZRoom

from world.theme_colors import ROOM_COLORS

from .objects import ObjectParent
from typeclasses.matrix.mixins.matrix_id import MatrixIdMixin


# Substring that indicates the stock Evennia welcome desc (replace with our default)
_DEFAULT_WELCOME_MARKER = "evennia.com"

# Room look palette — see world.theme_colors.ROOM_COLORS
ROOM_DESC_ROOM_NAME_COLOR = ROOM_COLORS["room_name"]
ROOM_DESC_CHARACTER_NAME_COLOR = ROOM_COLORS["character_name"]
ROOM_DESC_OBJECT_NAME_COLOR = ROOM_COLORS["object"]
ROOM_DESC_BODY_COLOR = ROOM_COLORS["room_desc_body"]
ROOM_DESC_EXIT_PROSE_COLOR = ROOM_COLORS["exit_prose"]
ROOM_DESC_EXIT_NAME_DIM_COLOR = ROOM_COLORS["exit_name_dim"]


def _ic_room_char_name(char, looker, **kwargs):
    """Plain display name wrapped with skin tone (or default room name color)."""
    from world.skin_tones import format_ic_character_name

    plain = char.get_display_name(looker, **kwargs)
    return format_ic_character_name(char, looker, plain)


def _is_motorcycle_vehicle(obj):
    """True if obj is a motorcycle (open bike)."""
    try:
        from typeclasses.vehicles import Motorcycle

        return isinstance(obj, Motorcycle) or getattr(obj.db, "vehicle_type", None) == "motorcycle"
    except ImportError:
        return getattr(getattr(obj, "db", None), "vehicle_type", None) == "motorcycle"


def _article_word(name):
    """Return 'a' or 'an' for the given noun (no leading article)."""
    n = (name or "").strip()
    if not n:
        return "a"
    return "an" if n[0].lower() in "aeiou" else "a"


def _bike_phrase_for_riding(bike):
    """Noun phrase for 'riding on …' (e.g. 'a ratbike')."""
    raw = getattr(bike.db, "vehicle_name", None) or getattr(bike, "key", None) or "bike"
    raw = (raw or "").strip()
    low = raw.lower()
    if low.startswith("a ") or low.startswith("an "):
        return raw
    return f"{_article_word(raw)} {raw}"


def _riding_on_motorcycle_sentence(rider, bike, looker, **kwargs):
    """Colored line: 'Name is riding on a ratbike' or 'You are riding on a ratbike'."""
    bike_colored = f"{ROOM_DESC_OBJECT_NAME_COLOR}{_bike_phrase_for_riding(bike)}|n"
    if rider is looker:
        return f"You are riding on {bike_colored}"
    rname = _ic_room_char_name(rider, looker, **kwargs)
    return f"{rname} is riding on {bike_colored}"


def _is_vehicle(obj):
    """True if obj is a Vehicle (for room pose: parked/idling). Lazy import to avoid circular import."""
    try:
        from typeclasses.vehicles import Vehicle
        return isinstance(obj, Vehicle)
    except ImportError:
        return False


def _is_corpse(obj):
    """True if obj is a Corpse (permanent dead body). Shown in 'You see' line, not as a character."""
    try:
        from typeclasses.corpse import Corpse
        return isinstance(obj, Corpse)
    except ImportError:
        return False


def _is_operating_table(obj):
    """True if obj is an OperatingTable (patient lies on it; show 'X is lying on the operating table')."""
    try:
        from typeclasses.medical_tools import OperatingTable
        return isinstance(obj, OperatingTable)
    except ImportError:
        return False


def _is_seat(obj):
    """True if obj is a Seat (chair, couch; show 'X is sitting on Y')."""
    try:
        from typeclasses.seats import Seat
        return isinstance(obj, Seat)
    except ImportError:
        return False


def _is_bed(obj):
    """True if obj is a Bed (bed, cot; show 'X is lying on Y')."""
    try:
        from typeclasses.seats import Bed
        return isinstance(obj, Bed)
    except ImportError:
        return False


class Room(MatrixIdMixin, ObjectParent, DefaultRoom):
    """
    Rooms are like any Object, except their location is None
    (which is default). Look output: room name (colored), desc, "You see a X, a Y.",
    character/vehicle/corpse poses, then "There are exits to the north (n), ...".

    Builder fields (optional):
      db.room_display_mode — "street" for narrative exits + global climate line, else interior (default).
      db.room_look_state — bracket suffix on the title, e.g. CROWDED → " [CROWDED]".
      db.narrative_exit_prose — optional legacy: used only when no exit has db.exit_narrative set.
      Prefer db.exit_narrative on each Exit for street exit lines (see typeclasses.exits.Exit).
      db.ambient_messages — optional list of one-line ambient strings (one random per look).
        Street: appended after weather on the same line as the desc (separate sentence). Interior: block below desc.
    """

    # In-character, non-descript default when room has no custom desc
    default_description = "A place. Nothing much to note."

    def _should_have_matrix_id(self):
        """
        Rooms only need Matrix IDs when they're access points (mlinked to a router).
        """
        return self.db.network_router is not None

    def msg_contents(self, text=None, exclude=None, from_obj=None, mapping=None,
                     raise_funcparse_errors=False, **kwargs):
        """Send to room. Cameras in the room (or held by characters here) capture via feed_cameras_in_location."""
        super().msg_contents(
            text=text,
            exclude=exclude,
            from_obj=from_obj,
            mapping=mapping,
            raise_funcparse_errors=raise_funcparse_errors,
            **kwargs,
        )
        raw = text if isinstance(text, str) else (text[0] if isinstance(text, (tuple, list)) and text else "")
        if raw:
            try:
                from typeclasses.broadcast import feed_cameras_in_location
                feed_cameras_in_location(self, raw)
            except Exception:
                pass
            try:
                from typeclasses.vehicles import relay_to_parked_vehicle_interiors
                relay_to_parked_vehicle_interiors(self, raw)
            except Exception:
                pass

    def filter_visible(self, obj_list, looker, **kwargs):
        """Hide unspotted sneaking characters from look; staff see everyone."""
        from evennia.utils.utils import inherits_from, make_iter

        if not looker:
            return super().filter_visible(obj_list, looker, **kwargs)

        # Evennia's base filter_visible drops the looker (obj != looker). When callers pass
        # [looker] — e.g. motorcycle rider visibility — super() returns [] and riding/@lp break.
        # Filter everyone else first, then splice the looker back in original order.
        seq = list(make_iter(obj_list))
        looker_in_seq = any(o is looker for o in seq)
        others = [o for o in seq if o is not looker]
        result = super().filter_visible(others, looker, **kwargs)
        result = list(result if result is not None else [])

        try:
            from world.rpg import stealth

            if stealth._is_staff(looker):
                stealth_out = result
            else:
                stealth_out = []
                for obj in result:
                    try:
                        if inherits_from(obj, "evennia.objects.objects.DefaultCharacter"):
                            if stealth.is_hidden(obj) and not stealth.has_spotted(looker, obj):
                                continue
                    except Exception:
                        pass
                    stealth_out.append(obj)
        except Exception:
            stealth_out = result

        if not looker_in_seq:
            return stealth_out

        try:
            if not inherits_from(looker, "evennia.objects.objects.DefaultCharacter"):
                return stealth_out
        except Exception:
            return stealth_out

        out = []
        si = 0
        for o in seq:
            if o is looker:
                out.append(looker)
            else:
                if si < len(stealth_out) and o is stealth_out[si]:
                    out.append(o)
                    si += 1
        return out

    def _is_street_mode(self):
        """True when this room uses street layout (narrative exits, global climate line, etc.)."""
        return getattr(self.db, "room_display_mode", None) == "street"

    def get_extra_display_name_info(self, looker=None, **kwargs):
        """Bracket suffix for the room title, e.g. ' [CROWDED]' or ' [bedroom]' (builder: db.room_look_state)."""
        state = getattr(self.db, "room_look_state", None)
        if not state:
            return ""
        st = str(state).strip()
        if not st:
            return ""
        return f" [{st.upper()}]"

    def _raw_display_desc_text(self, looker, **kwargs):
        """Plain-text room description (no color), before street/climate wrapping."""
        desc = self.db.desc or ""
        if not desc:
            return self.default_description
        if _DEFAULT_WELCOME_MARKER.lower() in desc.lower():
            return self.default_description
        return desc

    @staticmethod
    def _ensure_sentence_end(text: str) -> str:
        t = (text or "").strip()
        if not t:
            return ""
        if t[-1] not in ".!?":
            return t + "."
        return t

    def _pick_ambient_message_plain(self):
        """Single random line from db.ambient_messages, plain text (no color)."""
        msgs = getattr(self.db, "ambient_messages", None) or []
        if not msgs:
            return ""
        import random

        line = random.choice(list(msgs))
        return (line or "").strip()

    def _format_street_desc_body(self, raw, looker, **kwargs):
        """
        Street rooms: static desc (grey), then global weather/time (white), then optional
        ambient (grey) — all appended on the same line as separate sentences.
        """
        from world.global_climate import get_ambient_weather_line_for_room

        body = f"{ROOM_DESC_BODY_COLOR}{raw}|n"
        wx = get_ambient_weather_line_for_room(self).strip()
        if wx:
            wx = self._ensure_sentence_end(wx)
            body += " " + f"|w{wx}|n"
        am = self._pick_ambient_message_plain()
        if am:
            am = self._ensure_sentence_end(am)
            body += " " + f"{ROOM_DESC_BODY_COLOR}{am}|n"
        return body

    def get_display_ambient(self, looker, **kwargs):
        """One ambient line from db.ambient_messages (random pick), grey prose. Used in street and interior."""
        msgs = getattr(self.db, "ambient_messages", None) or []
        if not msgs:
            return ""
        import random

        line = random.choice(list(msgs))
        line = (line or "").strip()
        if not line:
            return ""
        return f"{ROOM_DESC_BODY_COLOR}{line}|n"

    def _street_narrative_segment(self, prose, short):
        """Grey custom prose + bold white (alias); no trailing period (joiner adds punctuation)."""
        prose = (prose or "").strip().rstrip(".!?")
        if not prose:
            return ""
        return f"{ROOM_DESC_BODY_COLOR}{prose}|n |w({short})|n"

    def _join_narrative_exit_segments(self, parts):
        """
        Join multiple exit_narrative segments: earlier clauses end with a period;
        the last two are joined with ' and ' (one period at the very end).

        e.g. three segments -> 'A (e). B (n) and C (w).'
        """
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0] + "."
        if len(parts) == 2:
            return parts[0] + " and " + parts[1] + "."
        return ". ".join(parts[:-2]) + ". " + parts[-2] + " and " + parts[-1] + "."

    def _mechanical_exit_bits(self, name_short_pairs):
        bits = []
        for name, short in name_short_pairs:
            bits.append(f"{ROOM_DESC_EXIT_NAME_DIM_COLOR}{name}|n |w({short})|n")
        return bits

    def _mechanical_exit_line_from_bits(self, bits):
        if not bits:
            return ""
        stem = f"{ROOM_DESC_EXIT_PROSE_COLOR}There are exits to the "
        if len(bits) == 1:
            line = stem + bits[0] + "."
        elif len(bits) == 2:
            line = stem + bits[0] + " and " + bits[1] + "."
        else:
            line = stem + ", ".join(bits[:-1]) + " and " + bits[-1] + "."
        return re.sub(r"  +", " ", line)

    def _visible_exit_rows(self, looker, **kwargs):
        """
        Visible exits as (exit, name, short, exit_narrative) sorted/deduped.
        exit_narrative is stripped str or '' if unset/empty.
        """
        exits = self.filter_visible(self.contents_get(content_type="exit"), looker, **kwargs)
        if not exits:
            return []
        exit_order = kwargs.get("exit_order")
        if exit_order:
            sort_index = {str(n).strip().lower(): i for i, n in enumerate(exit_order)}
            exits = sorted(exits, key=lambda e: sort_index.get((e.key or "").strip().lower(), 999))
        else:
            exits = sorted(exits, key=lambda e: (e.key or "").lower())
        seen = set()
        rows = []
        for exi in exits:
            name = (exi.key or "out").strip()
            raw_aliases = getattr(exi, "aliases", None)
            if hasattr(raw_aliases, "all"):
                aliases = list(raw_aliases.all())
            else:
                aliases = raw_aliases if isinstance(raw_aliases, (list, tuple)) else []
            short = (aliases[0].strip() if aliases else name[0].lower()) if aliases else name[0].lower()
            key = (name.lower(), short.lower())
            if key in seen:
                continue
            seen.add(key)
            narr = getattr(exi.db, "exit_narrative", None)
            narr = str(narr).strip() if narr is not None and str(narr).strip() else ""
            rows.append((exi, name, short, narr))
        return rows

    def get_display_street_exit_line(self, looker, **kwargs):
        """
        Street bottom line: exit db.exit_narrative clauses first (grey + |w(alias)|n), then
        a mechanical tail for exits without prose. If no exit has prose, use room
        narrative_exit_prose if set, else default mechanical line for all exits.
        """
        rows = self._visible_exit_rows(looker, **kwargs)
        if not rows:
            return ""
        with_narr = [(name, short, narr) for _, name, short, narr in rows if narr]
        without = [(name, short) for _, name, short, narr in rows if not narr]

        if not with_narr:
            legacy = getattr(self.db, "narrative_exit_prose", None)
            if legacy and str(legacy).strip():
                return f"{ROOM_DESC_BODY_COLOR}{str(legacy).strip()}|n"
            bits = self._mechanical_exit_bits([(n, s) for _, n, s, _ in rows])
            return self._mechanical_exit_line_from_bits(bits)

        inner = []
        for _, short, narr in with_narr:
            seg = self._street_narrative_segment(narr, short)
            if seg:
                inner.append(seg)
        narr_line = self._join_narrative_exit_segments(inner)
        out = []
        if narr_line:
            out.append(narr_line)
        if without:
            bits = self._mechanical_exit_bits(without)
            mech = self._mechanical_exit_line_from_bits(bits)
            if mech:
                out.append(mech)
        return " ".join(out)

    def get_display_narrative_exits(self, looker, **kwargs):
        """Alias for street exit line (exit-level narrative + mechanical tail)."""
        return self.get_display_street_exit_line(looker, **kwargs)

    def return_appearance(self, looker, **kwargs):
        """
        Override to explicitly call all display methods including furniture.
        Street mode: header, desc (with inline weather + optional ambient sentences), things,
        furniture, characters, footer, then narrative exit prose at the bottom.
        Interior mode: header, optional ambient block (no climate), then the rest.
        """
        header = self.get_display_header(looker, **kwargs)
        desc = self.get_display_desc(looker, **kwargs)
        things = self.get_display_things(looker, **kwargs)
        furniture = self.get_display_furniture(looker, **kwargs)
        characters = self.get_display_characters(looker, **kwargs)
        footer = self.get_display_footer(looker, **kwargs)
        if self._is_street_mode():
            ambient = ""
        else:
            ambient = self.get_display_ambient(looker, **kwargs)

        if self._is_street_mode():
            narrative = self.get_display_narrative_exits(looker, **kwargs)
            head = "\n".join([p for p in (header, desc) if p])
            parts = [head]
            if things:
                parts.append(things)
            if furniture:
                parts.append(furniture)
            tail = "\n".join([p for p in (characters, footer) if p])
            if tail:
                parts.append(tail)
            # Narrative exit prose last — same role as mechanical exits on interior rooms
            if narrative:
                parts.append(narrative)
            appearance = "\n\n".join([p for p in parts if p])
            return self.format_appearance(appearance, looker, **kwargs)

        exits = self.get_display_exits(looker, **kwargs)
        # Format with intentional paragraph breaks:
        # - Header + desc (no blank line between), optional ambient, then major sections
        #   joined with blank lines (\n\n): things, furniture (if any), then characters/exits/footer.
        # - Characters, exits, footer stay in one sub-block (single newlines inside tail).
        head = "\n".join([p for p in (header, desc) if p])
        parts = [head]
        if ambient:
            parts.append(ambient)
        if things:
            parts.append(things)

        if furniture:
            parts.append(furniture)

        tail = "\n".join([p for p in (characters, exits, footer) if p])
        if tail:
            parts.append(tail)

        # Use blank lines between major sections.
        appearance = "\n\n".join([p for p in parts if p])
        return self.format_appearance(appearance, looker, **kwargs)

    def format_appearance(self, appearance, looker, **kwargs):
        """Allow one blank line between sections."""
        return compress_whitespace(appearance, max_linebreaks=2).strip()

    def get_display_header(self, looker, **kwargs):
        """Room name at top, colored to stand out."""
        name = self.get_display_name(looker, **kwargs)
        extra = self.get_extra_display_name_info(looker, **kwargs) or ""
        return f"{ROOM_DESC_ROOM_NAME_COLOR}{name}{extra}|n"

    def get_display_desc(self, looker, **kwargs):
        """Use our default if the room still has the stock Evennia welcome text."""
        raw = self._raw_display_desc_text(looker, **kwargs)
        if self._is_street_mode():
            return self._format_street_desc_body(raw, looker, **kwargs)
        return raw

    def _name_for_you_see(self, name):
        """Strip leading 'A ' / 'a ' so we can add our own article without 'a A foo'."""
        s = (name or "").strip()
        if s.lower().startswith("a "):
            s = s[2:].lstrip()
        return s or (name or "").strip()

    def _article(self, name):
        """Return 'a' or 'an' for the given noun (no leading article)."""
        n = (name or "").strip()
        if not n:
            return "a"
        return "an" if n[0].lower() in "aeiou" else "a"

    def get_display_things(self, looker, **kwargs):
        """
        Objects section: "You see a X, an Y and a Z." for objects (excluding vehicles and set-place items);
        then "A X is <pose>." for set-place objects; then "X is parked/idling here." for vehicles.
        No characters or furniture in this section.
        """
        # include_looker is a room-level flag; strip it before forwarding to object methods
        # that don't accept it (e.g. OperatingTable.get_display_name).
        kwargs = {k: v for k, v in kwargs.items() if k != "include_looker"}
        characters = self.filter_visible(
            self.contents_get(content_type="character"), looker, **kwargs
        )
        # Be defensive: only treat true Characters (avoid edge cases where non-characters slip in)
        try:
            from evennia.utils.utils import inherits_from
            characters = [c for c in characters if inherits_from(c, "typeclasses.characters.Character")]
        except Exception:
            pass
        # Corpses are objects, not character poses; show them in "You see" line only
        characters = [c for c in characters if not _is_corpse(c)]
        see_items = []
        set_place_objects = []
        vehicle_poses = []  # (obj, "is parked here." / "is idling here.")
        for obj in self.contents:
            if obj in characters or isinstance(obj, DefaultExit):
                continue
            if not self.filter_visible([obj], looker, **kwargs):
                continue
            if _is_corpse(obj):
                name = obj.get_display_name(looker, **kwargs)
                short = self._name_for_you_see(name).strip()
                article = self._article(short)
                see_items.append((f"{article} {ROOM_DESC_OBJECT_NAME_COLOR}{short}|n").strip())
                continue
            if _is_vehicle(obj):
                if _is_motorcycle_vehicle(obj):
                    rider = getattr(obj.db, "rider", None)
                    if rider and (
                        rider is looker
                        or self.filter_visible([rider], looker, **kwargs)
                    ):
                        see_items.append(
                            _riding_on_motorcycle_sentence(rider, obj, looker, **kwargs)
                        )
                        continue
                pose = "idling here." if getattr(obj, "engine_running", False) else "parked here."
                vehicle_poses.append((obj, pose))
                continue
            # Operating tables - skip here, handled in furniture section
            if _is_operating_table(obj):
                continue
            # Seats/beds - skip here, handled in furniture section
            if _is_seat(obj) or _is_bed(obj):
                continue
            room_pose = getattr(obj.db, "room_pose", None)
            if room_pose:
                pose = (room_pose or "").strip().rstrip(".")
                if pose:
                    set_place_objects.append((obj, pose))
                    continue
            name = obj.get_display_name(looker, **kwargs)
            short = self._name_for_you_see(name).strip()
            article = self._article(short)
            see_items.append((f"{article} {ROOM_DESC_OBJECT_NAME_COLOR}{short}|n").strip())
        you_see = ""
        if see_items:
            # Use sep="," so iter_to_str doesn't add extra space (sep in punctuation); result: "A, B and C"
            you_see = "You see " + iter_to_str(see_items, sep=",", endsep=" and") + "."
        object_pose_parts = []
        for obj, pose in set_place_objects:
            if pose:
                try:
                    from world.rpg.crafting import substitute_clothing_desc
                    pose = substitute_clothing_desc(pose, obj)
                except Exception:
                    pass
            name = obj.get_display_name(looker, **kwargs)
            short = self._name_for_you_see(name).strip()
            article = self._article(short).capitalize()
            # Do not force an 'is' here; let builders/players include it in the text if desired
            object_pose_parts.append(f"{article} {ROOM_DESC_OBJECT_NAME_COLOR}{short}|n {pose}.")
        vehicle_pose_parts = []
        for obj, pose in vehicle_poses:
            name = obj.get_display_name(looker, **kwargs)
            vehicle_pose_parts.append(f"{ROOM_DESC_OBJECT_NAME_COLOR}{name}|n is {pose}")
        parts = [you_see]
        if object_pose_parts:
            parts.append(" ".join(object_pose_parts))
        if vehicle_pose_parts:
            parts.append(" ".join(vehicle_pose_parts))
        return " ".join(filter(None, parts)).strip()

    def get_display_characters(self, looker, **kwargs):
        """
        Characters section: Shows character poses, including special states like
        sitting/lying (tracked but displayed in furniture section), grappled, on operating tables, etc.
        """
        include_looker = kwargs.get("include_looker", True)
        characters = self.filter_visible(
            self.contents_get(content_type="character"), looker, **kwargs
        )
        # Be defensive: only treat true Characters (avoid edge cases where non-characters slip in)
        try:
            from evennia.utils.utils import inherits_from
            characters = [c for c in characters if inherits_from(c, "evennia.objects.objects.DefaultCharacter")]
        except Exception:
            pass
        # Corpses are objects, not character poses; show them in "You see" line only
        characters = [c for c in characters if not _is_corpse(c)]
        mounted_set = {c for c in characters if getattr(c.db, "mounted_on", None)}
        # Looker may be omitted from `characters` (typeclass filter); still suppress "standing here".
        if looker and getattr(looker.db, "mounted_on", None):
            mounted_set.add(looker)
        try:
            from world.death import is_flatlined
        except ImportError:
            is_flatlined = lambda o: False
        # Patients lying on an operating table (db.lying_on_table = table; they stay in room)
        # Displayed in furniture section; here we just track so we can suppress normal poses.
        on_table = set()  # characters shown in "lying on table" so we skip them in normal poses
        for obj in self.contents:
            if not _is_operating_table(obj) or not self.filter_visible([obj], looker, **kwargs):
                continue
            for char in characters:
                if getattr(char.db, "lying_on_table", None) != obj:
                    continue
                if not self.filter_visible([char], looker, **kwargs):
                    continue
                on_table.add(char)
        # Track sitting/lying characters so we exclude them from normal character poses
        sitting_set = set()
        lying_set = set()
        for obj in self.contents:
            if not (_is_seat(obj) or _is_bed(obj)) or not self.filter_visible([obj], looker, **kwargs):
                continue
            # Just track which characters are sitting/lying (don't generate display here)
            for char in characters:
                if getattr(char.db, "sitting_on", None) == obj:
                    if self.filter_visible([char], looker, **kwargs):
                        sitting_set.add(char)
                elif getattr(char.db, "lying_on", None) == obj:
                    if self.filter_visible([char], looker, **kwargs):
                        lying_set.add(char)
        # Grappled: "X is locked in the grasp of Y"
        grappled_parts = []
        grappled_set = set()
        for char in characters:
            holder = getattr(char.db, "grappled_by", None)
            if not holder or not self.filter_visible([char, holder], looker, **kwargs):
                continue
            grappled_set.add(char)
            vname = _ic_room_char_name(char, looker, **kwargs)
            hname = _ic_room_char_name(holder, looker, **kwargs)
            grappled_parts.append(f"{vname} is locked in the grasp of {hname}.")
        char_pose_parts = []
        chars_to_show = list(characters)
        # Include looker if not already shown (helps you see your own @lp).
        # Some callers (like Photograph capture) want a third-person snapshot and will set include_looker=False.
        if include_looker:
            looker_shown = (
                looker in on_table
                or looker in sitting_set
                or looker in lying_set
                or looker in grappled_set
                or looker in mounted_set
            )
            if not looker_shown and looker not in chars_to_show:
                chars_to_show.append(looker)
        for char in chars_to_show:
            # If a character is sitting/lying/on a table, rely on the furniture/table display
            # instead of also showing a generic room pose (avoids "standing here" while seated/lying).
            if (
                char in on_table
                or char in sitting_set
                or char in lying_set
                or char in grappled_set
                or char in mounted_set
                or getattr(char.db, "sitting_on", None)
                or getattr(char.db, "lying_on", None)
                or getattr(char.db, "lying_on_table", None)
            ):
                continue
            try:
                if hasattr(self, "get_vehicle_interior_seat_line"):
                    seat_line = self.get_vehicle_interior_seat_line(char, looker, **kwargs)
                    if seat_line:
                        char_pose_parts.append(seat_line)
                        continue
            except Exception:
                pass
            logged_off = False
            is_dead = False
            if is_flatlined(char):
                # Flatlined characters always use an explicit "is" construction.
                is_dead = True
                pose = "lying here, dead."
            else:
                try:
                    logged_off = not (getattr(char, "sessions", None) and char.sessions.get())
                except Exception:
                    pass
                if getattr(char.db, "is_npc", False):
                    logged_off = False  # NPCs never show as sleeping when unpuppeted
                if logged_off:
                    try:
                        from world.death import is_character_multi_puppeted
                        if is_character_multi_puppeted(char):
                            logged_off = False  # Multi-puppeted = always "present" like NPCs
                    except Exception:
                        pass
                if logged_off:
                    pose = getattr(char.db, "sleep_place", None)
                    # Default fallback and legacy value ("sleeping here") both become "is sleeping here"
                    if not pose or pose.strip().lower() == "sleeping here":
                        pose = "is sleeping here"
                else:
                    # Temporary place (@tp) overrides normal @lp while set in this room.
                    temp_pose = getattr(char.db, "temp_room_pose", None)
                    if temp_pose:
                        pose = temp_pose
                    else:
                        # Default fallback: "is standing here" so the full line reads "Name is standing here."
                        pose = getattr(char.db, "room_pose", None)
                        if not pose or pose.strip().lower() == "standing here":
                            pose = "is standing here"
            pose = (pose or "").strip().rstrip(".")
            if pose:
                try:
                    from world.rpg.crafting import substitute_clothing_desc
                    pose = substitute_clothing_desc(pose, char)
                except Exception:
                    pass
                # Resolve mentions of the viewer in the pose text using the same
                # recog/sdesc logic as emotes: whatever name the poser would use
                # for the viewer (recog, helmet-recog, or sdesc) becomes "you/your".
                try:
                    from world.rp_features import get_display_name_for_viewer
                except ImportError:
                    get_display_name_for_viewer = None
                if get_display_name_for_viewer and looker:
                    try:
                        # This is the string the posing character would use for the viewer.
                        matched_name = (get_display_name_for_viewer(looker, char) or "").strip()
                    except Exception:
                        matched_name = ""
                    if matched_name:
                        # Use word-boundary-like matching that also works for hyphens/digits,
                        # mirroring the emote system's behavior.
                        pattern_base = r"(?<!\w)" + re.escape(matched_name) + r"(?!\w)"
                        pose = re.sub(pattern_base + r"'s", "your", pose, flags=re.IGNORECASE)
                        pose = re.sub(pattern_base, "you", pose, flags=re.IGNORECASE)
            name = _ic_room_char_name(char, looker, **kwargs)
            if char is not looker:
                try:
                    from world.rpg import stealth

                    if stealth._is_staff(looker) and stealth.is_hidden(char):
                        name = f"{name} |c[HIDDEN]|n"
                except Exception:
                    pass
            if char is looker:
                # Special handling so you see "You are ..." instead of "Name is ..."
                you_pose = pose
                if (you_pose or "").lower().startswith("is "):
                    you_pose = "are " + you_pose[3:]
                if logged_off:
                    char_pose_parts.append(f"You |b|w{you_pose}.|n")
                elif is_dead:
                    char_pose_parts.append(f"You are {you_pose}.")
                else:
                    char_pose_parts.append(f"You {you_pose}.")
            else:
                if logged_off:
                    # Name in character color; sleep-place text in bold white (caller controls verb, e.g. "is sleeping here")
                    char_pose_parts.append(f"{name} |b|w{pose}.|n")
                elif is_dead:
                    # Dead/flatlined: always "Name is <pose>."
                    char_pose_parts.append(f"{name} is {pose}.")
                else:
                    # For living, present characters, do not force an 'is' – use whatever the player set
                    # with @lp (e.g. 'is leaning against the wall', 'leaning against the wall', 'crouched here').
                    char_pose_parts.append(f"{name} {pose}.")
        char_pose_line = " ".join(char_pose_parts) if char_pose_parts else ""
        if grappled_parts:
            char_pose_line = " ".join(filter(None, [char_pose_line, " ".join(grappled_parts)]))
        return char_pose_line

    def at_object_receive(self, obj, source_location, move_type="move", **kwargs):
        """
        Called when an object enters this room. After the base handler runs,
        apply any configured smell effects (e.g. bad-smell tiles).

        Builder fields:
            db.room_faction_required — faction key (e.g. IMP); only members may enter.
            db.room_faction_min_rank — minimum rank (default 1).
        """
        try:
            fk = getattr(self.db, "room_faction_required", None)
            if fk:
                from evennia.objects.objects import DefaultCharacter

                if isinstance(obj, DefaultCharacter):
                    from world.rpg.factions import is_faction_member
                    from world.rpg.factions.membership import get_member_rank
                    from world.rpg.factions.doors import staff_bypass

                    if not staff_bypass(obj):
                        min_r = int(getattr(self.db, "room_faction_min_rank", None) or 1)
                        if not is_faction_member(obj, fk):
                            obj.msg("|rAccess denied. This area is restricted.|n")
                            if source_location and hasattr(obj, "move_to"):
                                obj.move_to(source_location, quiet=True)
                            return
                        if get_member_rank(obj, fk) < min_r:
                            obj.msg("|rAccess denied. Insufficient clearance.|n")
                            if source_location and hasattr(obj, "move_to"):
                                obj.move_to(source_location, quiet=True)
                            return
        except Exception:
            pass

        super().at_object_receive(obj, source_location, move_type=move_type, **kwargs)
        try:
            scripts = list(self.scripts.all())
        except Exception:
            scripts = []
        for scr in scripts:
            if getattr(scr, "key", "") == "bad_smell_room_script":
                try:
                    scr.at_object_receive(obj, source_location=source_location)
                except TypeError:
                    scr.at_object_receive(obj, source_location)

    def get_display_furniture(self, looker, **kwargs):
        """
        Furniture section: Seats/beds AND operating tables.
        Delegates to each furniture object's get_room_appearance() method when available,
        and also shows patients lying on operating tables.
        """
        # include_looker is a room-level flag; strip it before forwarding to object methods
        # that don't accept it (e.g. OperatingTable.get_display_name).
        kwargs = {k: v for k, v in kwargs.items() if k != "include_looker"}
        lines = []

        # Operating tables: show "X is lying on <table>." here so it groups with dive rigs/seats.
        characters = self.filter_visible(
            self.contents_get(content_type="character"), looker, **kwargs
        )
        for obj in self.contents:
            if not _is_operating_table(obj):
                continue
            if not self.filter_visible([obj], looker, **kwargs):
                continue
            table_name = obj.get_display_name(looker, **kwargs)
            any_patients = False
            for char in characters:
                if getattr(char.db, "lying_on_table", None) != obj:
                    continue
                if not self.filter_visible([char], looker, **kwargs):
                    continue
                any_patients = True
                name = _ic_room_char_name(char, looker, **kwargs)
                lines.append(
                    f"{name} is lying on {ROOM_DESC_OBJECT_NAME_COLOR}{table_name}|n."
                )
            if not any_patients:
                lines.append(f"The {ROOM_DESC_OBJECT_NAME_COLOR}{table_name}|n is waiting for a patient.")

        for obj in self.contents:
            if not (_is_seat(obj) or _is_bed(obj)):
                continue
            if not self.filter_visible([obj], looker, **kwargs):
                continue

            # Let the furniture object handle its own display
            if hasattr(obj, 'get_room_appearance'):
                appearance = obj.get_room_appearance(looker, **kwargs)
                if appearance:
                    lines.append(appearance)

        return " ".join(lines)

    def get_display_exits(self, looker, **kwargs):
        """Interior: grey prose stem; exit name dim; |w only on (alias). Street mode: no summary line."""
        if self._is_street_mode():
            return ""
        rows = self._visible_exit_rows(looker, **kwargs)
        if not rows:
            return ""
        bits = self._mechanical_exit_bits([(n, s) for _, n, s, _ in rows])
        return self._mechanical_exit_line_from_bits(bits)


# Floodgate passthrough rooms: `typeclasses.bulkhead_room.BulkheadRoom` (seal/unseal in `world.maps.bulkheads`).


class CityRoom(XYZRoom, Room):
    """
    Base room for city grid cells. Inherits XYZ coordinate tags from the contrib
    and full IC appearance from Room.
    """

    map_display = False

    def at_object_creation(self):
        super().at_object_creation()
        self.db.city_level = None
        self.db.district = None
        self.db.stealth_modifier = 0
        self.db.ambient_messages = []
        self.db.specimen_tags = []

    def get_display_desc(self, looker, **kwargs):
        desc = super().get_display_desc(looker, **kwargs)
        if not self.tags.has("lift_station"):
            return desc
        try:
            from evennia.utils.utils import inherits_from
            from typeclasses.freight_lift import FreightLift

            docked = False
            for exi in self.contents_get(content_type="exit"):
                dest = getattr(exi, "destination", None)
                if (
                    dest
                    and getattr(exi.db, "is_lift_exit", None)
                    and inherits_from(dest, FreightLift)
                ):
                    docked = True
                    break
            extra = (
                "\n\n|g[FREIGHT] A lift is docked here. Type |wboard|g to enter.|n"
                if docked
                else "\n\n|x[FREIGHT] The lift bay is empty. The lift is in transit.|n"
            )
            return (desc or "") + extra
        except Exception:
            return desc


class SlumRoom(CityRoom):
    """Top tier grid: largest footprint, lowest maintenance (mechanical tier, not lore name)."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.city_level = "slums"


class GuildRoom(CityRoom):
    """Second tier: industrial / guild-controlled."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.city_level = "guild"


class BourgeoisRoom(CityRoom):
    """Third tier: controlled, comfortable."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.city_level = "bourgeois"


class EliteRoom(CityRoom):
    """Bottom tier: smallest footprint, seat of power."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.city_level = "elite"


class AirRoom(CityRoom):
    """
    Open vertical space between levels. Entering without flying/climbing triggers a fall.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.city_level = "shaft"
        self.db.fall_damage_per_z = 8
        self.db.fall_destination = None
        self.db.is_air = True

    def at_object_receive(self, obj, source_location, move_type="move", **kwargs):
        super().at_object_receive(obj, source_location, move_type=move_type, **kwargs)
        if not hasattr(obj, "msg"):
            return
        try:
            from typeclasses.vehicles import AerialVehicle

            if isinstance(obj, AerialVehicle) or getattr(obj.db, "vehicle_type", None) == "aerial":
                return
        except Exception:
            pass
        from world.movement.falling import process_fall

        delay(0.5, process_fall, obj.id, self.id)


class GateMixin:
    """
    Sealable bulkhead behavior. Mix into a district room typeclass, or use `GateRoom`
    for a standalone gate cell on the same Z as that district.
    Set `db.city_level` to the district (slums, guild, bourgeois, elite) when building.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.gate_id = ""
        self.db.sealed = False
        self.db.seal_reason = ""
        self.db.connects_to = ""


class GateRoom(GateMixin, CityRoom):
    """
    Sealable bulkhead on a district Z. Lifts handle vertical travel; street↔gate↔freight
    are normal horizontal exits. Mark exits toward freight with `exit.db.gate_bulkhead = True`.
    """

    def return_appearance(self, looker, **kwargs):
        if getattr(self.db, "sealed", False):
            return self._sealed_appearance(looker)
        return super().return_appearance(looker, **kwargs)

    def _sealed_appearance(self, looker):
        reason = self.db.seal_reason or "unspecified"
        return (
            f"|r{'=' * 52}|n\n"
            f"  |RSEALED|n\n"
            f"|r{'=' * 52}|n\n\n"
            f"  The bulkhead is shut. Two feet of solid steel.\n"
            f"  The warning lights pulse red.\n\n"
            f"  |wSeal reason:|n {reason}\n"
            f"|r{'=' * 52}|n"
        )
