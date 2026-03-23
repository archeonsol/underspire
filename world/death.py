"""
Death and dying: flatlined (can be defibbed) vs permanent (corpse).
When HP reaches 0, character enters flatlined state. After a duration (endurance-based, min 5 min)
or if executed by another, they become permanently dead and turn into a corpse.
"""
import time
from evennia.utils import delay

DEATH_STATE_ALIVE = None
DEATH_STATE_FLATLINED = "flatlined"
DEATH_STATE_PERMANENT = "permanent"

# Minimum time in flatline before permanent death (seconds)
FLATLINE_MIN_SECONDS = 300  # 5 minutes
# Extra seconds per endurance point (0-300 scale); total = FLATLINE_MIN_SECONDS + endurance * 6
FLATLINE_SECONDS_PER_ENDURANCE = 6

# Big message when you drop to 0 HP and enter flatline
FLATLINE_MESSAGE = """
|r
================================================================================
  YOU HAVE LOST CONSCIOUSNESS
================================================================================
  Your legs give. The ground comes up. The pain is there and then it is not.
  Something turns off. You do not get to see what happens next.
  You are dying. There is no sound. No light. Only the slow fade.
  Someone might still bring you back. Or time might run out.
================================================================================
|n"""

# Message to attacker when someone drops
FLATLINE_ATTACKER_MESSAGE = "|y{name} goes down and does not get up. The fight is over. You are still standing. They are not. That is the only difference that matters.|n"

# Room message when someone flatlines (customizable via character.db.flatline_room_msg; use {name} for their name)
DEFAULT_FLATLINE_ROOM_MSG = "{name} falls over and begins to die."

