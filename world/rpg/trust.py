"""
Consent as mechanics: trust categories keyed by recog name (identity), not dbref.
See plan: trusting character stores character.db.trust = { name_key: set(categories) }.
"""
import time

from world.rp_features import HELMET_RECOG_REF2RECOG, get_helmet_recog_for_viewer

TRUST_CATEGORIES = {
    "heal": {
        "key": "heal",
        "desc": "Allow this person to perform medical treatment on you.",
        "systems": ["medical_menu", "medical_treatment"],
    },
    "operate": {
        "key": "operate",
        "desc": "Allow this person to perform surgery on you, including cybersurgery.",
        "systems": ["medical_surgery", "cybersurgery"],
    },
    "skinweave": {
        "key": "skinweave",
        "desc": "Allow this person to install or adjust skinweave on you.",
        "systems": ["cybersurgery", "skinweave"],
    },
    "grapple": {
        "key": "grapple",
        "desc": "Do not resist when this person grapples you.",
        "systems": ["grapple"],
    },
    "strip": {
        "key": "strip",
        "desc": "Allow this person to remove clothing and items from you.",
        "systems": ["clothing", "frisk"],
    },
    "dress": {
        "key": "dress",
        "desc": "Allow this person to put clothing on you.",
        "systems": ["clothing"],
    },
    "escort": {
        "key": "escort",
        "desc": "Allow this person to lead you when they move.",
        "systems": ["escort", "movement"],
    },
    "cuff": {
        "key": "cuff",
        "desc": "Allow this person to restrain you without resistance.",
        "systems": ["restraint", "cuff"],
    },
    "tattoo": {
        "key": "tattoo",
        "desc": "Allow this person to tattoo or brand you.",
        "systems": ["tattoo", "body_modification"],
    },
    "runecarve": {
        "key": "runecarve",
        "desc": "Allow this person to carve spiritual runes onto your body.",
        "systems": ["rune_carving"],
    },
    "feed": {
        "key": "feed",
        "desc": "Allow this person to force-feed you food, drink, or drugs.",
        "systems": ["feed", "dose"],
    },
    "collect": {
        "key": "collect",
        "desc": "Allow this person to collect biological specimens from you.",
        "systems": ["alchemy_collection"],
    },
    "protect": {
        "key": "protect",
        "desc": "Allow this person to bodyguard you — intercepting attacks meant for you.",
        "systems": ["protect", "bodyguard"],
    },
    "shackle": {
        "key": "shackle",
        "desc": "Allow this person to shackle or chain you.",
        "systems": ["shackle", "restraint"],
    },
    "force": {
        "key": "force",
        "desc": "Allow this person to force you into or out of vehicles and containers.",
        "systems": ["vehicle", "force_move"],
    },
    "makeup": {
        "key": "makeup",
        "desc": "Allow this person to apply cosmetics to you.",
        "systems": ["cosmetics", "makeup"],
    },
}

TRUST_CATEGORY_KEYS = sorted(TRUST_CATEGORIES.keys())


def _norm_key(name):
    return (name or "").strip().lower()


def _coerce_trust_category_iterable(iterable):
    """Turn an iterable of category tokens into a normalized set of strings."""
    out = set()
    for x in iterable:
        if x is None:
            continue
        if isinstance(x, str):
            nk = _norm_key(x)
            if nk:
                out.add(nk)
        else:
            try:
                out.add(_norm_key(str(x)))
            except Exception:
                pass
    return out


def _entry_to_set(entry):
    """
    Normalize trust bucket values to a set of lowercase category strings.
    Evennia may persist sets as tuples or as `_SaverSet` (not isinstance(..., set)).
    """
    if entry is None:
        return set()
    if isinstance(entry, str):
        nk = _norm_key(entry)
        return {nk} if nk else set()
    if isinstance(entry, (dict, bytes)):
        return set()
    if isinstance(entry, (list, tuple, set, frozenset)):
        return _coerce_trust_category_iterable(entry)
    # Evennia `_SaverSet`: iterable via __iter__ but not a built-in set
    try:
        return _coerce_trust_category_iterable(entry)
    except TypeError:
        return set()


def _helmet_recog_names(character):
    """Lowercase names from helmet/mask overlay table."""
    out = set()
    try:
        ref2 = character.attributes.get(HELMET_RECOG_REF2RECOG, default={}) or {}
        for v in ref2.values():
            nk = _norm_key(v)
            if nk:
                out.add(nk)
    except Exception:
        pass
    return out


