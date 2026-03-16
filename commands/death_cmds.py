"""
Death/OOC/pod/splinter/shard/light and flatlined/unconscious command handlers.
"""

from evennia.utils import logger
from commands.base_cmds import Command
from commands.combat_cmds import _combat_caller
from evennia.commands.cmdhandler import CMD_NOMATCH


def _can_use_ooc_room(character):
    """Return (True, None) or (False, reason_string). Blocks combat, dead, corpse, grappled, unconscious, voided."""
    if not character or not getattr(character, "db", None):
        return False, "You can't do that right now."
    if getattr(character.db, "combat_target", None) is not None:
        return False, "You can't go OOC while in combat."
    try:
        from world.death import is_flatlined, is_permanently_dead
        if is_flatlined(character):
            return False, "You can't go OOC while dying."
        if is_permanently_dead(character):
            return False, "You're dead."
    except ImportError:
        if getattr(character.db, "current_hp", None) is not None and (character.db.current_hp or 0) <= 0:
            return False, "You can't go OOC in that state."
    try:
        from typeclasses.corpse import Corpse
        if isinstance(character, Corpse):
            return False, "You're a corpse."
    except ImportError as e:
        logger.log_trace("death_cmds._can_use_ooc_room Corpse check: %s" % e)
    if getattr(character.db, "grappled_by", None) or getattr(character.db, "grappling", None):
        return False, "You can't go OOC while grappled."
    try:
        from world.medical import is_unconscious
        if is_unconscious(character):
            return False, "You can't go OOC while unconscious."
    except ImportError as e:
        logger.log_trace("death_cmds._can_use_ooc_room is_unconscious: %s" % e)
    if getattr(character.db, "voided", False):
        return False, "You can't go OOC from the void."
    return True, None


def _spirit_account(caller):
    """Get the Account puppeting this Spirit (caller in death limbo)."""
    if not hasattr(caller, "sessions"):
        return None
    try:
        for session in (caller.sessions.get() or []):
            acc = getattr(session, "account", None)
            if acc:
                return acc
    except Exception as e:
        logger.log_trace("death_cmds._spirit_account: %s" % e)
    return None


def _get_pod_from_caller(caller):
    """If caller is inside a splinter pod interior, return the pod object; else None."""
    loc = getattr(caller, "location", None)
    if not loc:
        return None
    pod = getattr(loc.db, "pod", None)
    if pod:
        return pod
    try:
        from evennia.utils.search import search_typeclass
        for p in search_typeclass("typeclasses.splinter_pod.SplinterPod"):
            if getattr(p.db, "interior", None) is loc:
                return p
    except Exception as e:
        logger.log_trace("death_cmds._get_pod_from_caller: %s" % e)
    return None


def _go_light_unpuppet_all(account):
    """Unpuppet all sessions from the account. Logs and continues on exception."""
    if not hasattr(account, "unpuppet_object") or not hasattr(account, "sessions"):
        return
    for session in (account.sessions.get() or []):
        try:
            account.unpuppet_object(session)
        except Exception as e:
            logger.log_trace("death_cmds._go_light_unpuppet_all: %s" % e)


def _go_light_clear_death_attrs(account):
    """Remove corpse/spirit refs and spirit object from account. Logs and continues on exception."""
    for key in ("dead_character_name", "dead_character_corpse"):
        if hasattr(account.db, key):
            try:
                del account.db[key]
            except Exception as e:
                logger.log_trace("death_cmds._go_light_clear_death_attrs %s: %s" % (key, e))
    spirit = getattr(account.db, "death_spirit", None)
    if spirit and hasattr(spirit, "id"):
        if hasattr(account, "characters") and hasattr(account.characters, "remove"):
            try:
                account.characters.remove(spirit)
            except Exception as e:
                logger.log_trace("death_cmds._go_light_clear_death_attrs remove spirit: %s" % e)
        try:
            spirit.delete()
        except Exception as e:
            logger.log_trace("death_cmds._go_light_clear_death_attrs spirit.delete: %s" % e)
    if hasattr(account.db, "death_spirit"):
        try:
            del account.db["death_spirit"]
        except Exception as e:
            logger.log_trace("death_cmds._go_light_clear_death_attrs del death_spirit: %s" % e)
    if hasattr(account.db, "_last_puppet"):
        try:
            del account.db["_last_puppet"]
        except Exception as e:
            logger.log_trace("death_cmds._go_light_clear_death_attrs del _last_puppet: %s" % e)


def _go_light_disconnect_sessions(account, reason):
    """Disconnect all sessions with reason. Logs and continues on exception."""
    if not hasattr(account, "sessions"):
        return
    for session in (account.sessions.get() or []):
        try:
            if hasattr(session, "sessionhandler") and session.sessionhandler:
                session.sessionhandler.disconnect(session, reason=reason)
            elif hasattr(session, "disconnect"):
                session.disconnect(reason=reason)
        except Exception as e:
            logger.log_trace("death_cmds._go_light_disconnect_sessions: %s" % e)


