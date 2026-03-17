"""
Medical tools and devices: scanners, bandages, medkits, suture kits, splints, defibrillator, etc.
Use with the medical menu or 'use <tool> on <target>' for scan/treat. Defib: defib <target> or use defibrillator on <target>.
"""
from evennia import DefaultObject
from typeclasses.items import Item

from world.medical_treatment import (
    TOOL_SCANNER,
    TOOL_BANDAGES,
    TOOL_MEDKIT,
    TOOL_SUTURE_KIT,
    TOOL_SPLINT,
    TOOL_HEMOSTATIC,
    TOOL_SURGICAL_KIT,
    TOOL_TOURNIQUET,
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

    def use_for_treatment(self, operator, target, action_id, target_info):
        """Dispatch to treatment module; return (success, message)."""
        from world import medical_treatment as mt
        t = self.medical_tool_type
        if action_id == "bleeding":
            return mt.attempt_stop_bleeding(operator, target, t)
        if action_id == "splint" and target_info:
            return mt.attempt_splint(operator, target, target_info, t)
        if action_id == "organ" and target_info:
            return mt.attempt_stabilize_organ(operator, target, target_info, t)
        return False, "Unknown or unsupported procedure."


class Bioscanner(MedicalTool):
    """Hand-held scanner for vitals and trauma readout. No consumable uses."""
    def at_object_creation(self):
        super().at_object_creation()
        self.db.medical_tool_type = TOOL_SCANNER

    def use_for_scan(self, operator, target):
        if not hasattr(target, "db"):
            return False, "Target not scannable; no valid biosigns."
        from world.medical_scanner import get_scanner_readout
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


def get_medical_tools_from_inventory(character):
    """
    Return dict tool_type -> list of MedicalTool objects.
    Includes character's inventory and any stationary medical fixtures in the room (e.g. OR station).
    """
    from world.medical_treatment import (
        TOOL_SCANNER, TOOL_BANDAGES, TOOL_MEDKIT, TOOL_SUTURE_KIT,
        TOOL_SPLINT, TOOL_HEMOSTATIC, TOOL_TOURNIQUET, TOOL_SURGICAL_KIT,
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
