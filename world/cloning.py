"""
Clone / splinter system: soul-shard stored in a pod; on permanent death you may
return in a vat-grown body from the shard. Snapshot = stats, skills, appearance only (no items).
"""
import time
from evennia.utils.search import search_object
from evennia.utils.create import create_object
from evennia.utils import delay

# ---- Splintering narrative (Warhammer 40k / brutal, soul torn) ----
SPLINTER_NARRATIVE = [
    "|xThe crown of needles descends.|n",
    "|rYou feel it before you hear it — a frequency that is not sound. Your teeth vibrate. Your bones answer.|n",
    "|rThe light is wrong. It comes from nowhere and everywhere. The walls are breathing.|n",
    "|xSomething pierces. Not skin. Not flesh. |rDeeper.|n",
    "|RThey are in your head. In the place where you end and the world begins. They are |rtaking|R.|n",
    "|rYour soul is not one thing. It is a |xthousand shards|r. One of them is being |Rprised loose|r.|n",
    "|xYou cannot scream. You are not allowed. The mechanism does not care. It has done this before.|n",
    "|rA piece of you |Rtears|r. Not metaphor. Not poetry. |xSomething that was you is no longer.|n",
    "|xThe pod stores it. A sliver. A backup. The rest of you is still whole. You think. You hope.|n",
    "|RThe needles withdraw. The hum fades. You are still you. Mostly.|n",
    "|gThe splinter is sealed. If you die, truly die — you may wake again. In another body. With a price.|n",
]

# ---- Clone awakening narrative (biohorror, soul shard into homunculus) ----
AWAKENING_NARRATIVE = [
    "|xThere is no light. There is no dark. There is only |rwaiting|n.|n",
    "|rSomething |Rclicks|r. Fluids drain. The vat is opening.|n",
    "|xThe body is not yours. It was grown. It was |rempty|n. Now it is not.|n",
    "|RYour shard finds purchase. Nerves that were never yours |xignite|r. You feel |rlungs|n. |rHeart|n. |rBone|n.|n",
    "|xThe homunculus |rstirs|n. The soul-fragment |Rseats|r. Something that was dead is |rnot quite alive|n.|n",
    "|rYou open eyes that have never seen. You breathe with a chest that has never drawn air.|n",
    "|xThe chamber is sterile. Cold. You are |rnew|n. You are |Rold|n. You are |rboth|n and |Rneither|n.|n",
    "|gYou stand. The shard holds. You are you. Again. For now.|n",
]


def build_clone_snapshot(character):
    """
    Build a snapshot of the character for cloning: stats, skills, appearance, background.
    No inventory, no wounds, no worn gear. Returns a dict that apply_clone_snapshot can restore.
    """
    if not character or not getattr(character, "db", None):
        return None
    from world.medical import BODY_PARTS
    snapshot = {
        "key": character.key,
        "stats": dict(getattr(character.db, "stats", {}) or {}),
        "skills": dict(getattr(character.db, "skills", {}) or {}),
        "body_descriptions": dict(getattr(character.db, "body_descriptions", {}) or {}),
        "background": getattr(character.db, "background", "Unknown"),
        "traits": list(getattr(character.db, "traits", []) or []),
        "pronoun": getattr(character.db, "pronoun", "neutral"),
        "xp": int(getattr(character.db, "xp", 0) or 0),
        "fragmented_at": time.time(),
    }
    # Ensure body_descriptions has all parts (fill missing with empty)
    for part in BODY_PARTS:
        if part not in snapshot["body_descriptions"]:
            snapshot["body_descriptions"][part] = ""
    return snapshot


def apply_clone_snapshot(character, snapshot):
    """
    Apply a clone snapshot to a character. Overwrites stats, skills, body_descriptions,
    background, traits, pronoun. Does not touch inventory, wounds, or worn.
    """
    if not character or not snapshot:
        return
    character.key = snapshot.get("key", character.key)
    if "stats" in snapshot:
        character.db.stats = dict(snapshot["stats"])
    if "skills" in snapshot:
        character.db.skills = dict(snapshot["skills"])
    if "body_descriptions" in snapshot:
        character.db.body_descriptions = dict(snapshot["body_descriptions"])
    if "background" in snapshot:
        character.db.background = snapshot["background"]
    if "traits" in snapshot:
        character.db.traits = list(snapshot["traits"])
    if "pronoun" in snapshot:
        character.db.pronoun = snapshot["pronoun"]
    if "xp" in snapshot:
        character.db.xp = int(snapshot["xp"])
    character.db.needs_chargen = False
    # Fresh body: full HP/stamina, no trauma
    if hasattr(character, "max_hp"):
        character.db.current_hp = character.max_hp
    if hasattr(character, "max_stamina"):
        character.db.current_stamina = character.max_stamina
    for attr in ("organ_damage", "fractures", "bleeding_level", "injuries",
                 "stabilized_organs", "splinted_bones", "bandaged_body_parts"):
        if hasattr(character.db, attr):
            try:
                del character.db[attr]
            except Exception:
                pass
    character.db.room_pose = "standing here"
    character.db.death_state = None


