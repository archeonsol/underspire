"""
Corpse cyberware salvage logic.
"""

import random
import time

from evennia.utils import delay
from evennia.utils.create import create_object
from evennia.utils.search import search_object

from world.body import cleanup_adds_body_parts_on_remove
from world.medical import add_injury
from world.theme_colors import MEDICAL_COLORS as MC


SALVAGE_NARRATIVES = {
    "limb": [
        "You cut around the interface junction. The flesh is cold and stiff and the tissue fights the blade. You pry the dermal seal apart and work the connectors free. Blood pools but does not flow.",
        "The limb attachment is buried in scar tissue and old adhesive. You slice through someone else's careful work and peel it apart. The interface bolts resist, then give.",
        "You find the seam and open it. Biology has grown into every gap around the metal. You strip tissue from chrome in wet layers until the hardware shows clean.",
    ],
    "neural": [
        "You cut behind the ear and follow an old scar line down to the chip bed. The electrodes cling to dead tissue with stubborn resistance before finally letting go.",
        "The access port is obvious. The implant under it is not. You cut tiny adhesions, patient and precise, and lever the chip free from dead membrane.",
        "You peel back scalp over a burr hole and work a blade tip into the gap. The chrome separates from grey tissue with a soft tearing pull.",
    ],
    "ocular": [
        "You retract the lids and cut the orbital anchors one by one. The optic interface disconnects in damp clicks until the eye comes free.",
        "The housings are seated in bone. You pry and unscrew with improvised leverage, then slide the optics out trailing dried nerve stubs.",
    ],
    "subdermal": [
        "You trace the implant edge under the skin and open long cuts along it. The plating peels away in strips with attached tissue.",
        "The work is distributed and tedious. You cut free node after node, then drag linking filaments out through narrow incisions.",
    ],
    "implant": [
        "You open old scar tissue and find the implant seated in its pocket. Feed lines and mounts come apart under your blade, then the unit pulls free slick and dark.",
        "You find it by touch in cooling flesh, cut down, and lever hard. The cavity weeps and the implant comes out with a wet pop.",
    ],
    "default": [
        "You cut into the body and find the chrome. The extraction is ugly but functional. The implant comes free in your hands trailing old tissue.",
    ],
}

SALVAGE_ROOM_MESSAGES = [
    "{operator} crouches over {corpse}, working with a scalpel. The sound of blade on dead flesh.",
    "{operator} cuts into {corpse}, prying at something beneath the skin.",
    "{operator} is elbow-deep in {corpse}, extracting hardware.",
]

SALVAGE_DIFFICULTY_LABELS = {
    (0, 8): "straightforward",
    (8, 14): "moderate",
    (14, 20): "delicate",
    (20, 99): "extremely delicate",
}


def _resolve_obj(dbid):
    try:
        res = search_object(f"#{int(dbid)}")
        return res[0] if res else None
    except Exception:
        return None


def _is_valid_corpse(obj):
    try:
        from typeclasses.corpse import Corpse
        return isinstance(obj, Corpse)
    except Exception:
        return False


def _iter_room_chars(room, exclude=None):
    if not room or not hasattr(room, "contents_get"):
        return []
    out = []
    for viewer in room.contents_get(content_type="character"):
        if exclude and viewer in exclude:
            continue
        out.append(viewer)
    return out


def _room_msg(operator, corpse, template):
    room = getattr(operator, "location", None)
    if not room:
        return
    for viewer in _iter_room_chars(room, exclude=(operator,)):
        opname = operator.get_display_name(viewer) if hasattr(operator, "get_display_name") else operator.name
        cname = corpse.get_display_name(viewer) if hasattr(corpse, "get_display_name") else corpse.key
        viewer.msg(template.format(operator=opname, corpse=cname))


