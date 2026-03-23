"""
Clone / splinter system: soul-shard stored in a pod; on permanent death you may
return in a vat-grown body from the shard.

The shard records your natural baseline only: no cyberware, no cyberware-added
body parts, no implant overlays. Body descriptions are limited to racial
anatomy (see build_clone_snapshot). Awakening applies a fresh, healthy body
(see apply_clone_snapshot).
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


def _remove_db_attr(character, name):
    try:
        if hasattr(character.db, name):
            character.attributes.remove(name)
    except KeyError:
        pass


def build_clone_snapshot(character):
    """
    Build a snapshot for the soul-shard: stats, skills, identity, and *natural*
    appearance only. Omits cyberware, implant-added anatomy, and locked/appended
    chrome text — the vat body is grown without chrome. Body description keys
    are limited to racial anatomy (world.races.get_race_body_parts).
    """
    if not character or not getattr(character, "db", None):
        return None
    from world.races import get_race_body_parts

    race = getattr(character.db, "race", "human") or "human"
    natural_parts = get_race_body_parts(race)
    raw_desc = dict(getattr(character.db, "body_descriptions", None) or {})
    body_descriptions = {part: (raw_desc.get(part) or "") for part in natural_parts}
    from world.rpg.factions import get_character_factions

    snapshot = {
        "key": character.key,
        "stats": dict(getattr(character.db, "stats", {}) or {}),
        "skills": dict(getattr(character.db, "skills", {}) or {}),
        "body_descriptions": body_descriptions,
        "race": race,
        "splicer_animal": getattr(character.db, "splicer_animal", None),
        "traits": list(getattr(character.db, "traits", []) or []),
        "pronoun": getattr(character.db, "pronoun", "neutral"),
        "xp": int(getattr(character.db, "xp", 0) or 0),
        "fragmented_at": time.time(),
        "skin_tone": getattr(character.db, "skin_tone", None),
        "skin_tone_code": getattr(character.db, "skin_tone_code", None),
        "skin_tone_set": getattr(character.db, "skin_tone_set", False),
        "gender": getattr(character.db, "gender", None),
        "height_cm": getattr(character.db, "height_cm", None),
        "weight_kg": getattr(character.db, "weight_kg", None),
        "height_category": getattr(character.db, "height_category", None),
        "weight_category": getattr(character.db, "weight_category", None),
        "age_years": getattr(character.db, "age_years", None),
        "addictions": dict(getattr(character.db, "addictions", None) or {}),
        "known_recipes": list(getattr(character.db, "known_recipes", None) or []),
        "cyberpsychosis_score": int(getattr(character.db, "cyberpsychosis_score", 0) or 0),
    }
    _trust = dict(getattr(character.db, "trust", None) or {})
    snapshot["trust"] = {k: list(v) if isinstance(v, (set, list)) else list(v) for k, v in _trust.items()}
    snapshot["factions"] = {}
    for fdata in get_character_factions(character):
        faction_key = fdata["key"]
        rank = (character.db.faction_ranks or {}).get(faction_key, 1)
        joined = (character.db.faction_joined or {}).get(faction_key)
        snapshot["factions"][faction_key] = {
            "rank": rank,
            "joined": joined,
        }
    snapshot["faction_pay_collected"] = dict(getattr(character.db, "faction_pay_collected", None) or {})
    return snapshot


def apply_clone_snapshot(character, snapshot):
    """
    Apply a clone snapshot to a vat-grown body: stats, skills, natural body text,
    race, traits, pronoun. Always clears cyberware state and trauma — the shard
    never carried chrome; the new body is whole and healthy.
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
    if "race" in snapshot:
        character.db.race = snapshot.get("race") or "human"
    if "splicer_animal" in snapshot:
        character.db.splicer_animal = snapshot.get("splicer_animal")
    if "traits" in snapshot:
        character.db.traits = list(snapshot["traits"])
    if "pronoun" in snapshot:
        character.db.pronoun = snapshot["pronoun"]
    if "xp" in snapshot:
        character.db.xp = int(snapshot["xp"])
    if "skin_tone" in snapshot:
        character.db.skin_tone = snapshot.get("skin_tone")
    if "skin_tone_code" in snapshot:
        character.db.skin_tone_code = snapshot.get("skin_tone_code")
    if "skin_tone_set" in snapshot:
        character.db.skin_tone_set = bool(snapshot.get("skin_tone_set"))
    if "gender" in snapshot and snapshot.get("gender") is not None:
        character.db.gender = snapshot.get("gender")
    if "height_cm" in snapshot:
        character.db.height_cm = snapshot.get("height_cm")
    if "weight_kg" in snapshot:
        character.db.weight_kg = snapshot.get("weight_kg")
    if "height_category" in snapshot:
        character.db.height_category = snapshot.get("height_category")
    if "weight_category" in snapshot:
        character.db.weight_category = snapshot.get("weight_category")
    if "age_years" in snapshot:
        character.db.age_years = snapshot.get("age_years")

    faction_data = snapshot.get("factions") or {}
    if faction_data:
        from world.rpg.factions import get_faction

        faction_ranks = {}
        faction_joined = {}
        for faction_key, finfo in faction_data.items():
            fdata = get_faction(faction_key)
            if not fdata:
                continue
            character.tags.add(fdata["tag"], category=fdata["tag_category"])
            faction_ranks[faction_key] = finfo.get("rank", fdata.get("default_rank", 1))
            faction_joined[faction_key] = finfo.get("joined")
        character.db.faction_ranks = faction_ranks
        character.db.faction_joined = faction_joined
    character.db.faction_pay_collected = dict(snapshot.get("faction_pay_collected") or {})

    if "addictions" in snapshot:
        character.db.addictions = dict(snapshot.get("addictions") or {})
    if "known_recipes" in snapshot:
        character.db.known_recipes = list(snapshot.get("known_recipes") or [])
    if "cyberpsychosis_score" in snapshot:
        character.db.cyberpsychosis_score = int(snapshot.get("cyberpsychosis_score") or 0)
    if "trust" in snapshot:
        tdat = snapshot.get("trust") or {}
        character.db.trust = {str(k): set(v) for k, v in tdat.items()}

    character.db.needs_chargen = False
    # Restrict stored naked descriptions to racial anatomy (legacy shards may have extra keys).
    from world.races import get_race_body_parts

    _race = getattr(character.db, "race", "human") or "human"
    _natural = get_race_body_parts(_race)
    _bd = dict(getattr(character.db, "body_descriptions", None) or {})
    character.db.body_descriptions = {p: _bd.get(p, "") for p in _natural}
    # No cyberware on a shard-grown body (snapshot never stored implants).
    character.db.extra_body_parts = []
    character.db.cyberware = []
    character.db.locked_descriptions = {}
    character.db.appended_descriptions = {}
    # Fresh body: full HP/stamina, intact limbs and organs, no wounds
    if hasattr(character, "max_hp"):
        character.db.current_hp = character.max_hp
    if hasattr(character, "max_stamina"):
        character.db.current_stamina = character.max_stamina
    character.db.missing_body_parts = []
    character.db.organ_damage = {}
    character.db.limb_damage = {}
    character.db.fractures = []
    character.db.injuries = []
    character.db.bleeding_level = 0
    character.db.stabilized_organs = {}
    character.db.splinted_bones = []
    character.db.bandaged_body_parts = []
    character.db.surgery_in_progress = False
    for attr in (
        "tourniquet_applied",
        "tourniquet_ticks",
        "bleeding_hemostatic_stabilized",
        "bleeding_hemostatic_at",
        "tourniquet_at",
        "flatline_at",
    ):
        _remove_db_attr(character, attr)

    try:
        from world.combat.tickers import remove_both_combat_tickers

        remove_both_combat_tickers(character, None)
    except Exception:
        pass

    character.db.grappling = None
    character.db.grappled_by = None
    try:
        from world.combat.grapple import clear_grapple_cmdsets_on_clone_reset

        clear_grapple_cmdsets_on_clone_reset(character)
    except Exception:
        pass
    character.db.combat_target = None
    character.db.sedated_until = 0.0

    try:
        from world.combat.cover import clear_cover_state

        clear_cover_state(character, reset_pose=False)
    except Exception:
        character.db.in_cover = False
        character.db.cover_hp = 0

    character.db.room_pose = "standing here"
    character.db.death_state = None

    try:
        character.ndb._medical_session_log = None
    except Exception:
        pass


