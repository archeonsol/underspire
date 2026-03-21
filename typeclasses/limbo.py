"""
Death Lobby (Limbo): OOC waiting room for players who have permanently died.
Spirit: temporary puppet so the player has somewhere to "be" and can look around the lobby.
"""
from evennia import DefaultRoom, DefaultCharacter
from django.utils.translation import gettext as _


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
    Uses SpiritCmdSet only (look, say, pose, go light; go shard if corpse or account has shard data).
    """
    def at_object_creation(self):
        self.db.desc = "A faint, slightly translucent presence. You. Or what's left of you."
        self.db.room_pose = "floating here with an expression of mild annoyance"
        self.cmdset.clear()
        self.cmdset.add("commands.spirit_cmdset.SpiritCmdSet")
        try:
            self.locks.add("puppet:all()")
        except Exception:
            pass

    @property
    def has_spirit_puppet(self):
        """True when this is the Spirit (death lobby). Used so go light / go shard are only available in limbo."""
        return True

    @property
    def account_has_clone(self):
        """True if corpse has a shard or account has clone_snapshot_backup. Used by CmdGoShard lock."""
        acc = getattr(self, "account", None)
        if not acc or not getattr(acc, "db", None):
            return False
        corpse = getattr(acc.db, "dead_character_corpse", None)
        if corpse and getattr(corpse, "db", None) and getattr(corpse.db, "clone_snapshot", None):
            return True
        return bool(getattr(acc.db, "clone_snapshot_backup", None))

    def at_post_puppet(self, **kwargs):
        """Skip the default 'You become X' message; do look and room announcement only."""
        if hasattr(self, "account") and self.account:
            self.account.db._last_puppet = self
        if self.location:
            self.msg((self.at_look(self.location), {"type": "look"}), options=None)
            from evennia.utils import _ as _translate
            self.location.for_contents(
                lambda obj, from_obj: obj.msg(_("{name} has entered the game.").format(name=self.get_display_name(obj)), from_obj=from_obj),
                exclude=[self],
                from_obj=self,
            )

    def get_cmdsets(self, caller, current, **kwargs):
        """Never return None for current so the cmdset merger does not crash."""
        cur = self.cmdset.current
        stack = list(self.cmdset.cmdset_stack)
        if cur is None:
            from evennia.commands.cmdset import CmdSet
            cur = CmdSet()
        return cur, stack

    def get_display_desc(self, looker, **kwargs):
        return "A wisp of a form. You. Waiting."
