"""
Surgery on the operating table: delayed narrative messages (grimdark/arcanepunk) and skill check.
Patient must be lying on an operating table; surgeon runs the surgery <organ> command.
"""
from evennia.utils import delay
import time

from world.theme_colors import MEDICAL_COLORS as MC

# Delays in seconds (longer than defib: ~5, 12, 20, 28 then finish)
SURGERY_MSG1, SURGERY_MSG2, SURGERY_MSG3, SURGERY_MSG4 = 5, 12, 20, 28


def _get_object_by_id(dbref):
    if dbref is None:
        return None
    try:
        from world.combat import _get_object_by_id as combat_resolve
        return combat_resolve(dbref)
    except Exception:
        pass
    try:
        from evennia.utils.search import search_object
        result = search_object("#%s" % int(dbref))
        if result:
            return result[0]
    except Exception:
        pass
    return None


# Per-organ surgery narratives: 4 messages each (grimdark / 40k / arcanepunk).
# Caller sees full text; room sees short third-person.
ORGAN_SURGERY_NARRATIVES = {
    "brain": [
        "You position the skull clamp. The bone is cracked. You drill a burr hole; the smell of ozone and charred bone fills the theatre. The link-scanner shows pressure. You have to go in.",
        "The dura parts. Blood and CSF. You suction. Deeper — the tissue is bruised, swollen. You work by feel and the flicker of the neural mapper. One wrong move and they are a vegetable. The Authority does not waste resources on vegetables.",
        "You resect the damaged matter. Seal the vessels. The graft-patch goes in — cheap colony stock, but it holds. You close the dura. The bone flap goes back. Screws. The patient has not moved. The monitor still shows activity. Small mercies.",
        "You close the scalp. The surgery is done. Whether they wake up sane is in the hands of the machine-spirit and whatever they did to deserve this. You step back and let the autoclave hum.",
    ],
    "eyes": [
        "The face is a mess. You retract the lid. The globe is intact but the vessels are a ruin. You irrigate. Blood clouds the field. You work under magnification — the kind the undercity rarely sees. Every cut is a gamble.",
        "You repair the sclera. Suture after suture. The lens is cracked; you remove the fragments. They will see shadows and light at best. Maybe. The other eye is worse. You do what you can.",
        "You seal the chamber. Patch the muscle. The eye will sit in the socket. Infection will kill them if the trauma did not. You pack the orbit and close. They will wear a patch. They will be lucky to wear anything.",
        "You dress the wound. The theatre stinks of blood and antiseptic. Another body patched for the grinder. You strip your gloves and signal for cleanup.",
    ],
    "throat": [
        "The neck is open. You find the trachea — crushed, swollen. You cannot intubate blind. You go for a cric — blade to the membrane, tube in. Air hisses. They are breathing. For now.",
        "You clear the hematoma. The larynx is a mess. You stabilize the cartilage, secure the airway. One slip and they drown in their own blood. You do not slip. You have done this in the dark, in the tunnels. Here you have light.",
        "You repair what you can. The vocal cords may never work right. They will breathe. You close the wound in layers. The scar will be ugly. Ugly is alive.",
        "You tape the tube. The patient is stable. They will wake up with a hole in their throat and a story they might not remember. You have done your part.",
    ],
    "carotid": [
        "The neck is a slaughterhouse. You clamp. You have to find the vessel before they exsanguinate. The field is red. You suction. There — the carotid is nicked, not severed. The Authority's surgeons would have better tools. You have hands and wire.",
        "You place the first suture. The vessel pulses. You work fast. One leak and they are gone. The second suture. The third. The flow slows. You seal the last of it. The clamp comes off. It holds.",
        "You irrigate. No new bleeding. You close the wound. The pulse is strong at the angle of the jaw. They will live. They may wish they had not. You have seen what comes after.",
        "You dress the site. The carotid is repaired. They will carry the scar and the memory of your hands in their neck. Such is the price of the undercity.",
    ],
    "collarbone_area": [
        "The shoulder is a wreck. You palpate — clavicle is in pieces, the subclavian is at risk. You open the field. Bone fragments. You have to reduce and fix before the vessel tears.",
        "You reduce the fracture. The plate is old — recycled from a dozen surgeries — but it holds. Screws bite into bone. The alignment is good. The nerve is intact. You have seen worse. You have done worse.",
        "You close the muscle and skin. The arm will move again. The pain will linger. Pain is the body's way of saying it is still there. You have done your job.",
        "You wrap the shoulder. The collarbone is fixed. They will carry metal for the rest of their days. In the undercity, that is a luxury.",
    ],
    "heart": [
        "The chest is open. You have cracked the sternum. The heart is visible — bruised, struggling. You work in the rhythm of the pump. One mistake and it stops. You do not have a second chance.",
        "You repair the pericardium. The muscle is damaged but not ruptured. You suture the tear. The heart beats against your fingers. You close the defect. The rhythm holds. You have seen hearts stop. This one does not.",
        "You irrigate the cavity. No bleeding. You wire the sternum shut. The chest closes. The monitor shows a rhythm. It is not pretty. It is alive.",
        "You dress the wound. The heart is repaired. They will carry the scar and the memory of the cold that followed. You step back. The theatre is quiet except for the hum of machines.",
    ],
    "lungs": [
        "The chest is open. The lung is collapsed — punctured, bloody. You find the hole. You have to seal it before they drown in their own blood. The suction runs. You work.",
        "You suture the parenchyma. The lung reinflates — slow, ragged. You check the other side. Intact. You place a chest tube. The air hisses out. They will breathe. The tube will stay until the hole seals.",
        "You close the chest. The lung holds. The monitor shows saturation climbing. They are not out of danger. They are out of the worst of it. For now.",
        "You secure the tube and dress the site. The surgery is done. The undercity will take the rest. You have given them a chance.",
    ],
    "spine_cord": [
        "The back is open. You have retracted the muscle. The spine is visible — the cord is compressed, bruised. You cannot fix the cord. No one can. You can only take the pressure off. You work with the care of a bomb disposal tech.",
        "You remove the fragment. The cord is still there. Still intact. You do not know if they will walk. You know that if you do nothing they will not. You close the dura. The bone goes back.",
        "You close the wound. The spine is decompressed. The rest is up to the nerve and the machine-spirit. You have done what the field allows. It may not be enough. It often is not.",
        "You dress the site. The patient is still. You have given them a chance. In the undercity, that is all anyone can ask.",
    ],
    "liver": [
        "The abdomen is open. The liver is lacerated — a mess of blood and tissue. You pack it. You have to find the bleed. The suction runs. Your hands are red. The patient is dying under your fingers.",
        "You find the vessel. You clamp it. You suture the parenchyma. The liver is a forgiving organ. It can take a lot. It has taken a lot. You close the laceration. The bleeding stops.",
        "You irrigate. No new bleeding. You remove the packs. The liver holds. You close the abdomen in layers. They will live. They will hurt. Such is the price.",
        "You dress the wound. The liver is repaired. The undercity does not care. It will take more from them. You have given them a chance to pay.",
    ],
    "spleen": [
        "The abdomen is open. The spleen is ruptured — a bag of blood and pulp. You cannot repair it. No one can. You have to take it out. You clamp the pedicle. The blade goes in.",
        "You dissect the attachments. The spleen comes free. You tie off the vessels. The field is a ruin. You irrigate. You look for other damage. The spleen was the worst. You close.",
        "You close the abdomen. They will live without a spleen. They will be more vulnerable to infection. In the undercity, that is a later problem. Today they live.",
        "You dress the wound. The spleen is gone. The patient is stable. You have done what you could. It will have to be enough.",
    ],
    "stomach": [
        "The abdomen is open. The stomach is perforated — contents and blood. You have to close the hole before sepsis kills them. The field is contaminated. You work fast.",
        "You suture the perforation. Two layers. The stomach holds. You irrigate the cavity. The smell is foul. You have smelled worse. You close the abdomen. They will need antibiotics. They will need luck.",
        "You close the wound. The stomach is repaired. They will eat again. They will wish they had not. You have seen what the undercity does to those who cannot work.",
        "You dress the site. The surgery is done. The patient is stable. You strip your gloves. Another body saved for the grinder.",
    ],
    "kidneys": [
        "The abdomen is open. The kidney is lacerated — blood everywhere. You pack it. You have to decide: repair or remove. You try repair first. The clamp goes on.",
        "You suture the parenchyma. The kidney is fragile. You work with the care of a thief. One wrong move and it is gone. The bleeding slows. You close the capsule. The kidney holds.",
        "You irrigate. No new bleeding. You leave the kidney in place. They will have two. They will need both. You close the abdomen. The monitor holds. They will live.",
        "You dress the wound. The kidney is repaired. The undercity will take its share. You have given them a chance to pay it.",
    ],
    "pelvic_organs": [
        "The pelvis is a wreck. You have opened the abdomen. The organs are damaged — bladder, bowel, vessels. You have to control the bleeding first. You pack. You clamp. You work in the red.",
        "You repair what you can. The bladder holds a suture. The bowel is patched. The vessels are tied. You cannot fix everything. You can stop the dying. For now.",
        "You irrigate. You close the abdomen. The pelvis is stable. They will have scars. They will have pain. They will have a chance. In the undercity, that is a gift.",
        "You dress the wound. The surgery is done. The patient is stable. You have done what the machine-spirit allowed. The rest is up to them.",
    ],
}

