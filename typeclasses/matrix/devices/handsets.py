"""
Handset Device - Personal Communication Device

A handset is a personal networked device (phone) that provides access to
Matrix communication features like calls, texts, and social media.

The handset authenticates using the holder's Matrix ID (chip implant) and
provides access to their Matrix account settings.

Key features:
- View account info (Matrix ID, alias)
- Set/change Matrix alias
- Future: calls, texts, contacts, camera, social media
"""

import time

from typeclasses.matrix.items import NetworkedItem
from world.matrix_accounts import get_account, set_alias, get_alias, has_alias


class Handset(NetworkedItem):
    """
    Personal communication device (phone).

    Basic handsets authenticate using the holder's Matrix chip ID.
    Future jailbroken devices can have independent IDs.

    Device Commands (physical only):
        account - View your Matrix account info
        set_alias - Set your Matrix alias (@handle)
    """

    def at_object_creation(self):
        """Initialize the handset device."""
        super().at_object_creation()
        self.setup_networked_attrs()

        # Handset-specific attributes
        self.db.device_type = "handset"
        # Handset storage (contacts + text buffer) is per-device.
        self.db.has_storage = False  # Device-framework storage is separate; we use explicit attrs below.
        self.db.has_controls = True  # Has account/communication controls
        self.db.security_level = 0  # Personal device, low security
        self.db.is_jailbroken = False  # Future feature

        # Per-handset contact list (alias -> handset Matrix ID). Stored ONLY on this handset.
        if not getattr(self.db, "contacts", None):
            self.db.contacts = {}

        # Per-handset text buffer (list of dicts). Stored ONLY on this handset.
        if not getattr(self.db, "texts", None):
            self.db.texts = []

        # Per-handset photo album (list of dicts). Stored ONLY on this handset.
        if not getattr(self.db, "photos", None):
            self.db.photos = []
        if not getattr(self.db, "next_photo_id", None):
            self.db.next_photo_id = 1

        # NOTE: Handset player command (`hs`) is now a global Character command
        # to avoid cmdset ambiguity when multiple handsets exist in scope.

        # Register device commands (used by operate / device interface).
        self._ensure_handset_device_commands()

    def at_cmdset_get(self, **kwargs):
        """
        Ensure handset device-commands exist for older handsets too.
        """
        # Remove any legacy handset-local cmdset that could cause ambiguous command matches.
        try:
            self.cmdset.remove("commands.handset_cmdset.HandsetCmdSet")
        except Exception:
            pass
        try:
            self._ensure_handset_device_commands()
        except Exception:
            pass
        return super().at_cmdset_get(**kwargs)

    def _ensure_handset_device_commands(self):
        """
        Ensure the handset has all expected device-commands registered.

        This is safe to call multiple times and helps migrate older handset objects.
        """
        # NetworkedMixin stores these registrations on self.db.device_commands.
        existing = getattr(self.db, "device_commands", None) or {}
        if not isinstance(existing, dict):
            existing = {}
            self.db.device_commands = existing

        if "account" not in existing:
            self.register_device_command(
                "account",
                "handle_account_info",
                help_text="View your Matrix account information",
                auth_level=0,
                visibility_threshold=0,
            )
        if "set_alias" not in existing:
            self.register_device_command(
                "set_alias",
                "handle_set_alias",
                help_text="Set your Matrix alias: set_alias @name",
                auth_level=0,
                physical_only=True,
                visibility_threshold=0,
            )
        if "contacts" not in existing:
            self.register_device_command(
                "contacts",
                "handle_contacts",
                help_text="View your contacts",
                auth_level=0,
                visibility_threshold=0,
            )
        if "messages" not in existing:
            self.register_device_command(
                "messages",
                "handle_messages",
                help_text="View recent text messages (last 24h)",
                auth_level=0,
                visibility_threshold=0,
            )

        if "photos" not in existing:
            # This is primarily used by the device interface menu; it routes to the photo viewer.
            self.register_device_command(
                "photos",
                "handle_photos",
                help_text="View photos saved on this handset",
                auth_level=0,
                visibility_threshold=0,
            )

    def get_authenticated_user(self):
        """
        Get the character currently authenticated on this handset.

        For basic handsets, this is whoever is holding/wearing it.
        Future jailbroken devices may have separate authentication.

        Returns:
            Character or None: The authenticated user
        """
        # For now, handset authenticates whoever is holding it
        if hasattr(self, 'location'):
            from typeclasses.characters import Character
            if isinstance(self.location, Character):
                return self.location
        return None

    def handle_contacts(self, caller, *args):
        """
        Display contacts stored on this handset (device-local).
        """
        contacts = {}
        try:
            contacts = self.get_contacts() or {}
        except Exception:
            raw = getattr(self.db, "contacts", None) or {}
            contacts = raw if isinstance(raw, dict) else {}

        if not contacts:
            caller.msg("No contacts saved on this handset.")
            return True

        lines = ["|c=== Handset Contacts (max 15) ===|n"]
        for alias in sorted(contacts.keys()):
            lines.append(f"|w{alias}|n: {contacts[alias]}")
        caller.msg("\n".join(lines))
        return True

    def _prune_texts_24h(self):
        """
        Prune the handset-local text buffer to the last 24 hours.

        Entries are dicts like:
          {"t": <epoch seconds>, "ts": "<display timestamp>", "from": "^ID", "msg": "..."}
        Legacy entries without "t" are dropped when pruning.
        """
        cutoff = time.time() - 86400
        raw = list(getattr(self.db, "texts", []) or [])
        kept = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            t = entry.get("t", None)
            if t is None:
                continue
            try:
                if float(t) >= cutoff:
                    kept.append(entry)
            except Exception:
                continue
        if kept != raw:
            self.db.texts = kept
        return kept

    def add_text_message(self, sender_id: str, msg: str, ts_display: str):
        """
        Add a text message to this handset's buffer.

        Pruning is handled by a server-side cleanup script so opening/viewing the
        menu won't unexpectedly delete messages.
        """
        sender_id = (sender_id or "").strip()
        msg = (msg or "").strip()
        if not sender_id or not msg:
            return False
        if not sender_id.startswith("^"):
            sender_id = "^" + sender_id
        entry = {"t": time.time(), "ts": ts_display, "from": sender_id, "msg": msg}
        raw = list(getattr(self.db, "texts", []) or [])
        raw.append(entry)
        self.db.texts = raw
        return True

    def get_text_messages(self):
        """
        Get stored text messages.

        Note: Pruning is done by a timed server script, not on view.
        """
        return list(getattr(self.db, "texts", []) or [])

    def handle_messages(self, caller, *args):
        """
        Display handset text buffer (last 24 hours).
        """
        # Do not prune on view; cleanup script keeps this within 24h.
        msgs = self.get_text_messages()
        if not msgs:
            caller.msg("No recent texts on this handset (last 24 hours).")
            return True
        lines = [f"|c=== Messages on {self.key} (last 24h) ===|n"]
        for entry in msgs[-50:]:
            ts = entry.get("ts", "")
            frm = entry.get("from", "")
            msg = entry.get("msg", "")
            display = self.display_alias_or_id(frm)
            lines.append(f"[{ts}]{display}: {msg}")
        caller.msg("\n".join(lines))

        # Mark messages as "viewed" for notification counts.
        try:
            self.db.last_texts_viewed_t = time.time()
        except Exception:
            pass
        return True

    # -------------------------------------------------------------------------
    # Handset photo album (device-local)
    # -------------------------------------------------------------------------

    def add_photo(self, kind: str, title: str, snapshot_text: str, ts_display: str, snapshot_chars: dict | None = None):
        """
        Store a photo/selfie in the handset-local album.
        """
        kind = (kind or "photo").strip().lower()
        title = (title or "").strip()
        snapshot_text = (snapshot_text or "").rstrip()
        ts_display = (ts_display or "").strip()
        snapshot_chars = snapshot_chars or {}
        
        if not snapshot_text:
            return False

        # Assign the lowest available numeric id (fill gaps after deletions).
        current_photos = getattr(self.db, "photos", None)
        if current_photos is None:
            current_photos_list = []
        elif not isinstance(current_photos, list):
            try:
                from collections.abc import Iterable
            except Exception:
                Iterable = None
            if Iterable is not None and isinstance(current_photos, Iterable) and not isinstance(current_photos, (str, bytes)):
                current_photos_list = list(current_photos)
            else:
                current_photos_list = []
        else:
            current_photos_list = list(current_photos)

        used = set()
        for p in current_photos_list:
            try:
                pid = int((p or {}).get("id"))
                if pid > 0:
                    used.add(pid)
            except Exception:
                continue
        next_id = 1
        while next_id in used:
            next_id += 1

        entry = {
            "id": next_id,
            "t": time.time(),
            "ts": ts_display,
            "kind": kind,
            "title": title,
            "text": snapshot_text,
            "chars": snapshot_chars,
        }

        try:
            # Keep for any UI that wants a monotonic counter, but ids themselves fill gaps.
            self.db.next_photo_id = max(int(getattr(self.db, "next_photo_id", 1) or 1), next_id + 1)
        except Exception:
            pass

        # Always assign a fresh list object (avoid in-place mutation edge cases).
        new_photos = list(current_photos_list)
        new_photos.append(entry)

        # Keep album bounded
        if len(new_photos) > 100:
            new_photos = new_photos[-100:]

        try:
            self.db.photos = new_photos
        except Exception:
            pass
        
        return entry["id"]

    def handle_photos(self, caller, *args):
        """
        Open the handset photo viewer (device interface menu node).
        """
        try:
            from evennia import EvMenu
            from typeclasses.matrix.menu_formatters import get_matrix_formatters
        except Exception:
            caller.msg("|rPhoto viewer unavailable.|n")
            return False
        # Determine Matrix vs physical context for formatting.
        try:
            from typeclasses.matrix.avatars import MatrixAvatar
            from_matrix = isinstance(caller, MatrixAvatar)
        except Exception:
            from_matrix = False
        EvMenu(
            caller,
            "typeclasses.matrix.device_menu",
            startnode="node_view_photos",
            startnode_input=("", {"device": self, "from_matrix": from_matrix}),
            cmd_on_exit=None,
            persistent=False,
            **get_matrix_formatters(),
            device=self,
            from_matrix=from_matrix,
        )
        return True

    def get_photos(self):
        """Return list of photo dicts (oldest -> newest)."""
        raw = getattr(self.db, "photos", None)
        if raw is None:
            return []
        # Evennia may deserialize Attributes into SaverList/SaverDict variants.
        # Treat them as list/dict-like rather than requiring exact builtins.
        try:
            from collections.abc import Iterable, Mapping
        except Exception:
            Iterable = None
            Mapping = None

        if not isinstance(raw, list) and not isinstance(raw, tuple):
            if Iterable is None or not isinstance(raw, Iterable) or isinstance(raw, (str, bytes)):
                return []

        out = []
        for p in list(raw):
            if Mapping is not None:
                if isinstance(p, Mapping):
                    out.append(dict(p))
            else:
                if isinstance(p, dict):
                    out.append(p)
        return out

    def get_photo_by_id(self, photo_id: int):
        """Find a photo dict by its stored numeric id."""
        try:
            pid = int(photo_id)
        except Exception:
            return None
        for entry in self.get_photos():
            try:
                if int(entry.get("id", -1)) == pid:
                    return entry
            except Exception:
                continue
        return None

    def _get_user_from_caller(self, caller):
        """
        Get the actual user character from a caller.

        For physical access, caller is the character directly.
        For Matrix access, caller might be an avatar - get the operator.

        Args:
            caller: The caller (Character or MatrixAvatar)

        Returns:
            Character or None: The user character
        """
        from typeclasses.characters import Character
        if isinstance(caller, Character):
            return caller

        # Check if it's a Matrix avatar with an operator
        if hasattr(caller, 'db') and hasattr(caller.db, 'operator'):
            return caller.db.operator

        return None

    def handle_account_info(self, caller, *args):
        """
        Display the user's Matrix account information.

        Shows:
        - Matrix ID (chip ID)
        - Current alias (if set)
        - Future: account creation date, reputation, etc.

        Authenticates via whoever is holding the handset (works from Matrix or physical).

        Args:
            caller: The character/avatar using the command

        Returns:
            bool: Always True
        """
        # Always authenticate via who's holding the device
        user = self.get_authenticated_user()
        if not user:
            caller.msg("|rHandset authentication failed. Nobody is holding this device.|n")
            return False

        # Get account data
        account = get_account(user)
        matrix_id = account.get('matrix_id') or 'Not assigned'
        alias = account.get('alias') or '|x(not set)|n'

        # Build display
        caller.msg("|c" + "=" * 50 + "|n")
        caller.msg("|c=== Matrix Account Information ===|n")
        caller.msg("|c" + "=" * 50 + "|n")
        caller.msg(f"\n|wMatrix ID:|n {matrix_id}")

        # Display alias with @ prefix (UI decoration)
        if account.get('alias'):
            caller.msg(f"|wAlias:|n @{alias}")
        else:
            caller.msg(f"|wAlias:|n |x(not set)|n")
            caller.msg("\n|yYou haven't set an alias yet.|n")
            caller.msg("Set one with: |wset_alias @yourname|n")

        if account.get('created'):
            caller.msg(f"\n|xAccount created: {account['created']}|n")

        caller.msg("|c" + "=" * 50 + "|n")

        return True

    def handle_set_alias(self, caller, *args):
        """
        Set the user's Matrix alias.

        Usage: set_alias @newname

        The alias must:
        - Start with @
        - Be 2-10 characters
        - Contain only letters, numbers, underscore
        - Be unique (not taken by another user)

        Args:
            caller: The character using the command
            *args: The desired alias

        Returns:
            bool: True on success, False on failure
        """
        user = self._get_user_from_caller(caller)
        if not user:
            caller.msg("|rHandset authentication failed.|n")
            return False

        if not args:
            # Show current alias and usage
            current_alias = get_alias(user)
            if current_alias:
                caller.msg(f"Your current alias is: |w@{current_alias}|n")
            else:
                caller.msg("You don't have an alias set yet.")

            caller.msg("\n|wUsage:|n set_alias @yourname")
            caller.msg("\nAlias must be 2-10 characters and contain only letters, numbers, and underscores.")
            caller.msg("Example: set_alias @runner")
            return False

        # Get the desired alias
        new_alias = args[0].strip()

        # Attempt to set it
        success, message = set_alias(user, new_alias)

        if success:
            caller.msg(f"|g{message}|n")
        else:
            caller.msg(f"|r{message}|n")

        return success

    def return_appearance(self, looker, **kwargs):
        """
        Customize how the handset appears when examined.

        Args:
            looker: The object examining this handset
            **kwargs: Additional arguments

        Returns:
            str: Description of the handset
        """
        # Get base appearance
        text = super().return_appearance(looker, **kwargs)

        # Show authentication status if holder is looking
        user = self.get_authenticated_user()
        if user and user == looker:
            matrix_id = user.get_matrix_id() if hasattr(user, 'get_matrix_id') else None
            if matrix_id:
                text += f"\n|gAuthenticated to your Matrix chip: {matrix_id}|n"

            # Show alias if set (with @ prefix for display)
            alias = get_alias(user)
            if alias:
                text += f"\n|wMatrix alias: @{alias}|n"

        # Show network status
        if self.has_network_coverage():
            text += "\n|g[ONLINE]|n Connected to Matrix network."
        else:
            text += "\n|r[OFFLINE]|n No network coverage."

        return text

    # -------------------------------------------------------------------------
    # Handset phone/text helpers (used by handset commands).
    # -------------------------------------------------------------------------

    def get_phone_number(self):
        """Phone number for this handset: its Matrix ID."""
        return self.get_matrix_id()

    def get_contacts(self):
        """Return contacts dict (alias_lower -> matrix_id)."""
        contacts = getattr(self.db, "contacts", None)
        if not isinstance(contacts, dict):
            contacts = {}
            self.db.contacts = contacts
        # Normalize keys to lowercase for matching.
        normalized = {}
        for k, v in contacts.items():
            if not k or not v:
                continue
            normalized[str(k).strip().lower()] = str(v).strip()
        if normalized != contacts:
            self.db.contacts = normalized
        return normalized

    def save_contact(self, matrix_id: str, alias: str):
        """Save a contact on this handset."""
        matrix_id = (matrix_id or "").strip()
        alias = (alias or "").strip()
        if not matrix_id or not alias:
            return False, "Usage: handset save <ID> as <alias>"
        if not matrix_id.startswith("^"):
            matrix_id = "^" + matrix_id
        contacts = self.get_contacts()
        # Enforce max contacts per handset (15). Updating an existing alias does not count as a new slot.
        if alias.lower() not in contacts and len(contacts) >= 15:
            return False, "|rContact list full.|n Max 15 contacts per handset."
        contacts[alias.lower()] = matrix_id
        self.db.contacts = contacts
        return True, f"|gSaved|n {matrix_id} as |w{alias}|n."

    def resolve_contact_or_id(self, raw: str):
        """
        Resolve an input token to a handset Matrix ID.
        Accepts:
          - a Matrix ID with or without '^'
          - a saved contact alias (case-insensitive)
        """
        raw = (raw or "").strip()
        if not raw:
            return None
        contacts = self.get_contacts()
        key = raw.lower()
        if key in contacts:
            return contacts[key]
        # Treat as raw ID, allow missing prefix.
        if raw.startswith("^"):
            return raw
        # If it looks like a 6-char base32 token, allow it.
        if len(raw) == 6:
            return "^" + raw.upper()
        return "^" + raw

    def display_alias_or_id(self, matrix_id: str):
        """Return saved alias for matrix_id if present, else matrix_id."""
        matrix_id = (matrix_id or "").strip()
        if not matrix_id:
            return ""
        if not matrix_id.startswith("^"):
            matrix_id = "^" + matrix_id
        for alias, mid in self.get_contacts().items():
            if str(mid).strip().upper() == matrix_id.upper():
                return alias
        return matrix_id

    def _call_state(self):
        return str(getattr(self.ndb, "call_state", "idle") or "idle")

    def _set_call_state(self, state: str, peer_dbref: int | None = None):
        self.ndb.call_state = state
        self.ndb.call_peer = peer_dbref

