"""
Cmdset for Spirit (death limbo puppet). Only look, say, pose so we don't duplicate
with Account cmdset and avoid "More than one match for 'l'" when puppeting the Spirit.
"""
from evennia import default_cmds
from evennia.commands.default.general import CmdLook, CmdSay
from commands.command import CmdPose, CmdGoShard, CmdGoLight


class SpiritCmdSet(default_cmds.CmdSet):
    """Spirit in Death Lobby: look, say, pose, go shard (if clone), go light."""
    key = "SpiritCmdSet"
    priority = 2  # Higher than Character so only one look when merged

    def at_cmdset_creation(self):
        self.add(CmdLook())
        self.add(CmdSay())
        self.add(CmdPose())
        self.add(CmdGoShard())
        self.add(CmdGoLight())
