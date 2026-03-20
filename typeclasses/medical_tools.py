"""
Medical tools and devices: scanners, bandages, medkits, suture kits, splints, defibrillator, etc.
Use with the medical menu or 'use <tool> on <target>' for scan/treat. Defib: defib <target> or use defibrillator on <target>.
"""
import random
import time

from evennia import DefaultObject
from evennia.utils import delay
from typeclasses.items import Item

from world.medical.medical_treatment import (
    TOOL_SCANNER,
    TOOL_BANDAGES,
    TOOL_MEDKIT,
    TOOL_SUTURE_KIT,
    TOOL_SPLINT,
    TOOL_HEMOSTATIC,
    TOOL_SURGICAL_KIT,
    TOOL_TOURNIQUET,
    TOOL_ANTIBIOTICS,
)


class MedicalTool(Item):
    """
    Base for medical items. Set db.medical_tool_type to one of:
    scanner, bandages, medkit, suture_kit, splint, hemostatic, surgical_kit
    """
    def at_object_creation(self):
        super().at_object_creation()
        if not self.db.medical_tool_type:
            self.db.medical_tool_type = TOOL_MEDKIT  # default
        self.db.uses_remaining = getattr(self.db, "uses_remaining", None)  # None = unlimited

    @property
    def medical_tool_type(self):
        return self.db.medical_tool_type or TOOL_MEDKIT

    def consume_use(self):
        """If limited uses, decrement. Return True if still usable."""
        u = self.db.uses_remaining
        if u is None:
            return True
        if u <= 0:
            return False
        self.db.uses_remaining = u - 1
        return True

    def use_for_scan(self, operator, target):
        """Override in Scanner; return (success, message)."""
        return False, "This item cannot be used to scan."

    def use_for_sedation(self, operator, target):
        """Optional immediate-use sedation hook. Return (success, message) or (None, None) if unsupported."""
        return None, None

    def use_for_treatment(self, operator, target, action_id, target_info):
        """Dispatch to treatment module; return (success, message)."""
        from world import medical_treatment as mt
        t = self.medical_tool_type
        if action_id == "bleeding":
            return mt.attempt_stop_bleeding(operator, target, t, tool_obj=self)
        if action_id == "splint" and target_info:
            return mt.attempt_splint(operator, target, target_info, t, tool_obj=self)
        if action_id == "organ" and target_info:
            return mt.attempt_stabilize_organ(operator, target, target_info, t, tool_obj=self)
        if action_id == "clean" and target_info:
            return mt.attempt_clean_wound(operator, target, target_info, t, tool_obj=self)
        if action_id == "infection" and target_info:
            return mt.attempt_treat_infection(operator, target, target_info, t, tool_obj=self)
        return False, "Unknown or unsupported procedure."


class Bioscanner(MedicalTool):
    """Hand-held scanner for vitals and trauma readout. No consumable uses."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.medical_tool_type = TOOL_SCANNER

    def use_for_scan(self, operator, target):
        if not hasattr(target, "db"):
            return False, "Target not scannable; no valid biosigns."
        from world.medical import BIOSCANNER_MIN_MEDICINE
        med_level = getattr(operator, "get_skill_level", lambda s: 0)("medicine")
        if med_level < BIOSCANNER_MIN_MEDICINE:
            return False, "You lack the training to interpret its readout."
        from world.medical.medical_scanner import get_scanner_readout
        hp = getattr(target, "hp", 0)
        mx = getattr(target, "max_hp", 1)
        formatted = get_scanner_readout(target)
        target_name = target.get_display_name(operator) if hasattr(target, "get_display_name") else target.name
        return True, {
            "hp": hp,
            "max_hp": mx,
            "formatted": formatted,
            "target_name": target_name,
        }


class Bandages(MedicalTool):
    """Basic gauze and bandages for controlling bleeding."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.medical_tool_type = TOOL_BANDAGES
        self.db.uses_remaining = 5


class Medkit(MedicalTool):
    """General first-aid kit: bandages, basic splinting, some stabilizers."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.medical_tool_type = TOOL_MEDKIT
        self.db.uses_remaining = 10


class SutureKit(MedicalTool):
    """Needle and thread for wound closure; better bleeding control."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.medical_tool_type = TOOL_SUTURE_KIT
        self.db.uses_remaining = 3


class Splint(MedicalTool):
    """Rigid support for fractures; single use per bone."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.medical_tool_type = TOOL_SPLINT
        self.db.uses_remaining = 2


class HemostaticAgent(MedicalTool):
    """Hemostatic gel/compound for rapid bleeding control. Best for severe/critical bleeds; temporary until suture or surgery."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.medical_tool_type = TOOL_HEMOSTATIC
        self.db.uses_remaining = 2


