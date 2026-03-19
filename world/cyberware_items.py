"""
Concrete cyberware implementations.

Each item subclasses CyberwareBase and declares buff_class and/or body_mods.
Add new chrome here; no other files need changing for purely appearance/stat mods.
"""

from evennia.contrib.rpg.buffs.buff import BaseBuff, Mod

from typeclasses.cyberware import CyberwareBase


class ChromeLegsBuff(BaseBuff):
    key = "chrome_legs"
    name = "Chrome Legs"
    flavor = "Your legs hum with the quiet precision of high-grade chrome."
    duration = -1  # permanent
    maxstacks = 1
    stacks = 1
    mods = [Mod(stat="endurance_display", modifier="add", value=10)]


class ChromeLegs(CyberwareBase):
    """
    A matched pair of precision chrome prosthetic legs.

    Locks left/right thigh and foot nakeds. Grants +10 endurance.
    Spawn with: @create chrome legs:world.cyberware_items.ChromeLegs
    """

    buff_class = ChromeLegsBuff
    body_mods = {
        "left thigh":  ("lock", "A precision-machined chrome prosthetic, seamlessly integrated at the hip."),
        "right thigh": ("lock", "A precision-machined chrome prosthetic, seamlessly integrated at the hip."),
        "left foot":   ("lock", "An articulated mechanical foot with independently moving toes."),
        "right foot":  ("lock", "An articulated mechanical foot with independently moving toes."),
    }
