"""
Staff commands: givexp, charsheet, setstat, setskill, create, typeclasses,
spawn (item/armor/vehicle/medical/or/seat/bed/pod/camera/tv/creature),
creatureset, despawn, npc, makenpc, npcset, @goto, @gotoroom, @summon,
@setvoid, @void, release (@release), boot, @find, announce, restore,
debugkill, emotedebug, damagevehicle, @climate. CmdPending imported from roleplay_cmds.
"""

from datetime import datetime

from commands.base_cmds import Command, ADMIN_LOCK
from commands.roleplay_cmds import CmdPending
from evennia.commands.default.account import CmdCharCreate, CmdCharDelete
from evennia.utils import logger
from evennia.utils.evtable import EvTable
from evennia.utils.evmore import EvMore
from world.ui_utils import fade_rule
from world.utils import get_containing_room


class CmdStaffSheet(Command):
    """
    View any character's full sheet (stats, skills, vitals). Builder+.
    Usage: charsheet <character>
    """
    key = "charsheet"
    aliases = ["staffsheet", "viewsheet",]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: charsheet <character>")
            return
        target = caller.search(args, global_search=True)
        if not target:
            return
        if not hasattr(target, "db") or not hasattr(target.db, "stats"):
            caller.msg("That is not a character with a sheet.")
            return
        from world.rpg.chargen import STAT_KEYS
        from world.skills import SKILL_KEYS, SKILL_DISPLAY_NAMES
        from world.levels import get_stat_grade, get_skill_grade
        _db = target.db
        stats = _db.stats or {}
        skills = _db.skills or {}
        try:
            hp_str = "{} / {}".format(target.hp, target.max_hp)
            st_str = "{} / {}".format(target.stamina, target.max_stamina)
            load_str = "{} kg".format(target.carry_capacity)
        except Exception as e:
            logger.log_trace("staff_cmds.CmdStaffSheet vitals: %s" % e)
            hp_str = st_str = load_str = "---"
        w = 50
        strong_rule = fade_rule(w - 2, "=")
        thin_rule = fade_rule(w - 2, "-")
        line = "|c+" + strong_rule + "+|n"
        thin = "|c|" + thin_rule + "||n"
        npc_tag = " |r[NPC]|n" if getattr(_db, "is_npc", False) else ""
        output = line + "\n"
        output += "|c||n  |W STAFF READOUT |w {}|n{}\n".format((target.name or "Unknown"), npc_tag)
        rk = (getattr(_db, "race", None) or "human").lower()
        if rk == "splicer":
            an = (getattr(_db, "splicer_animal", None) or "unknown").title()
            output += "|c|||n  |wRace|n Splicer (" + an + ")\n"
        else:
            output += "|c|||n  |wRace|n Human\n"
        try:
            ay = getattr(_db, "age_years", None)
            if ay is not None:
                output += "|c|||n  |wAge|n {} years\n".format(int(ay))
        except Exception as e:
            logger.log_trace("staff_cmds.CmdStaffSheet age: %s" % e)
        output += thin + "\n"
        output += "|c|||n  |rVitality|n " + hp_str.ljust(12) + " |yStamina|n " + st_str.ljust(12) + " |gLoad|n " + load_str + "\n"
        output += thin + "\n"
        output += "|c|||n  |W S P E C I A L|n\n"
        for key in STAT_KEYS:
            lv = stats.get(key, 0)
            letter = get_stat_grade(target.get_stat_level(key) if hasattr(target, "get_stat_level") else lv)
            adj = target.get_stat_grade_adjective(letter, key) if hasattr(target, "get_stat_grade_adjective") else letter
            output += "|c|||n    |w{}|n  |w[{}]|n {} ({})\n".format(key.capitalize().ljust(12), letter, adj, lv)
        output += thin + "\n"
        output += "|c|||n  |W SKILLS|n\n"
        for key in SKILL_KEYS:
            lv = skills.get(key, 0)
            letter = get_skill_grade(target.get_skill_level(key) if hasattr(target, "get_skill_level") else lv)
            adj = target.get_skill_grade_adjective(letter) if hasattr(target, "get_skill_grade_adjective") else letter
            label = SKILL_DISPLAY_NAMES.get(key, key.replace("_", " ").title())
            output += "|c|||n    |w{}|n  |w[{}]|n {} ({})\n".format(label.ljust(20), letter, adj, lv)
        output += line + "\n"
        caller.msg(output)


