import random
import string
from typing import Iterable

# --- Your Existing Config ---

DECOY_COUNT_RANGE = (8, 10)

TAG_POOL: list[str] = [
    "just vibing", "afk 2m", "anyone got wheels?", "need a doc. asap.",
    "looking for work", "coffee run?", "don't @ me", "where's the party?",
]

def _fallback_alias(*, max_len: int) -> str:
    if max_len <= 1: return "x"
    first = random.choice(string.ascii_lowercase)
    rest = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(max_len - 1))
    return first + rest

def _fallback_tag(*, max_len: int) -> str:
    raw = random.choice(TAG_POOL) if TAG_POOL else "..."
    return raw[:max_len]

# --- The Main Function ---

def generate_decoy_entries(
    *,
    count: int,
    id_col_width: int,
    tag_col_width: int,
    existing_aliases: Iterable[str] = (),
) -> list[tuple[str, str]]:
    existing = {str(a).strip().lower() for a in existing_aliases if a}
    rows: list[tuple[str, str]] = []

    # Try to get Faker for names
    fake = None
    try:
        from faker import Faker
        fake = Faker()
    except Exception:
        fake = None

    attempts = 0
    while len(rows) < max(0, int(count)) and attempts < 200:
        attempts += 1

        # 1. Generate Alias (Using Faker or Fallback)
        if fake:
            alias = str(fake.user_name() or "").strip()
        else:
            alias = _fallback_alias(max_len=max(3, min(id_col_width, 14)))

        # 2. Generate Tag (From the shared tag pool)
        tag = _fallback_tag(max_len=tag_col_width)

        # Clean up strings
        alias = alias.replace("\r", "").replace("\n", "").strip()
        # Ensure decoy aliases are displayed as handles.
        # Keep within the fixed ID column width.
        if alias:
            alias = "@" + alias.lstrip("@")
        else:
            alias = "@x"
        alias = alias[:id_col_width]
        tag = tag.replace("\r", " ").replace("\n", " ").strip()[:tag_col_width]

        if not alias:
            continue

        key = alias.lower()
        if key in existing:
            continue

        existing.add(key)
        rows.append((alias, tag))

    return rows