"""
Combat commands: CmdAttack, CmdStop, CmdFlee, CmdStance, CmdGrapple, CmdLetGo, CmdResist, CmdExecute, _combat_caller.
"""

from evennia.utils import logger
from commands.base_cmds import Command, _command_character
from world.combat import start_combat_ticker, stop_combat_ticker, _get_combat_target, _combat_display_name


def _combat_caller(cmd_self):
    """Resolve caller to puppeted character when command runs with Account as caller (e.g. from Session cmdset)."""
    caller = cmd_self.caller
    if not getattr(caller.db, "stats", None) and getattr(cmd_self, "session", None):
        try:
            puppet = getattr(cmd_self.session, "puppet", None)
            if puppet:
                return puppet
        except Exception as e:
            logger.log_trace("combat_cmds._combat_caller: %s" % e)
    return caller


class CmdStance(Command):
    """
    Set your combat stance: balanced (default), aggressive (+attack, -defense), or defensive (-attack, +defense).
    Usage: stance [balanced|aggressive|defensive]
    """
    key = "stance"
    aliases = ["combat stance"]
    locks = "cmd:all()"
    help_category = "Combat"
    STANCES = ("balanced", "aggressive", "defensive")

    def func(self):
        caller = _combat_caller(self)
        if not getattr(caller, "db", None) or not hasattr(caller.db, "stats"):
            self.caller.msg("You must be in character to do that.")
            return
        arg = (self.args or "").strip().lower()
        if not arg:
            current = getattr(caller.db, "combat_stance", None) or "balanced"
            caller.msg("Your combat stance is |w{}|n. Use |wstance balanced|n, |wstance aggressive|n, or |wstance defensive|n to change.".format(current))
            return
        if arg not in self.STANCES:
            caller.msg("Stance must be one of: {}.".format(", ".join(self.STANCES)))
            return
        caller.db.combat_stance = arg
        caller.msg("You shift to a |w{}|n stance.".format(arg))


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
                caller.msg(f"|r{_combat_display_name(target, caller)} is already dead.|n")
                return
            if is_flatlined(target):
                tname = _combat_display_name(target, caller)
                caller.msg(f"|r{tname} is down and dying. Use |wexecute {tname}|n to end them.|n")
                return
        except ImportError:
            if getattr(target.db, "current_hp", None) is not None and target.db.current_hp <= 0:
                caller.msg(f"|r{_combat_display_name(target, caller)} is already dead.|n")
                return
        try:
            from world.stamina import is_exhausted
            if is_exhausted(caller):
                caller.msg("You're too tired to fight.")
                return
        except ImportError as e:
            logger.log_trace("combat_cmds.CmdAttack stamina check: %s" % e)
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
            caller.msg(f"|yYou switch targets to {_combat_display_name(target, caller)}.|n")
        start_combat_ticker(caller, target)
        # If target is a creature, set its target to you and start its AI so it fights back
        if getattr(target.db, "is_creature", False):
            target.db.current_target = caller
            try:
                from world.creature_combat import start_creature_ai_ticker
                start_creature_ai_ticker(target)
            except Exception as e:
                logger.log_trace("combat_cmds.CmdAttack creature_combat: %s" % e)


class CmdStop(Command):
    """
    Stops the automated combat sequence.
    Usage: stop attacking [target]
    """
    key = "stop"
    aliases = ["cease", "retreat"]
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        from world.combat import stop_combat_ticker, _get_combat_target

        # No arguments: stop attacking your current combat target, if any.
        if not args:
            current = _get_combat_target(caller)
            if not current:
                caller.msg("You're not in combat.")
                return
            stop_combat_ticker(caller, current)
            return

        # Expect "attacking [name]" if arguments are given.
        if not args.lower().startswith("attacking"):
            caller.msg("Usage: stop attacking [name]")
            return

        # Strip off the word "attacking" and any following whitespace to get an optional name.
        target_name = args[len("attacking"):].strip()

        # "stop attacking" with no name: fall back to current combat target.
        if not target_name:
            current = _get_combat_target(caller)
            if not current:
                caller.msg("You're not in combat.")
                return
            stop_combat_ticker(caller, current)
            return

        # "stop attacking <name>": look up that target and stop only your attacks on them.
        target = caller.search(target_name)
        if not target:
            return

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
            if loc and hasattr(loc, "contents_get"):
                for v in loc.contents_get(content_type="character"):
                    if v in (caller, opponent):
                        continue
                    v.msg("%s tries to flee but %s keeps them in the fight." % (_combat_display_name(caller, v), _combat_display_name(opponent, v)))
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
            if dest and hasattr(dest, "contents_get"):
                for v in dest.contents_get(content_type="character"):
                    if v in (caller, victim):
                        continue
                    v.msg("%s is dragged in by %s." % (_combat_display_name(victim, v), _combat_display_name(caller, v)))
        caller.msg("|gYou break away and flee %s!|n" % dir_name)
        opponent.msg("|r%s breaks away and flees %s!|n" % (_combat_display_name(caller, opponent), dir_name))
        if loc and hasattr(loc, "contents_get"):
            for v in loc.contents_get(content_type="character"):
                if v == caller:
                    continue
                v.msg("%s breaks away and flees %s!" % (_combat_display_name(caller, v), dir_name))
        if dest and hasattr(dest, "contents_get"):
            for v in dest.contents_get(content_type="character"):
                if v == caller:
                    continue
                v.msg("%s bursts in from %s, out of breath." % (_combat_display_name(caller, v), dir_name))


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
                if caller.location and hasattr(caller.location, "contents_get"):
                    for v in caller.location.contents_get(content_type="character"):
                        if v in (caller, victim):
                            continue
                        v.msg("%s releases %s." % (_combat_display_name(caller, v), _combat_display_name(victim, v)))
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
        if freed and caller.location and hasattr(caller.location, "contents_get"):
            for v in caller.location.contents_get(content_type="character"):
                if v == caller or (grappler and v == grappler):
                    continue
                if grappler:
                    v.msg("%s breaks free of %s's grasp!" % (_combat_display_name(caller, v), _combat_display_name(grappler, v)))
                else:
                    v.msg("%s breaks free!" % _combat_display_name(caller, v))


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
