"""Full cyberware catalog for gameplay implants."""

from typeclasses.cyberware import CyberwareBase
from world.cyberware_buffs import *


SKINWEAVE_DEFAULTS = {
    "torso": "The skin has an almost-too-perfect quality: uniform texture, no blemishes, no visible pores at close inspection. The color is even in a way that nature never produces. In certain light, it shimmers faintly, as if the surface itself is synthetic.",
    "face": "The complexion is flawless in a way that reads as artificial to a trained eye. No pores, no asymmetry, no capillary flush. The features are the person's own, but the surface is a mask that happens to be permanent.",
    "left arm": "The skin of the arm is smooth and featureless: no freckles, no hair, no visible veins. The texture is uniform from shoulder to wrist, as though poured rather than grown.",
    "right arm": "The arm's skin has an uncanny evenness. No scars take, no tan lines form.",
    "neck": "The neck's skin is seamless, meeting the jawline without the usual creases or texture changes.",
}

SKINWEAVE_EXTENDED_COVERAGE = {
    "arms": (["left arm", "right arm"], 3),
    "neck": (["neck"], 2),
    "legs": (["left thigh", "right thigh"], 4),
    "hands": (["left hand", "right hand"], 2),
}


class ChromeArmLeft(CyberwareBase):
    buff_class = ChromeArmLeftBuff
    chrome_replacement_for = "left_arm"
    surgery_category = "limb"
    surgery_narrative_key = "chrome_arm"
    surgery_difficulty = 20
    surgery_blood_loss = "severe"
    chrome_max_hp = 120
    armor_values = {"slashing": 4, "impact": 3, "penetrating": 2}
    body_mods = {
        "left arm": ("lock", "Chrome from shoulder to wrist. The joint articulates with a faint hydraulic whisper, pistons nested in brushed steel housing. Cable bundles run the length of the forearm like exposed tendons, flexing when the fingers move."),
        "left hand": ("lock", "Five chrome fingers, each knuckle a visible pin joint. The grip plates are crosshatched for traction. When the hand closes, the servos hum at a pitch just below hearing. The fingertips are smooth, featureless: no prints, no whorls."),
    }


class ChromeArmRight(CyberwareBase):
    buff_class = ChromeArmRightBuff
    surgery_category = "limb"
    surgery_narrative_key = "chrome_arm"
    surgery_difficulty = 20
    surgery_blood_loss = "severe"
    chrome_max_hp = 120
    armor_values = {"slashing": 4, "impact": 3, "penetrating": 2}
    body_mods = {
        "right arm": ("lock", "Chrome from shoulder to wrist. The joint articulates with a faint hydraulic whisper, pistons nested in brushed steel housing. Cable bundles run the length of the forearm like exposed tendons, flexing when the fingers move."),
        "right hand": ("lock", "Five chrome fingers, each knuckle a visible pin joint. The grip plates are crosshatched for traction. When the hand closes, the servos hum at a pitch just below hearing. The fingertips are smooth, featureless: no prints, no whorls."),
    }


class ChromeLegLeft(CyberwareBase):
    buff_class = ChromeLegLeftBuff
    chrome_replacement_for = "left_leg"
    surgery_category = "limb"
    surgery_narrative_key = "chrome_leg"
    surgery_difficulty = 22
    surgery_blood_loss = "severe"
    chrome_max_hp = 140
    armor_values = {"slashing": 4, "impact": 4, "penetrating": 2}
    body_mods = {
        "left thigh": ("lock", "Chrome from the hip socket down. The thigh is a single piston-driven column sheathed in matte steel plating. The interface where chrome meets skin is a puckered seam of scar tissue and surgical adhesive."),
        "left foot": ("lock", "A chrome foot, segmented and articulated. Each toe is a jointed plate that grips the ground independently. The sole is ridged rubber over a steel frame."),
    }


class ChromeLegRight(CyberwareBase):
    buff_class = ChromeLegRightBuff
    chrome_replacement_for = "right_leg"
    surgery_category = "limb"
    surgery_narrative_key = "chrome_leg"
    surgery_difficulty = 22
    surgery_blood_loss = "severe"
    chrome_max_hp = 140
    armor_values = {"slashing": 4, "impact": 4, "penetrating": 2}
    body_mods = {
        "right thigh": ("lock", "Chrome from the hip socket down. The thigh is a single piston-driven column sheathed in matte steel plating. The interface where chrome meets skin is a puckered seam of scar tissue and surgical adhesive."),
        "right foot": ("lock", "A chrome foot, segmented and articulated. Each toe is a jointed plate that grips the ground independently. The sole is ridged rubber over a steel frame."),
    }


