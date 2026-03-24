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
from evennia.utils import search, utils, logger

from commands.base_cmds import CmdGo, Command as _BaseCommand


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


class GrappledCmdSet(CmdSet):
    """
    When character is grappled, only allow look and resist.
    Added/removed by world.grapple when grapple state changes.
    """
    key = "GrappledCmdSet"
    priority = 180

    def at_cmdset_creation(self):
        from commands.base_cmds import CmdLook
        from commands.combat_cmds import CmdResist
        from commands.death_cmds import CmdNoMatchGrappled

        self.add(CmdLook())
        self.add(CmdResist())
        self.add(CmdNoMatchGrappled())


class GrapplingCmdSet(CmdSet):
    """
    When character is holding someone in a grapple: only look, attack (strangle),
    grapple/letgo, stop walking, and exits (movement). Hands are occupied.
    Added/removed by world.combat.grapple when grappling state changes.
    """
    key = "GrapplingCmdSet"
    priority = 180

    def at_cmdset_creation(self):
        from commands.base_cmds import CmdLook, CmdStopWalking
        from commands.combat_cmds import CmdGrapplingAttack, CmdGrapple, CmdLetGo
        from commands.death_cmds import CmdNoMatchGrappling

        self.add(CmdLook())
        self.add(CmdGrapplingAttack())
        self.add(CmdGrapple())
        self.add(CmdLetGo())
        self.add(CmdStopWalking())
        self.add(CmdGo())
        self.add(CmdNoMatchGrappling())


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

        # ExtendedRoom detail/state commands: `look <detail>`, `detail`, `roomdesc`, `roomstate`, `gametime`
        from evennia.contrib.grid.extended_room.extended_room import ExtendedRoomCmdSet
        self.add(ExtendedRoomCmdSet)

        from commands.base_cmds import CmdLook, CmdExamine, CmdGet, CmdPut, CmdStopWalking, CmdStop
        from commands.stealth_cmds import CmdHide, CmdSneak, CmdSearch, CmdUnhide
        from commands.follow_cmds import CmdFollow, CmdShadow, CmdEscort
        from commands.matrix_cmds import CmdMacl
        from commands.combat_cmds import (
            CmdAttack,
            CmdFlee,
            CmdStance,
            CmdExecute,
            CmdGrapple,
            CmdLetGo,
            CmdResist,
        )
        from commands.cover_commands import CmdCover, CmdLeaveCover, CmdPeek, CmdSuppress
        from commands.scavenge_cmds import CmdScavenge, CmdSkin, CmdButcher, CmdSever, CmdLoot
        from commands.salvage_cmds import CmdSalvage
        from commands.medical_cmds import CmdHt, CmdPatient, CmdApply, CmdStabilize, CmdSedate, CmdWakePatient, CmdSurgery, CmdDefib
        from commands.use_cmds import CmdUse
        from commands.survival_cmds import CmdEat, CmdDrink
        from commands.food_cmds import CmdMenu, CmdNewRecipe, CmdPrepare, CmdServe, CmdDelRecipe, CmdRate
        from commands.bar_mgmt_cmds import CmdBarSet, CmdBarSetAdmin
        from commands.inventory_cmds import CmdWield, CmdUnwield, CmdFreehands, CmdInventory, CmdReload, CmdUnload, CmdCheckAmmo, CmdWear, CmdRemove, CmdStrip, CmdFrisk
        from commands.crafting_cmds import CmdSurvey, CmdRepairArmor, CmdTailor
        from commands.alchemy_cmds import (
            CmdAlchemyCheck,
            CmdAnalyze,
            CmdBrew,
            CmdClaim,
            CmdCollect,
            CmdDose,
            CmdLoad,
            CmdRefine,
            CmdTend,
        )
        from commands.media_cmds import CmdCamera, CmdTuneTelevision, CmdLabel
        from commands.trust_cmds import CmdTrust, CmdUntrust, CmdTrusted
        from commands.cosmetic_cmds import (
            CmdInk, CmdRemoveTattoo, CmdTattoos,
            CmdApply as CmdApplyCosmetic,
            CmdWipe, CmdColor, CmdColors,
        )
        from commands.rune_cmds import CmdCarve, CmdIgnite
        from commands.roleplay_cmds import CmdTease, CmdDescribeMeAs, CmdBody, CmdVoice, CmdSmellSet, CmdLanguage, CmdSdesc, CmdPending, CmdLookPlace, CmdTempPlace, CmdSleepPlace, CmdWakeMsg, CmdFlatlineMsg, CmdSetPlace, CmdPose, CmdPronoun, CmdEmote, CmdNoMatch, CmdCount, CmdRecog, CmdMemorize, CmdMemory, CmdSmell
        from commands.skintone_cmd import CmdSkintone
        from commands.roleplay_cmds import CmdSit, CmdLieOnTable, CmdGetOffTable
        from commands.performance_cmds import CmdPerformance
        from commands.artistry_cmds import CmdArtistry
        from commands.death_cmds import CmdGoOOC, CmdReturnIC, CmdEnterPod, CmdLeavePod, CmdSplinterMe
        from commands.lock_cmds import CmdLock, CmdUnlock
        from commands.vehicle_cmds import (
            CmdEnterVehicle,
            CmdExitVehicle,
            CmdMount,
            CmdDismount,
            CmdControlVehicle,
            CmdReleaseControls,
            CmdHaltVehicleMovement,
            CmdStartEngine,
            CmdStopEngine,
            CmdShutoffEngine,
            CmdDrive,
            CmdFly,
            CmdTakeoff,
            CmdLand,
            CmdEvaluateVehicle,
            CmdRepairPart,
            CmdRefuel,
            CmdSwapVehiclePart,
            CmdPaintVehicle,
            CmdCustomizeVehicle,
        )
        from commands.vehicle_security_cmds import (
            CmdAuthorize,
            CmdDeauthorize,
            CmdAuthorizations,
            CmdTransferVehicle,
            CmdBreakIn,
            CmdHotwire,
        )
        from commands.vehicle_combat_cmds import (
            CmdFire,
            CmdRam,
            CmdManGunner,
            CmdLeaveGunner,
            CmdEject,
            CmdInstallVehicleWeapon,
            CmdUninstallVehicleWeapon,
            CmdReloadVehicleWeapon,
            CmdDislodgeHarpoon,
        )
        from commands.tunnel_cmds import CmdAutopilot
        from commands.matrix_cmds import CmdJackIn, CmdJackOut, CmdRoute
        from commands.network_cmds import CmdNetworkWho, CmdNetworkSend, CmdNetworkNtag
        from commands.handset_cmds import CmdHandset
        from commands.cyberware_cmds import CmdCyberware, CmdSkinWeave, CmdSurge, CmdClaws
        from commands.staff_cmds import (
            CmdGiveXp, CmdStaffSheet, CmdStaffSetStat, CmdStaffSetSkill,
            CmdCreateItem, CmdTypeclasses, CmdSpawnItem, CmdSpawnArmor, CmdSpawnVehicle, CmdSpawnMedical, CmdSpawnOR, CmdSpawnCyberwareStation,
            CmdSpawnCreature, CmdCreatureSet, CmdDespawn, CmdNpc, CmdMakeNpc, CmdNpcSet, CmdSpawnPerfume, CmdBadSmellRoom,
            CmdGoto, CmdGotoRoom, CmdSummon, CmdSetVoid, CmdVoid, CmdRelease, CmdBoot, CmdFind, CmdAnnounce, CmdRestore, CmdDebugKill,
            CmdSpawnSeat, CmdSpawnBed, CmdSpawnPod, CmdSpawnDiveRig, CmdSpawnCamera, CmdSpawnTelevision,
            CmdEmoteDebug, CmdDamageVehicle, CmdMusic, CmdProfiling, CmdBuffDebug, CmdClimate,
            CmdMigrateTraits, CmdGrantScript,
        )
        from commands.staff_vehicle_cmds import (
            CmdVmod,
            CmdVmodtypes,
            CmdVrepair,
            CmdVweaponInstall,
            CmdVweaponKeys,
            CmdVweaponRemove,
        )
        from commands.rpg.faction_cmds import CmdFaction
        from commands.economy_cmds import (
            CmdPay, CmdDropMoney, CmdShopList, CmdBuy, CmdWire, CmdWireConfirm,
            CmdBankMenu, CmdShopSet, CmdShopItem, CmdSpawnBank, CmdTagBank,
        )
        from commands.rentable_door_cmds import CmdRent, CmdPayRent, CmdPush, CmdDoorCode as CmdProgramDoor, CmdRentSet, CmdCheckDoor
        from commands.sheet_cmds import CmdStats
        from commands.player_cmds import CmdXp
        from commands.notes_cmds import CmdAddNote, CmdNotes, CmdNoteSearch
        from commands.builder_commands import (
            CmdTag, CmdHere, CmdListCmds, CmdCloneSpawn, CmdDig, CmdMatrixDig, CmdDesc,
            CmdSetAttr, CmdName, CmdOpen, CmdAtOpen, CmdDestroy, CmdMatrixLink, CmdDoor, CmdDoorPair,
        )
        from commands.city_grid_cmds import (
            CmdAirRoom,
            CmdCityCoord,
            CmdCityLevel,
            CmdCityMap,
            CmdShaftConnect,
        )
        from commands.freight_cmds import CmdFreight
        from commands.bulkhead_cmds import CmdBulkheadAdmin, CmdBulkheadStatus, CmdSeal, CmdUnseal
        try:
            from evennia.commands.default.general import CmdGet as DefaultCmdGet
        except ImportError:
            DefaultCmdGet = None

        # --- Player commands (everyone) ---
        from evennia.commands.default import general as default_general

        # Use our custom CmdLook instead of Evennia's default
        self.remove(default_general.CmdLook)
        # Evennia's building CmdOpen matches plain "open" via prefix strip; use CmdAtOpen
        # so only |w@open|n matches building, and |wopen|n stays the IC door command.
        from evennia.commands.default import building as default_building

        self.remove(default_building.CmdOpen)
        self.add(CmdAtOpen())
        from commands.door_cmds import CmdOpenDoor, CmdCloseDoor, CmdVerify, CmdUnlockDoor

        self.add(CmdOpenDoor())
        self.add(CmdCloseDoor())
        self.add(CmdVerify())
        self.add(CmdUnlockDoor())
        # Replace Evennia's built-in `who` with our `@who`.
        try:
            from evennia.commands.default.account import CmdWho as DefaultCmdWho
            self.remove(DefaultCmdWho)
        except Exception:
            pass
        self.add(CmdLook())
        self.add(CmdHide())
        self.add(CmdSneak())
        self.add(CmdSearch())
        self.add(CmdUnhide())
        self.add(CmdFollow())
        self.add(CmdShadow())
        self.add(CmdEscort())
        self.add(CmdStopWalking())
        self.add(CmdStop())
        self.add(CmdGo())
        self.add(CmdScavenge())
        self.add(CmdSkin())
        self.add(CmdButcher())
        self.add(CmdSever())
        self.add(CmdStats())
        self.add(CmdAttack())
        self.add(CmdFlee())
        self.add(CmdExecute())
        self.add(CmdStance())
        self.add(CmdHt())
        self.add(CmdPatient())
        self.add(CmdUse())
        self.add(CmdApply())
        self.add(CmdStabilize())
        self.add(CmdGrapple())
        self.add(CmdLetGo())
        self.add(CmdResist())
        self.add(CmdCover())
        self.add(CmdLeaveCover())
        self.add(CmdPeek())
        self.add(CmdSuppress())
        self.add(CmdSit())
        self.add(CmdLieOnTable())
        self.add(CmdGetOffTable())
        self.add(CmdSedate())
        self.add(CmdWakePatient())
        self.add(CmdSurgery())
        self.add(CmdEat())
        self.add(CmdDrink())
        self.add(CmdMenu())
        self.add(CmdNewRecipe())
        self.add(CmdPrepare())
        self.add(CmdServe())
        self.add(CmdDelRecipe())
        self.add(CmdRate())
        self.add(CmdBarSet())
        self.add(CmdBarSetAdmin())
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
        self.add(CmdSalvage())
        self.add(CmdFrisk())
        if DefaultCmdGet is not None:
            self.remove(DefaultCmdGet)
            self.add(CmdGet())
        self.add(CmdPut())
        self.add(CmdHandset())
        self.add(CmdMacl())
        self.add(CmdCamera())
        self.add(CmdTuneTelevision())
        self.add(CmdTailor())
        self.add(CmdCollect())
        self.add(CmdLoad())
        self.add(CmdBrew())
        self.add(CmdTend())
        self.add(CmdRefine())
        self.add(CmdAlchemyCheck())
        self.add(CmdClaim())
        self.add(CmdAnalyze())
        self.add(CmdDose())
        self.add(CmdTease())
        self.add(CmdXp())
        self.add(CmdPay())
        self.add(CmdDropMoney())
        self.add(CmdShopList())
        self.add(CmdBuy())
        self.add(CmdRent())
        self.add(CmdPayRent())
        self.add(CmdPush())
        self.add(CmdProgramDoor())
        self.add(CmdCheckDoor())
        self.add(CmdWire())
        self.add(CmdWireConfirm())
        self.add(CmdBankMenu())
        self.add(CmdDescribeMeAs())
        self.add(CmdSkintone())
        self.add(CmdBody())
        self.add(CmdVoice())
        self.add(CmdSmellSet())
        self.add(CmdLanguage())
        self.add(CmdSdesc())
        self.add(CmdPending())
        self.add(CmdLookPlace())
        self.add(CmdTempPlace())
        self.add(CmdSleepPlace())
        self.add(CmdWakeMsg())
        self.add(CmdFlatlineMsg())
        self.add(CmdSetPlace())
        self.add(CmdGoOOC())
        self.add(CmdReturnIC())
        self.add(CmdPose())
        self.add(CmdPronoun())
        self.add(CmdEmote())
        self.add(CmdCount())
        self.add(CmdRecog())
        self.add(CmdTrust())
        self.add(CmdUntrust())
        self.add(CmdTrusted())
        self.add(CmdInk())
        self.add(CmdRemoveTattoo())
        self.add(CmdTattoos())
        self.add(CmdApplyCosmetic())
        self.add(CmdWipe())
        self.add(CmdColor())
        self.add(CmdColors())
        self.add(CmdCarve())
        self.add(CmdIgnite())
        self.add(CmdNoMatch())
        self.add(CmdPerformance())
        self.add(CmdArtistry())
        self.add(CmdExamine())
        self.add(CmdMemorize())
        self.add(CmdMemory())
        self.add(CmdSmell())
        self.add(CmdTag())
        self.add(CmdHere())
        self.add(CmdListCmds())
        self.add(CmdCloneSpawn())
        self.add(CmdDig())
        self.add(CmdMatrixDig())
        self.add(CmdDesc())
        self.add(CmdSetAttr())
        self.add(CmdName())
        self.add(CmdOpen())  # buopen
        self.add(CmdDestroy())
        self.add(CmdMatrixLink())
        self.add(CmdDoor())
        self.add(CmdDoorPair())
        self.add(CmdEnterPod())
        self.add(CmdSplinterMe())
        self.add(CombatGrappleCmdSet())  # grapple/letgo/resist above exits (priority 120)
        self.add(CmdEnterVehicle())
        self.add(CmdExitVehicle())
        self.add(CmdMount())
        self.add(CmdDismount())
        self.add(CmdLock())
        self.add(CmdUnlock())
        self.add(CmdControlVehicle())
        self.add(CmdReleaseControls())
        self.add(CmdHaltVehicleMovement())
        self.add(CmdStartEngine())
        self.add(CmdStopEngine())
        self.add(CmdShutoffEngine())
        self.add(CmdDrive())
        self.add(CmdFly())
        self.add(CmdTakeoff())
        self.add(CmdLand())
        self.add(CmdAutopilot())
        self.add(CmdEvaluateVehicle())
        self.add(CmdRepairPart())
        self.add(CmdRefuel())
        self.add(CmdSwapVehiclePart())
        self.add(CmdPaintVehicle())
        self.add(CmdCustomizeVehicle())
        self.add(CmdAuthorize())
        self.add(CmdDeauthorize())
        self.add(CmdAuthorizations())
        self.add(CmdTransferVehicle())
        self.add(CmdBreakIn())
        self.add(CmdHotwire())
        self.add(CmdFire())
        self.add(CmdRam())
        self.add(CmdManGunner())
        self.add(CmdLeaveGunner())
        self.add(CmdEject())
        self.add(CmdInstallVehicleWeapon())
        self.add(CmdUninstallVehicleWeapon())
        self.add(CmdReloadVehicleWeapon())
        self.add(CmdDislodgeHarpoon())
        self.add(CmdJackIn())
        self.add(CmdJackOut())
        self.add(CmdNetworkWho())
        self.add(CmdNetworkSend())
        self.add(CmdNetworkNtag())
        self.add(CmdRoute())
        self.add(CmdSkinWeave())
        self.add(CmdSurge())
        self.add(CmdClaws())
        self.add(CmdAddNote())
        self.add(CmdNotes())
        self.add(CmdNoteSearch())
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
        self.add(CmdVweaponKeys())
        self.add(CmdVweaponInstall())
        self.add(CmdVweaponRemove())
        self.add(CmdVmod())
        self.add(CmdVmodtypes())
        self.add(CmdVrepair())
        self.add(CmdSpawnMedical())
        self.add(CmdSpawnOR())
        self.add(CmdSpawnCyberwareStation())
        self.add(CmdSpawnPerfume())
        self.add(CmdShopSet())
        self.add(CmdShopItem())
        self.add(CmdSpawnBank())
        self.add(CmdTagBank())
        self.add(CmdRentSet())
        self.add(CmdGrantScript())
        self.add(CmdStaffSheet())
        self.add(CmdStaffSetStat())
        self.add(CmdStaffSetSkill())
        self.add(CmdMigrateTraits())
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
        self.add(CmdSpawnDiveRig())
        self.add(CmdSpawnCamera())
        self.add(CmdSpawnTelevision())
        self.add(CmdBadSmellRoom())
        self.add(CmdSpawnCreature())
        self.add(CmdCreatureSet())
        self.add(CmdMusic())
        self.add(CmdCyberware())
        self.add(CmdProfiling())
        self.add(CmdBuffDebug())
        self.add(CmdClimate())
        self.add(CmdFaction())
        self.add(CmdCityMap())
        self.add(CmdCityLevel())
        self.add(CmdCityCoord())
        self.add(CmdAirRoom())
        self.add(CmdShaftConnect())
        self.add(CmdFreight())
        self.add(CmdSeal())
        self.add(CmdUnseal())
        self.add(CmdBulkheadStatus())
        self.add(CmdBulkheadAdmin())
        # Whoosh-powered full-text help search
        self.add(CmdHelpSearch())