_GENERIC_BONE_NARRATIVE = [
    "You expose the fracture and clear shredded tissue. Bone ends are displaced and unstable. You irrigate, reduce, and prepare fixation.",
    "You align the fragments under direct vision. Plate and screws go in, one by one. The reduction is not elegant, but it is solid.",
    "You test stability and confirm no major bleed has restarted. The construct holds. You close in layers and dress the field.",
    "You secure the dressing and step back. The bone is fixed for now; rehab and time will decide the rest.",
]

BONE_SURGERY_NARRATIVES = {
    "femur": _GENERIC_BONE_NARRATIVE,
    "humerus": _GENERIC_BONE_NARRATIVE,
    "clavicle": _GENERIC_BONE_NARRATIVE,
    "scapula": _GENERIC_BONE_NARRATIVE,
    "pelvis": _GENERIC_BONE_NARRATIVE,
    "spine": _GENERIC_BONE_NARRATIVE,
    "cervical_spine": _GENERIC_BONE_NARRATIVE,
    "ribs": _GENERIC_BONE_NARRATIVE,
    "metacarpals": _GENERIC_BONE_NARRATIVE,
    "metatarsals": _GENERIC_BONE_NARRATIVE,
    "ankle": _GENERIC_BONE_NARRATIVE,
    "jaw": _GENERIC_BONE_NARRATIVE,
    "nose": _GENERIC_BONE_NARRATIVE,
    "skull": _GENERIC_BONE_NARRATIVE,
}

