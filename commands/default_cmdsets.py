"""
Command sets

All commands in the game must be grouped in a cmdset.  A given command
can be part of any number of cmdsets and cmdsets can be added/removed
and merged onto entities at runtime.

To create new commands to populate the cmdset, see
`commands/command.py`.

This module wraps the default command sets of Evennia; overloads them
to add/remove commands from the default lineup. You can create your
own cmdsets by inheriting from them or directly from `evennia.CmdSet`.

"""

from evennia import default_cmds
from evennia.commands.cmdset import CmdSet
from evennia.commands.default.account import (
    CmdIC,
    CmdOOC,
    CmdCharCreate,
    CmdCharDelete,
)


class SplinterPodCmdSet(CmdSet):
    """
    Leave-pod (and pod-related) commands with priority above ExitCmdSet (101)
    so "done" works inside the pod instead of matching room exits.
    """
    key = "SplinterPod"
    priority = 110

    def at_cmdset_creation(self):
        from commands.command import CmdLeavePod
        self.add(CmdLeavePod())


class CharacterCmdSet(default_cmds.CharacterCmdSet):
    """
    The `CharacterCmdSet` contains general in-game commands like `look`,
    `get`, etc available on in-game Character objects.
    """
    key = "DefaultCharacter"

    def at_cmdset_creation(self):
        """
        Populates the cmdset. Player commands use cmd:all(); admin commands
        use perm(Builder) or perm(Admin) so only staff can run them.
        """
        super().at_cmdset_creation()

        from commands.command import (
            CmdStats, CmdAttack, CmdStance, CmdStop, CmdExecute, CmdGrapple, CmdLetGo, CmdResist, CmdDiagnose, CmdUse, CmdApply, CmdStabilize, CmdEat, CmdDrink, CmdWield, CmdUnwield, CmdFreehands, CmdInventory, CmdReload, CmdUnload, CmdCheckAmmo,
            CmdWear, CmdRemove, CmdStrip, CmdLoot, CmdFrisk, CmdGet, CmdTailor, CmdTease, CmdXp,
            CmdDescribeBodypart, CmdBody, CmdLookPlace, CmdSleepPlace, CmdWakeMsg, CmdSetPlace, CmdPose, CmdPronoun, CmdEmote, CmdNoMatch,
            CmdEmoteDebug, CmdSpawn, CmdDespawn, CmdGiveXp, CmdCreateItem, CmdTypeclasses, CmdSpawnVehicle, CmdSpawnMedical, CmdSpawnOR, CmdDefib,
            CmdSit, CmdLieOnTable, CmdGetOffTable, CmdSurgery,
            CmdStaffSheet, CmdStaffSetStat, CmdStaffSetSkill, CmdMakeNpc, CmdNpcSet, CmdGoto, CmdSummon,
            CmdSetVoid, CmdVoid, CmdRelease, CmdBoot, CmdFind, CmdAnnounce, CmdRestore, CmdDebugKill,
            CmdSpawnSeat, CmdSpawnBed, CmdSpawnPod,
            CmdEnterPod, CmdSplinterMe,
            CmdEnterVehicle, CmdExitVehicle, CmdStartEngine, CmdStopEngine, CmdShutoffEngine, CmdDrive, CmdStartEngine, CmdStopEngine, CmdShutoffEngine, CmdDrive,
            CmdVehicleStatus, CmdRepairPart,             CmdDamageVehicle,
            CmdExamine,
        )
        from commands.builder_commands import (
            CmdTag, CmdHere, CmdListCmds, CmdCloneSpawn, CmdDig, CmdDesc,
            CmdSetAttr, CmdName, CmdOpen, CmdDestroy,
        )
        try:
            from evennia.commands.default.general import CmdGet as DefaultCmdGet
        except ImportError:
            DefaultCmdGet = None

        # --- Player commands (everyone) ---
        self.add(CmdStats())
        self.add(CmdAttack())
        self.add(CmdStop())
        self.add(CmdExecute())
        self.add(CmdStance())
        self.add(CmdDiagnose())
        self.add(CmdUse())
        self.add(CmdApply())
        self.add(CmdStabilize())
        self.add(CmdGrapple())
        self.add(CmdLetGo())
        self.add(CmdResist())
        self.add(CmdSit())
        self.add(CmdLieOnTable())
        self.add(CmdGetOffTable())
        self.add(CmdSurgery())
        self.add(CmdEat())
        self.add(CmdDrink())
        self.add(CmdDefib())
        self.add(CmdWield())
        self.add(CmdUnwield())
        self.add(CmdFreehands())
        self.add(CmdInventory())
        self.add(CmdReload())
        self.add(CmdUnload())
        self.add(CmdCheckAmmo())
        self.add(CmdWear())
        self.add(CmdRemove())
        self.add(CmdStrip())
        self.add(CmdLoot())
        self.add(CmdFrisk())
        if DefaultCmdGet is not None:
            self.remove(DefaultCmdGet)
            self.add(CmdGet())
        self.add(CmdTailor())
        self.add(CmdTease())
        self.add(CmdXp())
        self.add(CmdDescribeBodypart())
        self.add(CmdBody())
        self.add(CmdLookPlace())
        self.add(CmdSleepPlace())
        self.add(CmdWakeMsg())
        self.add(CmdSetPlace())
        self.add(CmdPose())
        self.add(CmdPronoun())
        self.add(CmdEmote())
        self.add(CmdNoMatch())
        self.add(CmdExamine())
        self.add(CmdTag())
        self.add(CmdHere())
        self.add(CmdListCmds())
        self.add(CmdCloneSpawn())
        self.add(CmdDig())
        self.add(CmdDesc())
        self.add(CmdSetAttr())
        self.add(CmdName())
        self.add(CmdOpen())
        self.add(CmdDestroy())
        self.add(CmdEnterPod())
        self.add(CmdSplinterMe())
        self.add(SplinterPodCmdSet())  # CmdLeavePod here so it beats exits (priority 110)
        self.add(CmdEnterVehicle())
        self.add(CmdExitVehicle())
        self.add(CmdStartEngine())
        self.add(CmdStopEngine())
        self.add(CmdShutoffEngine())
        self.add(CmdDrive())
        self.add(CmdVehicleStatus())
        self.add(CmdRepairPart())

        # --- Admin commands (Builder/Admin only; locked in command class) ---
        self.add(CmdEmoteDebug())
        self.add(CmdSpawn())
        self.add(CmdDespawn())
        self.add(CmdGiveXp())
        self.add(CmdCreateItem())
        self.add(CmdTypeclasses())
        self.add(CmdSpawnVehicle())
        self.add(CmdDamageVehicle())
        self.add(CmdSpawnMedical())
        self.add(CmdSpawnOR())
        self.add(CmdStaffSheet())
        self.add(CmdStaffSetStat())
        self.add(CmdStaffSetSkill())
        self.add(CmdMakeNpc())
        self.add(CmdNpcSet())
        self.add(CmdGoto())
        self.add(CmdSummon())
        self.add(CmdSetVoid())
        self.add(CmdVoid())
        self.add(CmdRelease())
        self.add(CmdBoot())
        self.add(CmdFind())
        self.add(CmdAnnounce())
        self.add(CmdRestore())
        self.add(CmdDebugKill())
        self.add(CmdSpawnSeat())
        self.add(CmdSpawnBed())
        self.add(CmdSpawnPod())