class ChromeHandLeft(CyberwareBase):
    buff_class = ChromeHandLeftBuff
    surgery_category = "limb"
    surgery_narrative_key = "chrome_hand"
    surgery_difficulty = 15
    surgery_blood_loss = "moderate"
    chrome_max_hp = 60
    conflicts_with = ["ChromeArmLeft"]
    body_mods = {"left hand": ("lock", "Five chrome fingers, each knuckle a visible pin joint. The grip plates are crosshatched for traction. When the hand closes, the servos hum at a pitch just below hearing. The fingertips are smooth, featureless: no prints, no whorls.")}


class ChromeHandRight(CyberwareBase):
    buff_class = ChromeHandRightBuff
    surgery_category = "limb"
    surgery_narrative_key = "chrome_hand"
    surgery_difficulty = 15
    surgery_blood_loss = "moderate"
    chrome_max_hp = 60
    conflicts_with = ["ChromeArmRight"]
    body_mods = {"right hand": ("lock", "Five chrome fingers, each knuckle a visible pin joint. The grip plates are crosshatched for traction. When the hand closes, the servos hum at a pitch just below hearing. The fingertips are smooth, featureless: no prints, no whorls.")}


class ChromeTail(CyberwareBase):
    """
    Adds the tail body part for races that lack it; locks/replaces for Splicers.
    Future tail-slot cyberware should set conflicts_with to include ChromeTail (both ways).
    """

    buff_class = ChromeTailBuff
    adds_body_parts = ["tail"]
    surgery_category = "limb"
    surgery_narrative_key = "chrome_tail"
    surgery_difficulty = 16
    surgery_blood_loss = "moderate"
    chrome_max_hp = 80
    armor_values = {"slashing": 3, "impact": 3}
    damage_model = "none"
    body_mods = {
        "tail": (
            "lock",
            "A chrome tail extends from the base of the spine — segmented, articulated, each vertebral plate clicking softly as it moves.",
        ),
    }


class ChromeEyes(CyberwareBase):
    buff_class = ChromeEyesBuff
    surgery_category = "ocular"
    surgery_narrative_key = "chrome_eyes"
    surgery_difficulty = 20
    surgery_blood_loss = "moderate"
    chrome_max_hp = 40
    body_mods = {
        "left eye": ("lock", "The left eye is chrome. No iris, no white, instead there is a dark lens set in a burnished steel orbit, ringed by a mechanical aperture that contracts and dilates with a faint click. In low light, it catches the faintest glow and holds it."),
        "right eye": ("lock", "The right eye is chrome. A camera aperture where the iris should be, nested in polished steel. When it focuses, the aperture adjusts with an audible whisper."),
    }


class ChromeEyeLeft(CyberwareBase):
    buff_class = ChromeEyeLeftBuff
    surgery_category = "ocular"
    surgery_narrative_key = "chrome_eye_single"
    surgery_difficulty = 16
    surgery_blood_loss = "moderate"
    chrome_max_hp = 30
    body_mods = {"left eye": ("lock", "The left eye is chrome. No iris, no white, instead there is a dark lens set in a burnished steel orbit, ringed by a mechanical aperture that contracts and dilates with a faint click. In low light, it catches the faintest glow and holds it.")}


class ChromeEyeRight(CyberwareBase):
    buff_class = ChromeEyeRightBuff
    surgery_category = "ocular"
    surgery_narrative_key = "chrome_eye_single"
    surgery_difficulty = 16
    surgery_blood_loss = "moderate"
    chrome_max_hp = 30
    body_mods = {"right eye": ("lock", "The right eye is chrome. A camera aperture where the iris should be, nested in polished steel. When it focuses, the aperture adjusts with an audible whisper.")}


class AudioImplant(CyberwareBase):
    buff_class = AudioImplantBuff
    damage_model = "arc_only"
    surgery_category = "neural"
    surgery_narrative_key = "audio_implant"
    surgery_difficulty = 14
    surgery_blood_loss = "minor"
    chrome_max_hp = 25
    body_mods = {
        "left ear": ("append", "A thin line of chrome traces the curve behind the left ear and vanishes into the hairline. The metal is flush with the skin, almost invisible unless the light catches it at the right angle."),
        "right ear": ("append", "A matching chrome trace arcs behind the right ear, sitting almost flush with the skin except where the light catches its seam."),
    }


