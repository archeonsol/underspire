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

def _command_character(self):
    """Resolve to the puppeted character when command runs with Account as caller (e.g. Session cmdset)."""
    caller = self.caller
    if getattr(self, "session", None) and getattr(self.session, "puppet", None):
        puppet = self.session.puppet
        if puppet and (getattr(caller, "db", None) is None or not hasattr(caller.db, "current_hp")):
            return puppet
    return caller


class Command(BaseCommand):
    """
    Base command. Blocks all commands when character is flatlined (dying) or dead except for Admins/Builders.
    """
    def at_pre_cmd(self):
        """Block commands if character is flatlined (dying) or permanently dead."""
        caller = self.caller
        if not caller:
            return super().at_pre_cmd()
        # Resolve to puppeted character so we check the right object (caller may be Account when using Session cmdset)
        char = _command_character(self)
        try:
            if char.account and (char.account.permissions.check("Builder") or char.account.permissions.check("Admin")):
                return super().at_pre_cmd()
        except Exception:
            pass
        try:
            from world.death import is_flatlined, is_permanently_dead
            if is_flatlined(char):
                caller.msg("|rYou are dying. There is nothing you can do.|n")
                return True
            if is_permanently_dead(char):
                caller.msg("|rYou are dead. Only an administrator can help you now.|n")
                return True
        except Exception:
            pass
        hp = getattr(char, "hp", None)
        if hp is not None and hp <= 0:
            caller.msg("|rYou are dying. There is nothing you can do.|n")
            return True
        return super().at_pre_cmd()

# -------------------------------------------------------------
# CUSTOM COMMANDS
# -------------------------------------------------------------

class CmdStats(Command):
    """
    Display your character sheet: SPECIAL stats, skills, XP, and when the soul was last fragmented (shard date).

    Usage:
      @stats
      @sheet
    """
    key = "@stats"
    aliases = ["@sheet", "@score"]
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
        xp = int(getattr(caller.db, "xp", 0) or 0)

        # Soul last fragmented: from character's clone_snapshot (shard is per-character)
        snapshot = getattr(caller.db, "clone_snapshot", None)
        fragmented_str = ""
        if snapshot and snapshot.get("fragmented_at"):
            try:
                from datetime import datetime
                ts = snapshot["fragmented_at"]
                if isinstance(ts, (int, float)):
                    dt = datetime.utcfromtimestamp(ts)
                else:
                    dt = ts
                fragmented_str = dt.strftime("%Y-%m-%d %H:%M") + " UTC"
            except Exception:
                pass

        from world.levels import get_stat_grade, get_skill_grade
        # Original tall structure; grades from exact thresholds (stats: stored level, skills: level)
        w = 50
        edge = "|x├" + "─" * (w - 2) + "┤|n"
        output = "|x┌" + "─" * (w - 2) + "┐|n\n"
        output += "|x│|n |R■|n |wSOUL READOUT|n  |x—|n  " + (caller.name or "Unknown").ljust(18) + " |x│|n\n"
        output += "|x│|n   |wOrigin|n " + (bg or "Unknown").ljust(w - 18) + " |x│|n\n"
        output += edge + "\n"
        output += "|x│|n |wXP|n " + str(xp).ljust(w - 10) + " |x│|n\n"
        if fragmented_str:
            output += "|x│|n |wLast fragmented|n " + fragmented_str.ljust(w - 21) + " |x│|n\n"
        output += edge + "\n"
        output += "|x│|n |R CORE|n" + " ".ljust(w - 9) + "|x│|n\n"
        for key in STAT_KEYS:
            stored = caller.get_stat_level(key) if hasattr(caller, "get_stat_level") else 0
            letter = get_stat_grade(stored)
            adj = caller.get_stat_grade_adjective(letter, key) if hasattr(caller, "get_stat_grade_adjective") else letter
            output += "|x│|n   |w{}|n  |R[{}]|n {}\n".format(key.capitalize().ljust(12), letter, adj)
        output += edge + "\n"
        output += "|x│|n |R IMPLANTS|n" + " ".ljust(w - 14) + "|x│|n\n"
        skill_label_width = 24
        for key in SKILL_KEYS:
            level = caller.get_skill_level(key) if hasattr(caller, "get_skill_level") else (skills.get(key, 0) or 0)
            if not level:
                continue
            letter = get_skill_grade(level)
            adj = caller.get_skill_grade_adjective(letter) if hasattr(caller, "get_skill_grade_adjective") else letter
            label = SKILL_DISPLAY_NAMES.get(key, key.replace("_", " ").title())
            output += "|x│|n   |w{}|n  |R[{}]|n {}\n".format(label.ljust(skill_label_width), letter, adj)
        output += "|x└" + "─" * (w - 2) + "┘|n\n"
        caller.msg(output)


