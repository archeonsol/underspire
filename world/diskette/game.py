"""
Diskette — game state manager.

One DisketteGame instance per active arena interior.
Module-level _BY_PLAYER maps character.id → game for quick lookup.
"""
from __future__ import annotations

from evennia.utils import delay

from world.diskette.physics import DisketteBoard
from world.diskette.renderer import render_board, render_scores


_BY_PLAYER: dict = {}   # char.id → DisketteGame


def get_game_for(char) -> "DisketteGame | None":
    if not char:
        return None
    return _BY_PLAYER.get(char.id)


def start_game(interior, players: list) -> "DisketteGame":
    """Create a fresh game for two players and register it."""
    game = DisketteGame(interior, players)
    for p in players:
        _BY_PLAYER[p.id] = game
    return game


def end_game(game: "DisketteGame"):
    """Remove game from registry."""
    for p in game.players:
        _BY_PLAYER.pop(p.id, None)


def start_practice(interior, player, bot) -> "DisketteGame":
    """Create a practice game against the AI bot and register it."""
    game = DisketteGame(interior, [player, bot], bot=bot)
    _BY_PLAYER[player.id] = game
    return game


class DisketteGame:
    """
    Tracks all state for a Diskette match between two players.

    States:
        waiting     — players present, waiting for 'start game'
        active      — turn timer running, accepting actions
        match_over  — match finished
    """

    def __init__(self, interior, players: list, bot=None):
        self.interior = interior        # DisketteArenaInterior room
        self.players = list(players)    # [p1, p2] — p2 may be a DisketteBot
        self.bot = bot                  # DisketteBot instance or None
        self.scores = {p.id: 0 for p in players}
        self.round_num = 0
        self.turn_num = 0
        self.state = "waiting"
        self.board = None
        self.pending_actions: dict = {}
        self._timer = None
        self._warn_timer = None

    # ── Public interface ──────────────────────────────────────────────────────

    def start_round(self):
        self.round_num += 1
        self.turn_num = 0
        self.board = DisketteBoard(self.players)
        self.pending_actions = {}
        self.state = "active"
        self._broadcast(f"\n|c── Round {self.round_num} begins! ──|n")
        self._broadcast(render_scores(self), stadium=False)
        self._send_board()
        self._broadcast(
            "|wActions:|n throw <dir>  move <dir>  reflect <dir>  pass\n"
            "|wDirections:|n N NE E SE S SW W NW"
        )
        self._start_timer()

    def submit_action(self, player, action: dict):
        """
        Called when a player submits an action this turn.
        action: {"type": "throw"|"move"|"reflect"|"pass", "dir": str|None}
        """
        if self.state != "active":
            player.msg("No active game to submit to.")
            return

        if player.id in self.pending_actions:
            player.msg("You have already submitted an action this turn.")
            return

        self.pending_actions[player.id] = action
        player.msg("|gAction locked in.|n Waiting for opponent...")

        opponent = self._other(player)
        if opponent.id not in self.pending_actions:
            # Notify opponent that the clock is now ticking
            opponent.msg("|yYour opponent has acted.|n")

        if len(self.pending_actions) >= 2:
            self._cancel_timers()
            self.resolve_turn()

    def resolve_turn(self):
        """Run one turn of physics, display result, advance game."""
        if self.state != "active":
            return

        # Fill missing actions as pass
        for p in self.players:
            if p.id not in self.pending_actions:
                self.pending_actions[p.id] = {"type": "pass", "dir": None}

        self.turn_num += 1
        result = self.board.resolve_turn(self.pending_actions)
        self.pending_actions = {}

        # Display: board first (inside only), then narrative (echoed outside)
        self._send_board()
        for line in result.narrative:
            self._broadcast(line)

        if result.hits:
            self._end_round(result.hits)
        else:
            self._start_timer()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _end_round(self, hit_ids: list):
        self.state = "round_over"
        p1, p2 = self.players
        both_hit = len(hit_ids) == 2

        if both_hit:
            self.scores[p1.id] += 1
            self.scores[p2.id] += 1
            self._broadcast("|yDraw! Both players are hit. Each scores a point.|n")
        else:
            loser_id = hit_ids[0]
            winner = p1 if loser_id == p2.id else p2
            self.scores[winner.id] += 1
            self._broadcast(f"|g{winner.key} wins the round!|n")

        self._broadcast(render_scores(self))

        winner = self._match_winner()
        if winner:
            self._end_match(winner)
        else:
            # Brief pause then next round
            delay(3, self.start_round)

    def _match_winner(self):
        p1, p2 = self.players
        s1, s2 = self.scores[p1.id], self.scores[p2.id]
        if s1 >= 3 and s1 > s2:
            return p1
        if s2 >= 3 and s2 > s1:
            return p2
        return None

    def _end_match(self, winner):
        self.state = "match_over"
        loser = self._other(winner)
        self._broadcast(f"\n|C{winner.key} wins the match!|n")
        end_game(self)

        # Eject loser from arena after a moment
        def _eject():
            if loser is self.bot:
                return  # bot has no location or db
            if loser and loser.location == self.interior:
                stadium = getattr(self.interior.db, "arena", None)
                stadium = getattr(stadium, "location", None)
                if stadium:
                    loser.move_to(stadium, quiet=True, move_type="teleport")
                    loser.msg("You are escorted out of the arena.")
                    stadium.msg_contents(
                        f"{loser.key} stumbles out of the Diskette Arena."
                    )
            loser.db.in_diskette_arena = None

        delay(2, _eject)

    def _other(self, player):
        p1, p2 = self.players
        return p2 if player.id == p1.id else p1

    def _start_timer(self):
        self._timer = delay(15, self.resolve_turn)
        self._warn_timer = delay(10, self._warn_5s)
        if self.bot:
            self._submit_bot_action()

    def _submit_bot_action(self):
        """Immediately generate and lock in the bot's action for this turn."""
        if self.state != "active" or self.bot.id in self.pending_actions:
            return
        from world.diskette.ai import choose_action
        human = self._other(self.bot)
        action = choose_action(self.board, self.bot.id, human.id)
        self.pending_actions[self.bot.id] = action

    def _cancel_timers(self):
        for t in (self._timer, self._warn_timer):
            if t and not t.called and not t.cancelled:
                try:
                    t.cancel()
                except Exception:
                    pass
        self._timer = None
        self._warn_timer = None

    def _warn_5s(self):
        if self.state != "active":
            return
        for p in self.players:
            if p.id not in self.pending_actions:
                p.msg("|y5 seconds remaining to submit your action.|n")

    def _send_board(self):
        board_text = render_board(self.board)
        self.interior.msg_contents(board_text, stadium=False)

    def _broadcast(self, text, stadium=True):
        self.interior.msg_contents(text, stadium=stadium)