def _get_scalpel(caller):
    for obj in (getattr(caller, "contents", None) or []):
        if not obj:
            continue
        db = getattr(obj, "db", None)
        if not db:
            continue
        if bool(getattr(db, "is_scalpel", False)):
            return obj
        if (getattr(db, "item_type", None) or "").lower() == "scalpel":
            return obj
        if (getattr(db, "tool_type", None) or "").lower() == "scalpel":
            return obj
        try:
            if hasattr(obj, "tags") and obj.tags.get("scalpel", category="item_type"):
                return obj
        except Exception:
            pass
    return None


def has_scalpel(caller):
    return _get_scalpel(caller) is not None


def _consume_scalpel_use(scalpel):
    if not scalpel:
        return False, "You need a scalpel for this work. A knife will destroy the interfaces."
    if hasattr(scalpel, "consume_use"):
        if not scalpel.consume_use():
            return False, "The blade is dull. It will not cut clean anymore. You need a fresh scalpel."
        return True, None
    uses = getattr(getattr(scalpel, "db", None), "uses_remaining", None)
    if uses is None:
        return True, None
    uses = int(uses or 0)
    if uses <= 0:
        return False, "The blade is dull. It will not cut clean anymore. You need a fresh scalpel."
    scalpel.db.uses_remaining = uses - 1
    return True, None


def _corpse_cyberware(corpse):
    return list(getattr(corpse.db, "cyberware", None) or [])


def _salvage_difficulty(cyberware_obj):
    base = int(getattr(cyberware_obj, "surgery_difficulty", 15) or 15)
    category = (getattr(cyberware_obj, "surgery_category", "implant") or "implant").lower()
    salvage_base = int(base * 0.6)
    if category in ("neural", "ocular"):
        salvage_base = int(base * 0.75)
    if category == "limb":
        salvage_base = int(base * 0.45)
    return max(5, salvage_base)


def _with_corpse_modifiers(corpse, cyberware_obj, difficulty):
    modded = int(difficulty)
    category = (getattr(cyberware_obj, "surgery_category", "implant") or "implant").lower()
    if bool(getattr(corpse.db, "skinned", False)) and category == "subdermal":
        modded -= 5
    if bool(getattr(corpse.db, "butchered", False)):
        if category == "implant":
            modded -= 3
        if category in ("neural", "ocular"):
            modded += 3
    return max(5, modded)


def difficulty_label(difficulty):
    for (lo, hi), label in SALVAGE_DIFFICULTY_LABELS.items():
        if lo <= difficulty < hi:
            return label
    return "delicate"


def describe_chrome_location(cw):
    mods = getattr(cw, "body_mods", {}) or {}
    if not mods:
        return "internal implant"
    parts = list(mods.keys())
    modes = [mode for mode, _txt in mods.values()]
    if "lock" in modes:
        return f"full replacement, {' and '.join(parts)}"
    return f"augmentation, {' and '.join(parts)}"


def _medicine_roll(operator, difficulty):
    if not hasattr(operator, "roll_check"):
        return 0, 0
    result, value = operator.roll_check(
        ["intelligence", "perception"],
        "medicine",
        difficulty=max(0, int(difficulty)),
    )
    if result == "Critical Success":
        return 3, value
    if result == "Full Success":
        return 2, value
    if result == "Marginal Success":
        return 1, value
    return 0, value


def _safe_on_uninstall(cyberware_obj, corpse):
    try:
        cyberware_obj.on_uninstall(corpse)
    except Exception:
        cyberware_obj.db.installed = False
        cyberware_obj.db.installed_on = None


def _remove_cyberware_from_corpse(corpse, cyberware_obj):
    lst = _corpse_cyberware(corpse)
    target_id = getattr(cyberware_obj, "id", None)
    kept = []
    removed = False
    for entry in lst:
        entry_id = getattr(entry, "id", None)
        if entry is cyberware_obj:
            removed = True
            continue
        if target_id is not None and entry_id == target_id:
            removed = True
            continue
        kept.append(entry)
    corpse.db.cyberware = kept if removed else lst


