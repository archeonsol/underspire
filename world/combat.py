"""
Legacy facade for the combat system.

The actual engine/ticker logic now lives in the `world.combat` package:

    - world.combat.engine
    - world.combat.tickers
    - world.combat.utils

Existing imports of `world.combat` continue to work by re-exporting the
primary functions.
"""

from world.combat.engine import resolve_attack, execute_combat_turn, can_attack  # noqa
from world.combat.tickers import (  # noqa
    start_combat_ticker,
    stop_combat_ticker,
    remove_both_combat_tickers,
)
from world.combat.utils import (  # noqa
    is_in_combat,
    is_being_attacked,
    get_combat_target as _get_combat_target,
    set_combat_target as _set_combat_target,
    combat_display_name as _combat_display_name,
)
