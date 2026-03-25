"""
Diskette — AI opponent for practice mode.

DisketteBot: lightweight duck-typed mock player (not a DB object).
choose_action: returns a random valid action dict each turn.
"""
import random

from world.diskette.physics import DIRS, in_bounds


class DisketteBot:
    """
    Minimal mock of a character object. DisketteGame treats it as a player.
    Has no DB, no location — guards must exist anywhere those are accessed.
    """
    id = "AI"
    key = "The Grid"

    def msg(self, *args, **kwargs):
        pass  # swallow silently


def choose_action(board, bot_id, opponent_id) -> dict:
    """
    Pick a random valid action for the bot this turn.

    Valid pool:
      - pass (always)
      - move <dir> for each in-bounds direction from current position
      - throw <dir> for all 8 directions, only if armed

    reflect is excluded — it requires predicting where a disc will land this
    turn, which is meaningless to do randomly and would just waste turns.
    """
    pos = board.positions[bot_id]
    armed = board.armed[bot_id]

    valid = [{"type": "pass", "dir": None}]

    for dname, (dx, dy) in DIRS.items():
        nx, ny = pos[0] + dx, pos[1] + dy
        if in_bounds(nx, ny):
            valid.append({"type": "move", "dir": dname})

    if armed:
        for dname in DIRS:
            valid.append({"type": "throw", "dir": dname})

    return random.choice(valid)