# Death Lobby room description (set on limbo whenever we get/create it so existing rooms get it too)
DEATH_LOBBY_DESC = (
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

# Execute: weapon-class messages when you end a flatlined character. {name} = victim name. Visceral.
EXECUTE_ATTACKER_MSG = {
    "fists": "|rYou finish them. Your hands around their throat, or a last blow to the head. They stop moving. You let go. It is over.|n",
    "knife": "|rYou put the blade to their throat and draw it across. Or one last thrust. The blood runs. They are gone. You wipe the steel.|n",
    "long_blade": "|rYou bring the edge down. One clean stroke, or several. The body goes still. You step back. The blade is red. They will not get up.|n",
    "blunt": "|rYou raise the weapon and end it. The impact is final. Something gives. They do not move again. You lower it. Done.|n",
    "sidearm": "|rYou level the gun. One shot. Or two. The crack echoes. They jerk and then lie still. You holster. No pulse. No second chances.|n",
    "longarm": "|rYou sight and squeeze. The round finds them. They drop for good. You work the action. The room is quiet. They are gone.|n",
    "automatic": "|rYou put a burst into them. No doubt. No movement after. You release the trigger. Smoke. Silence. They are finished.|n",
}
EXECUTE_ROOM_MSG = {
    "fists": "|r{attacker} ends {name}. No struggle left. The body goes still. It is over.|n",
    "knife": "|r{attacker} draws the blade across {name}, or drives it home. Blood. Then nothing. They are gone.|n",
    "long_blade": "|r{attacker}'s blade falls. {name} does not move again. The edge is red. Over.|n",
    "blunt": "|r{attacker} brings the weapon down. A last, final impact. {name} is still. Done.|n",
    "sidearm": "|rA shot. {attacker} has put one into {name}. No pulse. No return. They are gone.|n",
    "longarm": "|rA bullet into the brain. {attacker} has ended {name}. The body lies still. No coming back.|n",
    "automatic": "|rA short burst. {attacker} has finished {name}. The body does not move. It is over.|n",
}

# Pronoun -> corpse key for room/look display (male/female/neuter corpse)
CORPSE_KEY_BY_PRONOUN = {"male": "male corpse", "female": "female corpse", "neutral": "neuter corpse"}

# Seconds a character must be logged off before others can get/strip from them (safe-keep for sleeping)
LOGGED_OFF_TAKE_AFTER_SECONDS = 30 * 60  # 30 minutes


def _log_limbo_error(step, err):
    """Log death-lobby errors for debugging."""
    try:
        from evennia import logger
        logger.log_err("death._send_account_to_limbo %s: %s" % (step, err))
    except Exception:
        pass


def _log_death_step(step, err):
    """Log make_permanent_death sub-step failures."""
    try:
        from evennia import logger
        logger.log_err("death.make_permanent_death %s: %s" % (step, err))
    except Exception:
        pass


def account_has_stored_clone(account):
    """True if corpse carries clone_snapshot or account has clone_snapshot_backup."""
    if not account or not getattr(account, "db", None):
        return False
    corpse = getattr(account.db, "dead_character_corpse", None)
    if corpse and getattr(corpse, "db", None) and getattr(corpse.db, "clone_snapshot", None):
        return True
    return bool(getattr(account.db, "clone_snapshot_backup", None))


def is_character_multi_puppeted(character):
    """True if character is in an account's multi-puppet set and that account has a session (staff multi-puppeting)."""
    if not character or not getattr(character, "db", None):
        return False
    account_id = getattr(character.db, "_multi_puppet_account_id", None)
    if account_id is None:
        return False
    try:
        from evennia.accounts.accounts import DefaultAccount
        account = DefaultAccount.objects.get_account_from_uid(int(account_id))
    except (TypeError, ValueError, AttributeError):
        return False
    if not account or not getattr(account, "sessions", None):
        return False
    return bool(account.sessions.get() if hasattr(account.sessions, "get") else [])


def is_character_logged_off(character):
    """True if character has no connected sessions (player is logged off / sleeping).
    NPCs and multi-puppeted characters are always treated as present (never logged off).
    Objects that are not Characters (vehicles, items, rooms, etc.) are never "logged off."""
    if not character:
        return True
    try:
        from typeclasses.characters import Character

        if not isinstance(character, Character):
            return False
    except ImportError:
        pass
    if not getattr(character, "sessions", None):
        return True
    if getattr(character.db, "is_npc", False):
        return False  # NPCs act like they are always logged on
    if is_character_multi_puppeted(character):
        return False  # In someone's multi-puppet set with an active session = "present"
    try:
        return not character.sessions.get()
    except Exception:
        return True


def character_logged_off_long_enough(character):
    """True if character is logged off and has been for 30+ minutes (can get/strip from them)."""
    if not character or not getattr(character, "db", None):
        return False
    if not is_character_logged_off(character):
        return False
    logout_time = getattr(character.db, "last_logout_time", None)
    if logout_time is None:
        return False  # never recorded logout (e.g. old character)
    return (time.time() - logout_time) >= LOGGED_OFF_TAKE_AFTER_SECONDS


def get_flatline_duration_seconds(character):
    """Seconds until flatlined character becomes permanently dead. Minimum 5 minutes; endurance adds time."""
    base = FLATLINE_MIN_SECONDS
    end = 0
    if hasattr(character, "get_display_stat"):
        end = character.get_display_stat("endurance")
    elif hasattr(character, "get_stat_level"):
        end = (character.get_stat_level("endurance") or 0) // 2
    return base + (end * FLATLINE_SECONDS_PER_ENDURANCE)


def is_flatlined(obj):
    """True if character is in flatlined state (0 HP, can be defibbed)."""
    return getattr(obj.db, "death_state", None) == DEATH_STATE_FLATLINED


def is_permanently_dead(obj):
    """True if character has been permanently killed (or already converted to corpse)."""
    return getattr(obj.db, "death_state", None) == DEATH_STATE_PERMANENT


def _room_pose_is_flatline_dead_placeholder(text):
    """
    True if room_pose (or @tp) matches the flatline corpse line from make_flatlined.
    Normalized so minor edits (spacing, final period, case) still clear on resuscitation/@restore.
    """
    p = (text or "").strip().lower().rstrip(".")
    return p == "lying here, dead"


def character_can_act(character, allow_builders=True):
    """
    Central check for whether a character can act (not flatlined, not permanently dead).
    Returns (can_act: bool, block_message: str or None). If can_act is False, block_message
    is the message to show the caller. Used by Command.at_pre_cmd and CmdLook.
    If allow_builders is True and character's account has Builder/Admin, returns (True, None).
    """
    if not character:
        return True, None
    try:
        if allow_builders and getattr(character, "account", None):
            if character.account.permissions.check("Builder") or character.account.permissions.check("Admin"):
                return True, None
    except Exception:
        pass
    try:
        if is_flatlined(character):
            return False, "|rYou are dying. There is nothing you can do.|n"
        if is_permanently_dead(character):
            return False, "|rYou are dead. Only an administrator can help you now.|n"
    except Exception:
        pass
    hp = getattr(character, "hp", None)
    if hp is not None and hp <= 0:
        return False, "|rYou are dying. There is nothing you can do.|n"
    return True, None


def can_be_defibbed(obj):
    """True if target has hp <= 0 and is not permanently dead (so they can be revived)."""
    if not obj or not hasattr(obj, "db"):
        return False
    if is_permanently_dead(obj):
        return False
    return getattr(obj, "hp", 1) <= 0


def make_flatlined(character, attacker):
    """
    Put character into flatlined state: set death_state, flatline timestamp, show big message.
    Schedules permanent death after endurance-based duration.
    Call when HP first reaches 0 (e.g. from at_damage).
    """
    if not character or not hasattr(character, "db"):
        return
    if is_flatlined(character) or is_permanently_dead(character):
        return
    character.db.death_state = DEATH_STATE_FLATLINED
    character.db.flatline_at = time.time()
    character.db.combat_ended = True
    character.db.room_pose = "lying here, dead."
    try:
        # Remove the default character cmdset (index 0); remove() only affects stack[1:], so we must use remove_default().
        character.cmdset.remove_default()
        character.cmdset.add("commands.default_cmdsets.FlatlinedCmdSet", persistent=False)
    except Exception:
        pass
    # Echo customizable message to the room (per-viewer so sdesc/recog respected)
    loc = character.location
    if loc and hasattr(loc, "contents_get"):
        template = getattr(character.db, "flatline_room_msg", None) or DEFAULT_FLATLINE_ROOM_MSG
        for v in loc.contents_get(content_type="character"):
            if v == character:
                continue
            name = character.get_display_name(v) if hasattr(character, "get_display_name") else character.name
            try:
                room_msg = template.format(name=name)
            except (KeyError, ValueError):
                room_msg = template.replace("{name}", name)
            v.msg(room_msg)
    character.msg(FLATLINE_MESSAGE)
    if attacker and attacker != character and hasattr(attacker, "msg"):
        name_for_attacker = character.get_display_name(attacker) if hasattr(character, "get_display_name") else character.name
        attacker.msg(FLATLINE_ATTACKER_MESSAGE.format(name=name_for_attacker))
    try:
        from world.combat import remove_both_combat_tickers
        other = attacker if attacker else getattr(character.db, "combat_target", None)
        remove_both_combat_tickers(character, other)
    except Exception:
        pass
    try:
        from world.combat.grapple import release_grapple_forced
        victim = getattr(character.db, "grappling", None)
        if victim:
            def _flatline_grapple_msg(v):
                cname = character.get_display_name(v) if hasattr(character, "get_display_name") else character.name
                vname = victim.get_display_name(v) if hasattr(victim, "get_display_name") else victim.name
                return "%s's grip goes slack as they collapse; %s is free." % (cname, vname)
            release_grapple_forced(character, room_message=_flatline_grapple_msg)
    except Exception:
        pass
    sec = get_flatline_duration_seconds(character)
    delay(sec, _flatline_to_permanent_callback, character.id, persistent=True)


def _flatline_to_permanent_callback(character_id):
    """Called after flatline duration: convert to permanent death if still flatlined."""
    from evennia.utils.search import search_object
    from evennia.utils import logger
    try:
        result = search_object("#%s" % character_id)
        if not result:
            return
        character = result[0]
    except Exception as e:
        logger.log_trace("death._flatline_to_permanent_callback(#%s): %s" % (character_id, e))
        return
    if not is_flatlined(character):
        return
    if is_permanently_dead(character):
        return
    make_permanent_death(character, attacker=None, reason="time")


def _get_or_create_limbo():
    """Return the Death Lobby room, creating it if it doesn't exist. Always set description so existing rooms get it."""
    from evennia.utils.search import search_object_by_tag
    from evennia.utils.create import create_object
    try:
        rooms = search_object_by_tag(key="death_limbo")
    except Exception:
        rooms = []
    if rooms:
        limbo = rooms[0]
        if hasattr(limbo, "db"):
            limbo.db.desc = DEATH_LOBBY_DESC
        return limbo
    try:
        limbo = create_object(
            "typeclasses.limbo.DeathLimbo",
            key="Death Lobby",
            location=None,
            nohome=True,
        )
    except Exception as e:
        _log_limbo_error("create_limbo", e)
        return None
    if limbo:
        try:
            limbo.tags.add("death_limbo")
            limbo.db.desc = DEATH_LOBBY_DESC
        except Exception as e:
            _log_limbo_error("limbo_setup", e)
    return limbo


def _get_or_create_spirit(account, limbo):
    """Return a Spirit for this account, creating and storing it if needed. Moves spirit to limbo."""
    from evennia.utils.create import create_object
    spirit = getattr(account.db, "death_spirit", None)
    if spirit and hasattr(spirit, "location") and spirit.id:
        spirit.move_to(limbo)
        try:
            spirit.locks.add("puppet:all()")
        except Exception:
            pass
        # Ensure Spirit has death-lobby cmds (go light always; go shard only when account has clone)
        try:
            spirit.cmdset.clear()
            spirit.cmdset.add("commands.spirit_cmdset.SpiritCmdSet")
            spirit.cmdset.update()
            # Persist so command handler sees this cmdset when resolving Spirit as caller
            spirit.cmdset_storage = ["commands.spirit_cmdset.SpiritCmdSet"]
        except Exception:
            pass
        return spirit
    spirit = create_object(
        "typeclasses.limbo.Spirit",
        key="Spirit of %s" % account.key,
        location=limbo,
    )
    if spirit:
        account.db.death_spirit = spirit
        try:
            spirit.locks.add("puppet:all()")
        except Exception:
            pass
    return spirit


def _fail_unpuppet_sessions(account, sessions):
    """If we can't send to limbo, unpuppet so the account isn't left on the body when it becomes a corpse."""
    for session in sessions:
        try:
            if hasattr(account, "unpuppet_object"):
                account.unpuppet_object(session)
        except Exception as e:
            _log_limbo_error("unpuppet_on_fail", e)


def _ensure_limbo_room():
    """Return (limbo, None) or (None, error)."""
    try:
        limbo = _get_or_create_limbo()
        return limbo, None
    except Exception as e:
        _log_limbo_error("limbo", e)
        return None, e


def _ensure_spirit_on_limbo(account, limbo):
    """Return (spirit, None) or (None, error)."""
    try:
        spirit = _get_or_create_spirit(account, limbo)
        return spirit, None
    except Exception as e:
        _log_limbo_error("spirit", e)
        return None, e


def _puppet_sessions_to_spirit(account, sessions, spirit):
    for session in sessions:
        try:
            if hasattr(account, "puppet_object"):
                account.puppet_object(session, spirit)
        except Exception as e:
            _log_limbo_error("puppet_object", e)


def _send_death_lobby_messages(account, dead_character_name):
    """Death lobby text; dead_character_name reserved for future personalization."""
    if not hasattr(account, "msg"):
        return
    has_clone = account_has_stored_clone(account)
    account.msg(
        "|rYou have permanently died.|n\n"
        "|yYou wake in a dim, quiet space. No pain. No body. Just you and a sign that says "
        "PLEASE WAIT. Welcome to Hell. Make yourself at home. Type |wlook|n when you're ready.|n"
    )
    if has_clone:
        account.msg(
            "|yYou feel a sliver of yourself elsewhere — a shard. Type |wgo shard|n to wake in the clone. "
            "Or type |wgo light|n to let go and create a new character.|n"
        )
    else:
        account.msg("|yYou have no stored shard. Type |wgo light|n to let go and create a new character from the start.|n")


def _send_account_to_limbo(account, sessions, dead_character_name):
    """Puppet the account's spirit in the Death Lobby (replaces current puppet, no OOC) and send death message."""
    limbo, _err = _ensure_limbo_room()
    if not limbo:
        if hasattr(account, "msg"):
            account.msg("|rYou have died. You are in the void. (Limbo room could not be created.)|n")
        _fail_unpuppet_sessions(account, sessions)
        return
    spirit, _err = _ensure_spirit_on_limbo(account, limbo)
    if not spirit:
        if hasattr(account, "msg"):
            account.msg("|rYou have died. (Spirit could not be created.)|n")
        _fail_unpuppet_sessions(account, sessions)
        return
    _puppet_sessions_to_spirit(account, sessions, spirit)
    _send_death_lobby_messages(account, dead_character_name)


def _safe_swap_corpse_typeclass(character, name, pronoun, corpse_key, corpse_cyberware):
    """Swap to Corpse and set corpse-specific db. Returns True on success."""
    try:
        character.swap_typeclass("typeclasses.corpse.Corpse", clean_attributes=False, no_default=True)
        character.db.original_name = name
        character.db.corpse_pronoun = pronoun
        character.db.death_time = time.time()
        if corpse_cyberware:
            character.db.cyberware = corpse_cyberware
            character.db.cyberware_source_name = name
        character.key = corpse_key
        return True
    except Exception as e:
        _log_death_step("swap_typeclass", e)
        return False


def _safe_clear_corpse_aliases(character, corpse_key):
    try:
        character.aliases.clear()
        character.aliases.add("corpse")
        character.aliases.add(corpse_key)
    except Exception as e:
        _log_death_step("aliases", e)


def _safe_clear_room_pose(character):
    try:
        if hasattr(character.db, "room_pose"):
            character.attributes.remove("room_pose")
    except KeyError:
        pass
    except Exception as e:
        _log_death_step("clear_room_pose", e)


def _safe_corpse_locks(character):
    try:
        character.locks.add("get:all()")
    except Exception as e:
        _log_death_step("locks_get", e)
    try:
        character.locks.add("puppet:false()")
    except Exception as e:
        _log_death_step("locks_puppet", e)


def _safe_wipe_corpse_cmdsets(character):
    try:
        del character.cmdset_storage
    except Exception:
        try:
            character.cmdset_storage = []
        except Exception as e:
            _log_death_step("cmdset_storage", e)
    try:
        character.cmdset.cmdset_stack = []
        character.cmdset.update()
    except Exception as e:
        _log_death_step("cmdset_stack", e)


def _safe_remove_corpse_from_account_list(character, account_sessions):
    for acc in account_sessions:
        try:
            if hasattr(acc, "characters"):
                acc.characters.remove(character)
        except Exception as e:
            _log_death_step("account_characters_remove", e)


def _broadcast_simple_death_fallback(loc, character, name):
    """Minimal room notify when corpse conversion fails."""
    if not loc or not hasattr(loc, "contents_get"):
        return
    try:
        for v in loc.contents_get(content_type="character"):
            if v == character:
                continue
            n = character.get_display_name(v) if hasattr(character, "get_display_name") else name
            v.msg("|r%s has died.|n" % n)
    except Exception as e:
        _log_death_step("broadcast_simple_death_fallback", e)


def _safe_send_room_messages_on_permanent_death(loc, character, attacker, reason, predeath_names_by_viewer, name):
    if not loc or not hasattr(loc, "contents_get"):
        return
    try:
        if reason == "executed" and attacker and attacker != character:
            try:
                from world.combat import _get_attacker_weapon_key
                weapon_key = _get_attacker_weapon_key(attacker)
            except Exception:
                weapon_key = "fists"
            attacker_msg = EXECUTE_ATTACKER_MSG.get(weapon_key, EXECUTE_ATTACKER_MSG["fists"])
            room_msg = EXECUTE_ROOM_MSG.get(weapon_key, EXECUTE_ROOM_MSG["fists"])
            if hasattr(attacker, "msg"):
                name_for_attacker = predeath_names_by_viewer.get(
                    attacker,
                    character.get_display_name(attacker) if hasattr(character, "get_display_name") else name,
                )
                attacker.msg(attacker_msg.format(name=name_for_attacker))
            for v in loc.contents_get(content_type="character"):
                if v in (character, attacker):
                    continue
                victim_name_for_viewer = predeath_names_by_viewer.get(
                    v,
                    character.get_display_name(v) if hasattr(character, "get_display_name") else name,
                )
                attacker_name_for_viewer = (
                    attacker.get_display_name(v) if hasattr(attacker, "get_display_name") else attacker.name
                )
                v.msg(
                    room_msg.format(
                        attacker=attacker_name_for_viewer,
                        name=victim_name_for_viewer,
                    )
                )
        else:
            for v in loc.contents_get(content_type="character"):
                if v == character:
                    continue
                n = predeath_names_by_viewer.get(
                    v,
                    character.get_display_name(v) if hasattr(character, "get_display_name") else name,
                )
                v.msg("|r%s has slipped away. No pulse. No return. The body is still.|n" % n)
    except Exception as e:
        _log_death_step("room_messages", e)


def make_permanent_death(character, attacker=None, reason="executed"):
    """
    Convert flatlined character to permanent death: turn into corpse, unpuppet, room message.
    reason: "executed" or "time"
    """
    if not character or not hasattr(character, "db"):
        return
    if is_permanently_dead(character):
        return
    character.db.death_state = DEATH_STATE_PERMANENT
    loc = character.location
    name = character.name
    # Capture installed chrome before conversion so the corpse keeps installed hardware.
    # We intentionally do not call on_uninstall: the chrome is still in the body.
    corpse_cyberware = list(getattr(character.db, "cyberware", None) or [])
    character.db.cyberware = []
    # Send each account straight to Death Lobby by puppeting their Spirit (puppet_object
    # unpuppets the current character and puppets the spirit in one go — no OOC stop).
    account_sessions = {}
    try:
        for session in character.sessions.get():
            try:
                acc = getattr(session, "account", None)
                if acc:
                    account_sessions.setdefault(acc, []).append(session)
                    acc.db.dead_character_name = name
                    acc.db.dead_character_corpse = character
            except Exception as e:
                _log_death_step("collect_account_session", e)
    except Exception as e:
        _log_death_step("collect_sessions", e)

    clone_snap = getattr(character.db, "clone_snapshot", None)
    if clone_snap and account_sessions:
        try:
            snap_copy = dict(clone_snap)
            for acc in account_sessions:
                acc.db.clone_snapshot_backup = snap_copy
        except Exception as e:
            _log_death_step("clone_snapshot_backup", e)

    try:
        for acc, sessions in account_sessions.items():
            _send_account_to_limbo(acc, sessions, name)
    except Exception as e:
        _log_death_step("send_account_to_limbo", e)

    pronoun = getattr(character.db, "pronoun", None) or "neutral"
    corpse_key = CORPSE_KEY_BY_PRONOUN.get(pronoun, "neuter corpse")
    predeath_names_by_viewer = {}
    if loc and hasattr(loc, "contents_get"):
        for v in loc.contents_get(content_type="character"):
            if v == character:
                continue
            try:
                predeath_names_by_viewer[v] = (
                    character.get_display_name(v) if hasattr(character, "get_display_name") else name
                )
            except Exception:
                predeath_names_by_viewer[v] = name

    if not _safe_swap_corpse_typeclass(character, name, pronoun, corpse_key, corpse_cyberware):
        _broadcast_simple_death_fallback(loc, character, name)
        return

    try:
        from world.rpg.factions import FACTIONS

        for _fk, fd in FACTIONS.items():
            if character.tags.has(fd["tag"], category=fd["tag_category"]):
                character.tags.remove(fd["tag"], category=fd["tag_category"])
    except Exception as e:
        _log_death_step("strip_corpse_faction_tags", e)

    _safe_clear_corpse_aliases(character, corpse_key)
    _safe_clear_room_pose(character)
    _safe_corpse_locks(character)
    _safe_wipe_corpse_cmdsets(character)
    _safe_remove_corpse_from_account_list(character, account_sessions)
    _safe_send_room_messages_on_permanent_death(loc, character, attacker, reason, predeath_names_by_viewer, name)


def clear_flatline(target):
    """Clear flatlined state and flatline_at after successful resuscitation."""
    if not target or not hasattr(target, "db"):
        return
    target.db.death_state = DEATH_STATE_ALIVE
    try:
        if hasattr(target.db, "flatline_at"):
            target.attributes.remove("flatline_at")
    except KeyError:
        pass
    except Exception as e:
        try:
            from evennia import logger
            logger.log_err("death.clear_flatline flatline_at: %s" % e)
        except Exception:
            pass
    try:
        # add() uses the dotted path; remove() must match the same identifier or the set can stay on the stack.
        for _cs_key in ("commands.default_cmdsets.FlatlinedCmdSet", "FlatlinedCmdSet"):
            try:
                target.cmdset.remove(_cs_key)
            except Exception:
                pass
        from django.conf import settings

        char_cmdset = getattr(settings, "CMDSET_CHARACTER", "commands.default_cmdsets.CharacterCmdSet")
        target.cmdset.add_default(char_cmdset)
        try:
            target.cmdset.update()
        except Exception:
            pass
    except Exception:
        pass
    if _room_pose_is_flatline_dead_placeholder(getattr(target.db, "room_pose", None)):
        target.db.room_pose = "standing here"
    if _room_pose_is_flatline_dead_placeholder(getattr(target.db, "temp_room_pose", None)):
        try:
            if hasattr(target.db, "temp_room_pose"):
                target.attributes.remove("temp_room_pose")
        except Exception:
            try:
                del target.db.temp_room_pose
            except Exception:
                pass
