"""
Scavenge/loot commands: CmdScavenge, CmdLoot, CmdSkin, CmdButcher, CmdSever, _loot_finish.
"""

from evennia.utils import logger
from commands.base_cmds import Command, _command_character
from commands.inventory_cmds import _update_primary_wielded


def _loot_finish(caller_id, corpse_id):
    """Called after delay: mark corpse as looted by caller and show inventory."""
    from evennia.utils.search import search_object
    from evennia.utils.utils import list_to_string
    try:
        from typeclasses.corpse import Corpse
        from world.clothing import get_worn_items
    except ImportError as e:
        logger.log_trace("scavenge_cmds._loot_finish imports: %s" % e)
        return
    try:
        caller = search_object("#%s" % caller_id)
        corpse = search_object("#%s" % corpse_id)
    except Exception as e:
        logger.log_trace("scavenge_cmds._loot_finish search: %s" % e)
        return
    if not caller or not corpse:
        return
    caller = caller[0]
    corpse = corpse[0]
    if caller.location != corpse.location:
        caller.msg("You are no longer next to the corpse.")
        return
    looted_by = list(corpse.db.looted_by or [])
    if caller.id not in looted_by:
        looted_by.append(caller.id)
        corpse.db.looted_by = looted_by
    worn_objs = set(get_worn_items(corpse))
    contents = [o for o in corpse.contents if o != caller and o not in worn_objs]
    cname = corpse.get_display_name(caller)
    if not contents:
        caller.msg(f"You've gone through the pockets of {cname}. Nothing of interest.")
    else:
        names = [obj.get_display_name(caller) for obj in contents]
        caller.msg(f"You've gone through the pockets of {cname}. |wCarrying:|n " + list_to_string(names, endsep=" and ") + ".")
    caller.msg("You can take items with |wget <item> from %s|n." % cname)


class CmdScavenge(Command):
    """
    Search a tagged area for salvage using your Scavenging skill (int + per with a luck bonus).

    Usage:
      scavenge

    Only works in rooms tagged for scavenging, such as:
      - wildscavenge
      - urbanscavenge
    """

    key = "scavenge"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from evennia.utils import delay
        from world.skills import SKILL_STATS
        from world.scavenging import perform_scavenge, _pick_loot_table

        caller = _command_character(self)
        if not caller or not getattr(caller, "db", None) or not hasattr(caller.db, "stats"):
            self.caller.msg("You must be in character to scavenge.")
            return

        loc = getattr(caller, "location", None)
        if not loc or not hasattr(loc, "tags"):
            caller.msg("There is nothing here to scavenge.")
            return

        loot_table, env = _pick_loot_table(loc)
        if not loot_table:
            caller.msg("There is nothing here to scavenge.")
            return

        # Prevent spamming: simple per-character cooldown
        try:
            last = getattr(caller.db, "last_scavenge_at", None)
            import time
            now = time.time()
            if last and now - float(last) < 10:
                caller.msg("You just finished searching — give it a moment before you rummage again.")
                return
            caller.db.last_scavenge_at = now
        except Exception as e:
            logger.log_trace("scavenge_cmds.CmdScavenge cooldown: %s" % e)

        if getattr(caller.ndb, "is_scavenging", False):
            caller.msg("You are already picking through this place.")
            return

        caller.ndb.is_scavenging = True

        # Roll: scavenging skill uses intelligence + perception, plus luck display as a bonus modifier.
        stats = SKILL_STATS.get("scavenging", ["intelligence", "perception"])
        luck_bonus = int(caller.get_display_stat("luck")) if hasattr(caller, "get_display_stat") else 0
        level, final_roll = caller.roll_check(stats, "scavenging", modifier=luck_bonus)

        # Narrative: 10–15s of searching flavor, then resolve.
        import random

        env_text = "the concrete and rust" if env == "urban" else "the scrub and twisted growth"
        caller.msg(f"You start picking through {env_text}, eyes and hands working for anything useful...")
        if loc:
            loc.msg_contents(f"{caller.get_display_name(loc)} starts rummaging through the area for salvage.", exclude=caller)

        def _finish_scavenge():
            try:
                caller.ndb.is_scavenging = False
            except Exception as e:
                logger.log_trace("scavenge_cmds.CmdScavenge _finish is_scavenging clear: %s" % e)

            room = getattr(caller, "location", None)
            if not room:
                return

            obj = perform_scavenge(caller, room, final_roll)
            if not obj:
                caller.msg("You come up empty-handed this time.")
                return

            name = obj.get_display_name(caller) if hasattr(obj, "get_display_name") else obj.key
            caller.msg(f"|gYou find|n {name}|g while scavenging.|n")
            room.msg_contents(f"{caller.get_display_name(room)} straightens up, holding {name}|g.|n", exclude=caller)

        try:
            delay_time = random.randint(10, 15)
            delay(delay_time, _finish_scavenge)
        except Exception as e:
            logger.log_trace("scavenge_cmds.CmdScavenge delay: %s" % e)
            caller.msg("Something went wrong with the scavenge delay; you finish searching immediately.")
            _finish_scavenge()


