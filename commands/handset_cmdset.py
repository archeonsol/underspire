from evennia.commands.cmdset import CmdSet


class HandsetCmdSet(CmdSet):
    """
    Commands available on a handset item when carried.
    """

    key = "HandsetCmdSet"
    priority = 5
    mergetype = "Union"
    no_exits = True
    no_objs = False
    no_channels = False

    def at_cmdset_creation(self):
        from commands.handset_cmds import CmdHandset

        self.add(CmdHandset())

