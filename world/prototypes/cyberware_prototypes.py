"""Cyberware prototypes."""

_CYBER = ["cyberware"]


def _p(key, name, cls):
    return {"prototype_key": key, "prototype_tags": _CYBER, "key": name, "typeclass": f"typeclasses.cyberware_catalog.{cls}"}


CHROME_ARM_LEFT = _p("chrome_arm_left", "chrome arm (left)", "ChromeArmLeft")
CHROME_ARM_RIGHT = _p("chrome_arm_right", "chrome arm (right)", "ChromeArmRight")
CHROME_LEG_LEFT = _p("chrome_leg_left", "chrome leg (left)", "ChromeLegLeft")
CHROME_LEG_RIGHT = _p("chrome_leg_right", "chrome leg (right)", "ChromeLegRight")
CHROME_HAND_LEFT = _p("chrome_hand_left", "chrome hand (left)", "ChromeHandLeft")
CHROME_HAND_RIGHT = _p("chrome_hand_right", "chrome hand (right)", "ChromeHandRight")
CHROME_TAIL = _p("chrome_tail", "chrome tail", "ChromeTail")
CHROME_EYES = _p("chrome_eyes", "chrome eyes", "ChromeEyes")
CHROME_EYE_LEFT = _p("chrome_eye_left", "chrome eye (left)", "ChromeEyeLeft")
CHROME_EYE_RIGHT = _p("chrome_eye_right", "chrome eye (right)", "ChromeEyeRight")
AUDIO_IMPLANT = _p("audio_implant", "audio implant", "AudioImplant")
OLFACTORY_BOOSTER = _p("olfactory_booster", "olfactory booster", "OlfactoryBooster")
SUBDERMAL_PLATING = _p("subdermal_plating", "subdermal plating", "SubdermalPlating")
DERMAL_WEAVE = _p("dermal_weave", "dermal weave", "DermalWeave")
BONE_LACING = _p("bone_lacing", "bone lacing", "BoneLacing")
SKIN_WEAVE = _p("skin_weave", "skin weave", "SkinWeave")
WIRED_REFLEXES = _p("wired_reflexes", "wired reflexes", "WiredReflexes")
SYNAPTIC_ACCELERATOR = _p("synaptic_accelerator", "synaptic accelerator", "SynapticAccelerator")
PAIN_EDITOR = _p("pain_editor", "pain editor", "PainEditor")
THREAT_ASSESSMENT = _p("threat_assessment", "threat assessment module", "ThreatAssessment")
MEMORY_CORE = _p("memory_core", "memory core", "MemoryCore")
CARDIO_PULMONARY_BOOSTER = _p("cardio_pulmonary_booster", "cardiopulmonary booster", "CardioPulmonaryBooster")
ADRENAL_PUMP = _p("adrenal_pump", "adrenal pump", "AdrenalPump")
TOXIN_FILTER = _p("toxin_filter", "toxin filter", "ToxinFilter")
METABOLIC_REGULATOR = _p("metabolic_regulator", "metabolic regulator", "MetabolicRegulator")
HEMOSTATIC_REGULATOR = _p("hemostatic_regulator", "hemostatic regulator", "HemostaticRegulator")
VOICE_MODULATOR = _p("voice_modulator", "voice modulator", "VoiceModulator")
GRIP_PADS = _p("grip_pads", "subdermal grip pads", "GripPads")
TARGETING_RETICLE = _p("targeting_reticle", "targeting reticle", "TargetingReticle")
SUBVOCAL_COMM = _p("subvocal_comm", "subvocal communicator", "SubvocalComm")
ADRENALINE_SHUNT = _p("adrenaline_shunt", "adrenaline shunt", "AdrenalineShunt")
RETRACTABLE_CLAWS = _p("retractable_claws", "retractable claws", "RetractableClaws")
CHROME_HEART = _p("chrome_heart", "chrome heart", "ChromeHeart")
CHROME_LUNGS = _p("chrome_lungs", "chrome lungs", "ChromeLungs")
CHROME_SPINE = _p("chrome_spine", "chrome spine", "ChromeSpine")
CHROME_LIVER = _p("chrome_liver", "chrome liver", "ChromeLiver")
CHROME_KIDNEYS = _p("chrome_kidneys", "chrome kidneys", "ChromeKidneys")
CHROME_THROAT = _p("chrome_throat", "chrome throat", "ChromeThroat")
CHROME_STOMACH = _p("chrome_stomach", "chrome stomach", "ChromeStomach")
CHROME_SPLEEN = _p("chrome_spleen", "chrome spleen", "ChromeSpleen")