class CmdSkin(Command):
    """
    Skin a corpse using your Scavenging skill to strip away hide or flesh.

    Usage:
      skin <corpse>
    """

    key = "skin"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from evennia.utils import delay
        from world.skills import SKILL_STATS

        caller = _command_character(self)
        if not caller or not getattr(caller, "db", None) or not hasattr(caller.db, "stats"):
            self.caller.msg("You must be in character to do that.")
            return

        # Require a short blade (knife-tier 1-3) wielded in hand.
        weapon = getattr(caller.db, "wielded_obj", None)
        weapon_key = getattr(caller.db, "wielded", None)
        if not weapon or getattr(weapon, "location", None) is not caller or weapon_key != "knife":
            caller.msg("You need a basic short blade in hand — one of the gutter knives, not some esoteric tool — before you can skin a body.")
            return

        args = (self.args or "").strip()
        target = caller.search(args or "corpse", location=caller.location)
        if not target:
            return

        try:
            from typeclasses.corpse import Corpse
            is_corpse = isinstance(target, Corpse)
        except Exception as e:
            logger.log_trace("scavenge_cmds.CmdSkin Corpse check: %s" % e)
            is_corpse = False
        if not is_corpse:
            caller.msg("You can only skin a corpse.")
            return

        if getattr(target.db, "skinned", False):
            caller.msg("This body has already been skinned.")
            return

        if getattr(caller.ndb, "is_skinning", False):
            caller.msg("You are already elbows-deep in another body.")
            return
        caller.ndb.is_skinning = True

        # Scavenging roll: intelligence + perception, with luck bonus.
        from world.skills import SKILL_STATS
        stats = SKILL_STATS.get("scavenging", ["intelligence", "perception"])
        luck_bonus = int(caller.get_display_stat("luck")) if hasattr(caller, "get_display_stat") else 0
        level, final_roll = caller.roll_check(stats, "scavenging", modifier=luck_bonus)

        is_creature = bool(getattr(target.db, "is_creature", False))
        corpse_name = target.get_display_name(caller) if hasattr(target, "get_display_name") else target.key

        caller.msg("|rYou kneel by {} and begin to work the blade under skin and cloth, peeling it back in long, wet strips...|n".format(corpse_name))
        if caller.location:
            caller.location.msg_contents(
                f"{caller.get_display_name(caller.location)} kneels by {corpse_name}, knife working in slow, deliberate strokes.",
                exclude=caller,
            )

        import random

        def _finish_skin():
            try:
                caller.ndb.is_skinning = False
            except Exception as e:
                logger.log_trace("scavenge_cmds.CmdSkin _finish_skin is_skinning: %s" % e)

            room = getattr(caller, "location", None)
            if not room or target.location != room:
                return

            # Simple difficulty: decent scavengers get reliable skins; bad ones slip and tear.
            difficulty = 55 if is_creature else 65
            if final_roll < difficulty:
                caller.msg("|rThe hide comes away in ragged, useless chunks. Whatever was here is ruined.|n")
                target.db.skinned = True
                return

            from evennia.utils.create import create_object

            key = "mutated hide" if is_creature else "human skin"
            desc = (
                "A broad, reeking sheet of warped flesh and hair, slick with strange growths and lesions."
                if is_creature
                else "A flensed sheet of human skin, pale and clammy, with faint impressions of where muscle once clung beneath."
            )
            try:
                hide = create_object("typeclasses.items.Item", key=key, location=caller)
                hide.db.desc = desc
                hide.tags.add("scavenged_hide")
            except Exception as e:
                logger.log_trace("scavenge_cmds.CmdSkin create_object hide: %s" % e)
                hide = None

            target.db.skinned = True

            caller.msg("|gYou work the blade free and lift away {}.|n".format("a sheet of warped hide" if is_creature else "a full, glistening layer of skin"))
            if room:
                room.msg_contents(
                    f"{caller.get_display_name(room)} peels the last of the flesh free, leaving the body skinned and slick.",
                    exclude=caller,
                )

        try:
            delay_time = random.randint(10, 15)
            delay(delay_time, _finish_skin)
        except Exception as e:
            logger.log_trace("scavenge_cmds.CmdSkin delay: %s" % e)
            _finish_skin()


