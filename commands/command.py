"""
Commands

Commands describe the input the account can do to the game.
"""

import re
from evennia.commands.command import Command as BaseCommand
from evennia.commands.cmdhandler import CMD_NOMATCH
from evennia.utils.evtable import EvTable
from world.combat import execute_combat_turn

# Lock string for admin-only commands (Builder and Admin accounts)
ADMIN_LOCK = "cmd:perm(Builder) or perm(Admin)"

class Command(BaseCommand):
    """
    Base command. Blocks all commands when character is dead (hp <= 0) except for Admins/Builders.
    """
    def at_pre_cmd(self):
        """Block commands if caller is flatlined (dying) or permanently dead."""
        caller = self.caller
        if not caller:
            return super().at_pre_cmd()
        try:
            if caller.account and (caller.account.permissions.check("Builder") or caller.account.permissions.check("Admin")):
                return super().at_pre_cmd()
        except Exception:
            pass
        try:
            from world.death import is_flatlined, is_permanently_dead
            if is_flatlined(caller):
                caller.msg("|rYou are dying. There is nothing you can do.|n")
                return True
            if is_permanently_dead(caller):
                caller.msg("|rYou are dead. Only an administrator can help you now.|n")
                return True
        except Exception:
            pass
        hp = getattr(caller, "hp", None)
        if hp is not None and hp <= 0:
            caller.msg("|rYou are dying. There is nothing you can do.|n")
            return True
        return super().at_pre_cmd()

# -------------------------------------------------------------
# CUSTOM COMMANDS
# -------------------------------------------------------------

