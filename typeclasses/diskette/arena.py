"""
Diskette Arena — container object + interior room.

DisketteArena         — the object placed in the stadium MatrixNode
DisketteArenaInterior — the Room players move into when they enter
"""
from evennia.utils.create import create_object
from evennia.utils.search import search_tag

from typeclasses.mixins.enterable import EnterableMixin
from typeclasses.objects import Object
from typeclasses.rooms import Room

DISKETTE_INTERIOR_TAG = "diskette_interior"


class DisketteArena(EnterableMixin, Object):
    """
    The arena object. Place this in a MatrixNode stadium room.
    Players enter with: enter diskette arena
    """

    def at_object_creation(self):
        super().at_object_creation()
        self._ensure_interior()

    def _ensure_interior(self):
        # Try to recover existing interior after reload
        if self.db.interior:
            return self.db.interior
        existing = search_tag(DISKETTE_INTERIOR_TAG, category=str(self.id))
        if existing:
            interior = existing[0]
            interior.db.arena = self
            self.db.interior = interior
            return interior
        interior = create_object(
            "typeclasses.diskette.arena.DisketteArenaInterior",
            key=f"Inside {self.key}",
            location=None,
        )
        interior.tags.add(DISKETTE_INTERIOR_TAG, category=str(self.id))
        interior.db.arena = self
        self.db.interior = interior
        return interior

    @property
    def interior(self):
        return self._ensure_interior()

    def return_appearance(self, looker, **kwargs):
        interior = self.interior
        players_inside = [
            obj for obj in (interior.contents if interior else [])
            if obj.has_account
        ]

        from world.diskette.game import get_game_for
        game = get_game_for(players_inside[0]) if players_inside else None

        lines = [f"|w{self.get_display_name(looker)}|n"]
        lines.append("A disc combat arena. Two players, one disc each.")

        if game and game.state == "active":
            p1, p2 = game.players
            s1, s2 = game.scores[p1.id], game.scores[p2.id]
            lines.append(
                f"Status: |cIN PROGRESS|n — Round {game.round_num}  "
                f"[{p1.key}: {s1} | {p2.key}: {s2}]"
            )
        elif len(players_inside) == 2:
            lines.append("Status: |yAwaiting start.|n")
        elif len(players_inside) == 1:
            lines.append(
                f"Status: |y{players_inside[0].key} is waiting for an opponent.|n"
            )
        else:
            lines.append("Status: Empty. (|wenter diskette arena|n to play)")

        if players_inside:
            names = ", ".join(p.key for p in players_inside)
            lines.append(f"Players inside: {names}")

        return "\n".join(lines)

    def at_enter(self, caller):
        """Handle a character entering the arena (called by CmdEnter)."""
        if getattr(caller.db, "in_diskette_arena", None):
            caller.msg("You are already in a Diskette arena. Type |wleave|n to exit.")
            return
        interior = self.interior
        if not interior:
            caller.msg("That arena has no interior. Contact staff.")
            return
        players_inside = [obj for obj in interior.contents if obj.has_account]
        if len(players_inside) >= 2:
            caller.msg("The arena is full. Watch from here.")
            return
        if not caller.move_to(interior, quiet=True, move_type="teleport"):
            caller.msg("You couldn't enter the arena.")
            return
        caller.db.in_diskette_arena = self
        caller.msg(f"You step into {self.key}.")
        if self.location:
            self.location.msg_contents(
                f"{caller.key} enters the Diskette Arena.", exclude=caller
            )


class DisketteArenaInterior(Room):
    """
    The interior room of a Diskette arena. Players enter from the stadium.
    Max 2 players. Game commands are available here.
    Messages are relayed to the exterior stadium (except board renders).
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.desc = (
            "A virtual combat arena — a stark grid suspended in digital void. "
            "The floor is faintly luminescent. Two disc-launch pads glow at opposite ends."
        )
        self.cmdset.add(
            "commands.diskette_cmds.DisketteArenaCmdSet", persistent=True
        )

    def _players(self):
        return [obj for obj in self.contents if obj.has_account]

    def at_object_receive(self, moved_obj, source_location, **kwargs):
        super().at_object_receive(moved_obj, source_location, **kwargs)
        if not moved_obj.has_account:
            return
        players = self._players()
        if len(players) == 2:
            p1, p2 = players
            self.msg_contents(
                f"|w{p1.key}|n vs |w{p2.key}|n — type |wstart game|n to begin.",
                stadium=False,
            )
            arena = self.db.arena
            if arena and arena.location:
                arena.location.msg_contents(
                    f"The Diskette Arena now has two challengers: "
                    f"{p1.key} vs {p2.key}. A match is about to begin."
                )

    def at_object_leave(self, moved_obj, target_location, **kwargs):
        super().at_object_leave(moved_obj, target_location, **kwargs)
        if not moved_obj.has_account:
            return
        moved_obj.db.in_diskette_arena = None

        from world.diskette.game import get_game_for, end_game
        game = get_game_for(moved_obj)
        if not game or game.state not in ("active", "waiting"):
            return

        # Player left mid-game — opponent wins
        game._cancel_timers()
        remaining = [p for p in game.players if p != moved_obj]
        if remaining:
            winner = remaining[0]
            game.scores[winner.id] = max(game.scores.get(winner.id, 0), 3)
            self.msg_contents(
                f"|r{moved_obj.key} has left the arena. {winner.key} wins by forfeit!|n"
            )
        end_game(game)

    def msg_contents(self, text=None, exclude=None, from_obj=None, mapping=None,
                     raise_funcparse_errors=False, stadium=True, **kwargs):
        """Send to interior. If stadium=True (default), also relay to exterior stadium."""
        super().msg_contents(
            text=text,
            exclude=exclude,
            from_obj=from_obj,
            mapping=mapping,
            raise_funcparse_errors=raise_funcparse_errors,
            **kwargs,
        )
        if not stadium:
            return
        arena = self.db.arena
        if not arena:
            return
        exterior = getattr(arena, "location", None)
        if not exterior:
            return
        raw = text if isinstance(text, str) else (
            text[0] if isinstance(text, (tuple, list)) and text else ""
        )
        if raw:
            exterior.msg_contents(raw, exclude=None)

    def return_appearance(self, looker, **kwargs):
        from world.diskette.game import get_game_for
        from world.diskette.renderer import render_board, render_scores

        players = self._players()
        game = get_game_for(looker) if looker else None

        lines = [f"|w{self.get_display_name(looker)}|n"]
        lines.append(self.db.desc or "")

        if game and game.state == "active" and game.board:
            lines.append("")
            lines.append(render_scores(game))
            lines.append(render_board(game.board))
            submitted = game.pending_actions
            waiting_on = [
                p.key for p in game.players if p.id not in submitted
            ]
            if waiting_on:
                lines.append(f"Waiting for: {', '.join(waiting_on)}")
        elif players:
            names = " and ".join(p.key for p in players)
            lines.append(f"\n{names} {'is' if len(players) == 1 else 'are'} here.")
            if len(players) < 2:
                lines.append("Waiting for an opponent. (|wstart game|n when ready)")
            else:
                lines.append("Type |wstart game|n to begin.")
        else:
            lines.append("\nThe arena is empty.")

        return "\n".join(lines)