class CmdGoOOC(Command):
    """
    Temporarily move to the OOC room. You remain puppeted; use @ic to return.
    Blocked while in combat, dead, grappled, unconscious, or voided.
    Usage: @ooc
    """
    key = "@ooc"
    aliases = []
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _combat_caller(self)
        if not getattr(caller, "db", None) or not hasattr(caller.db, "stats"):
            self.caller.msg("You must be in character to use that.")
            return
        ok, reason = _can_use_ooc_room(caller)
        if not ok:
            self.caller.msg("|r%s|n" % reason)
            return
        from django.conf import settings
        from evennia.utils.search import search_object
        ooc_id = getattr(settings, "OOC_ROOM_ID", None)
        ooc_room = None
        if ooc_id is not None:
            try:
                res = search_object("#%s" % int(ooc_id))
                if res:
                    ooc_room = res[0]
            except (TypeError, ValueError):
                pass
        if not ooc_room:
            try:
                from evennia.utils.search import search_tag
                res = search_tag("ooc_room", category="room")
                if res:
                    ooc_room = res[0] if hasattr(res[0], "move_to") else res
            except Exception as e:
                logger.log_trace("death_cmds.CmdOOC search ooc_room: %s" % e)
        if not ooc_room or not hasattr(ooc_room, "move_to"):
            self.caller.msg("|rNo OOC room is configured. Ask staff to set OOC_ROOM_ID or tag a room 'ooc_room'.|n")
            return
        here = caller.location
        if not here:
            self.caller.msg("|rYou have no location to leave from.|n")
            return
        caller.db.ooc_previous_location_id = here.id
        caller.move_to(ooc_room)
        self.caller.msg("|gYou step OOC. Use |w@ic|n to return.|n")
        if here:
            here.msg_contents("%s steps out of the world for a moment." % caller.name, exclude=(caller,))


class CmdReturnIC(Command):
    """
    Return from the OOC room to where you were. Only works if you used @ooc.
    Usage: @ic
    """
    key = "@ic"
    aliases = []
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _combat_caller(self)
        if not getattr(caller, "db", None) or not hasattr(caller.db, "stats"):
            self.caller.msg("You must be in character to use that.")
            return
        prev_id = getattr(caller.db, "ooc_previous_location_id", None)
        if prev_id is None:
            self.caller.msg("|rYou're already in the world. Use |w@ooc|n to step out first.|n")
            return
        from evennia.utils.search import search_object
        try:
            res = search_object("#%s" % int(prev_id))
            if not res:
                self.caller.msg("|rThat place is gone. You remain here.|n")
                try:
                    caller.attributes.remove("ooc_previous_location_id")
                except Exception as e:
                    logger.log_trace("death_cmds.CmdReturnIC remove ooc_previous_location_id: %s" % e)
                return
            dest = res[0]
        except (TypeError, ValueError):
            self.caller.msg("|rSomething went wrong.|n")
            return
        del caller.db.ooc_previous_location_id
        caller.move_to(dest)
        self.caller.msg("|gYou step back into the world.|n")
        if dest:
            dest.msg_contents("%s steps back into the world." % caller.name, exclude=(caller,))