class CmdStats(Command):
    """
    Display your character sheet: vitals, SPECIAL stats, and skills.

    Usage:
      stats
      sheet
    """
    key = "stats"
    aliases = ["@stats", "sheet", "score"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.chargen import STAT_KEYS
        from world.skills import SKILL_KEYS, SKILL_DISPLAY_NAMES
        caller = self.caller
        # If caller is Account (no db.stats), use session's puppet so stats/sheet work when puppeted
        if not getattr(caller.db, "stats", None) and getattr(self, "session", None):
            try:
                puppet = getattr(self.session, "puppet", None)
                if puppet:
                    caller = puppet
            except Exception:
                pass
        if not getattr(caller, "db", None) or not hasattr(caller.db, "stats"):
            caller.msg("Puppet a character to view your sheet.")
            return
        stats = caller.db.stats or {}
        skills = caller.db.skills or {}
        bg = caller.db.background or "Unknown"

        # Vitals (guard in case max_hp not ready)
        try:
            hp_str = "{} / {}".format(caller.hp, caller.max_hp)
            st_str = "{} / {}".format(caller.stamina, caller.max_stamina)
            load_str = "{} kg".format(caller.carry_capacity)
        except Exception:
            hp_str = st_str = load_str = "---"

        # Single sheet: fixed order (STAT_KEYS, SKILL_KEYS), safe lookups
        w = 50
        line = "|c+" + "=" * (w - 2) + "+|n"
        thin = "|c|" + "-" * (w - 2) + "||n"
        output = line + "\n"
        output += "|c||n  |W NEURAL LINK  |w BIOMETRIC READOUT|n\n"
        output += "|c|||n  |wSubject|n " + (caller.name or "Unknown").ljust(18) + " |wOrigin|n " + bg + "\n"
        output += thin + "\n"
        output += "|c|||n  |rVitality|n " + hp_str.ljust(12) + " |yStamina|n " + st_str.ljust(12) + " |gLoad|n " + load_str + "\n"
        output += thin + "\n"
        from world.levels import level_to_letter, MAX_STAT_LEVEL, MAX_LEVEL
        output += "|c|||n  |W S P E C I A L|n\n"
        for key in STAT_KEYS:
            letter = level_to_letter(caller.get_stat_level(key), MAX_STAT_LEVEL) if hasattr(caller, "get_stat_level") else "Q"
            adj = caller.get_stat_grade_adjective(letter, key) if hasattr(caller, "get_stat_grade_adjective") else letter
            output += "|c|||n    |w{}|n  |w[{}]|n {}\n".format(key.capitalize().ljust(12), letter, adj)
        output += thin + "\n"
        output += "|c|||n  |W SKILL IMPLANTS|n\n"
        for key in SKILL_KEYS:
            letter = level_to_letter(caller.get_skill_level(key), MAX_LEVEL) if hasattr(caller, "get_skill_level") else "Q"
            adj = caller.get_skill_grade_adjective(letter) if hasattr(caller, "get_skill_grade_adjective") else letter
            label = SKILL_DISPLAY_NAMES.get(key, key.replace("_", " ").title())
            output += "|c|||n    |w{}|n  |w[{}]|n {}\n".format(label.ljust(20), letter, adj)
        output += line + "\n"
        caller.msg(output)


class CmdXp(Command):
    """
    View XP and spend it to advance stats or skills (cost for next raise increases with level).

    Usage:
      xp                          - show XP and XP needed for next raise per stat/skill
      xp advance stat <name> [N]   - spend XP to raise a stat by N levels (default 1)
      xp advance skill <name> [N]  - spend XP to raise a skill by N levels (default 1)
    Bulk advances account for the rising cost curve.

    XP is granted every 6 hours (max 4 drops per 24h). Cap tuned for ~1 year of play.
    """
    key = "xp"
    aliases = ["advance", "progress"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.xp import XP_CAP, get_xp_cost_stat, get_xp_cost_skill, _stat_level, _skill_level, _stat_cap_level, _skill_cap_level
        from world.levels import level_to_letter, MAX_STAT_LEVEL, MAX_LEVEL
        from world.chargen import STAT_KEYS
        from world.skills import SKILL_KEYS, SKILL_DISPLAY_NAMES
        caller = self.caller
        xp = int(getattr(caller.db, "xp", 0) or 0)
        cap = int(getattr(caller.db, "xp_cap", XP_CAP) or XP_CAP)

        if not self.args or self.args.strip().lower() in ("show", ""):
            output = "|cXP|n: |w{}|n / {}\n\n".format(xp, cap)
            output += "|cXP needed for next raise:|n\n\n"
            output += "|wStats|n:\n"
            for sk in STAT_KEYS:
                cost, _ = get_xp_cost_stat(caller, sk)
                letter = level_to_letter(_stat_level(caller, sk), MAX_STAT_LEVEL)
                adj = caller.get_stat_grade_adjective(letter, sk)
                if cost is None:
                    output += "  {}: [{}] {} |x(at cap)|n\n".format(sk.capitalize(), letter, adj)
                else:
                    output += "  {}: [{}] {} — next raise: |w{} XP|n\n".format(sk.capitalize(), letter, adj, cost)
            output += "\n|wSkills|n:\n"
            for sk in SKILL_KEYS:
                cost, _ = get_xp_cost_skill(caller, sk)
                letter = level_to_letter(_skill_level(caller, sk), MAX_LEVEL)
                adj = caller.get_skill_grade_adjective(letter)
                label = SKILL_DISPLAY_NAMES.get(sk, sk.replace("_", " ").title())
                if cost is None:
                    output += "  {}: [{}] {} |x(at cap)|n\n".format(label, letter, adj)
                else:
                    output += "  {}: [{}] {} — next raise: |w{} XP|n\n".format(label, letter, adj, cost)
            output += "\nUse |wxp advance stat <name> [N]|n or |wxp advance skill <name> [N]|n to spend XP (N = number of raises)."
            caller.msg(output)
            return

        parts = self.args.strip().split()
        if len(parts) < 2 or parts[0].lower() != "advance":
            caller.msg("Usage: xp [show] | xp advance stat <name> [N] | xp advance skill <name> [N]")
            return
        sub = parts[1].lower()
        # Parse: advance stat <name> [N] or advance skill <name> [N]
        if sub not in ("stat", "skill"):
            caller.msg("Use |wxp advance stat <name> [N]|n or |wxp advance skill <name> [N]|n.")
            return
        if len(parts) < 3:
            caller.msg("Specify which stat or skill to advance.")
            return
        target_name = parts[2].strip().lower()
        try:
            bulk_n = int(parts[3]) if len(parts) > 3 else 1
            if bulk_n < 1:
                bulk_n = 1
        except (ValueError, IndexError):
            bulk_n = 1
        if not target_name:
            caller.msg("Specify which stat or skill to advance.")
            return

        from world.levels import xp_cost_for_next_level

        if sub == "stat":
            stat_key = None
            for s in STAT_KEYS:
                if s.startswith(target_name) or target_name == s:
                    stat_key = s
                    break
            if not stat_key:
                caller.msg("Unknown stat. Use one of: {}.".format(", ".join(STAT_KEYS)))
                return
            cur = _stat_level(caller, stat_key)
            cap = _stat_cap_level(caller, stat_key)
            if cur >= cap:
                caller.msg("That stat is already at its cap.")
                return
            total_spent = 0
            levels_gained = 0
            while levels_gained < bulk_n and cur + levels_gained < cap:
                cost = xp_cost_for_next_level(cur + levels_gained, MAX_STAT_LEVEL)
                if cost is None or xp - total_spent < cost:
                    break
                total_spent += cost
                levels_gained += 1
            if levels_gained == 0:
                cost_one = xp_cost_for_next_level(cur, MAX_STAT_LEVEL)
                caller.msg("You need {} XP for the next raise. You have {} XP.".format(cost_one, xp))
                return
            if not getattr(caller.db, "stats", None):
                caller.db.stats = {}
            caller.db.stats[stat_key] = cur + levels_gained
            caller.db.xp = xp - total_spent
            old_letter = level_to_letter(cur, MAX_STAT_LEVEL)
            new_letter = level_to_letter(cur + levels_gained, MAX_STAT_LEVEL)
            letter_changed = old_letter != new_letter
            if levels_gained == 1:
                msg = "You spend {} XP.".format(total_spent)
                if letter_changed:
                    adj = caller.get_stat_grade_adjective(new_letter, stat_key)
                    msg += " {} is now [{}] {}.".format(stat_key.capitalize(), new_letter, adj)
            else:
                msg = "You spend {} XP and raise {} {} time{}.".format(
                    total_spent, stat_key.capitalize(), levels_gained, "s" if levels_gained > 1 else "")
                if letter_changed:
                    adj = caller.get_stat_grade_adjective(new_letter, stat_key)
                    msg += " {} is now [{}] {}.".format(stat_key.capitalize(), new_letter, adj)
            caller.msg(msg)
            return

        if sub == "skill":
            skill_key = None
            for s in SKILL_KEYS:
                if s.startswith(target_name) or target_name == s:
                    skill_key = s
                    break
            if not skill_key:
                caller.msg("Unknown skill. Use one of: {}.".format(", ".join(SKILL_DISPLAY_NAMES.get(s, s.replace("_", " ").title()) for s in SKILL_KEYS)))
                return
            cur = _skill_level(caller, skill_key)
            cap = _skill_cap_level(caller, skill_key)
            if cur >= cap:
                caller.msg("That skill is already at its cap.")
                return
            total_spent = 0
            levels_gained = 0
            while levels_gained < bulk_n and cur + levels_gained < cap:
                cost = xp_cost_for_next_level(cur + levels_gained, MAX_LEVEL)
                if cost is None or xp - total_spent < cost:
                    break
                total_spent += cost
                levels_gained += 1
            if levels_gained == 0:
                cost_one = xp_cost_for_next_level(cur, MAX_LEVEL)
                caller.msg("You need {} XP for the next raise. You have {} XP.".format(cost_one, xp))
                return
            if not getattr(caller.db, "skills", None):
                caller.db.skills = {}
            caller.db.skills[skill_key] = cur + levels_gained
            caller.db.xp = xp - total_spent
            old_letter = level_to_letter(cur, MAX_LEVEL)
            new_letter = level_to_letter(cur + levels_gained, MAX_LEVEL)
            letter_changed = old_letter != new_letter
            label = SKILL_DISPLAY_NAMES.get(skill_key, skill_key.replace("_", " ").title())
            if levels_gained == 1:
                msg = "You spend {} XP.".format(total_spent)
                if letter_changed:
                    adj = caller.get_skill_grade_adjective(new_letter)
                    msg += " {} is now [{}] {}.".format(label, new_letter, adj)
            else:
                msg = "You spend {} XP and raise {} {} time{}.".format(
                    total_spent, label, levels_gained, "s" if levels_gained > 1 else "")
                if letter_changed:
                    adj = caller.get_skill_grade_adjective(new_letter)
                    msg += " {} is now [{}] {}.".format(label, new_letter, adj)
            caller.msg(msg)
            return

        caller.msg("Use |wxp advance stat <name> [N]|n or |wxp advance skill <name> [N]|n.")


from world.combat import start_combat_ticker, stop_combat_ticker, _get_combat_target

class CmdAttack(Command):
    """
    Start an automated combat sequence.
    """
    key = "attack"
    aliases = ["kill", "hit"]
    locks = "cmd:all()"
    help_category = "Combat"
    usage_typeclasses = ["typeclasses.characters.Character"]
    usage_hint = "|wattack <them>|n (when wielding a weapon)"

    def func(self):
        caller = self.caller
        target = caller.search(self.args)
        if not target:
            return
        try:
            from typeclasses.corpse import Corpse
            if isinstance(target, Corpse):
                caller.msg("You can't attack a corpse.")
                return
        except ImportError:
            pass
        try:
            from world.death import is_permanently_dead, is_flatlined, is_character_logged_off
            if is_character_logged_off(target):
                caller.msg("Kill them when they wake up. It's more fun that way.")
                return
            if is_permanently_dead(target):
                caller.msg(f"|r{target.name} is already dead.|n")
                return
            if is_flatlined(target):
                caller.msg(f"|r{target.name} is down and dying. Use |wexecute {target.name}|n to end them.|n")
                return
        except ImportError:
            if getattr(target.db, "current_hp", None) is not None and target.db.current_hp <= 0:
                caller.msg(f"|r{target.name} is already dead.|n")
                return
        current = _get_combat_target(caller)
        if current == target:
            caller.msg("|yYou're already fighting them.|n")
            return
        if current and current != target:
            stop_combat_ticker(caller, current)
            caller.msg(f"|yYou switch targets to {target.name}.|n")
        start_combat_ticker(caller, target)

class CmdStop(Command):
    """
    Stops the automated combat sequence.
    Usage: stop attacking <target>
    """
    key = "stop"
    aliases = ["cease", "retreat"]
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Stop attacking who? Usage: stop attacking <name>")
            return
        if not args.lower().startswith("attacking "):
            caller.msg("Usage: stop attacking <name>")
            return
        target_name = args[10:].strip()
        if not target_name:
            caller.msg("Stop attacking who? Usage: stop attacking <name>")
            return
        target = caller.search(target_name)
        if not target:
            return

        from world.combat import stop_combat_ticker
        stop_combat_ticker(caller, target)


class CmdExecute(Command):
    """
    End a dying (flatlined) character permanently. They become a corpse and cannot be revived.
    Usage: execute <target>
    """
    key = "execute"
    locks = "cmd:all()"
    help_category = "Combat"
    usage_typeclasses = ["typeclasses.characters.Character"]
    usage_hint = "|wexecute <name>|n (only on a dying, flatlined character)"

    def func(self):
        caller = self.caller
        target = caller.search(self.args.strip())
        if not target:
            return
        if not hasattr(target, "db"):
            caller.msg("You cannot execute that.")
            return
        if caller.location != target.location:
            caller.msg("You need to be in the same place as them.")
            return
        try:
            from world.death import is_flatlined, is_permanently_dead, make_permanent_death, is_character_logged_off
            if is_character_logged_off(target):
                caller.msg("Kill them when they wake up. It's more fun that way.")
                return
            if is_permanently_dead(target):
                caller.msg("They are already dead. There is nothing left to end.")
                return
            if not is_flatlined(target):
                caller.msg("They are not dying. You can only execute someone who is flatlined and beyond fighting.")
                return
        except ImportError:
            caller.msg("Execution is not available.")
            return
        make_permanent_death(target, attacker=caller, reason="executed")


class CmdStance(Command):
    """
    Change your combat stance.

    Usage:
      stance <aggressive|defensive|balanced>

    Aggressive: Higher attack ceiling, but easier to hit.
    Defensive: Much harder to hit, but your strikes are weak/cautious.
    Balanced: No modifiers.
    """
    key = "stance"
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = self.caller
        args = self.args.strip().lower()

        if args not in ["aggressive", "defensive", "balanced"]:
            caller.msg("Usage: stance <aggressive|defensive|balanced>")
            # Show current stance
            current = caller.db.combat_stance or "balanced"
            caller.msg(f"Current stance: |w{current.capitalize()}|n")
            return

        caller.db.combat_stance = args
        caller.msg(f"You shift into an |y{args.upper()}|n stance.")
class CmdSpawn(Command):
    """
    Spawns a randomized combat NPC. (Admin/Builder only.)
    Usage:
      spawn <name>
    """
    key = "spawn"
    locks = ADMIN_LOCK
    help_category = "Admin"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: spawn <name>")
            return
        
        name = self.args.strip()
        # Create the NPC object
        from evennia.utils.create import create_object
        
        new_npc = create_object(
            "typeclasses.npc.NPC",
            key=name,
            location=self.caller.location
        )
        
        self.caller.msg(f"|gA haggered individual named '{name}' emerges from the shadows.|n")


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


class CmdTypeclasses(Command):
    """
    List all typeclass paths usable with the create command. (Admin/Builder only.)
    """
    key = "typeclasses"
    aliases = ["listtypeclasses", "typelist"]
    locks = ADMIN_LOCK
    help_category = "Admin"

    def func(self):
        import pkgutil
        import importlib
        from evennia import DefaultObject, DefaultCharacter, DefaultRoom, DefaultExit
        try:
            from evennia.scripts.scripts import DefaultScript
        except Exception:
            DefaultScript = None

        caller = self.caller
        bases = (DefaultObject, DefaultCharacter, DefaultRoom, DefaultExit)
        if DefaultScript is not None:
            bases = bases + (DefaultScript,)

        try:
            import typeclasses as pkg
            prefix = pkg.__name__ + "."
            paths = []
            # Skip account/channel typeclasses (not for create-in-room)
            skip_modules = (prefix + "accounts", prefix + "channels")
            for _importer, modname, _ispkg in pkgutil.walk_packages(pkg.__path__, prefix):
                if any(modname.startswith(s) for s in skip_modules):
                    continue
                try:
                    mod = importlib.import_module(modname)
                except Exception:
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


def _get_vehicle_from_caller(caller):
    """If caller is inside a vehicle interior, return the vehicle; else None."""
    loc = caller.location
    if not loc:
        return None
    return getattr(loc.db, "vehicle", None)


class CmdEnterVehicle(Command):
    """
    Enter (or ride) a vehicle. You are moved to its interior. Start the engine to drive.
    """
    key = "enter"
    aliases = ["ride", "board"]
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.vehicles.Vehicle"]
    usage_hint = "|wenter|n / |wride|n (to get in)"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Enter what? Usage: enter <vehicle>")
            return
        if _get_vehicle_from_caller(caller):
            caller.msg("You are already inside a vehicle. Exit first.")
            return
        vehicle = caller.search(self.args.strip(), location=caller.location)
        if not vehicle:
            return
        if not (hasattr(vehicle, "interior") and vehicle.interior):
            caller.msg("That is not a vehicle you can enter.")
            return
        caller.move_to(vehicle.interior)
        caller.db.in_vehicle = vehicle
        caller.msg(f"You enter {vehicle.key}. You're inside. Use |wstart|n to start the engine, |wdrive <direction>|n to move, |wexit|n to get out.")
        caller.location.msg_contents(f"{caller.key} enters.", exclude=caller)


class CmdExitVehicle(Command):
    """
    Get out of the vehicle. You appear in the same room as the vehicle.
    """
    key = "exit"
    aliases = ["get out", "leave vehicle"]
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.vehicles.VehicleInterior"]
    usage_hint = "|wexit|n (to get out)"

    def func(self):
        caller = self.caller
        vehicle = _get_vehicle_from_caller(caller)
        if not vehicle:
            caller.msg("You're not in a vehicle.")
            return
        dest = vehicle.location
        if not dest:
            caller.msg("The vehicle is nowhere. You can't exit.")
            return
        caller.db.in_vehicle = None
        caller.move_to(dest)
        caller.msg(f"You get out of {vehicle.key}.")
        dest.msg_contents(f"{caller.key} gets out of {vehicle.key}.", exclude=caller)


class CmdStartEngine(Command):
    """Start the vehicle's engine. Required to drive."""
    key = "start"
    aliases = ["start engine", "ignition"]
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.vehicles.VehicleInterior"]
    usage_hint = "|wstart|n (engine)"

    def func(self):
        caller = self.caller
        vehicle = _get_vehicle_from_caller(caller)
        if not vehicle:
            caller.msg("You're not inside a vehicle.")
            return
        if vehicle.engine_running:
            caller.msg("The engine is already running.")
            return
        ok, err = vehicle.start_engine()
        if not ok:
            caller.msg(f"|r{err}|n")
            return
        caller.msg("You start the engine. It's running. Use |wdrive <direction>|n to move.")
        caller.location.msg_contents("The engine starts.", exclude=caller)


class CmdStopEngine(Command):
    """Turn off the vehicle's engine."""
    key = "stop engine"
    aliases = ["stopengine", "kill engine", "turn off"]
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.vehicles.VehicleInterior"]
    usage_hint = "|wstop engine|n"

    def func(self):
        caller = self.caller
        vehicle = _get_vehicle_from_caller(caller)
        if not vehicle:
            caller.msg("You're not inside a vehicle.")
            return
        if not vehicle.engine_running:
            caller.msg("The engine is already off.")
            return
        vehicle.stop_engine()
        caller.msg("You turn off the engine.")
        caller.location.msg_contents("The engine stops.", exclude=caller)


class CmdShutoffEngine(Command):
    """
    Turn off a vehicle's engine from outside (e.g. you're in the room, not inside the vehicle).
    Usage: shutoff <vehicle>   or   turn off <vehicle>
    """
    key = "shutoff"
    aliases = ["turn off engine", "kill engine outside"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        location = caller.location
        if not location:
            caller.msg("You are not in a room.")
            return
        if _get_vehicle_from_caller(caller):
            caller.msg("You're inside a vehicle. Use |wstop engine|n to turn it off from here.")
            return
        arg = self.args.strip()
        if not arg:
            caller.msg("Usage: |wshutoff <vehicle>|n (e.g. shutoff sedan)")
            return
        vehicle = caller.search(arg, location=location)
        if not vehicle:
            return
        try:
            from typeclasses.vehicles import Vehicle
            if not isinstance(vehicle, Vehicle):
                caller.msg("That isn't a vehicle.")
                return
        except ImportError:
            caller.msg("That isn't a vehicle.")
            return
        if not vehicle.engine_running:
            caller.msg("The engine is already off.")
            return
        vehicle.stop_engine()
        caller.msg(f"You reach in and turn off {vehicle.key}'s engine.")
        location.msg_contents(f"{caller.key} turns off {vehicle.key}'s engine.", exclude=caller)


class CmdDrive(Command):
    """
    Drive the vehicle in a direction. Engine must be running. Uses driving skill.
    Usage: drive <direction>   e.g. drive east, drive n
    """
    key = "drive"
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.vehicles.VehicleInterior"]
    usage_hint = "|wdrive <direction>|n (e.g. drive east)"

    def func(self):
        caller = self.caller
        vehicle = _get_vehicle_from_caller(caller)
        if not vehicle:
            caller.msg("You're not inside a vehicle.")
            return
        if not vehicle.engine_running:
            caller.msg("Start the engine first.")
            return
        direction = self.args.strip() if self.args else ""
        if not direction:
            caller.msg("Drive which way? Usage: drive <direction>  (e.g. drive east)")
            return
        exit_obj = vehicle.get_exit(direction)
        if not exit_obj or not exit_obj.destination:
            caller.msg(f"There is no exit {direction} from here.")
            return
        dest = exit_obj.destination
        # Driving skill check; vehicle parts add failure modifier
        from world.skills import SKILL_STATS, DEFENSE_SKILL
        skill = getattr(vehicle.db, "driving_skill", "driving")
        stats = SKILL_STATS.get(skill, ["perception", "agility"])
        mod = getattr(vehicle, "drive_failure_modifier", lambda: 0)()
        level, roll_value = caller.roll_check(stats, skill, modifier=-mod)
        if level == "Failure":
            caller.msg("You fumble the controls. The vehicle doesn't move.")
            return
        # Optional stall check (damaged engine/fuel/electrical)
        if getattr(vehicle, "roll_stall_chance", lambda: False)():
            vehicle.stop_engine()
            caller.msg("|rThe engine sputters and dies. You coast to a stop.|n")
            caller.location.msg_contents("The engine sputters and stalls.", exclude=caller)
            return
        # Staggered drive: message first, then move after delay; passengers see new outside on arrival
        try:
            from evennia.utils import delay
            from world.staggered_movement import DRIVE_DELAY, _staggered_drive_callback
        except ImportError:
            delay = None
        if delay and _staggered_drive_callback:
            caller.msg(f"You begin driving {direction}.")
            caller.location.msg_contents(f"{caller.key} begins driving {direction}.", exclude=caller)
            delay(DRIVE_DELAY, _staggered_drive_callback, vehicle.id, dest.id, direction)
        else:
            old_room = vehicle.location
            vehicle.move_to(dest, quiet=True)
            caller.msg(f"You drive {direction}. You arrive at {dest.key}.")
            caller.location.msg_contents(f"The vehicle drives {direction}. You arrive at {dest.key}.", exclude=caller)
            if old_room:
                old_room.msg_contents(f"{vehicle.key} drives {direction}.")
            dest.msg_contents(f"{vehicle.key} arrives from {direction}.")


class CmdSpawnVehicle(Command):
    """
    Create a test vehicle in the current room. (Admin/Builder only.)
    Usage: spawnvehicle [name]
    """
    key = "spawnvehicle"
    aliases = ["spawn vehicle", "testvehicle"]
    locks = ADMIN_LOCK
    help_category = "Admin"

    def func(self):
        caller = self.caller
        name = self.args.strip() or "test sedan"
        loc = caller.location
        if not loc:
            caller.msg("You need to be in a room to spawn a vehicle.")
            return
        from evennia.utils.create import create_object
        try:
            vehicle = create_object("typeclasses.vehicles.Vehicle", key=name, location=loc)
            caller.msg(f"|gCreated vehicle|n |w{vehicle.key}|n here. Use |wenter {vehicle.key}|n to get in, then |wstart|n and |wdrive <direction>|n.")
        except Exception as e:
            caller.msg(f"|rCould not create vehicle: {e}|n")


class CmdVehicleStatus(Command):
    """
    Perform a mechanic-style inspection of a vehicle over 15–20 seconds. You check each part in turn
    with RP messages, then see the full condition and part types. Requires mechanical_engineering skill.
    Usage: vehicle status [vehicle]   or   inspect vehicle [vehicle]
    """
    key = "vehicle status"
    aliases = ["vehiclestatus", "inspect vehicle", "vstatus"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        loc = caller.location
        arg = self.args.strip()
        vehicle = None
        try:
            from evennia.utils import delay
            from typeclasses.vehicles import Vehicle
            from world.vehicle_parts import (
                INSPECT_DURATION_SECONDS,
                INSPECT_MECHANICS_MIN_LEVEL,
                INSPECT_FLAVOR_MESSAGES,
                _vehicle_inspect_flavor_callback,
                _vehicle_inspect_final_callback,
                default_part_types,
            )
        except ImportError as e:
            caller.msg("Vehicle system is not available.")
            return
        vehicle = _get_vehicle_from_caller(caller)
        if not vehicle and loc:
            if arg:
                vehicle = caller.search(arg, location=loc)
            if not vehicle and loc.contents:
                for obj in loc.contents:
                    if isinstance(obj, Vehicle):
                        vehicle = obj
                        break
        if not vehicle or not isinstance(vehicle, Vehicle):
            caller.msg("Inspect which vehicle? Usage: |wvehicle status [vehicle]|n (or use from inside one).")
            return
        # Gate behind mechanics skill
        level = getattr(caller, "get_skill_level", lambda s: 0)("mechanical_engineering")
        if level < INSPECT_MECHANICS_MIN_LEVEL:
            caller.msg("You don't know enough about mechanics to inspect the vehicle properly. Train |wmechanical_engineering|n.")
            return
        # Ensure part types exist on vehicle (older vehicles may not have them)
        if not getattr(vehicle.db, "vehicle_part_types", None):
            vehicle.db.vehicle_part_types = default_part_types()
        # Start timed inspection
        caller.msg("You walk around the vehicle and begin a proper inspection.")
        for i, (part_id, message) in enumerate(INSPECT_FLAVOR_MESSAGES):
            delay(2 * (i + 1), _vehicle_inspect_flavor_callback, caller.id, message)
        delay(INSPECT_DURATION_SECONDS, _vehicle_inspect_final_callback, caller.id, vehicle.id)


class CmdRepairPart(Command):
    """
    Repair a vehicle part using mechanical engineering. You must be next to the vehicle (same room).
    Usage: repair <vehicle> <part>   e.g. repair sedan engine
    """
    key = "repair"
    aliases = ["repair part", "fix vehicle"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        loc = caller.location
        args = self.args.strip().split()
        if len(args) < 2:
            caller.msg("Usage: |wrepair <vehicle> <part>|n (e.g. repair sedan engine). Parts: engine, transmission, brakes, suspension, tires, battery, fuel_system, cooling_system, electrical")
            return
        try:
            from typeclasses.vehicles import Vehicle
            from world.vehicle_parts import VEHICLE_PART_IDS, PART_DISPLAY_NAMES
            from world.skills import SKILL_STATS
        except ImportError as e:
            caller.msg("Vehicle or skill system not available.")
            return
        vehicle_name, part_id = args[0], args[1].lower().replace(" ", "_")
        vehicle = caller.search(vehicle_name, location=loc)
        if not vehicle or not isinstance(vehicle, Vehicle):
            caller.msg("No such vehicle here.")
            return
        if part_id not in VEHICLE_PART_IDS:
            caller.msg(f"Unknown part. Valid: {', '.join(VEHICLE_PART_IDS)}")
            return
        current = vehicle.get_part_condition(part_id)
        if current >= 100:
            caller.msg(f"The {PART_DISPLAY_NAMES.get(part_id, part_id)} is already in good shape.")
            return
        stats = SKILL_STATS.get("mechanical_engineering", ["intelligence", "strength"])
        level, _ = caller.roll_check(stats, "mechanical_engineering")
        repair_amount = 0
        if level == "Critical Success":
            repair_amount = 25
        elif level == "Full Success":
            repair_amount = 15
        elif level == "Marginal Success":
            repair_amount = 5
        if repair_amount <= 0:
            caller.msg("You work on it but don't manage to improve the condition.")
            return
        new_cond = vehicle.repair_part(part_id, repair_amount)
        part_name = PART_DISPLAY_NAMES.get(part_id, part_id)
        caller.msg(f"You repair the {part_name}. Condition now |w{new_cond}%|n (was {current}%).")
        loc.msg_contents(f"{caller.key} works on {vehicle.key}'s {part_name}.", exclude=caller)


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
            from world.vehicle_parts import VEHICLE_PART_IDS, PART_DISPLAY_NAMES
        except ImportError:
            caller.msg("Vehicle parts not available.")
            return
        vehicle = caller.search(args[0], location=loc)
        if not vehicle or not isinstance(vehicle, Vehicle):
            caller.msg("No such vehicle here.")
            return
        part_id = args[1].lower().replace(" ", "_")
        if part_id not in VEHICLE_PART_IDS:
            caller.msg(f"Unknown part. Valid: {', '.join(VEHICLE_PART_IDS)}")
            return
        amount = int(args[2]) if len(args) > 2 else 20
        amount = max(1, min(100, amount))
        old_c = vehicle.get_part_condition(part_id)
        new_c = vehicle.damage_part(part_id, amount)
        part_name = PART_DISPLAY_NAMES.get(part_id, part_id)
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
            ("typeclasses.medical_tools.Defibrillator", "defibrillator"),
        ]:
            try:
                obj = create_object(typeclass, key=key, location=caller)
                created.append(obj.key)
            except Exception:
                pass
        if created:
            caller.msg(f"|gCreated medical tools in your inventory:|n {', '.join(created)}. |wWield|n a tool, then |wuse scanner on <target>|n to scan, or |wapply to <target>|n to treat. (Surgical kit is room-only: use |wspawnor|n in an OR room.)")
        else:
            caller.msg("|rCould not create medical tools.|n")


class CmdSpawnOR(Command):
    """
    Create an operating room surgical station in the current room. Builder/Admin only.
    The station cannot be carried; it provides full surgical capability to anyone in the room.
    Usage: spawnor
    """
    key = "spawnor"
    aliases = ["spawn or", "spawn operating room"]
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        caller = self.caller
        from evennia.utils.create import create_object
        try:
            obj = create_object(
                "typeclasses.medical_tools.ORStation",
                key="operating theatre",
                location=caller.location,
            )
            caller.msg("|gOperating theatre (surgical station) created in this room. Anyone here can use full surgical options: |wwield|n a tool, then |wapply to <target>|n or |wstabilize <target>|n.|n")
        except Exception as e:
            caller.msg(f"|rCould not create OR station: {e}|n")


class CmdDefib(Command):
    """
    Resuscitate a dead or arrested character with a defibrillator.
    Takes about 12 seconds; you are locked in the action. Requires medicine skill.
    Usage: defib <target>
    """
    key = "defib"
    aliases = ["defibrillate", "resuscitate"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Defib who? Usage: defib <target>")
            return
        target = caller.search(args, location=caller.location)
        if not target:
            return
        defib = None
        for obj in caller.contents:
            from typeclasses.medical_tools import Defibrillator
            if isinstance(obj, Defibrillator):
                defib = obj
                break
        if not defib:
            caller.msg("You need a defibrillator in your inventory.")
            return
        from world.medical_defib import start_defib_sequence
        started, err = start_defib_sequence(caller, target, defib)
        if not started:
            caller.msg(err if err else "You cannot do that right now.")


class CmdExamine(Command):
    """
    Look at an object and see what commands you can use with it.

    Usage:
      examine <object>
      ex <object>
    """
    key = "examine"
    aliases = ["ex", "inspect"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Examine what? Usage: examine <object>")
            return
        obj = caller.search(self.args.strip(), location=caller.location)
        if not obj:
            # Try inventory
            obj = caller.search(self.args.strip(), location=caller)
        if not obj:
            return
        # Description (same as look)
        try:
            appearance = obj.return_appearance(caller)
            if appearance:
                caller.msg(appearance)
        except Exception:
            desc = obj.get_display_desc(caller) if hasattr(obj, "get_display_desc") else getattr(obj.db, "desc", None)
            if desc:
                caller.msg(desc)
        # Player-usable command hints
        try:
            from world.examine import get_usage_hints
            hints = get_usage_hints(obj)
            if hints:
                caller.msg("\n|wYou can use:|n " + ", ".join(hints))
            else:
                caller.msg("\n|wYou can use:|n Nothing special (get, drop, give if portable).")
        except Exception as e:
            caller.msg(f"\n|y(Could not determine usage: {e})|n")


class CmdDiagnose(Command):
    """
    Assess the physical condition of a target (physical exam). With medicine skill,
    you notice more: bleeding, possible fractures, then exact areas; higher skill
    reveals more. For full detail (vitals, exact organs) use a bioscanner.

    Usage:
      diagnose <target>
      diag <target>
    """
    key = "diagnose"
    aliases = ["diag", "check"]
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.characters.Character"]
    usage_hint = "|wdiagnose|n (to check condition)"

    def func(self):
        caller = self.caller
        if not self.args:
            # If no target, diagnose yourself
            target = caller
        else:
            target = caller.search(self.args)
            
        if not target:
            return

        if not hasattr(target, "get_health_description"):
            caller.msg("You cannot assess that.")
            return
        status = target.get_health_description(include_trauma=False)
        med_level = getattr(caller, "get_skill_level", lambda s: 0)("medicine")
        from world.medical import get_diagnose_trauma_for_skill
        extra = get_diagnose_trauma_for_skill(target, med_level)
        if extra:
            status = status + "\n\n" + extra
        prefix = "You assess your own condition:" if target == caller else f"You eye {target.name} critically:"
        caller.msg(f"{prefix}\n{status}")


class CmdUse(Command):
    """
    Use a medical tool on a target. The tool must be held in your hands (wield it first).

    Usage:
      use <tool> on <target>
      use <tool>

    Examples:
      wield scanner
      use scanner on Bob   - run bioscanner readout on Bob (detect damage type)
      wield bandage
      apply bandage to Bob  - then use apply to treat (after scanning)

    Scanner gives a readout only; treat with the correct tool using |wapply <item> to <target>|n.
    """
    key = "use"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: use <tool> [on <target>]")
            return
        # Parse "tool on target" or "tool"
        parts = args.split(None, 2)
        tool_name = parts[0]
        target = caller
        if len(parts) >= 3 and parts[1].lower() == "on":
            target = caller.search(parts[2])
            if not target:
                return
            if not hasattr(target, "db"):
                caller.msg("You cannot use that on them.")
                return

        tool = caller.search(tool_name, location=caller)
        if not tool:
            return
        # Item must be held in either hand to use
        if not _obj_in_hands(caller, tool):
            caller.msg("You need to hold that in your hands to use it. Wield it first (|wwield %s|n)." % tool_name)
            return
        try:
            from typeclasses.medical_tools import MedicalTool, Bioscanner, get_medical_tools_from_inventory
        except ImportError:
            caller.msg("That is not a medical tool.")
            return
        from typeclasses.medical_tools import Defibrillator
        if isinstance(tool, Defibrillator):
            if not target or target == caller:
                caller.msg("Use the defibrillator on who? Usage: use defibrillator on <target>")
                return
            if getattr(target, "hp", 1) > 0:
                caller.msg("They are not in arrest. The defibrillator is for the dead.")
                return
            from world.medical_defib import start_defib_sequence
            started, err = start_defib_sequence(caller, target, tool)
            if not started:
                caller.msg(err or "You cannot do that right now.")
            return

        if not isinstance(tool, MedicalTool):
            caller.msg("You can't use that for medical procedures.")
            return
        if getattr(tool.db, "uses_remaining", 1) is not None and (tool.db.uses_remaining or 0) <= 0:
            caller.msg(f"{tool.get_display_name(caller)} is used up.")
            return

        if isinstance(tool, Bioscanner):
            from world.medical import BIOSCANNER_MIN_MEDICINE
            med_level = getattr(caller, "get_skill_level", lambda s: 0)("medicine")
            if med_level < BIOSCANNER_MIN_MEDICINE:
                caller.msg("You need at least %d medicine skill to operate the bioscanner. You lack the training to interpret its readout." % BIOSCANNER_MIN_MEDICINE)
                return
            success, out = tool.use_for_scan(caller, target)
            if not success:
                caller.msg(out if isinstance(out, str) else "Scan failed.")
                return
            if isinstance(out, dict) and out.get("formatted"):
                caller.msg(out["formatted"])
            elif isinstance(out, dict):
                caller.msg(out.get("detail", "No readout."))
            else:
                caller.msg(out)
            if target != caller:
                target.msg(f"{caller.name} runs a scanner over you.")
            return

        # Other medical tools: treatment is done via "apply <item> to <target>" with tool wielded
        caller.msg("To treat, keep the tool in your hands and use: |wapply to %s|n (e.g. apply bandage to %s, apply splint to %s arm)." % (
            target.key if hasattr(target, "key") else target.name,
            target.key if hasattr(target, "key") else target.name,
            target.key if hasattr(target, "key") else target.name,
        ))


class CmdStabilize(Command):
    """
    Stop or reduce bleeding on a target using bandages or a medkit (or suture kit,
    hemostatic agent, surgical kit) held in your hands. Purely for haemorrhage control.

    Usage:
      stabilize <target>

    You must be wielding a bleeding-capable tool (e.g. wield bandage, then stabilize Bob).
    """
    key = "stabilize"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.medical_treatment import attempt_stop_bleeding, TOOL_CAN_STOP_BLEEDING
        from typeclasses.medical_tools import MedicalTool

        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Stabilize whom? Usage: stabilize <target>")
            return

        # Tool must be in either hand (prefer right)
        left = getattr(caller.db, "left_hand_obj", None)
        right = getattr(caller.db, "right_hand_obj", None)
        tool = None
        if right and right.location == caller and isinstance(right, MedicalTool) and getattr(right.db, "medical_tool_type", None) in TOOL_CAN_STOP_BLEEDING:
            tool = right
        elif left and left.location == caller and isinstance(left, MedicalTool) and getattr(left.db, "medical_tool_type", None) in TOOL_CAN_STOP_BLEEDING:
            tool = left
        if not tool:
            caller.msg("You need to hold bandages, a medkit, or another bleeding-control tool in your hands. Wield it first.")
            return
        tool_type = getattr(tool.db, "medical_tool_type", None)
        if tool_type not in TOOL_CAN_STOP_BLEEDING:
            caller.msg("That tool isn't meant for bleeding control. Use bandages, a medkit, suture kit, hemostatic agent, or surgical kit.")
            return

        target = caller.search(args)
        if not target:
            return
        if not hasattr(target, "db"):
            caller.msg("You cannot stabilize that.")
            return
        try:
            from world.death import is_flatlined
            if is_flatlined(target):
                caller.msg("They're flatlined. You need to restart their heart with a defibrillator before you can treat their injuries.")
                return
        except ImportError:
            pass

        bleeding_level = getattr(target.db, "bleeding_level", 0) or 0
        if bleeding_level <= 0:
            caller.msg("They are not bleeding. Nothing to stabilize.")
            return

        # Only block if tool has limited uses and they're exhausted (None = unlimited)
        uses = getattr(tool.db, "uses_remaining", None)
        if uses is not None and (int(uses) <= 0):
            caller.msg("Your supplies are spent. You need a fresh pack or another tool before you can stabilize anyone.")
            return

        success, msg = attempt_stop_bleeding(caller, target, tool_type)
        tool.consume_use()  # consume a use whether the roll succeeds or fails
        if success:
            caller.msg("|g" + msg + "|n")
            if target != caller:
                target.msg("|g%s works to control the bleeding: %s|n" % (caller.name, msg[:60] + ("..." if len(msg) > 60 else "")))
        else:
            caller.msg("|r" + msg + "|n")
            if target != caller:
                target.msg("|r%s tries to stem the bleed: %s|n" % (caller.name, msg[:60] + ("..." if len(msg) > 60 else "")))


class CmdApply(Command):
    """
    Apply a medical tool you're holding to a target (after scanning to see what's needed).

    Usage:
      apply to <target> [body part]
      apply <item> to <target> [body part]

    Examples:
      apply to Bob           - use wielded tool on Bob (one clear treatment)
      apply bandage to Bob   - stop bleeding on Bob (must be holding bandage)
      apply splint to Bob arm
      apply medkit to Bob throat

    The item must be wielded. For splints/organ stabilization, specify body part if multiple options.
    """
    key = "apply"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.medical_treatment import get_treatment_options, BONE_ALIASES, ORGAN_ALIASES
        from typeclasses.medical_tools import MedicalTool

        caller = self.caller
        args = (self.args or "").strip()
        if not args or " to " not in args:
            caller.msg("Usage: apply [item] to <target> [body part]  (e.g. apply bandage to Bob, apply splint to Bob arm)")
            return

        left, right = args.split(" to ", 1)
        item_part = left.strip()
        rest = right.strip().split()
        if not rest:
            caller.msg("Apply to whom? Usage: apply [item] to <target> [body part]")
            return
        target_name = rest[0]
        bodypart = " ".join(rest[1:]).strip().lower() or None

        left = getattr(caller.db, "left_hand_obj", None)
        right = getattr(caller.db, "right_hand_obj", None)
        if item_part:
            tool = caller.search(item_part, location=caller)
            if not tool:
                return
            if not _obj_in_hands(caller, tool):
                caller.msg("You're not holding that. Hold the correct tool and try again.")
                return
        else:
            tool = None
            if right and right.location == caller and isinstance(right, MedicalTool):
                tool = right
            elif left and left.location == caller and isinstance(left, MedicalTool):
                tool = left
            if not tool:
                caller.msg("You need to hold a medical tool in your hands to apply it. Wield it first.")
                return
        if getattr(tool.db, "uses_remaining", 1) is not None and (tool.db.uses_remaining or 0) <= 0:
            caller.msg("Your supplies are spent. You need a fresh pack or another tool before you can treat anyone.")
            return

        target = caller.search(target_name)
        if not target:
            return
        if not hasattr(target, "db"):
            caller.msg("You cannot treat that.")
            return
        try:
            from world.death import is_flatlined
            if is_flatlined(target):
                caller.msg("They're flatlined. You need to restart their heart with a defibrillator before you can treat their injuries.")
                return
        except ImportError:
            pass

        tool_type = tool.medical_tool_type
        tools_by_type = {tool_type: [tool]}
        options = get_treatment_options(caller, target, tools_by_type)
        if not options:
            caller.msg("There is nothing to treat on them with what you're holding, or they don't need that treatment.")
            return

        # Resolve which option to use (by body part or single option)
        choice = None
        if bodypart:
            bodypart_key = BONE_ALIASES.get(bodypart) or ORGAN_ALIASES.get(bodypart) or bodypart.replace(" ", "_")
            for action_id, _display, _t, target_info in options:
                if action_id == "splint" and target_info == bodypart_key:
                    choice = (action_id, target_info)
                    break
                if action_id == "organ" and target_info == bodypart_key:
                    choice = (action_id, target_info)
                    break
                if action_id == "bleeding" and not bodypart_key:
                    choice = (action_id, target_info)
                    break
            if not choice and options:
                for opt in options:
                    if opt[3] == bodypart_key or (opt[3] and bodypart in str(opt[3])):
                        choice = (opt[0], opt[3])
                        break
            if not choice:
                caller.msg("No matching injury or treatment for that body part. Use the scanner to see what's needed.")
                return
        elif len(options) == 1:
            choice = (options[0][0], options[0][3])
        else:
            parts = []
            for _aid, _disp, _t, info in options:
                if info:
                    parts.append(info.replace("_", " "))
                else:
                    parts.append("bleeding")
            caller.msg("Specify what to treat: " + ", ".join(parts) + "  (e.g. apply splint to %s arm)" % target_name)
            return

        action_id, target_info = choice
        success, msg = tool.use_for_treatment(caller, target, action_id, target_info)
        tool.consume_use()  # consume a use whether the roll succeeds or fails
        if success:
            caller.msg("|g" + msg + "|n")
            if target != caller:
                target.msg("|g%s works on you: %s|n" % (caller.name, msg[:70] + ("..." if len(msg) > 70 else "")))
        else:
            caller.msg("|r" + msg + "|n")
            if target != caller:
                target.msg("|r%s tries to help: %s|n" % (caller.name, msg[:70] + ("..." if len(msg) > 70 else "")))


def _is_edible(obj):
    """True if object is food (tag 'food' or db.edible)."""
    if getattr(obj, "tags", None) and obj.tags.has("food"):
        return True
    return bool(getattr(obj.db, "edible", False))


def _is_drinkable(obj):
    """True if object is drink (tag 'drink' or db.drinkable)."""
    if getattr(obj, "tags", None) and obj.tags.has("drink"):
        return True
    return bool(getattr(obj.db, "drinkable", False))


class CmdEat(Command):
    """
    Eat something you're holding. You must wield (hold) the food first.

    Usage:
      eat [item]
    """
    key = "eat"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        left = getattr(caller.db, "left_hand_obj", None)
        right = getattr(caller.db, "right_hand_obj", None)
        if not args:
            obj = None
            if right and right.location == caller and _is_edible(right):
                obj = right
            elif left and left.location == caller and _is_edible(left):
                obj = left
            if not obj:
                caller.msg("You aren't holding anything to eat. Wield food first (e.g. wield ration, then eat).")
                return
        else:
            obj = caller.search(args, location=caller)
            if not obj:
                return
            if not _obj_in_hands(caller, obj):
                caller.msg("You need to hold that in your hands to eat it. Wield it first.")
                return
        if not _is_edible(obj):
            caller.msg("That isn't something you can eat.")
            return
        name = obj.get_display_name(caller) if hasattr(obj, "get_display_name") else obj.name
        caller.msg("You eat |w%s|n." % name)
        caller.location.msg_contents("%s eats %s." % (caller.name, name), exclude=caller)
        # Consume: delete single-use or decrement uses
        if getattr(obj.db, "uses_remaining", None) is not None:
            u = (obj.db.uses_remaining or 0) - 1
            obj.db.uses_remaining = u
            if u <= 0:
                _clear_hand_for_obj(caller, obj)
                obj.delete()
        else:
            _clear_hand_for_obj(caller, obj)
            obj.delete()


class CmdDrink(Command):
    """
    Drink something you're holding. You must wield (hold) the drink first.

    Usage:
      drink [item]
    """
    key = "drink"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        left = getattr(caller.db, "left_hand_obj", None)
        right = getattr(caller.db, "right_hand_obj", None)
        if not args:
            obj = None
            if right and right.location == caller and _is_drinkable(right):
                obj = right
            elif left and left.location == caller and _is_drinkable(left):
                obj = left
            if not obj:
                caller.msg("You aren't holding anything to drink. Wield a drink first (e.g. wield canteen, then drink).")
                return
        else:
            obj = caller.search(args, location=caller)
            if not obj:
                return
            if not _obj_in_hands(caller, obj):
                caller.msg("You need to hold that in your hands to drink it. Wield it first.")
                return
        if not _is_drinkable(obj):
            caller.msg("That isn't something you can drink.")
            return
        name = obj.get_display_name(caller) if hasattr(obj, "get_display_name") else obj.name
        caller.msg("You drink |w%s|n." % name)
        caller.location.msg_contents("%s drinks %s." % (caller.name, name), exclude=caller)
        if getattr(obj.db, "uses_remaining", None) is not None:
            u = (obj.db.uses_remaining or 0) - 1
            obj.db.uses_remaining = u
            if u <= 0:
                _clear_hand_for_obj(caller, obj)
                obj.delete()
        else:
            _clear_hand_for_obj(caller, obj)
            obj.delete()


def _hands_required(weapon_key):
    """Return 1 or 2 hands needed for this weapon key."""
    from world.combat import WEAPON_HANDS
    return WEAPON_HANDS.get(weapon_key, 1)


def _obj_in_hands(caller, obj):
    """True if obj is held in either hand (and still on caller)."""
    if not obj or getattr(obj, "location", None) != caller:
        return False
    left = getattr(caller.db, "left_hand_obj", None)
    right = getattr(caller.db, "right_hand_obj", None)
    return left is obj or right is obj


def _update_primary_wielded(caller):
    """Set wielded_obj and wielded from hands (right takes precedence for combat)."""
    right = getattr(caller.db, "right_hand_obj", None)
    left = getattr(caller.db, "left_hand_obj", None)
    primary = right if right and right.location == caller else (left if left and left.location == caller else None)
    caller.db.wielded_obj = primary
    if not primary:
        caller.db.wielded = None
        return
    try:
        from typeclasses.weapons import get_weapon_key
        caller.db.wielded = get_weapon_key(primary) or getattr(primary.db, "weapon_key", None)
    except Exception:
        caller.db.wielded = getattr(primary.db, "weapon_key", None)


def _clear_hand_for_obj(caller, obj):
    """Clear the hand that holds obj and update primary wielded."""
    if getattr(caller.db, "left_hand_obj", None) is obj:
        caller.db.left_hand_obj = None
    if getattr(caller.db, "right_hand_obj", None) is obj:
        caller.db.right_hand_obj = None
    _update_primary_wielded(caller)


class CmdWield(Command):
    """
    Wield a weapon from your inventory. One-handed uses one hand, two-handed uses both.

    Usage:
      wield <weapon>
    """
    key = "wield"
    locks = "cmd:all()"
    help_category = "Combat"
    usage_typeclasses = ["typeclasses.weapons.CombatWeapon"]
    usage_hint = "|wwield <weapon>|n (e.g. wield katana)"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("What do you want to wield? Usage: wield <weapon>")
            return

        target = caller.search(self.args.strip(), location=caller)
        if not target:
            return

        # Allow weapons or holdable tools (medical tools, defibrillator, etc.)
        try:
            from typeclasses.weapons import get_weapon_key
            weapon_key = get_weapon_key(target)
        except Exception:
            weapon_key = getattr(target.db, "weapon_key", None)
        if not weapon_key:
            # Not a weapon: allow if holdable (medical tool, defib, food, drink)
            try:
                from typeclasses.medical_tools import MedicalTool, Defibrillator
                if isinstance(target, (MedicalTool, Defibrillator)):
                    weapon_key = None  # holdable, one hand
                elif getattr(target, "tags", None) and (target.tags.has("food") or target.tags.has("drink")):
                    weapon_key = None
                elif getattr(target.db, "edible", False) or getattr(target.db, "drinkable", False):
                    weapon_key = None
                else:
                    caller.msg(f"{target.name} isn't something you can wield or fight with.")
                    return
            except ImportError:
                if getattr(target, "tags", None) and (target.tags.has("food") or target.tags.has("drink")):
                    weapon_key = None
                elif getattr(target.db, "edible", False) or getattr(target.db, "drinkable", False):
                    weapon_key = None
                else:
                    caller.msg(f"{target.name} isn't something you can fight with effectively.")
                    return
        if weapon_key and not getattr(target.db, "weapon_key", None):
            target.db.weapon_key = weapon_key  # persist
        hands_needed = _hands_required(weapon_key) if weapon_key else 1
        left = getattr(caller.db, "left_hand_obj", None)
        right = getattr(caller.db, "right_hand_obj", None)
        if hands_needed == 2:
            if left or right:
                caller.msg("You need both hands free to wield that. Unwield or drop what you're holding first.")
                return
        else:
            if left and right:
                caller.msg("You have no free hand. Unwield or drop something first.")
                return
        try:
            from world.ammo import is_ranged_weapon, WEAPON_AMMO_TYPE, DEFAULT_AMMO_CAPACITY
            if is_ranged_weapon(weapon_key) and not getattr(target.db, "ammo_type", None):
                target.db.ammo_type = WEAPON_AMMO_TYPE.get(weapon_key)
                target.db.ammo_capacity = DEFAULT_AMMO_CAPACITY.get(weapon_key, 0)
                target.db.ammo_current = int(getattr(target.db, "ammo_current", 0) or 0)
        except Exception:
            pass
        if hands_needed == 2:
            caller.db.left_hand_obj = target
            caller.db.right_hand_obj = target
        else:
            if not right:
                caller.db.right_hand_obj = target
            else:
                caller.db.left_hand_obj = target
        _update_primary_wielded(caller)
        caller.msg(f"You shift your grip and wield |w{target.name}|n.")


class CmdUnwield(Command):
    """
    Stop wielding the current weapon and put it back in your inventory.

    Usage:
      unwield
      unwield <weapon>
    """
    key = "unwield"
    locks = "cmd:all()"
    help_category = "Combat"
    usage_hint = "|wunwield|n or |wunwield <weapon>|n"

    def func(self):
        caller = self.caller
        left = getattr(caller.db, "left_hand_obj", None)
        right = getattr(caller.db, "right_hand_obj", None)
        if not self.args.strip():
            # Unwield primary (right hand, or left if no right)
            target = right if right and right.location == caller else (left if left and left.location == caller else None)
            if not target:
                caller.msg("You aren't wielding anything.")
                return
        else:
            target = caller.search(self.args.strip(), location=caller)
            if not target:
                return
            if target is not left and target is not right:
                caller.msg(f"You aren't wielding {target.name}.")
                return
        # Clear only the hand that holds this item
        if getattr(caller.db, "left_hand_obj", None) is target:
            caller.db.left_hand_obj = None
        if getattr(caller.db, "right_hand_obj", None) is target:
            caller.db.right_hand_obj = None
        _update_primary_wielded(caller)
        caller.msg(f"You stop wielding |w{target.name}|n and put it away.")


class CmdFreehands(Command):
    """
    Put away whatever you're holding in your hands (unwield / free hands).
    Usage: fh   or   freehands
    """
    key = "fh"
    aliases = ["freehands"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        left = getattr(caller.db, "left_hand_obj", None)
        right = getattr(caller.db, "right_hand_obj", None)
        if (not left or left.location != caller) and (not right or right.location != caller):
            caller.msg("Your hands are already free.")
            return
        names = []
        if left and left.location == caller:
            names.append(left.get_display_name(caller) if hasattr(left, "get_display_name") else left.name)
        if right and right.location == caller and right is not left:
            names.append(right.get_display_name(caller) if hasattr(right, "get_display_name") else right.name)
        caller.db.left_hand_obj = None
        caller.db.right_hand_obj = None
        _update_primary_wielded(caller)
        caller.msg(f"You put away {' and '.join('|w' + n + '|n' for n in names)}.")


class CmdInventory(Command):
    """
    Show what you're holding in your hands and your inventory.
    Usage: inventory   or   inv   or   i
    """
    key = "inventory"
    aliases = ["inv", "i"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        left = getattr(caller.db, "left_hand_obj", None)
        right = getattr(caller.db, "right_hand_obj", None)
        hand_parts = []
        if right and right.location == caller:
            hand_parts.append(f"{right.get_display_name(caller) if hasattr(right, 'get_display_name') else right.name} (right)")
        if left and left.location == caller and left is not right:
            hand_parts.append(f"{left.get_display_name(caller) if hasattr(left, 'get_display_name') else left.name} (left)")
        if hand_parts:
            hands_line = "|wHolding in hands:|n " + ", ".join(hand_parts)
        else:
            hands_line = "|wHolding in hands:|n Your hands are free."
        items = [o for o in caller.contents if o]
        if not items:
            caller.msg(hands_line + "\n\n|wYou are carrying:|n Nothing.")
            return
        from evennia.utils import utils
        from evennia.utils.ansi import raw as raw_ansi
        try:
            from world.clothing import get_worn_items
            worn_set = set(get_worn_items(caller))
        except Exception:
            worn_set = set()
        lines = [hands_line, ""]
        table = self.styled_table(border="header")
        wielded_set = {left, right} if left or right else set()
        for key, desc, obj_list in utils.group_objects_by_key_and_desc(items, caller=caller):
            if wielded_set and obj_list and any(o in wielded_set for o in obj_list):
                key = f"{key} |y(wielded)|n"
            elif worn_set and obj_list and any(o in worn_set for o in obj_list):
                key = f"{key} |y(worn)|n"
            table.add_row(
                f"|C{key}|n",
                "{}|n".format(utils.crop(raw_ansi(desc or ""), width=50) or ""),
            )
        lines.append(f"|wYou are carrying:\n{table}")
        caller.msg("\n".join(lines))


class CmdReload(Command):
    """
    Load ammunition into a ranged weapon. Wield the weapon, have matching ammo in inventory.

    Usage:
      reload              - load wielded weapon from ammo in inventory
      reload <weapon>     - load specified weapon (must be in inventory)
    """
    key = "reload"
    locks = "cmd:all()"
    help_category = "Combat"
    usage_typeclasses = ["typeclasses.weapons.CombatWeapon", "typeclasses.ammo.Ammo"]
    usage_hint = "|wreload|n (ranged weapon when wielded; ammo from inventory)"

    def func(self):
        caller = self.caller
        weapon = None
        if self.args.strip():
            weapon = caller.search(self.args.strip(), location=caller)
            if not weapon:
                return
        else:
            weapon = getattr(caller.db, "wielded_obj", None)
            if weapon and weapon.location != caller:
                weapon = None
            if not weapon:
                caller.msg("Wield a ranged weapon first, or specify one: |wreload <weapon>|n.")
                return

        from world.ammo import is_ranged_weapon, AMMO_TYPES, AMMO_TYPE_DISPLAY_NAMES
        weapon_key = getattr(weapon.db, "weapon_key", None)
        if not weapon_key or not is_ranged_weapon(weapon_key):
            caller.msg(f"{weapon.name} doesn't use ammunition.")
            return

        ammo_type = getattr(weapon.db, "ammo_type", None)
        if not ammo_type or ammo_type not in AMMO_TYPES:
            caller.msg(f"{weapon.name} has no ammo type set.")
            return

        capacity = int(getattr(weapon.db, "ammo_capacity", 0) or 0)
        current = int(getattr(weapon.db, "ammo_current", 0) or 0)
        need = capacity - current
        if need <= 0:
            caller.msg(f"{weapon.name} is already fully loaded ({current}/{capacity}).")
            return

        # Find matching ammo in caller's inventory
        ammo_candidates = [obj for obj in caller.contents if getattr(obj.db, "ammo_type", None) == ammo_type and (int(getattr(obj.db, "quantity", 0) or 0) > 0)]
        if not ammo_candidates:
            type_name = AMMO_TYPE_DISPLAY_NAMES.get(ammo_type, ammo_type)
            caller.msg(f"You have no {type_name} ammo in your inventory.")
            return

        # Use first stack with quantity
        ammo_stack = ammo_candidates[0]
        take = min(need, int(ammo_stack.db.quantity or 0))
        if take <= 0:
            caller.msg("That ammo stack is empty.")
            return

        weapon.db.ammo_current = current + take
        ammo_stack.db.quantity = int(ammo_stack.db.quantity or 0) - take
        type_name = AMMO_TYPE_DISPLAY_NAMES.get(ammo_type, ammo_type)
        caller.msg(f"You load {take} round(s) into |w{weapon.name}|n. ({current + take}/{capacity})")
        if ammo_stack.db.quantity <= 0:
            ammo_stack.delete()


class CmdUnload(Command):
    """
    Eject the magazine from a ranged weapon and get it back as an item.

    Usage:
      unload              - eject mag from wielded weapon
      unload <weapon>     - eject mag from specified weapon (in inventory)
    """
    key = "unload"
    aliases = ["eject", "eject mag"]
    locks = "cmd:all()"
    help_category = "Combat"
    usage_typeclasses = ["typeclasses.weapons.CombatWeapon"]
    usage_hint = "|wunload|n (when wielded, ranged only)"

    def func(self):
        caller = self.caller
        weapon = None
        if self.args.strip():
            weapon = caller.search(self.args.strip(), location=caller)
            if not weapon:
                return
        else:
            weapon = getattr(caller.db, "wielded_obj", None)
            if weapon and weapon.location != caller:
                weapon = None
            if not weapon:
                caller.msg("Wield a ranged weapon first, or specify one: |wunload <weapon>|n.")
                return

        from world.ammo import (
            is_ranged_weapon, AMMO_TYPES, AMMO_TYPE_TYPECLASS, AMMO_TYPE_MAGAZINE_KEY,
        )
        weapon_key = getattr(weapon.db, "weapon_key", None)
        if not weapon_key or not is_ranged_weapon(weapon_key):
            caller.msg(f"{weapon.name} doesn't use magazines.")
            return

        ammo_type = getattr(weapon.db, "ammo_type", None)
        if not ammo_type or ammo_type not in AMMO_TYPES:
            caller.msg(f"{weapon.name} has no ammo type set.")
            return

        current = int(getattr(weapon.db, "ammo_current", 0) or 0)
        if current <= 0:
            caller.msg(f"{weapon.name} is already empty. Nothing to eject.")
            return

        typeclass_path = AMMO_TYPE_TYPECLASS.get(ammo_type)
        if not typeclass_path:
            caller.msg("Cannot create magazine for that ammo type.")
            return

        from evennia.utils.create import create_object
        key = AMMO_TYPE_MAGAZINE_KEY.get(ammo_type, "magazine")
        try:
            mag = create_object(typeclass_path, key=key, location=caller)
            mag.db.quantity = current
            weapon.db.ammo_current = 0
            caller.msg(f"You eject the magazine from |w{weapon.name}|n. You have |w{mag.name}|n ({current} rounds) in hand.")
        except Exception as e:
            caller.msg(f"|rCould not eject magazine: {e}|n")


class CmdCheckAmmo(Command):
    """
    Check how many rounds are left in a ranged weapon's magazine (without unloading).

    Usage:
      check ammo              - check wielded weapon
      check ammo <weapon>     - check specified weapon
      ammo
      mag
    """
    key = "check ammo"
    aliases = ["ammo", "mag", "check mag", "rounds"]
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = self.caller
        weapon = None
        args = self.args.strip() if self.args else ""
        if args:
            weapon = caller.search(args, location=caller)
            if not weapon:
                return
        else:
            weapon = getattr(caller.db, "wielded_obj", None)
            if weapon and weapon.location != caller:
                weapon = None
            if not weapon:
                caller.msg("Wield a ranged weapon first, or specify one: |wcheck ammo <weapon>|n.")
                return

        from world.ammo import is_ranged_weapon
        weapon_key = getattr(weapon.db, "weapon_key", None)
        if not weapon_key or not is_ranged_weapon(weapon_key):
            caller.msg(f"{weapon.name} doesn't use ammunition.")
            return

        capacity = int(getattr(weapon.db, "ammo_capacity", 0) or 0)
        current = int(getattr(weapon.db, "ammo_current", 0) or 0)
        caller.msg(f"You thumb the magazine on |w{weapon.name}|n: |w{current}|n round(s) left." + (f" (capacity {capacity})" if capacity else "") + ".")


class CmdCheckAmmo(Command):
    """
    Check how many rounds are left in a ranged weapon's magazine (without unloading).

    Usage:
      check ammo              - check wielded weapon
      check ammo <weapon>     - check specified weapon
      ammo
      mag
    """
    key = "check ammo"
    aliases = ["ammo", "mag", "check mag", "rounds"]
    locks = "cmd:all()"
    help_category = "Combat"
    usage_typeclasses = ["typeclasses.weapons.CombatWeapon"]
    usage_hint = "|wcheck ammo|n (when wielded, ranged only)"

    def func(self):
        caller = self.caller
        weapon = None
        args = self.args.strip() if self.args else ""
        if args:
            weapon = caller.search(args, location=caller)
            if not weapon:
                return
        else:
            weapon = getattr(caller.db, "wielded_obj", None)
            if weapon and weapon.location != caller:
                weapon = None
            if not weapon:
                caller.msg("Wield a ranged weapon first, or specify one: |wcheck ammo <weapon>|n.")
                return

        from world.ammo import is_ranged_weapon
        weapon_key = getattr(weapon.db, "weapon_key", None)
        if not weapon_key or not is_ranged_weapon(weapon_key):
            caller.msg(f"{weapon.name} doesn't use ammunition.")
            return

        capacity = int(getattr(weapon.db, "ammo_capacity", 0) or 0)
        current = int(getattr(weapon.db, "ammo_current", 0) or 0)
        caller.msg(f"You thumb the magazine on |w{weapon.name}|n: |w{current}|n round(s) left." + (f" (capacity {capacity})" if capacity else "") + ".")


class CmdWear(Command):
    """
    Wear a piece of clothing from your inventory.

    Usage:
      wear <clothing>
    """
    key = "wear"
    aliases = ["put on", "don"]
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.clothing.Clothing"]
    usage_hint = "|wwear|n"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Wear what?")
            return
        target = caller.search(self.args, location=caller)
        if not target:
            return
        covered = getattr(target.db, "covered_parts", None)
        if not covered:
            caller.msg(f"{target.get_display_name(caller)} isn't something you can wear.")
            return
        worn = caller.db.worn or []
        if target in worn:
            caller.msg(f"You're already wearing {target.get_display_name(caller)}.")
            return
        caller.db.worn = worn + [target]
        caller.msg(f"You put on {target.get_display_name(caller)}.")
        caller.location.msg_contents(
            f"{caller.get_display_name(caller)} puts on {target.get_display_name(caller)}.",
            exclude=caller,
        )


class CmdRemove(Command):
    """
    Remove a piece of clothing you're wearing.

    Usage:
      remove <clothing>
    """
    key = "remove"
    aliases = ["take off", "doff"]
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.clothing.Clothing"]
    usage_hint = "|wremove|n"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Remove what?")
            return
        target = caller.search(self.args, location=caller)
        if not target:
            return
        worn = caller.db.worn or []
        if target not in worn:
            caller.msg(f"You aren't wearing {target.get_display_name(caller)}.")
            return
        caller.db.worn = [o for o in worn if o != target]
        caller.msg(f"You remove {target.get_display_name(caller)}.")
        caller.location.msg_contents(
            f"{caller.get_display_name(caller)} removes {target.get_display_name(caller)}.",
            exclude=caller,
        )


class CmdStrip(Command):
    """
    Take off a worn item from yourself or from another (living or corpse).
    The item is moved to your inventory.

    Usage:
      strip <item>              - take off something you're wearing
      strip <item> from <target> - take off something worn by another or a corpse
    """
    key = "strip"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not self.args or not self.args.strip():
            caller.msg("Strip what? Usage: strip <item> [from <target>]")
            return
        args = self.args.strip()
        if " from " in args:
            item_spec, _, target_spec = args.partition(" from ")
            item_spec = item_spec.strip()
            target_spec = target_spec.strip()
            if not item_spec or not target_spec:
                caller.msg("Usage: strip <item> from <target>")
                return
            target = caller.search(target_spec, location=caller.location)
            if not target:
                return
            if target != caller:
                try:
                    from world.death import is_character_logged_off, character_logged_off_long_enough
                    if is_character_logged_off(target):
                        if not character_logged_off_long_enough(target):
                            caller.msg("They haven't been asleep long enough.")
                            return
                except ImportError:
                    pass
        else:
            item_spec = args
            target = caller
        worn = list(target.db.worn or [])
        if not worn:
            if target is caller:
                caller.msg("You aren't wearing anything to strip.")
            else:
                caller.msg(f"{target.get_display_name(caller)} isn't wearing anything you can strip.")
            return
        item = caller.search(item_spec, candidates=worn)
        if not item:
            if target is caller:
                caller.msg(f"You aren't wearing '{item_spec}'.")
            else:
                caller.msg(f"{target.get_display_name(caller)} isn't wearing '{item_spec}'.")
            return
        target.db.worn = [o for o in worn if o != item]
        item.move_to(caller)
        iname = item.get_display_name(caller) if hasattr(item, "get_display_name") else item.name
        tname = target.get_display_name(caller) if hasattr(target, "get_display_name") else target.key
        if target is caller:
            caller.msg(f"You strip {iname} and take it.")
            caller.location.msg_contents(
                f"{caller.get_display_name(caller)} strips {iname}.",
                exclude=caller,
            )
        else:
            caller.msg(f"You strip {iname} from {tname} and take it.")
            caller.location.msg_contents(
                f"{caller.get_display_name(caller)} strips {iname} from {tname}.",
                exclude=caller,
            )


def _frisk_readout(caller, target):
    """One-time inventory readout for frisk/loot: show what target is carrying (excluding worn)."""
    from evennia.utils.utils import list_to_string
    from world.clothing import get_worn_items
    worn_objs = set(get_worn_items(target))
    contents = [o for o in target.contents if o != caller and o not in worn_objs]
    tname = target.get_display_name(caller)
    if not contents:
        caller.msg(f"You've checked {tname}. Nothing of interest on them.")
    else:
        names = [obj.get_display_name(caller) for obj in contents]
        caller.msg(f"You've checked {tname}. |wCarrying:|n " + list_to_string(names, endsep=" and ") + ".")


class CmdFrisk(Command):
    """
    Get a one-time readout of what someone is carrying (alive or sleeping).
    You must run the command again to see their inventory again.

    Usage:
      frisk <character>
    """
    key = "frisk"
    aliases = ["check", "patdown"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not self.args or not self.args.strip():
            caller.msg("Frisk who? Usage: frisk <character>")
            return
        from typeclasses.corpse import Corpse
        from evennia import DefaultCharacter
        target = caller.search(self.args.strip(), location=caller.location)
        if not target:
            return
        if isinstance(target, Corpse):
            caller.msg("That's a corpse. Use |wloot|n to search the body.")
            return
        if not isinstance(target, DefaultCharacter):
            caller.msg("You can only frisk characters.")
            return
        if target == caller:
            caller.msg("You know what you're carrying.")
            return
        tname = target.get_display_name(caller)
        caller.msg("You run your hands over %s's pockets and belongings." % tname)
        caller.location.msg_contents(
            "%s frisks %s." % (caller.get_display_name(caller), tname),
            exclude=caller,
        )
        _frisk_readout(caller, target)


# Custom Get: block taking from corpse until 30 min after death
try:
    from evennia.commands.default.general import CmdGet as DefaultCmdGet
except ImportError:
    DefaultCmdGet = None


class CmdGet(DefaultCmdGet if DefaultCmdGet else BaseCommand):
    """Get: same as default but taking from a logged-off character only allowed after 30 min."""

    def func(self):
        if DefaultCmdGet and " from " in self.args:
            args = self.args.strip()
            _, _, container_spec = args.partition(" from ")
            if container_spec:
                container = self.caller.search(container_spec.strip(), location=self.caller.location)
                if container:
                    try:
                        from typeclasses.corpse import Corpse
                        from evennia import DefaultCharacter
                        from world.death import is_character_logged_off, character_logged_off_long_enough
                        # Container is a character (not a corpse): only allow if logged off 30+ min
                        if isinstance(container, DefaultCharacter) and not isinstance(container, Corpse):
                            if is_character_logged_off(container) and not character_logged_off_long_enough(container):
                                self.caller.msg("They haven't been gone long enough. You can only take from someone who's been logged off at least half an hour.")
                                return
                            if not is_character_logged_off(container):
                                self.caller.msg("You can't take from someone who's wide awake!")
                                return
                    except ImportError:
                        pass
        if DefaultCmdGet:
            super().func()


def _loot_finish(caller_id, corpse_id):
    """Called after delay: mark corpse as looted by caller and show inventory."""
    from evennia.utils.search import search_object
    from evennia.utils.utils import list_to_string
    try:
        from typeclasses.corpse import Corpse
        from world.clothing import get_worn_items
    except ImportError:
        return
    try:
        caller = search_object("#%s" % caller_id)
        corpse = search_object("#%s" % corpse_id)
    except Exception:
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


# Tailor subcommands: first occurrence in args splits bolt_spec | subcmd | value
_TAILOR_SUBCMDS = ["name", "aliases", "worn", "worndesc", "desc", "tease", "coverage", "finalize"]


def _tailor_parse_args(args):
    """Return (bolt_spec, subcmd, value) or (None, None, None) if no subcmd found."""
    if not args or not args.strip():
        return None, None, None
    args = args.strip()
    best_pos = len(args)
    found_sub = None
    for sub in _TAILOR_SUBCMDS:
        pos = args.find(sub)
        if pos == 0 or (pos > 0 and args[pos - 1].isspace()):
            if pos < best_pos:
                best_pos = pos
                found_sub = sub
    if found_sub is None:
        return args.strip(), None, None
    bolt_spec = args[:best_pos].strip()
    rest = args[best_pos + len(found_sub):].strip()
    return bolt_spec, found_sub, rest


class CmdTailor(Command):
    """
    Customize a bolt of cloth (name, aliases, desc, tease, coverage) then finalize into clothing.

    Usage:
      tailor [bolt]                    - show draft status
      tailor [bolt] name <name>
      tailor [bolt] aliases <a1> [a2 ...]
      tailor [bolt] desc <text>         - main desc (when item is looked at)
      tailor [bolt] worndesc <text>     - worn desc (replaces body parts on look; $N, $P, $S)
      tailor [bolt] tease <text>        - wearer $N $P $S; target $T $R $U; item $I (see help tease)
      tailor [bolt] coverage <part> [part ...]  - body parts (lfoot, rshoulder, torso, etc.)
      tailor [bolt] finalize            - turn bolt into wearable clothing
    """
    key = "tailor"
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.bolt_of_cloth.BoltOfCloth"]
    usage_hint = "|wtailor|n (to make clothing)"

    def func(self):
        caller = self.caller
        bolt_spec, subcmd, value = _tailor_parse_args(self.args)

        if not bolt_spec and not subcmd:
            caller.msg("Usage: tailor [bolt] [name|aliases|desc|worndesc|tease|coverage|finalize] ...")
            return

        if bolt_spec:
            bolt = caller.search(bolt_spec, location=caller)
            if not bolt:
                return
            if not getattr(bolt, "is_draft", lambda: False)():
                caller.msg(f"{bolt.get_display_name(caller)} is not a bolt of cloth.")
                return
        else:
            # Find a bolt in inventory
            from typeclasses.bolt_of_cloth import BoltOfCloth
            bolts = [o for o in caller.contents if isinstance(o, BoltOfCloth)]
            if not bolts:
                caller.msg("You aren't holding a bolt of cloth. Specify which bolt or get one.")
                return
            if len(bolts) > 1:
                caller.msg("You have more than one bolt; specify which: tailor <bolt> ...")
                return
            bolt = bolts[0]

        if not subcmd:
            # Status
            st = bolt.get_draft_status()
            caller.msg("|wDraft status|n for %s:" % bolt.get_display_name(caller))
            caller.msg("  Name: %s" % st["name"])
            caller.msg("  Aliases: %s" % (st["aliases"] or "(none)"))
            caller.msg("  Desc: %s" % (st["desc"] or "(none)"))
            caller.msg("  Worn: %s" % (st["worn_desc"] or "(none)"))
            caller.msg("  Tease: %s" % (st["tease"] or "(none)"))
            caller.msg("  Coverage: %s" % (st["covered_parts"] or "(none)"))
            return

        if subcmd == "name":
            if not value:
                caller.msg("Usage: tailor [bolt] name <name>")
                return
            bolt.db.draft_name = value
            caller.msg("Draft name set to: %s" % value)
            return

        if subcmd == "aliases":
            aliases = value.split() if value else []
            bolt.db.draft_aliases = aliases
            caller.msg("Draft aliases set to: %s" % (aliases or "(none)"))
            return

        if subcmd == "desc":
            bolt.db.draft_desc = value or ""
            caller.msg("Draft description set.")
            return

        if subcmd in ("worndesc", "worn"):
            bolt.db.draft_worn_desc = value or ""
            caller.msg("Draft worn description set.")
            return

        if subcmd == "tease":
            bolt.db.draft_tease = value or ""
            caller.msg("Draft tease message set.")
            return

        if subcmd == "coverage":
            from typeclasses.bolt_of_cloth import resolve_coverage_args
            from world.medical import BODY_PARTS_HEAD_TO_FEET
            parts = value.split() if value else []
            canonical, invalid = resolve_coverage_args(parts)
            if invalid:
                caller.msg("Unknown body parts: %s. Use: %s" % (", ".join(invalid), ", ".join(BODY_PARTS_HEAD_TO_FEET)))
                return
            bolt.db.draft_covered_parts = canonical
            caller.msg("Coverage set to: %s" % canonical)
            return

        if subcmd == "finalize":
            name = (bolt.db.draft_name or "").strip() or "garment"
            if not bolt.db.draft_covered_parts:
                caller.msg("Set coverage before finalizing (e.g. tailor bolt coverage torso lshoulder rshoulder).")
                return
            try:
                bolt.swap_typeclass("typeclasses.clothing.Clothing")
            except Exception as e:
                caller.msg("Could not finalize: %s" % e)
                return
            bolt.key = name
            bolt.aliases.clear()
            for a in (bolt.db.draft_aliases or []):
                bolt.aliases.add(a)
            bolt.db.desc = bolt.db.draft_desc or ""
            bolt.db.worn_desc = bolt.db.draft_worn_desc or ""
            bolt.db.tease_message = bolt.db.draft_tease or ""
            bolt.db.covered_parts = list(bolt.db.draft_covered_parts or [])
            for k in ("draft_name", "draft_aliases", "draft_desc", "draft_worn_desc", "draft_tease", "draft_covered_parts"):
                if bolt.attributes.has(k):
                    bolt.attributes.remove(k)
            caller.msg("You finalize the bolt into: %s" % bolt.get_display_name(caller))
            return

        caller.msg("Unknown subcommand. Use: name, aliases, desc, worndesc, tease, coverage, finalize.")


class CmdTease(Command):
    """
    Use a clothing item's tease message. Tokens: wearer $N $P $S, target $T $R $U, item $I/$i.
    Use .verb so it conjugates. E.g. '$N .lift $p $I and .flash $p tits at $T'.
    Same tokens work in describe_bodypart, lp/pose, and worndesc. See |whelp tokens|n.

    Usage:
      tease <clothing> [at <target>]
    """
    key = "tease"
    aliases = ["flaunt"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Usage: tease <clothing> [at <target>]")
            return
        args = self.args.strip()
        target = None
        if " at " in args:
            part, _, target_spec = args.partition(" at ")
            args = part.strip()
            target = caller.search(target_spec.strip())
            if not target:
                return
        clothing_spec = args
        worn = getattr(caller.db, "worn", None) or []
        # Prefer matching worn item by name or alias
        item = None
        for w in worn:
            if not hasattr(w, "key"):
                continue
            if clothing_spec.lower() in (w.key or "").lower():
                item = w
                break
            if hasattr(w, "aliases"):
                for a in w.aliases.all():
                    if clothing_spec.lower() in str(a).lower():
                        item = w
                        break
                if item:
                    break
        if not item:
            item = caller.search(clothing_spec, location=caller)
        if not item:
            caller.msg("You don't have or aren't wearing '%s'." % clothing_spec)
            return
        if item not in worn:
            caller.msg("You need to be wearing it to tease with it.")
            return
        template = getattr(item.db, "tease_message", None) or ""
        if not template:
            caller.msg("That item has no tease message set.")
            return
        from world.crafting import substitute_tease_for_viewer
        from world.emote import format_emote_message
        room = caller.location
        if not room:
            return
        doer_name = caller.get_display_name(caller)
        for viewer in room.contents:
            if not hasattr(viewer, "msg"):
                continue
            body = substitute_tease_for_viewer(template, caller, target, viewer, item=item)
            if body:
                if viewer == caller:
                    viewer.msg(body)
                else:
                    viewer.msg(format_emote_message(doer_name, body))
        return


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
        # Permanently delete from the database
        target.delete()
        
        caller.msg(f"|y[SYSTEM]|n Entity '|w{name}|n' has been purged from the sector.")
        caller.location.msg_contents(f"The individual known as {name} vanishes as the simulation recalibrates.", exclude=caller)
class CmdHeal(Command):
    """
    Completely restores a target's HP and Stamina.

    Usage:
      heal <target>
      heal (targets yourself)
    """
    key = "heal"
    aliases = ["fullheal", "restore"]
    locks = "cmd:perm(Builder)"  # Restrict to Admins/Builders
    help_category = "Admin"

    def func(self):
        caller = self.caller
        
        # 1. Determine the target
        if not self.args:
            target = caller
        else:
            target = caller.search(self.args)
            
        if not target:
            return

        # 2. Reset the values and clear trauma
        target.db.current_hp = target.max_hp
        target.db.current_stamina = target.max_stamina
        try:
            from world.medical import reset_medical
            reset_medical(target)
        except Exception:
            pass

        # 3. Messaging
        if target == caller:
            caller.msg("|g[ADMIN]|n You have been fully restored.")
        else:
            caller.msg(f"|g[ADMIN]|n You have fully restored |w{target.name}|n.")
            target.msg(f"|g[ADMIN]|n Your vitals have been reset by {caller.name}.")


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
        from world.xp import XP_CAP

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


def _resolve_body_part(name):
    """Resolve short alias or full name to canonical body part key, or None."""
    from world.medical import BODY_PARTS, BODY_PART_ALIASES
    raw = name.strip().lower()
    if raw in BODY_PARTS:
        return raw
    return BODY_PART_ALIASES.get(raw)


def _body_parts_usage_list():
    """Head-to-feet list with short names where available (for usage line)."""
    from world.medical import BODY_PARTS_HEAD_TO_FEET, BODY_PART_ALIASES
    rev = {v: k for k, v in BODY_PART_ALIASES.items()}
    return [rev.get(p, p) for p in BODY_PARTS_HEAD_TO_FEET]


class CmdDescribeBodypart(Command):
    """
    Set a body-part description for your character (shown when someone looks at you).
    You can use tokens $N (your name), $P/$p (possessive), $S/$s (subject). See help tokens.

    Usage:
      describe_bodypart <body part> = <text>
      describe_bodypart head = scarred and crooked
      describe_bodypart lshoulder = $S has an old burn mark on $p shoulder

    Body parts (head to feet): head, face, neck, lshoulder, rshoulder, torso, back,
    abdomen, larm, rarm, lhand, rhand, groin, lthigh, rthigh, lfoot, rfoot
    """
    key = "describe_bodypart"
    aliases = ["descpart"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not hasattr(caller, "get_body_descriptions"):
            caller.msg("You cannot set body descriptions.")
            return
        if not self.args or "=" not in self.args:
            caller.msg("Usage: describe_bodypart <body part> = <text>")
            caller.msg("Body parts: " + ", ".join(_body_parts_usage_list()))
            return
        raw, _, rest = self.args.partition("=")
        rest = rest.strip()
        if not rest:
            caller.msg("Provide a description after the =.")
            return
        part = _resolve_body_part(raw)
        if not part:
            caller.msg("Unknown body part. Use: " + ", ".join(_body_parts_usage_list()))
            return
        caller.get_body_descriptions()
        caller.db.body_descriptions[part] = rest
        caller.msg(f"Set your |w{part}|n description: {rest}")


class CmdBody(Command):
    """
    List all body parts and their current descriptions (head to feet).

    Usage:
      body
    """
    key = "body"
    aliases = ["bodyparts", "mydesc"]
    help_category = "General"

    def func(self):
        from world.medical import BODY_PARTS_HEAD_TO_FEET
        caller = self.caller
        if not hasattr(caller, "db") or not hasattr(caller.db, "body_descriptions"):
            caller.msg("You cannot view body descriptions.")
            return
        # Show raw descriptions you set, not clothing-overridden (look uses effective desc)
        parts = caller.db.body_descriptions or {}
        caller.msg("|wYour body part descriptions|n (use |wdescribe_bodypart <part> = <text>|n to set)")
        caller.msg("")
        for part in BODY_PARTS_HEAD_TO_FEET:
            text = (parts.get(part) or "").strip()
            if text:
                caller.msg(f"  |w{part}|n: {text}")
            else:
                caller.msg(f"  |w{part}|n: |x(not set)|n")


class CmdLookPlace(Command):
    """
    Set how you appear in the room when someone looks (e.g. "standing here", "sitting by the fire").
    You can use tokens $N (your name), $P/$p (possessive), $S/$s (subject). See help tokens.

    Usage:
      lp <text>
      look_place <text>
      lp                    (show current)
    """
    key = "lp"
    aliases = ["look_place", "standing", "roompose"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = self.args.strip()
        if not args:
            current = getattr(caller.db, "room_pose", None) or "standing here"
            caller.msg(f"You appear in the room as: |w{current}|n.")
            caller.msg("Use |wlp <text>|n to change it (e.g. lp leaning against the wall).")
            return
        caller.db.room_pose = args
        pose = args.rstrip(".")
        caller.msg(f"When people look here, they will see: |w{caller.name} is {pose}.|n")


class CmdSleepPlace(Command):
    """
    Set how you appear when logged off: both the look line (e.g. "is sleeping here") and
    the message the room sees when you log off (e.g. "$N falls asleep."). Same command sets both.
    Use $N $P $S in the text. See help tokens.

    Usage:
      sp <text>
      sleep place <text>
      sleep_place <text>
      sp                    (show current)
    """
    key = "sp"
    aliases = ["sleep place", "sleep_place", "sleepplace", "logout_pose"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = self.args.strip()
        if not args:
            place = getattr(caller.db, "sleep_place", None) or "sleeping here"
            fall = getattr(caller.db, "fall_asleep_message", None) or "$N falls asleep."
            caller.msg(f"When logged off, you appear: |w{place}|n.")
            caller.msg(f"When you log off, the room sees: |w{fall}|n")
            caller.msg("Use |wsp <text>|n to set both (e.g. sp slumps into a doze).")
            return
        caller.db.sleep_place = args
        fall_msg = "$N " + args.rstrip(".") + "." if args else "$N falls asleep."
        caller.db.fall_asleep_message = fall_msg
        caller.msg(f"When logged off, others will see you as: |w{caller.name} is {args.rstrip('.')}.|n")
        caller.msg(f"When you log off, the room will see: |w{fall_msg}|n")


class CmdWakeMsg(Command):
    """
    Set the message the room sees when you log on (e.g. "wakes up").
    Use $N for your name. See help tokens.

    Usage:
      wakemsg <text>
      wakemsg                 (show current)
    """
    key = "wakemsg"
    aliases = ["wake_up", "wakeupmsg", "loginmsg"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = self.args.strip()
        if not args:
            current = getattr(caller.db, "wake_up_message", None) or "$N wakes up."
            caller.msg(f"When you log on, the room sees: |w{current}|n")
            caller.msg("Use |wwakemsg <text>|n (e.g. wakemsg $N stirs and opens $p eyes.).")
            return
        caller.db.wake_up_message = args
        caller.msg(f"Set. When you log on, the room will see: |w{args}|n")


class CmdSetPlace(Command):
    """
    Set how an object/item appears in the room when someone looks (e.g. "on the ground", "leaning against the wall").
    Only works on items and objects—you cannot set the place for characters (they use |wlp|n).

    Usage:
      set place <item> = <text>
      setplace <item> = <text>
      set place <item>     (show current; clear with empty text)
    """
    key = "set place"
    aliases = ["setplace"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from evennia import DefaultCharacter
        caller = self.caller
        args = self.args.strip()
        if not args:
            caller.msg("Usage: |wset place <item> = <text>|n (e.g. set place knife = lying in a pool of blood)")
            return
        if "=" in args:
            raw_name, _, text = args.partition("=")
            item_name = raw_name.strip()
            text = text.strip()
        else:
            item_name = args
            text = None
        if not item_name:
            caller.msg("Name an item: |wset place <item> = <text>|n")
            return
        location = caller.location
        if not location:
            caller.msg("You are not in a room.")
            return
        obj = caller.search(item_name, location=location)
        if not obj:
            return
        if isinstance(obj, DefaultCharacter):
            caller.msg("You can only set the place for objects and items, not for characters. Characters use |wlp|n.")
            return
        try:
            from typeclasses.vehicles import Vehicle
            if isinstance(obj, Vehicle):
                caller.msg("You cannot set the place for vehicles; they appear as parked or idling based on the engine.")
                return
        except ImportError:
            pass
        if getattr(obj.db, "original_name", None):
            caller.msg("You cannot set the place for corpses.")
            return
        if text is None:
            current = getattr(obj.db, "room_pose", None) or "on the ground"
            caller.msg(f"|w{obj.get_display_name(caller)}|n appears here as: {current}.")
            caller.msg("To change: |wset place {name} = <text>|n. To clear back to default: |wset place {name} = |n".format(name=obj.get_display_name(caller)))
            return
        if not text:
            if obj.db.room_pose:
                del obj.db.room_pose
            caller.msg(f"Cleared. |w{obj.get_display_name(caller)}|n will now appear as: on the ground.")
            return
        obj.db.room_pose = text
        pose = text.rstrip(".")
        caller.msg(f"When people look here, they will see: |w{obj.get_display_name(caller)} is {pose}.|n")


class CmdPronoun(Command):
    """Set your gender/pronouns for poses: male, female, or nonbinary (set in chargen; change here if needed)."""
    key = "pronoun"
    locks = "cmd:all()"
    help_category = "Roleplay"

    def func(self):
        from world.emote import PRONOUN_MAP
        caller = self.caller
        arg = (self.args or "").strip().lower()
        if not arg:
            current = getattr(caller.db, "pronoun", None) or getattr(caller.db, "gender", None) or "nonbinary"
            caller.msg(f"Your gender/pronouns: |w{current}|n. Options: male, female, nonbinary.")
            return
        if arg not in PRONOUN_MAP:
            caller.msg("Choose one: male (he/his/him), female (she/her), nonbinary (they/their/them).")
            return
        caller.db.pronoun = arg
        caller.db.gender = arg
        caller.msg(f"Gender/pronouns set to |w{arg}|n.")


def _run_emote(caller, text):
    """Shared emote logic for CmdEmote and CmdNoMatch."""
    from world.emote import (
        first_to_third,
        first_to_second,
        split_emote_segments,
        find_targets_in_text,
        build_emote_for_viewer,
        format_emote_message,
        replace_first_pronoun_with_name,
    )

    text = (text or "").strip()
    if not text:
        caller.msg("Usage: . <first-person text>")
        return

    location = caller.location
    if not location:
        return

    segments = split_emote_segments(text)
    # Comma-start = no "You " prefix in echo (scene-setting style)
    starts_with_comma = bool(segments and segments[0].strip().startswith(","))
    emitter_name = caller.get_display_name(caller)
    chars_here = location.filter_visible(location.contents_get(content_type="character"), caller)
    viewers = list(chars_here) + [caller]
    debug_on = getattr(caller.db, "emote_debug", False) and caller.account
    if debug_on:
        debug_on = caller.account.permissions.check("Builder") or caller.account.permissions.check("Admin")
    debug_lines = [] if debug_on else None

    for viewer in viewers:
        if viewer == caller:
            # --- Improved: handle quote protection, echo to caller cleanly ---
            echo_parts = []
            for i, seg in enumerate(segments):
                # Strip leading comma (no-conjugate marker) so it doesn't appear in echo
                seg = seg.lstrip().lstrip(",").lstrip() if seg.strip().startswith(",") else seg
                # Treat '.word' in the middle of a pose as plain 'word' (e.g. '.look' -> 'look')
                seg = re.sub(r" \.\s*(\w+)", r" \1", seg)
                # Quoted text is character speech: protect from transformation and restore verbatim
                quotes = re.findall(r'"([^"]*)"', seg)
                quote_map = {f"__Q{i}_{j}__": f'"{q}"' for j, q in enumerate(quotes)}
                temp_seg = seg
                for placeholder, original in quote_map.items():
                    temp_seg = temp_seg.replace(original, placeholder)
                converted = first_to_second(temp_seg)
                for placeholder, original in quote_map.items():
                    converted = converted.replace(placeholder, original)
                # Capitalization rules
                if i == 0:
                    converted = converted[0].upper() + converted[1:] if converted else converted
                else:
                    converted = converted[0].lower() + converted[1:] if converted else converted
                echo_parts.append(converted)
            # Join and ensure trailing punctuation
            full_echo = ". ".join(echo_parts).strip()
            if not full_echo.endswith((".", "!", "?", '"')):
                full_echo += "."
            # Capitalize first letter after each ". " (e.g. "calm. you" -> "calm. You")
            full_echo = re.sub(r"\.\s+(\w)", lambda m: ". " + m.group(1).upper(), full_echo)
            # Comma-start: no "You " prefix; else template adds "You " and we avoid double capital
            if starts_with_comma:
                body = full_echo
                msg = (body[0].upper() + body[1:]) if body and body[0].islower() else (body or "")
            else:
                if full_echo.lower().startswith("you "):
                    body = full_echo[4:].strip()
                else:
                    body = (full_echo[0].lower() + full_echo[1:]) if full_echo and full_echo[0].isupper() else full_echo
                msg = f"|cYou|n {body}" if body else "|cYou|n"
            if debug_lines is not None:
                debug_lines.append(("you", msg))
            caller.msg(msg)
        else:
            # --- THIRD PERSON VIEWERS ---
            body_parts = []
            for seg in segments:
                # Keep " .word" so first_to_third can conjugate those verbs (dot = verb tell)
                third = first_to_third(seg.strip(), caller)
                targets = find_targets_in_text(third, location.contents_get(content_type="character"), caller)
                body_parts.append(build_emote_for_viewer(third, viewer, targets, emitter_name))
            full_body = ". ".join(p.strip() for p in body_parts if p.strip())
            # Capitalize first letter after each ". " (e.g. "clear. he" -> "clear. He")
            full_body = re.sub(r"\.\s+(\w)", lambda m: ". " + m.group(1).upper(), full_body)
            if starts_with_comma:
                pronoun_key = getattr(caller.db, "pronoun", "neutral")
                full_body = replace_first_pronoun_with_name(full_body, pronoun_key, emitter_name)
                msg = full_body
            else:
                msg = format_emote_message(emitter_name, full_body)
            if debug_lines is not None:
                debug_lines.append((viewer.get_display_name(viewer), msg))
            viewer.msg(msg)

    if debug_lines:
        caller.msg("|w--- Emote debug ---|n")
        for who, line in debug_lines:
            if who == "you":
                caller.msg(f"|yTo you:|n {line}")
            else:
                caller.msg(f"|yTo {who}:|n {line}")
        caller.msg("|w---|n")


class CmdNoMatch(Command):
    """
    When no command matches, check if the line starts with '.' or ',' and run as emote.
    '.wave at Cairn.' and ',The stage is clear. I .look at Cairn.' work without typing 'emote'.
    """
    key = CMD_NOMATCH
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        if raw.startswith("."):
            emote_text = raw[1:].strip()
            if emote_text:
                _run_emote(self.caller, emote_text)
                return
        if raw.startswith(","):
            # Comma-start = emote with no-conjugate first segment (pass full string so comma is kept)
            if len(raw) > 1:
                _run_emote(self.caller, raw)
                return
        self.caller.msg(
            "Command '%s' is not available. Type \"help\" for help." % (raw or "(empty)")
        )


class CmdPose(Command):
    """
    First-person roleplay pose. You write as yourself; the room sees third person.
    Targets in the pose (e.g. "at Cairn") see "you" instead of their name.

    Usage:
      .<first-person text>   (no space needed)
      pose <first-person text>

    Markers:
      .word  = verb (conjugated in third person: .look -> looks)
      ,      = no conjugation for this segment's first word (start with scene-setting)

    Examples:
      .wave my hand.
      pose ,The stage is calm. I .look at Cairn.
      pose nod to Kase and step back.
    """
    key = "pose"
    aliases = ["."]
    locks = "cmd:all()"
    help_category = "Roleplay"

    def parse(self):
        """If line starts with '.', treat everything after the dot as args."""
        raw = (self.raw_string or "").strip()
        if raw.startswith("."):
            self.args = raw[1:].strip()

    def func(self):
        _run_emote(self.caller, self.args)


class CmdEmote(Command):
    """
    Simple emote: your name plus the exact text. No targeting, no pronoun/name replacement.
    Everyone in the room sees the same line.

    Usage:
      emote <text>

    Example:
      emote waves his hand at Cairn.
      Everyone sees: Bob waves his hand at Cairn.
    """
    key = "emote"
    locks = "cmd:all()"
    help_category = "Roleplay"

    def func(self):
        caller = self.caller
        text = (self.args or "").strip()
        if not text:
            caller.msg("Usage: emote <text>  (e.g. emote waves his hand at Cairn)")
            return
        name = caller.get_display_name(caller)
        msg = f"{name} {text.rstrip('.')}." if text and not text.endswith((".", "!", "?")) else f"{name} {text}"
        if caller.location:
            caller.location.msg_contents(msg)


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