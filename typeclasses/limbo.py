"""
Death Lobby (Limbo): OOC waiting room for players who have permanently died.
Spirit: temporary puppet so the player has somewhere to "be" and can look around the lobby.
"""
from evennia import DefaultRoom, DefaultCharacter


class DeathLimbo(DefaultRoom):
    """
    A room that doesn't exist. Or does it? You're dead. This is the lobby.
    """
    def at_object_creation(self):
        self.db.desc = (
            "|yTHE DEATH LOBBY|n\n\n"
            "So. You died. Permanently. No defib, no last-minute save. Someone put you down, "
            "or time ran out while you were flatlined. Congratulations.\n\n"
            "You are in a featureless, softly lit space. There are no doors. There are no windows. "
            "There is only the faint hum of recycled air and the nagging sense that you are supposed to "
            "be filling out paperwork. A sign on one wall reads: |wPLEASE WAIT. A representative will "
            "assist you shortly. Estimated wait: ???|n\n\n"
            "Nobody has ever seen a representative. The chairs are uncomfortable. The magazines are from "
            "last decade. Welcome to the afterlife's waiting room. Make yourself at home. You have time."
        )


class Spirit(DefaultCharacter):
    """
    Disembodied spirit in the Death Lobby. One per account, reused.
    Uses SpiritCmdSet only (look, say, pose) to avoid duplicate 'l'/'look' matches.
    """
    def at_object_creation(self):
        self.db.desc = "A faint, slightly translucent presence. You. Or what's left of you."
        self.db.room_pose = "floating here with an expression of mild annoyance"
        self.cmdset.clear()
        self.cmdset.add("commands.spirit_cmdset.SpiritCmdSet")

    def get_display_desc(self, looker, **kwargs):
        return "A wisp of a form. You. Waiting."