def _surgery_msg(caller, target, table, organ_key, step):
    """Send one narrative message to caller and short line to room."""
    if not caller or not target or not hasattr(caller, "msg"):
        return
    narratives = ORGAN_SURGERY_NARRATIVES.get(organ_key) or BONE_SURGERY_NARRATIVES.get(organ_key)
    if not narratives or step < 0 or step >= len(narratives):
        return
    from world.medical import ORGAN_INFO, BONE_INFO
    names = ORGAN_INFO.get(organ_key, (None,) * 4)
    organ_name = names[0] if names and names[0] else BONE_INFO.get(organ_key, organ_key)
    # To caller
    caller.msg("|w%s|n" % narratives[step])
    # To room (short)
    loc = table.location if table else caller.location
    if loc and target != caller and hasattr(loc, "contents_get"):
        for v in loc.contents_get(content_type="character"):
            if v in (caller, target):
                continue
            v.msg("%s works over %s — %s. The theatre reeks of blood and antiseptic." % (
                caller.get_display_name(v) if hasattr(caller, "get_display_name") else caller.name,
                target.get_display_name(v) if hasattr(target, "get_display_name") else target.name,
                organ_name,
            ))


def _surgery_finish(ids, organ_key):
    """Last delay: run the actual roll and apply result."""
    if not ids or len(ids) < 3:
        return
    caller = _get_object_by_id(ids[0])
    target = _get_object_by_id(ids[1])
    table = _get_object_by_id(ids[2])
    if not caller or not target or not hasattr(target, "db"):
        if caller and hasattr(caller, "db"):
            caller.db.surgery_in_progress = False
        return
    if hasattr(caller, "db"):
        caller.db.surgery_in_progress = False

    from world.medical import ORGAN_INFO, BONE_INFO, rebuild_derived_trauma_views
    rebuild_derived_trauma_views(target)
    organ_damage = target.db.organ_damage or {}
    fractures = target.db.fractures or []
    is_bone_case = organ_key in fractures
    severity = organ_damage.get(organ_key, 0)
    if severity <= 0 and not is_bone_case:
        caller.msg("There is no significant trauma to that target. The field is clean.")
        return

    from world.medical.medical_treatment import (
        _ensure_medical_db,
        _organ_difficulty,
        _splint_difficulty,
        _medicine_roll,
        TOOL_SURGICAL_KIT,
    )
    from world.medical import _set_injury_treatment_quality
    _ensure_medical_db(target)
    stabilized = target.db.stabilized_organs or {}
    if (not is_bone_case) and stabilized.get(organ_key):
        caller.msg("That organ is already stabilized. Nothing more to do.")
        return

    names = ORGAN_INFO.get(organ_key, (organ_key,) * 4)
    difficulty = _splint_difficulty(organ_key) + 8 if is_bone_case else _organ_difficulty(severity)
    now_ts = time.time()
    sedated = (
        float(getattr(target.db, "sedated_until", 0.0) or 0.0) > now_ts
        or (
            bool(getattr(target.db, "medical_unconscious", False))
            and float(getattr(target.db, "medical_unconscious_until", 0.0) or 0.0) > now_ts
        )
    )
    if not sedated:
        # Awake surgery is much harder due to movement/pain response.
        difficulty += 18
    # Table gives a bonus: proper OR, full kit, patient immobilized
    table_mod = 20
    success_level, _ = _medicine_roll(caller, max(0, difficulty - table_mod), table_mod)

    if success_level == 0:
        caller.msg(f"{MC['critical']}You do what you can. The damage is too deep, or your hands betray you. The organ does not hold. They will need more — or they will not make it.|n")
        if target != caller and target.location and hasattr(target.location, "contents_get"):
            for v in target.location.contents_get(content_type="character"):
                if v in (caller, target):
                    continue
                v.msg("%s steps back from the table. The surgery did not take. %s lies still." % (
                    caller.get_display_name(v) if hasattr(caller, "get_display_name") else caller.name,
                    target.get_display_name(v) if hasattr(target, "get_display_name") else target.name,
                ))
        return

    injuries = getattr(target.db, "injuries", None) or []
    if is_bone_case:
        from world.medical.limb_trauma import body_part_to_limb_slot, is_limb_destroyed
        for inj in injuries:
            if inj.get("fracture") != organ_key or (inj.get("hp_occupied", 0) or 0) <= 0:
                continue
            slot = body_part_to_limb_slot((inj.get("body_part") or "").strip())
            if slot and is_limb_destroyed(target, slot):
                caller.msg(f"{MC['critical']}The bone won't hold hardware. The limb is pulp. They need chrome — not plates.|n")
                return
            break
        target.db.fractures = [b for b in fractures if b != organ_key]
        target.db.splinted_bones = [b for b in (target.db.splinted_bones or []) if b != organ_key]
        for i in injuries:
            if i.get("fracture") == organ_key:
                i["fracture"] = None
                _set_injury_treatment_quality(i, 3)
                # Surgery gives immediate partial restoration to reduce idle waiting.
                hp_occ = float(i.get("hp_occupied", 0) or 0)
                restore = max(1, int(round(hp_occ * 0.25)))
                i["hp_occupied"] = max(0, hp_occ - restore)
                target.db.current_hp = min(getattr(target, "max_hp", 100) or 100, (target.db.current_hp or 0) + restore)
                break
    else:
        target.db.organ_damage[organ_key] = severity - 1
        if severity - 1 <= 0:
            del target.db.organ_damage[organ_key]
        stabilized = dict(stabilized)
        stabilized[organ_key] = True
        target.db.stabilized_organs = stabilized
        for i in injuries:
            od = dict(i.get("organ_damage") or {})
            if organ_key not in od:
                continue
            od[organ_key] = max(0, int(od.get(organ_key, 0)) - 1)
            if od[organ_key] <= 0:
                del od[organ_key]
            i["organ_damage"] = od
            _set_injury_treatment_quality(i, 3)
            hp_occ = float(i.get("hp_occupied", 0) or 0)
            restore = max(1, int(round(hp_occ * 0.2)))
            i["hp_occupied"] = max(0, hp_occ - restore)
            target.db.current_hp = min(getattr(target, "max_hp", 100) or 100, (target.db.current_hp or 0) + restore)
            break
    target.db.injuries = injuries
    rebuild_derived_trauma_views(target)

    caller.msg(f"{MC['stable']}The organ holds. You have done what you could. They may yet live.|n")
    if target != caller:
        target.msg(f"{MC['stable']}You drift back. The pain is still there, but the worst has passed. Someone has pulled you through.|n")
        if target.location and hasattr(target.location, "contents_get"):
            for v in target.location.contents_get(content_type="character"):
                if v in (caller, target):
                    continue
                v.msg(f"{MC['stable']}%s finishes the procedure. %s lies still on the table — alive.|n" % (
                    caller.get_display_name(v) if hasattr(caller, "get_display_name") else caller.name,
                    target.get_display_name(v) if hasattr(target, "get_display_name") else target.name,
                ))


