# world/audio/audio.py
#
# Server-side helpers for controlling music in the Evennia web client.
# These functions send OOB messages that audio_plugin.js intercepts.
#
# Only affects the web client — MUD clients connected via telnet/SSH
# silently ignore OOB messages they don't understand, so these are safe
# to call regardless of how a player is connected.
#
# Usage:
#   from world.audio import play_music, stop_music, set_volume
#
#   play_music(caller, "/static/audio/rite_ambience.ogg", loop=True)
#   play_music(caller, "https://cdn.example.com/tracks/undercity.mp3")
#   stop_music(caller)
#   set_volume(caller, 0.4)
 
 
def play_music(caller, url: str, volume: float = 0.7, loop: bool = True,
               fade_in: float = 2.0):
    """
    Begin playing a music track in the player's web client.
 
    Args:
        caller:     The character or account object to send to.
        url:        URL of the audio file. Use a path relative to your
                    Django STATIC_URL (e.g. "/static/audio/track.ogg")
                    or any fully-qualified HTTPS URL.
        volume:     0.0 (silent) → 1.0 (full). Default 0.7.
        loop:       Whether the track loops continuously. Default True.
        fade_in:    Seconds to fade from silence to `volume`. Default 2.0.
                    Set to 0 for an immediate cut-in.
 
    Supported formats:
        .ogg  — best cross-browser support for game audio
        .mp3  — universally supported; larger files
        .wav  — lossless but large; use for short stings, not music
    """
    volume  = max(0.0, min(1.0, float(volume)))
    fade_in = max(0.0, float(fade_in))
    caller.msg(oob=(
        "PLAY_AUDIO", [],
        {"url": url, "volume": volume, "loop": loop, "fade_in": fade_in},
    ))
 
 
def stop_music(caller, fade_out: float = 2.0):
    """
    Stop the currently playing track.
 
    Args:
        caller:     The character or account object.
        fade_out:   Seconds to fade out before stopping. Default 2.0.
                    Set to 0 for an immediate cut.
    """
    fade_out = max(0.0, float(fade_out))
    caller.msg(oob=("STOP_AUDIO", [], {"fade_out": fade_out}))
 
 
def set_volume(caller, volume: float, fade: float = 1.0):
    """
    Change the volume of the currently playing track without stopping it.
    Useful for dimming music during tense scenes.
 
    Args:
        caller:   The character or account object.
        volume:   Target volume 0.0 → 1.0.
        fade:     Seconds to reach the new volume. Default 1.0.
    """
    volume = max(0.0, min(1.0, float(volume)))
    fade   = max(0.0, float(fade))
    caller.msg(oob=("SET_AUDIO_VOLUME", [], {"volume": volume, "fade": fade}))
 
 
# ─── Convenience wrappers for common zone transitions ────────────────────────
 
def play_music_for_zone(caller, zone_key: str):
    """
    Play the registered track for a named zone.
    Add entries to ZONE_TRACKS below as you build out areas.
    """
    track = ZONE_TRACKS.get(zone_key)
    if track:
        play_music(caller, **track)
 
 
# Map zone keys → play_music kwargs.
# Paths are relative to Django STATIC_URL.
ZONE_TRACKS = {
    "soul_registry":    {"url": "/static/media/thegrid.ogg",   "volume": 0.5, "loop": True,  "fade_in": 3.0},
    "chargen_rite":     {"url": "/static/media/thegrid.ogg",    "volume": 0.6, "loop": True,  "fade_in": 2.0},
    "undercity_market": {"url": "/static/audio/undercity_market.ogg", "volume": 0.7, "loop": True,  "fade_in": 1.5},
    "combat":           {"url": "/static/audio/combat_pulse.ogg",     "volume": 0.8, "loop": True,  "fade_in": 0.5},
    "inquisition":      {"url": "/static/audio/inquisition_drone.ogg","volume": 0.65,"loop": True,  "fade_in": 4.0},
    "death":            {"url": "/static/audio/flatline.ogg",         "volume": 0.9, "loop": False, "fade_in": 0.0},
}