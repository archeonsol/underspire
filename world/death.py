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


def is_character_logged_off(character):
    """True if character has no connected sessions (player is logged off / sleeping)."""
    if not character or not getattr(character, "sessions", None):
        return True
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
    if hasattr(character, "get_stat_level"):
        end = character.get_stat_level("endurance") or 0
    return base + (end * FLATLINE_SECONDS_PER_ENDURANCE)


def is_flatlined(obj):
    """True if character is in flatlined state (0 HP, can be defibbed)."""
    return getattr(obj.db, "death_state", None) == DEATH_STATE_FLATLINED


def is_permanently_dead(obj):
    """True if character has been permanently killed (or already converted to corpse)."""
    return getattr(obj.db, "death_state", None) == DEATH_STATE_PERMANENT


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
    character.msg(FLATLINE_MESSAGE)
    if attacker and attacker != character and hasattr(attacker, "msg"):
        attacker.msg(FLATLINE_ATTACKER_MESSAGE.format(name=character.name))
    try:
        from world.combat import remove_both_combat_tickers
        remove_both_combat_tickers(character, attacker)
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
    make_permanent_death(character, attacker=None, reason="time")


def _get_or_create_limbo():
    """Return the Death Lobby room, creating it if it doesn't exist. Always set description so existing rooms get it."""
    from evennia.utils.search import search_object
    from evennia.utils.create import create_object
    rooms = search_object(tag="death_limbo")
    if rooms:
        limbo = rooms[0]
        limbo.db.desc = DEATH_LOBBY_DESC
        return limbo
    limbo = create_object(
        "typeclasses.limbo.DeathLimbo",
        key="Death Lobby",
        location=None,
    )
    if limbo:
        limbo.tags.add("death_limbo")
        limbo.db.desc = DEATH_LOBBY_DESC
    return limbo


def _get_or_create_spirit(account, limbo):
    """Return a Spirit for this account, creating and storing it if needed. Moves spirit to limbo."""
    from evennia.utils.create import create_object
    spirit = getattr(account.db, "death_spirit", None)
    if spirit and hasattr(spirit, "location") and spirit.id:
        spirit.move_to(limbo)
        return spirit
    spirit = create_object(
        "typeclasses.limbo.Spirit",
        key="Spirit of %s" % account.key,
        location=limbo,
    )
    if spirit:
        account.db.death_spirit = spirit
    return spirit


def _send_account_to_limbo(account, sessions, dead_character_name):
    """Puppet the account's spirit in the Death Lobby and send a message."""
    limbo = _get_or_create_limbo()
    if not limbo:
        if hasattr(account, "msg"):
            account.msg("|rYou have died. You are in the void. (Limbo room could not be created.)|n")
        return
    spirit = _get_or_create_spirit(account, limbo)
    if not spirit:
        if hasattr(account, "msg"):
            account.msg("|rYou have died. (Spirit could not be created.)|n")
        return
    for session in sessions:
        try:
            if hasattr(account, "puppet_object"):
                account.puppet_object(session, spirit)
        except Exception:
            pass
    if hasattr(account, "msg"):
        account.msg(
            "|rYou have permanently died.|n\n"
            "|yYou wake in a dim, quiet space. No pain. No body. Just you and a sign that says "
            "PLEASE WAIT. Welcome to Hell. Make yourself at home. Type |wlook|n when you're ready.|n"
        )


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
    # Unpuppet all sessions, then send each account to the Death Lobby (limbo)
    account_sessions = {}  # account -> list of sessions
    try:
        for session in character.sessions.get():
            try:
                acc = getattr(session, "account", None)
                if hasattr(session, "unpuppet"):
                    session.unpuppet()
                elif acc and hasattr(acc, "unpuppet_object"):
                    acc.unpuppet_object(session)
                if acc:
                    account_sessions.setdefault(acc, []).append(session)
            except Exception:
                pass
        for acc, sessions in account_sessions.items():
            _send_account_to_limbo(acc, sessions, name)
    except Exception:
        pass
    # Convert to corpse (swap typeclass); key by pronoun so "male corpse", "female corpse", "neuter corpse"
    pronoun = getattr(character.db, "pronoun", None) or "neutral"
    corpse_key = CORPSE_KEY_BY_PRONOUN.get(pronoun, "neuter corpse")
    try:
        character.swap_typeclass("typeclasses.corpse.Corpse", clean_attributes=False, no_default=True)
        character.db.original_name = name
        character.db.corpse_pronoun = pronoun  # for look: "body of a man/woman/neuter"
        character.db.death_time = time.time()  # when they became a corpse (for logs/future use)
        character.key = corpse_key
        # Remove the dead character's aliases (e.g. "Cairn") so the corpse is only findable as "corpse" / "neuter corpse" etc.
        try:
            character.aliases.clear()
            character.aliases.add("corpse")
            character.aliases.add(corpse_key)
        except Exception:
            pass
        if hasattr(character.db, "room_pose"):
            del character.db.room_pose
        try:
            character.locks.add("get:all()")
        except Exception:
            pass
        try:
            character.locks.add("puppet:false()")
        except Exception:
            pass
        # Wipe the Character's cmdset_storage (persistent DB) so the corpse doesn't keep
        # look/get/wield etc. and get merged for everyone in the room as an "interactive" object.
        try:
            del character.cmdset_storage
        except Exception:
            try:
                character.cmdset_storage = []
            except Exception:
                pass
        try:
            character.cmdset.cmdset_stack = []
            character.cmdset.update()
        except Exception:
            pass
        if loc:
            if reason == "executed" and attacker and attacker != character:
                try:
                    from world.combat import _get_attacker_weapon_key
                    weapon_key = _get_attacker_weapon_key(attacker)
                except Exception:
                    weapon_key = "fists"
                attacker_msg = EXECUTE_ATTACKER_MSG.get(weapon_key, EXECUTE_ATTACKER_MSG["fists"])
                room_msg = EXECUTE_ROOM_MSG.get(weapon_key, EXECUTE_ROOM_MSG["fists"])
                if hasattr(attacker, "msg"):
                    attacker.msg(attacker_msg.format(name=name))
                loc.msg_contents(
                    room_msg.format(attacker=attacker.name, name=name),
                    exclude=(character, attacker),
                )
            else:
                loc.msg_contents(
                    "|r%s has slipped away. No pulse. No return. The body is still.|n" % name,
                    exclude=(character,),
                )
    except Exception as e:
        if loc:
            loc.msg_contents("|r%s has died.|n" % name, exclude=(character,))
        try:
            from evennia import logger
            logger.log_err("death.make_permanent_death swap_typeclass: %s" % e)
        except Exception:
            pass


def clear_flatline(target):
    """Clear flatlined state and flatline_at after successful resuscitation."""
    if not target or not hasattr(target, "db"):
        return
    target.db.death_state = DEATH_STATE_ALIVE
    if hasattr(target.db, "flatline_at"):
        del target.db.flatline_at
    if getattr(target.db, "room_pose", None) == "lying here, dead.":
        target.db.room_pose = "standing here"
