"""
Perfume and bad-smell helpers.

Perfume bottles are simple items you can 'use perfume' with to apply a temporary
scent overlay and Charisma bonus via world.smell, for testing and gameplay.
"""

import time
from evennia.utils.create import create_object

from typeclasses.items import Item


class Perfume(Item):
    """
    A small bottle of perfume or cologne.

    Attributes (db.*):
      - scent_phrase: base phrase for this perfume (e.g. "intoxicating" or "like ozone and rain").
      - move_suffix: optional full movement suffix; if blank, generated from scent_phrase.
                     Example: "who smells intoxicating".
      - smell_suffix: optional extra line appended to smell output; if blank, generated
                      from scent_phrase. Example: "A faint aura of intoxicating perfume clings to them."
      - lore: optional flavor text shown on examine.
    """

    def at_object_creation(self):
        super().at_object_creation()
        if self.db.scent_phrase is None:
            self.db.scent_phrase = "intoxicating"
        if self.db.move_suffix is None:
            self.db.move_suffix = ""
        if self.db.smell_suffix is None:
            self.db.smell_suffix = ""
        if self.db.lore is None:
            self.db.lore = "A small, matte-black bottle of perfume from the Shard's underlevels."

    def at_use(self, user):
        """
        Called by the PerfumeUse command when a player uses the perfume.
        Applies a temporary scent overlay for ~3 hours and a Charisma bonus.
        """
        from world.smell import PERFUME_DURATION_SECS
        from world.buffs import PerfumeBuff

        now = time.time()
        phrase = (self.db.scent_phrase or "intoxicating").strip()
        # Movement suffix: default "who smells <phrase>"
        move_suffix = (self.db.move_suffix or "").strip()
        if not move_suffix:
            lower = phrase.lower()
            if lower.startswith(("like ", "of ", "smelling ", "smelling of ", "smells ", "who ")):
                move_suffix = "who " + phrase
            else:
                move_suffix = "who smells " + phrase
        user.db.smell_move_suffix = move_suffix

        # Smell-command suffix: default full sentence
        smell_suffix = (self.db.smell_suffix or "").strip()
        if not smell_suffix:
            smell_suffix = f"A faint aura of {phrase} clings to them."
        user.db.smell_smell_suffix = smell_suffix

        # Common expiry (for smell text overlays)
        user.db.smell_scent_until = now + PERFUME_DURATION_SECS

        # Mechanical Charisma bonus is handled via the buff system; does not
        # touch stored stats or XP.
        if hasattr(user, "buffs"):
            try:
                user.buffs.add(PerfumeBuff)
            except Exception:
                pass

        user.msg(f"|gYou apply {self.get_display_name(user)}.|n A faint aura of |w{phrase}|n clings to you.")
        if self.location == user:
            # Default: one-shot bottle; customize as desired.
            self.delete()


def spawn_example_perfume(caller):
    """
    Helper for staff/testing: spawn a lore-fitting perfume bottle into caller's inventory.
    """
    bottle = create_object(
        "typeclasses.perfume.Perfume",
        key="Colony Intoxicant No. 7",
        location=caller,
    )
    bottle.db.scent_phrase = "intoxicating"
    bottle.db.desc = (
        "A squat, matte-black bottle with a cracked holo-label reading "
        "|wINTX-7|n. The scent inside is sharp and sweet at once."
    )
    return bottle

