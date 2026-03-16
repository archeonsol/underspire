"""
Voice system: optional character voice description (e.g. "British accented") that
sometimes shows when they speak, based on listeners' perception stat (rare).
"""

import random


def get_voice_phrase(character):
    """
    Return the full voice phrase for the character, or "" if unset.
    db.voice is stored without " voice" (e.g. "British accented"); we affix " voice".
    """
    if not character:
        return ""
    raw = (getattr(character.db, "voice", None) or "").strip()
    if not raw:
        return ""
    return raw + " voice"


def get_speaking_tag(character):
    """
    Return "*speaking in a X voice* " for use inside say/emote, or "" if no voice.
    """
    phrase = get_voice_phrase(character)
    if not phrase:
        return ""
    return "*speaking in a %s* " % phrase


def voice_perception_check(listener, speaker):
    """
    Roll whether the listener "hears" the speaker's voice quality.
    Uses listener's perception stat (0-300). Rare: ~4%% at 100 perception, ~12%% at 300.
    """
    if not listener or not speaker or listener == speaker:
        return False
    stats = getattr(listener, "db", None) and getattr(listener.db, "stats", None)
    if not stats or not isinstance(stats, dict):
        return False
    perception = int(stats.get("perception", 0) or 0)
    if perception <= 0:
        return False
    # Roll 1-100; show voice if roll <= perception/25 (max 12 at 300)
    chance = max(1, min(100, perception // 25))
    return random.randint(1, 100) <= chance