class OlfactoryBooster(CyberwareBase):
    buff_class = OlfactoryBoosterBuff
    surgery_category = "neural"
    surgery_narrative_key = "olfactory_booster"
    surgery_difficulty = 12
    surgery_blood_loss = "minor"
    chrome_max_hp = 20
    body_mods = {"face": ("append", "The nostrils have a faint chrome lining, barely visible.")}


class SubdermalPlating(CyberwareBase):
    buff_class = SubdermalPlatingBuff
    damage_model = "armor"
    surgery_category = "subdermal"
    surgery_narrative_key = "subdermal_plating"
    surgery_difficulty = 18
    surgery_blood_loss = "moderate"
    chrome_max_hp = 200
    conflicts_with = ["DermalWeave"]
    armor_values = {"slashing": 8, "impact": 6, "penetrating": 5, "burn": 3, "freeze": 2}
    body_mods = {
        "torso": ("append", "Faint geometric lines are visible beneath the skin of the chest. The skin doesn't move naturally over whatever lies beneath it."),
        "abdomen": ("append", "The abdomen has an unnatural firmness. The skin is taut over something rigid, subdivided into hexagonal segments visible only when the muscle flexes."),
        "back": ("append", "Across the back, the skin sits over something that isn't muscle and isn't bone. Faint ridges trace the spine and fan outward along the ribs."),
    }


class DermalWeave(CyberwareBase):
    buff_class = DermalWeaveBuff
    damage_model = "armor"
    surgery_category = "subdermal"
    surgery_narrative_key = "dermal_weave"
    surgery_difficulty = 14
    surgery_blood_loss = "minor"
    chrome_max_hp = 100
    conflicts_with = ["SubdermalPlating"]
    armor_values = {"slashing": 5, "impact": 3, "penetrating": 3, "burn": 2}
    body_mods = {
        "torso": ("append", "The skin across the chest has an unusual quality: tighter than natural, with a faint sheen that catches the light like silk over glass. It dimples oddly under pressure, as though something woven lies just beneath the surface."),
        "abdomen": ("append", "The skin of the abdomen is smooth and slightly iridescent. It doesn't wrinkle or fold the way skin should."),
    }


class BoneLacing(CyberwareBase):
    buff_class = BoneLacingBuff
    surgery_category = "subdermal"
    surgery_narrative_key = "bone_lacing"
    surgery_difficulty = 22
    surgery_blood_loss = "moderate"
    chrome_max_hp = 300
    body_mods = {"torso": ("append", "There are tiny pinpoint prick scars all across the skin where there are joints underneath.")}


class SkinWeave(CyberwareBase):
    buff_class = SkinWeaveBuff
    damage_model = "armor"
    surgery_category = "subdermal"
    surgery_narrative_key = "skin_weave"
    surgery_difficulty = 12
    surgery_blood_loss = "minor"
    chrome_max_hp = 50
    armor_values = {"burn": 3, "freeze": 3}
    default_coverage = ("torso", "face")
    body_mods = {}

    def at_object_creation(self):
        super().at_object_creation()
        self.db.weave_parts = list(self.default_coverage)
        self.db.weave_descriptions = {p: SKINWEAVE_DEFAULTS.get(p, "The skin here is synthetic and uncanny.") for p in self.db.weave_parts}
        self.db.weave_presets = {}

    def _rebuild_dynamic_body_mods(self):
        descs = dict(self.db.weave_descriptions or {})
        self.body_mods = {part: ("append", text) for part, text in descs.items()}

    def on_install(self, character):
        self._rebuild_dynamic_body_mods()
        super().on_install(character)

    def reapply_buffs(self, character):
        self._rebuild_dynamic_body_mods()
        super().reapply_buffs(character)
        appended = dict(character.db.appended_descriptions or {})
        for part, (_mode, text) in self.body_mods.items():
            if part not in appended:
                appended[part] = {}
            appended[part][self.typeclass_path] = text
        character.db.appended_descriptions = appended

    def update_weave_appearance(self, character, body_part, new_desc):
        parts = list(self.db.weave_parts or [])
        if body_part not in parts:
            return False, f"Your skin weave doesn't cover your {body_part}."
        new_desc = (new_desc or "").strip()
        if len(new_desc) < 20:
            return False, "Description too short (min 20 characters)."
        if len(new_desc) > 500:
            return False, "Description too long (max 500 characters)."
        descs = dict(self.db.weave_descriptions or {})
        descs[body_part] = new_desc
        self.db.weave_descriptions = descs
        self._rebuild_dynamic_body_mods()
        appended = dict(character.db.appended_descriptions or {})
        if body_part not in appended:
            appended[body_part] = {}
        appended[body_part][self.typeclass_path] = new_desc
        character.db.appended_descriptions = appended
        return True, f"Skin weave updated on your {body_part}."

    def save_preset(self, name):
        name = (name or "").strip().lower()
        if not name or len(name) > 20:
            return False, "Preset name must be 1-20 characters."
        presets = dict(self.db.weave_presets or {})
        if len(presets) >= 10 and name not in presets:
            return False, "Max 10 presets. Delete one first."
        presets[name] = dict(self.db.weave_descriptions or {})
        self.db.weave_presets = presets
        return True, f"Saved preset '{name}'."

    def load_preset(self, character, name):
        name = (name or "").strip().lower()
        presets = self.db.weave_presets or {}
        if name not in presets:
            return False, f"No preset named '{name}'."
        for part, desc in dict(presets[name]).items():
            self.update_weave_appearance(character, part, desc)
        return True, f"Loaded preset '{name}'."

    def reset_to_defaults(self, character):
        for part in (self.db.weave_parts or []):
            self.update_weave_appearance(character, part, SKINWEAVE_DEFAULTS.get(part, "The skin here is synthetic."))
        return True, "Skin weave reset to factory defaults."


