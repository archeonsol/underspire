"""
Diskette — arena entry command (global) and in-game commands (room CmdSet).
"""
from evennia import CmdSet
from commands.command import Command
from world.diskette.physics import DIRS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_game(caller):
    from world.diskette.game import get_game_for
    return get_game_for(caller)


def _validate_dir(caller, raw):
    """Return normalized direction string or None (with error message sent)."""
    if not raw:
        caller.msg("You must specify a direction. (N NE E SE S SW W NW)")
        return None
    d = raw.strip().upper()
    if d not in DIRS:
        caller.msg(f"Unknown direction '{raw}'. Use: N NE E SE S SW W NW")
        return None
    return d


# ── In-arena game commands ────────────────────────────────────────────────────

class CmdDisketteThrow(Command):
    """
    Throw your disc in a direction.
    Usage: throw <dir>
    You are unarmed until your disc returns to you.
    """
    key = "throw"
    locks = "cmd:all()"
    help_category = "Diskette"

    def func(self):
        game = _get_game(self.caller)
        if not game or game.state != "active":
            self.caller.msg("There is no active game.")
            return
        d = _validate_dir(self.caller, self.args.strip())
        if not d:
            return
        game.submit_action(self.caller, {"type": "throw", "dir": d})


class CmdDisketteMove(Command):
    """
    Move one tile in a direction.
    Usage: move <dir>
    """
    key = "move"
    locks = "cmd:all()"
    help_category = "Diskette"

    def func(self):
        game = _get_game(self.caller)
        if not game or game.state != "active":
            self.caller.msg("There is no active game.")
            return
        d = _validate_dir(self.caller, self.args.strip())
        if not d:
            return
        game.submit_action(self.caller, {"type": "move", "dir": d})


class CmdDisketteReflect(Command):
    """
    Reflect an incoming disc in a direction (requires your disc).
    Usage: reflect <dir>
    You must be armed and the disc must land on your tile this turn.
    Redirects the disc — purely defensive, cannot hit opponent directly.
    """
    key = "reflect"
    locks = "cmd:all()"
    help_category = "Diskette"

    def func(self):
        game = _get_game(self.caller)
        if not game or game.state != "active":
            self.caller.msg("There is no active game.")
            return
        d = _validate_dir(self.caller, self.args.strip())
        if not d:
            return
        game.submit_action(self.caller, {"type": "reflect", "dir": d})


class CmdDiskettePass(Command):
    """
    Take no action this turn.
    Usage: pass
    """
    key = "pass"
    locks = "cmd:all()"
    help_category = "Diskette"

    def func(self):
        game = _get_game(self.caller)
        if not game or game.state != "active":
            self.caller.msg("There is no active game.")
            return
        game.submit_action(self.caller, {"type": "pass", "dir": None})


class CmdDisketteStart(Command):
    """
    Start a Diskette match. Both players must be in the arena.
    Usage: start game
    """
    key = "start game"
    locks = "cmd:all()"
    help_category = "Diskette"

    def func(self):
        interior = self.caller.location
        players = [obj for obj in interior.contents if obj.has_account]

        if len(players) < 2:
            self.caller.msg("Need two players to start a match.")
            return

        game = _get_game(self.caller)
        if game and game.state == "active":
            self.caller.msg("A match is already in progress.")
            return

        from world.diskette.game import start_game
        game = start_game(interior, players[:2])
        game.start_round()


class CmdDiskettePractice(Command):
    """
    Start a practice match against the AI. Must be alone in the arena.
    Usage: practice
    The AI plays randomly — good for learning the mechanics.
    """
    key = "practice"
    locks = "cmd:all()"
    help_category = "Diskette"

    def func(self):
        interior = self.caller.location
        players = [obj for obj in interior.contents if obj.has_account]

        if len(players) != 1:
            self.caller.msg(
                "Practice mode is for solo players only. "
                "Use |wstart game|n when two players are present."
            )
            return

        game = _get_game(self.caller)
        if game and game.state == "active":
            self.caller.msg("A match is already in progress.")
            return

        from world.diskette.game import start_practice
        from world.diskette.ai import DisketteBot
        bot = DisketteBot()
        game = start_practice(interior, self.caller, bot)
        game.start_round()


class CmdDisketteLeave(Command):
    """
    Leave the Diskette arena.
    Usage: leave
    Leaving during an active match forfeits the match.
    """
    key = "leave"
    locks = "cmd:all()"
    help_category = "Diskette"

    def func(self):
        caller = self.caller
        interior = caller.location
        arena = getattr(interior.db, "arena", None)
        if not arena:
            caller.msg("You're not inside an arena.")
            return
        dest = getattr(arena, "location", None)
        if not dest:
            caller.msg("The arena has no exterior. Contact staff.")
            return
        if not caller.move_to(dest, quiet=True, move_type="teleport"):
            caller.msg("You couldn't leave.")
            return
        caller.msg("You step out of the arena.")
        dest.msg_contents(f"{caller.key} steps out of the Diskette Arena.", exclude=caller)
        # at_object_leave on the interior handles game forfeit + cleanup


# ── CmdSet added to the interior room ────────────────────────────────────────

class DisketteArenaCmdSet(CmdSet):
    key = "DisketteArenaCmdSet"
    priority = 110
    mergetype = "Union"

    def at_cmdset_creation(self):
        self.add(CmdDisketteThrow())
        self.add(CmdDisketteMove())
        self.add(CmdDisketteReflect())
        self.add(CmdDiskettePass())
        self.add(CmdDisketteStart())
        self.add(CmdDiskettePractice())
        self.add(CmdDisketteLeave())


# ── Global enter command ──────────────────────────────────────────────────────

class CmdEnterDisketteArena(Command):
    """
    Enter a Diskette arena to play disc combat.
    Usage: enter <arena name>
    Max two players. Type 'start game' once both are inside.
    """
    key = "enter"
    locks = "cmd:all()"
    help_category = "Diskette"
    usage_typeclasses = ["typeclasses.diskette.arena.DisketteArena"]
    usage_hint = "|wenter|n <arena> (to enter the disc arena)"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Enter what? Usage: enter <arena name>")
            return

        # Block if already in an arena
        if getattr(caller.db, "in_diskette_arena", None):
            caller.msg("You are already in a Diskette arena. Type |wleave|n to exit.")
            return

        arena = caller.search(self.args.strip(), location=caller.location)
        if not arena:
            return

        try:
            from typeclasses.diskette.arena import DisketteArena
        except ImportError:
            caller.msg("Diskette system unavailable.")
            return

        if not isinstance(arena, DisketteArena):
            caller.msg("That is not a Diskette arena.")
            return

        interior = arena.interior
        if not interior:
            caller.msg("That arena has no interior. Contact staff.")
            return

        # Check capacity
        players_inside = [obj for obj in interior.contents if obj.has_account]
        if len(players_inside) >= 2:
            caller.msg("The arena is full. Watch from here.")
            return

        if not caller.move_to(interior, quiet=True, move_type="teleport"):
            caller.msg("You couldn't enter the arena.")
            return

        caller.db.in_diskette_arena = arena
        caller.msg(f"You step into {arena.key}.")
        if arena.location:
            arena.location.msg_contents(
                f"{caller.key} enters the Diskette Arena.", exclude=caller
            )