class Tourniquet(MedicalTool):
    """Stops limb haemorrhage fast. Bleeding stops immediately but the limb is at risk; wound may reopen after a short time until proper closure."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.medical_tool_type = TOOL_TOURNIQUET
        self.db.uses_remaining = 1


class SurgicalKit(MedicalTool):
    """Advanced field kit: sutures, splinting, internal stabilization. Portable."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.medical_tool_type = TOOL_SURGICAL_KIT
        self.db.uses_remaining = 5


class CoAmoxiclav(MedicalTool):
    """Co-amoxiclav (amoxicillin/clavulanate): broad skin/soft tissue coverage."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.medical_tool_type = TOOL_ANTIBIOTICS
        self.key = "co-amoxiclav"
        self.db.antibiotic_profile = "co_amoxiclav"
        self.db.antibiotic_targets = [
            "surface_cellulitis",
            "stitch_abscess",
            "sewer_fever",
        ]
        self.db.uses_remaining = 4


class Cephalexin(MedicalTool):
    """Cephalexin: first-line skin/soft tissue oral cephalosporin."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.medical_tool_type = TOOL_ANTIBIOTICS
        self.key = "cephalexin"
        self.db.antibiotic_profile = "cephalexin"
        self.db.antibiotic_targets = [
            "surface_cellulitis",
            "stitch_abscess",
        ]
        self.db.uses_remaining = 5


class Doxycycline(MedicalTool):
    """Doxycycline: atypical/respiratory and mixed soft tissue support."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.medical_tool_type = TOOL_ANTIBIOTICS
        self.key = "doxycycline"
        self.db.antibiotic_profile = "doxycycline"
        self.db.antibiotic_targets = [
            "sewer_fever",
            "pleural_empyema",
        ]
        self.db.uses_remaining = 4


class Metronidazole(MedicalTool):
    """Metronidazole: anaerobic coverage for deep foul/necrotic wounds."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.medical_tool_type = TOOL_ANTIBIOTICS
        self.key = "metronidazole"
        self.db.antibiotic_profile = "metronidazole"
        self.db.antibiotic_targets = [
            "anaerobic_wound_rot",
        ]
        self.db.uses_remaining = 4


class Clindamycin(MedicalTool):
    """Clindamycin: tissue/bone anaerobic and skin-adjacent coverage."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.medical_tool_type = TOOL_ANTIBIOTICS
        self.key = "clindamycin"
        self.db.antibiotic_profile = "clindamycin"
        self.db.antibiotic_targets = [
            "anaerobic_wound_rot",
            "bone_deep_osteitis",
        ]
        self.db.uses_remaining = 3


class PiperacillinTazobactam(MedicalTool):
    """Piperacillin/tazobactam: broad severe polymicrobial rescue coverage."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.medical_tool_type = TOOL_ANTIBIOTICS
        self.key = "piperacillin/tazobactam"
        self.db.antibiotic_profile = "pip_tazo"
        self.db.antibiotic_targets = [
            "anaerobic_wound_rot",
            "bone_deep_osteitis",
            "pleural_empyema",
            "sewer_fever",
            "bloodfire_sepsis",
        ]
        self.db.uses_remaining = 2