class WiredReflexes(CyberwareBase):
    buff_class = WiredReflexesBuff
    damage_model = "arc_only"
    surgery_category = "neural"
    surgery_narrative_key = "wired_reflexes"
    surgery_difficulty = 25
    chrome_max_hp = 60
    body_mods = {
        "neck": ("append", "Fine chrome filaments trace the veins of the neck, visible just beneath the skin like silver threads in pale fabric. They pulse faintly with each heartbeat."),
        "back": ("append", "A thin line of chrome runs the length of the spine, just visible beneath the skin. It catches the light when the back arches or twists."),
    }


class SynapticAccelerator(CyberwareBase):
    buff_class = SynapticAcceleratorBuff
    damage_model = "arc_only"
    surgery_category = "neural"
    surgery_narrative_key = "synaptic_accelerator"
    surgery_difficulty = 28
    chrome_max_hp = 30
    body_mods = {"left ear": ("append", "A small chrome port is recessed behind the left ear, barely larger than a coin. The skin around it is slightly raised, the scar tissue faded to a pale ridge.")}


class PainEditor(CyberwareBase):
    buff_class = PainEditorBuff
    damage_model = "arc_only"
    surgery_category = "neural"
    surgery_narrative_key = "pain_editor"
    surgery_difficulty = 18
    chrome_max_hp = 20
    body_mods = {"neck": ("append", "A small chrome disc sits at the base of the skull, nestled in the hollow where spine meets brain.")}


class ThreatAssessment(CyberwareBase):
    buff_class = ThreatAssessmentBuff
    damage_model = "arc_only"
    surgery_category = "neural"
    surgery_narrative_key = "threat_assessment"
    surgery_difficulty = 22
    chrome_max_hp = 35
    required_implants_any = ["ChromeEyes", "ChromeEyeLeft", "ChromeEyeRight"]
    body_mods = {"head": ("append", "A barely visible seam runs from temple to temple across the crown of the skull.")}


class MemoryCore(CyberwareBase):
    buff_class = MemoryCoreBuff
    damage_model = "arc_only"
    surgery_category = "neural"
    surgery_narrative_key = "memory_core"
    surgery_difficulty = 20
    chrome_max_hp = 25
    body_mods = {"head": ("append", "There is a faint asymmetry to the skull - one temple slightly fuller than the other.")}


class CardioPulmonaryBooster(CyberwareBase):
    buff_class = CardioPulmonaryBoosterBuff
    damage_model = "collateral"
    surgery_category = "implant"
    surgery_narrative_key = "cardiopulmonary_booster"
    surgery_difficulty = 22
    surgery_blood_loss = "severe"
    chrome_max_hp = 80
    body_mods = {"torso": ("append", "A rhythmic clicking emanates from the chest: faint, mechanical, one tick behind the heartbeat like an echo in a different register.")}


