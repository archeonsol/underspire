"""
World combat package.

This package hosts the combat engine, ticker wiring, and small utilities.
`world.combat` remains the public facade for legacy callers.
"""

from .engine import resolve_attack, execute_combat_turn, can_attack, _body_part_and_multiplier  # noqa
from .tickers import (  # noqa
    start_combat_ticker,
    stop_combat_ticker,
    remove_both_combat_tickers,
    resume_offensive_schedule,
)
from .utils import (  # noqa
    is_in_combat,
    is_being_attacked,
    get_combat_target,
    set_combat_target,
    combat_display_name,
    is_attacking_target,
)

# Public data definitions (used by commands, etc)
from .weapon_definitions import WEAPON_HANDS  # noqa: E402,F401
from .instance import CombatInstance, ensure_instance, get_instance_for, try_auto_switch_target  # noqa: E402,F401

# Backwards-compatible aliases for legacy imports that expect private helpers
_get_combat_target = get_combat_target
_set_combat_target = set_combat_target
_combat_display_name = combat_display_name