def _apply_marginal_damage(cyberware_obj):
    mx = int(getattr(cyberware_obj.db, "chrome_max_hp", getattr(cyberware_obj, "chrome_max_hp", 100)) or 100)
    hp = getattr(cyberware_obj.db, "chrome_hp", None)
    if hp is None:
        cyberware_obj.db.chrome_hp = max(1, int(mx * 0.6))
        cyberware_obj.db.chrome_max_hp = mx
        return
    cyberware_obj.db.chrome_hp = max(0, min(int(hp), int(mx * 0.6)))


def _degrade_if_destroyed(cyberware_obj, tier):
    hp = getattr(cyberware_obj.db, "chrome_hp", None)
    if hp is not None and int(hp or 0) <= 0:
        return max(0, tier - 1)
    return tier


def _create_scrap(operator, cyberware_obj):
    try:
        scrap = create_object("typeclasses.items.Item", key=f"destroyed {cyberware_obj.key}", location=operator)
        scrap.db.desc = "Shattered interface contacts and buckled chrome housing. Scrap."
        scrap.tags.add("scrap")
    except Exception:
        pass


def get_assessment_entries(corpse):
    entries = []
    for cw in _corpse_cyberware(corpse):
        diff = _with_corpse_modifiers(corpse, cw, _salvage_difficulty(cw))
        entries.append(
            {
                "id": cw.id,
                "obj": cw,
                "name": cw.key,
                "location": describe_chrome_location(cw),
                "difficulty": diff,
                "label": difficulty_label(diff),
            }
        )
    return entries


def start_assessment_sequence(caller, corpse, on_complete=None):
    cyberware = _corpse_cyberware(corpse)
    if not cyberware:
        return False, "There is no chrome on this body. Nothing worth taking."
    if getattr(caller.db, "salvage_assessing", False):
        return False, "You are already assessing a body."
    caller.db.salvage_assessing = True
    caller.msg("You kneel by the body and start tracing old seams and scar lines, mapping where the chrome sits under dead flesh.")
    for idx, cw in enumerate(cyberware):
        step_delay = 8 * (idx + 1)

        def _reveal(cw_id=cw.id):
            actor = _resolve_obj(caller.id)
            body = _resolve_obj(corpse.id)
            chrome = _resolve_obj(cw_id)
            if not actor or not body or not chrome:
                return
            if actor.location != body.location:
                return
            diff = _with_corpse_modifiers(body, chrome, _salvage_difficulty(chrome))
            actor.msg(f"You find {chrome.key}: {describe_chrome_location(chrome)}. Looks {difficulty_label(diff)} to pull clean.")

        delay(step_delay, _reveal)

    def _finish():
        actor = _resolve_obj(caller.id)
        body = _resolve_obj(corpse.id)
        if actor:
            actor.db.salvage_assessing = False
        if not actor or not body:
            return
        if actor.location != body.location:
            actor.msg("You lose the body before you finish your assessment.")
            return
        actor.msg("You have the map in your head now. You know where to cut.")
        if callable(on_complete):
            on_complete(actor, body)

    delay((8 * len(cyberware)) + 1, _finish)
    return True, None


def start_extraction(caller, corpse, cyberware_obj):
    if getattr(caller.db, "salvage_in_progress", False):
        return False, "You are already cutting chrome out of a body."
    if getattr(caller.db, "combat_target", None):
        return False, "You cannot do this while someone is trying to kill you."
    if not _is_valid_corpse(corpse):
        return False, "You can only salvage chrome from a corpse."
    if caller.location != corpse.location:
        return False, "You are not close enough to that body."
    if cyberware_obj not in _corpse_cyberware(corpse):
        return False, "That piece is no longer in the body."
    scalpel = _get_scalpel(caller)
    ok, err = _consume_scalpel_use(scalpel)
    if not ok:
        return False, err

    caller.db.salvage_in_progress = True
    caller.db.salvage_started_room = caller.location.id if caller.location else None
    caller.msg(f"You set the blade and begin cutting {cyberware_obj.key} out of the body.")
    _room_msg(caller, corpse, "{operator} begins cutting into {corpse}.")

    delay_seconds = random.randint(6, 8)
    delay(
        delay_seconds,
        _finish_extraction,
        caller.id,
        corpse.id,
        cyberware_obj.id,
        scalpel.id if scalpel else None,
        caller.location.id if caller.location else None,
    )
    return True, None


