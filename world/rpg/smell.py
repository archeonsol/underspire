"""
Smell system helpers.

Each object (characters, rooms, items) may define:
  - db.smell: base smell text (e.g. "like engine grease")

Characters can also have:
  - db.perfume_smell: temporary perfume scent (overrides base while active)

Rooms can define:
  - db.smell: ambient room smell when you 'smell' the room itself.
  - tag 'smell_override' (category 'smell'): if present and db.smell is set,
    the room's smell temporarily overrides personal/perfume smells for
    characters standing in the room.
"""

from typing import Optional
import time

from world.rpg.xp import _stat_display_level
from evennia.scripts.scripts import DefaultScript


def _clean(text: Optional[str]) -> str:
    if not text:
        return ""
    return str(text).strip()


CHARISMA_THRESHOLD_FOR_SMELL = 75  # display-level Charisma needed to use custom @smell text
PERFUME_DURATION_SECS = 3 * 60 * 60  # ~3 hours
PERFUME_CHARISMA_BONUS = 5
BAD_SMELL_CHARISMA_PENALTY = -5


def get_object_smell(obj) -> str:
    """
    Return the base smell string for any object, or '' if none.
    This is the raw db.smell text without any leading words.
    """
    if not obj or not hasattr(obj, "db"):
        return ""
    return _clean(getattr(obj.db, "smell", None))


def _now() -> float:
    return time.time()


def get_effective_charisma_display(character) -> int:
    """
    Return effective Charisma display including temporary modifiers (buffs).

    Base: world.rpg.xp._stat_display_level(character, "charisma") -> 0–150
    Buffs:
      - Routed through the character's BuffHandler (character.buffs) using the
        'charisma_display' stat identifier. See world.buffs.PerfumeBuff,
        world.buffs.BadSmellBuff for examples.
    """
    if not character:
        return 0
    base = int(_stat_display_level(character, "charisma") or 0)
    if hasattr(character, "buffs"):
        try:
            total = int(character.buffs.check(base, "charisma_display"))
        except Exception:
            total = base
    else:
        total = base
    total = max(0, min(150, total))
    return total


def _effect_active_until(character) -> float:
    """
    Return the common expiry timestamp for smell effects (0 if none).
    Currently uses character.db.smell_scent_until.
    """
    if not character or not hasattr(character, "db"):
        return 0.0
    try:
        until = float(getattr(character.db, "smell_scent_until", 0) or 0)
    except Exception:
        until = 0.0
    if until and until < _now():
        return 0.0
    return until


def get_smell_for(obj) -> str:
    """
    Public entry point: get the effective smell string for any non-character object.
    Characters have custom logic in format_smell_line; here we only handle rooms/items.
    """
    if not obj:
        return ""
    return get_object_smell(obj)


def get_move_sdesc_suffix(character) -> str:
    """
    Calculates suffix on the fly for movement lines. No need to store the
    formatted 'who smells ...' text in the DB.
    """
    if _effect_active_until(character) <= 0:
        return ""

    # Manual override takes precedence.
    suffix = _clean(getattr(character.db, "smell_move_suffix", None))
    if suffix:
        return suffix

    # Generate on the fly from the core phrase.
    phrase = _clean(getattr(character.db, "smell_scent_phrase", "like rot"))
    if not phrase:
        return ""
    lower = phrase.lower()
    # Only treat phrases that already start with "who " as complete; everything else
    # should read "who smells <phrase>" so we don't get "who like rot ...".
    if lower.startswith("who "):
        return phrase
    return f"who smells {phrase}"


def get_smell_append_text(character) -> str:
    """
    Calculates the full sentence to append to 'smell' command output on the fly.
    """
    if _effect_active_until(character) <= 0:
        return ""

    suffix = _clean(getattr(character.db, "smell_smell_suffix", None))
    if suffix:
        return suffix

    phrase = _clean(getattr(character.db, "smell_scent_phrase", "rot"))
    return f"A cloying stench of {phrase} hangs about them."


