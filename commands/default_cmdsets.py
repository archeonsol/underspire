"""
Command sets

All commands in the game must be grouped in a cmdset.  A given command
can be part of any number of cmdsets and cmdsets can be added/removed
and merged onto entities at runtime.

To add or change commands, edit the appropriate module under commands/
(e.g. commands/base_cmds.py, commands/combat_cmds.py) and ensure the
command is imported and added here or in command.py for re-export.

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
        from commands.death_cmds import CmdLeavePod
        self.add(CmdLeavePod())


class CombatGrappleCmdSet(CmdSet):
    """
    Grapple/letgo/resist with priority above ExitCmdSet (101) so "grapple"
    is never taken by an exit or other location cmdset. Also added to
    SessionCmdSet so these commands are always in the merge when logged in.
    """
    key = "CombatGrapple"
    priority = 120

    def at_cmdset_creation(self):
        from commands.combat_cmds import CmdGrapple, CmdLetGo, CmdResist
        self.add(CmdGrapple())
        self.add(CmdLetGo())
        self.add(CmdResist())


class UnconsciousCmdSet(CmdSet):
    """
    When character is knocked out (0 stamina from grapple strikes): only look (shows "You are unconscious.")
    and everything else replies "You are unconscious." Added/removed by world.grapple.set_unconscious / wake.
    """
    key = "UnconsciousCmdSet"
    priority = 200

    def at_cmdset_creation(self):
        from commands.death_cmds import CmdLookUnconscious, CmdNoMatchUnconscious
        self.add(CmdLookUnconscious())
        self.add(CmdNoMatchUnconscious())


class FlatlinedCmdSet(CmdSet):
    """
    When character is flatlined (0 HP, dying): only look (shows "You are dying...") and
    everything else replies "You are dying. There is nothing you can do."
    Added/removed by world.death.make_flatlined / clear_flatline.
    """
    key = "FlatlinedCmdSet"
    priority = 200

    def at_cmdset_creation(self):
        from commands.death_cmds import CmdLookFlatlined, CmdNoMatchFlatlined
        self.add(CmdLookFlatlined())
        self.add(CmdNoMatchFlatlined())


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

        from commands.base_cmds import CmdLook, CmdExamine, CmdGet, CmdPut
        from commands.combat_cmds import CmdAttack, CmdStop, CmdFlee, CmdStance, CmdExecute, CmdGrapple, CmdLetGo, CmdResist
        from commands.scavenge_cmds import CmdScavenge, CmdSkin, CmdButcher, CmdSever, CmdLoot
        from commands.medical_cmds import CmdHt, CmdUse, CmdApply, CmdStabilize, CmdSurgery, CmdDefib
        from commands.survival_cmds import CmdEat, CmdDrink
        from commands.inventory_cmds import CmdWield, CmdUnwield, CmdFreehands, CmdInventory, CmdReload, CmdUnload, CmdCheckAmmo, CmdWear, CmdRemove, CmdStrip, CmdFrisk
        from commands.crafting_cmds import CmdSurvey, CmdRepairArmor, CmdTailor
        from commands.media_cmds import CmdCamera, CmdTuneTelevision, CmdLabel
        from commands.roleplay_cmds import CmdTease, CmdDescribeBodypart, CmdDescribeMeAs, CmdBody, CmdVoice, CmdSdesc, CmdPending, CmdLookPlace, CmdSleepPlace, CmdWakeMsg, CmdFlatlineMsg, CmdSetPlace, CmdPose, CmdPronoun, CmdEmote, CmdNoMatch
        from commands.roleplay_cmds import CmdSit, CmdLieOnTable, CmdGetOffTable
        from commands.death_cmds import CmdGoOOC, CmdReturnIC, CmdEnterPod, CmdLeavePod, CmdSplinterMe
        from commands.vehicle_cmds import CmdEnterVehicle, CmdExitVehicle, CmdStartEngine, CmdStopEngine, CmdShutoffEngine, CmdDrive, CmdVehicleStatus, CmdRepairPart
        from commands.staff_cmds import (
            CmdStats, CmdXp, CmdGiveXp, CmdStaffSheet, CmdStaffSetStat, CmdStaffSetSkill,
            CmdCreateItem, CmdTypeclasses, CmdSpawnItem, CmdSpawnArmor, CmdSpawnVehicle, CmdSpawnMedical, CmdSpawnOR,
            CmdSpawnCreature, CmdCreatureSet, CmdDespawn, CmdNpc, CmdMakeNpc, CmdNpcSet,
            CmdGoto, CmdGotoRoom, CmdSummon, CmdSetVoid, CmdVoid, CmdRelease, CmdBoot, CmdFind, CmdAnnounce, CmdRestore, CmdDebugKill,
            CmdSpawnSeat, CmdSpawnBed, CmdSpawnPod, CmdSpawnCamera, CmdSpawnTelevision,
            CmdEmoteDebug, CmdDamageVehicle,
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
        from evennia.commands.default import general as default_general

        # Use our custom CmdLook instead of Evennia's default
        self.remove(default_general.CmdLook)
        self.add(CmdLook())
        self.add(CmdScavenge())
        self.add(CmdSkin())
        self.add(CmdButcher())
        self.add(CmdSever())
        self.add(CmdStats())
        self.add(CmdAttack())
        self.add(CmdStop())
        self.add(CmdFlee())
        self.add(CmdExecute())
        self.add(CmdStance())
        self.add(CmdHt())
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
        self.add(CmdSurvey())
        self.add(CmdRepairArmor())
        self.add(CmdLoot())
        self.add(CmdFrisk())
        if DefaultCmdGet is not None:
            self.remove(DefaultCmdGet)
            self.add(CmdGet())
        self.add(CmdPut())
        self.add(CmdCamera())
        self.add(CmdTuneTelevision())
        self.add(CmdTailor())
        self.add(CmdTease())
        self.add(CmdXp())
        self.add(CmdDescribeBodypart())
        self.add(CmdDescribeMeAs())
        self.add(CmdBody())
        self.add(CmdVoice())
        self.add(CmdSdesc())
        self.add(CmdPending())
        self.add(CmdLookPlace())
        self.add(CmdSleepPlace())
        self.add(CmdWakeMsg())
        self.add(CmdFlatlineMsg())
        self.add(CmdSetPlace())
        self.add(CmdGoOOC())
        self.add(CmdReturnIC())
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
        self.add(CombatGrappleCmdSet())  # grapple/letgo/resist above exits (priority 120)
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
        self.add(CmdNpc())
        self.add(CmdGiveXp())
        self.add(CmdCreateItem())
        self.add(CmdTypeclasses())
        self.add(CmdSpawnItem())
        self.add(CmdSpawnArmor())
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
        self.add(CmdGotoRoom())
        self.add(CmdSummon())
        self.add(CmdDespawn())
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
        self.add(CmdSpawnCamera())
        self.add(CmdSpawnTelevision())
        self.add(CmdSpawnCreature())
        self.add(CmdCreatureSet())

class StaffOnlyPuppet(CmdIC):
    """Puppet a character. Staff only (one character per account for players)."""
    key = "@puppet"
    aliases = []
    locks = "cmd:perm(Builder)"

    def func(self):
        from commands.media_cmds import _get_object_by_id
        from commands.multipuppet_cmds import _clear_multi_puppet_links_for_account, _set_multi_puppet_link
        old_ids = list(getattr(self.account.db, "multi_puppets", None) or [])
        super().func()
        for oid in old_ids:
            obj = _get_object_by_id(oid)
            if obj and hasattr(obj, "db"):
                for key in ("_multi_puppet_account_id", "_multi_puppet_slot"):
                    if hasattr(obj.db, key):
                        try:
                            del obj.db[key]
                        except Exception:
                            pass
        if getattr(self.session, "puppet", None):
            self.account.db.multi_puppets = [self.session.puppet.id]
            _set_multi_puppet_link(self.session.puppet, self.account.id, 1)


class StaffOnlyUnpuppet(CmdOOC):
    """Unpuppet / leave character. Staff only."""
    key = "@unpuppet"
    aliases = []
    locks = "cmd:perm(Builder)"

    def func(self):
        """
        Staff unpuppet:
          - No args: unpuppet completely (current behaviour).
          - Args like 'p2 p3 p4': drop those multi-puppet slots only, keeping p1 puppeted.
        """
        from commands.media_cmds import _get_object_by_id
        from commands.multipuppet_cmds import _clear_multi_puppet_links_for_account, _multi_puppet_list

        args = (self.args or "").strip()

        # No arguments: full unpuppet + clear all multi-puppets (legacy behaviour).
        if not args:
            _clear_multi_puppet_links_for_account(self.account)
            super().func()
            if hasattr(self.account, "db"):
                self.account.db.multi_puppets = []
            return

        # With arguments: interpret as one or more p-slots (p2, p3, ...). Only drop those slots.
        tokens = args.split()
        indices_to_remove = set()
        wants_full_unpuppet = False
        for tok in tokens:
            tok = tok.lower()
            if tok.startswith("p") and tok[1:].isdigit():
                idx = int(tok[1:]) - 1  # p1 -> 0, p2 -> 1, ...
                if idx == 0:
                    # Asking to unpuppet p1 too – treat as full unpuppet.
                    wants_full_unpuppet = True
                elif idx > 0:
                    indices_to_remove.add(idx)

        if wants_full_unpuppet or not indices_to_remove:
            # Fall back to full unpuppet if p1 requested or nothing valid parsed.
            _clear_multi_puppet_links_for_account(self.account)
            super().func()
            if hasattr(self.account, "db"):
                self.account.db.multi_puppets = []
            return

        # Remove selected multi-puppet slots while keeping main puppet (p1) active.
        ids = _multi_puppet_list(self.account)
        if not ids:
            self.caller.msg("You have no puppets in your set.")
            return

        removed_names = []
        # Work from highest index down so list pops don't shift earlier indices.
        for idx in sorted(indices_to_remove, reverse=True):
            if 0 <= idx < len(ids):
                oid = ids[idx]
                obj = _get_object_by_id(oid)
                if obj and hasattr(obj, "db"):
                    removed_names.append(obj.get_display_name(self.caller))
                    for key in ("_multi_puppet_account_id", "_multi_puppet_slot"):
                        if hasattr(obj.db, key):
                            try:
                                del obj.db[key]
                            except Exception:
                                pass
                ids.pop(idx)

        # Re-number remaining slots and persist.
        if hasattr(self.account, "db"):
            self.account.db.multi_puppets = ids
        for slot, oid in enumerate(ids, start=1):
            obj = _get_object_by_id(oid)
            if obj:
                from commands.multipuppet_cmds import _set_multi_puppet_link
                _set_multi_puppet_link(obj, self.account.id, slot)
        if removed_names:
            self.caller.msg("Unpuppeted: %s" % ", ".join(removed_names))


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
        self.add(StaffOnlyPuppet())
        self.remove(CmdOOC)
        self.add(StaffOnlyUnpuppet())
        self.remove(CmdCharCreate)
        self.add(StaffCharCreate())
        self.remove(CmdCharDelete)
        self.add(StaffCharDelete())
        from commands.staff_cmds import CmdStats
        from commands.death_cmds import CmdGoLight, CmdGoShard
        from commands.multipuppet_cmds import CmdAddPuppet, CmdPuppetList, CmdPuppetSlot
        from commands.channel_cmds import CmdChannelSub, CmdChannelUnsub, CmdHelpReply, CmdHelp, CmdOocName
        from commands.media_cmds import CmdTuneTelevision, CmdTelevisionApp, CmdLabel
        from commands.channel_cmds import CmdXooc, CmdXgame, CmdXstaff
        self.add(CmdStats())
        self.add(CmdGoLight())
        self.add(CmdGoShard())
        self.add(CmdAddPuppet())
        self.add(CmdPuppetList())
        self.add(CmdPuppetSlot())
        self.add(CmdChannelSub())
        self.add(CmdChannelUnsub())
        self.add(CmdTuneTelevision())
        self.add(CmdTelevisionApp())
        self.add(CmdLabel())
        self.add(CmdXooc())
        self.add(CmdXgame())
        self.add(CmdXstaff())
        self.add(CmdHelpReply())
        self.add(CmdHelp())
        self.add(CmdOocName())


class UnloggedinCmdSet(default_cmds.UnloggedinCmdSet):
    """
    Command set available to the Session before being logged in.  This
    holds commands like creating a new account, logging in, etc.
    """

    key = "DefaultUnloggedin"

    def at_cmdset_creation(self):
        """
        Populates the cmdset. Use our create command so account-creation
        errors are surfaced instead of a generic message.
        """
        super().at_cmdset_creation()
        from evennia.commands.default import unloggedin as default_unloggedin
        from commands.unloggedin import CmdUnconnectedCreate
        self.remove(default_unloggedin.CmdUnconnectedCreate)
        self.add(CmdUnconnectedCreate())


class SessionCmdSet(default_cmds.SessionCmdSet):
    """
    This cmdset is made available on Session level once logged in. It
    is empty by default. We add CombatGrappleCmdSet here so grapple/letgo/resist
    are always in the merged set (priority 120), even if the character or
    account cmdset is not merged yet or is overridden by location.
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
        self.add(CombatGrappleCmdSet())