def _finish_extraction(caller_id, corpse_id, cyberware_id, scalpel_id, start_room_id):
    caller = _resolve_obj(caller_id)
    corpse = _resolve_obj(corpse_id)
    cyberware_obj = _resolve_obj(cyberware_id)
    scalpel = _resolve_obj(scalpel_id) if scalpel_id else None
    if caller:
        caller.db.salvage_in_progress = False
        caller.db.salvage_started_room = None
    if not caller or not corpse or not cyberware_obj:
        if caller:
            caller.msg("The body or the chrome is gone before you can finish.")
        return
    if caller.location is None or corpse.location is None:
        caller.msg("The work collapses midway. The body is gone.")
        return
    if caller.location.id != start_room_id or corpse.location != caller.location:
        caller.msg("You break off the cut before finishing.")
        return
    if getattr(caller.db, "combat_target", None):
        caller.msg("You abort as violence closes in.")
        return
    if cyberware_obj not in _corpse_cyberware(corpse):
        caller.msg("Someone beat you to it. That chrome is already gone.")
        return

    category = (getattr(cyberware_obj, "surgery_category", "default") or "default").lower()
    pool = SALVAGE_NARRATIVES.get(category, SALVAGE_NARRATIVES["default"])
    caller.msg(random.choice(pool))
    _room_msg(caller, corpse, random.choice(SALVAGE_ROOM_MESSAGES))

    diff = _with_corpse_modifiers(corpse, cyberware_obj, _salvage_difficulty(cyberware_obj))
    tier, _roll = _medicine_roll(caller, diff)
    tier = _degrade_if_destroyed(cyberware_obj, tier)

    _safe_on_uninstall(cyberware_obj, corpse)
    _remove_cyberware_from_corpse(corpse, cyberware_obj)
    cleanup_adds_body_parts_on_remove(corpse, cyberware_obj, _corpse_cyberware(corpse))

    if tier == 3:
        cyberware_obj.location = caller
        caller.msg(f"{MC['stable']}Clean extraction. The chrome is intact, not a scratch. Whoever installed this did good work. You did better taking it out.|n")
        return
    if tier == 2:
        cyberware_obj.location = caller
        caller.msg(f"{MC['stable']}The chrome comes free. Intact. A few scratches from the extraction but nothing that affects function. Good enough.|n")
        return
    if tier == 1:
        _apply_marginal_damage(cyberware_obj)
        cyberware_obj.location = caller
        caller.msg(f"{MC['compensated']}You got it out, but not clean. Contacts are bent and the housing is scored. It might still function, but it needs proper repair.|n")
        return

    try:
        cyberware_obj.delete()
    except Exception:
        pass
    _create_scrap(caller, cyberware_obj)
    caller.msg(f"{MC['critical']}The implant cracks as it comes free. Contacts shatter. The housing buckles. Whatever it was, it is scrap now.|n")

    if random.random() < 0.2:
        if random.random() < 0.5:
            hand = random.choice(("left hand", "right hand"))
            add_injury(caller, 5, body_part=hand, weapon_key="surgery")
            caller.msg(f"{MC['critical']}The blade skates and bites your hand. Blood wells between your fingers.|n")
        else:
            if scalpel and getattr(scalpel, "location", None) == caller:
                caller.msg(f"{MC['critical']}The blade catches bone and snaps. You need a new scalpel.|n")
                try:
                    scalpel.delete()
                except Exception:
                    pass