def _permanent_recog_names(character):
    out = set()
    try:
        if hasattr(character, "recog") and callable(getattr(character.recog, "all", None)):
            for recog_name, _obj in (character.recog.all() or {}).items():
                nk = _norm_key(recog_name)
                if nk:
                    out.add(nk)
    except Exception:
        pass
    return out


def _is_valid_trust_name(character, name_key):
    """Name must match a permanent recog label or a helmet-only label."""
    nk = _norm_key(name_key)
    if not nk:
        return False
    if nk in _permanent_recog_names(character):
        return True
    if nk in _helmet_recog_names(character):
        return True
    return False


def _get_recog_name(character, actor):
    """
    How `character` labels `actor` for trust lookup — helmet overlay first (if masked),
    then permanent recog, aligned with get_display_name_for_viewer.
    """
    if not character or not actor:
        return None
    if character == actor:
        return None
    try:
        from world.rpg.sdesc import character_has_mask_or_helmet

        if character_has_mask_or_helmet(actor):
            temp = get_helmet_recog_for_viewer(character, actor)
            if temp:
                return _norm_key(temp)
    except Exception:
        pass
    if hasattr(character, "recog") and callable(getattr(character.recog, "get", None)):
        r = character.recog.get(actor)
        if r:
            return _norm_key(r)
    return None


def grant_trust(character, name_str, category=None):
    """
    Grant trust to a recog'd identity (name_str).
    category None => complete trust {"all"}.
    Returns (success, message).
    """
    if not character or not getattr(character, "db", None):
        return False, "Invalid."
    name_key = _norm_key(name_str)
    if not name_key:
        return False, "Trust whom?"

    if not _is_valid_trust_name(character, name_key):
        return False, f"You don't recognize anyone as '{name_str}'. Recog them first."

    trust = dict(getattr(character.db, "trust", None) or {})

    if category is None:
        trust[name_key] = {"all"}
        character.db.trust = trust
        return True, "You now trust them completely."

    cat = _norm_key(category)
    if cat not in TRUST_CATEGORIES:
        valid = ", ".join(TRUST_CATEGORY_KEYS)
        return False, f"Unknown trust category. Valid options: {valid}"

    current = _entry_to_set(trust.get(name_key))
    if "all" in current:
        return False, "You already trust them completely."

    current.add(cat)
    trust[name_key] = current
    character.db.trust = trust
    return True, f"You now trust them to: {cat}."


def revoke_trust(character, name_str=None, revoke_all_people=False):
    if not character or not getattr(character, "db", None):
        return False, "Invalid."
    if revoke_all_people:
        character.db.trust = {}
        return True, "Trust revoked from everyone."

    name_key = _norm_key(name_str)
    if not name_key:
        return False, "Untrust whom?"

    trust = dict(getattr(character.db, "trust", None) or {})
    if name_key not in trust:
        return False, f"You don't trust anyone named '{name_str}'."

    del trust[name_key]
    character.db.trust = trust
    return True, "Trust revoked."


def revoke_trust_category(character, name_str, category):
    if not character or not getattr(character, "db", None):
        return False, "Invalid."
    name_key = _norm_key(name_str)
    cat = _norm_key(category)
    if cat not in TRUST_CATEGORIES:
        return False, "Unknown category."

    trust = dict(getattr(character.db, "trust", None) or {})
    if name_key not in trust:
        return False, f"You don't trust anyone named '{name_str}'."

    current = _entry_to_set(trust.get(name_key))
    if "all" in current:
        current = set(TRUST_CATEGORY_KEYS) - {cat}
        trust[name_key] = current
        character.db.trust = trust
        return True, f"Complete trust revoked. They can still: {', '.join(sorted(current))}."

    if cat not in current:
        return False, f"You don't trust them for '{cat}'."

    current.discard(cat)
    if not current:
        del trust[name_key]
    else:
        trust[name_key] = current
    character.db.trust = trust
    return True, f"Trust for '{cat}' revoked from {name_str}."


def _staff_bypass(actor):
    try:
        acc = getattr(actor, "account", None)
        if acc and (acc.permissions.check("Builder") or acc.permissions.check("Admin")):
            return True
    except Exception:
        pass
    return False


def _category_allowed(entry_set, category):
    """entry_set is lowercase category strings plus maybe 'all'."""
    if "all" in entry_set:
        return True
    cat = _norm_key(category)
    if cat == "heal":
        if "heal" in entry_set or "operate" in entry_set:
            return True
    if cat == "operate":
        if "operate" in entry_set or "skinweave" in entry_set:
            return True
    if cat == "skinweave":
        if "skinweave" in entry_set or "operate" in entry_set:
            return True
    return cat in entry_set


