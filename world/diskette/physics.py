"""
Diskette — disc physics.

Grid: columns A–F (x 0–5), rows 1–6 (y 0–5).
Tile notation: "B3" → col=1, row=2.

Resolution order per turn:
  1. Move discs (raw, may go out of bounds)
  2. Player move actions
  3. Auto-catch first pass (own disc on player tile — works even if moved)
  4. Throw actions
  5. Reflect actions
  6. Player hit check
  7. Disc-disc collision
  8. Edge bounce
  9. Final kill check (hits produced by steps 7–8)
 10. Final auto-catch (own disc on tile after physics)
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field

COLS = "ABCDEF"   # index = x
ROWS = "123456"   # index = y

DIRS = {
    "N":  (0, -1),
    "NE": (1, -1),
    "E":  (1,  0),
    "SE": (1,  1),
    "S":  (0,  1),
    "SW": (-1,  1),
    "W":  (-1,  0),
    "NW": (-1, -1),
}

# Starting positions: (col_idx, row_idx)
START_P1 = (1, 0)   # B1
START_P2 = (4, 5)   # E6


def tile_name(col: int, row: int) -> str:
    return f"{COLS[col]}{ROWS[row]}"


def parse_tile(name: str):
    """'B3' → (1, 2)"""
    col = COLS.index(name[0].upper())
    row = ROWS.index(name[1])
    return col, row


def in_bounds(col: int, row: int) -> bool:
    return 0 <= col <= 5 and 0 <= row <= 5


def raw_step(pos: tuple, heading: tuple) -> tuple:
    """One step without bounds checking."""
    return (pos[0] + heading[0], pos[1] + heading[1])


def apply_edge_bounce(pos: tuple, heading: tuple) -> tuple[tuple, tuple, str | None]:
    """
    Given a raw (possibly out-of-bounds) position, return the clamped
    in-bounds position, reflected heading, and wall label (or None if in bounds).

    Corner (out of bounds on both axes) → reverse completely.
    Single-axis wall → flip that component.
    Already in bounds → no change.
    """
    col, row = pos
    dx, dy = heading

    out_x = not (0 <= col <= 5)
    out_y = not (0 <= row <= 5)

    if out_x and out_y:
        wall = "corner"
        col = max(0, min(5, col))
        row = max(0, min(5, row))
        return (col, row), (-dx, -dy), wall
    if out_x:
        wall = "west wall" if col < 0 else "east wall"
        col = max(0, min(5, col))
        return (col, row), (-dx, dy), wall
    if out_y:
        wall = "north wall" if row < 0 else "south wall"
        row = max(0, min(5, row))
        return (col, row), (dx, -dy), wall
    return pos, heading, None


def resolve_disc_disc(h1: tuple, h2: tuple) -> tuple[tuple, tuple]:
    """
    Two discs collide at the same position.
    Head-on (h1 == -h2): both reverse.
    Otherwise: swap headings (standard billiard reflection).
    """
    if h1 == (-h2[0], -h2[1]):
        return (-h1[0], -h1[1]), (-h2[0], -h2[1])
    return h2, h1


@dataclass
class DiscState:
    in_flight: bool = False
    pos: tuple = (0, 0)      # (col, row) — only meaningful if in_flight
    heading: tuple = (0, 0)  # (dx, dy)


@dataclass
class TurnResult:
    hits: list = field(default_factory=list)        # player ids who were hit
    catches: list = field(default_factory=list)     # player ids who auto-caught
    reflects: list = field(default_factory=list)    # player ids who reflected
    disc_collision: bool = False
    edge_bounces: list = field(default_factory=list)
    narrative: list = field(default_factory=list)


class DisketteBoard:
    """
    Manages all mutable game state for one round.

    players: [p1, p2]  (character objects)
    """

    def __init__(self, players: list):
        self.players = players
        self.positions = {
            players[0].id: START_P1,
            players[1].id: START_P2,
        }
        self.discs = {
            players[0].id: DiscState(in_flight=False),
            players[1].id: DiscState(in_flight=False),
        }
        # Whether each player is armed (disc in hand)
        self.armed = {
            players[0].id: True,
            players[1].id: True,
        }

    def _other(self, player_id):
        p1, p2 = self.players
        return p2 if player_id == p1.id else p1

    def resolve_turn(self, actions: dict) -> TurnResult:
        """
        actions: {player.id: {"type": "throw"|"move"|"reflect"|"pass", "dir": str|None}}
        Missing entry treated as pass.
        Returns TurnResult with narrative list.
        """
        result = TurnResult()
        newly_thrown: set = set()

        def action_for(pid):
            return actions.get(pid) or {"type": "pass", "dir": None}

        p1, p2 = self.players

        # ── 1. Move discs (raw) ───────────────────────────────────────────────
        for pid in (p1.id, p2.id):
            disc = self.discs[pid]
            if disc.in_flight:
                disc.pos = raw_step(disc.pos, disc.heading)

        # ── 2. Player move actions ────────────────────────────────────────────
        intended: dict = {}  # pid -> (nx, ny, dname)
        for player in self.players:
            act = action_for(player.id)
            if act["type"] == "move" and act["dir"]:
                dname = act["dir"].upper()
                if dname not in DIRS:
                    player.msg(f"|rUnknown direction '{act['dir']}'.|n")
                    continue
                dx, dy = DIRS[dname]
                cx, cy = self.positions[player.id]
                nx, ny = cx + dx, cy + dy
                if in_bounds(nx, ny):
                    intended[player.id] = (nx, ny, dname)
                else:
                    result.narrative.append(f"{player.key} tries to move {dname} but the wall stops them.")

        # Collision: both players end up on the same tile → random winner
        def dest(pid):
            return intended[pid][:2] if pid in intended else self.positions[pid]

        if dest(p1.id) == dest(p2.id):
            winner, loser = random.choice([(p1, p2), (p2, p1)])
            intended.pop(loser.id, None)
            flavor = random.choice([
                f"body-checks {loser.key} out of the way",
                f"bullies {loser.key} back",
                f"shoulder-checks {loser.key} aside",
            ])
            result.narrative.append(f"{winner.key} {flavor}!")

        for player in self.players:
            if player.id in intended:
                nx, ny, dname = intended[player.id]
                self.positions[player.id] = (nx, ny)
                result.narrative.append(f"{player.key} moves {dname}.")

        # ── 3. Auto-catch (first pass) ────────────────────────────────────────
        for player in self.players:
            disc = self.discs[player.id]
            if disc.in_flight and disc.pos == self.positions[player.id]:
                disc.in_flight = False
                self.armed[player.id] = True
                result.catches.append(player.id)
                result.narrative.append(f"{player.key} catches their disc.")

        # ── 4. Throw actions ──────────────────────────────────────────────────
        for player in self.players:
            act = action_for(player.id)
            if act["type"] != "throw":
                continue
            if not self.armed[player.id]:
                result.narrative.append(f"{player.key} has no disc to throw.")
                continue
            dname = act["dir"].upper() if act.get("dir") else None
            if not dname or dname not in DIRS:
                result.narrative.append(f"{player.key}'s throw has no valid direction.")
                continue
            dx, dy = DIRS[dname]
            self.armed[player.id] = False
            disc = self.discs[player.id]
            disc.in_flight = True
            disc.pos = raw_step(self.positions[player.id], (dx, dy))
            disc.heading = (dx, dy)
            newly_thrown.add(player.id)
            result.narrative.append(f"{player.key} throws their disc {dname}.")

        # ── 5. Reflect actions ────────────────────────────────────────────────
        for player in self.players:
            act = action_for(player.id)
            if act["type"] != "reflect":
                continue
            opponent = self._other(player.id)
            enemy_disc = self.discs[opponent.id]
            if not enemy_disc.in_flight:
                # No disc incoming — wasted turn, nothing happens
                continue
            if enemy_disc.pos != self.positions[player.id]:
                # Disc not on player's tile this turn — wasted turn
                continue
            if not self.armed[player.id]:
                # Unarmed — will be hit in step 6
                continue
            dname = act["dir"].upper() if act.get("dir") else None
            if not dname or dname not in DIRS:
                result.narrative.append(f"{player.key} fumbles the reflect — bad direction.")
                # Treat as failure; hit resolved in step 6
                continue
            # Redirect and immediately advance
            new_heading = DIRS[dname]
            enemy_disc.heading = new_heading
            enemy_disc.pos = raw_step(enemy_disc.pos, new_heading)
            result.reflects.append(player.id)
            result.narrative.append(
                f"{player.key} reflects the enemy disc {dname}!"
            )

        # ── 6. Player hit check ───────────────────────────────────────────────
        for player in self.players:
            opponent = self._other(player.id)
            enemy_disc = self.discs[opponent.id]
            if not enemy_disc.in_flight:
                continue
            if enemy_disc.pos != self.positions[player.id]:
                continue
            # Was this resolved by a successful reflect?
            if player.id in result.reflects:
                continue
            result.hits.append(player.id)
            result.narrative.append(f"|r{player.key} is hit by {opponent.key}'s disc!|n")

        # ── 7. Disc-disc collision ────────────────────────────────────────────
        d1 = self.discs[p1.id]
        d2 = self.discs[p2.id]
        if d1.in_flight and d2.in_flight and d1.pos == d2.pos:
            new_h1, new_h2 = resolve_disc_disc(d1.heading, d2.heading)
            d1.heading = new_h1
            d2.heading = new_h2
            result.disc_collision = True
            result.narrative.append("The two discs collide!")

        # ── 8. Edge bounce ────────────────────────────────────────────────────
        for player in self.players:
            disc = self.discs[player.id]
            if not disc.in_flight:
                continue
            if not in_bounds(*disc.pos):
                new_pos, new_heading, wall = apply_edge_bounce(disc.pos, disc.heading)
                result.edge_bounces.append(player.id)
                disc.pos = new_pos
                disc.heading = new_heading
                result.narrative.append(f"{player.key}'s disc bounces off the {wall}.")

        # ── 9. Final kill check ───────────────────────────────────────────────
        for player in self.players:
            if player.id in result.hits:
                continue  # already counted
            opponent = self._other(player.id)
            enemy_disc = self.discs[opponent.id]
            if not enemy_disc.in_flight:
                continue
            if enemy_disc.pos != self.positions[player.id]:
                continue
            if player.id in result.reflects:
                continue
            result.hits.append(player.id)
            result.narrative.append(f"|r{player.key} is hit by {opponent.key}'s disc!|n")

        # ── 10. Final auto-catch ──────────────────────────────────────────────
        for player in self.players:
            if player.id in result.catches:
                continue  # already caught this turn
            if player.id in newly_thrown:
                continue  # just threw — disc hasn't moved yet, don't catch it back
            disc = self.discs[player.id]
            if disc.in_flight and disc.pos == self.positions[player.id]:
                disc.in_flight = False
                self.armed[player.id] = True
                result.catches.append(player.id)
                result.narrative.append(f"{player.key} catches their disc.")

        return result