class CmdButcher(Command):
    """
    Butcher a skinned corpse for organs using your Scavenging skill.

    Usage:
      butcher <corpse>
    """

    key = "butcher"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from evennia.utils import delay
        from world.skills import SKILL_STATS

        caller = _command_character(self)
        if not caller or not getattr(caller, "db", None) or not hasattr(caller.db, "stats"):
            self.caller.msg("You must be in character to do that.")
            return

        args = (self.args or "").strip()
        target = caller.search(args or "corpse", location=caller.location)
        if not target:
            return

        try:
            from typeclasses.corpse import Corpse
            is_corpse = isinstance(target, Corpse)
        except Exception as e:
            logger.log_trace("scavenge_cmds.CmdButcher Corpse check: %s" % e)
            is_corpse = False
        if not is_corpse:
            caller.msg("You can only butcher a corpse.")
            return

        if not getattr(target.db, "skinned", False):
            caller.msg("You need to skin the body before you can properly butcher it.")
            return

        if getattr(target.db, "butchered", False):
            caller.msg("There is nothing left inside this body worth taking.")
            return

        if getattr(caller.ndb, "is_butchering", False):
            caller.msg("You are already wrist-deep in another carcass.")
            return
        caller.ndb.is_butchering = True

        stats = SKILL_STATS.get("scavenging", ["intelligence", "perception"])
        luck_bonus = int(caller.get_display_stat("luck")) if hasattr(caller, "get_display_stat") else 0
        level, base_roll = caller.roll_check(stats, "scavenging", modifier=luck_bonus)

        is_creature = bool(getattr(target.db, "is_creature", False))
        corpse_name = target.get_display_name(caller) if hasattr(target, "get_display_name") else target.key

        caller.msg("|rYou open {} up with slow, practiced cuts, ribs creaking as you spread the cage and reach inside.|n".format(corpse_name))
        if caller.location:
            caller.location.msg_contents(
                f"{caller.get_display_name(caller.location)} leans over {corpse_name}, cutting it open and working both hands deep into the cavity.",
                exclude=caller,
            )

        import random

        # Organ difficulties (relative to base_roll). Some are harder to take clean.
        organs = [
            ("lungs", 50),
            ("heart", 55),
            ("liver", 60),
            ("spleen", 65),
            ("brain", 70),
        ]

        made_any = {"value": False}
        processed = {"count": 0}

        from evennia.utils.create import create_object

        def _process_next(index):
            room = getattr(caller, "location", None)
            if not room or target.location != room:
                # Character moved or corpse gone; stop the sequence.
                try:
                    caller.ndb.is_butchering = False
                except Exception as e:
                    logger.log_trace("scavenge_cmds.CmdButcher _process_next clear is_butchering (early): %s" % e)
                return

            if index >= len(organs):
                # Finished all organs; finalize.
                target.db.butchered = True
                try:
                    caller.ndb.is_butchering = False
                except Exception as e:
                    logger.log_trace("scavenge_cmds.CmdButcher _process_next clear is_butchering: %s" % e)
                if not made_any["value"]:
                    caller.msg("|rYour cuts are clumsy; by the time you are done, the insides are just shredded meat.|n")
                    room.msg_contents(
                        f"{caller.get_display_name(room)} pulls back empty-handed, the corpse's insides a ruin.",
                        exclude=caller,
                    )
                    return
                room.msg_contents(
                    f"{caller.get_display_name(room)} withdraws handfuls of glistening organs from the opened body.",
                    exclude=caller,
                )
                return

            organ_key, diff = organs[index]
            roll = base_roll + random.randint(-10, 10)
            if roll < diff:
                caller.msg(f"|rYou tear through where the {organ_key} should be, leaving nothing usable.|n")
            else:
                if is_creature:
                    key = f"mutated {organ_key}"
                    desc = f"A twisted, unnatural {organ_key}: knotted tissue, wrong colors, and pulsing growths that should not be alive."
                    name_for_msg = f"the mutated {organ_key.replace('_', ' ')}"
                else:
                    key = organ_key
                    pretty = organ_key.replace("_", " ")
                    desc = f"A freshly taken {pretty}, still warm and slick, with clamps of torn tissue hanging where it was cut free."
                    name_for_msg = f"the {pretty}"
                try:
                    organ = create_object("typeclasses.items.Item", key=key, location=caller)
                    organ.db.desc = desc
                    organ.tags.add("butchered_organ")
                    made_any["value"] = True
                    caller.msg(f"|gYou ease out {name_for_msg}, cradling it in both hands before setting it aside.|n")
                except Exception as e:
                    logger.log_trace("scavenge_cmds.CmdButcher create_object organ %s: %s" % (organ_key, e))

            # Schedule next organ 4–5 seconds later, from easiest to hardest.
            processed["count"] += 1
            try:
                delay(random.randint(4, 5), _process_next, index + 1)
            except Exception as e:
                logger.log_trace("scavenge_cmds.CmdButcher delay _process_next: %s" % e)
                _process_next(index + 1)

        # Initial delay for opening the body: 10–15 seconds, then start organs one by one.
        try:
            delay(random.randint(10, 15), _process_next, 0)
        except Exception as e:
            logger.log_trace("scavenge_cmds.CmdButcher initial delay: %s" % e)
            _process_next(0)