def _splinter_narrative_step(character_id, step_index):
    """One step of the splinter narrative; schedules next or stores snapshot."""
    from evennia.utils.search import search_object
    from evennia.utils import delay
    try:
        result = search_object("#%s" % character_id)
        if not result:
            return
        character = result[0]
    except Exception:
        return
    if step_index < len(SPLINTER_NARRATIVE):
        character.msg(SPLINTER_NARRATIVE[step_index])
        delay(2.5, _splinter_narrative_step, character_id, step_index + 1)
    else:
        snapshot = build_clone_snapshot(character)
        if snapshot:
            character.db.clone_snapshot = snapshot
        else:
            character.msg("|rSomething went wrong. The mechanism did not take.|n")


def run_splinter_sequence(character):
    """Start the splinter narrative; at the end stores clone_snapshot on character."""
    if not character:
        return
    character.msg(SPLINTER_NARRATIVE[0])
    from evennia.utils import delay
    delay(2.5, _splinter_narrative_step, character.id, 1)


def _awakening_narrative_step(account_id, step_index, clone_char_id, spawn_room_id):
    """One step of the awakening narrative; at the end puppets account to clone and clears temp data."""
    from evennia.utils.search import search_object
    from evennia.utils import delay
    if step_index < len(AWAKENING_NARRATIVE):
        try:
            from evennia.accounts.accounts import AccountDB
            acc = AccountDB.objects.get(id=account_id)
            if acc and hasattr(acc, "msg"):
                acc.msg(AWAKENING_NARRATIVE[step_index])
        except Exception:
            pass
        delay(2.2, _awakening_narrative_step, account_id, step_index + 1, clone_char_id, spawn_room_id)
        return
    # Done: puppet to clone
    try:
        result = search_object("#%s" % clone_char_id)
        spawn_result = search_object("#%s" % spawn_room_id) if spawn_room_id else []
        if not result:
            return
        clone_char = result[0]
        spawn_room = spawn_result[0] if spawn_result else get_clone_spawn_room()
        if spawn_room and clone_char.location != spawn_room:
            clone_char.move_to(spawn_room)
        from evennia.accounts.accounts import AccountDB
        acc = AccountDB.objects.get(id=account_id)
        if acc and hasattr(acc, "sessions") and hasattr(acc, "puppet_object"):
            # Suppress "You become X" for clone awakening (handled in Character.at_post_puppet)
            try:
                clone_char.db._suppress_become_message = True
            except Exception:
                pass
            for session in (acc.sessions.get() or []):
                try:
                    acc.puppet_object(session, clone_char)
                except Exception:
                    pass
        # Clear death-lobby state (shard is consumed from corpse in CmdGoShard)
        if acc and hasattr(acc, "db"):
            for key in ("dead_character_name", "dead_character_corpse"):
                if hasattr(acc.db, key):
                    try:
                        del acc.db[key]
                    except Exception:
                        pass
    except Exception:
        pass


def run_awakening_sequence(account, clone_character, spawn_room):
    """Run the awakening narrative then puppet account to clone_character in spawn_room."""
    if not account or not clone_character:
        return
    account.msg(AWAKENING_NARRATIVE[0])
    from evennia.utils import delay
    delay(2.2, _awakening_narrative_step,
          account.id, 1,
          clone_character.id, spawn_room.id if spawn_room else None)


def get_clone_spawn_room():
    """Return the room where clones awaken (tagged 'clone_spawn'). Creates one if missing.
    Builders: stand in a room and type |wbuclone_spawn|n to tag it, or |wbutag here = clone_spawn|n."""
    from evennia.utils.search import search_tag
    from evennia.utils.create import create_object
    rooms = search_tag(key="clone_spawn")
    if rooms:
        return rooms[0]
    room = create_object(
        "typeclasses.rooms.Room",
        key="Clone Awakening Bay",
        location=None,
    )
    if room:
        room.tags.add("clone_spawn")
        room.db.desc = (
            "A sterile, low-lit chamber. Vat racks line the walls; the air smells of "
            "antiseptic and something older, coppery. This is where the shards wake."
        )
    return room
