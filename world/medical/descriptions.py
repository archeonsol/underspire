"""
Narrative injury description helpers split from world.medical.__init__.
"""

INJURY_SEVERITY_WORDING = {
    "cut": {1: "a minor cut", 2: "a weeping cut", 3: "a deep cut", 4: "a grievous laceration"},
    "bruise": {1: "a bruise", 2: "heavy bruising", 3: "a severe contusion", 4: "massive contusion"},
    "gunshot": {1: "a graze", 2: "a gunshot wound", 3: "a severe gunshot wound", 4: "a critical gunshot wound"},
    "trauma": {1: "an abrasion", 2: "bruising", 3: "heavy impact trauma", 4: "severe trauma"},
    "arcane": {1: "a minor arcane burn", 2: "an arcane wound", 3: "a severe arcane wound", 4: "a critical arcane wound"},
    "surgery": {1: "a small incision", 2: "a surgical incision", 3: "a deep surgical wound", 4: "a major surgical wound"},
}
INJURY_SEVERITY_PLURAL = {
    "cut": {1: "minor cuts", 2: "weeping cuts", 3: "deep cuts", 4: "grievous lacerations"},
    "bruise": {1: "bruises", 2: "areas of heavy bruising", 3: "severe contusions", 4: "massive contusions"},
    "gunshot": {1: "grazes", 2: "gunshot wounds", 3: "severe gunshot wounds", 4: "critical gunshot wounds"},
    "trauma": {1: "abrasions", 2: "areas of bruising", 3: "heavy impact trauma", 4: "areas of severe trauma"},
    "arcane": {1: "minor arcane burns", 2: "arcane wounds", 3: "severe arcane wounds", 4: "critical arcane wounds"},
    "surgery": {1: "small incisions", 2: "surgical incisions", 3: "deep surgical wounds", 4: "major surgical wounds"},
}


def _pronoun_sub_poss(character):
    key = (getattr(character.db, "pronoun", None) or "neutral").lower()
    from world.rpg.emote import PRONOUN_MAP
    sub, poss, _ = PRONOUN_MAP.get(key, PRONOUN_MAP["neutral"])
    return (sub or "They").capitalize(), (poss or "their")


def _pronoun_verb_has_have(character):
    key = (getattr(character.db, "pronoun", None) or "neutral").lower()
    from world.rpg.emote import PRONOUN_MAP
    sub, _, _ = PRONOUN_MAP.get(key, PRONOUN_MAP["neutral"])
    return "have" if (sub or "they").lower() == "they" else "has"


def format_body_part_injuries(character, body_part, part_entries):
    if not part_entries:
        return ""
    if isinstance(part_entries[0], str):
        return " ".join(part_entries).strip()
    from collections import Counter
    sub, poss = _pronoun_sub_poss(character)
    verb = _pronoun_verb_has_have(character)
    groups = Counter((e.get("type", "trauma"), e.get("severity", 1)) for e in part_entries if isinstance(e, dict))
    bits = []
    for (itype, sev), count in groups.items():
        w = INJURY_SEVERITY_WORDING.get(itype, INJURY_SEVERITY_WORDING["trauma"])
        p = INJURY_SEVERITY_PLURAL.get(itype, INJURY_SEVERITY_PLURAL["trauma"])
        singular = w.get(sev, w[1])
        plural_phrase = p.get(sev, p[1])
        if count == 1:
            bits.append(singular)
        elif count == 2:
            bits.append(f"two {plural_phrase}")
        else:
            bits.append(f"multiple {plural_phrase}")
    if not bits:
        return ""
    return f"|r{sub} {verb} {' and '.join(bits)} on {poss} {body_part}.|n"


def get_untreated_injuries_by_part(character):
    injuries = getattr(character.db, "injuries", None) or []
    by_part = {}
    for i in injuries:
        if i.get("treated"):
            continue
        part = (i.get("body_part") or "").strip()
        if not part:
            continue
        by_part.setdefault(part, []).append({
            "type": i.get("type", "trauma"),
            "severity": i.get("severity", 1),
        })
    return by_part
