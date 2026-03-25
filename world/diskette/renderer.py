"""
Diskette — ASCII board renderer.

Board layout (columns 1-6 left-to-right, rows A-F top-to-bottom):

     1   2   3   4   5   6
   ┌───────────────────────┐
 A │|_|                   │
   │   ·   ·   ·   ·   ·   │
 B │                       │
   │   ·   ·   ·   ·   ·   │
 ...
 F │                   (_)│
   └───────────────────────┘

Symbols (3 chars each):
  |_|  — player 1 (P1)
  |x|  — player 1 with own disc on same tile
  (_)  — player 2 (P2)
  (o)  — player 2 with own disc on same tile
   x   — P1 disc in flight (no player)
   o   — P2 disc in flight (no player)
       — empty (3 spaces)
"""
from world.diskette.physics import DisketteBoard

_ROW_LABELS = "ABCDEF"
_COL_LABELS = "123456"

# Interior: 6 cells × 3 chars + 5 separators = 23 chars
_BORDER_TOP    = "   ┌───────────────────────┐"
_BORDER_BOTTOM = "   └───────────────────────┘"
_SEPARATOR_ROW = "   │   ·   ·   ·   ·   ·   │"
_COL_HEADER    = "     1   2   3   4   5   6"


def _build_row(cells: list[str]) -> str:
    """
    Join 6 three-char cell strings into a 23-char interior string.
    Cells are separated by a single space (invisible in content rows).
    """
    return " ".join(cells)


def render_board(board: DisketteBoard) -> str:
    p1, p2 = board.players

    d1 = board.discs[p1.id]
    d2 = board.discs[p2.id]

    pos1 = board.positions[p1.id]
    pos2 = board.positions[p2.id]

    lines = [_COL_HEADER, _BORDER_TOP]

    for ry in range(6):
        row_label = _ROW_LABELS[ry]
        cells = []
        for cx in range(6):
            tile = (cx, ry)

            p1_here = pos1 == tile
            p2_here = pos2 == tile
            d1_here = d1.in_flight and d1.pos == tile
            d2_here = d2.in_flight and d2.pos == tile

            if p1_here:
                sym = "|x|" if d1_here else "|_|"
            elif p2_here:
                sym = "(o)" if d2_here else "(_)"
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
        if ry < 5:
            lines.append(_SEPARATOR_ROW)

    lines.append(_BORDER_BOTTOM)
    return "\n".join(lines)


def render_scores(game) -> str:
    p1, p2 = game.players
    s1 = game.scores.get(p1.id, 0)
    s2 = game.scores.get(p2.id, 0)
    return f"|w{p1.key}|n {s1} — {s2} |w{p2.key}|n  (Round {game.round_num})"