class AdminOnlyIC(CmdIC):
    """IC/puppet: staff only (one character per account for players)."""
    locks = "cmd:perm(Builder)"


class AdminOnlyOOC(CmdOOC):
    """OOC/unpuppet: staff only (players stay in their single character)."""
    locks = "cmd:perm(Builder)"


class StaffCharCreate(CmdCharCreate):
    """Character creation: staff only (players get one character at account creation)."""
    locks = "cmd:perm(Builder)"


class StaffCharDelete(CmdCharDelete):
    """Character deletion: staff only."""
    locks = "cmd:perm(Builder)"


class AccountCmdSet(default_cmds.AccountCmdSet):
    """
    This is the cmdset available to the Account at all times. It is
    combined with the `CharacterCmdSet` when the Account puppets a
    Character. It holds game-account-specific commands, channel
    commands, etc.

    One character per account: ic/ooc/charcreate/chardelete are Builder-only.
    """

    key = "DefaultAccount"

    def at_cmdset_creation(self):
        """
        Populates the cmdset. Replace default ic/ooc/charcreate/chardelete
        with staff-only versions so regular players cannot switch character
        or create more than the single auto-created one.
        """
        super().at_cmdset_creation()
        self.remove(CmdIC)
        self.add(AdminOnlyIC())
        self.remove(CmdOOC)
        self.add(AdminOnlyOOC())
        self.remove(CmdCharCreate)
        self.add(StaffCharCreate())
        self.remove(CmdCharDelete)
        self.add(StaffCharDelete())
        from commands.command import CmdStats, CmdGoLight, CmdGoShard
        self.add(CmdStats())
        self.add(CmdGoLight())
        self.add(CmdGoShard())


class UnloggedinCmdSet(default_cmds.UnloggedinCmdSet):
    """
    Command set available to the Session before being logged in.  This
    holds commands like creating a new account, logging in, etc.
    """

    key = "DefaultUnloggedin"

    def at_cmdset_creation(self):
        """
        Populates the cmdset
        """
        super().at_cmdset_creation()
        #
        # any commands you add below will overload the default ones.
        #


class SessionCmdSet(default_cmds.SessionCmdSet):
    """
    This cmdset is made available on Session level once logged in. It
    is empty by default.
    """

    key = "DefaultSession"

    def at_cmdset_creation(self):
        """
        This is the only method defined in a cmdset, called during
        its creation. It should populate the set with command instances.

        As and example we just add the empty base `Command` object.
        It prints some info.
        """
        super().at_cmdset_creation()
        #
        # any commands you add below will overload the default ones.
        #
