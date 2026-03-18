"""
Defibrillator resuscitation: 12s sequence. Messages at 3s, 6s, 9s; at 9s the same callback
also runs the roll and success/fail (no separate timer - so the result always shows).
"""
from evennia.utils import delay

DEFIB_MSG1, DEFIB_MSG2, DEFIB_MSG3 = 3, 6, 9


def _get_object_by_id(dbref):
    """Resolve dbref to typeclassed Object."""
    if dbref is None:
        return None
    try:
        from world.combat import _get_object_by_id as combat_resolve
        return combat_resolve(dbref)
    except Exception as e:
        from evennia.utils import logger
        logger.log_trace("medical_defib._get_object_by_id(combat_resolve #%s): %s" % (dbref, e))
    try:
        from evennia.utils.search import search_object
        result = search_object(f"#{int(dbref)}")
        if result:
            return result[0]
        result = search_object(key=int(dbref))
        if result:
            return result[0]
    except Exception as e:
        from evennia.utils import logger
        logger.log_trace("medical_defib._get_object_by_id(#%s): %s" % (dbref, e))
    return None


def _defib_msg1(*args):
    """+3s: Place pads. args = single tuple (caller_id, target_id, defib_id) or three ids."""
    ids = args[0] if (len(args) == 1 and isinstance(args[0], (tuple, list))) else list(args)
    if not ids or len(ids) < 2:
        return
    caller = _get_object_by_id(ids[0])
    target = _get_object_by_id(ids[1])
    if not caller or not target:
        return
    caller.msg("|wYou place the pads: one below the right collarbone, one on the left side. The unit analyses. |rNo pulse. Charging.|n")
    if target != caller and target.location:
        target.location.msg_contents(
            f"{caller.name} presses defibrillator pads to {target.name}'s chest. The machine hums.",
            exclude=(caller, target),
        )


def _defib_msg2(*args):
    """+6s: First shock."""
    ids = args[0] if (len(args) == 1 and isinstance(args[0], (tuple, list))) else list(args)
    if not ids or len(ids) < 2:
        return
    caller = _get_object_by_id(ids[0])
    target = _get_object_by_id(ids[1])
    if not caller or not target:
        return
    caller.msg("|rCLEAR.|n You trigger the first shock. Their body jerks. You check the monitor.")
    if target != caller and target.location:
        target.location.msg_contents(
            f"A sharp crack. {target.name}'s body convulses as {caller.name} delivers the shock.",
            exclude=(caller, target),
        )


def _defib_msg3_and_finish(*args):
    """
    +9s: Last shock message then immediately roll and success/fail.
    """
    if not args:
        return
    ids = args[0] if (len(args) == 1 and isinstance(args[0], (tuple, list))) else list(args)
    if not ids or len(ids) < 2:
        return
    
    cid = ids[0]
    tid = ids[1]
    did = ids[2] if len(ids) > 2 else None
    
    caller = _get_object_by_id(cid)
    target = _get_object_by_id(tid)
    defib = _get_object_by_id(did) if did else None
    
    if not caller or not target or not hasattr(target, "db"):
        if caller and hasattr(caller, "db"):
            caller.db.defib_in_progress = False
        return
        
    if hasattr(caller, "db"):
        caller.db.defib_in_progress = False
        
    # Last thematic message
    caller.msg("|wStill flatline. You charge again. The hum rises. You clear and deliver a second shock.|n")
    if target != caller and target.location:
        target.location.msg_contents(
            f"Another shock. {caller.name} works the defibrillator over {target.name}, face set.",
            exclude=(caller, target),
        )

    if getattr(target, "hp", 1) > 0:
        caller.msg("They are already moving. You power down the unit.")
        return

    # --- THE FIX STARTS HERE ---
    try:
        from world.medical.medical_treatment import attempt_resuscitate
        success, msg = attempt_resuscitate(caller, target)
        
        if success and defib and hasattr(defib, "consume_use"):
            defib.consume_use()
            
        if success:
            # Safely handle 'msg' even if it is None or empty
            if msg:
                caller.msg(f"|g{msg}|n")
                
            caller.msg("|gThe monitor shows a rhythm now. HR present. SpO2 climbing. |wThey have been brought back.|n")
            
            if target != caller:
                target.msg("|gYou feel the shocks. Then something pulls you back. You gasp. You are here. You are alive.|n")
                if target.location:
                    target.location.msg_contents(
                        f"|g{target.name} gasps. A pulse. The monitor picks up a rhythm. They have been brought back.|n",
                        exclude=(caller, target),
                    )
        else:
            if msg:
                caller.msg(f"|r{msg}|n")
            if target != caller and target.location:
                target.location.msg_contents(
                    f"{caller.name} tries once more. Nothing. {target.name} does not move.",
                    exclude=(caller, target),
                )
                
    except Exception as e:
        import traceback
        err_trace = traceback.format_exc()
        caller.msg(f"|r[SYSTEM ERROR]|n Resuscitation failed:\n|w{err_trace}|n")


def start_defib_sequence(caller, target, defib):
    """
    Start the 12s defib sequence. Messages at 3s, 6s, 9s. At 9s the same callback also does the roll and result.
    Pass a single tuple (cid, tid, did) to each delay so the callback always gets one argument.
    """
    if getattr(caller.db, "defib_in_progress", False):
        return False, "You are already busy with the defibrillator."
    if not target or not hasattr(target, "db"):
        return False, "You need a valid target."
    try:
        from world.death import can_be_defibbed, is_permanently_dead
        if is_permanently_dead(target):
            return False, "They are gone. The defibrillator cannot bring back the dead."
        if not can_be_defibbed(target) and getattr(target, "hp", 1) > 0:
            return False, "They are not in arrest. The defibrillator is for the dead."
    except Exception as e:
        from evennia.utils import logger
        logger.log_trace("medical_defib.start_defib_sequence(can_be_defibbed): %s" % e)
        if getattr(target, "hp", 1) > 0:
            return False, "They are not in arrest. The defibrillator is for the dead."
    if caller.location != target.location:
        return False, "You need to be in the same place as the patient."
    if defib:
        u = getattr(defib.db, "uses_remaining", 0)
        if u is not None and (u or 0) <= 0:
            return False, "The defibrillator has no charge left."
    caller.db.defib_in_progress = True
    ids = (getattr(caller, "id", None), getattr(target, "id", None), getattr(defib, "id", None) if defib else None)
    # Immediate first message
    caller.msg("|wYou drop beside them. The unit powers on with a low whine. You tear open the pad packaging.|n")
    if target != caller and target.location:
        target.location.msg_contents(
            f"{caller.name} drops to their knees beside {target.name}, ripping open a defibrillator pack.",
            exclude=(caller, target),
        )
    # 3s, 6s, 9s: pass single tuple so callback always receives one argument
    delay(DEFIB_MSG1, _defib_msg1, ids)
    delay(DEFIB_MSG2, _defib_msg2, ids)
    delay(DEFIB_MSG3, _defib_msg3_and_finish, ids)
    return True, None
