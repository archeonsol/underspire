"""Cyberware buff definitions."""

from evennia.contrib.rpg.buffs.buff import Mod

from world.buffs import GameBuffBase


WEAPON_SKILLS = (
    "unarmed",
    "short_blades",
    "long_blades",
    "blunt_weaponry",
    "sidearms",
    "longarms",
    "automatics",
)


class _CyberBuffMeta(type):
    """
    Build Evennia ``Mod`` lists from ``stat_mods`` / ``skill_mods`` on each
    cyberware buff class. BuffHandler only applies ``check()`` modifiers for
    buffs with non-empty ``mods`` (see traits / get_by_stat in the contrib).
    """

    def __new__(mcs, name, bases, namespace, **kwds):
        cls = super().__new__(mcs, name, bases, namespace)
        if name in ("_CyberBuff", "RetractableClawsBuff"):
            return cls
        if not any(getattr(b, "__name__", None) == "_CyberBuff" for b in bases):
            return cls
        stat_mods = namespace.get("stat_mods") or {}
        skill_mods = namespace.get("skill_mods") or {}
        mods = []
        for stat, value in stat_mods.items():
            mods.append(Mod(stat=f"{stat}_display", modifier="add", value=int(value)))
        for skill, value in skill_mods.items():
            mods.append(Mod(stat=f"skill:{skill}", modifier="add", value=int(value)))
        if mods:
            cls.mods = mods
        return cls


class _CyberBuff(GameBuffBase, metaclass=_CyberBuffMeta):
    # Evennia contrib: duration -1 is permanent (see BaseBuff in contrib).
    duration = -1
    tickrate = 0
    stat_mods = {}
    skill_mods = {}
    vulnerabilities = {}


class ChromeArmLeftBuff(_CyberBuff):
    key = "chrome_arm_left"
    name = "Chrome Arm (Left)"
    flavor = "Hydraulic servos amplify force."
    stat_mods = {"strength": 8}
    vulnerabilities = {"arc": 0.15}


class ChromeArmRightBuff(_CyberBuff):
    key = "chrome_arm_right"
    name = "Chrome Arm (Right)"
    flavor = "Hydraulic servos amplify force."
    stat_mods = {"strength": 8}
    vulnerabilities = {"arc": 0.15}


class ChromeLegLeftBuff(_CyberBuff):
    key = "chrome_leg_left"
    name = "Chrome Leg (Left)"
    flavor = "Piston-assisted stride."
    stat_mods = {"agility": 8}
    vulnerabilities = {"arc": 0.15}


class ChromeLegRightBuff(_CyberBuff):
    key = "chrome_leg_right"
    name = "Chrome Leg (Right)"
    flavor = "Piston-assisted stride."
    stat_mods = {"agility": 8}
    vulnerabilities = {"arc": 0.15}


class ChromeHandLeftBuff(_CyberBuff):
    key = "chrome_hand_left"
    name = "Chrome Hand (Left)"
    flavor = "Reinforced grip and strike surfaces."
    stat_mods = {"strength": 4}
    skill_mods = {"unarmed": 3}
    vulnerabilities = {"arc": 0.08}


class ChromeHandRightBuff(_CyberBuff):
    key = "chrome_hand_right"
    name = "Chrome Hand (Right)"
    flavor = "Reinforced grip and strike surfaces."
    stat_mods = {"strength": 4}
    skill_mods = {"unarmed": 3}
    vulnerabilities = {"arc": 0.08}


class ChromeTailBuff(_CyberBuff):
    key = "chrome_tail"
    name = "Chrome Tail"
    flavor = "Counterbalance and proprioception from an articulated appendage."
    stat_mods = {"agility": 3}
    vulnerabilities = {"arc": 0.05}


class ChromeEyesBuff(_CyberBuff):
    key = "chrome_eyes"
    name = "Chrome Eyes"
    flavor = "Paired optical replacement."
    stat_mods = {"perception": 10}
    skill_mods = {"evasion": 5}
    vulnerabilities = {"arc": 0.20}


class ChromeEyeLeftBuff(_CyberBuff):
    key = "chrome_eye_left"
    name = "Chrome Eye (Left)"
    flavor = "Single optical replacement."
    stat_mods = {"perception": 5}
    skill_mods = {"evasion": 2}
    vulnerabilities = {"arc": 0.10}


class ChromeEyeRightBuff(_CyberBuff):
    key = "chrome_eye_right"
    name = "Chrome Eye (Right)"
    flavor = "Single optical replacement."
    stat_mods = {"perception": 5}
    skill_mods = {"evasion": 2}
    vulnerabilities = {"arc": 0.10}


