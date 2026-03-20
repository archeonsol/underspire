"""
Device Interface Menu

EvMenu-based interface for interacting with networked devices.
Can be accessed from meatspace (via 'operate' command) or from Matrix (via 'patch cmd.exe').
"""

from evennia import EvMenu
from evennia.utils.evtable import EvTable
import textwrap
from collections.abc import Mapping


def _as_plain_mapping(value):
    """
    Normalize mapping-like Evennia Attribute wrappers to plain dicts.
    """
    if isinstance(value, Mapping):
        try:
            return dict(value)
        except Exception:
            return {}
    return {}


def _node_call(func, caller, **kwargs):
    """
    Render a target node directly for safe transition shape.
    """
    return func(caller, "", **kwargs)


def _reflow_box(text: str, width: int = 74) -> str:
    """
    Reflow text to fixed width inside a simple ASCII box.
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    # Split on blank lines to preserve paragraph breaks.
    paras = [p.strip() for p in text.split("\n\n")]
    wrapped_lines = []
    for para in paras:
        if not para:
            wrapped_lines.append("")
            continue
        # Normalize internal whitespace but keep explicit linebreaks inside para.
        subparas = [sp.strip() for sp in para.split("\n") if sp.strip()]
        joined = " ".join(subparas)
        wrapped = textwrap.fill(joined, width=width)
        wrapped_lines.extend(wrapped.split("\n"))
        wrapped_lines.append("")
    # Drop trailing blank.
    while wrapped_lines and wrapped_lines[-1] == "":
        wrapped_lines.pop()

    border = "-" * (width + 4)
    out = [border]
    for line in wrapped_lines:
        out.append(f"| {line[:width].ljust(width)} |")
    out.append(border)
    return "\n".join(out)


def device_main_menu(caller, raw_string, **kwargs):
    """
    Main menu for device interaction.

    Shows device info and available commands.
    """
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    if not device:
        caller.msg("|rError: Device interface unavailable.|n")
        return None

    # Build menu text
    text = f"|c=== {device.key} Interface ===|n\n\n"
    text += f"Device Type: {getattr(device.db, 'device_type', 'unknown')}\n"
    text += f"Security Level: {getattr(device.db, 'security_level', 0)}\n"
    try:
        matrix_id = device.get_matrix_id() if hasattr(device, "get_matrix_id") else None
    except Exception:
        matrix_id = None
    if matrix_id:
        text += f"Matrix ID: {matrix_id}\n"

    # Show capabilities
    has_storage = getattr(device.db, 'has_storage', False)
    has_controls = getattr(device.db, 'has_controls', False)
    text += f"Storage: {'Yes' if has_storage else 'No'}\n"
    text += f"Controls: {'Yes' if has_controls else 'No'}\n"

    # Check ACL authorization
    is_authorized = device.check_acl(caller)
    if is_authorized:
        text += "\n|gYou are authorized on this device's ACL.|n\n"
    else:
        text += "\n|yYou are NOT authorized on this device's ACL.|n\n"

    # Build options dict
    options = []

    # Get available commands from device (filtered by skill and access)
    available_commands = device.get_available_commands(caller, from_matrix)
    if available_commands:
        text += "\n|wAvailable Commands:|n\n"
        for i, (cmd_name, cmd_help) in enumerate(available_commands.items(), 1):
            text += f"  {i}. |y{cmd_name}|n - {cmd_help}\n"
            # Some commands (especially handset helpers) take no arguments. If we
            # prompt for args anyway, players can get stuck thinking they must type
            # something. So for handset no-arg commands, execute immediately.
            goto_node = "node_execute_command"
            if str(getattr(device.db, "device_type", "") or "").lower() == "handset" and cmd_name in (
                "account",
                "contacts",
                "messages",
                "photos",
                "call_history",
                "groups",
            ):
                # Photos / groups use dedicated menu nodes; others are true no-arg device commands.
                if cmd_name == "photos":
                    goto_node = "node_view_photos"
                elif cmd_name == "groups":
                    goto_node = "node_view_groups"
                else:
                    goto_node = "node_execute_noargs"
            options.append({
                "key": str(i),
                "desc": cmd_name,
                "goto": (goto_node, {"device": device, "command": cmd_name, "from_matrix": from_matrix})
            })

    # Storage browsing if available
    if has_storage:
        options.append({
            "key": "f",
            "desc": "Browse files",
            "goto": ("node_browse_files", {"device": device, "from_matrix": from_matrix})
        })

    # ACL management if authorized or via exploit
    options.append({
        "key": "a",
        "desc": "View ACL",
        "goto": ("node_view_acl", {"device": device, "from_matrix": from_matrix})
    })

    options.append({
        "key": "q",
        "desc": "Exit interface",
        "goto": "node_exit"
    })

    return text, options


def node_execute_command(caller, raw_string, **kwargs):
    """
    Execute a device command, prompting for arguments if needed.
    """
    device = kwargs.get("device")
    command = kwargs.get("command")
    from_matrix = kwargs.get("from_matrix", False)

    if not device or not command:
        return _node_call(node_error, caller, **kwargs)

    text = f"|c=== Execute: {command} ===|n\n\n"
    text += "Enter command arguments (or 'back' to cancel):\n"

    options = [{"key": "_default", "desc": None, "goto": ("node_process_command", {"device": device, "command": command, "from_matrix": from_matrix})}]

    return text, options


def node_execute_noargs(caller, raw_string, **kwargs):
    """
    Execute a device command immediately with no arguments.
    """
    device = kwargs.get("device")
    command = kwargs.get("command")
    from_matrix = kwargs.get("from_matrix", False)

    if not device or not command:
        return _node_call(node_error, caller, **kwargs)

    # Execute with no args.
    success = device.invoke_device_command(command, caller, from_matrix)

    # Many no-arg commands (like handset account/contacts/messages) output directly to the
    # caller via caller.msg. Still, we must return a proper EvMenu node response here,
    # otherwise the menu may display the node name and appear "stuck".
    text = "\n|gCommand executed.|n\n" if success else "\n|rCommand failed.|n\n"
    text += "\nPress any key to return to main menu."

    options = {
        "key": "_default",
        "goto": ("device_main_menu", {"device": device, "from_matrix": from_matrix}),
    }

    return text, options


def node_process_command(caller, raw_string, **kwargs):
    """
    Process the command with provided arguments.
    """
    device = kwargs.get("device")
    command = kwargs.get("command")
    from_matrix = kwargs.get("from_matrix", False)

    if not device or not command:
        return _node_call(node_error, caller, **kwargs)

    if raw_string.strip().lower() == "back":
        return _node_call(device_main_menu, caller, device=device, from_matrix=from_matrix)

    # Parse arguments
    args = raw_string.strip().split() if raw_string.strip() else []

    # Execute the command via device framework
    result = device.invoke_device_command(command, caller, from_matrix, *args)

    # Handlers can return a (node_name, kwargs) tuple to drive menu navigation
    if isinstance(result, tuple):
        return result

    text = "\n|gCommand executed.|n\n" if result else "\n|rCommand failed.|n\n"
    text += "\nPress any key to return to main menu."

    options = [{"key": "_default", "desc": None, "goto": ("device_main_menu", {"device": device, "from_matrix": from_matrix})}]

    return text, options


def node_browse_files(caller, raw_string, **kwargs):
    """
    Browse files on device storage.
    """
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)

    if not device or not device.db.has_storage:
        return _node_call(node_error, caller, **kwargs)

    files = device.list_files()

    text = f"|c=== Files on {device.key} ===|n\n\n"

    if not files:
        text += "No files on device.\n\n"
    else:
        # Create table
        table = EvTable("Filename", "Type", "Size", border="cells")
        for f in files:
            filename = f.get('filename', 'unknown')
            filetype = f.get('filetype', 'unknown')
            size = len(f.get('contents', ''))
            table.add_row(filename, filetype, f"{size} bytes")
        text += str(table) + "\n\n"

    options = [
        {
            "key": "r",
            "desc": "Read a file",
            "goto": ("node_read_file_prompt", {"device": device, "from_matrix": from_matrix})
        },
        {
            "key": "b",
            "desc": "Back to main menu",
            "goto": ("device_main_menu", {"device": device, "from_matrix": from_matrix})
        }
    ]

    return text, options


def node_read_file_prompt(caller, raw_string, **kwargs):
    """
    Prompt for filename to read.
    """
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)

    text = "|c=== Read File ===|n\n\n"
    text += "Enter filename to read (or 'back' to cancel):\n"

    options = [{"key": "_default", "desc": None, "goto": ("node_read_file", {"device": device, "from_matrix": from_matrix})}]

    return text, options


def node_read_file(caller, raw_string, **kwargs):
    """
    Read and display a file.
    """
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)

    if raw_string.strip().lower() == "back":
        return _node_call(node_browse_files, caller, **kwargs)

    filename = raw_string.strip()
    file_obj = device.get_file(filename)

    if not file_obj:
        text = f"|rFile not found: {filename}|n\n\n"
        text += "Press any key to return to file browser."
    else:
        text = f"|c=== {filename} ===|n\n\n"
        text += file_obj.get('contents', '[empty]')
        text += "\n\nPress any key to return to file browser."

    options = [{"key": "_default", "desc": None, "goto": ("node_browse_files", {"device": device, "from_matrix": from_matrix})}]

    return text, options


def node_view_acl(caller, raw_string, **kwargs):
    """
    View device ACL.
    """
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)

    acl_names = device.get_acl_names()

    text = f"|c=== ACL for {device.key} ===|n\n\n"

    if not acl_names:
        text += "No access restrictions (public device).\n\n"
    else:
        text += "Authorized users:\n"
        for name in acl_names:
            text += f"  - {name}\n"
        text += "\n"

    options = [
        {
            "key": "b",
            "desc": "Back to main menu",
            "goto": ("device_main_menu", {"device": device, "from_matrix": from_matrix})
        }
    ]

    return text, options


def node_view_contacts(caller, raw_string, **kwargs):
    """
    View handset contacts (stored only on that handset).
    """
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)

    text = f"|c=== Contacts on {device.key} ===|n\n\n"

    contacts = {}
    try:
        if hasattr(device, "get_contacts"):
            contacts = device.get_contacts() or {}
        else:
            raw = getattr(device.db, "contacts", None) or {}
            contacts = raw if isinstance(raw, dict) else {}
    except Exception:
        contacts = {}

    if not contacts:
        text += "No contacts saved.\n"
    else:
        text += "|wAlias|n - |wID|n\n"
        text += "-" * 40 + "\n"
        for alias in sorted(contacts.keys()):
            text += f"{alias} - {contacts[alias]}\n"
        text += f"\n({len(contacts)}/15 contacts)\n"

    options = [
        {
            "key": "b",
            "desc": "Back to main menu",
            "goto": ("device_main_menu", {"device": device, "from_matrix": from_matrix})
        }
    ]
    return text, options


def node_view_messages(caller, raw_string, **kwargs):
    """
    View handset text buffer (last 24 hours).
    """
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)

    text = f"|c=== Messages on {device.key} (last 24h) ===|n\n\n"

    import time

    # Messages that arrive after this moment stay unread until the next view.
    view_started = time.time()

    msgs = []
    try:
        if hasattr(device, "get_text_messages"):
            msgs = device.get_text_messages() or []
        else:
            msgs = list(getattr(device.db, "texts", []) or [])
    except Exception:
        msgs = []

    if not msgs:
        text += "No recent texts.\n"
    else:
        from world.matrix_groups import format_inbox_line

        for entry in msgs[-50:]:
            if not isinstance(entry, dict):
                continue
            text += format_inbox_line(device, entry) + "\n"

    try:
        if device:
            device.db.last_texts_viewed_t = view_started
    except Exception:
        pass

    options = [
        {
            "key": "b",
            "desc": "Back to main menu",
            "goto": ("device_main_menu", {"device": device, "from_matrix": from_matrix})
        }
    ]
    return text, options


def node_view_photos(caller, raw_string, **kwargs):
    """
    Browse photos stored on a handset.
    """
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)

    photos = []
    try:
        photos = device.get_photos() if hasattr(device, "get_photos") else list(getattr(device.db, "photos", []) or [])
    except Exception:
        photos = []
    # Evennia may return SaverDict/SaverList types; accept mapping-like entries.
    try:
        from collections.abc import Mapping
        photos = [dict(p) for p in photos if isinstance(p, Mapping)]
    except Exception:
        photos = [p for p in photos if isinstance(p, dict)]

    text = f"|c=== Photos on {device.key} ===|n\n\n"
    if not photos:
        text += "|x┌──────────────────────────────────────────────────────────────┐|n\n"
        text += "|x│|n |wPHOTO VIEWER|n  |250(no saved photos)|n".ljust(62) + "|x│|n\n"
        text += "|x└──────────────────────────────────────────────────────────────┘|n\n"
        return text, [
            {"key": "b", "desc": "Back to main menu", "goto": ("device_main_menu", {"device": device, "from_matrix": from_matrix})}
        ]

    # List newest first.
    photos_rev = list(reversed(photos))
    # Terminal-style header + simplified columns (no Type column).
    text = "|x┌──────────────────────────────────────────────────────────────┐|n\n"
    text += f"|x│|n |wPHOTO VIEWER|n  |250{device.key}|n".ljust(62) + "|x│|n\n"
    text += "|x├──────────────────────────────────────────────────────────────┤|n\n"
    table = EvTable("|wID|n", "|wWhen|n", "|wTitle|n", border="cells")
    for entry in photos_rev[:25]:
        table.add_row(
            str(entry.get("id", "")),
            entry.get("ts", "")[:20],
            (entry.get("title", "") or "")[:40],
        )
    text += str(table) + "\n"
    text += "|x├──────────────────────────────────────────────────────────────┤|n\n"
    text += "|250Select an ID to view. Showing up to 25 newest.|n\n"
    text += "|x└──────────────────────────────────────────────────────────────┘|n\n"

    options = [
        {"key": "b", "desc": "Back to main menu", "goto": ("device_main_menu", {"device": device, "from_matrix": from_matrix})},
        {"key": "d", "desc": "Delete a photo", "goto": ("node_delete_photo_prompt", {"device": device, "from_matrix": from_matrix})},
    ]
    # Allow selecting by visible photo IDs (newest 25).
    for entry in photos_rev[:25]:
        pid = entry.get("id", None)
        if pid is None:
            continue
        options.append(
            {"key": str(pid), "desc": f"View photo {pid}", "goto": ("node_view_photo_one", {"device": device, "from_matrix": from_matrix, "photo_id": pid})}
        )
    return text, options


def node_delete_photo_prompt(caller, raw_string, **kwargs):
    """
    Prompt for a photo id to delete from a handset.
    """
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    text = f"|c=== Delete photo on {device.key} ===|n\n\n"
    text += "Enter a photo ID to delete (or 'back' to cancel):\n"
    options = {"key": "_default", "goto": ("node_delete_photo_do", {"device": device, "from_matrix": from_matrix})}
    return text, options


def node_delete_photo_do(caller, raw_string, **kwargs):
    """
    Delete a photo by id and return to photos list.
    """
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    s = (raw_string or "").strip()
    if s.lower() == "back":
        return _node_call(node_view_photos, caller, device=device, from_matrix=from_matrix)

    try:
        pid = int(s)
    except Exception:
        text = "|rInvalid photo id.|n\n\nPress any key to return."
        options = {"key": "_default", "goto": ("node_view_photos", {"device": device, "from_matrix": from_matrix})}
        return text, options

    try:
        photos = device.get_photos() if hasattr(device, "get_photos") else list(getattr(device.db, "photos", []) or [])
    except Exception:
        photos = []
    try:
        from collections.abc import Mapping
        photos = [dict(p) for p in photos if isinstance(p, Mapping)]
    except Exception:
        photos = [p for p in photos if isinstance(p, dict)]

    before = len(photos)
    kept = []
    deleted = None
    for p in photos:
        try:
            if int(p.get("id", -1)) == pid and deleted is None:
                deleted = p
                continue
        except Exception:
            pass
        kept.append(p)

    if len(kept) == before:
        text = f"|yNo photo with id {pid} found.|n\n\nPress any key to return."
    else:
        try:
            device.db.photos = kept
        except Exception:
            pass
        title = (deleted or {}).get("title", "")
        extra = f" ({title})" if title else ""
        text = f"|gDeleted photo {pid}{extra}.|n\n\nPress any key to return."

    options = {"key": "_default", "goto": ("node_view_photos", {"device": device, "from_matrix": from_matrix})}
    return text, options


def node_view_photo_one(caller, raw_string, **kwargs):
    """
    View a single photo entry by stored id.
    """
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    photo_id = kwargs.get("photo_id", None)
    photos = []
    try:
        photos = device.get_photos() if hasattr(device, "get_photos") else list(getattr(device.db, "photos", []) or [])
    except Exception:
        photos = []
    try:
        from collections.abc import Mapping
        photos = [dict(p) for p in photos if isinstance(p, Mapping)]
    except Exception:
        photos = [p for p in photos if isinstance(p, dict)]
    entry = None
    if hasattr(device, "get_photo_by_id"):
        try:
            entry = device.get_photo_by_id(photo_id)
        except Exception:
            entry = None
    if not entry:
        # Fallback: scan list
        try:
            pid_int = int(photo_id)
        except Exception:
            pid_int = None
        if pid_int is not None:
            for e in photos:
                try:
                    if int(e.get("id", -1)) == pid_int:
                        entry = e
                        break
                except Exception:
                    continue
    if not entry:
        return _node_call(node_view_photos, caller, device=device, from_matrix=from_matrix)
    when = entry.get("ts", "")
    title = entry.get("title", "")
    snap = entry.get("text", "")
    snap_chars = entry.get("chars", {}) if isinstance(entry, dict) else {}

    pid_display = entry.get("id", "")
    header = f"|w{title or 'photo'}|n  |250#{pid_display}  {when}|n"
    body = snap or ""
    # Resolve per-viewer character placeholders (<<CHAR:<dbref>>>) to viewer-aware display names.
    if body and isinstance(body, str) and "<<CHAR:" in body:
        try:
            import re
            from evennia.utils.search import search_object

            pattern = re.compile(r"<<CHAR:(\d+)>>")

            def _get_obj_by_id(dbref):
                try:
                    ref = "#%s" % int(dbref)
                    result = search_object(ref)
                    return result[0] if result else None
                except Exception:
                    return None

            def _sub(match):
                cid = match.group(1)
                obj = _get_obj_by_id(cid)
                if obj and hasattr(obj, "get_display_name"):
                    try:
                        return obj.get_display_name(caller)
                    except Exception:
                        pass
                try:
                    fallback = (snap_chars or {}).get(str(cid), {}).get("sdesc")
                except Exception:
                    fallback = None
                return fallback or "someone"

            body = pattern.sub(_sub, body)
        except Exception:
            pass
    # Selfies render nicer reflowed, but still inside a terminal frame.
    is_selfie = str(entry.get("kind", "") or "").lower() == "selfie"
    if is_selfie:
        body = _reflow_box(body, width=74)
    frame_top = "|x┌──────────────────────────────────────────────────────────────┐|n"
    frame_mid = "|x├──────────────────────────────────────────────────────────────┤|n"
    frame_bot = "|x└──────────────────────────────────────────────────────────────┘|n"
    text = (
        frame_top
        + "\n|x│|n "
        + f"|w{device.key}|n |250:: photo viewer|n".ljust(58)
        + "|x│|n\n"
        + frame_mid
        + "\n|x│|n "
        + header.ljust(58)
        + "|x│|n\n"
        + frame_mid
        + "\n"
        + body
        + "\n"
        + frame_bot
    )

    options = [
        {"key": "b", "desc": "Back to photos", "goto": ("node_view_photos", {"device": device, "from_matrix": from_matrix})}
    ]
    return text, options


# =========================================================================
# Handset group chats
# =========================================================================


def _group_frame_header(title: str, subtitle: str = "") -> str:
    top = "|x┌──────────────────────────────────────────────────────────────┐|n"
    mid = "|x├──────────────────────────────────────────────────────────────┤|n"
    line = f"|x│|n |w{title}|n"
    if subtitle:
        line += f" |250{subtitle}|n"
    line = line.ljust(62) + "|x│|n"
    return top + "\n" + line + "\n" + mid + "\n"


def _group_frame_footer() -> str:
    return "|x└──────────────────────────────────────────────────────────────┘|n\n"


def node_view_groups(caller, raw_string, **kwargs):
    """
    List group chats on this handset.
    """
    from world import matrix_groups as mg

    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    chats = _as_plain_mapping(getattr(device.db, "group_chats", None) or {})
    text = _group_frame_header("GROUP CHATS", device.key)
    options = []

    if chats:
        sorted_items = sorted(
            chats.items(),
            key=lambda x: str((x[1] or {}).get("name", x[0])).lower(),
        )
        for idx, (gid, data) in enumerate(sorted_items[:12], 1):
            data = _as_plain_mapping(data)
            if not data:
                continue
            name = data.get("name", gid)
            nmem = len(data.get("members") or []) if isinstance(data.get("members"), list) else 0
            unread = mg.get_unread_group_count(device, gid)
            role = (data.get("role") or "member").lower()
            text += f"|250{idx}.|n |w{name}|n  |x({nmem}m, {unread} new) [{role}]|n  |x{gid}|n\n"
            options.append(
                {
                    "key": str(idx),
                    "desc": f"Open {name}",
                    "goto": (
                        "node_view_group_detail",
                        {"device": device, "from_matrix": from_matrix, "group_id": gid},
                    ),
                }
            )
    else:
        text += "|250No groups yet.|n\n"

    text += _group_frame_footer()
    text += "|250c|n create  |250i|n invites  |250b|n back\n"

    options.extend(
        [
            {
                "key": "c",
                "desc": "Create a group",
                "goto": ("node_group_create_prompt", {"device": device, "from_matrix": from_matrix}),
            },
            {
                "key": "i",
                "desc": "Pending invites",
                "goto": ("node_view_group_pending", {"device": device, "from_matrix": from_matrix}),
            },
            {
                "key": "b",
                "desc": "Back to main menu",
                "goto": ("device_main_menu", {"device": device, "from_matrix": from_matrix}),
            },
        ]
    )
    return text, options


def node_view_group_pending(caller, raw_string, **kwargs):
    from world import matrix_groups as mg

    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    invites = mg.get_pending_invites(device)
    text = _group_frame_header("PENDING INVITES", device.key)
    if not invites:
        text += "|250None.|n\n"
    else:
        for idx, inv in enumerate(invites[:12], 1):
            gid = str(inv.get("group_invite", "")).upper()
            nm = inv.get("group_invite_name", gid)
            text += f"|250{idx}.|n |w{nm}|n  |x{gid}|n\n"
    text += _group_frame_footer()
    text += "Type |waccept <id>|n or |wdecline <id>|n, or use keys below.\n"

    options = []
    for idx, inv in enumerate(invites[:9], 1):
        gid = str(inv.get("group_invite", "")).upper()
        options.append(
            {
                "key": str(idx),
                "desc": f"Accept {gid}",
                "goto": (
                    "node_group_accept_run",
                    {"device": device, "from_matrix": from_matrix, "group_id": gid},
                ),
            }
        )
    options.extend(
        [
            {
                "key": "a",
                "desc": "Accept (enter id next)",
                "goto": ("node_group_menu_accept_prompt", {"device": device, "from_matrix": from_matrix}),
            },
            {
                "key": "d",
                "desc": "Decline (enter id next)",
                "goto": ("node_group_menu_decline_prompt", {"device": device, "from_matrix": from_matrix}),
            },
            {
                "key": "b",
                "desc": "Back",
                "goto": ("node_view_groups", {"device": device, "from_matrix": from_matrix}),
            },
        ]
    )
    return text, options


def node_group_accept_run(caller, raw_string, **kwargs):
    from world import matrix_groups as mg

    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    gid = (kwargs.get("group_id") or "").strip().upper()
    ok, msg = mg.accept_group_invite(device, gid)
    caller.msg(msg)
    return _node_call(node_view_groups, caller, device=device, from_matrix=from_matrix)


def node_group_menu_accept_prompt(caller, raw_string, **kwargs):
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    text = _group_frame_header("ACCEPT INVITE", device.key)
    text += "Enter the |wgroup id|n (e.g. A7K2M1), or |wb|n to cancel:\n"
    text += _group_frame_footer()
    options = {"key": "_default", "goto": ("node_group_menu_accept_do", {"device": device, "from_matrix": from_matrix})}
    return text, options


def node_group_menu_accept_do(caller, raw_string, **kwargs):
    from world import matrix_groups as mg

    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    s = (raw_string or "").strip()
    if s.lower() == "b" or not s:
        return _node_call(node_view_group_pending, caller, device=device, from_matrix=from_matrix)
    ok, msg = mg.accept_group_invite(device, s.upper())
    caller.msg(msg)
    return _node_call(node_view_groups, caller, device=device, from_matrix=from_matrix)


def node_group_menu_decline_prompt(caller, raw_string, **kwargs):
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    text = _group_frame_header("DECLINE INVITE", device.key)
    text += "Enter the |wgroup id|n, or |wb|n to cancel:\n"
    text += _group_frame_footer()
    options = {"key": "_default", "goto": ("node_group_menu_decline_do", {"device": device, "from_matrix": from_matrix})}
    return text, options


def node_group_menu_decline_do(caller, raw_string, **kwargs):
    from world import matrix_groups as mg

    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    s = (raw_string or "").strip()
    if s.lower() == "b" or not s:
        return _node_call(node_view_group_pending, caller, device=device, from_matrix=from_matrix)
    ok, msg = mg.decline_group_invite(device, s.upper())
    caller.msg(msg)
    return _node_call(node_view_groups, caller, device=device, from_matrix=from_matrix)


def node_view_group_detail(caller, raw_string, **kwargs):
    from world import matrix_groups as mg

    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    gid = (kwargs.get("group_id") or "").strip().upper()
    chats = _as_plain_mapping(getattr(device.db, "group_chats", None) or {})
    data = _as_plain_mapping(chats.get(gid))
    if not isinstance(data, dict):
        return _node_call(node_view_groups, caller, device=device, from_matrix=from_matrix)

    name = data.get("name", gid)
    muted = bool(data.get("muted"))
    unread = mg.get_unread_group_count(device, gid)
    text = _group_frame_header(name, gid)
    text += f"|250Members:|n {len(data.get('members') or [])}  |250Unread:|n {unread}  |250Muted:|n {'yes' if muted else 'no'}\n"
    text += _group_frame_footer()
    text += "|250v|n history  |250s|n send  |250n|n invite  |250m|n mute  |250l|n leave  |250e|n roster  |250b|n back\n"

    base = {"device": device, "from_matrix": from_matrix, "group_id": gid}
    options = [
        {"key": "v", "desc": "View history", "goto": ("node_view_group_history", base)},
        {"key": "s", "desc": "Send message", "goto": ("node_group_send_prompt", base)},
        {"key": "n", "desc": "Invite contact", "goto": ("node_group_invite_prompt", base)},
        {
            "key": "m",
            "desc": "Toggle mute",
            "goto": ("node_group_mute_toggle", base),
        },
        {"key": "l", "desc": "Leave group", "goto": ("node_group_leave_confirm", base)},
        {"key": "e", "desc": "Member list", "goto": ("node_view_group_roster", base)},
        {"key": "b", "desc": "Back", "goto": ("node_view_groups", {"device": device, "from_matrix": from_matrix})},
    ]
    return text, options


def node_group_mute_toggle(caller, raw_string, **kwargs):
    from world import matrix_groups as mg

    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    gid = (kwargs.get("group_id") or "").strip().upper()
    chats = _as_plain_mapping(getattr(device.db, "group_chats", None) or {})
    data = _as_plain_mapping(chats.get(gid))
    if isinstance(data, dict):
        new_m = not bool(data.get("muted"))
        ok, msg = mg.set_group_muted(device, gid, new_m)
        caller.msg(msg)
    return _node_call(node_view_group_detail, caller, device=device, from_matrix=from_matrix, group_id=gid)


def node_view_group_history(caller, raw_string, **kwargs):
    from world import matrix_groups as mg

    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    gid = (kwargs.get("group_id") or "").strip().upper()
    chats = _as_plain_mapping(getattr(device.db, "group_chats", None) or {})
    data = _as_plain_mapping(chats.get(gid))
    if not isinstance(data, dict):
        return _node_call(node_view_groups, caller, device=device, from_matrix=from_matrix)

    msgs = mg.get_group_messages(device, gid, limit=30)
    mg.mark_group_read(device, gid)
    name = data.get("name", gid)
    text = _group_frame_header(f"HISTORY: {name}", "")
    if not msgs:
        text += "|250No messages yet.|n\n"
    else:
        for e in msgs:
            if isinstance(e, dict):
                text += mg.format_inbox_line(device, e) + "\n"
    text += _group_frame_footer()
    options = [
        {
            "key": "b",
            "desc": "Back",
            "goto": ("node_view_group_detail", {"device": device, "from_matrix": from_matrix, "group_id": gid}),
        }
    ]
    return text, options


def node_view_group_roster(caller, raw_string, **kwargs):
    from world import matrix_groups as mg

    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    gid = (kwargs.get("group_id") or "").strip().upper()
    chats = _as_plain_mapping(getattr(device.db, "group_chats", None) or {})
    data = _as_plain_mapping(chats.get(gid))
    if not isinstance(data, dict):
        return _node_call(node_view_groups, caller, device=device, from_matrix=from_matrix)

    members = data.get("members") or []
    admins = set(mg.normalize_matrix_id(str(a)) for a in (data.get("admins") or []))
    text = _group_frame_header("MEMBERS", data.get("name", gid))
    if isinstance(members, list):
        for m in members:
            mid = mg.normalize_matrix_id(str(m))
            disp = device.display_alias_or_id(mid) if hasattr(device, "display_alias_or_id") else mid
            role = "admin" if mid in admins else "member"
            h = mg.lookup_handset(mid)
            if h and h.has_network_coverage():
                sig = "|gonline|n"
            elif h:
                sig = "|yoffline|n"
            else:
                sig = "|xno handset|n"
            text += f"  {disp}  [{role}]  {sig}\n"
    text += _group_frame_footer()
    options = [
        {
            "key": "b",
            "desc": "Back",
            "goto": ("node_view_group_detail", {"device": device, "from_matrix": from_matrix, "group_id": gid}),
        }
    ]
    return text, options


def node_group_send_prompt(caller, raw_string, **kwargs):
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    gid = kwargs.get("group_id")
    text = _group_frame_header("SEND TO GROUP", str(gid))
    text += "Enter your message (|wb|n to cancel):\n"
    text += _group_frame_footer()
    options = {
        "key": "_default",
        "goto": ("node_group_send_do", {"device": device, "from_matrix": from_matrix, "group_id": gid}),
    }
    return text, options


def node_group_send_do(caller, raw_string, **kwargs):
    from world import matrix_groups as mg

    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    gid = (kwargs.get("group_id") or "").strip().upper()
    msg = (raw_string or "").strip()
    if msg.lower() == "b" or not msg:
        return _node_call(node_view_group_detail, caller, device=device, from_matrix=from_matrix, group_id=gid)
    d, tot = mg.send_group_message(device, gid, msg)
    caller.msg(f"|gSent|n |x({d}/{tot} online)|n.")
    return _node_call(node_view_group_detail, caller, device=device, from_matrix=from_matrix, group_id=gid)


def node_group_invite_prompt(caller, raw_string, **kwargs):
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    gid = kwargs.get("group_id")
    text = _group_frame_header("INVITE", str(gid))
    text += "Enter |wcontact alias|n or |wMatrix ID|n (|wb|n to cancel):\n"
    text += _group_frame_footer()
    options = {
        "key": "_default",
        "goto": ("node_group_invite_do", {"device": device, "from_matrix": from_matrix, "group_id": gid}),
    }
    return text, options


def node_group_invite_do(caller, raw_string, **kwargs):
    from world import matrix_groups as mg

    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    gid = (kwargs.get("group_id") or "").strip().upper()
    tok = (raw_string or "").strip()
    if tok.lower() == "b" or not tok:
        return _node_call(node_view_group_detail, caller, device=device, from_matrix=from_matrix, group_id=gid)
    mid = device.resolve_contact_or_id(tok) if hasattr(device, "resolve_contact_or_id") else None
    if not mid:
        caller.msg("|rInvalid contact or ID.|n")
        return _node_call(node_view_group_detail, caller, device=device, from_matrix=from_matrix, group_id=gid)
    ok, msg = mg.invite_to_group(device, gid, mid)
    caller.msg(msg)
    return _node_call(node_view_group_detail, caller, device=device, from_matrix=from_matrix, group_id=gid)


def node_group_create_prompt(caller, raw_string, **kwargs):
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    text = _group_frame_header("NEW GROUP", device.key)
    text += "Enter a |wname|n (2-30 chars), or |wb|n to cancel:\n"
    text += _group_frame_footer()
    options = {
        "key": "_default",
        "goto": ("node_group_create_do", {"device": device, "from_matrix": from_matrix}),
    }
    return text, options


def node_group_create_do(caller, raw_string, **kwargs):
    from world import matrix_groups as mg

    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    name = (raw_string or "").strip()
    if name.lower() == "b" or not name:
        return _node_call(node_view_groups, caller, device=device, from_matrix=from_matrix)
    ok, msg, _gid = mg.create_group(device, name)
    caller.msg(msg)
    return _node_call(node_view_groups, caller, device=device, from_matrix=from_matrix)


def node_group_leave_confirm(caller, raw_string, **kwargs):
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    gid = kwargs.get("group_id")
    text = _group_frame_header("LEAVE GROUP", str(gid))
    text += "|yLeave this group?|n  |wy|n yes  |wn|n no\n"
    text += _group_frame_footer()
    options = [
        {
            "key": "y",
            "desc": "Yes, leave",
            "goto": ("node_group_leave_do", {"device": device, "from_matrix": from_matrix, "group_id": gid}),
        },
        {
            "key": "n",
            "desc": "No",
            "goto": ("node_view_group_detail", {"device": device, "from_matrix": from_matrix, "group_id": gid}),
        },
    ]
    return text, options


def node_group_leave_do(caller, raw_string, **kwargs):
    from world import matrix_groups as mg

    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    gid = (kwargs.get("group_id") or "").strip().upper()
    ok, msg = mg.leave_group(device, gid)
    caller.msg(msg)
    return _node_call(node_view_groups, caller, device=device, from_matrix=from_matrix)


def node_error(caller, raw_string, **kwargs):
    """Error state - device not found or invalid."""
    text = "|rError: Device interface unavailable.|n\n"
    return text, [{"key": "_default", "desc": None, "goto": "node_exit"}]


def node_exit(caller, raw_string, **kwargs):
    """Exit the menu."""
    caller.msg("Disconnecting from device interface.")
    return None


# =========================================================================
# ACL Management Menu Nodes
# =========================================================================

def node_device_acl_list(caller, raw_string, **kwargs):
    """
    Display ACL entries and allow selection for deletion.
    """
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    if not device:
        caller.msg("|rError: No device specified.|n")
        return None

    if not hasattr(device.db, 'acl') or not device.db.acl:
        text = f"|c=== ACL for {device.key} ===|n\n\n"
        text += "No ACL entries (public device).\n"
        return text, [{"key": "q", "desc": "Back to main menu", "goto": ("device_main_menu", {"device": device, "from_matrix": from_matrix})}]

    text = f"|c=== ACL for {device.key} ===|n\n"

    from evennia.objects.models import ObjectDB

    acl_list = []
    for char_pk, level in device.db.acl.items():
        try:
            obj = ObjectDB.objects.get(pk=char_pk)
            if obj.typeclass_path and 'MatrixAvatar' in obj.typeclass_path:
                name = f"{obj.key} (matrix, level {level})"
            else:
                name = f"{obj.key} (physical, level {level})"
        except ObjectDB.DoesNotExist:
            name = f"<err> (<err>, level {level})"
        acl_list.append((char_pk, name))

    options = []
    for i, (char_pk, display_name) in enumerate(acl_list, 1):
        options.append({
            "key": str(i),
            "desc": display_name,
            "goto": ("node_device_acl_confirm", {"device": device, "from_matrix": from_matrix, "char_pk": char_pk, "name": display_name})
        })
    options.append({"key": "q", "desc": "Back to main menu", "goto": ("device_main_menu", {"device": device, "from_matrix": from_matrix})})

    return text, options


def node_device_acl_confirm(caller, raw_string, **kwargs):
    """
    Confirm deletion of an ACL entry.
    """
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    char_pk = kwargs.get("char_pk")
    name = kwargs.get("name")

    if not device or char_pk is None:
        caller.msg("|rError: Invalid parameters.|n")
        return _node_call(node_device_acl_list, caller, device=device, from_matrix=from_matrix)

    text = f"|yConfirm removal of:|n\n"
    text += f"  {name}\n\n"
    text += "This will revoke all access for this user.\n"

    options = [
        {
            "key": "y",
            "desc": "Yes, remove",
            "goto": ("node_device_acl_delete", {"device": device, "from_matrix": from_matrix, "char_pk": char_pk, "name": name})
        },
        {
            "key": "n",
            "desc": "No, go back",
            "goto": ("node_device_acl_list", {"device": device, "from_matrix": from_matrix})
        }
    ]

    return text, options


def node_device_acl_delete(caller, raw_string, **kwargs):
    """
    Delete the ACL entry and return to the list.
    """
    device = kwargs.get("device")
    from_matrix = kwargs.get("from_matrix", False)
    char_pk = kwargs.get("char_pk")
    name = kwargs.get("name")

    if not device or char_pk is None:
        caller.msg("|rError: Invalid parameters.|n")
        return _node_call(node_device_acl_list, caller, device=device, from_matrix=from_matrix)

    if hasattr(device.db, 'acl') and char_pk in device.db.acl:
        del device.db.acl[char_pk]
        caller.msg(f"|gRemoved {name} from ACL.|n")
        try:
            from evennia.objects.models import ObjectDB
            target = ObjectDB.objects.get(pk=char_pk)
            if target.has_account:
                target.msg(f"|rYour access to {device.key} has been revoked.|n")
        except ObjectDB.DoesNotExist:
            pass
    else:
        caller.msg(f"|rEntry not found in ACL.|n")

    return _node_call(node_device_acl_list, caller, device=device, from_matrix=from_matrix)


def start_device_menu(caller, device, from_matrix=False):
    """
    Start the device interface menu.

    Args:
        caller: The character/avatar accessing the device
        device: The networked device being accessed
        from_matrix: True if accessed via cmd.exe in Matrix, False if from meatspace
    """
    if not device:
        caller.msg("|rError: No device specified.|n")
        return

    # Store context
    menu_data = {
        "device": device,
        "from_matrix": from_matrix
    }

    from typeclasses.matrix.menu_formatters import get_matrix_formatters
    EvMenu(
        caller,
        "typeclasses.matrix.device_menu",
        startnode="device_main_menu",
        startnode_input=("", menu_data),
        cmd_on_exit=None,
        persistent=False,
        **get_matrix_formatters(),
        **menu_data
    )
