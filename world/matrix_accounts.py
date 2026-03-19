"""
Matrix Accounts System

Manages Matrix social accounts for characters - aliases, profiles, and future social features.

Each character can have one Matrix account tied to their chip (Matrix ID).
The account stores their alias (@handle) and other social data.

Basic handsets use the owner's account. Future hacked devices can spoof accounts.
"""

from evennia import DefaultScript
from evennia.utils import search
import re


# Alias validation pattern: username (letters, numbers, underscore, 2-10 chars)
# The @ symbol is just UI decoration - not stored
ALIAS_PATTERN = re.compile(r'^[a-zA-Z0-9_]{2,10}$')


def _sync_avatar_alias(character, alias):
    """
    Push an alias update directly to the character's avatar cache, if one exists.

    Sets db.matrix_alias on the avatar without going through the rig, since
    the alias is already known at the call site. Only updates if the character
    is currently associated with a rig.
    """
    rig = character.db.sitting_on
    if not rig:
        return
    from typeclasses.matrix.avatars import MatrixAvatar
    for avatar in MatrixAvatar.objects.all():
        if avatar.db.entry_device == rig and not avatar.db.dead:
            avatar.db.matrix_alias = alias
            break


def get_accounts_script():
    """
    Get or create the global Matrix accounts registry script.

    Returns:
        DefaultScript: The accounts script with account data
    """
    script = search.search_script("matrix_accounts_registry")

    if not script:
        # Create the registry script
        script = DefaultScript.create(
            key="matrix_accounts_registry",
            persistent=True,
            desc="Global registry for Matrix accounts and aliases"
        )
        script.db.accounts = {}  # {character_dbref: account_data}
        script.db.alias_to_dbref = {}  # {@alias: character_dbref} for fast lookup
    else:
        if len(script) > 1:
            from evennia.utils import logger
            logger.log_warn(
                f"Multiple matrix_accounts_registry scripts found ({len(script)})! "
                "Using first one. This should not happen."
            )
        script = script[0]

    # Ensure attributes exist
    if script.db.accounts is None:
        script.db.accounts = {}
    if script.db.alias_to_dbref is None:
        script.db.alias_to_dbref = {}

    return script


def get_account(character):
    """
    Get matrix account data for a character.

    Creates a default account if one doesn't exist.

    Args:
        character: The character to look up

    Returns:
        dict: Account data with keys: alias, created, matrix_id
    """
    if not character or not character.pk:
        return None

    registry = get_accounts_script()
    dbref = character.id

    # Return existing account
    if dbref in registry.db.accounts:
        return registry.db.accounts[dbref]

    # Create default account
    account_data = {
        'alias': None,  # No alias set yet
        'created': None,  # Will be set when alias is first chosen
        'last_alias_change': None,  # Timestamp of last alias change
        'matrix_id': character.get_matrix_id() if hasattr(character, 'get_matrix_id') else None
    }

    registry.db.accounts[dbref] = account_data
    return account_data


def validate_alias(alias):
    """
    Check if an alias meets format requirements.

    Rules:
    - 2-10 characters
    - Only letters, numbers, and underscore
    - Case insensitive (stored as lowercase)
    - The @ prefix is just UI decoration (not stored)

    Args:
        alias (str): The alias to validate

    Returns:
        tuple: (True, normalized_alias) on success, (False, error_message) on failure
    """
    if not alias:
        return False, "Alias cannot be empty."

    # Strip @ prefix if present (UI decoration)
    if alias.startswith('@'):
        alias = alias[1:]

    if not ALIAS_PATTERN.match(alias):
        return False, (
            "Alias must be 2-10 characters and contain only "
            "letters, numbers, and underscores."
        )

    return True, alias  # Return normalized alias without @