class CmdStaffSetStat(Command):
    """
    Set a character's stat value (0-300). Builder+.
    Usage: setstat <character> <stat> <value>
    """
    key = "setstat"
    aliases = ["staffstat"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        parts = (self.args or "").strip().split()
        if len(parts) < 3:
            caller.msg("Usage: setstat <character> <stat> <value>")
            return
        target = caller.search(parts[0], global_search=True)
        if not target or not hasattr(target, "db"):
            return
        from world.rpg.chargen import STAT_KEYS
        stat_key = None
        for s in STAT_KEYS:
            if s.startswith(parts[1].lower()) or parts[1].lower() == s:
                stat_key = s
                break
        if not stat_key:
            caller.msg("Unknown stat. Use one of: {}.".format(", ".join(STAT_KEYS)))
            return
        try:
            value = int(parts[2])
            value = max(0, min(300, value))
        except ValueError:
            caller.msg("Value must be a number (0-300).")
            return
        if not target.db.stats:
            target.db.stats = {}
        target.db.stats[stat_key] = value
        caller.msg("|g{}'s {} set to {}.|n".format(target.name, stat_key, value))
        try:
            _ = target.max_hp
            _ = target.max_stamina
        except Exception:
            pass


class CmdStaffSetSkill(Command):
    """
    Set a character's skill value (0-150). Builder+.
    Usage: setskill <character> <skill> <value>
    """
    key = "setskill"
    aliases = ["staffskill"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        parts = (self.args or "").strip().split()
        if len(parts) < 3:
            caller.msg("Usage: setskill <character> <skill> <value>")
            return
        target = caller.search(parts[0], global_search=True)
        if not target or not hasattr(target, "db"):
            return
        from world.skills import SKILL_KEYS, SKILL_DISPLAY_NAMES
        skill_key = None
        for s in SKILL_KEYS:
            if s.startswith(parts[1].lower().replace(" ", "_")) or parts[1].lower().replace(" ", "_") == s:
                skill_key = s
                break
        if not skill_key:
            caller.msg("Unknown skill. Use one of: {}.".format(", ".join(SKILL_KEYS)))
            return
        try:
            value = int(parts[2])
            value = max(0, min(150, value))
        except ValueError:
            caller.msg("Value must be a number (0-150).")
            return
        if not target.db.skills:
            target.db.skills = {}
        target.db.skills[skill_key] = value
        label = SKILL_DISPLAY_NAMES.get(skill_key, skill_key)
        caller.msg("|g{}'s {} set to {}.|n".format(target.name, label, value))


class CmdMakeNpc(Command):
    """
    Create an NPC (staff-controlled character) in the current room. Builder+.
    NPCs use the same stats/skills as PCs but do not show as sleeping when unpuppeted.
    Usage: makenpc <name>
    """
    key = "makenpc"
    aliases = ["createnpc", "npccreate"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        name = (self.args or "").strip()
        if not name:
            caller.msg("Usage: makenpc <name>")
            return
        from evennia.utils.create import create_object
        try:
            from typeclasses.npc import NPC
            obj = create_object(
                "typeclasses.npc.NPC",
                key=name,
                location=caller.location,
            )
            caller.msg("|gNPC |w{}|n created here. Use |w@puppet {}|n to puppet.|n".format(name, name))
        except Exception as e:
            caller.msg("|rCould not create NPC: {}|n".format(e))


class CmdNpcSet(Command):
    """
    Set a character as NPC or PC. NPCs do not show as sleeping when unpuppeted. Builder+.
    Usage: npcset <character> npc|pc
    """
    key = "npcset"
    aliases = ["setnpc"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        parts = (self.args or "").strip().split(None, 1)
        if len(parts) < 2:
            caller.msg("Usage: npcset <character> npc|pc")
            return
        target = caller.search(parts[0], global_search=True)
        if not target or not hasattr(target, "db"):
            return
        mode = parts[1].strip().lower()
        if mode not in ("npc", "pc"):
            caller.msg("Use npc or pc.")
            return
        target.db.is_npc = (mode == "npc")
        caller.msg("|g{} is now a {}.|n".format(target.name, mode.upper()))


class CmdGoto(Command):
    """
    Teleport yourself to a character's location. Builder+.
    Usage: @goto <character>
    """
    key = "@goto"
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: @goto <character>")
            return
        target = caller.search(args, global_search=True)
        if not target:
            return
        loc = target.location
        if not loc:
            caller.msg("That character has no location.")
            return
        caller.move_to(loc)
        caller.msg("|gYou go to {}.|n".format(target.name))


class CmdGotoRoom(Command):
    """
    Teleport yourself directly to a room by dbref or exact room name. Builder+.

    Usage:
      @gotoroom #123
      @gotoroom Room Name
      @gotoroom <object>  (teleports to containing room)
    """

    key = "@gotoroom"
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: @gotoroom <#dbref> or <exact room name>")
            return

        # Use caller.search which handles dbrefs, names, etc.
        target = caller.search(args, global_search=True)
        if not target:
            return

        # get_containing_room handles both rooms (returns self) and objects (walks up)
        dest = get_containing_room(target)
        if not dest:
            caller.msg("Could not find containing room for that object.")
            return
        caller.move_to(dest)
        caller.msg(f"|gYou teleport to room: {dest.get_display_name(caller)}|n")


class CmdSummon(Command):
    """
    Bring a character to your location. Builder+.
    Usage: @summon <character>
    """
    key = "@summon"
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: @summon <character>")
            return
        target = caller.search(args, global_search=True)
        if not target:
            return
        if not hasattr(target, "move_to"):
            caller.msg("That object cannot be moved.")
            return
        dest = caller.location
        if not dest:
            caller.msg("You have no location.")
            return
        target.move_to(dest)
        caller.msg("|gYou summon {} here.|n".format(target.name))
        target.msg("|yYou have been summoned to {}.|n".format(caller.get_display_name(target) if hasattr(caller, "get_display_name") else caller.name))


class CmdSetVoid(Command):
    """
    Set the current room as the void (discipline holding room). Builder+.
    Voided characters are moved here and cannot leave until released.
    Usage: @setvoid
    """
    key = "@setvoid"
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        loc = caller.location
        if not loc:
            caller.msg("You have no location.")
            return
        try:
            from evennia.server.models import ServerConfig
            ServerConfig.objects.conf("VOID_ROOM_ID", loc.id)
            caller.msg("|gThis room is now the void. Use |w@void <character> [reason]|n to send someone here, |w@release <character>|n to free them.|n")
        except Exception as e:
            caller.msg("|rCould not set void room: {}|n".format(e))


class CmdVoid(Command):
    """
    Send a character to the void (discipline room). They cannot leave until released. Builder+.
    Set the void room first with |w@setvoid|n in that room.
    Usage: @void <character> [reason]
    """
    key = "@void"
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        parts = (self.args or "").strip().split(None, 1)
        if not parts:
            caller.msg("Usage: @void <character> [reason]")
            return
        target = caller.search(parts[0], global_search=True)
        if not target or not hasattr(target, "move_to"):
            return
        reason = parts[1].strip() if len(parts) > 1 else ""
        try:
            from evennia.server.models import ServerConfig
            void_id = ServerConfig.objects.conf("VOID_ROOM_ID", default=None)
        except Exception:
            void_id = None
        if void_id is None:
            caller.msg("|rNo void room set. Go to the discipline room and use |w@setvoid|n first.|n")
            return
        from evennia.utils.search import search_object
        void_room = search_object("#%s" % int(void_id))
        if not void_room:
            void_room = search_object(int(void_id))
        if not void_room:
            caller.msg("|rVoid room no longer exists. Use |w@setvoid|n in the discipline room again.|n")
            return
        void_room = void_room[0] if isinstance(void_room, list) else void_room
        target.db.voided = True
        target.db.voided_reason = reason
        target.db.voided_at = __import__("time", fromlist=["time"]).time()
        target.move_to(void_room)
        caller.msg("|g{} has been sent to the void.{}|n".format(target.name, " Reason: " + reason if reason else ""))
        target.msg("|rYou have been moved to the void.{}|n".format(" " + reason if reason else " A staff member will release you when appropriate."))


class CmdRelease(Command):
    """
    Release a character from the void and bring them to your location. Builder+.
    Usage: @release <character>
    """
    key = "@releasevoid"
    aliases = ["@releasevoid"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: @release <character>")
            return
        target = caller.search(args, global_search=True)
        if not target or not hasattr(target, "db"):
            return
        if not getattr(target.db, "voided", False):
            caller.msg("{} is not in the void.".format(target.name))
            return
        dest = caller.location
        if not dest or not hasattr(target, "move_to"):
            caller.msg("You have no location to release them to.")
            return
        target.db.voided = False
        for key in ("voided_reason", "voided_at"):
            if hasattr(target.db, key):
                del target.db[key]
        target.move_to(dest)
        caller.msg("|g{} has been released here.|n".format(target.name))
        target.msg("|gYou have been released from the void.|n")


class CmdBoot(Command):
    """
    Disconnect a character's session(s) and send them to the login screen. Builder+.
    Usage: boot <character> [message]
    """
    key = "boot"
    aliases = ["kick", "disconnect"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        parts = (self.args or "").strip().split(None, 1)
        if not parts:
            caller.msg("Usage: boot <character> [message]")
            return
        target = caller.search(parts[0], global_search=True)
        if not target:
            return
        msg = parts[1].strip() if len(parts) > 1 else "You have been disconnected by staff."
        try:
            for session in target.sessions.get():
                session.msg("|r%s|n" % msg)
                session.sessionhandler.disconnect(session, reason=msg)
            caller.msg("|gBooted {} (all sessions).|n".format(target.name))
        except Exception as e:
            caller.msg("|rCould not boot: {}|n".format(e))


class CmdFind(Command):
    """
    Find where an object or character is (room name and id). Builder+.
    Shows all matches if multiple objects have similar names.
    Usage: @find <search term>
    """
    key = "@find"
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        from evennia.utils.search import search_object

        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: @find <search term>")
            return

        # Check for Matrix ID first (starts with ^)
        if args.startswith("^"):
            from world.matrix_ids import lookup_matrix_id
            result = lookup_matrix_id(args)
            matches = [result] if result else []
        else:
            # Use search_object with exact=False for partial matching
            matches = search_object(args, exact=False)

        if not matches:
            caller.msg(f"No objects found matching '{args}'.")
            return

        # Build results for all matches
        results = []
        for obj in matches:
            loc = get_containing_room(obj)
            if not loc:
                loc_text = "|rNo location|n"
            else:
                loc_text = f"|w{loc.name or loc.key}|n (#{getattr(loc, 'id', '?')})"

            voided = " |r[VOIDED]|n" if getattr(getattr(obj, "db", None), "voided", False) else ""
            obj_name = getattr(obj, "name", getattr(obj, "key", str(obj)))
            obj_id = getattr(obj, "id", "?")

            results.append(f"|w{obj_name}|n (#{obj_id}): {loc_text}{voided}")

        # Use EvMore for pagination only if many results (>20)
        if len(results) == 1:
            caller.msg(results[0])
        elif len(results) <= 20:
            caller.msg(f"Found {len(results)} matches for '{args}':")
            for i, result in enumerate(results, 1):
                caller.msg(f"  {i}. {result}")
        else:
            header = f"Found {len(results)} matches for '{args}':\n"
            output = header + "\n".join(f"  {i}. {result}" for i, result in enumerate(results, 1))
            EvMore(caller, output)


class CmdAnnounce(Command):
    """
    Send a message to everyone in the game (all connected characters). Builder+.
    Usage: announce <message>
    """
    key = "announce"
    aliases = ["broadcast", "shout"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        msg = (self.args or "").strip()
        if not msg:
            caller.msg("Usage: announce <message>")
            return
        import evennia
        sent = 0
        for session in evennia.SESSION_HANDLER.get_sessions():
            puppet = getattr(session, "puppet", None)
            if puppet and hasattr(puppet, "msg") and puppet != caller:
                puppet.msg("|y[ANNOUNCE]|n %s" % msg)
                sent += 1
        caller.msg("|gAnnouncement sent to {} recipient(s).|n".format(sent))


class CmdRestore(Command):
    """
    Restore a character to full health: HP, stamina, flatline state, and all trauma (bleeding, fractures, organ damage). Builder+.
    Usage: @restore <character>
    """
    key = "@restore"
    aliases = ["restore", "fullheal", "healup", "heal"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        raw = (self.args or "").strip()

        # Quality-of-life: allow self-target shorthand so you can very quickly
        # restore your current puppet. The following all target the caller:
        #   @restore
        #   @restore/me
        #   @restore/self
        #
        # Note: plain "me"/"self" without a slash are left alone so they can still
        # be resolved via normal search if desired.
        if not raw or raw.lower() in ("/me", "/self"):
            target = caller
        else:
            args = raw
            # First try the normal global search (quiet so we can run our own fallback without spurious errors).
            target = caller.search(args, global_search=True, quiet=True)

        # If that failed, try a more relaxed match on characters in the room,
        # allowing partial/surname matching similar to @puppet.
        if not target:
            loc = getattr(caller, "location", None)
            if loc and hasattr(loc, "contents_get"):
                arg_low = args.lower()
                relaxed = []
                for obj in loc.contents_get(content_type="character"):
                    if not hasattr(obj, "db"):
                        continue
                    key_low = (getattr(obj, "key", "") or "").lower()
                    words = key_low.split()
                    if any(w.startswith(arg_low) for w in words) or arg_low in key_low:
                        relaxed.append(obj)
                if len(relaxed) == 1:
                    target = relaxed[0]
                elif len(relaxed) > 1:
                    # Ambiguous – show options like other staff commands do.
                    names = [f"{o.name}(#{getattr(o, 'id', '?')})" for o in relaxed]
                    caller.msg("Multiple matches for that name here: %s" % ", ".join(names))
                    return

        if not target or not hasattr(target, "db"):
            return
        try:
            # Heal first, then clear flatline. If death_state is cleared while HP is still 0,
            # character_can_act() still blocks on hp <= 0 with the same "dying" message.
            mx = target.max_hp
            target.db.current_hp = mx
            target.db.current_stamina = target.max_stamina
            from world.death import clear_flatline

            clear_flatline(target)
            from world.medical import reset_medical

            reset_medical(target)
            caller.msg("|g{} restored to full HP, stamina, and trauma cleared; flatline/dying state cleared.|n".format(target.name))
            if target != caller:
                target.msg("|gYou have been restored to full health; all trauma and flatline state have been cleared.|n")
        except Exception as e:
            caller.msg("|rCould not restore: {}|n".format(e))


class CmdDebugKill(Command):
    """
    Admin debug: immediately kill a character and put them into corpse state so you
    can test the death limbo / go shard / go light flow. Target becomes a corpse;
    their account is unpuppeted and sent to the Death Lobby.
    Usage: debugkill [target]
    If no target, kills yourself.
    """
    key = "debugkill"
    aliases = ["debug death"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        from world.death import DEATH_STATE_FLATLINED, make_permanent_death, is_permanently_dead
        caller = self.caller
        args = (self.args or "").strip()
        if args:
            target = caller.search(args, global_search=True)
            if not target:
                return
        else:
            target = caller
        if not hasattr(target, "db"):
            caller.msg("|rNot a valid character.|n")
            return
        if is_permanently_dead(target):
            caller.msg("|r{} is already permanently dead (a corpse).|n".format(target.name))
            return
        # Set to 0 HP and flatlined so make_permanent_death can run
        target.db.current_hp = 0
        if hasattr(target, "max_stamina"):
            target.db.current_stamina = 0
        target.db.death_state = DEATH_STATE_FLATLINED
        target.db.room_pose = "lying here, dead."
        make_permanent_death(target, attacker=None, reason="time")
        if target == caller:
            caller.msg("|y[DEBUG]|n You have been killed. You should be in the Death Lobby now.|n")
        else:
            caller.msg("|y[DEBUG]|n {} has been killed and is now a corpse. Their account is in the Death Lobby.|n".format(target.name))


class CmdCreateItem(Command):
    """
    Create an object with a specific typeclass and key. (Admin/Builder only.)
    The typeclass is applied correctly so at_object_creation runs and the object
    gets the right name.

    Usage:
      create <typeclass> = <key>
      create typeclasses.ammo.PistolAmmo = pistol rounds
      create typeclasses.weapons.SidearmWeapon = heavy pistol
    """
    key = "create"
    aliases = ["createitem", "newitem"]
    locks = ADMIN_LOCK
    help_category = "Admin"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Usage: create <typeclass> = <key>")
            return

        raw = self.args.strip()
        if "=" in raw:
            typeclass_part, key_part = raw.split("=", 1)
            typeclass_path = typeclass_part.strip()
            key = key_part.strip()
        else:
            caller.msg("Usage: create <typeclass> = <key>  (e.g. create typeclasses.ammo.PistolAmmo = pistol rounds)")
            return

        if not typeclass_path or not key:
            caller.msg("Provide both a typeclass path and a key.")
            return

        from evennia.utils.create import create_object
        try:
            obj = create_object(typeclass_path, key=key, location=caller)
            caller.msg(f"|gCreated|n |w{obj.name}|n (|y{typeclass_path}|n) in your inventory.")
        except Exception as e:
            caller.msg(f"|rCould not create object: {e}|n")


def _discover_typeclass_paths(package_path, prefix, skip_modules, bases):
    """Discover typeclass paths under a package. Returns sorted list of 'modname.ClassName' strings."""
    import pkgutil
    import importlib
    paths = []
    for _importer, modname, _ispkg in pkgutil.walk_packages(package_path, prefix):
        if any(modname.startswith(s) for s in skip_modules):
            continue
        try:
            mod = importlib.import_module(modname)
        except Exception as e:
            logger.log_trace("staff_cmds._discover_typeclass_paths import %s: %s" % (modname, e))
            continue
        for name in dir(mod):
            if name.startswith("_"):
                continue
            obj = getattr(mod, name)
            if not isinstance(obj, type):
                continue
            if obj.__module__ != modname:
                continue
            if not any(base in obj.__mro__ for base in bases):
                continue
            paths.append(f"{modname}.{name}")
    paths.sort()
    return paths


class CmdTypeclasses(Command):
    """
    List all typeclass paths usable with the create command. (Admin/Builder only.)
    """
    key = "typeclasses"
    aliases = ["listtypeclasses", "typelist"]
    locks = ADMIN_LOCK
    help_category = "Admin"

    def func(self):
        from evennia import DefaultObject, DefaultCharacter, DefaultRoom, DefaultExit
        try:
            from evennia.scripts.scripts import DefaultScript
        except Exception as e:
            logger.log_trace("staff_cmds.CmdTypeclasses DefaultScript import: %s" % e)
            DefaultScript = None

        caller = self.caller
        bases = (DefaultObject, DefaultCharacter, DefaultRoom, DefaultExit)
        if DefaultScript is not None:
            bases = bases + (DefaultScript,)

        try:
            import typeclasses as pkg
            prefix = pkg.__name__ + "."
            skip_modules = (prefix + "accounts", prefix + "channels")
            paths = _discover_typeclass_paths(pkg.__path__, prefix, skip_modules, bases)
        except Exception as e:
            caller.msg(f"|rCould not discover typeclasses: {e}|n")
            return

        if not paths:
            caller.msg("|yNo typeclasses found.|n")
            return

        caller.msg("|wTypeclasses for |wcreate|n (usage: |wcreate <typeclass> = <key>|n):|n")
        for path in paths:
            caller.msg(f"  |y{path}|n")
        caller.msg(f"|w({len(paths)} typeclass(s).)|n")


class CmdSpawnItem(Command):
    """
    Spawn test items by prototype key. List is auto-generated from PROTOTYPE_MODULES.
    Filter lists with |wprototype_tags|n (see |wspawnitem list|n footer). Builder/Admin only.

    Usage:
      spawnitem list                      - list all prototype keys
      spawnitem list <category>           - list keys that have that tag (e.g. spawnitem list combat)
      spawnitem list <category> <subtag>  - list keys that have both tags (e.g. spawnitem list combat weapon)
      spawnitem list drug                 - alchemy drugs (also: drugs, alchemy drug, …)
      spawnitem list alchemy              - stations, chemicals, drugs, recipes, etc.
      spawnitem list vehicle              - vehicles (ground / motorcycle / aerial)
      spawnitem list vehicle ground       - enclosed ground vehicles only
      spawnitem <prototype_key>           - spawn into your inventory (e.g. spawnitem bolt_of_silk)
      spawnitem <vehicle_key>             - spawns vehicle in your current room (not inventory)

    For typeclass-only items use |wtypeclasses|n and |wcreate <typeclass> = <key>|n.
    """
    key = "spawnitem"
    aliases = ["debugspawn", "spawni"]
    locks = ADMIN_LOCK
    help_category = "Admin"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            self._show_list(caller, tag_filters=None)
            return
        low = args.lower()
        if low == "list":
            self._show_list(caller, tag_filters=None)
            return
        if low.startswith("list "):
            rest = args[5:].strip().split()
            if not rest:
                self._show_list(caller, tag_filters=None)
            else:
                self._show_list(
                    caller,
                    tag_filters=[self._normalize_spawnitem_tag(x) for x in rest],
                )
            return
        self._spawn_prototype(caller, args)

    @staticmethod
    def _normalize_spawnitem_tag(token):
        from world.prototypes.categories import SPAWNITEM_TAG_ALIASES

        t = token.lower()
        return SPAWNITEM_TAG_ALIASES.get(t, t)

    def _show_list(self, caller, tag_filters):
        from evennia.prototypes import prototypes as protlib
        from evennia.utils.evtable import EvTable
        from world.prototypes.categories import KNOWN_LIST_TAGS, LIST_CATEGORY_HELP

        protlib.load_module_prototypes(override=True)
        try:
            if tag_filters is None:
                all_prots = protlib.search_prototype(no_db=True)
            elif len(tag_filters) == 1:
                all_prots = protlib.search_prototype(tags=[tag_filters[0]], no_db=True)
            else:
                all_prots = protlib.search_prototype(no_db=True)
                need = set(tag_filters)
                all_prots = [
                    p
                    for p in all_prots
                    if need.issubset(set(p.get("prototype_tags") or []))
                ]
        except Exception as e:
            caller.msg("|rCould not load prototypes: %s|n" % e)
            return
        if not all_prots:
            caller.msg("|yNo prototypes match that filter.|n")
            if tag_filters:
                unknown = [t for t in tag_filters if t not in KNOWN_LIST_TAGS]
                if unknown:
                    caller.msg("|yUnknown tag(s):|n %s" % ", ".join(unknown))
            caller.msg(LIST_CATEGORY_HELP)
            caller.msg("For typeclass items use |wtypeclasses|n and |wcreate <typeclass> = <key>|n.")
            return
        table = EvTable("|wprototype_key|n", "|wspawns as (key)|n", border="cells")
        for prot in sorted(all_prots, key=lambda p: (p.get("prototype_key") or "").lower()):
            pk = prot.get("prototype_key") or "(unnamed)"
            key = prot.get("key") or "(no key)"
            if callable(key):
                key = "(dynamic)"
            else:
                key = str(key)
            table.add_row(pk, key)
        if tag_filters:
            caller.msg(
                "|wSpawn (filtered):|n |wspawnitem <prototype_key>|n — tags: %s"
                % ", ".join(tag_filters)
            )
        else:
            caller.msg(
                "|wSpawn:|n |wspawnitem <prototype_key>|n (e.g. |wspawnitem %s|n)"
                % (all_prots[0].get("prototype_key", "bolt_of_silk"))
            )
        caller.msg(table)
        caller.msg(LIST_CATEGORY_HELP)
        caller.msg("|wTypeclass items:|n use |wtypeclasses|n and |wcreate <typeclass> = <key>|n.")

    def _spawn_prototype(self, caller, prototype_key):
        from evennia.prototypes import spawner
        from evennia.prototypes import prototypes as protlib
        protlib.load_module_prototypes(override=True)
        key_lower = str(prototype_key).strip().lower()
        try:
            objs = spawner.spawn(key_lower, caller=caller)
        except KeyError as e:
            caller.msg("|rNo prototype with that key. Use |wspawnitem list|n for options.|n")
            return
        except Exception as e:
            caller.msg("|rSpawn failed: %s|n" % e)
            return
        if not objs:
            caller.msg("|rNo object spawned (prototype key may be wrong).|n")
            return
        try:
            from typeclasses.vehicles import Vehicle
        except ImportError:
            Vehicle = None
        names = []
        any_vehicle = False
        for obj in objs:
            if Vehicle and isinstance(obj, Vehicle):
                any_vehicle = True
                loc = caller.location
                if not loc:
                    caller.msg("|rYou must be in a room to spawn a vehicle.|n")
                    obj.delete()
                    return
                obj.location = loc
                try:
                    from world.vehicles.vehicle_security import set_owner

                    set_owner(obj, caller)
                except Exception:
                    pass
            else:
                obj.location = caller
            names.append(obj.get_display_name(caller))
        if any_vehicle:
            caller.msg(
                "|gSpawned in your current room:|n %s — you are registered as |wbiometric owner|n."
                % ", ".join(names)
            )
        else:
            caller.msg("|gSpawned into your inventory:|n %s" % ", ".join(names))


class CmdSpawnArmor(Command):
    """
    Spawn placeholder/basic armor from world.armor_levels templates. Builder+.
    Usage:
      @spawnarmor list                    - list template keys by level
      @spawnarmor <template_key> [quality] - spawn one (quality 0-100, default 100)
    """
    key = "@spawnarmor"
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args or args.lower() == "list":
            self._show_list(caller)
            return
        parts = args.split()
        template_key = parts[0].strip().lower()
        quality = 100
        if len(parts) >= 2:
            try:
                quality = max(0, min(100, int(parts[1])))
            except ValueError:
                pass
        from world.armor_levels import create_armor_from_template, get_armor_template
        if get_armor_template(template_key) is None:
            caller.msg("|rUnknown armor template. Use |w@spawnarmor list|n for keys.|n")
            return
        obj = create_armor_from_template(template_key, location=caller, quality=quality)
        if not obj:
            caller.msg("|rFailed to create armor.|n")
            return
        caller.msg("|gSpawned:|n %s (quality %s)." % (obj.get_display_name(caller), quality))

    def _show_list(self, caller):
        from world.armor_levels import (
            ARMOR_TEMPLATES,
            ARMOR_LEVEL_SCAVENGER,
            ARMOR_LEVEL_CIVILIAN,
            ARMOR_LEVEL_ENFORCER,
            ARMOR_LEVEL_MILITARY,
            ARMOR_LEVEL_HEAVY,
            ARMOR_LEVEL_INQUISITOR,
        )
        from evennia.utils.evtable import EvTable
        level_names = {
            ARMOR_LEVEL_SCAVENGER: "Scavenger",
            ARMOR_LEVEL_CIVILIAN: "Civilian",
            ARMOR_LEVEL_ENFORCER: "Enforcer",
            ARMOR_LEVEL_MILITARY: "Medium Military",
            ARMOR_LEVEL_HEAVY: "Heavy Military",
            ARMOR_LEVEL_INQUISITOR: "Inquisitorate",
        }
        table = EvTable("|wkey|n", "|wname|n", "|wlevel|n", border="cells")
        for t in ARMOR_TEMPLATES:
            table.add_row(t["key"], t["name"], level_names.get(t.get("level", 1), "?"))
        caller.msg("|wArmor templates:|n |w@spawnarmor <key> [quality]|n")
        caller.msg(table)


class CmdSpawnVehicle(Command):
    """
    Create a test vehicle in the current room. (Admin/Builder only.)
    Usage: spawnvehicle [prototype_key|name]  — e.g. spawnvehicle rattler, spawnvehicle test sedan
    """
    key = "spawnvehicle"
    aliases = ["spawn vehicle", "testvehicle"]
    locks = ADMIN_LOCK
    help_category = "Admin"

    def func(self):
        caller = self.caller
        arg = self.args.strip()
        loc = caller.location
        if not loc:
            caller.msg("You need to be in a room to spawn a vehicle.")
            return
        from evennia.utils.create import create_object
        try:
            from typeclasses.vehicles import _room_allows_vehicle_tags
            from world.prototypes.vehicle_prototypes import ALL_VEHICLE_PROTOTYPES
        except Exception:
            ALL_VEHICLE_PROTOTYPES = {}
            _room_allows_vehicle_tags = lambda r: True

        if not _room_allows_vehicle_tags(loc):
            caller.msg(
                "|yThis room has no drivable-surface tag with category |wvehicle_access|n "
                "(|wstreet|n / |wtunnel|n / |waerial|n / |woffroad|n). "
                "Example: |w@tag here = street:vehicle_access|n or |woffroad:vehicle_access|n|n"
            )

        proto = ALL_VEHICLE_PROTOTYPES.get(arg.lower()) if arg else None
        if proto:
            try:
                vehicle = create_object(
                    proto["typeclass"],
                    key=proto["key"],
                    location=loc,
                )
                for attr_name, val in proto.get("attrs", []):
                    setattr(vehicle.db, attr_name, val)
                caller.msg(
                    f"|gCreated|n |w{vehicle.key}|n (|w{proto['prototype_key']}|n). "
                    f"|wenter|n / |wmount|n, |wstart|n, |wdrive|n or |wfly|n."
                )
            except Exception as e:
                caller.msg(f"|rCould not create vehicle: {e}|n")
            return

        name = arg or "test sedan"
        try:
            vehicle = create_object("typeclasses.vehicles.Vehicle", key=name, location=loc)
            caller.msg(
                f"|gCreated vehicle|n |w{vehicle.key}|n here. Use |wenter {vehicle.key}|n to get in, "
                f"then |wstart|n and |wdrive <direction>|n. "
                f"Prototypes: |w{', '.join(sorted(ALL_VEHICLE_PROTOTYPES.keys()))}|n."
            )
        except Exception as e:
            caller.msg(f"|rCould not create vehicle: {e}|n")


class CmdDamageVehicle(Command):
    """
    Damage a vehicle part (for testing / admin). Builder or Admin only.
    Usage: damagevehicle <vehicle> <part> [amount]
    """
    key = "damagevehicle"
    aliases = ["damage vehicle", "breakpart"]
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        caller = self.caller
        loc = caller.location
        args = self.args.strip().split()
        if len(args) < 2:
            caller.msg("Usage: |wdamagevehicle <vehicle> <part> [amount]|n (amount default 20)")
            return
        try:
            from typeclasses.vehicles import Vehicle
            from world.vehicle_parts import get_part_display_name, get_part_ids
        except ImportError:
            caller.msg("Vehicle parts not available.")
            return
        vehicle = caller.search(args[0], location=loc)
        if not vehicle or not isinstance(vehicle, Vehicle):
            caller.msg("No such vehicle here.")
            return
        part_id = args[1].lower().replace(" ", "_")
        valid = get_part_ids(vehicle)
        if part_id not in valid:
            caller.msg(f"Unknown part for this vehicle. Valid: {', '.join(valid)}")
            return
        amount = int(args[2]) if len(args) > 2 else 20
        amount = max(1, min(100, amount))
        old_c = vehicle.get_part_condition(part_id)
        new_c = vehicle.damage_part(part_id, amount)
        part_name = get_part_display_name(part_id)
        caller.msg(f"Damaged {vehicle.key}'s {part_name}: {old_c}% -> {new_c}%.")


class CmdSpawnMedical(Command):
    """
    Create a set of medical tools in your inventory (for testing or handout). Builder/Admin only.
    Usage: spawnmedical
    """
    key = "spawnmedical"
    aliases = ["spawn medical", "medkit spawn"]
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        caller = self.caller
        from evennia.utils.create import create_object
        created = []
        # One of each common tool
        for typeclass, key in [
            ("typeclasses.medical_tools.Bioscanner", "bioscanner"),
            ("typeclasses.medical_tools.Medkit", "medkit"),
            ("typeclasses.medical_tools.Bandages", "bandages"),
            ("typeclasses.medical_tools.SutureKit", "suture kit"),
            ("typeclasses.medical_tools.Splint", "splint"),
            ("typeclasses.medical_tools.HemostaticAgent", "hemostatic agent"),
            ("typeclasses.medical_tools.Tourniquet", "tourniquet"),
            ("typeclasses.medical_tools.Defibrillator", "defibrillator"),
            ("typeclasses.med_pills.TacrolimusBottle", "tacrolimus"),
            ("typeclasses.med_pills.MycophenolateBottle", "mycophenolate"),
            ("typeclasses.med_pills.CoAmoxiclavBottle", "co-amoxiclav"),
            ("typeclasses.items.Item", "scalpel"),
        ]:
            try:
                obj = create_object(typeclass, key=key, location=caller)
                if key == "scalpel":
                    obj.db.is_scalpel = True
                    obj.db.item_type = "scalpel"
                    obj.db.uses_remaining = 10
                created.append(obj.key)
            except Exception as e:
                logger.log_trace("staff_cmds.CmdSpawnMedical create %s: %s" % (key, e))
        if created:
            caller.msg(f"|gCreated medical tools in your inventory:|n {', '.join(created)}. |wWield|n a tool, then |wuse scanner on <target>|n to scan, or |wapply to <target>|n to treat. (Surgical kit is room-only: use |wspawnor|n in an OR room.)")
        else:
            caller.msg("|rCould not create medical tools.|n")


class CmdSpawnOR(Command):
    """
    Create an operating table in the current room. Builder/Admin only.
    Patients lie on it with |wlie on operating table|n; surgery with |wsurgery <organ>|n.
    Usage: spawnor
    """
    key = "spawnor"
    aliases = ["spawn or", "spawn operating room", "spawn table"]
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        caller = self.caller
        from evennia.utils.create import create_object
        try:
            from typeclasses.medical_tools import OperatingTable
            obj = create_object(
                "typeclasses.medical_tools.OperatingTable",
                key="operating table",
                location=caller.location,
            )
            caller.msg("|gOperating table created here. Patients: |wlie on operating table|n. Surgeon: |wsurgery <organ>|n (patient must be on the table).|n")
        except Exception as e:
            caller.msg(f"|rCould not create operating table: {e}|n")


class CmdSpawnCyberwareStation(Command):
    """
    Create a cyberware customization station in the current room. Builder/Admin only.
    Put cyberware in it, then use it to customize color and descriptions (requires EE 75).
    Usage: spawnstation [name]
    """
    key = "spawnstation"
    aliases = ["spawn station", "spawn cyberware station", "spawn chromework station"]
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        caller = self.caller
        name = (self.args or "cyberware customization station").strip()
        loc = caller.location
        if not loc:
            caller.msg("You need to be in a room to spawn a station.")
            return
        from evennia.utils.create import create_object
        try:
            obj = create_object(
                "typeclasses.cyberware_station.CyberwareCustomizationStation",
                key=name,
                location=loc,
            )
            caller.msg(
                f"|gCyberware customization station |w{name}|n created here. "
                f"|wPut|n cyberware in it, then |wuse {name}|n to customize.|n"
            )
        except Exception as e:
            caller.msg(f"|rCould not create station: {e}|n")


class CmdSpawnSeat(Command):
    """
    Create a seat (chair, couch, bench) in the room. Builder+.
    Usage: spawnseat [name]

    Capacity = how many people can sit (each person takes 1 slot).
    Default capacity is 1. Use @set <seat>/capacity = <number> for larger furniture.
    Use @set <seat>/room_pose = <text> to change how it appears in room look.
    """
    key = "spawnseat"
    aliases = ["spawn seat", "spawn chair", "spawn couch"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        name = (self.args or "chair").strip()
        from evennia.utils.create import create_object
        try:
            from typeclasses.seats import Seat
            seat = create_object("typeclasses.seats.Seat", key=name, location=caller.location)
            caller.msg("|gSeat |w%s|n created here. Players can |wsit on %s|n.|n" % (name, name))
            caller.msg("|yUse |w@set %s/capacity = <number>|y for capacity, |w@set %s/room_pose = <text>|y for appearance.|n" % (name, name))
        except Exception as e:
            caller.msg("|rCould not create seat: %s|n" % e)


class CmdSpawnBed(Command):
    """
    Create a bed (or cot, sofa) in the room. Builder+.
    Usage: spawnbed [name]

    Players can sit OR lie on beds. Capacity uses slots: sitting = 1 slot, lying = 3 slots.
    Default capacity is 1. Recommended: single bed = 4, double bed = 7, couch = 4.
    A couch (capacity 4) can fit: 4 sitting, OR 1 lying + 1 sitting.
    A single bed (capacity 4) can fit: 4 sitting, OR 1 lying + 1 sitting.
    A double bed (capacity 7) can fit: 7 sitting, OR 2 lying + 1 sitting.
    Use @set <bed>/capacity = <number> and @set <bed>/room_pose = <text> to customize.
    """
    key = "spawnbed"
    aliases = ["spawn bed", "spawn cot"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        name = (self.args or "bed").strip()
        from evennia.utils.create import create_object
        try:
            from typeclasses.seats import Bed
            bed = create_object("typeclasses.seats.Bed", key=name, location=caller.location)
            caller.msg("|gBed |w%s|n created here. Players can |wsit on %s|n or |wlie on %s|n.|n" % (name, name, name))
            caller.msg("|yUse |w@set %s/capacity = <number>|y for capacity, |w@set %s/room_pose = <text>|y for appearance.|n" % (name, name))
        except Exception as e:
            caller.msg("|rCould not create bed: %s|n" % e)


class CmdSpawnPod(Command):
    """
    Create a splinter pod in the room. Builder+. Players enter pod, then 'splinter me' to store a clone shard.
    Usage: spawnpod [name]
    """
    key = "spawnpod"
    aliases = ["spawn pod", "spawn splinter pod"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        name = (self.args or "splinter pod").strip()
        from evennia.utils.create import create_object
        try:
            from typeclasses.splinter_pod import SplinterPod
            create_object("typeclasses.splinter_pod.SplinterPod", key=name, location=caller.location)
            caller.msg("|gSplinter pod |w%s|n created here. Players: |wenter pod|n, then |wsplinter me|n to store a clone shard.|n" % name)
        except Exception as e:
            caller.msg("|rCould not create splinter pod: %s|n" % e)


class CmdSpawnDiveRig(Command):
    """
    Create a dive rig in the room. Builder+.

    A dive rig is a reclining chair that allows characters to jack into the Matrix.
    Characters must sit in the rig before using 'jack in'.

    Usage: spawndiverig [name]
    """
    key = "spawndiverig"
    aliases = ["spawn diverig", "spawn rig", "spawn dive rig"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        name = (self.args or "dive rig").strip()
        from evennia.utils.create import create_object
        try:
            from typeclasses.matrix.devices.dive_rig import DiveRig
            rig = create_object("typeclasses.matrix.devices.dive_rig.DiveRig", key=name, location=caller.location)
            caller.msg("|gDive rig |w%s|n created here. Players can |wsit on %s|n then |wjack in|n.|n" % (name, name))
            caller.msg("|yReminder: Link this rig to a Matrix node with |wmatrixlink <node>|y while standing in the rig's location.|n")
        except Exception as e:
            caller.msg("|rCould not create dive rig: %s|n" % e)


# Predefined creature types for spawncreature (key for display, typeclass path)
CREATURE_SPAWN_TYPES = {
    "gutter hulk": ("typeclasses.creatures.GutterHulk", "Gutter Hulk"),
    "gutterhulk": ("typeclasses.creatures.GutterHulk", "Gutter Hulk"),
    "spore runner": ("typeclasses.creatures.SporeRunner", "Spore Runner"),
    "sporerunner": ("typeclasses.creatures.SporeRunner", "Spore Runner"),
    "rust stalker": ("typeclasses.creatures.RustStalker", "Rust Stalker"),
    "ruststalker": ("typeclasses.creatures.RustStalker", "Rust Stalker"),
    "creature": ("typeclasses.creatures.Creature", "Creature"),
}


class CmdSpawnCreature(Command):
    """
    Spawn a PvE creature in the room. Builder+.
    Usage:
      spawncreature list
      spawncreature <type> [= name]
    Types: gutter hulk, spore runner, rust stalker, creature (base).
    """
    key = "spawncreature"
    aliases = ["spawnc"]
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: |wspawncreature list|n or |wspawncreature <type> [= name]|n")
            return
        loc = caller.location
        if not loc:
            caller.msg("You need to be in a room to spawn a creature.")
            return
        if args.lower() == "list":
            caller.msg("|wAvailable creature types:|n gutter hulk, spore runner, rust stalker, creature")
            caller.msg("Use |wspawncreature <type>|n or |wspawncreature <type> = Custom Name|n")
            return
        name = None
        if "=" in args:
            type_part, name = args.split("=", 1)
            type_part = type_part.strip().lower()
            name = name.strip() or None
        else:
            type_part = args.strip().lower()
        entry = CREATURE_SPAWN_TYPES.get(type_part)
        if not entry:
            caller.msg("Unknown type. Use |wspawncreature list|n for options.")
            return
        typeclass_path, default_key = entry
        key = name or default_key
        from evennia.utils.create import create_object
        try:
            creature = create_object(typeclass_path, key=key, location=loc)
            caller.msg("|gCreature |w%s|n spawned here. Use |wcreatureset %s target <player>|n to make it attack, or attack it yourself.|n" % (creature.key, creature.key))
        except Exception as e:
            caller.msg("|rCould not spawn creature: %s|n" % e)


class CmdCreatureSet(Command):
    """
    Set a creature's target so it uses its AI to attack. Builder+.
    Usage:
      creatureset <creature> target <player>   - creature will attack that player every ~8s
      creatureset <creature> notarget          - clear target and stop AI
    If a player attacks a creature, the creature automatically targets them and fights back.
    """
    key = "creatureset"
    aliases = ["cset", "creature target"]
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip().split()
        if len(args) < 2:
            caller.msg("Usage: |wcreatureset <creature> target <player>|n or |wcreatureset <creature> notarget|n")
            return
        creature = caller.search(args[0], location=caller.location)
        if not creature:
            return
        if not getattr(creature.db, "is_creature", False):
            caller.msg("%s is not a creature." % creature.name)
            return
        sub = args[1].lower()
        if sub == "notarget":
            from world.combat.creature_combat import stop_creature_ai_ticker
            creature.db.current_target = None
            creature.db.ai_state = "idle"
            stop_creature_ai_ticker(creature)
            caller.msg("|g%s no longer has a target. AI stopped.|n" % creature.name)
            return
        if sub == "target":
            if len(args) < 3:
                caller.msg("Usage: |wcreatureset <creature> target <player>|n")
                return
            target_name = " ".join(args[2:])
            target = caller.search(target_name, location=caller.location)
            if not target:
                return
            if not hasattr(target, "db") or not hasattr(target.db, "current_hp"):
                caller.msg("That is not a valid target.")
                return
            creature.db.current_target = target
            creature.db.ai_state = "aggro"
            from world.combat.creature_combat import start_creature_ai_ticker
            start_creature_ai_ticker(creature)
            caller.msg("|g%s will now attack %s. AI runs every ~8 seconds.|n" % (creature.name, target.name))
            return
        caller.msg("Use |wtarget <player>|n or |wnotarget|n.")


class CmdDespawn(Command):
    """
    Remove an NPC from the room and delete them from the database. (Admin/Builder only.)
    Usage:
      despawn <target>
    """
    key = "despawn"
    aliases = ["cleanup", "delete_npc"]
    locks = ADMIN_LOCK
    help_category = "Admin"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Usage: despawn <target>")
            return

        # Search for the target in the room
        target = caller.search(self.args)
        if not target:
            return

        # Safety Check: Ensure we aren't deleting a real player
        if target.has_account:
            caller.msg("|rCRITICAL ERROR: Cannot de-spawn a player character.|n")
            return

        name = target.name
        if caller.location and hasattr(caller.location, "contents_get"):
            for v in caller.location.contents_get(content_type="character"):
                if v == caller:
                    continue
                dname = target.get_display_name(v) if hasattr(target, "get_display_name") else name
                v.msg(f"The individual known as {dname} vanishes as the simulation recalibrates.")
        # Permanently delete from the database
        target.delete()

        caller.msg(f"|y[SYSTEM]|n Entity '|w{name}|n' has been purged from the sector.")


class CmdNpc(Command):
    """
    List, summon, unsummon, rename, or set base attributes on NPCs. Builder+.
    Usage:
      @npc/list                          - list NPC templates
      @npc/summon <template>             - summon NPC from template
      @npc/summon <template>=<name>      - summon and set name
      @npc/unsummon <npc>                - remove NPC from the world
      @npc/rename <npc>=<name>           - rename NPC (IC)
      @npc/attr <npc>/<attr>=<value>     - set NPC base stat or skill
    """
    key = "@npc"
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        raw = (self.args or "").strip()
        # Parse subcommand: first word (e.g. "list" or "summon ..."); allow leading slash (@npc/list)
        parts = raw.split(None, 1)
        sub = (parts[0].lower() if parts else "").lstrip("/")
        rest = (parts[1] if len(parts) > 1 else "").strip()

        if sub == "list":
            self._do_list(caller)
            return
        if sub == "summon":
            self._do_summon(caller, rest)
            return
        if sub == "unsummon":
            self._do_unsummon(caller, rest)
            return
        if sub == "rename":
            self._do_rename(caller, rest)
            return
        if sub == "attr":
            self._do_attr(caller, rest)
            return
        caller.msg("Usage: @npc/list | @npc/summon <template>[=<name>] | @npc/unsummon <npc> | @npc/rename <npc>=<name> | @npc/attr <npc>/<attr>=<value>")

    def _do_list(self, caller):
        from world.rpg.npc_templates import NPC_TEMPLATES
        from evennia.utils.evtable import EvTable
        table = EvTable("|wtemplate|n", "|wdescription|n", border="cells")
        for key, t in sorted(NPC_TEMPLATES.items()):
            table.add_row(key, t.get("name", key))
        caller.msg("|wNPC templates:|n |w@npc/summon <template>|n or |w@npc/summon <template>=<name>|n")
        caller.msg(table)

    def _do_summon(self, caller, rest):
        from world.rpg.npc_templates import create_npc_from_template, get_npc_template
        name = None
        if "=" in rest:
            template_part, name = rest.split("=", 1)
            template_key = template_part.strip().lower()
            name = name.strip()
        else:
            template_key = rest.strip().lower()
        if not template_key:
            caller.msg("Usage: @npc/summon <template> or @npc/summon <template>=<name>")
            return
        if get_npc_template(template_key) is None:
            caller.msg("|rUnknown template. Use |w@npc/list|n for templates.|n")
            return
        # Allow random name generation via Evennia's contrib name generator.
        # Usage example: @npc/summon ganger=rand  (or =random / =*)
        if name and name.lower() in ("random", "rand", "*"):
            try:
                from evennia.contrib.utils.name_generator import namegen
                name = namegen.full_name()
            except Exception:
                # If the name generator is unavailable, fall back silently to template-default naming.
                name = None
        loc = caller.location
        if not loc:
            caller.msg("You have no location.")
            return
        npc = create_npc_from_template(template_key, name=name, location=loc)
        if not npc:
            caller.msg("|rFailed to create NPC.|n")
            return
        caller.msg("|gSummoned:|n %s." % npc.name)
        if hasattr(loc, "contents_get"):
            for v in loc.contents_get(content_type="character"):
                if v == caller:
                    continue
                v.msg("%s appears." % (npc.get_display_name(v) if hasattr(npc, "get_display_name") else npc.name))
        else:
            loc.msg_contents("%s appears." % npc.name, exclude=caller)

    def _do_unsummon(self, caller, rest):
        if not rest:
            caller.msg("Usage: @npc/unsummon <npc>")
            return
        target = caller.search(rest)
        if not target:
            return
        if getattr(target, "has_account", False):
            caller.msg("|rCannot unsummon a player character.|n")
            return
        name = target.name
        if caller.location and hasattr(caller.location, "contents_get"):
            for v in caller.location.contents_get(content_type="character"):
                if v == caller:
                    continue
                v.msg("%s vanishes." % (target.get_display_name(v) if hasattr(target, "get_display_name") else name))
        target.delete()
        caller.msg("|y%s has been unsummoned.|n" % name)

    def _do_rename(self, caller, rest):
        if "=" not in rest:
            caller.msg("Usage: @npc/rename <npc>=<name>")
            return
        npc_part, new_name = rest.split("=", 1)
        npc_part = npc_part.strip()
        new_name = new_name.strip()
        if not npc_part or not new_name:
            caller.msg("Usage: @npc/rename <npc>=<name>")
            return
        target = caller.search(npc_part)
        if not target:
            return
        if getattr(target, "has_account", False):
            caller.msg("|rThat is a player character.|n")
            return
        old = target.name
        room_msg_pairs = []
        if caller.location and caller.location == target.location and hasattr(caller.location, "contents_get"):
            for v in caller.location.contents_get(content_type="character"):
                if v in (caller, target):
                    continue
                old_d = target.get_display_name(v) if hasattr(target, "get_display_name") else old
                room_msg_pairs.append((v, old_d))
        target.key = new_name
        target.save()

        # Check if key was auto-corrected (validation happens in save())
        if target.key != new_name:
            caller.msg("|gYou know them as %s now.|n (auto-corrected from '%s')" % (target.key, new_name))
        else:
            caller.msg("|gYou know them as %s now.|n" % new_name)
        for v, old_d in room_msg_pairs:
            v.msg("%s is now called %s." % (old_d, new_name))

    def _do_attr(self, caller, rest):
        # @npc/attr <npc>/<attr>=<value>
        if "/" not in rest or "=" not in rest:
            caller.msg("Usage: @npc/attr <npc>/<attr>=<value>")
            return
        npc_part, rhs = rest.split("=", 1)
        rhs = rhs.strip()
        if "/" not in npc_part:
            caller.msg("Usage: @npc/attr <npc>/<attr>=<value>")
            return
        npc_spec, attr = npc_part.strip().rsplit("/", 1)
        npc_spec = npc_spec.strip()
        attr = attr.strip().lower()
        if not npc_spec or not attr or not rhs:
            caller.msg("Usage: @npc/attr <npc>/<attr>=<value>")
            return
        target = caller.search(npc_spec)
        if not target:
            return
        if getattr(target, "has_account", False):
            caller.msg("|rThat is a player character.|n")
            return
        try:
            value = int(rhs)
        except ValueError:
            caller.msg("|rValue must be an integer.|n")
            return
        from world.skills import SKILL_KEYS
        from world.rpg.chargen import STAT_KEYS
        if attr in STAT_KEYS:
            if not hasattr(target.db, "stats") or target.db.stats is None:
                target.db.stats = {}
            target.db.stats[attr] = max(0, min(300, value))
            caller.msg("|g%s's %s is now %s.|n" % (target.name, attr, target.db.stats[attr]))
            return
        if attr in SKILL_KEYS:
            if not hasattr(target.db, "skills") or target.db.skills is None:
                from world.skills import SKILL_KEYS as SK
                target.db.skills = {k: 0 for k in SK}
            target.db.skills[attr] = max(0, min(150, value))
            caller.msg("|g%s's %s is now %s.|n" % (target.name, attr, target.db.skills[attr]))
            return
        caller.msg("|rUnknown attribute. Use a stat (%s) or skill (e.g. evasion, medicine).|n" % ", ".join(STAT_KEYS))


class CmdSpawnPerfume(Command):
    """
    Spawn a test perfume bottle in your inventory for smell/Charisma testing. Builder+.

    Usage:
      spawnperfume
    """
    key = "spawnperfume"
    aliases = ["spawn perfume", "testperfume"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        try:
            from typeclasses.perfume import spawn_example_perfume

            bottle = spawn_example_perfume(caller)
        except Exception as e:
            caller.msg(f"|rCould not spawn perfume: {e}|n")
            return
        caller.msg(
            f"|gSpawned perfume|n |w{bottle.get_display_name(caller)}|n in your inventory. "
            f"Use |wuse perfume|n to apply it."
        )


class CmdBadSmellRoom(Command):
    """
    Configure a room as a bad-smell tile that can tag passersby with a lingering stink.

    Usage (in the room to affect):
      @badsmellroom                        - attach script with defaults or show current settings
      @badsmellroom off                    - remove the bad-smell script from this room
      @badsmellroom chance=<0-1>           - set chance per entry (e.g. 0.5)
      @badsmellroom phrase=<text>          - set scent phrase (e.g. like gutter runoff and stale garbage)
      @badsmellroom duration=<seconds>     - set duration in seconds (default ~3h)

    Each time someone enters the room, a roll is made; on success they get
    a bad-smell overlay and -Charisma until it wears off.
    """

    key = "@badsmellroom"
    aliases = ["@smellyroom"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        from evennia.utils.create import create_script

        caller = self.caller
        room = caller.location
        if not room:
            caller.msg("You must be in a room to configure it.")
            return

        # Find existing script on this room, if any
        existing = None
        for scr in room.scripts.all():
            if scr.key == "bad_smell_room_script":
                existing = scr
                break

        if existing is None:
            try:
                existing = create_script("world.smell.BadSmellRoomScript", obj=room)
            except Exception as e:
                caller.msg(f"|rCould not attach bad-smell script: {e}|n")
                return

        raw = (self.args or "").strip()

        # Handle turning the effect off entirely.
        if raw.lower() in ("off", "remove", "clear", "none"):
            if existing:
                existing.delete()
                caller.msg("|gBad-smell effect removed from this room.|n")
            else:
                caller.msg("This room does not currently have a bad-smell effect.")
            return

        scr = existing
        if not raw:
            phrase = scr.db.bad_scent_phrase or "like rot and cheap solvent"
            chance = float(scr.db.chance or 0.35)
            duration = int(scr.db.duration or 0)
            caller.msg("|wBad-smell room settings for this room:|n")
            caller.msg(f"  |wphrase|n: {phrase}")
            move_suffix = getattr(scr.db, "move_suffix", "") or "(auto: who smells <phrase>)"
            smell_suffix = getattr(scr.db, "smell_suffix", "") or "(auto line from phrase)"
            caller.msg(f"  |wmove_suffix|n: {move_suffix}")
            caller.msg(f"  |wsmell_suffix|n: {smell_suffix}")
            caller.msg(f"  |wchance|n: {chance:.2f} per entry")
            if duration > 0:
                caller.msg(f"  |wduration|n: {duration} seconds (~{duration//3600}h)")
            else:
                caller.msg("  |wduration|n: (default from world.smell)")
            caller.msg("Use |w@badsmellroom phrase=<text>|n, |wmove=<suffix>|n, |wsmell=<suffix>|n, |wchance=<0-1>|n, |wduration=<seconds>|n to change, or |w@badsmellroom off|n to remove.")
            return

        changed = []

        lower_raw = raw.lower()

        # phrase=<...> may contain spaces; capture everything between 'phrase=' and the next known key or end.
        if "phrase=" in lower_raw:
            start = lower_raw.index("phrase=") + len("phrase=")
            # Find the earliest of other keys after phrase=
            next_idxs = []
            for marker in (" move=", " smell=", " chance=", " duration="):
                idx = lower_raw.find(marker, start)
                if idx != -1:
                    next_idxs.append(idx)
            end = min(next_idxs) if next_idxs else len(raw)
            phrase_val = raw[start:end].strip()
            if phrase_val:
                scr.db.bad_scent_phrase = phrase_val
                changed.append(f"phrase='{phrase_val}'")

        # move=<...> may contain spaces; capture similar to phrase.
        if " move=" in lower_raw:
            start = lower_raw.index(" move=") + len(" move=")
            next_idxs = []
            for marker in (" phrase=", " smell=", " chance=", " duration="):
                idx = lower_raw.find(marker, start)
                if idx != -1:
                    next_idxs.append(idx)
            end = min(next_idxs) if next_idxs else len(raw)
            move_val = raw[start:end].strip()
            if move_val:
                scr.db.move_suffix = move_val
                changed.append(f"move_suffix='{move_val}'")

        # smell=<...> may contain spaces; capture similar to phrase.
        if " smell=" in lower_raw:
            start = lower_raw.index(" smell=") + len(" smell=")
            next_idxs = []
            for marker in (" phrase=", " move=", " chance=", " duration="):
                idx = lower_raw.find(marker, start)
                if idx != -1:
                    next_idxs.append(idx)
            end = min(next_idxs) if next_idxs else len(raw)
            smell_val = raw[start:end].strip()
            if smell_val:
                scr.db.smell_suffix = smell_val
                changed.append(f"smell_suffix='{smell_val}'")

        # chance=VALUE (single token)
        import re as _re
        m_chance = _re.search(r"\bchance=([^\s]+)", raw, flags=_re.IGNORECASE)
        if m_chance:
            val_str = m_chance.group(1).strip()
            try:
                val = float(val_str)
                val = max(0.0, min(1.0, val))
                scr.db.chance = val
                changed.append(f"chance={val:.2f}")
            except ValueError:
                caller.msg("Chance must be a number between 0 and 1 (e.g. 0.35).")

        # duration=VALUE (single token, seconds)
        m_dur = _re.search(r"\bduration=([^\s]+)", raw, flags=_re.IGNORECASE)
        if m_dur:
            dur_str = m_dur.group(1).strip()
            try:
                dur = int(dur_str)
                if dur < 0:
                    dur = 0
                scr.db.duration = dur
                changed.append(f"duration={dur}s")
            except ValueError:
                caller.msg("Duration must be an integer number of seconds.")
        if changed:
            caller.msg("|gUpdated bad-smell room script:|n " + ", ".join(changed))
        else:
            caller.msg("No valid settings were changed.")


class CmdSpawnCamera(Command):
    """Create a camera in the current room. (Builder+.)"""
    key = "@spawncamera"
    aliases = ["@spawn camera"]
    locks = ADMIN_LOCK
    help_category = "Admin"

    def func(self):
        caller = self.caller
        loc = caller.location
        if not loc:
            caller.msg("You need to be in a room.")
            return
        from evennia.utils.create import create_object
        try:
            cam = create_object("typeclasses.broadcast.Camera", key="camera", location=loc)
            caller.msg("|gCreated|n |w%s|n here. Use |wcamera record|n, |wcamera live <tv>|n, |wcamera stop|n." % cam.key)
        except Exception as e:
            caller.msg("|rCould not create camera: %s|n" % e)


class CmdSpawnTelevision(Command):
    """Create a television in the current room. (Builder+.)"""
    key = "@spawntv"
    aliases = ["@spawn television", "@spawn tv"]
    locks = ADMIN_LOCK
    help_category = "Admin"

    def func(self):
        caller = self.caller
        loc = caller.location
        if not loc:
            caller.msg("You need to be in a room.")
            return
        from evennia.utils.create import create_object
        try:
            tv = create_object("typeclasses.broadcast.Television", key="television", location=loc)
            caller.msg("|gCreated|n |w%s|n here. |wPut|n a cassette in it and |wtune television|n to play." % tv.key)
        except Exception as e:
            caller.msg("|rCould not create television: %s|n" % e)


class CmdGiveXp(Command):
    """
    Grant XP to a character. (Admin/Builder only.)

    Usage:
      givexp <amount> [= target]
      givexp <amount>      (grants to yourself)
    """
    key = "givexp"
    aliases = ["grantxp", "xp grant"]
    locks = ADMIN_LOCK
    help_category = "Admin"

    def func(self):
        caller = self.caller
        from world.rpg.xp import XP_CAP

        if not self.args:
            caller.msg("Usage: givexp <amount> [= target]")
            return

        parts = self.args.strip().split(None, 1)
        try:
            amount = int(parts[0])
        except ValueError:
            caller.msg("Amount must be a number.")
            return
        if amount < 0:
            caller.msg("Amount must be positive.")
            return

        if len(parts) > 1:
            rest = parts[1].strip()
            if rest.startswith("="):
                rest = rest[1:].strip()
            target = caller.search(rest)
        else:
            target = caller

        if not target:
            return
        if not hasattr(target, "db") or not hasattr(target.db, "xp"):
            caller.msg(f"{target.name} doesn't have an XP attribute.")
            return

        cap = int(getattr(target.db, "xp_cap", XP_CAP) or XP_CAP)
        current = int(getattr(target.db, "xp", 0) or 0)
        new_total = min(current + amount, cap)
        added = new_total - current
        target.db.xp = new_total

        if target == caller:
            caller.msg(f"|g[ADMIN]|n Granted |w{added}|n XP. Total: |w{new_total}|n / {cap}.")
        else:
            caller.msg(f"|g[ADMIN]|n Granted |w{added}|n XP to |w{target.name}|n. Their total: |w{new_total}|n / {cap}.")
            target.msg(f"|g[ADMIN]|n You received |w{added}|n XP. Total: |w{new_total}|n / {cap}.")


class CmdBuffDebug(Command):
    """
    Inspect BuffHandler state and the stat/skill check chain (staff).

    Usage:
      @buffdebug
      @buffdebug <stat>
    """

    key = "@buffdebug"
    aliases = ["buffdebug"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        stat = (self.args or "").strip() or "strength"
        from world.rpg.xp import _stat_level

        raw = _stat_level(caller, stat)
        base = min(max((raw or 0) // 2, 0), 150)

        if not hasattr(caller, "buffs"):
            caller.msg("|rNo BuffHandler on this character.|n")
            return

        try:
            buffed = caller.buffs.check(base, f"{stat}_display")
        except Exception as err:
            caller.msg(f"|rafter buffs.check: {err}|n")
            buffed = base

        final = caller.get_display_stat(stat) if hasattr(caller, "get_display_stat") else base

        caller.msg(f"|wRaw stored:|n {raw}")
        caller.msg(f"|wBase display (raw//2):|n {base}")
        caller.msg(f"|wAfter buffs.check:|n {buffed}")
        caller.msg(f"|wFinal get_display_stat:|n {final}")

        try:
            buff_list = list(caller.buffs.get_all().values())
            caller.msg(f"|wActive buffs ({len(buff_list)}):|n")
            for b in buff_list:
                key = getattr(b, "key", "?")
                dur = getattr(b, "duration", "?")
                mods = getattr(b, "mods", [])
                sm = getattr(type(b), "stat_mods", {})
                caller.msg(f"  {key}: duration={dur}, mods={mods}, stat_mods={sm}")
        except Exception as e:
            caller.msg(f"|rError listing buffs: {e}|n")


class CmdEmoteDebug(Command):
    """
    Toggle emote debug mode. When on, after each emote you see what every
    viewer saw: you, each target, and everyone else in the room.

    Usage:
      emotedebug
    """
    key = "emotedebug"
    locks = ADMIN_LOCK
    help_category = "Admin"

    def func(self):
        current = getattr(self.caller.db, "emote_debug", False)
        self.caller.db.emote_debug = not current
        status = "on" if self.caller.db.emote_debug else "off"
        self.caller.msg(f"Emote debug is now |w{status}|n. Use an emote to see each viewer's line.")


class CmdNextNote(Command):
    """
    Review the next unread PC note. Read-tracking is per staff Account.

    Usage:
      @nextnote          - show the next unread note and mark it read
      @nextnote/peek     - show next unread note without marking read
      @nextnote/count    - show how many unread notes you have
    """

    key = "@nextnote"
    aliases = ["nextnote", "@next-note"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def _border_line(self):
        # Keep it short so it doesn't wrap on typical telnet widths.
        return f"|g{'-' * 38}|n"

    def _format_server_time(self, created_at, *, fmt="%Y-%m-%d %H:%M"):
        if not created_at:
            return "?"
        try:
            dt = datetime.fromisoformat(str(created_at))
        except ValueError:
            return str(created_at)
        try:
            dt = dt.astimezone()
        except Exception:
            pass
        return dt.strftime(fmt)

    def _truncate(self, text, *, limit):
        if text is None:
            return ""
        txt = str(text).strip()
        if len(txt) <= limit:
            return txt
        return txt[: max(0, limit - 3)] + "..."

    def func(self):
        from world.notes import staff_unread_notes, staff_mark_read

        caller = self.caller
        account = self.account or getattr(caller, "account", None) or caller
        # Some command base implementations may not set `self.switches` at all.
        switches = [s.lower() for s in getattr(self, "switches", [])]

        unread = staff_unread_notes(account)
        if "count" in switches:
            caller.msg(f"|wUnread PC notes for you:|n |w{len(unread)}|n")
            return

        if not unread:
            caller.msg("You have no unread PC notes.")
            return

        note = unread[0]
        nid = int(note.get("id") or 0)

        created_txt = self._format_server_time(note.get("created_at"))
        caller.msg(
            f"{self._border_line()}\n"
            f"|gPC Note|n |y#{note.get('id')}|n  |c{(note.get('category') or 'UNCATEGORIZED').strip().upper()}|n\n"
            f"|w{note.get('title') or '(untitled)'}|n\n"
            f"|xFrom|n: |w{note.get('char_key') or 'Unknown'}|n"
            f" |x(account)|n: |w{note.get('account_key') or 'Unknown'}|n\n"
            f"|xCreated|n: |x({created_txt})|n\n"
            f"{self._border_line()}\n"
            f"{note.get('body') or ''}"
        )

        if "peek" not in switches:
            staff_mark_read(account, nid)
            remaining = len(unread) - 1
            if remaining > 0:
                caller.msg(f"|xMarked read. Remaining unread for you: {remaining}.|n")


class CmdGmViewNotes(Command):
    """
    View a player's PC notes (with optional category filter and paging). Builder+.

    Usage:
      @gmviewnotes <character>                 - newest first, first page
      @gmviewnotes <character>=<category>      - filter by category
      @gmviewnotes/page <N> <character>        - page N (all categories)
      @gmviewnotes/page <N> <character>=<cat>  - page N, filtered by category
      @gmviewnotes <character> <note_id>     - show a specific note (by #id)
      @gmviewnotes <note_id>                 - show a specific note (by #id)
    """

    key = "@gmviewnotes"
    aliases = ["gmviewnotes", "@gm-notes"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def _border_line(self):
        return f"|g{'-' * 38}|n"

    def _format_server_time(self, created_at, *, fmt="%Y-%m-%d %H:%M"):
        if not created_at:
            return "?"
        try:
            dt = datetime.fromisoformat(str(created_at))
        except ValueError:
            return str(created_at)
        try:
            dt = dt.astimezone()
        except Exception:
            pass
        return dt.strftime(fmt)

    def _truncate(self, text, *, limit):
        if text is None:
            return ""
        txt = str(text).strip()
        if len(txt) <= limit:
            return txt
        return txt[: max(0, limit - 3)] + "..."

    def func(self):
        from world.notes import (
            notes_for_character_name,
            DEFAULT_CATEGORIES,
            get_note_by_id,
            staff_mark_read,
        )

        caller = self.caller
        account = self.account or getattr(caller, "account", None) or caller

        # Some command base implementations may not set `self.switches` at all.
        switches = [s.lower() for s in getattr(self, "switches", [])]
        raw = (self.args or "").strip()
        if not raw:
            cats_txt = ", ".join(DEFAULT_CATEGORIES)
            caller.msg(
                "Usage:\n"
                "  @gmviewnotes <character>\n"
                "  @gmviewnotes <character>=<category>\n"
                "  @gmviewnotes/page <N> <character>\n"
                "  @gmviewnotes/page <N> <character>=<category>\n"
                "  @gmviewnotes <character> <note_id>\n"
                "  @gmviewnotes <note_id>\n"
                f"Categories: |w{cats_txt}|n"
            )
            return

        page = 1
        target_part = raw

        # Support "@gmviewnotes/page <N> ..." even in templates that don't
        # populate `self.switches` correctly.
        if "page" in switches or (not switches and raw.split(None, 1) and raw.split(None, 1)[0].isdigit()):
            parts = raw.split(None, 1)
            if parts and parts[0].isdigit():
                try:
                    page = max(1, int(parts[0]))
                except ValueError:
                    page = 1
                target_part = parts[1] if len(parts) > 1 else ""

        if not target_part:
            caller.msg("Specify a character name.")
            return

        note_id = None
        note_only = False

        # Allow "@gmviewnotes <note_id>" to view a single note directly.
        if target_part.isdigit():
            note_id = int(target_part)
            note_only = True
        else:
            # Allow "@gmviewnotes <character>[=<cat>] <note_id>".
            # Capture trailing numeric token so character names can still include '=' once.
            import re

            m = re.match(r"^(?P<main>.+?)\s+(?P<nid>\d+)\s*$", target_part, flags=re.I)
            if m:
                try:
                    note_id = int(m.group("nid"))
                    target_part = m.group("main").strip()
                except ValueError:
                    note_id = None

        # Optional "=CATEGORY"
        if "=" in target_part:
            char_name, category = target_part.split("=", 1)
            char_name = char_name.strip()
            category = category.strip().upper()
            if category and category not in DEFAULT_CATEGORIES:
                cats_txt = ", ".join(DEFAULT_CATEGORIES)
                caller.msg(f"|rInvalid category.|n Choose one of: |w{cats_txt}|n.")
                return
        else:
            char_name = target_part.strip()
            category = None

        # If the user only passed a note id, don't treat it as a character name.
        if note_only:
            char_name = ""
            category = None

        if not char_name:
            if note_id is None:
                caller.msg("Specify a character name or a note id.")
                return

        # Helper: display a single note body.
        def _display_note(note: dict) -> None:
            nid = note.get("id")
            cat = str(note.get("category") or "UNCATEGORIZED").strip().upper()
            created_txt = self._format_server_time(note.get("created_at"))
            caller.msg(
                f"{self._border_line()}\n"
                f"|gPC Note|n |y#{nid}|n  |c{cat}|n\n"
                f"|w{note.get('title') or '(untitled)'}|n\n"
                f"|xFrom|n: |w{note.get('char_key') or 'Unknown'}|n"
                f" |x(account)|n: |w{note.get('account_key') or 'Unknown'}|n\n"
                f"|xCreated|n: |x({created_txt})|n\n"
                f"{self._border_line()}\n"
                f"{note.get('body') or ''}"
            )
            if note_id is not None:
                staff_mark_read(account, int(note_id))
                caller.msg("|xMarked read.|n")

        # If a note id was specified, show it (and mark read).
        if note_id is not None:
            note = get_note_by_id(note_id)
            if not note:
                caller.msg(f"No note found with |y#{note_id}|n.")
                return

            # If the user also provided a character name, ensure it matches.
            if char_name:
                expected = char_name.strip().lower()
                if (note.get("char_key") or "").strip().lower() != expected:
                    caller.msg(
                        f"|rThat note (|y#{note_id}|r) is not for |w{char_name}|n."
                    )
                    return
                if category:
                    wanted = category.strip().lower()
                    if (note.get("category") or "").strip().lower() != wanted:
                        caller.msg(
                            f"|rThat note (|y#{note_id}|r) is not in category |w{category}|n."
                        )
                        return

            _display_note(note)
            return

        notes = notes_for_character_name(char_name, category=category)
        if not notes:
            if category:
                caller.msg(
                    f"No notes found for |w{char_name}|n in category |w{category}|n "
                    "(note names are matched by exact key at time of note creation)."
                )
            else:
                caller.msg(
                    f"No notes found for |w{char_name}|n "
                    "(note names are matched by exact key at time of note creation)."
                )
            return

        per_page = 10
        total = len(notes)
        max_page = (total + per_page - 1) // per_page or 1
        if page > max_page:
            page = max_page
        start = (page - 1) * per_page
        end = start + per_page
        page_notes = notes[start:end]

        char_key = notes[0].get("char_key", char_name)

        lines = [
            self._border_line(),
            f"|gNotes|n for |w{char_key}|n",
        ]
        if category:
            lines.append(f"|cCategory|n: |w{category}|n")
        lines.append(f"|x(page {page}/{max_page}, newest first)|n")
        lines.append(
            "Use |w@gmviewnotes <character> <id>|n or |w@gmviewnotes <id>|n to view a note, or page again."
        )
        for n in page_notes:
            nid = n.get("id")
            cat = str(n.get("category") or "UNCATEGORIZED").strip().upper()
            title = self._truncate(n.get("title", ""), limit=42)
            created_txt = self._format_server_time(n.get("created_at"))
            lines.append(
                f"  |y#{nid}|n  |c{cat}|n  |w{title}|n |x({created_txt})|n"
            )
        lines.append(self._border_line())
        caller.msg("\n".join(lines))


class StaffCharCreate(CmdCharCreate):
    """Character creation: staff only (players get one character at account creation)."""

    locks = "cmd:perm(Builder)"


class StaffCharDelete(CmdCharDelete):
    """Character deletion: staff only."""

    locks = "cmd:perm(Builder)"

class CmdProfiling(Command):
    """
    View server performance metrics and toggle profiling modes.

    Usage:
      @profiling              view current metrics
      @profiling/timing       toggle wall-clock and DB query timing on/off
      @profiling/reset        clear all aggregates (baselines are kept)

    Always-on metrics (command rate, object counts, script ticks, RSS memory)
    are shown regardless of timing mode. The /timing switch enables per-command
    wall-clock measurement and DB query counting; it sets settings.DEBUG=True
    while active, which has a small memory cost per query — disable when done.

    Budget thresholds are calibrated for 300 concurrent users.
    """
    key = "@profiling"
    aliases = ["@prof"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        from world.profiling import get_profiling_script, BUDGETS

        script = get_profiling_script()
        if not script:
            caller.msg("|rProfiler script not found. Try @reload or check at_server_start.|n")
            return

        if "timing" in self.switches:
            self._toggle_timing(caller, script)
            return

        if "reset" in self.switches:
            script.ndb.cmd_counts = {}
            script.ndb.cmd_rate_buckets = {}
            script.ndb.script_ticks = {}
            caller.msg("|gProfiler aggregates cleared.|n Baselines retained.")
            return

        self._show(caller, script)

    def _toggle_timing(self, caller, script):
        current = bool(script.ndb.timing_enabled)
        new_state = not current
        script.ndb.timing_enabled = new_state
        if new_state:
            try:
                from django.conf import settings
                settings.DEBUG = True
            except Exception:
                pass
            caller.msg("|gTiming enabled.|n settings.DEBUG=True — query counting active. Disable when done.")
        else:
            try:
                from django.conf import settings
                from django.db import reset_queries
                settings.DEBUG = False
                reset_queries()
            except Exception:
                pass
            caller.msg("|yTiming disabled.|n settings.DEBUG restored to False.")

    def _show(self, caller, script):
        import time
        import sys
        from world.profiling import get_cmd_rate_1min, get_p95, BUDGETS
        from world.ui_utils import fade_rule
        from evennia.utils.evtable import EvTable

        timing = bool(script.ndb.timing_enabled)
        start_time = script.ndb.start_time or time.time()
        uptime_s = int(time.time() - start_time)
        h, m = divmod(uptime_s // 60, 60)
        try:
            from evennia.server.sessionhandler import SESSION_HANDLER
            session_count = SESSION_HANDLER.count()
        except Exception:
            session_count = "?"

        w = 65
        rule = "|c" + fade_rule(w - 2, "=") + "|n"
        timing_label = "|gON|n" if timing else "|yOFF|n"
        caller.msg(rule)
        caller.msg(f"|wServer Profiling|n   Uptime: {h}h {m}m | Sessions: {session_count} | Timing: {timing_label}")
        caller.msg(rule)

        # --- Always-on ---
        caller.msg("|w[Always-On]|n")

        rate = get_cmd_rate_1min(script)
        budget_rate = BUDGETS["cmd_rate_per_min"]
        rate_status = "|gOK|n" if rate <= budget_rate else "|rOVER|n"
        caller.msg(f"  Cmd rate (1m):   {rate:<6}  budget: {budget_rate}/min   {rate_status}")

        try:
            from evennia.scripts.models import ScriptDB
            scount = ScriptDB.objects.count()
            baseline = script.ndb.script_count_baseline or scount
            sdelta = scount - baseline
            if sdelta == 0:
                s_status = "|gOK|n"
            elif sdelta > 0:
                s_status = f"|rCHANGED (+{sdelta})|n"
            else:
                s_status = f"|yCHANGED ({sdelta})|n"
            caller.msg(f"  ScriptDB count:  {scount:<6}  baseline: {baseline}   {s_status}")
        except Exception:
            caller.msg("  ScriptDB count:  |yunavailable|n")

        try:
            import resource as _res
            rss_raw = _res.getrusage(_res.RUSAGE_SELF).ru_maxrss
            baseline_raw = script.ndb.rss_baseline_kb or rss_raw
            # macOS: ru_maxrss is bytes; Linux: kilobytes
            divisor = (1024 * 1024) if sys.platform == "darwin" else 1024
            rss_mb = rss_raw / divisor
            base_mb = baseline_raw / divisor
            delta_mb = rss_mb - base_mb
            sign = "+" if delta_mb >= 0 else ""
            caller.msg(f"  RSS memory:      {rss_mb:.0f} MB   baseline: {base_mb:.0f} MB   ({sign}{delta_mb:.0f} MB)")
        except Exception:
            caller.msg("  RSS memory:      |yunavailable|n")

        # --- Object counts (cached from cleanup cycles) ---
        caller.msg("\n|w[Object Counts]|n  |x(updated each cleanup cycle)|n")
        obj_counts = script.ndb.object_counts or {}
        if not obj_counts:
            caller.msg("  |yNo snapshot yet — waiting for first cleanup cycle.|n")
        else:
            for name, count in sorted(obj_counts.items()):
                caller.msg(f"  {name:<30} {count}")

        # --- Script ticks ---
        caller.msg("\n|w[Script Ticks]|n")
        ticks = script.ndb.script_ticks or {}
        if not ticks:
            caller.msg("  |yNo tick data yet — waiting for first script cycle.|n")
        else:
            for key, entry in sorted(ticks.items()):
                interval_s = entry.get("interval_s") or 1
                budget_ms = interval_s * BUDGETS["script_tick_pct"] * 1000
                last_ms = entry.get("last_ms", 0.0)
                max_ms = entry.get("max_ms", 0.0)
                calls = entry.get("calls", 0)
                t_status = "|gOK|n" if max_ms < budget_ms else "|rWARN|n"
                caller.msg(
                    f"  {key:<25} last: {last_ms:6.1f}ms  max: {max_ms:6.1f}ms"
                    f"  calls: {calls:<4}  budget: <{budget_ms:.0f}ms  {t_status}"
                )

        # --- Command timings ---
        caller.msg("\n|w[Command Timings]|n")
        if not timing:
            caller.msg("  |yOFF — use @profiling/timing to enable.|n")
        else:
            counts = script.ndb.cmd_counts or {}
            if not counts:
                caller.msg("  |yNo data yet — run some commands first.|n")
            else:
                t = EvTable(
                    "cmd", "calls", "avg_ms", "p95_ms", "max_ms", "queries", "status",
                    border="none", pad_width=1,
                )
                for cmd_key, entry in sorted(counts.items(), key=lambda x: -x[1]["calls"]):
                    calls = entry["calls"]
                    avg_ms = entry["total_ms"] / calls if calls else 0.0
                    max_ms = entry["max_ms"]
                    p95_ms = get_p95(entry.get("ms_samples", []))
                    avg_q = entry["total_queries"] / calls if calls else 0.0
                    if max_ms > BUDGETS["cmd_max_ms"] or p95_ms > BUDGETS["cmd_p95_ms"]:
                        st = "|rCRIT|n"
                    elif avg_ms > BUDGETS["cmd_avg_ms"] or avg_q > BUDGETS["cmd_queries_warn"]:
                        st = "|yWARN|n"
                    else:
                        st = "|gOK|n"
                    t.add_row(
                        cmd_key, calls,
                        f"{avg_ms:.1f}", f"{p95_ms:.1f}", f"{max_ms:.1f}",
                        f"{avg_q:.1f}", st,
                    )
                caller.msg(str(t))

        caller.msg(rule)


class CmdClimate(Command):
    """
    View or set global weather and time-of-day (street room ambient prose).

    Usage:
      @climate
      @climate weather <rain|sun|fog|snow>
      @climate time <dusk|night|morning|afternoon|evening>   (manual; turns off UTC auto)
      @climate time auto|utc   — narrative time follows real UTC (persistent)
      @climate time manual    — freeze at current UTC phase; edit with @climate time <phase>
      @climate override <district> <weather> <time> = <plain text>
      @climate clearoverride <district> <weather> <time>

    Districts: slums, guild, bourgeois, elite
    """
    key = "@climate"
    aliases = ["climate"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        from world import global_climate as gc

        raw = (self.args or "").strip()
        if not raw:
            from datetime import datetime, timezone

            w = gc.get_global_weather()
            t = gc.get_global_time_of_day()
            auto = gc.get_time_auto_utc()
            now = datetime.now(timezone.utc)
            auto_str = "|gON|n (UTC)" if auto else "|rOFF|n (manual)"
            self.caller.msg(
                f"Global climate: |wweather|n={w}  |wtime|n={t}  |wUTC auto|n={auto_str}\n"
                f"  Now UTC: {now.strftime('%Y-%m-%d %H:%M:%S')} → phase |w{gc.utc_time_phase(now)}|n\n"
                f"Use |w@climate weather <...>|n or |w@climate time <...>|n or |w@climate time auto|n / |wmanual|n"
            )
            return

        parts = raw.split()
        sub = parts[0].lower()

        if sub == "weather" and len(parts) >= 2:
            val = parts[1].lower()
            try:
                ok = gc.set_global_weather(val)
            except Exception as err:
                self.caller.msg(str(err))
                return
            if not ok:
                self.caller.msg("Global climate script is missing (server not initialized?).")
                return
            self.caller.msg(f"Global weather set to |w{gc.get_global_weather()}|n.")
            return

        if sub == "time" and len(parts) >= 2:
            val = parts[1].lower()
            if val in ("auto", "utc"):
                ok = gc.set_time_auto_utc(True)
                if not ok:
                    self.caller.msg("Global climate script is missing (server not initialized?).")
                    return
                self.caller.msg(
                    f"UTC auto time |gON|n. Current phase: |w{gc.get_global_time_of_day()}|n."
                )
                return
            if val == "manual":
                ok = gc.set_time_auto_utc(False)
                if not ok:
                    self.caller.msg("Global climate script is missing (server not initialized?).")
                    return
                self.caller.msg(
                    f"UTC auto |rOFF|n; time frozen at |w{gc.get_global_time_of_day()}|n "
                    f"(change with |w@climate time <phase>|n)."
                )
                return
            try:
                ok = gc.set_global_time_of_day(val)
            except Exception as err:
                self.caller.msg(str(err))
                return
            if not ok:
                self.caller.msg("Global climate script is missing (server not initialized?).")
                return
            self.caller.msg(
                f"Global time-of-day set to |w{gc.get_global_time_of_day()}|n (UTC auto |roff|n)."
            )
            return

        if sub == "clearoverride" and len(parts) >= 4:
            district, weather, tod = parts[1], parts[2], parts[3]
            try:
                gc.clear_line_override(district, weather, tod)
            except Exception as err:
                self.caller.msg(str(err))
                return
            self.caller.msg("Override cleared for that cell.")
            return

        if sub == "override":
            rest = raw[len("override") :].strip()
            if "=" not in rest:
                self.caller.msg(
                    'Usage: @climate override <district> <weather> <time> = <text>'
                )
                return
            left, _, right = rest.partition("=")
            left_toks = left.strip().split()
            if len(left_toks) < 3:
                self.caller.msg(
                    'Usage: @climate override <district> <weather> <time> = <text>'
                )
                return
            district, weather, tod = left_toks[0], left_toks[1], left_toks[2]
            text = right.strip()
            try:
                key = gc.set_line_override(district, weather, tod, text)
            except Exception as err:
                self.caller.msg(str(err))
                return
            self.caller.msg(f"Stored override |w{key}|n ({len(text)} chars).")
            return

        self.caller.msg(
            "Usage: @climate | @climate weather <rain|sun|fog|snow> | "
            "@climate time <phase> | @climate time auto|utc | @climate time manual | "
            "@climate override <district> <weather> <time> = <text> | "
            "@climate clearoverride <district> <weather> <time>"
        )


class CmdMusic(Command):
    """
    Play a background track via YouTube ID.

    Usage:
      music <youtube_id>
      music stop

    Example:
      music dQw4w9WgXcQ
    """
    key = "music"
    help_category = "General"
    locks = "cmd:perm(Builder)"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: music <youtube_id> or music stop")
            return

        arg = self.args.strip()

        if arg == "stop":
            # Send the stop signal to the webclient
            self.caller.msg("Stopping audio transmission...")
            self.caller.msg(("stop_music", {}), options={"type": "msg"})
        else:
            # Send the play_yt signal with the ID
            self.caller.msg(f"Initiating uplink for stream ID: {arg}")
            self.caller.msg(("play_yt", [arg], {}), options={"type": "msg"})