class AdrenalPump(CyberwareBase):
    buff_class = AdrenalPumpBuff
    damage_model = "collateral"
    surgery_category = "implant"
    surgery_narrative_key = "adrenal_pump"
    surgery_difficulty = 16
    chrome_max_hp = 50
    conflicts_with = ["AdrenalineShunt"]
    body_mods = {"abdomen": ("append", "A hard lump sits beneath the skin of the lower abdomen, slightly off-center.")}


class ToxinFilter(CyberwareBase):
    buff_class = ToxinFilterBuff
    damage_model = "collateral"
    surgery_category = "implant"
    surgery_narrative_key = "toxin_filter"
    surgery_difficulty = 15
    chrome_max_hp = 60
    body_mods = {"abdomen": ("append", "Faint scarring traces the flank in parallel lines.")}


class MetabolicRegulator(CyberwareBase):
    buff_class = MetabolicRegulatorBuff
    damage_model = "collateral"
    surgery_category = "implant"
    surgery_narrative_key = "metabolic_regulator"
    surgery_difficulty = 14
    surgery_blood_loss = "minor"
    chrome_max_hp = 40


class HemostaticRegulator(CyberwareBase):
    buff_class = HemostaticRegulatorBuff
    damage_model = "collateral"
    surgery_category = "implant"
    surgery_narrative_key = "hemostatic_regulator"
    surgery_difficulty = 16
    surgery_blood_loss = "minor"
    chrome_max_hp = 45


class VoiceModulator(CyberwareBase):
    buff_class = VoiceModulatorBuff
    surgery_category = "implant"
    surgery_narrative_key = "voice_modulator"
    surgery_difficulty = 12
    chrome_max_hp = 25
    body_mods = {"neck": ("append", "A thin chrome band encircles the base of the throat, barely wider than a finger.")}


class GripPads(CyberwareBase):
    buff_class = GripPadsBuff
    surgery_category = "subdermal"
    surgery_narrative_key = "grip_pads"
    surgery_difficulty = 10
    chrome_max_hp = 30
    body_mods = {
        "left hand": ("append", "The palms and fingertips have an unusual texture: they are slightly tacky, faintly iridescent under direct light."),
        "right hand": ("append", "The fingertips catch on surfaces with a deliberate friction."),
    }


class TargetingReticle(CyberwareBase):
    buff_class = TargetingReticleBuff
    damage_model = "arc_only"
    surgery_category = "neural"
    surgery_narrative_key = "targeting_reticle"
    surgery_difficulty = 16
    chrome_max_hp = 20
    required_implants_any = ["ChromeEyes", "ChromeEyeLeft", "ChromeEyeRight"]

    def _has_eye_dependency(self, character):
        installed = {type(c).__name__ for c in (character.db.cyberware or [])}
        return bool({"ChromeEyes", "ChromeEyeLeft", "ChromeEyeRight"} & installed)

    def on_install(self, character):
        super().on_install(character)
        if not self._has_eye_dependency(character) and self.buff_class:
            character.buffs.remove(self.buff_class.key)

    def reapply_buffs(self, character):
        if self._has_eye_dependency(character):
            super().reapply_buffs(character)
        elif self.buff_class:
            character.buffs.remove(self.buff_class.key)


class SubvocalComm(CyberwareBase):
    buff_class = SubvocalCommBuff
    damage_model = "arc_only"
    surgery_category = "implant"
    surgery_narrative_key = "subvocal_comm"
    surgery_difficulty = 13
    surgery_blood_loss = "minor"
    chrome_max_hp = 20
    body_mods = {"neck": ("append", "A thin line of surgical scarring traces the larynx.")}


class AdrenalineShunt(CyberwareBase):
    buff_class = AdrenalineShuntBuff
    damage_model = "collateral"
    surgery_category = "implant"
    surgery_narrative_key = "adrenaline_shunt"
    surgery_difficulty = 14
    surgery_blood_loss = "minor"
    chrome_max_hp = 35
    conflicts_with = ["AdrenalPump"]