def set_alias(character, alias):
    """
    Set a character's matrix alias.

    Validates format and uniqueness. Updates both the account registry
    and the reverse lookup index.

    Enforces a 1 hour cooldown between alias changes.

    Args:
        character: The character setting their alias
        alias (str): The desired alias (e.g., "netrunner" or "@netrunner")

    Returns:
        tuple: (success, message)
    """
    if not character or not character.pk:
        return False, "Invalid character."

    # Normalize alias to lowercase and strip @ if present
    alias = alias.lower().strip()

    # Validate format (also normalizes by removing @)
    is_valid, normalized_alias = validate_alias(alias)
    if not is_valid:
        return False, normalized_alias  # normalized_alias contains error message on failure

    alias = normalized_alias  # Use the normalized version without @

    registry = get_accounts_script()
    dbref = character.id

    # Check if alias is already taken by someone else
    if alias in registry.db.alias_to_dbref:
        existing_dbref = registry.db.alias_to_dbref[alias]
        if existing_dbref != dbref:
            return False, f"Alias {alias} is already taken."

    # Get or create account
    account = get_account(character)
    old_alias = account.get('alias')

    # Check cooldown (1 hour) if they already have an alias
    if old_alias:
        from datetime import datetime, timedelta
        last_change = account.get('last_alias_change')
        if last_change:
            try:
                last_change_time = datetime.fromisoformat(last_change)
                now = datetime.utcnow()
                time_since_change = now - last_change_time
                cooldown_duration = timedelta(hours=1)

                if time_since_change < cooldown_duration:
                    remaining = cooldown_duration - time_since_change
                    minutes = int(remaining.total_seconds() / 60)
                    if minutes > 0:
                        return False, f"You can change your alias again in {minutes} minutes."
                    else:
                        seconds = int(remaining.total_seconds())
                        return False, f"You can change your alias again in {seconds} seconds."
            except (ValueError, TypeError):
                # If timestamp is invalid, allow the change
                pass

    # Remove old alias from reverse lookup if it exists
    if old_alias and old_alias in registry.db.alias_to_dbref:
        del registry.db.alias_to_dbref[old_alias]

    # Set new alias and update timestamp
    from datetime import datetime
    account['alias'] = alias
    account['last_alias_change'] = datetime.utcnow().isoformat()

    if not account.get('created'):
        account['created'] = datetime.utcnow().isoformat()

    # Update matrix ID snapshot. NOTE: if ID recycling is ever enabled in
    # matrix_ids.py, this snapshot can silently drift — a reassigned ID would
    # not be reflected here. Audit this if recycling becomes active.
    if hasattr(character, 'get_matrix_id'):
        account['matrix_id'] = character.get_matrix_id()

    # Update reverse lookup
    registry.db.alias_to_dbref[alias] = dbref

    # Save back to registry
    registry.db.accounts[dbref] = account

    # Push alias to avatar cache if the character is currently jacked in
    _sync_avatar_alias(character, alias)

    return True, f"Matrix alias set to @{alias}"


def get_character_by_alias(alias):
    """
    Look up a character by their matrix alias.

    Args:
        alias (str): The alias to look up (with or without @ prefix)

    Returns:
        Character or None: The character with this alias, or None if not found
    """
    if not alias:
        return None

    # Normalize alias (strip @ if present since we don't store it)
    alias = alias.lower().strip()
    if alias.startswith('@'):
        alias = alias[1:]

    registry = get_accounts_script()
    dbref = registry.db.alias_to_dbref.get(alias)

    if not dbref:
        return None

    # Look up character by dbref
    from evennia import search_object
    results = search_object(f"#{dbref}")

    if not results:
        # Character was deleted - clean up the registry (lazy cleanup)
        del registry.db.alias_to_dbref[alias]
        if dbref in registry.db.accounts:
            del registry.db.accounts[dbref]
        return None

    return results[0]


def get_alias(character):
    """
    Get a character's current matrix alias.

    Args:
        character: The character to look up

    Returns:
        str or None: The alias without @ prefix (e.g., "netrunner") or None if not set
    """
    account = get_account(character)
    return account.get('alias') if account else None


def has_alias(character):
    """
    Check if a character has set their matrix alias.

    Args:
        character: The character to check

    Returns:
        bool: True if alias is set, False otherwise
    """
    return get_alias(character) is not None


def get_account_stats():
    """
    Get statistics about the Matrix accounts system.

    Returns:
        dict: Statistics including total accounts, aliases set, etc.
    """
    registry = get_accounts_script()
    total_accounts = len(registry.db.accounts)
    aliases_set = len(registry.db.alias_to_dbref)

    return {
        'total_accounts': total_accounts,
        'aliases_set': aliases_set,
        'accounts_without_alias': total_accounts - aliases_set
    }