class Vancomycin(MedicalTool):
    """Vancomycin: high-tier rescue for severe bloodstream/device infections."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.medical_tool_type = TOOL_ANTIBIOTICS
        self.key = "vancomycin"
        self.db.antibiotic_profile = "vancomycin"
        self.db.antibiotic_targets = [
            "bloodfire_sepsis",
            "chrome_interface_necrosis",
        ]
        self.db.uses_remaining = 2


# Backward-compatible aliases for older prototypes/scripts.
class Antibiotics(CoAmoxiclav):
    """Compatibility alias -> co-amoxiclav."""
    pass


class AntiAnaerobeKit(Metronidazole):
    """Compatibility alias -> metronidazole."""
    pass


class InterfacePhageCocktail(Vancomycin):
    """Compatibility alias -> vancomycin."""
    pass


class ORStation(MedicalTool):
    """
    Legacy operating room surgical station (operating theatre). Use OperatingTable for new spawns.
    """
    def at_object_creation(self):
        super().at_object_creation()
        self.db.medical_tool_type = TOOL_SURGICAL_KIT
        self.db.uses_remaining = None
        self.db.stationary_medical = True
        self.locks.add("get:false()")

    def get_display_name(self, looker):
        return getattr(self.db, "desc", None) or self.key or "operating theatre (surgical station)"


class OperatingTable(MedicalTool):
    """
    Operating table: patients lie down on it for surgery. Room look shows "X is lying on the operating table".
    Provides surgical capability; use the surgery command for organ procedures with narrative and skill checks.
    """
    def at_object_creation(self):
        super().at_object_creation()
        self.db.medical_tool_type = TOOL_SURGICAL_KIT
        self.db.uses_remaining = None
        self.db.stationary_medical = True
        # Fixtures: immovable and no @sp for non-builders.
        self.db.immovable = True
        self.db.allow_setplace = False
        self.locks.add("get:false()")

    def get_display_name(self, looker):
        return getattr(self.db, "desc", None) or self.key or "operating table"

    def get_patient(self):
        """Return the character lying on this table (db.lying_on_table == self), or None. Character stays in room."""
        room = self.location
        if not room:
            return None
        for char in room.contents_get(content_type="character"):
            if getattr(char.db, "lying_on_table", None) == self:
                return char
        return None

    def _ko_seconds_for_target(self, target):
        endurance = 0
        if hasattr(target, "get_stat_level"):
            endurance = int(target.get_stat_level("endurance") or 0)
        else:
            endurance = int((getattr(target.db, "stats", None) or {}).get("endurance", 0) or 0)
        # Keep OR sedation long enough for multi-phase surgeries.
        base = 240
        return max(90, base - int(endurance * 0.4))

    def use_for_sedation(self, operator, target):
        if not hasattr(target, "db"):
            return False, "That target cannot be anesthetized."
        patient = self.get_patient()
        if patient != target:
            return False, "Anesthesia can only be administered to the patient on the operating table."
        now_ts = time.time()
        if bool(getattr(target.db, "unconscious", False)) and float(getattr(target.db, "sedated_until", 0.0) or 0.0) > now_ts:
            return False, "Patient is already unconscious."
        delay_secs = random.randint(5, 6)
        target.msg("|mA mask descends. You inhale |wsevoflurane|m vapor as the room starts to blur...|n")
        if target.location and hasattr(target.location, "contents_get"):
            for v in target.location.contents_get(content_type="character"):
                if v in (target, operator):
                    continue
                v.msg("%s adjusts the vaporizer and starts sevoflurane induction on %s." % (
                    operator.get_display_name(v) if hasattr(operator, "get_display_name") else operator.name,
                    target.get_display_name(v) if hasattr(target, "get_display_name") else target.name,
                ))

        def _induce():
            if self.get_patient() != target or not getattr(target, "db", None):
                return
            from world.combat.grapple import set_unconscious_for_seconds
            ko_secs = self._ko_seconds_for_target(target)
            set_unconscious_for_seconds(target, ko_secs)
            now = time.time()
            old_until = float(getattr(target.db, "sedated_until", 0.0) or 0.0)
            target.db.sedated_until = max(old_until, now + ko_secs)
            target.db.sedated_by = getattr(operator, "id", None)
            target.msg("|mThe vapor takes hold. Darkness closes in.|n")

        delay(delay_secs, _induce)
        return True, "You start sevoflurane induction. Loss of consciousness expected in about %ds." % delay_secs


def get_medical_tools_from_inventory(character):
    """
    Return dict tool_type -> list of MedicalTool objects.
    Includes character's inventory and any stationary medical fixtures in the room (e.g. OR station).
    """
    from world.medical.medical_treatment import (
        TOOL_SCANNER, TOOL_BANDAGES, TOOL_MEDKIT, TOOL_SUTURE_KIT,
        TOOL_SPLINT, TOOL_HEMOSTATIC, TOOL_TOURNIQUET, TOOL_SURGICAL_KIT, TOOL_ANTIBIOTICS,
    )
    result = {}
    if not character:
        return result
    # Inventory
    if hasattr(character, "contents"):
        for obj in character.contents:
            if not isinstance(obj, MedicalTool):
                continue
            if getattr(obj.db, "stationary_medical", False):
                continue
            if getattr(obj.db, "uses_remaining", 1) is not None and (obj.db.uses_remaining or 0) <= 0:
                continue
            t = obj.db.medical_tool_type
            if t not in result:
                result[t] = []
            result[t].append(obj)
    # Room fixtures (OR station, etc.)
    loc = getattr(character, "location", None)
    if loc and hasattr(loc, "contents"):
        for obj in loc.contents:
            if not isinstance(obj, MedicalTool):
                continue
            if not getattr(obj.db, "stationary_medical", False):
                continue
            t = obj.db.medical_tool_type
            if t not in result:
                result[t] = []
            result[t].append(obj)
    return result


# -----------------------------------------------------------------------------
# Defibrillator: resuscitation only, not part of medical menu
# -----------------------------------------------------------------------------

class Defibrillator(Item):
    """Portable defibrillator for resuscitating the dead/arrested. Use: defib <target> or use defibrillator on <target>."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.uses_remaining = 3

    def consume_use(self):
        u = self.db.uses_remaining
        if u is None or u <= 0:
            return False
        self.db.uses_remaining = u - 1
        return True

    def get_display_name(self, looker):
        return self.key or "defibrillator"
