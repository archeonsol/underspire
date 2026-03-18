"""
Player-facing PC note commands.

@add-note   - create a categorized note using EvEditor.
@notes      - list/view your character's saved notes.
@notesearch - search your notes by category.
"""

from __future__ import annotations

from datetime import datetime

from evennia.utils.eveditor import EvEditor
from commands.base_cmds import Command, _command_character


def _format_server_time(created_at: str | None, *, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Convert stored UTC ISO timestamps into server-local time for display.
    """
    if not created_at:
        return "?"
    try:
        dt = datetime.fromisoformat(created_at)
    except ValueError:
        # Fallback: if it's not ISO-ish, just show the raw value.
        return str(created_at)

    # datetime.astimezone() with no args converts to the local timezone.
    try:
        dt = dt.astimezone()
    except Exception:
        pass

    # Keep it short/readable for players.
    return dt.strftime(fmt)


def _truncate(text: str | None, *, limit: int) -> str:
    """
    Truncate long strings for compact list display.
    """
    if text is None:
        return ""
    txt = str(text).strip()
    if len(txt) <= limit:
        return txt
    # ASCII-only suffix to keep telnet safe.
    return txt[: max(0, limit - 3)] + "..."


def _border_line() -> str:
    # Keep it short so it doesn't wrap on typical telnet widths.
    return f"|g{'-' * 38}|n"


def _note_list_line(note: dict[str, object], *, time_fmt: str) -> str:
    note_id = note.get("id")
    cat = str(note.get("category") or "UNCATEGORIZED").strip().upper()
    title = _truncate(note.get("title", ""), limit=42)
    created_at = note.get("created_at")

    time_txt = _format_server_time(str(created_at) if created_at else None, fmt=time_fmt)
    return (
        f"  |x#{note_id}|n  |c{cat}|n  |w{title}|n"
        f" |x({time_txt})|n"
    )


def _render_notes_header(*, page: int, max_page: int, mode: str, category: str | None = None) -> list[str]:
    """
    mode:
      - "list": @notes
      - "search": @notesearch
    """
    if mode == "search":
        return [
            _border_line(),
            f"|gNotes|n in |c{(category or '').strip().upper()}|n  |x(page {page}/{max_page}, newest first)|n",
            "Use |w@notes <id>|n to view, |w@notesearch <category>/page <N>|n for another page."
        ]
    return [
        _border_line(),
        f"|gNotes|n  |x(page {page}/{max_page}, newest first)|n",
        "Use |w@notes <id>|n to view, |w@notes/page <N>|n for another page."
    ]


class CmdAddNote(Command):
    """
    Add a character note (stored and viewable later).

    Usage:
      @add-note
    """

    key = "@add-note"
    aliases = ["@addnote", "@add_note"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.notes import DEFAULT_CATEGORIES, add_note

        caller = self.caller
        char = _command_character(self)
        if not getattr(char, "db", None):
            caller.msg("You must be in character to add a note.")
            return

        # --- STEP 1: Category Selection ---
        categories = list(DEFAULT_CATEGORIES)
        cats_txt = "\n".join(
            f"  |y{idx})|n |c{cat}|n" for idx, cat in enumerate(categories, start=1)
        )

        caller.msg(
            f"{_border_line()}\n"
            f"|gAdd a note|n\n"
            f"|wChoose a category by number:{'' if cats_txt else ''}\n"
            f"{cats_txt}\n"
            f"{_border_line()}"
        )

        # The 'yield' pauses the command and waits for the player to type
        cat_input = yield "Type the number (or 'cancel' to abort): "

        if cat_input.lower() in ("cancel", "c", "quit", "q"):
            caller.msg("|yNote creation cancelled.|n")
            return

        try:
            idx = int(cat_input)
            if idx < 1 or idx > len(categories):
                raise ValueError
            category = categories[idx - 1]
        except ValueError:
            caller.msg("|rInvalid category number. Note creation cancelled.|n")
            return

        caller.msg(f"Category set to |w{category}|n.")

        # --- STEP 2: Title Selection ---
        title_input = yield "Enter a short title for this note (or 'cancel'): "

        if title_input.lower() in ("cancel", "c", "quit", "q"):
            caller.msg("|yNote creation cancelled.|n")
            return

        title = title_input.strip()
        if not title:
            caller.msg("|rTitle cannot be empty. Note creation cancelled.|n")
            return

        # --- STEP 3: The EvEditor Body ---
        # These functions dictate what happens when the player saves or quits the editor.
        
        def _save_note(editor_caller, buffer):
            if not buffer.strip():
                editor_caller.msg("|yNote body empty; note discarded.|n")
                return

            account = getattr(self, "account", None) or getattr(editor_caller, "account", None) or editor_caller
            
            note = add_note(character=char, account=account, category=category, title=title, body=buffer.strip())
            editor_caller.msg(f"|gSaved note|n |w#{note['id']}|n: |w{note['title']}|n (|c{note['category']}|n).")
            
            # Leave a flag telling the quit function we successfully saved!
            editor_caller.ndb._eveditor_just_saved = True

        def _quit_note(editor_caller):
            # Check if we just saved the note
            if getattr(editor_caller.ndb, "_eveditor_just_saved", False):
                # Clean up the flag and exit quietly (or print a nice exit message)
                del editor_caller.ndb._eveditor_just_saved
                editor_caller.msg("|wExited note editor.|n")
            else:
                # They typed :q without saving
                editor_caller.msg("|yNote creation aborted. Nothing was saved.|n")

        # Launch the built-in Evennia Editor
        EvEditor(
            caller,
            loadfunc=None,
            savefunc=_save_note,
            quitfunc=_quit_note,
            key=f"Note: {title}" # This sets the title header in the editor interface
        )


class CmdNotes(Command):
    """
    View your character notes (with paging).

    Usage:
      @notes                - list your notes (newest first, first page)
      @notes <id>           - view a note by id
      @notes/page <N>       - list page N (10 per page)
    """

    key = "@notes"
    aliases = ["@note", "@mynotes"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.notes import notes_for_character, get_note_by_id

        caller = self.caller
        char = _command_character(self)
        if not getattr(char, "db", None):
            caller.msg("You must be in character to view notes.")
            return

        switches = [s.lower() for s in getattr(self, "switches", [])]
        arg = (self.args or "").strip()
        page = 1

        # Fallback parsing: support "@notes/page <N>" even if the command base
        # doesn't populate `self.switches` (some templates only set `self.args`).
        if not switches and arg:
            import re

            m = re.match(r"^(?:/)?page\s+(?P<num>\d+)\s*$", arg, flags=re.I)
            if m:
                page = max(1, int(m.group("num")))
                arg = ""  # don't treat it like a note ID

        # Lookup a specific note by ID
        if arg and not switches:
            note = get_note_by_id(arg)
            if not note or note.get("char_id") != getattr(char, "id", None):
                caller.msg("No such note (or it isn't yours).")
                return
                
            caller.msg(
                f"{_border_line()}\n"
                f"|gNote|n |y#{note['id']}|n  |c{note.get('category') or 'UNCATEGORIZED'}|n\n"
                f"|w{note.get('title') or '(untitled)'}|n\n\n"
                f"|xBy|n: |w{note.get('char_key') or 'Unknown'}|n\n"
                f"|xCreated|n: |x({_format_server_time(note.get('created_at'))})|n\n"
                f"{_border_line()}\n"
                f"{note.get('body') or ''}"
            )
            return

        notes = notes_for_character(char)
        if not notes:
            caller.msg("You have no saved notes. Use |w@add-note|n to create one.")
            return

        # Pagination Logic
        if "page" in switches and arg:
            try:
                page = max(1, int(arg))
            except ValueError:
                page = 1
                
        per_page = 10
        total = len(notes)
        max_page = (total + per_page - 1) // per_page or 1
        page = min(page, max_page) # Ensure page doesn't exceed max
        
        start = (page - 1) * per_page
        end = start + per_page
        page_notes = notes[start:end]

        lines = _render_notes_header(page=page, max_page=max_page, mode="list")
        for n in page_notes:
            lines.append(_note_list_line(n, time_fmt="%Y-%m-%d %H:%M"))
            
        caller.msg("\n".join(lines))


class CmdNoteSearch(Command):
    """
    Search your notes by category (with paging).

    Usage:
      @notesearch <category>            - newest first, page 1
      @notesearch <category>/page <N>   - specific page (10 per page)
    """

    key = "@notesearch"
    aliases = ["@note-search", "@searchnotes"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.notes import notes_for_character, DEFAULT_CATEGORIES

        caller = self.caller
        char = _command_character(self)
        if not getattr(char, "db", None):
            caller.msg("You must be in character to search notes.")
            return

        arg = (self.args or "").strip()
        if not arg:
            cats_txt = ", ".join(DEFAULT_CATEGORIES)
            caller.msg(
                "Usage: @notesearch <category> or @notesearch <category>/page <N>\n"
                f"Categories: |w{cats_txt}|n"
            )
            return

        import re

        page = 1
        category = arg

        # Fallback parsing: support "@notesearch IC/page <N>" even if the command
        # base doesn't populate `self.switches`.
        m = re.match(r"^(?P<cat>[^/]+)/page(?:\s+(?P<num>\d+))?\s*$", arg, flags=re.I)
        if m:
            category = (m.group("cat") or "").strip()
            if m.group("num"):
                page = max(1, int(m.group("num")))
        else:
            switches = [s.lower() for s in getattr(self, "switches", [])]

            if "page" in switches:
                # In some setups the page number may be `self.args`, while the
                # category is held in `self.lhs`.
                lhs = (getattr(self, "lhs", None) or "").strip()
                if arg.isdigit():
                    page = max(1, int(arg))
                    if lhs:
                        category = lhs
                else:
                    parts = arg.rsplit(" ", 1)
                    if len(parts) == 2 and parts[1].isdigit():
                        category, page_raw = parts[0], parts[1]
                        page = max(1, int(page_raw))

        category = category.strip().upper()
        if category not in DEFAULT_CATEGORIES:
            cats_txt = ", ".join(DEFAULT_CATEGORIES)
            caller.msg(f"|rInvalid category.|n Choose one of: |w{cats_txt}|n.")
            return

        notes = notes_for_character(char, category=category)
        if not notes:
            caller.msg(f"No notes found in category |w{category}|n.")
            return

        per_page = 10
        total = len(notes)
        max_page = (total + per_page - 1) // per_page or 1
        page = min(page, max_page)
        
        start = (page - 1) * per_page
        end = start + per_page
        page_notes = notes[start:end]

        lines = _render_notes_header(page=page, max_page=max_page, mode="search", category=category)
        for n in page_notes:
            lines.append(_note_list_line(n, time_fmt="%Y-%m-%d %H:%M"))
            
        caller.msg("\n".join(lines))