def format_smell_line(obj, viewer=None, prefix_name: Optional[str] = None) -> Optional[str]:
    """
    Build a one-line message describing how an object smells when someone
    explicitly uses the 'smell' command.

    prefix_name: optionally supply the already-resolved display name for obj.
    Returns None if there is no notable smell.
    """
    # Characters have special handling: @smell text, charisma gating, perfume/room overlays.
    from evennia import DefaultCharacter

    is_char = isinstance(obj, DefaultCharacter) or getattr(obj, "has_account", False) or bool(
        getattr(getattr(obj, "db", None), "is_npc", False)
    )

    name = prefix_name
    if not name:
        try:
            from world.rp_features import get_display_name_for_viewer

            if viewer is not None:
                name = get_display_name_for_viewer(obj, viewer)
            else:
                name = getattr(obj, "key", None) or "It"
        except Exception:
            name = getattr(obj, "key", None) or "It"

    # Character: use their personal @smell text only if charisma high enough.
    if is_char:
        eff_cha = get_effective_charisma_display(obj)
        base_text = _clean(getattr(obj.db, "smell_text", None))
        lines = []

        if eff_cha < CHARISMA_THRESHOLD_FOR_SMELL or not base_text:
            # Generic fallback for low-charisma or unset @smell.
            if viewer is not None and (viewer == obj or name == "You"):
                lines.append("You smell just fine, maybe a little off.")
            else:
                lines.append(f"{name} smells just fine, maybe a little off.")
        else:
            lines.append(base_text)

        # Optional perfume/room overlay line based on configured smell suffix.
        append = get_smell_append_text(obj)
        if append:
            lines.append(append)

        return " ".join(lines).strip() if lines else None

    # Non-character object/room: simple "X smells Y."
    smell = get_smell_for(obj)
    if not smell:
        return None
    return f"{name} smells {smell}."


class BadSmellRoomScript(DefaultScript):
    """
    Script to tag characters with a lingering bad smell when they move through
    a location. Attach to smelly rooms and configure chance/phrase.

    Attributes (db.*):
      - bad_scent_phrase: phrase for sdesc/overlay (default: "like rot and cheap solvent").
      - chance: 0.0–1.0 float chance per entry/move (default 0.35).
      - duration: seconds the smell lingers (default PERFUME_DURATION_SECS).
    """

    def at_script_creation(self):
        self.key = "bad_smell_room_script"
        self.persistent = True
        if self.db.bad_scent_phrase is None:
            self.db.bad_scent_phrase = "like rot and cheap solvent"
        # Optional explicit suffixes; if blank, helpers will synthesize from bad_scent_phrase
        if self.db.move_suffix is None:
            self.db.move_suffix = ""
        if self.db.smell_suffix is None:
            self.db.smell_suffix = ""
        if self.db.chance is None:
            self.db.chance = 0.35
        if self.db.duration is None:
            self.db.duration = PERFUME_DURATION_SECS

    def at_object_receive(self, character, source_location, **kwargs):
        """
        Called whenever something moves into the room this script is attached to.
        Roll once; on success, apply a bad-smell overlay and -Charisma modifier.
        """
        from evennia import DefaultCharacter
        import random
        from world.buffs import BadSmellBuff

        if not isinstance(character, DefaultCharacter) or random.random() > float(self.db.chance or 0.0):
            return

        phrase = (self.db.bad_scent_phrase or "like rot and cheap solvent").strip()
        now = time.time()
        duration = float(self.db.duration or PERFUME_DURATION_SECS)

        # Core data for smell overlays; helpers compute display strings.
        character.db.smell_scent_phrase = phrase
        character.db.smell_scent_until = now + duration

        # Optional manual overrides from the room script.
        if _clean(getattr(self.db, "move_suffix", None)):
            character.db.smell_move_suffix = self.db.move_suffix
        if _clean(getattr(self.db, "smell_suffix", None)):
            character.db.smell_smell_suffix = self.db.smell_suffix

        # Mechanical Charisma penalty via buff system.
        if hasattr(character, "buffs"):
            try:
                character.buffs.add(BadSmellBuff, duration=duration)
            except Exception:
                pass

        # Slight delay so the arrival/room description prints first, then the smell.
        try:
            from evennia.utils import delay as _delay

            _delay(0.1, character.msg, f"|rThe air clings to you, leaving you smelling {phrase}.|n")
        except Exception:
            character.msg(f"|rThe air clings to you, leaving you smelling {phrase}.|n")
