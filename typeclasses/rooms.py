"""
Room

Rooms are simple containers that has no location of their own.
Look output: room name (colored), desc, "You see a X, a Y and a Z.", character poses, exits.
"""

import re
from evennia.objects.objects import DefaultRoom, DefaultExit
from evennia.utils.utils import compress_whitespace, iter_to_str

from .objects import ObjectParent


# Substring that indicates the stock Evennia welcome desc (replace with our default)
_DEFAULT_WELCOME_MARKER = "evennia.com"

# Xterm256 colors for room contents (|### = RGB each 0-5; |n resets)
ROOM_DESC_ROOM_NAME_COLOR = "|050"        # green – room name at top
ROOM_DESC_CHARACTER_NAME_COLOR = "|520"   # warm orange/amber
ROOM_DESC_OBJECT_NAME_COLOR = "|035"      # teal/cyan – objects in "You see"
ROOM_DESC_EXIT_NAME_COLOR = "|050"        # green – exit names and shortcuts


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


class Room(ObjectParent, DefaultRoom):
    """
    Rooms are like any Object, except their location is None
    (which is default). Look output: room name (colored), desc, "You see a X, a Y.",
    character/vehicle/corpse poses, then "There are exits to the north (n), ...".
    """

    # In-character, non-descript default when room has no custom desc
    default_description = "A place. Nothing much to note."

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

    # Order: room name (header), desc, blank line, objects (you see), furniture (seats/beds), characters (poses), exits
    appearance_template = """
{header}
{desc}

{things}
{furniture}
{characters}
{exits}
{footer}"""

    def return_appearance(self, looker, **kwargs):
        """
        Override to explicitly call all display methods including furniture.
        """
        appearance = self.appearance_template.format(
            header=self.get_display_header(looker, **kwargs),
            desc=self.get_display_desc(looker, **kwargs),
            things=self.get_display_things(looker, **kwargs),
            furniture=self.get_display_furniture(looker, **kwargs),
            characters=self.get_display_characters(looker, **kwargs),
            exits=self.get_display_exits(looker, **kwargs),
            footer=self.get_display_footer(looker, **kwargs),
        )
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
        desc = self.db.desc or ""
        if not desc:
            return self.default_description
        if _DEFAULT_WELCOME_MARKER.lower() in desc.lower():
            return self.default_description
        return desc

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
                pose = "idling here." if getattr(obj, "engine_running", False) else "parked here."
                vehicle_poses.append((obj, pose))
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
                    from world.crafting import substitute_clothing_desc
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
        try:
            from world.death import is_flatlined
        except ImportError:
            is_flatlined = lambda o: False
        # Patients lying on an operating table (db.lying_on_table = table; they stay in room)
        table_pose_parts = []
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
                name = char.get_display_name(looker, **kwargs)
                table_name = obj.get_display_name(looker, **kwargs)
                table_pose_parts.append(f"{ROOM_DESC_CHARACTER_NAME_COLOR}{name}|n is lying on {ROOM_DESC_OBJECT_NAME_COLOR}{table_name}|n.")
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
            vname = char.get_display_name(looker, **kwargs)
            hname = holder.get_display_name(looker, **kwargs)
            grappled_parts.append(f"{ROOM_DESC_CHARACTER_NAME_COLOR}{vname}|n is locked in the grasp of {ROOM_DESC_CHARACTER_NAME_COLOR}{hname}|n.")
        char_pose_parts = []
        # Include looker if not already shown (helps you see your own @lp)
        looker_shown = looker in on_table or looker in sitting_set or looker in lying_set or looker in grappled_set
        chars_to_show = list(characters)
        if not looker_shown and looker not in chars_to_show:
            chars_to_show.append(looker)
        for char in chars_to_show:
            if char in on_table or char in sitting_set or char in lying_set or char in grappled_set:
                continue
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
                    from world.crafting import substitute_clothing_desc
                    pose = substitute_clothing_desc(pose, char)
                except Exception:
                    pass
                # Resolve simple name mentions in pose for viewer: if pose contains the looker's
                # key, show "you/your" for that viewer instead of their name.
                try:
                    viewer_name = (getattr(looker, "key", None) or "").strip()
                    if viewer_name:
                        pose = re.sub(rf"\b{re.escape(viewer_name)}'s\b", "your", pose)
                        pose = re.sub(rf"\b{re.escape(viewer_name)}\b", "you", pose)
                except Exception:
                    pass
            name = char.get_display_name(looker, **kwargs)
            if logged_off:
                # Name in character color; sleep-place text in bold white (caller controls verb, e.g. "is sleeping here")
                char_pose_parts.append(f"{ROOM_DESC_CHARACTER_NAME_COLOR}{name}|n |b|w{pose}.|n")
            elif is_dead:
                # Dead/flatlined: always "Name is <pose>."
                char_pose_parts.append(f"{ROOM_DESC_CHARACTER_NAME_COLOR}{name}|n is {pose}.")
            else:
                # For living, present characters, do not force an 'is' – use whatever the player set
                # with @lp (e.g. 'is leaning against the wall', 'leaning against the wall', 'crouched here').
                char_pose_parts.append(f"{ROOM_DESC_CHARACTER_NAME_COLOR}{name}|n {pose}.")
        char_pose_line = " ".join(char_pose_parts) if char_pose_parts else ""
        if grappled_parts:
            char_pose_line = " ".join(filter(None, [char_pose_line, " ".join(grappled_parts)]))
        if table_pose_parts:
            char_pose_line = " ".join(filter(None, [char_pose_line, " ".join(table_pose_parts)]))
        return char_pose_line

    def at_object_receive(self, obj, source_location, move_type="move", **kwargs):
        """
        Called when an object enters this room. After the base handler runs,
        apply any configured smell effects (e.g. bad-smell tiles).
        """
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
        Furniture section: Seats/beds display.
        Delegates to each furniture object's get_room_appearance() method.
        """
        lines = []
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
        """There are exits to the north (n), south (s). – exit names and shortcuts colored."""
        exits = self.filter_visible(self.contents_get(content_type="exit"), looker, **kwargs)
        if not exits:
            return ""
        exit_order = kwargs.get("exit_order")
        if exit_order:
            sort_index = {str(n).strip().lower(): i for i, n in enumerate(exit_order)}
            exits = sorted(exits, key=lambda e: sort_index.get((e.key or "").strip().lower(), 999))
        else:
            exits = sorted(exits, key=lambda e: (e.key or "").lower())
        seen = set()
        bits = []
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
            bit = f"{ROOM_DESC_EXIT_NAME_COLOR}{name} ({short})|n"
            bits.append(bit.strip())
        if not bits:
            return ""
        if len(bits) == 1:
            line = "There are exits to the " + bits[0] + "."
        elif len(bits) == 2:
            line = "There are exits to the " + bits[0] + " and " + bits[1] + "."
        else:
            line = "There are exits to the " + ", ".join(bits[:-1]) + " and " + bits[-1] + "."
        return re.sub(r"  +", " ", line)
