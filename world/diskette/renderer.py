"""
Diskette — ASCII board renderer.

Board layout (columns 1-5 left-to-right, rows A-E top-to-bottom):

     1   2   3   4   5
   ┌───────────────────┐
 A │[_]               │
   │   ·   ·   ·   ·   │
 B │                   │
   │   ·   ·   ·   ·   │
 ...
 E │               ( )│
   └───────────────────┘

Symbols (3 chars each):
  [_]  — player 1, unarmed (disc in flight)
  [x]  — player 1, armed (holding disc)
  ( )  — player 2, unarmed (disc in flight)
  (o)  — player 2, armed (holding disc)
   x   — P1 disc in flight (no player)
   o   — P2 disc in flight (no player)
       — empty (3 spaces)
"""
from world.diskette.physics import DisketteBoard

_ROW_LABELS = "ABCDE"
_COL_LABELS = "12345"

# Interior: 5 cells × 3 chars + 4 separators = 19 chars
_BORDER_TOP    = "   ┌───────────────────┐"
_BORDER_BOTTOM = "   └───────────────────┘"
_SEPARATOR_ROW = "   │   ·   ·   ·   ·   │"
_COL_HEADER    = "     1   2   3   4   5"


def _build_row(cells: list[str]) -> str:
    """
    Join 6 three-char cell strings into a 23-char interior string.
    Cells are separated by a single space (invisible in content rows).
    """
    return " ".join(cells)


def render_board(board: DisketteBoard, scores: dict = None, round_num: int = None) -> str:
    p1, p2 = board.players

    d1 = board.discs[p1.id]
    d2 = board.discs[p2.id]

    pos1 = board.positions[p1.id]
    pos2 = board.positions[p2.id]

    lines = [_COL_HEADER, _BORDER_TOP]

    for ry in range(5):
        row_label = _ROW_LABELS[ry]
        cells = []
        for cx in range(5):
            tile = (cx, ry)

            p1_here = pos1 == tile
            p2_here = pos2 == tile
            d1_here = d1.in_flight and d1.pos == tile
            d2_here = d2.in_flight and d2.pos == tile

            if p1_here:
                sym = "[x]" if board.armed[p1.id] else "[_]"
            elif p2_here:
                sym = "(o)" if board.armed[p2.id] else "( )"
            elif d1_here and d2_here:
                sym = " @ "
            elif d1_here:
                sym = " x "
            elif d2_here:
                sym = " o "
            else:
                sym = "   "

            cells.append(sym)

        content = _build_row(cells)
        lines.append(f" {row_label} │{content}│")

        # Separator after every row except the last
        if ry < 4:
            lines.append(_SEPARATOR_ROW)

    lines.append(_BORDER_BOTTOM)

    # Sidebar: attach player/score info to the right of rows A, B, C
    if scores is not None:
        s1 = scores.get(p1.id, 0)
        s2 = scores.get(p2.id, 0)
        sidebar = [
            f"   |w[x]|n {p1.key}  {s1}",
            f"   |w(o)|n {p2.key}  {s2}",
        ]
        if round_num is not None:
            sidebar.append(f"   Round {round_num}")
        # Row A is index 2, row B is index 4, row C is index 6
        sidebar_indices = [2, 4, 6]
        for i, extra in zip(sidebar_indices, sidebar):
            lines[i] = lines[i] + extra

    return "\n".join(lines)


def render_scores(game) -> str:
    p1, p2 = game.players
    s1 = game.scores.get(p1.id, 0)
    s2 = game.scores.get(p2.id, 0)
    return f"|w{p1.key}|n {s1} — {s2} |w{p2.key}|n  (Round {game.round_num})"
