"""
Clothing crafting: bolt of cloth customization and token substitution.
Tease tokens: Wearer $N $P $S, Target $T $R $U, Item $I/$i (garment name). Use .verb for
conjugation. E.g. '$N .lift $p $I at $T'.
"""
from world.emote import PRONOUN_MAP


def _pronoun_tuple(character):
    """Return (sub, poss, obj) for character's pronoun set."""
    key = (getattr(character.db, "pronoun", None) or "neutral").lower()
    return PRONOUN_MAP.get(key, PRONOUN_MAP["neutral"])


def substitute_clothing_desc(text, wearer):
    """
    Replace clothing tokens in a description string for look/appearance.
    Context: wearer = the character wearing the item.
    $N/$n = wearer name, $P/$p = possessive (his/her/their), $S/$s = subject (he/she/they).
    """
    if not text or not wearer:
        return text or ""
    name = wearer.get_display_name(wearer)
    name_lower = name.lower()
    sub, poss, obj = _pronoun_tuple(wearer)
    # Capitalize for $P, $S
    poss_cap = (poss or "their").capitalize()
    sub_cap = (sub or "they").capitalize()
    replacements = [
        ("$N", name), ("$n", name_lower),
        ("$P", poss_cap), ("$p", poss or "their"),
        ("$S", sub_cap), ("$s", sub or "they"),
    ]
    result = text
    for token, value in replacements:
        result = result.replace(token, value)
    return result


def substitute_tease_for_viewer(template, doer, target, viewer, item=None):
    """
    Replace tease tokens for a specific viewer (doer, target, or room).

    Modes:
      - Token mode (legacy):
        Wearer/doer: $N/$n name, $P/$p possessive, $S/$s subject.
        Target (tease at): $T/$t name, $R/$r possessive, $U/$u subject.
        Item (garment): $I/$i = item's display name (e.g. 't-shirt'). Pass item= when teasing.
        When no target, $T/$t/$R/$r/$U/$u are empty. When no item, $I/$i are empty.

      - Pose-style mode:
        If the template uses only first-person text plus $T (no $N/$P/$S/$R/$U/$I tokens),
        we treat it as a first-person emote and auto-convert per viewer. Example:
          "I lift my shirt and show my chest to $T."
        Doer sees first person with $T resolved; others see third person via emote helpers.
    """
    if not template:
        return ""
    # Detect pose-style mode: allow $T (and $I/$i for item) but no other legacy tokens.
    legacy_tokens = ["$N", "$n", "$P", "$p", "$S", "$s", "$R", "$r", "$U", "$u", "$t"]
    has_legacy = any(tok in template for tok in legacy_tokens)
    pose_mode = ("$T" in template) and not has_legacy

    if pose_mode:
        # Resolve $T for this viewer first
        if target:
            if viewer == target:
                t_str = "you"
            else:
                t_str = target.get_display_name(viewer)
        else:
            t_str = ""
        base = template.replace("$T", t_str)
        # Resolve item tokens for this viewer as well
        if item:
            item_display = item.get_display_name(viewer)
            item_display_lower = (item_display or "").lower()
            base = base.replace("$I", item_display or "")
            base = base.replace("$i", item_display_lower)
        # Doer sees their own first-person wording
        if viewer == doer:
            return base
        # Others see third-person form of the doer's emote
        from world.emote import first_to_third
        return first_to_third(base, doer)
    if item:
        item_display = item.get_display_name(viewer)
        item_display_lower = (item_display or "").lower()
    else:
        item_display = ""
        item_display_lower = ""
    doer_name = doer.get_display_name(viewer) if doer else "Someone"
    doer_name_lower = doer_name.lower()
    sub, poss, obj = _pronoun_tuple(doer) if doer else ("they", "their", "them")
    poss_cap = (poss or "their").capitalize()
    sub_cap = (sub or "they").capitalize()

    if viewer == doer:
        doer_display = "You"
        doer_display_lower = "you"
        poss_display = "your"
        poss_display_cap = "Your"
        sub_display = "You"
        sub_display_lower = "you"
    else:
        doer_display = doer_name
        doer_display_lower = doer_name_lower
        poss_display = poss or "their"
        poss_display_cap = poss_cap
        sub_display = sub_cap
        sub_display_lower = sub or "they"

    if target:
        target_name = target.get_display_name(viewer)
        target_name_lower = target_name.lower()
        t_sub, t_poss, t_obj = _pronoun_tuple(target)
        t_poss_cap = (t_poss or "their").capitalize()
        t_sub_cap = (t_sub or "they").capitalize()
        if viewer == target:
            target_display = "you"
            target_display_lower = "you"
            r_display = "your"
            r_display_cap = "Your"
            u_display = "You"
            u_display_lower = "you"
        else:
            target_display = target_name
            target_display_lower = target_name_lower
            r_display = t_poss or "their"
            r_display_cap = t_poss_cap
            u_display = t_sub_cap
            u_display_lower = t_sub or "they"
    else:
        target_display = ""
        target_display_lower = ""
        r_display = ""
        r_display_cap = ""
        u_display = ""
        u_display_lower = ""

    result = template
    result = result.replace("$N", doer_display).replace("$n", doer_display_lower)
    result = result.replace("$P", poss_display_cap).replace("$p", poss_display)
    result = result.replace("$S", sub_display).replace("$s", sub_display_lower)
    result = result.replace("$T", target_display).replace("$t", target_display_lower)
    result = result.replace("$R", r_display_cap).replace("$r", r_display)
    result = result.replace("$U", u_display).replace("$u", u_display_lower)
    result = result.replace("$I", item_display).replace("$i", item_display_lower)
    # .verb conjugation: .lift -> "lift" for doer, "lifts" for others (like posing)
    import re
    from world.emote import _conjugate
    if viewer == doer:
        result = re.sub(r"\.(\w+)", r"\1", result)
    else:
        result = re.sub(r"\.(\w+)", lambda m: _conjugate(m.group(1)), result)
    if not target:
        result = re.sub(r"\s+at\s*$", "", result)
    return result