class RetractableClaws(CyberwareBase):
    buff_class = RetractableClawsBuff
    surgery_category = "subdermal"
    surgery_narrative_key = "retractable_claws"
    surgery_difficulty = 14
    surgery_blood_loss = "moderate"
    chrome_max_hp = 40
    body_mods = {}

    def _claw_descs(self):
        return {
            "left hand": ("append", "Sharp, animalistic claws extend from the fingertips, made out of some bone and steel composite."),
            "right hand": ("append", "Sharp, animalistic claws extend from the fingertips, made out of some bone and steel composite."),
        }

    def are_deployed(self):
        return bool(getattr(self.db, "claws_deployed", False))

    def _echo_room(self, character, template):
        """Send per-viewer room text so recog/sdesc resolves correctly."""
        loc = getattr(character, "location", None)
        if not loc or not hasattr(loc, "contents_get"):
            return
        for viewer in loc.contents_get(content_type="character"):
            if viewer == character:
                continue
            name = character.get_display_name(viewer) if hasattr(character, "get_display_name") else character.name
            viewer.msg(template.format(name=name))

    def deploy(self, character):
        if self.are_deployed():
            return False, "Your claws are already deployed."
        left = getattr(character.db, "left_hand_obj", None)
        right = getattr(character.db, "right_hand_obj", None)
        if left or right:
            return False, "Your hands must be empty before deploying claws."
        self.db.claws_deployed = True
        self.body_mods = self._claw_descs()
        for part, (_mode, text) in self.body_mods.items():
            appended = dict(character.db.appended_descriptions or {})
            if part not in appended:
                appended[part] = {}
            appended[part][self.typeclass_path] = text
            character.db.appended_descriptions = appended
        self._echo_room(character, "{name}'s chrome talons slide out from their fingertips.")
        return True, "Chrome talons slide out from your fingertips."

    def retract(self, character):
        if not self.are_deployed():
            return False, "Your claws are already retracted."
        self.db.claws_deployed = False
        for part in ("left hand", "right hand"):
            appended = dict(character.db.appended_descriptions or {})
            if part in appended:
                appended[part].pop(self.typeclass_path, None)
            character.db.appended_descriptions = appended
        self.body_mods = {}
        self._echo_room(character, "{name}'s chrome talons retract flush beneath their fingertips.")
        return True, "The talons retract flush beneath your fingertips."


class ChromeHeart(CyberwareBase):
    buff_class = ChromeHeartBuff
    chrome_replacement_for = "heart"
    surgery_narrative_key = "chrome_heart"
    surgery_difficulty = 25
    body_mods = {"torso": ("append", "A rhythmic clicking emanates from the chest, offset from the pulse.")}


class ChromeLungs(CyberwareBase):
    buff_class = ChromeLungsBuff
    chrome_replacement_for = "lungs"
    surgery_narrative_key = "chrome_lungs"
    surgery_difficulty = 22
    body_mods = {"torso": ("append", "Subtle vents line the lower ribcage, each the width of a fingernail.")}


class ChromeSpine(CyberwareBase):
    buff_class = ChromeSpineBuff
    chrome_replacement_for = "spine_cord"
    surgery_narrative_key = "chrome_spine"
    surgery_difficulty = 30
    body_mods = {"back": ("append", "Chrome vertebrae are visible beneath the skin along the length of the spine, each segment catching the light when the back bends.")}


class ChromeLiver(CyberwareBase):
    buff_class = ChromeLiverBuff
    chrome_replacement_for = "liver"
    surgery_narrative_key = "chrome_liver"
    surgery_difficulty = 18
    body_mods = {"abdomen": ("append", "The abdomen hums faintly on the right side.")}


class ChromeKidneys(CyberwareBase):
    buff_class = ChromeKidneysBuff
    chrome_replacement_for = "kidneys"
    surgery_narrative_key = "chrome_kidneys"
    surgery_difficulty = 16
    body_mods = {"back": ("append", "The flanks carry a subtle vibration.")}


class ChromeThroat(CyberwareBase):
    buff_class = ChromeThroatBuff
    chrome_replacement_for = "throat"
    surgery_narrative_key = "chrome_throat"
    surgery_difficulty = 18
    body_mods = {"neck": ("append", "The throat is reconstructed. Chrome and synthetic cartilage form a visible collar around the larynx.")}


class ChromeStomach(CyberwareBase):
    buff_class = ChromeStomachBuff
    chrome_replacement_for = "stomach"
    surgery_narrative_key = "chrome_stomach"
    surgery_difficulty = 14


class ChromeSpleen(CyberwareBase):
    buff_class = ChromeSpleenBuff
    chrome_replacement_for = "spleen"
    surgery_narrative_key = "chrome_spleen"
    surgery_difficulty = 14
    body_mods = {"abdomen": ("append", "Something in the left upper abdomen ticks.")}