class AudioImplantBuff(_CyberBuff):
    key = "audio_implant"
    name = "Audio Implant"
    flavor = "Augmented hearing."
    stat_mods = {"perception": 5}
    skill_mods = {"scavenging": 3}
    vulnerabilities = {"arc": 0.10}


class OlfactoryBoosterBuff(_CyberBuff):
    key = "olfactory_booster"
    name = "Olfactory Booster"
    flavor = "Chemical and biological scent parsing."
    stat_mods = {"perception": 4}
    skill_mods = {"medicine": 3, "scavenging": 3}
    vulnerabilities = {"arc": 0.05}


class SubdermalPlatingBuff(_CyberBuff):
    key = "subdermal_plating"
    name = "Subdermal Plating"
    flavor = "Dense internal armor grid."
    stat_mods = {"perception": -3}
    vulnerabilities = {"arc": 0.10}


class DermalWeaveBuff(_CyberBuff):
    key = "dermal_weave"
    name = "Dermal Weave"
    flavor = "Reactive woven reinforcement under skin."
    vulnerabilities = {"arc": 0.05}


class BoneLacingBuff(_CyberBuff):
    key = "bone_lacing"
    name = "Bone Lacing"
    flavor = "Reinforced skeletal lattice."
    stat_mods = {"endurance": 5}
    vulnerabilities = {"arc": 0.12}


class SkinWeaveBuff(_CyberBuff):
    key = "skin_weave"
    name = "Skin Weave"
    flavor = "Programmable synthetic dermal overlay."
    stat_mods = {"charisma": 4, "perception": -2}
    vulnerabilities = {"arc": 0.03}


class WiredReflexesBuff(_CyberBuff):
    key = "wired_reflexes"
    name = "Wired Reflexes"
    flavor = "Neural latency reduction."
    stat_mods = {"agility": 6}
    skill_mods = {"evasion": 5, "gunnery": 3}
    vulnerabilities = {"arc": 0.18}


class SynapticAcceleratorBuff(_CyberBuff):
    key = "synaptic_accelerator"
    name = "Synaptic Accelerator"
    flavor = "Boosted cognition and throughput."
    stat_mods = {"intelligence": 8}
    skill_mods = {"medicine": 4, "cyber_surgery": 4, "electrical_engineering": 3}
    vulnerabilities = {"arc": 0.15}


class PainEditorBuff(_CyberBuff):
    key = "pain_editor"
    name = "Pain Editor"
    flavor = "Pain-signaling suppression."
    stat_mods = {"endurance": 4}
    vulnerabilities = {"arc": 0.10}


class ThreatAssessmentBuff(_CyberBuff):
    key = "threat_assessment"
    name = "Threat Assessment Module"
    flavor = "Predictive vector analysis."
    stat_mods = {"perception": 5}
    skill_mods = {"evasion": 4}
    vulnerabilities = {"arc": 0.12}


class MemoryCoreBuff(_CyberBuff):
    key = "memory_core"
    name = "Memory Core"
    flavor = "Auxiliary mnemonic lattice."
    stat_mods = {"intelligence": 5, "perception": 3}
    skill_mods = {"cyberdecking": 5}
    vulnerabilities = {"arc": 0.08}


class CardioPulmonaryBoosterBuff(_CyberBuff):
    key = "cardio_pulmonary_booster"
    name = "Cardiopulmonary Booster"
    flavor = "Mechanical cardio-respiratory assist."
    stat_mods = {"endurance": 6}
    vulnerabilities = {"arc": 0.08}


class AdrenalPumpBuff(_CyberBuff):
    key = "adrenal_pump"
    name = "Adrenal Pump"
    flavor = "Baseline hormone boost."
    stat_mods = {"strength": 3, "agility": 3}
    vulnerabilities = {"arc": 0.05}


class ToxinFilterBuff(_CyberBuff):
    key = "toxin_filter"
    name = "Toxin Filter"
    flavor = "Accelerated internal filtration."
    stat_mods = {"endurance": 4}
    vulnerabilities = {"arc": 0.05}


class MetabolicRegulatorBuff(_CyberBuff):
    key = "metabolic_regulator"
    name = "Metabolic Regulator"
    flavor = "Steady-state metabolism control."
    stat_mods = {"endurance": 3, "charisma": -2}
    vulnerabilities = {"arc": 0.03}


