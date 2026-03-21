"""
Weekly pay collection. Characters collect pay at a registry terminal.
Pay is available once every 7 real-time days per faction.

Currency is stored on character.db.currency (int). Vendors and other systems
should use the same field for a single wallet balance.
"""

import time

from world.rpg.factions.membership import get_member_rank

PAY_COOLDOWN_SECONDS = 7 * 24 * 60 * 60  # 7 days

# Minimum membership before first paycheck (anti join-collect-discharge exploit).
FIRST_PAY_DELAY_SECONDS = 3 * 24 * 60 * 60  # 3 days after joining


def can_collect_pay(character, faction_key):
    """
    Check if a character can collect weekly pay from a faction.

    Returns (can_collect: bool, reason: str, amount: int).
    """
    from world.rpg.factions import get_faction, is_faction_member
    from world.rpg.factions.ranks import get_rank_pay

    fdata = get_faction(faction_key)
    if not fdata:
        return False, "Unknown faction.", 0

    if not is_faction_member(character, faction_key):
        return False, "Not a member.", 0

    rank = get_member_rank(character, faction_key)
    pay_amount = get_rank_pay(fdata["ranks"], rank)

    if pay_amount <= 0:
        return False, "Your rank does not include pay.", 0

    joined = (character.db.faction_joined or {}).get(fdata["key"])
    if joined and (time.time() - joined) < FIRST_PAY_DELAY_SECONDS:
        remaining_hours = int((FIRST_PAY_DELAY_SECONDS - (time.time() - joined)) / 3600)
        return False, f"New member. First pay available in {remaining_hours}h.", 0

    last_collected = (character.db.faction_pay_collected or {}).get(fdata["key"])
    if last_collected:
        elapsed = time.time() - last_collected
        if elapsed < PAY_COOLDOWN_SECONDS:
            remaining_days = int((PAY_COOLDOWN_SECONDS - elapsed) / 86400)
            remaining_hours = int(((PAY_COOLDOWN_SECONDS - elapsed) % 86400) / 3600)
            return False, f"Next pay in {remaining_days}d {remaining_hours}h.", 0

    return True, "Pay available.", pay_amount


def collect_pay(character, faction_key):
    """
    Collect weekly pay. Adds currency to character, updates timestamp.

    Returns (success: bool, message: str, amount: int).
    """
    from world.rpg.factions import get_faction

    can, reason, amount = can_collect_pay(character, faction_key)
    if not can:
        return False, reason, 0

    fdata = get_faction(faction_key)

    current = int(getattr(character.db, "currency", 0) or 0)
    character.db.currency = current + amount

    pay_times = character.db.faction_pay_collected or {}
    pay_times[fdata["key"]] = time.time()
    character.db.faction_pay_collected = pay_times

    return True, f"Collected {amount} from {fdata['name']}.", amount
