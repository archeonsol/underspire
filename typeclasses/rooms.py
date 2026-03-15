"""
Room

Rooms are simple containers that has no location of their own.
Look output: room name (colored), desc, "You see a X, a Y and a Z.", character poses, exits.
"""

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


class Room(ObjectParent, DefaultRoom):
    """
    Rooms are like any Object, except their location is None
    (which is default). Look output: room name (colored), desc, "You see a X, a Y.",
    character/vehicle/corpse poses, then "There are exits to the north (n), ...".
    """

    # In-character, non-descript default when room has no custom desc
    default_description = "A place. Nothing much to note."

    # Order: room name (header), desc, blank line, characters+things (you see + poses), exits
    appearance_template = """
{header}
{desc}

{characters}
{things}
{exits}
{footer}"""

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

    def get_display_characters(self, looker, **kwargs):
        """
        "You see a X, an Y and a Z." for objects (excluding vehicles and set-place items);
        then "A X is <pose>." for set-place objects; then "X is parked/idling here." for vehicles.
        Characters on a separate line. No vehicles in "You see" list.
        """
        characters = self.filter_visible(
            self.contents_get(content_type="character"), looker, **kwargs
        )
        # Corpses are objects, not character poses; show them in "You see" line only
        characters = [c for c in characters if not _is_corpse(c)]
        try:
            from world.death import is_flatlined
        except ImportError:
            is_flatlined = lambda o: False
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
            object_pose_parts.append(f"{article} {ROOM_DESC_OBJECT_NAME_COLOR}{short}|n is {pose}.")
        vehicle_pose_parts = []
        for obj, pose in vehicle_poses:
            name = obj.get_display_name(looker, **kwargs)
            vehicle_pose_parts.append(f"{ROOM_DESC_OBJECT_NAME_COLOR}{name}|n is {pose}")
        first_para_parts = [you_see]
        if object_pose_parts:
            first_para_parts.append(" ".join(object_pose_parts))
        if vehicle_pose_parts:
            first_para_parts.append(" ".join(vehicle_pose_parts))
        first_para = " ".join(filter(None, first_para_parts)).strip()
        char_pose_parts = []
        for char in characters:
            logged_off = False
            if is_flatlined(char):
                pose = "lying here, dead."
            else:
                try:
                    logged_off = not (getattr(char, "sessions", None) and char.sessions.get())
                except Exception:
                    pass
                if logged_off:
                    pose = getattr(char.db, "sleep_place", None) or "sleeping here"
                else:
                    pose = getattr(char.db, "room_pose", None) or "standing here"
            pose = (pose or "").strip().rstrip(".")
            if pose:
                try:
                    from world.crafting import substitute_clothing_desc
                    pose = substitute_clothing_desc(pose, char)
                except Exception:
                    pass
            name = char.get_display_name(looker, **kwargs)
            if logged_off:
                # Name in character color; "is sleeping here" in bold white
                char_pose_parts.append(f"{ROOM_DESC_CHARACTER_NAME_COLOR}{name}|n |b|wis {pose}.|n")
            else:
                char_pose_parts.append(f"{ROOM_DESC_CHARACTER_NAME_COLOR}{name}|n is {pose}.")
        char_pose_line = " ".join(char_pose_parts) if char_pose_parts else ""
        parts = []
        if first_para:
            parts.append(first_para)
        if char_pose_line:
            parts.append(char_pose_line)
        if not parts:
            return ""
        return "\n\n".join(parts)

    def get_display_things(self, looker, **kwargs):
        """Unused; objects and poses are in get_display_characters."""
        return ""

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
        bits = []
        for exi in exits:
            name = (exi.key or "out").strip()
            raw_aliases = getattr(exi, "aliases", None)
            if hasattr(raw_aliases, "all"):
                aliases = list(raw_aliases.all())
            else:
                aliases = raw_aliases if isinstance(raw_aliases, (list, tuple)) else []
            short = (aliases[0].strip() if aliases else name[0].lower()) if aliases else name[0].lower()
            bits.append(f"{ROOM_DESC_EXIT_NAME_COLOR}{name} ({short})|n")
        return "There are exits to the " + iter_to_str(bits, sep=", ", endsep=" and ") + "."
