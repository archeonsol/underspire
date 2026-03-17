"""
Server startstop hooks

This module contains functions called by Evennia at various
points during its startup, reload and shutdown sequence. It
allows for customizing the server operation as desired.

This module must contain at least these global functions:

at_server_init()
at_server_start()
at_server_stop()
at_server_reload_start()
at_server_reload_stop()
at_server_cold_start()
at_server_cold_stop()

"""


def at_server_init():
    """
    This is called first as the server is starting up, regardless of how.
    """
    pass


def at_server_start():
    """
    This is called every time the server starts up, regardless of
    how it was shut down.
    """
    from evennia import create_script, create_channel, search_channel
    from evennia.scripts.models import ScriptDB
    from world.staff_pending import PENDING_SCRIPT_KEY, STAFF_PENDING_CHANNEL_ALIAS
    from world.language import ensure_lore_languages
    ensure_lore_languages()
    if not ScriptDB.objects.filter(db_key="stamina_regen").first():
        create_script(
            "typeclasses.scripts.StaminaRegenScript",
            key="stamina_regen",
            persistent=True,
        )
    if not ScriptDB.objects.filter(db_key="bleeding_tick").first():
        create_script(
            "typeclasses.scripts.BleedingTickScript",
            key="bleeding_tick",
            persistent=True,
        )
    if not ScriptDB.objects.filter(db_key=PENDING_SCRIPT_KEY).first():
        create_script(
            "typeclasses.scripts.StaffPendingScript",
            key=PENDING_SCRIPT_KEY,
            persistent=True,
        )
    # Staff pending channel: so staff can subscribe and see new requests
    if not list(search_channel(STAFF_PENDING_CHANNEL_ALIAS)):
        create_channel(
            key=STAFF_PENDING_CHANNEL_ALIAS,
            aliases=["pending", "staffpending"],
            desc="Staff queue for pending approval requests (sdesc custom terms, etc.). Subscribe to see new requests.",
            locks="listen:perm(Builder);send:perm(Builder);control:perm(Admin)",
        )

    # OOC channels: xooc, xgame, xstaff, xassist only (no non-x aliases)
    # First nuke any legacy Help/xhelp channels so we can recreate cleanly.
    try:
        legacy_help = list(search_channel("Help")) + list(search_channel("xhelp"))
        seen = set()
        for ch in legacy_help:
            if not ch or ch.id in seen:
                continue
            seen.add(ch.id)
            try:
                ch.delete()
            except Exception:
                continue
    except Exception:
        pass

    ooc_channels = (
        ("OOC-Chat", ["xooc"], "OOC chat. Uses your account OOC name (set with @oocname).", "listen:all();send:all();control:perm(Admin)"),
        ("Game-Help", ["xgame"], "Game help. Ask questions about how to play.", "listen:all();send:all();control:perm(Admin)"),
        ("Staff", ["xstaff"], "Staff-only channel.", "listen:perm(Builder);send:perm(Builder);control:perm(Admin)"),
        ("Assist", ["xassist"], "One-way assistance channel to staff. You only see your own messages; staff see all. Staff reply privately with xhelpreply <account> <message>.", "listen:all();send:all();control:perm(Admin)"),
    )
    for key, aliases, desc, locks in ooc_channels:
        if not list(search_channel(aliases[0])):
            create_channel(key=key, aliases=aliases, desc=desc, locks=locks)


def at_server_stop():
    """
    This is called just before the server is shut down, regardless
    of it is for a reload, reset or shutdown.
    """
    pass


def at_server_reload_start():
    """
    This is called only when server starts back up after a reload.
    """
    pass


def at_server_reload_stop():
    """
    This is called only time the server stops before a reload.
    """
    pass


def at_server_cold_start():
    """
    This is called only when the server starts "cold", i.e. after a
    shutdown or a reset.
    """
    pass


def at_server_cold_stop():
    """
    This is called only when the server goes down due to a shutdown or
    reset.
    """
    pass