class CmdHelpSearch(_BaseCommand):
    """
    Search help entries using full-text matching.

    Usage:
      helpsearch <query>
      hs <query>

    Returns ranked help topics that match the query, even if
    the exact command name is not known.
    """
    key = "helpsearch"
    aliases = ["hs"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        query = (self.args or "").strip()
        if not query:
            self.caller.msg("Usage: helpsearch <query>")
            return
        try:
            from world.help_search import search_help
            results = search_help(query, limit=7)
        except Exception:
            results = []
        if not results:
            self.caller.msg(f"No help entries found for '{query}'.")
            return
        lines = [f"|wHelp search results for:|n {query}"]
        for hit in results:
            lines.append(f"  |w{hit['key']}|n ({hit['category']})")
        lines.append("\nUse |whelp <topic>|n to read an entry.")
        self.caller.msg("\n".join(lines))


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
        # Replace Evennia's built-in `who` with our `@who`.
        try:
            from evennia.commands.default.account import CmdWho as DefaultCmdWho
            self.remove(DefaultCmdWho)
        except Exception:
            pass

        from commands.who_cmds import CmdWho, CmdWhoMsg, CmdWhoAnon
        self.add(CmdWho())
        self.add(CmdWhoMsg())
        self.add(CmdWhoAnon())

        from commands.multipuppet_cmds import StaffOnlyPuppet, StaffOnlyUnpuppet
        from commands.staff_cmds import StaffCharCreate, StaffCharDelete
        self.remove(CmdIC)
        self.add(StaffOnlyPuppet())
        self.remove(CmdOOC)
        self.add(StaffOnlyUnpuppet())
        self.remove(CmdCharCreate)
        self.add(StaffCharCreate())
        self.remove(CmdCharDelete)
        self.add(StaffCharDelete())
        from commands.sheet_cmds import CmdStats
        from commands.staff_cmds import CmdNextNote, CmdGmViewNotes
        from commands.death_cmds import CmdReturnIC
        from commands.multipuppet_cmds import CmdAddPuppet, CmdPuppetList, CmdPuppetSlot
        from commands.channel_cmds import CmdChannelSub, CmdChannelUnsub, CmdHelpReply, CmdHelp, CmdOocName
        from commands.media_cmds import CmdTuneTelevision, CmdTelevisionApp, CmdLabel
        from commands.channel_cmds import CmdXooc, CmdXgame, CmdXstaff
        self.add(CmdStats())
        self.add(CmdNextNote())
        self.add(CmdGmViewNotes())
        self.add(CmdReturnIC())
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