def start_surgery_sequence(caller, target, table, organ_key):
    """
    Start the surgery sequence: 4 delayed narrative messages then skill check and result.
    Caller must be in same room as table; target must be the patient on the table.
    """
    if getattr(caller.db, "surgery_in_progress", False):
        return False, "You are already in the middle of a procedure."
    if not table or not hasattr(table, "get_patient"):
        return False, "You need an operating table with a patient."
    patient = table.get_patient()
    if patient != target:
        return False, "They are not on the operating table."
    if caller.location != table.location:
        return False, "You must be at the operating table to perform surgery."
    from world.medical import rebuild_derived_trauma_views
    from world.medical.limb_trauma import body_part_to_limb_slot, is_limb_destroyed
    rebuild_derived_trauma_views(target)
    organ_damage = target.db.organ_damage or {}
    fractures = target.db.fractures or []
    if organ_damage.get(organ_key, 0) <= 0 and organ_key not in fractures:
        return False, "That target does not require surgery."
    if organ_key in fractures:
        for inj in (target.db.injuries or []):
            if inj.get("fracture") != organ_key or (inj.get("hp_occupied", 0) or 0) <= 0:
                continue
            slot = body_part_to_limb_slot((inj.get("body_part") or "").strip())
            if slot and is_limb_destroyed(target, slot):
                return False, "That limb is shattered beyond repair. They need a chrome replacement, not pinning."
            break
    from world.medical.medical_treatment import ORGAN_INFO
    if organ_key not in ORGAN_SURGERY_NARRATIVES and organ_key not in BONE_SURGERY_NARRATIVES:
        return False, "No surgical procedure for that organ."

    now_ts = time.time()
    sedated = (
        float(getattr(target.db, "sedated_until", 0.0) or 0.0) > now_ts
        or (
            bool(getattr(target.db, "medical_unconscious", False))
            and float(getattr(target.db, "medical_unconscious_until", 0.0) or 0.0) > now_ts
        )
    )
    if not sedated and hasattr(caller, "msg"):
        caller.msg(f"{MC['compensated']}Warning: patient is not sedated. The surgery will be harder.|n")

    caller.db.surgery_in_progress = True
    ids = (caller.id, target.id, table.id)

    # Immediate first message
    _surgery_msg(caller, target, table, organ_key, 0)
    delay(SURGERY_MSG1, lambda: _surgery_msg(_get_object_by_id(ids[0]), _get_object_by_id(ids[1]), _get_object_by_id(ids[2]), organ_key, 1))
    delay(SURGERY_MSG2, lambda: _surgery_msg(_get_object_by_id(ids[0]), _get_object_by_id(ids[1]), _get_object_by_id(ids[2]), organ_key, 2))
    delay(SURGERY_MSG3, lambda: _surgery_msg(_get_object_by_id(ids[0]), _get_object_by_id(ids[1]), _get_object_by_id(ids[2]), organ_key, 3))

    def _last():
        _surgery_finish(ids, organ_key)
    delay(SURGERY_MSG4, _last)

    return True, None