class CmdSever(Command):
    """
    Sever a limb or head from a corpse or an unconscious character, producing a severed part.

    Usage:
      sever <target> <body part>

    Body parts: head, left/right arm, left/right hand, left/right thigh, left/right foot.
    """

    key = "sever"
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        from world.skills import SKILL_STATS
        from world.medical import (
            BODY_PARTS,
            BODY_PART_ALIASES,
            BODY_PART_ORGANS,
            BONE_TO_BODY_PARTS,
            is_unconscious,
        )
        from world.death import is_flatlined, is_permanently_dead, make_permanent_death
        from evennia.utils.create import create_object

        caller = _command_character(self)
        if not caller or not getattr(caller, "db", None) or not hasattr(caller.db, "stats"):
            self.caller.msg("You must be in character to do that.")
            return

        # Require a basic short blade (knife) wielded.
        weapon = getattr(caller.db, "wielded_obj", None)
        weapon_key = getattr(caller.db, "wielded", None)
        if not weapon or getattr(weapon, "location", None) is not caller or weapon_key != "knife":
            caller.msg("You need a basic short blade in hand before you can sever anything.")
            return

        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: sever <target> <body part>")
            return
        parts = args.split(None, 1)
        if len(parts) < 2:
            caller.msg("Usage: sever <target> <body part>")
            return
        target_name, part_raw = parts[0], parts[1]

        target = caller.search(target_name, location=caller.location)
        if not target:
            return

        # Resolve body part (reuse same rules as describe_bodypart).
        raw = part_raw.strip().lower()
        full = raw
        if full not in BODY_PARTS:
            full = BODY_PART_ALIASES.get(full)
        if not full:
            caller.msg("Unknown body part. Try one of: head, larm, rarm, lhand, rhand, lthigh, rthigh, lfoot, rfoot.")
            return

        # Allowed parts: head (special), limbs. No torso/back/abdomen/groin/neck/shoulder.
        allowed_parts = {
            "head",
            "left arm", "right arm",
            "left hand", "right hand",
            "left thigh", "right thigh",
            "left foot", "right foot",
        }
        if full not in allowed_parts:
            caller.msg("You can only sever a head or limb: head, left/right arm/hand/thigh/foot.")
            return

        # Determine if target is a corpse or a living/unconscious character.
        is_corpse = False
        try:
            from typeclasses.corpse import Corpse
            is_corpse = isinstance(target, Corpse)
        except Exception as e:
            logger.log_trace("scavenge_cmds.CmdSever Corpse check: %s" % e)
            is_corpse = False

        if is_corpse:
            living_target = None
        else:
            living_target = target
            # Only unconscious, not flatlined or permanently dead.
            if is_flatlined(living_target) or is_permanently_dead(living_target):
                caller.msg("They are beyond this kind of work.")
                return
            if not is_unconscious(living_target):
                caller.msg("They are not unconscious. You cannot do this while they are awake.")
                return

        # Scavenging roll to control finesse.
        stats = SKILL_STATS.get("scavenging", ["intelligence", "perception"])
        luck_bonus = int(caller.get_display_stat("luck")) if hasattr(caller, "get_display_stat") else 0
        level, final_roll = caller.roll_check(stats, "scavenging", modifier=luck_bonus)

        is_creature = bool(getattr(target.db, "is_creature", False))

        # Cascading loss: head -> face; arm -> hand; thigh -> foot.
        cascade = {
            "head": ["face"],
            "left arm": ["left hand"],
            "right arm": ["right hand"],
            "left thigh": ["left foot"],
            "right thigh": ["right foot"],
        }
        removed_parts = [full] + cascade.get(full, [])

        # Do not allow severing an already-missing limb/part.
        existing_missing = set(getattr(target.db, "missing_body_parts", []) or [])
        if existing_missing.intersection(removed_parts):
            caller.msg("That part has already been severed.")
            return

        # Pull appearance description for this part (if available), to imprint on the severed item.
        body_descs = getattr(target.db, "body_descriptions", None) or {}
        if full == "head":
            # For heads, also include the face description since the face comes with it.
            head_txt = (body_descs.get("head") or "").strip()
            face_txt = (body_descs.get("face") or "").strip()
            desc_bits = [t for t in (head_txt, face_txt) if t]
            desc_source = " ".join(desc_bits)
        else:
            desc_source = (body_descs.get(full) or "").strip()

        # Build severed item key and description.
        pretty_part = full.replace("_", " ")
        base_key = f"severed {pretty_part}"
        if is_creature:
            item_key = f"mutated {base_key}"
        else:
            item_key = base_key

        # Build flavor line about origin: show "a corpse" for corpses, "a human" for the living.
        if is_corpse:
            origin_line = f"A {base_key} from a corpse."
        else:
            origin_line = f"A {base_key} from a human."

        if desc_source:
            item_desc = f"{origin_line} {desc_source}"
        else:
            item_desc = f"{origin_line} It is still slick and heavy."

        # Create the severed part in caller's inventory.
        severed = None
        try:
            severed = create_object("typeclasses.items.Item", key=item_key, location=caller)
            severed.db.desc = item_desc
            severed.tags.add("severed_limb")
        except Exception:
            severed = None

        # Mark missing parts on living target; corpses are static but we still update their
        # body_descriptions and medical state so look/medical summaries reflect the loss.
        if living_target:
            missing = list(getattr(living_target.db, "missing_body_parts", []) or [])
            for p in removed_parts:
                if p not in missing:
                    missing.append(p)
            living_target.db.missing_body_parts = missing
            # Clear any held items in lost hands.
            if "left arm" in removed_parts or "left hand" in removed_parts:
                held = getattr(living_target.db, "left_hand_obj", None)
                if held and getattr(held, "location", None) == living_target and living_target.location:
                    held.location = living_target.location
                living_target.db.left_hand_obj = None
            if "right arm" in removed_parts or "right hand" in removed_parts:
                held = getattr(living_target.db, "right_hand_obj", None)
                if held and getattr(held, "location", None) == living_target and living_target.location:
                    held.location = living_target.location
                living_target.db.right_hand_obj = None
            # Recompute wielded state after losing hands.
            try:
                _update_primary_wielded(living_target)
            except Exception:
                pass
            living_target.db.missing_body_parts = missing

        # Update descriptive text and injuries for both living characters and corpses.
        # 1) Clear organ, bone, and surface injuries tied to removed parts so summaries don't
        #    describe damage on limbs that no longer exist.
        organs_to_clear = set()
        for p in removed_parts:
            organs_to_clear.update(BODY_PART_ORGANS.get(p, []))

        organ_damage = getattr(target.db, "organ_damage", None) or {}
        for organ in organs_to_clear:
            if organ in organ_damage:
                del organ_damage[organ]
        target.db.organ_damage = organ_damage

        fractures = list(getattr(target.db, "fractures", []) or [])
        kept_fractures = []
        for bone in fractures:
            parts_for_bone = set(BONE_TO_BODY_PARTS.get(bone, []))
            if not parts_for_bone.intersection(removed_parts):
                kept_fractures.append(bone)
        target.db.fractures = kept_fractures

        # Clear surface injuries on removed parts (used by clothing.get_effective_body_descriptions).
        injuries = list(getattr(target.db, "injuries", []) or [])
        if injuries:
            kept_injuries = []
            for inj in injuries:
                part = (inj.get("body_part") or "").strip()
                if part and part in removed_parts:
                    # Drop injuries on amputated parts.
                    continue
                kept_injuries.append(inj)
            target.db.injuries = kept_injuries

        # 2) Replace body-part descriptions with "missing" text instead of whatever
        #    they had before.
        def _missing_desc(part_name: str) -> str:
            if part_name == "head":
                return "The head is gone; the neck ends in a jagged, butchered stump."
            if "arm" in part_name or "hand" in part_name:
                return "This limb is gone; only a ragged stump of torn muscle and bone remains."
            if "thigh" in part_name or "foot" in part_name:
                return "The leg ends abruptly in a torn stump; everything below is missing."
            return "This part of the body is missing, carved away to nothing."

        for p in removed_parts:
            body_descs[p] = _missing_desc(p)
        target.db.body_descriptions = body_descs

        # Messaging and special handling for head.
        part_for_msg = full
        if full == "head":
            part_for_msg = "head (and face)"
        caller.msg(f"|rYou work the blade until the {part_for_msg} comes free in a wet, final pull.|n")
        if caller.location:
            caller.location.msg_contents(
                f"{caller.get_display_name(caller.location)} saws away until {target.get_display_name(caller.location)}'s {part_for_msg} comes free.",
                exclude=caller,
            )

        if living_target and full == "head":
            # Decapitation: immediate death.
            make_permanent_death(living_target, attacker=caller, reason="executed")


class CmdLoot(Command):
    """
    Search a corpse's pockets and belongings. After a short delay you see what they had;
    run the command again to see the list again. Take items with 'get <item> from <corpse>'.

    Usage:
      loot <corpse>
    """
    key = "loot"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not self.args or not self.args.strip():
            caller.msg("Loot what? Usage: loot <corpse>")
            return
        from typeclasses.corpse import Corpse
        corpse = caller.search(self.args.strip(), location=caller.location)
        if not corpse:
            return
        if not isinstance(corpse, Corpse):
            caller.msg("You can only loot corpses.")
            return
        cname = corpse.get_display_name(caller)
        caller.msg("You kneel and start pilfering through the pockets and folds of %s." % cname)
        caller.location.msg_contents(
            "%s kneels beside %s and begins searching through the body's pockets and belongings." % (caller.get_display_name(caller), cname),
            exclude=caller,
        )
        from evennia.utils import delay
        delay(5.5, _loot_finish, caller.id, corpse.id)