class HemostaticRegulatorBuff(_CyberBuff):
    key = "hemostatic_regulator"
    name = "Hemostatic Regulator"
    flavor = "Aggressive clotting control."
    stat_mods = {"endurance": 3}
    vulnerabilities = {"arc": 0.05}


class VoiceModulatorBuff(_CyberBuff):
    key = "voice_modulator"
    name = "Voice Modulator"
    flavor = "Precision vocal shaping."
    stat_mods = {"charisma": 6}
    skill_mods = {"artistry": 4}
    vulnerabilities = {"arc": 0.05}


class GripPadsBuff(_CyberBuff):
    key = "grip_pads"
    name = "Subdermal Grip Pads"
    flavor = "High-friction grasp surfaces."
    skill_mods = dict({"unarmed": 5}, **{sk: 5 for sk in WEAPON_SKILLS if sk != "unarmed"})
    vulnerabilities = {"arc": 0.03}


class TargetingReticleBuff(_CyberBuff):
    key = "targeting_reticle"
    name = "Targeting Reticle"
    flavor = "Predictive ballistic overlay."
    skill_mods = {"sidearms": 5, "longarms": 5, "automatics": 5}
    stat_mods = {"perception": 5}
    vulnerabilities = {"arc": 0.05}


class SubvocalCommBuff(_CyberBuff):
    key = "subvocal_comm"
    name = "Subvocal Communicator"
    flavor = "Silent transmit micro-actuation."
    vulnerabilities = {"arc": 0.05}


class AdrenalineShuntBuff(_CyberBuff):
    key = "adrenaline_shunt"
    name = "Adrenaline Shunt"
    flavor = "Controlled stress chemistry."
    stat_mods = {"agility": 4, "charisma": -3}
    skill_mods = {"evasion": 4}
    vulnerabilities = {"arc": 0.05}


class RetractableClawsBuff(_CyberBuff):
    """Installed implant; unarmed bonus only while deployed (see RetractableClawsDeployedBuff)."""

    key = "retractable_claws"
    name = "Retractable Claws"
    flavor = "Finger-sheathed blade system."
    # No skill_mods here — unarmed +8 is applied only when claws are deployed.
    skill_mods = {}
    vulnerabilities = {"arc": 0.05}


class RetractableClawsDeployedBuff(GameBuffBase):
    """Applied when claws are deployed; removed when retracted."""

    key = "retractable_claws_deployed"
    name = "Claws Deployed"
    flavor = "Chrome talons extend from the fingertips."
    duration = -1
    tickrate = 0
    mods = [Mod(stat="skill:unarmed", modifier="add", value=8)]


class ChromeHeartBuff(_CyberBuff):
    key = "chrome_heart"
    name = "Chrome Heart"
    flavor = "Mechanical cardiac replacement."
    stat_mods = {"endurance": 3}
    skill_mods = {"stealth": -2}
    vulnerabilities = {"arc": 0.10}


class ChromeLungsBuff(_CyberBuff):
    key = "chrome_lungs"
    name = "Chrome Lungs"
    flavor = "Mechanical pulmonary replacement."
    stat_mods = {"endurance": 3}
    vulnerabilities = {"arc": 0.08}


class ChromeSpineBuff(_CyberBuff):
    key = "chrome_spine"
    name = "Chrome Spine"
    flavor = "Segmented spinal replacement."
    stat_mods = {"agility": 1}
    vulnerabilities = {"arc": 0.15}


class ChromeLiverBuff(_CyberBuff):
    key = "chrome_liver"
    name = "Chrome Liver"
    flavor = "Synthetic liver unit."
    stat_mods = {"endurance": 2}
    vulnerabilities = {"arc": 0.05}


class ChromeKidneysBuff(_CyberBuff):
    key = "chrome_kidneys"
    name = "Chrome Kidneys"
    flavor = "Synthetic renal pair."
    stat_mods = {"endurance": 2}
    vulnerabilities = {"arc": 0.05}


class ChromeThroatBuff(_CyberBuff):
    key = "chrome_throat"
    name = "Chrome Throat"
    flavor = "Synthetic laryngeal assembly."
    stat_mods = {"endurance": 2, "charisma": -3}
    vulnerabilities = {"arc": 0.05}


class ChromeStomachBuff(_CyberBuff):
    key = "chrome_stomach"
    name = "Chrome Stomach"
    flavor = "Synthetic digestion chamber."
    vulnerabilities = {"arc": 0.03}


class ChromeSpleenBuff(_CyberBuff):
    key = "chrome_spleen"
    name = "Chrome Spleen"
    flavor = "Synthetic spleen unit."
    vulnerabilities = {"arc": 0.03}