class CmdXp(Command):
    """
    View XP and spend it to advance stats or skills (cost per level from milestone curves).

    Usage:
      @xp                          - show XP and XP needed for next raise per stat/skill
      @xp advance stat <name> [N]   - spend XP to raise a stat by N levels (default 1)
      @xp advance skill <name> [N]  - spend XP to raise a skill by N levels (default 1)
    Bulk advances deduct the exact cost for each level step (while loop; max 3050 earnable XP).

    XP: 2 per 6h window, max 4 drops per 24h (8 XP/day).
    """
    key = "@xp"
    aliases = ["@advance", "@progress"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.xp import (
            XP_CAP, get_xp_cost_stat, get_xp_cost_skill,
            xp_cost_for_stat_level, xp_cost_for_skill_level,
            _stat_level, _skill_level, _stat_cap_level, _skill_cap_level,
        )
        from world.levels import get_stat_grade, get_skill_grade, MAX_STAT_LEVEL, MAX_LEVEL
        from world.chargen import STAT_KEYS
        from world.skills import SKILL_KEYS, SKILL_DISPLAY_NAMES
        caller = self.caller
        xp = float(getattr(caller.db, "xp", 0) or 0)
        cap = int(getattr(caller.db, "xp_cap", XP_CAP) or XP_CAP)

        if not self.args or self.args.strip().lower() in ("show", ""):
            # Column widths for aligned display (match chargen)
            NAME_W, LETTER_W, ADJ_W = 24, 5, 20
            xp_display = int(xp) if xp == int(xp) else round(xp, 2)
            output = "|cXP|n: |w{}|n\n\n".format(xp_display)
            output += "|cXP needed for next raise:|n\n\n"
            output += "|wStats|n:\n"
            for sk in STAT_KEYS:
                cost, _ = get_xp_cost_stat(caller, sk)
                letter = get_stat_grade(_stat_level(caller, sk))
                adj = caller.get_stat_grade_adjective(letter, sk)
                name_pad = sk.capitalize().ljust(NAME_W)
                letter_part = ("[" + letter + "] ").ljust(LETTER_W)
                adj_pad = adj.ljust(ADJ_W)
                if cost is None:
                    output += "  {} {} {} |x(at cap)|n\n".format(name_pad, letter_part, adj_pad)
                else:
                    cost_str = str(int(cost)) if cost == int(cost) else str(round(cost, 2))
                    output += "  {} {} {} next raise: |w{} XP|n\n".format(name_pad, letter_part, adj_pad, cost_str)
            output += "\n|wSkills|n:\n"
            for sk in SKILL_KEYS:
                cost, _ = get_xp_cost_skill(caller, sk)
                letter = get_skill_grade(_skill_level(caller, sk))
                adj = caller.get_skill_grade_adjective(letter)
                label = SKILL_DISPLAY_NAMES.get(sk, sk.replace("_", " ").title())
                name_pad = label.ljust(NAME_W)
                letter_part = ("[" + letter + "] ").ljust(LETTER_W)
                adj_pad = adj.ljust(ADJ_W)
                if cost is None:
                    output += "  {} {} {} |x(at cap)|n\n".format(name_pad, letter_part, adj_pad)
                else:
                    cost_str = str(int(cost)) if cost == int(cost) else str(round(cost, 2))
                    output += "  {} {} {} next raise: |w{} XP|n\n".format(name_pad, letter_part, adj_pad, cost_str)
            output += "\nUse |w@xp advance stat <name> [N]|n or |w@xp advance skill <name> [N]|n to spend XP (N = number of raises). You will be asked to confirm with |w@xp confirm|n."
            caller.msg(output)
            return

        parts = self.args.strip().split()
        # Handle confirm/cancel for pending XP spend
        if parts and parts[0].lower() == "confirm":
            pending = getattr(caller.db, "pending_xp_advance", None)
            if not pending:
                caller.msg("You have no pending XP advance. Use |w@xp advance stat <name> [N]|n or |w@xp advance skill <name> [N]|n.")
            else:
                from world.levels import get_stat_grade, get_skill_grade
                sub = pending["sub"]
                attr_key = pending["attr_key"]
                levels_gained = pending["levels_gained"]
                total_spent = pending["total_spent"]
                new_val = pending["new_val"]
                cur = pending["cur"]
                cap = pending["cap"]
                label = pending["label"]
                db_key = pending["db_key"]
                xp_now = float(getattr(caller.db, "xp", 0) or 0)
                if xp_now < total_spent:
                    caller.msg("You no longer have enough XP (need {}). Advance cancelled.".format(total_spent))
                    del caller.db.pending_xp_advance
                else:
                    get_grade_fn = get_stat_grade if sub == "stat" else get_skill_grade
                    get_adj_fn = (lambda letter: caller.get_stat_grade_adjective(letter, attr_key)) if sub == "stat" else caller.get_skill_grade_adjective
                    if not getattr(caller.db, db_key, None):
                        setattr(caller.db, db_key, {})
                    getattr(caller.db, db_key)[attr_key] = new_val
                    caller.db.xp = xp_now - total_spent
                    remainder = caller.db.xp
                    old_letter = get_grade_fn(cur)
                    new_letter = get_grade_fn(new_val)
                    letter_changed = old_letter != new_letter
                    spent_str = str(int(total_spent)) if total_spent == int(total_spent) else str(round(total_spent, 2))
                    if levels_gained == 1:
                        msg = "You spend {} XP.".format(spent_str)
                    else:
                        msg = "You spend {} XP and raise {} {} time{}.".format(spent_str, label, levels_gained, "s" if levels_gained > 1 else "")
                    if letter_changed:
                        adj = get_adj_fn(new_letter)
                        msg += " {} is now [{}] {}.".format(label, new_letter, adj)
                    rem_str = str(int(remainder)) if remainder == int(remainder) else str(round(remainder, 2))
                    if new_val >= cap and remainder > 0:
                        msg += " You reached your cap; {} XP remains.".format(rem_str)
                    caller.msg(msg)
                    del caller.db.pending_xp_advance
            return
        if parts and parts[0].lower() == "cancel":
            if getattr(caller.db, "pending_xp_advance", None):
                del caller.db.pending_xp_advance
                caller.msg("Pending XP advance cancelled.")
            else:
                caller.msg("You have no pending XP advance to cancel.")
            return

        if len(parts) < 2 or parts[0].lower() != "advance":
            caller.msg("Usage: @xp [show] | @xp advance stat <name> [N] | @xp advance skill <name> [N] | @xp confirm | @xp cancel")
            return
        sub = parts[1].lower()
        # Parse: advance stat <name> [N] or advance skill <name> [N]
        if sub not in ("stat", "skill"):
            caller.msg("Use |w@xp advance stat <name> [N]|n or |w@xp advance skill <name> [N]|n.")
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

        def advance_loop(cur, cap, bulk_n, xp_available, get_cost_fn):
            """Bulk-buy loop: sum cost step-by-step until cap or XP runs out. Returns (levels_gained, total_spent, new_val)."""
            total_spent = 0.0
            levels_gained = 0
            while levels_gained < bulk_n and cur + levels_gained < cap:
                cost = get_cost_fn(cur + levels_gained)
                if cost is None or xp_available - total_spent < cost:
                    break
                total_spent += cost
                levels_gained += 1
            new_val = min(cap, cur + levels_gained)
            return levels_gained, total_spent, new_val

        def format_insufficient_xp(get_cost_fn, cur, xp_available):
            cost_one = get_cost_fn(cur)
            cost_str = str(int(cost_one)) if cost_one is not None and cost_one == int(cost_one) else str(round(cost_one, 2)) if cost_one is not None else "?"
            xp_str = int(xp_available) if xp_available == int(xp_available) else round(xp_available, 2)
            caller.msg("You need {} XP for the next raise. You have {} XP.".format(cost_str, xp_str))

        def apply_and_msg(levels_gained, total_spent, new_val, cur, cap, get_grade_fn, label, db_key, attr_key, get_adj_fn):
            if levels_gained == 0:
                return
            if not getattr(caller.db, db_key, None):
                setattr(caller.db, db_key, {})
            getattr(caller.db, db_key)[attr_key] = new_val
            caller.db.xp = xp - total_spent
            remainder = xp - total_spent
            old_letter = get_grade_fn(cur)
            new_letter = get_grade_fn(new_val)
            letter_changed = old_letter != new_letter
            spent_str = str(int(total_spent)) if total_spent == int(total_spent) else str(round(total_spent, 2))
            if levels_gained == 1:
                msg = "You spend {} XP.".format(spent_str)
            else:
                msg = "You spend {} XP and raise {} {} time{}.".format(spent_str, label, levels_gained, "s" if levels_gained > 1 else "")
            if letter_changed:
                adj = get_adj_fn(new_letter)
                msg += " {} is now [{}] {}.".format(label, new_letter, adj)
            rem_str = str(int(remainder)) if remainder == int(remainder) else str(round(remainder, 2))
            if new_val >= cap and remainder > 0:
                msg += " You reached your cap; {} XP remains.".format(rem_str)
            caller.msg(msg)

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
            stat_cap = _stat_cap_level(caller, stat_key)
            if cur >= stat_cap:
                caller.msg("That stat is already at its cap.")
                return
            from world.xp import get_stat_cost
            levels_gained, total_spent, new_val = advance_loop(cur, stat_cap, bulk_n, xp, get_stat_cost)
            if levels_gained == 0:
                format_insufficient_xp(get_stat_cost, cur, xp)
                return
            spent_str = str(int(total_spent)) if total_spent == int(total_spent) else str(round(total_spent, 2))
            caller.db.pending_xp_advance = {
                "sub": "stat", "attr_key": stat_key, "levels_gained": levels_gained,
                "total_spent": total_spent, "new_val": new_val, "cur": cur, "cap": stat_cap,
                "label": stat_key.capitalize(), "db_key": "stats",
            }
            raise_msg = "time" if levels_gained == 1 else "times"
            caller.msg(
                "Raise |w{}|n by |w{}|n level(s)? This will spend |w{}|n XP ({} raise{}). "
                "Type |w@xp confirm|n to confirm or |w@xp cancel|n to cancel.".format(
                    stat_key.capitalize(), levels_gained, spent_str, levels_gained, raise_msg
                )
            )
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
            skill_cap = _skill_cap_level(caller, skill_key)
            if cur >= skill_cap:
                caller.msg("That skill is already at its cap.")
                return
            from world.xp import get_skill_cost
            levels_gained, total_spent, new_val = advance_loop(cur, skill_cap, bulk_n, xp, get_skill_cost)
            if levels_gained == 0:
                format_insufficient_xp(get_skill_cost, cur, xp)
                return
            label = SKILL_DISPLAY_NAMES.get(skill_key, skill_key.replace("_", " ").title())
            spent_str = str(int(total_spent)) if total_spent == int(total_spent) else str(round(total_spent, 2))
            caller.db.pending_xp_advance = {
                "sub": "skill", "attr_key": skill_key, "levels_gained": levels_gained,
                "total_spent": total_spent, "new_val": new_val, "cur": cur, "cap": skill_cap,
                "label": label, "db_key": "skills",
            }
            raise_msg = "time" if levels_gained == 1 else "times"
            caller.msg(
                "Raise |w{}|n by |w{}|n level(s)? This will spend |w{}|n XP ({} raise{}). "
                "Type |w@xp confirm|n to confirm or |w@xp cancel|n to cancel.".format(
                    label, levels_gained, spent_str, levels_gained, raise_msg
                )
            )
            return

        caller.msg("Use |w@xp advance stat <name> [N]|n or |w@xp advance skill <name> [N]|n.")


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
        try:
            from world.stamina import is_exhausted
            if is_exhausted(caller):
                caller.msg("You're too tired to fight.")
                return
        except ImportError:
            pass
        # If you're holding them in a grapple, attack = strangle (stamina drain until knockout); starts recurring tick
        if getattr(caller.db, "grappling", None) == target:
            from world.grapple import grapple_strike, start_grapple_strike_ticker
            success, msg = grapple_strike(caller, target)
            if success:
                caller.msg("|g%s|n" % msg)
                start_grapple_strike_ticker(caller, target)
            else:
                caller.msg("|r%s|n" % msg)
            return
        current = _get_combat_target(caller)
        if current == target:
            caller.msg("|yYou're already fighting them.|n")
            return
        if current and current != target:
            stop_combat_ticker(caller, current)
            caller.msg(f"|yYou switch targets to {target.name}.|n")
        start_combat_ticker(caller, target)
        # If target is a creature, set its target to you and start its AI so it fights back
        if getattr(target.db, "is_creature", False):
            target.db.current_target = caller
            try:
                from world.creature_combat import start_creature_ai_ticker
                start_creature_ai_ticker(target)
            except Exception:
                pass

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


class CmdFlee(Command):
    """
    Try to break away from combat and run. Contested evasion roll vs your opponent.
    Without a direction you flee to a random exit; with a direction you try that exit.
    Usage: flee [direction]
    """
    key = "flee"
    aliases = ["run", "escape"]
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = _combat_caller(self)
        if not getattr(caller, "db", None) or not hasattr(caller.db, "stats"):
            self.caller.msg("You must be in character to do that.")
            return
        from world.combat import _get_combat_target, remove_both_combat_tickers
        opponent = _get_combat_target(caller)
        if not opponent:
            caller.msg("You're not in combat.")
            return
        loc = caller.location
        if not loc:
            caller.msg("You have nowhere to go.")
            return
        exits = getattr(loc, "exits", None) or []
        if not exits:
            caller.msg("There's nowhere to flee!")
            return
        direction = (self.args or "").strip().lower()
        if direction:
            exit_obj = None
            for ex in exits:
                key = (getattr(ex, "key", None) or "").strip().lower()
                aliases = getattr(ex, "aliases", None)
                if hasattr(aliases, "all"):
                    aliases = [a.strip().lower() for a in (aliases.all() if aliases else [])]
                else:
                    aliases = [str(a).strip().lower() for a in (aliases or [])]
                if key == direction or direction in aliases:
                    exit_obj = ex
                    break
                if key.startswith(direction) or any(a.startswith(direction) for a in (aliases or [])):
                    exit_obj = ex
                    break
            if not exit_obj:
                caller.msg("No exit in that direction.")
                return
        else:
            import random
            exit_obj = random.choice(exits)
        dest = getattr(exit_obj, "destination", None)
        if not dest or not hasattr(caller, "move_to"):
            caller.msg("You can't flee that way.")
            return
        from world.skills import SKILL_STATS, DEFENSE_SKILL
        defense_stats = SKILL_STATS.get(DEFENSE_SKILL, ["agility", "perception"])
        _, flee_val = caller.roll_check(defense_stats, DEFENSE_SKILL, modifier=0)
        _, opp_val = opponent.roll_check(defense_stats, DEFENSE_SKILL, modifier=0)
        if flee_val <= opp_val:
            caller.msg("|rYou couldn't break away!|n")
            opponent.msg("|gThey tried to flee but you keep them in the fight.|n")
            if loc:
                loc.msg_contents(
                    "%s tries to flee but %s keeps them in the fight." % (caller.name, opponent.name),
                    exclude=(caller, opponent),
                )
            return
        remove_both_combat_tickers(caller, opponent)
        victim = getattr(caller.db, "grappling", None)
        if getattr(caller.db, "grappled_by", None) == opponent:
            caller.db.grappled_by = None
            if hasattr(opponent.db, "grappling") and opponent.db.grappling == caller:
                opponent.db.grappling = None
        dir_name = (getattr(exit_obj, "key", None) or "away").strip()
        caller.move_to(dest)
        if victim and hasattr(victim, "move_to"):
            victim.move_to(dest)
            dest.msg_contents("%s is dragged in by %s." % (victim.name, caller.name), exclude=(caller, victim))
        caller.msg("|gYou break away and flee %s!|n" % dir_name)
        opponent.msg("|r%s breaks away and flees %s!|n" % (caller.name, dir_name))
        if loc:
            loc.msg_contents("%s breaks away and flees %s!" % (caller.name, dir_name), exclude=(caller,))
        if dest:
            dest.msg_contents("%s bursts in from %s, out of breath." % (caller.name, dir_name), exclude=(caller,))


def _combat_caller(cmd_self):
    """Resolve caller to puppeted character when command runs with Account as caller (e.g. from Session cmdset)."""
    caller = cmd_self.caller
    if not getattr(caller.db, "stats", None) and getattr(cmd_self, "session", None):
        try:
            puppet = getattr(cmd_self.session, "puppet", None)
            if puppet:
                return puppet
        except Exception:
            pass
    return caller


class CmdGrapple(Command):
    """
    Grapple a character: agility vs perception (see it coming), then agility vs agility (land the grab).
    If you win, they are locked in your grasp and you can drag them when you move.
    Usage: grapple <target>
    """
    key = "grapple"
    aliases = ["grab", "grasp"]
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = _combat_caller(self)
        if not getattr(caller, "db", None) or not hasattr(caller.db, "stats"):
            self.caller.msg("You must be in character to grapple.")
            return
        args = (self.args or "").strip()
        if not args:
            caller.msg("Grapple who? Usage: grapple <target>")
            return
        target = caller.search(args, location=caller.location)
        if not target:
            return
        # Third party trying to grapple someone already in another's grasp (with delay like normal grapple)
        if getattr(target.db, "grappled_by", None):
            from world.grapple import start_grapple_third_party_attempt
            started, err = start_grapple_third_party_attempt(caller, target)
            if not started:
                caller.msg("|r%s|n" % err)
            return
        from world.grapple import start_grapple_attempt
        started, err = start_grapple_attempt(caller, target)
        if not started:
            caller.msg("|r%s|n" % err)


class CmdLetGo(Command):
    """
    Release the character you are grappling.
    Usage: letgo
    """
    key = "letgo"
    aliases = ["let go", "release", "ungrapple"]
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = _combat_caller(self)
        if not getattr(caller, "db", None) or not hasattr(caller.db, "stats"):
            self.caller.msg("You must be in character to do that.")
            return
        victim = getattr(caller.db, "grappling", None)
        from world.grapple import release_grapple
        success, msg = release_grapple(caller)
        if success:
            caller.msg("|g%s|n" % msg)
            if victim:
                victim.msg("|gYou are released.|n")
                if caller.location:
                    caller.location.msg_contents(
                        "%s releases %s." % (caller.name, victim.name),
                        exclude=(caller, victim),
                    )
        else:
            caller.msg("|r%s|n" % msg)


class CmdResist(Command):
    """
    Try to break out of a grapple. Strength + unarmed vs the holder; each attempt weakens their hold.
    Usage: resist
    """
    key = "resist"
    aliases = ["break free", "struggle"]
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = _combat_caller(self)
        if not getattr(caller, "db", None) or not hasattr(caller.db, "stats"):
            self.caller.msg("You must be in character to do that.")
            return
        grappler = getattr(caller.db, "grappled_by", None)
        from world.grapple import attempt_resist
        freed, msg_you, msg_holder = attempt_resist(caller)
        caller.msg("|g%s|n" % msg_you if freed else "|r%s|n" % msg_you)
        if grappler and msg_holder:
            grappler.msg("|r%s|n" % msg_holder if freed else "|y%s|n" % msg_holder)
        if freed and caller.location:
            caller.location.msg_contents(
                "%s breaks free of %s's grasp!" % (caller.name, grappler.name) if grappler else "%s breaks free!" % caller.name,
                exclude=(caller, grappler) if grappler else (caller,),
            )


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
            if is_character_logged_off(target) and not is_flatlined(target):
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
        from world.npc_templates import NPC_TEMPLATES
        from evennia.utils.evtable import EvTable
        table = EvTable("|wtemplate|n", "|wdescription|n", border="cells")
        for key, t in sorted(NPC_TEMPLATES.items()):
            table.add_row(key, t.get("name", key))
        caller.msg("|wNPC templates:|n |w@npc/summon <template>|n or |w@npc/summon <template>=<name>|n")
        caller.msg(table)

    def _do_summon(self, caller, rest):
        from world.npc_templates import create_npc_from_template, get_npc_template
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
        loc = caller.location
        if not loc:
            caller.msg("You have no location.")
            return
        npc = create_npc_from_template(template_key, name=name, location=loc)
        if not npc:
            caller.msg("|rFailed to create NPC.|n")
            return
        caller.msg("|gSummoned:|n %s." % npc.name)
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
        target.delete()
        caller.msg("|y%s has been unsummoned.|n" % name)
        if caller.location:
            caller.location.msg_contents("%s vanishes." % name, exclude=caller)

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
        target.key = new_name
        target.save()
        caller.msg("|gYou know them as %s now.|n" % new_name)
        if caller.location and caller.location == target.location:
            caller.location.msg_contents("%s is now called %s." % (old, new_name), exclude=(caller, target))

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
        from world.chargen import STAT_KEYS
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


class CmdSpawnItem(Command):
    """
    Spawn test items by prototype key. List is auto-generated from your game's
    prototype modules (e.g. world.prototypes). Builder/Admin only.

    Usage:
      spawnitem list              - list all available prototype keys
      spawnitem <prototype_key>   - spawn one into your inventory (e.g. spawnitem bolt_of_silk)

    New prototypes you add to world.prototypes (or other PROTOTYPE_MODULES) will
    appear in the list automatically. For typeclass-only items use |wtypeclasses|n
    and |wcreate <typeclass> = <key>|n.
    """
    key = "spawnitem"
    aliases = ["debugspawn", "spawni"]
    locks = ADMIN_LOCK
    help_category = "Admin"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args or args.lower() == "list":
            self._show_list(caller)
            return
        self._spawn_prototype(caller, args)

    def _show_list(self, caller):
        from evennia.prototypes import prototypes as protlib
        from evennia.utils.evtable import EvTable
        protlib.load_module_prototypes()
        # All module-based prototypes (no_db=True = don't hit DB prototypes)
        try:
            all_prots = protlib.search_prototype(no_db=True)
        except Exception as e:
            caller.msg("|rCould not load prototypes: %s|n" % e)
            return
        if not all_prots:
            caller.msg("|yNo prototypes found in PROTOTYPE_MODULES. Add dicts to world.prototypes (or your module) to see them here.|n")
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
        caller.msg("|wSpawn:|n |wspawnitem <prototype_key>|n (e.g. |wspawnitem %s|n)" % (all_prots[0].get("prototype_key", "bolt_of_silk")))
        caller.msg(table)
        caller.msg("|wTypeclass items:|n use |wtypeclasses|n and |wcreate <typeclass> = <key>|n.")

    def _spawn_prototype(self, caller, prototype_key):
        from evennia.prototypes import spawner
        from evennia.prototypes import prototypes as protlib
        protlib.load_module_prototypes()
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
        for obj in objs:
            obj.location = caller
        names = [o.get_display_name(caller) for o in objs]
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
        from world.armor_levels import ARMOR_TEMPLATES, ARMOR_LEVEL_STREET, ARMOR_LEVEL_ARMOR_WEAR, ARMOR_LEVEL_MEDIUM, ARMOR_LEVEL_HEAVY
        from evennia.utils.evtable import EvTable
        level_names = {
            ARMOR_LEVEL_STREET: "Street",
            ARMOR_LEVEL_ARMOR_WEAR: "Armor wear",
            ARMOR_LEVEL_MEDIUM: "Medium",
            ARMOR_LEVEL_HEAVY: "Heavy",
        }
        table = EvTable("|wkey|n", "|wname|n", "|wlevel|n", border="cells")
        for t in ARMOR_TEMPLATES:
            table.add_row(t["key"], t["name"], level_names.get(t.get("level", 1), "?"))
        caller.msg("|wArmor templates:|n |w@spawnarmor <key> [quality]|n")
        caller.msg(table)


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
    key = "disembark"
    aliases = ["disembark"]
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
            ("typeclasses.medical_tools.Tourniquet", "tourniquet"),
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


class CmdSpawnSeat(Command):
    """
    Create a seat (chair, couch, bench) in the room. Builder+.
    Usage: spawnseat [name]
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
            create_object("typeclasses.seats.Seat", key=name, location=caller.location)
            caller.msg("|gSeat |w%s|n created here. Players can |wsit on %s|n.|n" % (name, name))
        except Exception as e:
            caller.msg("|rCould not create seat: %s|n" % e)


class CmdSpawnBed(Command):
    """
    Create a bed (or cot, sofa) in the room. Builder+.
    Usage: spawnbed [name]
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
            create_object("typeclasses.seats.Bed", key=name, location=caller.location)
            caller.msg("|gBed |w%s|n created here. Players can |wlie on %s|n.|n" % (name, name))
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
            from world.creature_combat import stop_creature_ai_ticker
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
            from world.creature_combat import start_creature_ai_ticker
            start_creature_ai_ticker(creature)
            caller.msg("|g%s will now attack %s. AI runs every ~8 seconds.|n" % (creature.name, target.name))
            return
        caller.msg("Use |wtarget <player>|n or |wnotarget|n.")


class CmdGenerateCreature(Command):
    """
    Open a menu to generate a custom creature with your own stats and moves. Builder+.
    Usage: generatecreature
    """
    key = "generatecreature"
    aliases = ["gencreature", "create creature", "creature menu"]
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        caller = self.caller
        if not caller.location:
            caller.msg("You need to be in a room to create a creature.")
            return
        from evennia.utils.evmenu import EvMenu
        # Initialize builder state
        caller.ndb.creature_gen = {
            "key": "Custom Creature",
            "max_hp": 100,
            "armor_rating": 10,
            "base_attack": 50,
            "room_pose": "standing here",
            "moves": {},
        }
        EvMenu(caller, "world.creature_gen_menu", startnode="node_start")


def _get_pod_from_caller(caller):
    """If caller is inside a splinter pod interior, return the pod object; else None."""
    loc = getattr(caller, "location", None)
    if not loc:
        return None
    pod = getattr(loc.db, "pod", None)
    if pod:
        return pod
    from evennia.utils.search import search_typeclass
    for p in search_typeclass("typeclasses.splinter_pod.SplinterPod"):
        if getattr(p.db, "interior", None) is loc:
            return p
    return None


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
        except ImportError:
            pass
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


def _spirit_account(caller):
    """Get the Account puppeting this Spirit (caller in death limbo)."""
    if not hasattr(caller, "sessions"):
        return None
    try:
        for session in (caller.sessions.get() or []):
            acc = getattr(session, "account", None)
            if acc:
                return acc
    except Exception:
        pass
    return None


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
                except Exception:
                    pass
            if corpse and getattr(corpse, "db", None) and hasattr(corpse.db, "clone_snapshot"):
                try:
                    del corpse.db["clone_snapshot"]
                except Exception:
                    pass
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
        # Unpuppet all sessions first so nothing is attached to the Spirit
        if hasattr(account, "unpuppet_object") and hasattr(account, "sessions"):
            for session in (account.sessions.get() or []):
                try:
                    account.unpuppet_object(session)
                except Exception:
                    pass
        # Unlink corpse from account only; corpse stays persistent in the game world (do not delete)
        corpse = getattr(account.db, "dead_character_corpse", None)
        if corpse and hasattr(account, "characters"):
            try:
                account.characters.remove(corpse)
            except Exception:
                pass
        for key in ("dead_character_name", "dead_character_corpse"):
            if hasattr(account.db, key):
                try:
                    del account.db[key]
                except Exception:
                    pass
        # Erase the Spirit entirely so reconnect shows create-character / connect screen
        spirit = getattr(account.db, "death_spirit", None)
        if spirit and hasattr(spirit, "id"):
            if hasattr(account, "characters") and hasattr(account.characters, "remove"):
                try:
                    account.characters.remove(spirit)
                except Exception:
                    pass
            try:
                spirit.delete()
            except Exception:
                pass
        if hasattr(account.db, "death_spirit"):
            try:
                del account.db["death_spirit"]
            except Exception:
                pass
        # Clear any "last puppet" so reconnect doesn't try to restore Spirit
        if hasattr(account.db, "_last_puppet"):
            try:
                del account.db["_last_puppet"]
            except Exception:
                pass
        reason = "You have gone to the light. Create a new character when you return."
        if hasattr(account, "sessions"):
            for session in (account.sessions.get() or []):
                try:
                    if hasattr(session, "sessionhandler") and session.sessionhandler:
                        session.sessionhandler.disconnect(session, reason=reason)
                    elif hasattr(session, "disconnect"):
                        session.disconnect(reason)
                except Exception:
                    pass


class CmdSit(Command):
    """
    Sit on a seat (chair, couch, bench, etc.).
    Usage: sit <seat> / sit on <seat>
    """
    key = "sit"
    aliases = ["sit on"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if args.lower().startswith("on "):
            args = args[3:].strip()
        if not args:
            caller.msg("Sit on what? Usage: sit <seat>")
            return
        from typeclasses.seats import Seat
        seat = caller.search(args, location=caller.location)
        if not seat:
            return
        if not isinstance(seat, Seat):
            caller.msg("You can only sit on a chair, couch, or similar seat.")
            return
        if seat.get_sitter():
            caller.msg("Someone is already sitting there.")
            return
        caller.db.sitting_on = seat
        sname = seat.get_display_name(caller)
        caller.msg("|wYou sit down on %s.|n" % sname)
        if caller.location:
            caller.location.msg_contents(
                "%s sits down on %s." % (caller.name, sname),
                exclude=caller,
            )


class CmdLieOnTable(Command):
    """
    Lie down on an operating table (for surgery) or a bed/cot (for rest).
    Usage: lie on <table|bed> / lie down on <table|bed>
    """
    key = "lie"
    aliases = ["lie down", "lie on"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if args.lower().startswith("on "):
            args = args[3:].strip()
        if not args:
            caller.msg("Lie on what? Usage: lie on <operating table|bed>")
            return
        from typeclasses.medical_tools import OperatingTable
        from typeclasses.seats import Bed
        obj = caller.search(args, location=caller.location)
        if not obj:
            return
        if isinstance(obj, OperatingTable):
            if obj.get_patient():
                caller.msg("Someone is already on the table. Wait for them to get up.")
                return
            caller.db.lying_on_table = obj
            caller.msg("|wYou lie down on the operating table. The metal is cold.|n")
            if caller.location:
                caller.location.msg_contents(
                    "%s lies down on the operating table." % caller.name,
                    exclude=caller,
                )
        elif isinstance(obj, Bed):
            if obj.get_occupant():
                caller.msg("Someone is already lying there.")
                return
            caller.db.lying_on = obj
            bname = obj.get_display_name(caller)
            caller.msg("|wYou lie down on %s.|n" % bname)
            if caller.location:
                caller.location.msg_contents(
                    "%s lies down on %s." % (caller.name, bname),
                    exclude=caller,
                )
        else:
            caller.msg("You can only lie on an operating table or a bed.")


class CmdGetOffTable(Command):
    """
    Get up from a seat, bed, or operating table.
    Usage: getup / stand (avoid 'get' prefix so 'get <item>' is not stolen)
    """
    key = "getup"
    aliases = ["stand up", "stand", "getoff", "getofftable"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        cleared = []
        if getattr(caller.db, "lying_on_table", None):
            cleared.append("operating table")
            del caller.db.lying_on_table
        if getattr(caller.db, "sitting_on", None):
            cleared.append("seat")
            del caller.db.sitting_on
        if getattr(caller.db, "lying_on", None):
            cleared.append("bed")
            del caller.db.lying_on
        if not cleared:
            caller.msg("You are not sitting or lying on anything.")
            return
        caller.msg("|wYou get up.|n")
        if caller.location:
            caller.location.msg_contents(
                "%s gets up." % caller.name,
                exclude=caller,
            )


class CmdSurgery(Command):
    """
    Perform organ surgery on a patient lying on the operating table.
    Long narrative sequence with skill check; severe organ damage only.
    Usage: surgery <organ>
    """
    key = "surgery"
    aliases = ["operate"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Surgery on what organ? Usage: surgery <organ> (e.g. surgery heart, surgery liver)")
            return
        from world.medical_treatment import ORGAN_ALIASES
        organ_arg = args.strip().lower()
        organ_key = ORGAN_ALIASES.get(organ_arg, organ_arg.replace(" ", "_"))
        from typeclasses.medical_tools import OperatingTable
        table = None
        for obj in caller.location.contents:
            if isinstance(obj, OperatingTable):
                table = obj
                break
        if not table:
            caller.msg("There is no operating table here. The patient must lie on the table first.")
            return
        patient = table.get_patient()
        if not patient:
            caller.msg("No one is on the operating table. They must use 'lie on operating table' first.")
            return
        from world.medical_surgery import start_surgery_sequence
        from world.medical import ORGAN_INFO
        if organ_key not in ORGAN_INFO:
            caller.msg("Unknown organ. Try: brain, eyes, throat, carotid, heart, lungs, spine_cord, liver, spleen, stomach, kidneys, pelvic_organs, collarbone_area.")
            return
        started, err = start_surgery_sequence(caller, patient, table, organ_key)
        if not started:
            caller.msg(err or "You cannot perform that surgery now.")


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


# -----------------------------------------------------------------------------
# Staff suite: sheet, setstat, setskill, makenpc, npcset, goto, summon
# -----------------------------------------------------------------------------

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
        from world.chargen import STAT_KEYS
        from world.skills import SKILL_KEYS, SKILL_DISPLAY_NAMES
        from world.levels import get_stat_grade, get_skill_grade
        stats = target.db.stats or {}
        skills = target.db.skills or {}
        bg = target.db.background or "Unknown"
        try:
            hp_str = "{} / {}".format(target.hp, target.max_hp)
            st_str = "{} / {}".format(target.stamina, target.max_stamina)
            load_str = "{} kg".format(target.carry_capacity)
        except Exception:
            hp_str = st_str = load_str = "---"
        w = 50
        line = "|c+" + "=" * (w - 2) + "+|n"
        thin = "|c|" + "-" * (w - 2) + "||n"
        npc_tag = " |r[NPC]|n" if getattr(target.db, "is_npc", False) else ""
        output = line + "\n"
        output += "|c||n  |W STAFF READOUT |w {}|n{}\n".format((target.name or "Unknown"), npc_tag)
        output += "|c|||n  |wOrigin|n " + bg + "\n"
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
        from world.chargen import STAT_KEYS
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
    Usage: goto <character>
    """
    key = "goto"
    aliases = ["teleport", "tpto"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: goto <character>")
            return
        target = caller.search(args, global_search=True)
        if not target:
            return
        loc = getattr(target, "location", None)
        if not loc:
            caller.msg("That character has no location.")
            return
        caller.move_to(loc)
        caller.msg("|gYou go to {}.|n".format(target.name))


class CmdSummon(Command):
    """
    Bring a character to your location. Builder+.
    Usage: summon <character>
    """
    key = "summon"
    aliases = ["bring", "fetch"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: summon <character>")
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
        target.msg("|yYou have been summoned to {}.|n".format(caller.name))


class CmdSetVoid(Command):
    """
    Set the current room as the void (discipline holding room). Builder+.
    Voided characters are moved here and cannot leave until released.
    Usage: setvoid
    """
    key = "setvoid"
    aliases = ["voidroom"]
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
            caller.msg("|gThis room is now the void. Use |wvoid <character> [reason]|n to send someone here, |w@release <character>|n to free them.|n")
        except Exception as e:
            caller.msg("|rCould not set void room: {}|n".format(e))


class CmdVoid(Command):
    """
    Send a character to the void (discipline room). They cannot leave until released. Builder+.
    Set the void room first with |wsetvoid|n in that room.
    Usage: void <character> [reason]
    """
    key = "void"
    aliases = ["jail", "timeout", "discipline"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        parts = (self.args or "").strip().split(None, 1)
        if not parts:
            caller.msg("Usage: void <character> [reason]")
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
            caller.msg("|rNo void room set. Go to the discipline room and use |wsetvoid|n first.|n")
            return
        from evennia.utils.search import search_object
        void_room = search_object("#%s" % int(void_id))
        if not void_room:
            void_room = search_object(int(void_id))
        if not void_room:
            caller.msg("|rVoid room no longer exists. Use |wsetvoid|n in the discipline room again.|n")
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
    key = "@release"
    aliases = ["unvoid", "free", "unjail"]
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
    except ImportError:
        pass
    if getattr(character.db, "grappled_by", None) or getattr(character.db, "grappling", None):
        return False, "You can't go OOC while grappled."
    try:
        from world.grapple import is_unconscious
        if is_unconscious(character):
            return False, "You can't go OOC while unconscious."
    except ImportError:
        pass
    if getattr(character.db, "voided", False):
        return False, "You can't go OOC from the void."
    return True, None


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
            except Exception:
                pass
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
                except Exception:
                    pass
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
    Find where a character is (room name and id). Builder+.
    Usage: find <character>
    """
    key = "find"
    aliases = ["where", "locate"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: find <character>")
            return
        target = caller.search(args, global_search=True)
        if not target:
            return
        loc = getattr(target, "location", None)
        if not loc:
            caller.msg("{} has no location.".format(target.name))
            return
        voided = " |r[VOIDED]|n" if getattr(target.db, "voided", False) else ""
        caller.msg("|w{}|n is at: |w{}|n (#{}){}".format(target.name, loc.name or loc.key, getattr(loc, "id", "?"), voided))


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
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: @restore <character>")
            return
        target = caller.search(args, global_search=True)
        if not target or not hasattr(target, "db"):
            return
        try:
            from world.death import is_flatlined, clear_flatline
            if is_flatlined(target):
                clear_flatline(target)
            from world.medical import reset_medical
            reset_medical(target)
            mx = target.max_hp
            target.db.current_hp = mx
            target.db.current_stamina = target.max_stamina
            caller.msg("|g{} restored to full HP, stamina, and trauma cleared (no bleeding/fractures/organ damage).|n".format(target.name))
            if target != caller:
                target.msg("|gYou have been restored to full health; all trauma has been cleared.|n")
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


class CmdExamine(Command):
    """
    Look at an object and see what commands you can use with it.

    Usage:
      @examine <object>
      @ex <object>
    """
    key = "@examine"
    aliases = ["@ex"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Examine what? Usage: @examine <object>")
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


class CmdSurvey(Command):
    """
    Inspect armor to determine protection and mobility impact. Requires arms_tech skill.

    Usage:
      survey <armor>
    """
    key = "survey"
    aliases = ["armor survey", "inspect armor"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Survey what? Usage: survey <armor>")
            return
        from world.armor import _is_armor
        from world.skills import SKILL_STATS

        obj = caller.search(self.args.strip(), location=caller)
        if not obj:
            obj = caller.search(self.args.strip(), location=caller.location)
        if not obj:
            return
        if not _is_armor(obj):
            caller.msg(f"{obj.get_display_name(caller)} is not armor you can survey.")
            return

        stats = SKILL_STATS.get("arms_tech", ["intelligence", "perception"])
        level, roll_value = caller.roll_check(stats, "arms_tech")

        if level == "Failure":
            caller.msg("You can't tell much about its armor properties.")
            return

        # Basic: damage types protected, mobility yes/no
        from world.damage_types import DAMAGE_TYPES
        prot = getattr(obj.db, "protection", None) or {}
        types_protected = [dt for dt in DAMAGE_TYPES if prot.get(dt, 0) > 0]
        mobility = obj.get_mobility_impact() if hasattr(obj, "get_mobility_impact") else (getattr(obj.db, "mobility_impact", 0) or 0)
        has_mobility = mobility != 0

        if level == "Critical Success" or (level == "Full Success" and roll_value > 75):
            # High success: exact protection per type, exact mobility
            lines = ["|wArmor survey (detailed):|n"]
            if types_protected:
                for dt in types_protected:
                    base = prot.get(dt, 0)
                    effective = obj.get_protection(dt) if hasattr(obj, "get_protection") else base
                    lines.append("  %s: %s (effective %s)" % (dt.capitalize(), base, effective))
            else:
                lines.append("  No damage protection.")
            lines.append("  Mobility impact: %s" % mobility)
            quality = max(0, min(100, int(getattr(obj.db, "quality", 100) or 100)))
            lines.append("  Quality (durability): %s" % quality)
            caller.msg("\n".join(lines))
        else:
            # Basic success: types and mobility yes/no
            if types_protected:
                caller.msg("It protects against: %s." % ", ".join(types_protected))
            else:
                caller.msg("It offers no significant damage protection.")
            if has_mobility:
                caller.msg("It impacts mobility.")
            else:
                caller.msg("It does not impact mobility.")


class CmdRepairArmor(Command):
    """
    Restore armor quality (durability) using arms_tech. Use on worn or held armor.

    Usage:
      repair <armor>
    """
    key = "repair"
    aliases = ["repair armor", "fix armor"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Repair what? Usage: repair <armor>")
            return
        from world.armor import _is_armor, repair_armor
        from world.skills import SKILL_STATS

        obj = caller.search(self.args.strip(), location=caller)
        if not obj:
            obj = caller.search(self.args.strip(), location=caller.location)
        if not obj:
            return
        if not _is_armor(obj):
            caller.msg(f"{obj.get_display_name(caller)} is not armor you can repair.")
            return

        quality_before = max(0, min(100, int(getattr(obj.db, "quality", 100) or 100)))
        if quality_before >= 100:
            caller.msg("It's already in peak condition.")
            return

        stats = SKILL_STATS.get("arms_tech", ["intelligence", "perception"])
        level, _ = caller.roll_check(stats, "arms_tech")

        if level == "Failure":
            caller.msg("You fail to improve its condition.")
            return
        amount = 15 if level == "Critical Success" else (10 if level == "Full Success" else 5)
        repair_armor(obj, amount)
        quality_after = max(0, min(100, int(getattr(obj.db, "quality", 100) or 100)))
        caller.msg("You restore some of its condition. Quality: %s -> %s." % (quality_before, quality_after))


class CmdHt(Command):
    """
    Quick health check: condition (HP), rested (stamina), and recovering (stamina regen rate).
    Use on yourself or another; wording uses their pronouns when checking others.

    Usage:
      ht
      ht <target>
    """
    key = "ht"
    aliases = ["diagnose", "diag", "check"]
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.characters.Character"]
    usage_hint = "|wht|n or |wht <target>|n"

    def func(self):
        caller = self.caller
        if not self.args:
            target = caller
        else:
            target = caller.search(self.args)
        if not target:
            return
        if not hasattr(target, "db") or not hasattr(target, "max_hp"):
            caller.msg("You cannot assess that.")
            return
        from world.medical import get_ht_summary, get_diagnose_trauma_for_skill
        first_person = target == caller
        status = get_ht_summary(target, first_person=first_person)
        med_level = getattr(caller, "get_skill_level", lambda s: 0)("medicine")
        extra = get_diagnose_trauma_for_skill(target, med_level)
        if extra:
            status = status + "\n\n" + extra
        caller.msg(status)


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
            caller.msg("That tool isn't meant for bleeding control. Use bandages, a medkit, suture kit, hemostatic agent, tourniquet, or surgical kit.")
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
        # Nutritious food boosts stamina regen for a while (all food counts unless obj has db.nutritious = False)
        if getattr(obj.db, "nutritious", True):
            import time
            caller.db.last_nutritious_meal = time.time()
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
    Wear a piece of clothing or armor from your inventory.

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

        # Armor stacking: enforce max total stacking_score
        from world.armor import (
            MAX_ARMOR_STACKING_SCORE,
            get_worn_armor_stack_total,
            check_layer_warning,
            _is_armor,
        )
        if _is_armor(target):
            current_stack = get_worn_armor_stack_total(caller)
            add_score = target.get_stacking_score()
            if current_stack >= MAX_ARMOR_STACKING_SCORE:
                caller.msg("You cannot wear any more armor.")
                return
            if current_stack + add_score > MAX_ARMOR_STACKING_SCORE:
                caller.msg(
                    "That would exceed your armor limit. You may be able to wear a smaller piece of armor instead."
                )
                return

        # Layering warning: lower layer under higher on same part (don't block)
        warn, higher = check_layer_warning(caller, target)
        if warn and higher:
            caller.msg("The item must be worn under %s." % higher.get_display_name(caller))

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
    aliases = ["patdown"]  # "check" reserved for diagnose (medical check)
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
    """Get: supports 'get <item> from <container>'; from logged-off/corpse only when allowed."""
    key = "get"
    aliases = ["take", "pick up"]

    def at_pre_cmd(self):
        # Block when flatlined/dead (CmdGet does not inherit from Command)
        char = _command_character(self)
        try:
            if char.account and (char.account.permissions.check("Builder") or char.account.permissions.check("Admin")):
                return super().at_pre_cmd() if hasattr(super(), "at_pre_cmd") else None
        except Exception:
            pass
        try:
            from world.death import is_flatlined, is_permanently_dead
            if is_flatlined(char):
                self.caller.msg("|rYou are dying. There is nothing you can do.|n")
                return True
            if is_permanently_dead(char):
                self.caller.msg("|rYou are dead. Only an administrator can help you now.|n")
                return True
        except Exception:
            pass
        if getattr(char, "hp", None) is not None and char.hp <= 0:
            self.caller.msg("|rYou are dying. There is nothing you can do.|n")
            return True
        return super().at_pre_cmd() if hasattr(super(), "at_pre_cmd") else None

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            if DefaultCmdGet:
                super().func()
            else:
                caller.msg("Get what?")
            return
        if " from " not in args:
            if DefaultCmdGet:
                super().func()
            return
        # Parse "get <item> from <container>" — default CmdGet does NOT support this, so we handle it fully
        item_spec, _, container_spec = args.partition(" from ")
        item_spec = item_spec.strip()
        container_spec = container_spec.strip()
        if not item_spec or not container_spec:
            caller.msg("Usage: get <item> from <container>")
            return
        container = caller.search(container_spec, location=caller.location)
        if not container:
            return
        try:
            from typeclasses.corpse import Corpse
            from evennia import DefaultCharacter
            from world.death import is_character_logged_off, character_logged_off_long_enough
            if isinstance(container, DefaultCharacter) and not isinstance(container, Corpse):
                if not is_character_logged_off(container):
                    caller.msg("You can't take from someone who's wide awake!")
                    return
                if not character_logged_off_long_enough(container):
                    caller.msg("They haven't been gone long enough. You can only take from someone who's been logged off at least half an hour.")
                    return
        except ImportError:
            pass
        # Search for the item inside the container (contents, not location=caller.location)
        obj = caller.search(item_spec, location=container)
        if not obj:
            return
        from evennia.utils import utils
        objs = utils.make_iter(obj)
        if len(objs) == 1 and objs[0] == caller:
            caller.msg("You can't get yourself.")
            return
        for o in objs:
            if not o.access(caller, "get"):
                err = getattr(getattr(o, "db", None), "get_err_msg", None)
                caller.msg(err if err else "You can't get that.")
                return
            if not o.at_pre_get(caller):
                return
        moved = []
        for o in objs:
            if o.move_to(caller, quiet=True, move_type="get"):
                moved.append(o)
                o.at_get(caller)
        if not moved:
            caller.msg("That can't be picked up.")
        else:
            obj_name = moved[0].get_numbered_name(len(moved), caller, return_string=True)
            caller.msg("You get %s from %s." % (obj_name, container.get_display_name(caller)))
            caller.location.msg_contents(
                "%s gets %s from %s." % (caller.get_display_name(caller), obj_name, container.get_display_name(caller)),
                exclude=caller,
            )


class CmdPut(Command):
    """Put an object you're holding into a container (e.g. put cassette in television)."""
    key = "put"
    aliases = ["insert"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller or not caller.location:
            return
        args = (self.args or "").strip()
        if " in " not in args and " into " not in args:
            self.caller.msg("Usage: put <item> in <container>")
            return
        for sep in (" in ", " into "):
            if sep in args:
                item_spec, _, container_spec = args.partition(sep)
                break
        else:
            item_spec = container_spec = ""
        item_spec = item_spec.strip()
        container_spec = container_spec.strip()
        if not item_spec or not container_spec:
            self.caller.msg("Usage: put <item> in <container>")
            return
        obj = caller.search(item_spec, location=caller)
        if not obj:
            return
        container = caller.search(container_spec, location=caller.location)
        if not container:
            return
        if container == caller:
            self.caller.msg("You can't put something into yourself.")
            return
        if obj == container:
            self.caller.msg("You can't put something into itself.")
            return
        if not hasattr(obj, "move_to"):
            self.caller.msg("You can't put that anywhere.")
            return
        if obj.location != caller:
            self.caller.msg("You're not holding that.")
            return
        if not container.access(caller, "get"):
            self.caller.msg("You can't put anything in that.")
            return
        if hasattr(container, "at_pre_object_receive") and not container.at_pre_object_receive(obj, caller):
            return
        if obj.move_to(container, quiet=True):
            if hasattr(container, "at_object_receive"):
                container.at_object_receive(obj, caller)
            obj_name = obj.get_numbered_name(1, caller, return_string=True)
            cont_name = container.get_display_name(caller)
            self.caller.msg("You put %s in %s." % (obj_name, cont_name))
            caller.location.msg_contents(
                "%s puts %s in %s." % (caller.get_display_name(caller), obj_name, cont_name),
                exclude=caller,
            )
        else:
            self.caller.msg("You can't put that in there.")


def _find_camera(caller):
    """Return a Camera in caller's location or in caller's inventory, or None."""
    try:
        from typeclasses.broadcast import Camera
    except ImportError:
        return None
    loc = caller.location
    if loc:
        for obj in loc.contents:
            if isinstance(obj, Camera):
                return obj
    for obj in (caller.contents if hasattr(caller, "contents") else []):
        if isinstance(obj, Camera):
            return obj
    return None


def _find_television(caller):
    """Return a Television in caller's location, or None."""
    try:
        from typeclasses.broadcast import Television
    except ImportError:
        return None
    loc = caller.location
    if not loc:
        return None
    for obj in loc.contents:
        if isinstance(obj, Television):
            return obj
    return None


class CmdCamera(Command):
    """
    Operate a camera: set live (link to a TV), record, stop, or unlink from TV.
    Usage:
      camera live <television>   - broadcast this room to that TV in real time
      camera unlink             - unlink camera from TV and turn off live
      camera record             - start recording (stop with 'camera stop')
      camera stop               - stop recording and create a cassette here
      camera                    - show camera status
    """
    key = "camera"
    aliases = ["operate camera"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller or not caller.location:
            return
        args = (self.args or "").strip().lower()
        camera = _find_camera(caller)
        if not camera:
            self.caller.msg("There's no camera here or in your inventory.")
            return
        if not args:
            mode = getattr(camera.db, "mode", "off")
            tv_id = getattr(camera.db, "linked_tv", None)
            tv = _get_object_by_id(tv_id) if tv_id else None
            tv_name = tv.get_display_name(caller) if tv else "none"
            self.caller.msg("Camera is |w%s|n. Linked TV: %s." % (mode, tv_name))
            if mode == "record":
                buf = getattr(camera.db, "recording_buffer", []) or []
                self.caller.msg("Recording: %s lines so far." % len(buf))
            return
        parts = args.split(None, 1)
        sub = parts[0]
        rest = (parts[1] if len(parts) > 1 else "").strip()
        if sub == "live":
            if not rest:
                self.caller.msg("Usage: camera live <television>")
                return
            tv = caller.search(rest, location=caller.location)
            if not tv:
                return
            try:
                from typeclasses.broadcast import Television
                if not isinstance(tv, Television):
                    self.caller.msg("That's not a television.")
                    return
            except ImportError:
                self.caller.msg("That's not a television.")
                return
            camera.db.mode = "live"
            camera.db.linked_tv = tv.id
            self.caller.msg("Camera is now |wlive|n, broadcasting to %s." % tv.get_display_name(caller))
            return
        if sub in ("unlink", "off"):
            was_live = getattr(camera.db, "mode", "off") == "live"
            camera.db.mode = "off"
            camera.db.linked_tv = None
            if was_live:
                self.caller.msg("Camera unlinked from the television and turned off.")
            else:
                self.caller.msg("Camera is off. (It wasn't linked to a TV.)")
            return
        if sub == "record":
            camera.db.mode = "record"
            camera.db.recording_buffer = []
            camera.db.record_start_time = None
            self.caller.msg("Camera is now |wrecording|n. Use |wcamera stop|n to finish and create a cassette.")
            return
        if sub == "stop":
            if getattr(camera.db, "mode", "off") != "record":
                self.caller.msg("The camera isn't recording.")
                return
            cassette = camera.stop_recording_and_make_cassette(caller.location)
            if cassette:
                self.caller.msg("Recording stopped. A |wrecording cassette|n appears here.")
                caller.location.msg_contents(
                    "%s stops the camera; a recording cassette appears." % caller.get_display_name(caller),
                    exclude=caller,
                )
            else:
                self.caller.msg("Recording stopped. (Nothing was recorded.)")
            return
        self.caller.msg("Usage: camera live <tv> | camera unlink | camera record | camera stop")


def _get_object_by_id(dbref):
    if dbref is None:
        return None
    from evennia.utils.search import search_object
    try:
        ref = "#%s" % int(dbref)
        result = search_object(ref)
        return result[0] if result else None
    except (TypeError, ValueError):
        return None


class CmdTuneTelevision(Command):
    """
    Play the cassette that's inside a television in the room.
    Usage: tune television   or   tune tv
    Put a cassette in the TV first with: put <cassette> in <television>
    """
    key = "tune"
    aliases = ["tune television", "tune tv", "play television", "play tv"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller or not caller.location:
            return
        tv = _find_television(caller)
        if not tv:
            self.caller.msg("There's no television here.")
            return
        cassette = tv.get_cassette()
        if not cassette:
            self.caller.msg("There's no cassette in the television. Put one in first.")
            return
        self.caller.msg("You tune the television; the recording begins to play.")
        caller.location.msg_contents(
            "%s tunes the television; the recording begins to play." % caller.get_display_name(caller),
            exclude=caller,
        )
        tv.play_recording()


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


# --- Multi-puppet: run commands as a specific puppeted NPC (p1, p2, ... p9) ---


def _clear_multi_puppet_links_for_account(account):
    """Remove _multi_puppet_account_id and _multi_puppet_slot from all characters in account's multi_puppets."""
    ids = list(getattr(account.db, "multi_puppets", None) or [])
    for oid in ids:
        obj = _get_object_by_id(oid)
        if obj and hasattr(obj, "db"):
            if hasattr(obj.db, "_multi_puppet_account_id"):
                try:
                    del obj.db["_multi_puppet_account_id"]
                except Exception:
                    pass
            if hasattr(obj.db, "_multi_puppet_slot"):
                try:
                    del obj.db["_multi_puppet_slot"]
                except Exception:
                    pass


def _set_multi_puppet_link(char, account_id, slot_1based):
    """Mark a character as being in an account's multi-puppet set at the given slot (1-based)."""
    if char and hasattr(char, "db"):
        char.db._multi_puppet_account_id = account_id
        char.db._multi_puppet_slot = slot_1based


def _multi_puppet_account(caller):
    """Return the Account for multi-puppet commands (caller may be Account or Character)."""
    if hasattr(caller, "account") and caller.account:
        return caller.account
    return caller


def _multi_puppet_list(account):
    """Return list of puppet dbrefs; ensure current session.puppet is in the list if we're puppeting."""
    ids = list(getattr(account.db, "multi_puppets", None) or [])
    session = getattr(account, "sessions", None)
    if session and hasattr(session, "get"):
        sess_list = session.get()
        if sess_list:
            sess = sess_list[0]
            puppet = getattr(sess, "puppet", None)
            if puppet and (not ids or ids[-1] != getattr(puppet, "id", None)):
                if not ids:
                    ids = [puppet.id]
                elif puppet.id not in ids:
                    ids = list(ids) + [puppet.id]
                account.db.multi_puppets = ids
    return ids


def _resolve_multi_puppet(account, index):
    """Return (Character or None, 0-based index). index 0 = first in list (p1)."""
    ids = _multi_puppet_list(account)
    if index < 0 or index >= len(ids):
        return None, index
    from evennia.utils.search import search_object
    try:
        ref = "#%s" % int(ids[index])
        result = search_object(ref)
        return (result[0] if result else None), index
    except (TypeError, ValueError):
        return None, index


class CmdAddPuppet(BaseCommand):
    """
    Add another character to your multi-puppet set without unpuppeting the current one.
    Your session will now control the new character (normal commands use them); use p1, p2, ...
    to run commands as the first, second, etc. puppet.
    Usage: @addpuppet <character>
    """
    key = "@addpuppet"
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        account = getattr(self.caller, "account", self.caller)
        if not hasattr(account, "db"):
            self.msg("No account.")
            return
        session = getattr(self, "session", None)
        if not session:
            self.msg("No session.")
            return
        if not self.args or not self.args.strip():
            self.msg("Usage: @addpuppet <character>")
            return
        # Resolve character: search from current puppet's location or globally
        searcher = getattr(session, "puppet", None) or self.caller
        char = searcher.search(self.args.strip(), global_search=True) if hasattr(searcher, "search") else None
        if not char:
            from evennia.utils.search import search_object
            char = search_object(self.args.strip())
            char = char[0] if char else None
        if not char:
            return
        from evennia.utils import make_iter
        char = make_iter(char)[0] if make_iter(char) else char
        if not hasattr(char, "location"):
            self.msg("That's not a character you can puppet.")
            return
        # Build multi_puppets: current puppet is always p1; newly added go to p2, p3, ... Do NOT call puppet_object.
        ids = list(getattr(account.db, "multi_puppets", None) or [])
        if not ids and getattr(session, "puppet", None):
            ids = [session.puppet.id]
            _set_multi_puppet_link(session.puppet, account.id, 1)
        if char.id in ids:
            self.msg("You already have that character in your puppet set.")
            return
        # Append: p1 = current (first in list), p2 = first added, p3 = second added, etc.
        ids.append(char.id)
        account.db.multi_puppets = ids
        for i, oid in enumerate(ids):
            obj = _get_object_by_id(oid)
            if obj:
                _set_multi_puppet_link(obj, account.id, i + 1)
        self.msg("You add |w%s|n to your puppet set. You remain controlling your current character (p1). Use |wp2|n to act as %s, |wp3|n for the next, etc." % (char.get_display_name(self.caller), char.get_display_name(self.caller)))


class CmdPuppetList(BaseCommand):
    """
    List your current multi-puppet set (p1, p2, ... and which character each slot is).
    Usage: @puppet/list
    """
    key = "@puppet/list"
    aliases = ["@puppetlist", "puppet list"]
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        account = getattr(self.caller, "account", self.caller)
        if not hasattr(account, "db"):
            self.msg("No account.")
            return
        session = getattr(self, "session", None)
        ids = _multi_puppet_list(account)
        if not ids:
            self.msg("You have no puppets in your set. Use |w@puppet|n to puppet a character, then |w@addpuppet <name>|n to add more.")
            return
        lines = []
        current = getattr(session, "puppet", None) if session else None
        for i, oid in enumerate(ids):
            obj = _get_object_by_id(oid)
            name = obj.get_display_name(self.caller) if obj else "#%s (gone)" % oid
            slot = i + 1
            mark = " |w(you)|n" if obj and obj == current else ""
            lines.append("  p%s: %s%s" % (slot, name, mark))
        self.msg("|wYour puppet set:|n\n%s" % "\n".join(lines))


class CmdPuppetSlot(BaseCommand):
    """
    Run a command as one of your multi-puppeted characters.
    Usage: p1 <command>   p2 <command>   ...   p9 <command>
    Example: p1 say Hello world   p2 go north
    """
    key = "p1"
    aliases = ["p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9"]
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        account = _multi_puppet_account(self.caller)
        session = getattr(self, "session", None)
        if not session:
            # Fallback: get session from account
            if hasattr(account, "sessions") and account.sessions.get():
                session = account.sessions.get()[0]
        if not session:
            self.msg("No session.")
            return
        # Parse slot from cmdstring: p1 -> 0, p2 -> 1, ...
        raw = (self.cmdstring or "").strip().lower()
        if raw.startswith("p") and len(raw) >= 2 and raw[1:].isdigit():
            index = int(raw[1:]) - 1
        else:
            index = 0
        char, _ = _resolve_multi_puppet(account, index)
        if not char:
            self.msg("You don't have a puppet in slot %s. Use |w@puppet|n and |w@addpuppet|n to build your set." % (index + 1))
            return
        sub_cmd = (self.args or "").strip()
        if not sub_cmd:
            self.msg("Usage: %s <command>   (e.g. %s say Hello)" % (self.cmdstring, self.cmdstring))
            return
        # Temporarily set session.puppet to this character so the command runs as them (cmdset merge uses session.puppet)
        old_puppet = getattr(session, "puppet", None)
        session.puppet = char
        try:
            d = char.execute_cmd(sub_cmd, session=session)
            if d is not None and hasattr(d, "addBoth"):
                def _restore(_):
                    session.puppet = old_puppet
                d.addBoth(_restore)
            else:
                session.puppet = old_puppet
        except Exception as e:
            session.puppet = old_puppet
            self.msg("|rError running command: %s|n" % e)


def _send_to_channel(caller, channel_alias, args, session, msg_func, no_channel_msg, no_send_msg, usage_msg):
    """Helper: resolve account, find channel by alias, check send, send message."""
    from evennia import search_channel
    from evennia.utils.utils import strip_unsafe_input
    account = getattr(caller, "account", caller)
    if not hasattr(account, "permissions"):
        msg_func("You must be logged in to use channels.")
        return
    channels = search_channel(channel_alias)
    if not channels:
        msg_func(no_channel_msg)
        return
    try:
        channel = channels[0]
    except (TypeError, IndexError):
        msg_func(no_channel_msg)
        return
    if not channel.access(account, "send"):
        msg_func(no_send_msg)
        return
    message = (args or "").strip()
    if not message:
        msg_func(usage_msg)
        return
    message = strip_unsafe_input(message, session)
    channel.msg(message, senders=account)


def _subscribe_channel(account, alias, msg_func):
    """Subscribe account to channel by alias (xooc, xgame, xstaff). Returns True on success."""
    from evennia import search_channel
    channels = search_channel(alias)
    if not channels:
        msg_func("No channel found matching '%s'." % alias)
        return False
    try:
        channel = channels[0]
    except (TypeError, IndexError):
        msg_func("No channel found matching '%s'." % alias)
        return False
    if not channel.access(account, "listen"):
        msg_func("You are not allowed to subscribe to that channel.")
        return False
    if channel.has_connection(account):
        msg_func("You are already subscribed to %s." % channel.key)
        return False
    if not channel.connect(account):
        msg_func("Could not subscribe to %s." % channel.key)
        return False
    msg_func("You are now subscribed to |w%s|n (%s). You can leave with |wchannelunsub %s|n." % (channel.key, alias, alias))
    return True


def _unsubscribe_channel(account, alias, msg_func):
    """Unsubscribe account from channel by alias. Returns True on success."""
    from evennia import search_channel
    channels = search_channel(alias)
    if not channels:
        msg_func("No channel found matching '%s'." % alias)
        return False
    try:
        channel = channels[0]
    except (TypeError, IndexError):
        msg_func("No channel found matching '%s'." % alias)
        return False
    if not channel.has_connection(account):
        msg_func("You are not subscribed to %s." % channel.key)
        return False
    channel.disconnect(account)
    msg_func("You left %s (%s)." % (channel.key, alias))
    return True


class CmdChannelSub(Command):
    """Subscribe to an OOC channel so you can send and receive. Usage: channelsub xooc"""
    key = "channelsub"
    aliases = ["chsub"]
    locks = "cmd:all()"
    help_category = "Channels"

    def func(self):
        account = getattr(self.caller, "account", self.caller)
        if not hasattr(account, "permissions"):
            self.msg("You must be logged in.")
            return
        alias = (self.args or "").strip().lower()
        if not alias:
            self.msg("Usage: channelsub <channel>   (e.g. channelsub xooc, channelsub xgame). Staff: channelsub xstaff")
            return
        _subscribe_channel(account, alias, self.msg)


class CmdChannelUnsub(Command):
    """Leave an OOC channel. Usage: channelunsub xooc"""
    key = "channelunsub"
    aliases = ["chunsub"]
    locks = "cmd:all()"
    help_category = "Channels"

    def func(self):
        account = getattr(self.caller, "account", self.caller)
        if not hasattr(account, "permissions"):
            self.msg("You must be logged in.")
            return
        alias = (self.args or "").strip().lower()
        if not alias:
            self.msg("Usage: channelunsub <channel>   (e.g. channelunsub xooc)")
            return
        _unsubscribe_channel(account, alias, self.msg)


class CmdXooc(Command):
    """Send a message to OOC-Chat (xooc). Use @oocname to set the name others see."""
    key = "xooc"
    locks = "cmd:all()"
    help_category = "Channels"

    def func(self):
        _send_to_channel(
            self.caller, "xooc", self.args, self.session, self.msg,
            "OOC-Chat channel is not available.",
            "You are not allowed to send to OOC-Chat.",
            "Usage: xooc <message>",
        )


class CmdXgame(Command):
    """Send a message to Game-Help (xgame)."""
    key = "xgame"
    locks = "cmd:all()"
    help_category = "Channels"

    def func(self):
        _send_to_channel(
            self.caller, "xgame", self.args, self.session, self.msg,
            "Game-Help channel is not available.",
            "You are not allowed to send to Game-Help.",
            "Usage: xgame <message>",
        )


class CmdXstaff(Command):
    """Send a message to the Staff channel (staff only)."""
    key = "xstaff"
    locks = "cmd:perm(Builder)"
    help_category = "Channels"

    def func(self):
        _send_to_channel(
            self.caller, "xstaff", self.args, self.session, self.msg,
            "Staff channel is not available.",
            "You are not allowed to send to the Staff channel.",
            "Usage: xstaff <message>",
        )


def _xhelp_staff_reply(caller, target_name, message, msg_func, session):
    """Send a private help reply from staff to one account. Returns True on success."""
    from evennia.utils.search import search_account
    from evennia.utils.utils import strip_unsafe_input
    if not target_name or not (message or "").strip():
        return False
    accounts = search_account(target_name, exact=False)
    if not accounts:
        msg_func("No account found matching '%s'." % target_name)
        return False
    account = accounts[0] if isinstance(accounts, list) else accounts
    message = strip_unsafe_input(message.strip(), session)
    account.msg("|m[Help reply from Staff]|n %s" % message)
    msg_func("You replied privately to |w%s|n: %s" % (account.key, message))
    return True


class CmdHelpReply(Command):
    """Staff only: send a private reply to one player on the Help channel. Usage: xhelpreply <account> <message>"""
    key = "xhelpreply"
    locks = "cmd:perm(Builder)"
    help_category = "Channels"

    def func(self):
        caller = getattr(self.caller, "account", self.caller)
        raw = (self.args or "").strip()
        parts = raw.split(None, 1)
        if len(parts) < 2:
            self.msg("Usage: xhelpreply <account> <message>   (e.g. xhelpreply skythia Hello.)")
            return
        _xhelp_staff_reply(caller, parts[0], parts[1], self.msg, self.session)


class CmdHelp(Command):
    """
    Send to the Help channel (you only see your own; staff see all).
    Staff reply privately with: xhelpreply <account> <message>
    """
    key = "xhelp"
    aliases = ["help"]
    locks = "cmd:all()"
    help_category = "Channels"

    def func(self):
        from evennia import search_channel
        from evennia.utils.utils import strip_unsafe_input
        caller = getattr(self.caller, "account", self.caller)
        if not hasattr(caller, "permissions"):
            self.msg("You must be logged in to use the Help channel.")
            return
        raw = (self.args or "").strip()
        channels = search_channel("xhelp") or search_channel("Help")
        if not channels:
            self.msg("Help channel is not available.")
            return
        channel = channels[0]
        if not channel.access(caller, "send"):
            self.msg("You are not allowed to send to the Help channel.")
            return
        if not raw:
            self.msg("Usage: xhelp <message>   (Staff reply privately: xhelpreply <account> <message>)")
            return
        message = strip_unsafe_input(raw, self.session)
        channel.msg(message, senders=caller)


class CmdOocName(Command):
    """
    Set the name shown when you speak on OOC-Chat (xooc). If unset, your account name is used.
    Usage:
      @oocname [name]
    With no args, show current OOC name. With a name, set it.
    """
    key = "@oocname"
    aliases = ["oocname"]
    locks = "cmd:all()"
    help_category = "Channels"

    def func(self):
        caller = getattr(self.caller, "account", self.caller)
        if not hasattr(caller, "db"):
            self.msg("No account.")
            return
        if not self.args or not self.args.strip():
            current = getattr(caller.db, "ooc_display_name", None) or caller.key
            self.msg("Your OOC display name is: |w%s|n. Set it with |w@oocname <name>|n." % current)
            return
        name = self.args.strip()[:64]
        caller.db.ooc_display_name = name
        self.msg("OOC display name set to |w%s|n. You will appear as this on OOC-Chat (xooc)." % name)


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


class CmdTailor(Command):
    """
    Customize a bolt of cloth (name, aliases, desc, tease, coverage) then finalize into clothing.

    Usage:
      @tailor [bolt]                    - show draft status
      @tailor [bolt] name <name>
      @tailor [bolt] aliases <a1> [a2 ...]
      @tailor [bolt] desc <text>         - main desc (when item is looked at)
      @tailor [bolt] worndesc <text>     - worn desc (replaces body parts on look; $N, $P, $S)
      @tailor [bolt] tease <text>        - wearer $N $P $S; target $T $R $U; item $I (see help tease)
      @tailor [bolt] coverage <part> [part ...]  - body parts (lfoot, rshoulder, torso, etc.)
      @tailor [bolt] finalize            - turn bolt into wearable clothing
    """
    key = "@tailor"
    aliases = []
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.bolt_of_cloth.BoltOfCloth"]
    usage_hint = "|w@tailor|n (to make clothing)"

    def func(self):
        caller = self.caller
        from world.tailoring import tailor_parse_args
        bolt_spec, subcmd, value = tailor_parse_args(self.args)

        if not bolt_spec and not subcmd:
            caller.msg("Usage: @tailor [bolt] [name|aliases|desc|worndesc|tease|coverage|finalize] ...")
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
                caller.msg("You have more than one bolt; specify which: @tailor <bolt> ...")
                return
            bolt = bolts[0]

        if not subcmd:
            # Status
            st = bolt.get_draft_status()
            caller.msg("|wDraft status|n for %s:" % bolt.get_display_name(caller))
            caller.msg("  Material: %s" % st.get("material", "bolt of cloth"))
            caller.msg("  Name: %s" % st["name"])
            caller.msg("  Aliases: %s" % (st["aliases"] or "(none)"))
            caller.msg("  Desc: %s" % (st["desc"] or "(none)"))
            caller.msg("  Worn: %s" % (st["worn_desc"] or "(none)"))
            caller.msg("  Tease: %s" % (st["tease"] or "(none)"))
            caller.msg("  Coverage: %s" % (st["covered_parts"] or "(none)"))
            return

        if subcmd == "name":
            if not value:
                caller.msg("Usage: @tailor [bolt] name <name>")
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
            from world.tailoring import finalize_bolt_to_clothing
            clothing, msg = finalize_bolt_to_clothing(bolt, caller)
            caller.msg(msg)
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
      @describe_bodypart <body part> = <text>
      @describe_bodypart head = scarred and crooked
      @descpart lshoulder = $S has an old burn mark on $p shoulder

    Body parts (head to feet): head, face, neck, lshoulder, rshoulder, torso, back,
    abdomen, larm, rarm, lhand, rhand, groin, lthigh, rthigh, lfoot, rfoot
    """
    key = "@describe_bodypart"
    aliases = ["@descpart"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not hasattr(caller, "get_body_descriptions"):
            caller.msg("You cannot set body descriptions.")
            return
        if not self.args or "=" not in self.args:
            caller.msg("Usage: @describe_bodypart <body part> = <text>")
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


class CmdDescribeMeAs(Command):
    """
    Set the short "describe me as" line shown when someone looks at you (first line after your name).

    Usage:
      @dmas              - show your current general description
      @dmas = <text>     - set it (e.g. @dmas = A grizzled veteran with a permanent scowl.)
    """
    key = "@dmas"
    aliases = ["@describe me as", "@describe_me_as"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not hasattr(caller, "db"):
            return
        args = (self.args or "").strip()
        if "=" in args:
            _, _, rest = args.partition("=")
            rest = rest.strip()
            caller.db.general_desc = rest if rest else "This is a character."
            if rest:
                caller.msg("When someone looks at you, they will see: |w%s|n" % rest)
            else:
                caller.msg("Reset to default: |wThis is a character.|n")
            return
        current = getattr(caller.db, "general_desc", None) or "This is a character."
        caller.msg("|wYour general description|n (the first line when someone looks at you):")
        caller.msg("  %s" % current)
        caller.msg("To change: |w@dmas = <text>|n")


class CmdVoice(Command):
    """
    Set the optional voice description shown rarely when you speak (say/emote), based on listeners' perception.

    Usage:
      @voice           - show your current voice setting
      @voice = <text>  - set it (e.g. @voice = British accented). Affixed with " voice" automatically.
      @voice clear     - clear your voice (stop showing)
    """
    key = "@voice"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not hasattr(caller, "db"):
            return
        args = (self.args or "").strip()
        if args.lower() == "clear" or args == "" and "=" not in (self.args or ""):
            if args.lower() == "clear":
                caller.db.voice = ""
                caller.msg("Voice cleared. Your speech will no longer show a voice description.")
                return
            current = getattr(caller.db, "voice", None) or ""
            if current:
                caller.msg("|wYour voice|n (shown rarely to listeners who pass a perception check): |w%s voice|n" % current)
            else:
                caller.msg("|wYour voice|n: not set. Use |w@voice = <text>|n (e.g. @voice = British accented).")
            return
        if "=" in args:
            _, _, rest = args.partition("=")
            rest = rest.strip()
            caller.db.voice = rest
            if rest:
                caller.msg("Voice set. Listeners may occasionally see you |wspeaking in a %s voice|n." % rest)
            else:
                caller.msg("Voice cleared.")
            return
        current = getattr(caller.db, "voice", None) or ""
        if current:
            caller.msg("|wYour voice|n: |w%s voice|n" % current)
        else:
            caller.msg("|wYour voice|n: not set. Use |w@voice = <text>|n.")


class CmdBody(Command):
    """
    List all body parts and their current descriptions (head to feet).

    Usage:
      @body
    """
    key = "@body"
    help_category = "General"

    def func(self):
        from world.medical import BODY_PARTS_HEAD_TO_FEET
        caller = self.caller
        if not hasattr(caller, "db") or not hasattr(caller.db, "body_descriptions"):
            caller.msg("You cannot view body descriptions.")
            return
        # Show raw descriptions you set, not clothing-overridden (look uses effective desc)
        parts = caller.db.body_descriptions or {}
        caller.msg("|wYour body part descriptions|n (use |w@describe_bodypart <part> = <text>|n to set)")
        caller.msg("")
        for part in BODY_PARTS_HEAD_TO_FEET:
            text = (parts.get(part) or "").strip()
            if text:
                caller.msg(f"  |w{part}|n: {text}")
            else:
                caller.msg(f"  |w{part}|n: |x(not set)|n")


class CmdSdesc(Command):
    """
    View or customize your short description (the phrase in parentheses next to your name in the room).

    Usage:
      @sdesc                    - show your current sdesc and gender term
      @sdesc customize          - list choices for your gender; pick by number
      @sdesc set <term>         - set the gender term (e.g. @sdesc set lad, @sdesc set bloke)
      @sdesc custom <word>      - request a custom one-word term (staff approval required; max 15 chars)
    """
    key = "@sdesc"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.sdesc import get_short_desc, get_gender_term, get_gender_terms_list, _article_for
        from world.staff_pending import add_pending, get_pending
        caller = self.caller
        args = (self.args or "").strip().lower()
        # sdesc custom <word> - submit for staff approval
        if args.startswith("custom "):
            word = args[6:].strip()
            if not word:
                caller.msg("Usage: @sdesc custom <word>")
                caller.msg("Request a custom one-word gender term (max 15 characters). Staff must approve.")
                return
            if len(word) > 15:
                caller.msg("Custom term must be 15 characters or fewer.")
                return
            if len(word.split()) != 1:
                caller.msg("Custom term must be a single word.")
                return
            # One pending sdesc_gender_term per character
            for job in get_pending("sdesc_gender_term"):
                if job.get("requester_id") == getattr(caller, "id", None) or job.get("requester_id") == getattr(caller, "dbref", None):
                    caller.msg("You already have a pending custom term request. Wait for staff to approve or deny it.")
                    return
            job_id, ok = add_pending("sdesc_gender_term", caller, {"term": word})
            if not ok:
                caller.msg("The approval queue is unavailable. Try again later.")
                return
            caller.msg("|gYour request for the custom sdesc term |w%s|g has been submitted for staff approval. You will be notified when it is approved or denied.|n" % word)
            return
        # sdesc set <term>
        if args.startswith("set "):
            term = args[4:].strip()
            allowed = get_gender_terms_list(caller)
            if not term:
                caller.msg("Usage: @sdesc set <term>")
                caller.msg("Options: %s" % ", ".join(allowed))
                return
            if term not in [t.lower() for t in allowed]:
                caller.msg("That term isn't valid for your gender. Use |w@sdesc customize|n to see options.")
                return
            caller.db.sdesc_gender_term = term
            caller.db.sdesc_gender_term_custom = False  # clear custom flag when picking from list
            caller.msg("Your short description will now use |w%s|n (e.g. \"a rangy %s\")." % (term, term))
            return
        # sdesc customize: show numbered list
        if args == "customize" or args == "customise":
            allowed = get_gender_terms_list(caller)
            current = get_gender_term(caller)
            caller.msg("|wCurrent term:|n %s" % current)
            caller.msg("")
            caller.msg("|wChoose a term (use |w@sdesc set <term>|n):|n")
            for i, t in enumerate(allowed, 1):
                mark = " |y(current)|n" if t.lower() == current else ""
                caller.msg("  %2d: %s%s" % (i, t, mark))
            caller.msg("")
            caller.msg("Or request a custom one-word term (staff approval required, max 15 chars): |w@sdesc custom <word>|n")
            return
        # sdesc (no args): show current sdesc and term
        full = get_short_desc(caller, caller)
        current_term = get_gender_term(caller)
        caller.msg("|wYour short description:|n")
        caller.msg("  %s" % full)
        caller.msg("")
        article = _article_for(current_term)
        caller.msg("|wCurrently appearing as|n %s %s." % (article, current_term))
        caller.msg("Use |w@sdesc customize|n to see options, |w@sdesc set <term>|n to change, or |w@sdesc custom <word>|n to request a custom term.")


class CmdPending(Command):
    """
    View and resolve the staff pending-approval queue (custom sdesc terms, etc.).
    Use @pending so it is not overridden by the staff_pending channel nick.

    Usage:
      @pending              - list all pending jobs
      @pending approve <id> - approve (id = short id from channel, e.g. b841ccfc)
      @pending deny <id>     - deny
    """
    key = "@pending"
    aliases = ["staffpending", "approvals"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff"

    def func(self):
        from world.staff_pending import get_pending, get_by_id, resolve, _format_job_summary
        args = (self.args or "").strip().split()
        if len(args) >= 2 and args[0].lower() in ("approve", "deny"):
            action = args[0].lower()
            job_id = args[1].strip()
            if not job_id:
                self.caller.msg("Usage: @pending %s <id>   (id = short id from channel, e.g. b841ccfc)" % action)
                return
            success, msg = resolve(job_id, approved=(action == "approve"), staff_member=self.caller)
            self.caller.msg(msg)
            return
        pending = get_pending()
        if not pending:
            self.caller.msg("No pending approval requests.")
            return
        self.caller.msg("|wPending approval requests:|n")
        for job in pending:
            summary = _format_job_summary(job)
            if summary:
                self.caller.msg("  " + summary)
        self.caller.msg("Use |w@pending approve <id>|n or |w@pending deny <id>|n (id = short id from channel).")


class CmdLookPlace(Command):
    """
    Set how you appear in the room when someone looks (e.g. "standing here", "sitting by the fire").
    You can use tokens $N (your name), $P/$p (possessive), $S/$s (subject). See help tokens.

    Usage:
      @lp <text>
      @look_place <text>
      @lp                    (show current)
    """
    key = "@lp"
    aliases = ["@look_place", "@standing", "@roompose"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = self.args.strip()
        if not args:
            current = getattr(caller.db, "room_pose", None) or "standing here"
            caller.msg(f"You appear in the room as: |w{current}|n.")
            caller.msg("Use |w@lp <text>|n to change it (e.g. @lp leaning against the wall).")
            return
        caller.db.room_pose = args
        pose = args.rstrip(".")
        caller.msg(f"When people look here, they will see: |w{caller.name} is {pose}.|n")


class CmdSleepPlace(Command):
    """
    Set how you appear when logged off (look line) and/or the message the room sees when you log off.
    Use $N $P $S in the text. See help tokens.

    Usage:
      @sp                         - show current appearance and log-off message
      @sp <text>                   - set how you appear when logged off (e.g. "sleeping here")
      @sp msg <text>               - set the message the room sees when you log off (e.g. "$N falls asleep.")
    """
    key = "@sp"
    aliases = ["@sleep place", "@sleep_place", "@sleepplace", "@logout_pose"]
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
            caller.msg("Use |w@sp <text>|n to set how you appear when logged off.")
            caller.msg("Use |w@sp msg <text>|n to set the message the room sees when you log off.")
            return
        # @sp msg <text> or @sp message <text> -> set fall_asleep_message only
        if args.lower().startswith("msg ") or args.lower().startswith("message "):
            prefix = "msg " if args.lower().startswith("msg ") else "message "
            text = args[len(prefix):].strip()
            caller.db.fall_asleep_message = text if text else "$N falls asleep."
            caller.msg(f"When you log off, the room will see: |w{caller.db.fall_asleep_message}|n")
            return
        # @sp <text> -> set sleep_place only (how you appear when logged off)
        caller.db.sleep_place = args
        caller.msg(f"When logged off, others will see you as: |w{caller.name} is {args.rstrip('.')}.|n")


class CmdWakeMsg(Command):
    """
    Set the message the room sees when you log on (e.g. "wakes up").
    Use $N for your name. See help tokens.

    Usage:
      @wakemsg <text>
      @wakemsg                 (show current)
    """
    key = "@wakemsg"
    aliases = ["@wake_up", "@wakeupmsg", "@loginmsg"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = self.args.strip()
        if not args:
            current = getattr(caller.db, "wake_up_message", None) or "$N wakes up."
            caller.msg(f"When you log on, the room sees: |w{current}|n")
            caller.msg("Use |w@wakemsg <text>|n (e.g. @wakemsg $N stirs and opens $p eyes.).")
            return
        caller.db.wake_up_message = args
        caller.msg(f"Set. When you log on, the room will see: |w{args}|n")


class CmdFlatlineMsg(Command):
    """
    Set the message the room sees when you fall flatlined (dying). Use {name} for your name.

    Usage:
      @flatlinemsg <text>
      @flatlinemsg              (show current; clear to use default)
    """
    key = "@flatlinemsg"
    aliases = ["@flatline", "@deathmsg", "@dyingmsg"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = self.args.strip()
        if not args:
            current = getattr(caller.db, "flatline_room_msg", None)
            if current:
                caller.msg(f"When you flatline, the room will see: |w{current}|n")
                caller.msg("Use |w@flatlinemsg <text>|n to change, or |w@flatlinemsg default|n to clear and use the default.")
            else:
                from world.death import DEFAULT_FLATLINE_ROOM_MSG
                caller.msg(f"Currently using the default: |w{DEFAULT_FLATLINE_ROOM_MSG}|n")
                caller.msg("Use |w@flatlinemsg <text>|n to customize (use {{name}} for your name).")
            return
        if args.lower() == "default":
            if hasattr(caller.db, "flatline_room_msg"):
                del caller.db.flatline_room_msg
            caller.msg("Cleared. The default flatline message will be used.")
            return
        caller.db.flatline_room_msg = args
        caller.msg(f"Set. When you flatline, the room will see: |w{args}|n")


class CmdSetPlace(Command):
    """
    Set how an object/item appears in the room when someone looks (e.g. "on the ground", "leaning against the wall").
    Only works on items and objects—you cannot set the place for characters (they use |w@lp|n).

    Usage:
      @setplace <item> = <text>
      @setplace <item>     (show current; clear with empty text)
    """
    key = "@setplace"
    aliases = []
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from evennia import DefaultCharacter
        caller = self.caller
        args = self.args.strip()
        if not args:
            caller.msg("Usage: |w@setplace <item> = <text>|n (e.g. @setplace knife = lying in a pool of blood)")
            return
        if "=" in args:
            raw_name, _, text = args.partition("=")
            item_name = raw_name.strip()
            text = text.strip()
        else:
            item_name = args
            text = None
        if not item_name:
            caller.msg("Name an item: |w@setplace <item> = <text>|n")
            return
        location = caller.location
        if not location:
            caller.msg("You are not in a room.")
            return
        obj = caller.search(item_name, location=location)
        if not obj:
            return
        if isinstance(obj, DefaultCharacter):
            caller.msg("You can only set the place for objects and items, not for characters. Characters use |w@lp|n.")
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
            caller.msg("To change: |w@setplace {name} = <text>|n. To clear back to default: |w@setplace {name} = |n".format(name=obj.get_display_name(caller)))
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
    key = "@pronoun"
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
    room_line = None  # one canonical third-person line for cameras

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
            # Optional voice tag in quoted speech (perception check, rare)
            try:
                from world.voice import get_voice_phrase, get_speaking_tag, voice_perception_check
                if get_voice_phrase(caller) and voice_perception_check(viewer, caller) and '"' in full_body:
                    idx = full_body.index('"')
                    full_body = full_body[: idx + 1] + get_speaking_tag(caller) + full_body[idx + 1 :]
            except Exception:
                pass
            if starts_with_comma:
                pronoun_key = getattr(caller.db, "pronoun", "neutral")
                full_body = replace_first_pronoun_with_name(full_body, pronoun_key, emitter_name)
                msg = full_body
            else:
                msg = format_emote_message(emitter_name, full_body)
            if debug_lines is not None:
                debug_lines.append((viewer.get_display_name(viewer), msg))
            viewer.msg(msg)

    # Build one neutral third-person line for cameras (viewer=None so no "you", all names)
    if segments:
        body_parts = []
        for seg in segments:
            third = first_to_third(seg.strip(), caller)
            targets = find_targets_in_text(third, location.contents_get(content_type="character"), caller)
            body_parts.append(build_emote_for_viewer(third, None, targets, emitter_name))
        full_body = ". ".join(p.strip() for p in body_parts if p.strip()).strip()
        full_body = re.sub(r"\.\s+(\w)", lambda m: ". " + m.group(1).upper(), full_body)
        if starts_with_comma:
            pronoun_key = getattr(caller.db, "pronoun", "neutral")
            full_body = replace_first_pronoun_with_name(full_body, pronoun_key, emitter_name)
            room_line = (full_body[0].upper() + full_body[1:]) if full_body and full_body[0].islower() else (full_body or "")
        else:
            room_line = format_emote_message(emitter_name, full_body)
    else:
        room_line = None
    if room_line:
        try:
            from typeclasses.broadcast import feed_cameras_in_location
            feed_cameras_in_location(location, room_line)
        except Exception:
            pass

    if debug_lines:
        caller.msg("|w--- Emote debug ---|n")
        for who, line in debug_lines:
            if who == "you":
                caller.msg(f"|yTo you:|n {line}")
            else:
                caller.msg(f"|yTo {who}:|n {line}")
        caller.msg("|w---|n")


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