class CmdEnterPod(Command):
    """
    Enter a splinter pod. Same pattern as enter vehicle: move to interior.
    Usage: enter pod [or enter <pod>]
    """
    key = "enter pod"
    aliases = ["enter pod", "enter splinter pod"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if _get_pod_from_caller(caller):
            caller.msg("You are already inside a pod. Type |wdone|n to get out first.")
            return
        pod = None
        for obj in (caller.location.contents if caller.location else []):
            if getattr(obj, "db", None) and getattr(obj.db, "interior", None):
                pod = obj
                break
        if not pod:
            caller.msg("There is no splinter pod here.")
            return
        interior = pod.db.interior
        if not interior:
            caller.msg("The pod is inert. Nothing to enter.")
            return
        caller.move_to(interior)
        caller.msg("The seal closes behind you. |xYou are inside.|n Type |wdone|n when you are ready to leave.")
        if caller.location:
            caller.location.msg_contents("%s enters the splinter pod." % caller.name, exclude=caller)


class CmdSplinterMe(Command):
    """
    Undergo soul-splintering inside a pod. Stores a shard for clone resurrection.
    Usage: splinter me
    """
    key = "splinter me"
    aliases = ["splinter"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not _get_pod_from_caller(caller):
            caller.msg("You must be inside a splinter pod to do that.")
            return
        try:
            from world.death import is_flatlined, is_permanently_dead
            if is_flatlined(caller) or is_permanently_dead(caller):
                caller.msg("|rYou must be alive and conscious to be splintered.|n")
                return
        except ImportError as e:
            logger.log_trace("death_cmds.CmdSplinterMe is_flatlined/is_permanently_dead: %s" % e)
        from world.cloning import run_splinter_sequence
        caller.msg("|xYou speak the words. The mechanism answers.|n")
        run_splinter_sequence(caller)


class CmdLeavePod(Command):
    """
    Leave the splinter pod. Type 'done' when you are ready to step out.
    Usage: done
    """
    key = "done"
    aliases = []
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        pod = _get_pod_from_caller(caller)
        if not pod:
            caller.msg("You are not inside a splinter pod.")
            return
        dest = getattr(pod, "location", None)
        if not dest:
            caller.msg("The pod has no location. You cannot leave.")
            return
        caller.move_to(dest)
        caller.msg("You step out of the pod.")
        dest.msg_contents("%s steps out of the splinter pod." % caller.name, exclude=caller)


class CmdGoShard(Command):
    """
    Wake in your clone body (soul shard). Only in death limbo and only if your dead character had a stored splinter.
    Usage: go shard
    """
    key = "go shard"
    aliases = ["go shard", "shard"]
    locks = "cmd:attr(has_spirit_puppet) and attr(account_has_clone)"
    help_category = "Death"

    def func(self):
        caller = self.caller
        account = _spirit_account(caller)
        if not account:
            caller.msg("You are not in a state to do that.")
            return
        corpse = getattr(account.db, "dead_character_corpse", None)
        snapshot = getattr(corpse, "db", None) and getattr(corpse.db, "clone_snapshot", None) if corpse else None
        if not snapshot:
            caller.msg("|yYou have no stored shard. Only |wgo light|n is left.|n")
            return
        try:
            from world.cloning import (
                get_clone_spawn_room,
                apply_clone_snapshot,
                run_awakening_sequence,
            )
            from evennia.utils.create import create_object
            dead_name = getattr(account.db, "dead_character_name", "Unknown")
            corpse = getattr(account.db, "dead_character_corpse", None)
            spawn_room = get_clone_spawn_room()
            if not spawn_room:
                caller.msg("|rThe awakening bay could not be found.|n")
                return
            new_char = create_object(
                "typeclasses.characters.Character",
                key=dead_name,
                location=spawn_room,
            )
            if not new_char:
                caller.msg("|rThe clone could not be created.|n")
                return
            apply_clone_snapshot(new_char, snapshot)
            account.characters.add(new_char)
            # Unlink corpse from account only; corpse stays persistent in the game world (do not delete)
            if corpse and hasattr(account, "characters"):
                try:
                    account.characters.remove(corpse)
                except Exception as e:
                    logger.log_trace("death_cmds.CmdGoShard remove corpse: %s" % e)
            if corpse and getattr(corpse, "db", None) and hasattr(corpse.db, "clone_snapshot"):
                try:
                    del corpse.db["clone_snapshot"]
                except Exception as e:
                    logger.log_trace("death_cmds.CmdGoShard del clone_snapshot: %s" % e)
            caller.msg("|xThe shard stirs. You are pulled away from the lobby.|n")
            run_awakening_sequence(account, new_char, spawn_room)
        except Exception as e:
            caller.msg("|rSomething went wrong: %s|n" % e)


class CmdGoLight(Command):
    """
    Let go and return to the connection screen. You will create a new character from scratch.
    Usage: go light
    """
    key = "go light"
    aliases = ["go light", "light"]
    locks = "cmd:attr(has_spirit_puppet)"
    help_category = "Death"

    def func(self):
        caller = self.caller
        account = _spirit_account(caller)
        if not account:
            caller.msg("You are not in a state to do that.")
            return
        _go_light_unpuppet_all(account)
        # Unlink corpse from account only; corpse stays persistent in the game world (do not delete)
        corpse = getattr(account.db, "dead_character_corpse", None)
        if corpse and hasattr(account, "characters"):
            try:
                account.characters.remove(corpse)
            except Exception as e:
                logger.log_trace("death_cmds.CmdGoLight remove corpse: %s" % e)
        _go_light_clear_death_attrs(account)
        reason = "You have gone to the light. Create a new character when you return."
        _go_light_disconnect_sessions(account, reason)


class CmdLookFlatlined(Command):
    """When flatlined (dying), look only shows this."""
    key = "look"
    aliases = ["l"]
    locks = "cmd:all()"

    def func(self):
        self.caller.msg("You are dying. Everything is fading. There is nothing you can do.")


class CmdNoMatchFlatlined(Command):
    """When flatlined, any other command shows this."""
    key = CMD_NOMATCH
    locks = "cmd:all()"

    def func(self):
        self.caller.msg("You are dying. There is nothing you can do.")


class CmdLookUnconscious(Command):
    """When unconscious, look only shows this."""
    key = "look"
    aliases = ["l"]
    locks = "cmd:all()"

    def func(self):
        self.caller.msg("You are unconscious.")


class CmdNoMatchUnconscious(Command):
    """When unconscious, any other command shows this."""
    key = CMD_NOMATCH
    locks = "cmd:all()"

    def func(self):
        self.caller.msg("You are unconscious.")