def check_trust_operate_strict(character, actor):
    """
    True for trauma/organ surgery: @trust to operate, or complete trust.
    Skinweave-only trust does not authorize opening a chest or pinning a bone.
    """
    if not character or not actor:
        return False
    if character == actor:
        return True
    if _staff_bypass(actor):
        return True
    recog_name = _get_recog_name(character, actor)
    if not recog_name:
        return False
    trust = getattr(character.db, "trust", None) or {}
    entry = trust.get(recog_name)
    if entry is None:
        return False
    entry_set = _entry_to_set(entry)
    if "all" in entry_set:
        return True
    return "operate" in entry_set


def check_trust(character, actor, category):
    if not character or not actor:
        return False
    if character == actor:
        return True
    if _staff_bypass(actor):
        return True

    recog_name = _get_recog_name(character, actor)
    if not recog_name:
        return False

    trust = getattr(character.db, "trust", None) or {}
    entry = trust.get(recog_name)
    if entry is None:
        return False

    entry_set = _entry_to_set(entry)
    return _category_allowed(entry_set, category)


def check_trust_or_incapacitated(character, actor, category, operate_strict=False):
    """
    If category is operate and operate_strict is True, use check_trust_operate_strict
    (skinweave-only does not count) for the trust portion.
    """
    if operate_strict and category == "operate":
        trusted = check_trust_operate_strict(character, actor)
    else:
        trusted = check_trust(character, actor, category)
    if trusted:
        return True, "trusted"

    sedated_until = float(getattr(character.db, "sedated_until", 0.0) or 0.0)
    if sedated_until > time.time():
        return True, "sedated"

    grappled_by = getattr(character.db, "grappled_by", None)
    if grappled_by and hasattr(grappled_by, "id") and getattr(actor, "id", None) == grappled_by.id:
        return True, "restrained"

    try:
        from world.death import is_flatlined

        if is_flatlined(character):
            return True, "incapacitated"
    except Exception:
        pass

    try:
        from world.medical import is_unconscious

        if is_unconscious(character):
            return True, "unconscious"
    except Exception:
        pass

    return False, "denied"


def _resolve_recog_to_character(character, name_key):
    """Find a character object that `character` has labeled as name_key (permanent recog)."""
    nk = _norm_key(name_key)
    if not nk or not hasattr(character, "recog"):
        return None
    try:
        all_r = character.recog.all() or {}
        for recog_str, obj in all_r.items():
            if _norm_key(recog_str) == nk:
                return obj
    except Exception:
        pass
    return None


def cleanup_stale_trust_entries(character):
    """Remove trust keys that no longer match any recog or helmet name."""
    trust = dict(getattr(character.db, "trust", None) or {})
    if not trust:
        return
    valid = _permanent_recog_names(character) | _helmet_recog_names(character)
    changed = False
    for k in list(trust.keys()):
        if _norm_key(k) not in valid:
            del trust[k]
            changed = True
    if changed:
        character.db.trust = trust


def migrate_trust_rename(character, old_name, new_name):
    """When recog string changes from old_name to new_name, move trust entry."""
    o = _norm_key(old_name)
    n = _norm_key(new_name)
    if not o or not n or o == n:
        return
    trust = dict(getattr(character.db, "trust", None) or {})
    val = None
    for k in list(trust.keys()):
        if _norm_key(k) == o:
            val = trust.pop(k)
            break
    if val is None:
        return
    new_key = n
    if new_key in trust:
        merged = _entry_to_set(trust[new_key]) | _entry_to_set(val)
        trust[new_key] = merged
    else:
        trust[new_key] = val
    character.db.trust = trust


def get_trusted_list(character):
    """Return sorted list of (name_key, categories_set) after cleanup."""
    cleanup_stale_trust_entries(character)
    trust = dict(getattr(character.db, "trust", None) or {})
    out = []
    for k, v in sorted(trust.items()):
        out.append((k, _entry_to_set(v)))
    return out


def forget_trust_for_name(character, name_key):
    """Remove trust bucket for this label (e.g. on forget <name>)."""
    nk = _norm_key(name_key)
    if not nk:
        return
    trust = dict(getattr(character.db, "trust", None) or {})
    for k in list(trust.keys()):
        if _norm_key(k) == nk:
            del trust[k]
            character.db.trust = trust
            return