def _splinter_narrative_step(character_id, step_index):
    """One step of the splinter narrative; schedules next or stores snapshot."""
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
    delay(2.5, _splinter_narrative_step, character.id, 1)


def _awakening_narrative_step(account_id, step_index, clone_char_id, spawn_room_id):
    """One step of the awakening narrative; at the end puppets account to clone and clears temp data."""
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
            for session in acc.sessions.get() or []:
                try:
                    acc.puppet_object(session, clone_char)
                except Exception:
                    pass
        # Clear death-lobby state (shard consumed in CmdGoShard)
        if acc and hasattr(acc, "db"):
            for key in ("dead_character_name", "dead_character_corpse", "clone_snapshot_backup"):
                try:
                    if hasattr(acc.db, key):
                        acc.attributes.remove(key)
                except KeyError:
                    pass
                except Exception:
                    pass
    except Exception:
        pass


def run_awakening_sequence(account, clone_character, spawn_room):
    """Run the awakening narrative then puppet account to clone_character in spawn_room."""
    if not account or not clone_character:
        return
    account.msg(AWAKENING_NARRATIVE[0])
    delay(
        2.2,
        _awakening_narrative_step,
        account.id,
        1,
        clone_character.id,
        spawn_room.id if spawn_room else None,
    )


def get_clone_spawn_room():
    """Return the room where clones awaken (tagged 'clone_spawn'). Creates one if missing.
    Builders: stand in a room and type |wbuclone_spawn|n to tag it, or |wbutag here = clone_spawn|n."""
    from evennia.utils.search import search_tag

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
