"""
Motorcycle / mounted combat modifiers. Stacks with room size modifiers.
"""
from __future__ import annotations

from world.skills import WEAPON_KEY_TO_SKILL

MOUNTED_COMBAT_MODIFIERS = {
    "unarmed": -15,
    "short_blades": -5,
    "long_blades": -12,
    "blunt_weaponry": -8,
    "sidearms": 0,
    "longarms": -20,
    "automatics": -10,
}

MOMENTUM_BONUSES = {
    "unarmed": 3,
    "short_blades": 5,
    "long_blades": 0,
    "blunt_weaponry": 16,
    "sidearms": 3,
    "longarms": 0,
    "automatics": 5,
}

MOMENTUM_DEFENSE_PENALTY = -5

MELEE_WEAPON_CLASSES = frozenset({"unarmed", "short_blades", "long_blades", "blunt_weaponry"})


def _weapon_key_to_skill_class(weapon_key: str) -> str:
    sk = WEAPON_KEY_TO_SKILL.get(weapon_key, "unarmed")
    return sk


def mounted_combat_bonus(character) -> int:
    driving = character.get_skill_level("driving") or 0
    return driving // 5


def _is_biker(character) -> bool:
    bike = getattr(character.db, "mounted_on", None) if character and getattr(character, "db", None) else None
    if not bike:
        return False
    return getattr(bike.db, "vehicle_type", None) == "motorcycle"


def _motorcycle_combat_room(room) -> bool:
    """Biker combat modifiers only on street/tunnel vehicle-access rooms."""
    if not room or not hasattr(room, "tags"):
        return False
    t = room.tags
    from typeclasses.vehicles import VEHICLE_ACCESS_CAT

    return t.has("street", category=VEHICLE_ACCESS_CAT) or t.has("tunnel", category=VEHICLE_ACCESS_CAT)


def has_momentum(character) -> bool:
    return bool(character and getattr(character.ndb, "_biker_momentum", False))


def set_biker_momentum(character) -> None:
    if not character:
        return
    character.ndb._biker_momentum = True
    from evennia.utils import delay

    delay(8, _clear_momentum_cb, character.id)


def _clear_momentum_cb(char_id: int) -> None:
    from evennia.utils.search import search_object

    res = search_object(f"#{char_id}")
    if res:
        res[0].ndb._biker_momentum = False


def clear_biker_momentum_after_attack(attacker) -> None:
    if attacker and getattr(attacker.ndb, "_biker_momentum", False):
        attacker.ndb._biker_momentum = False


def get_mounted_attack_mod(attacker, weapon_key: str) -> int:
    """Extra atk_mod when attacker is on a motorcycle in a valid road room."""
    if not attacker or not getattr(attacker, "db", None):
        return 0
    if not _is_biker(attacker):
        return 0
    room = getattr(attacker, "location", None)
    if not _motorcycle_combat_room(room):
        return 0
    wclass = _weapon_key_to_skill_class(weapon_key)
    base = int(MOUNTED_COMBAT_MODIFIERS.get(wclass, -10))
    bonus = mounted_combat_bonus(attacker)
    momentum = 0
    if has_momentum(attacker):
        momentum = int(MOMENTUM_BONUSES.get(wclass, 0))
    return base + bonus + momentum


def get_antibiker_melee_mod(defender, weapon_key: str) -> int:
    """Attacker (not defender) is adjusted when striking a mounted biker — use from attacker perspective."""
    return 0


def pedestrian_vs_biker_melee_penalty(defender, weapon_key: str) -> int:
    """If defender is biker on bike in road room, attacker (caller uses weapon_key) gets -5 for melee."""
    if not defender or not _is_biker(defender):
        return 0
    room = getattr(defender, "location", None)
    if not _motorcycle_combat_room(room):
        return 0
    wclass = _weapon_key_to_skill_class(weapon_key)
    if wclass in MELEE_WEAPON_CLASSES:
        return -5
    return 0


def biker_defense_bonus(defender) -> int:
    """Extra defense rating when defender is mounted biker (speed); momentum makes you harder to track."""
    if not defender or not _is_biker(defender):
        return 0
    room = getattr(defender, "location", None)
    if not _motorcycle_combat_room(room):
        return 0
    drv = defender.get_skill_level("driving") or 0
    out = int(drv // 4)
    if has_momentum(defender):
        out += MOMENTUM_DEFENSE_PENALTY
    return out


# Each entry is (you_template, third_person_template).
# {biker} = third-person name; {weapon} = weapon name; {bike} = bike label.
_BIKER_PREFIXES_MELEE = [
    ("You lean hard off the saddle and swing {weapon} in a wide arc.",
     "Leaning hard off the saddle, {biker} swings {weapon} in a wide arc."),
    ("You wrench the throttle and cut in close, {weapon} already moving.",
     "{biker} wrenches the throttle and cuts in close, {weapon} already moving."),
    ("The engine screams as you carve past, {weapon} slashing through the gap.",
     "The engine screams as {biker} carves past, {weapon} slashing through the gap."),
    ("You drop a shoulder and drive {weapon} forward off the bike.",
     "{biker} drops a shoulder and drives {weapon} forward off the bike."),
    ("Throttle wide, you close the distance in a heartbeat and bring {weapon} around.",
     "Throttle wide, {biker} closes the distance in a heartbeat and brings {weapon} around."),
]

_BIKER_PREFIXES_GUN = [
    ("You steady the {weapon} one-handed, the engine's vibration absorbed into the shot.",
     "{biker} steadies the {weapon} one-handed, the engine's vibration absorbed into the shot."),
    ("The bike holds its line as you level the {weapon} and fire.",
     "The bike holds its line as {biker} levels the {weapon} and fires."),
    ("You throttle back just enough to draw a bead, {weapon} raised.",
     "{biker} throttles back just enough to draw a bead, {weapon} raised."),
    ("Engine idling low, you sight down the {weapon} and squeeze.",
     "Engine idling low, {biker} sights down the {weapon} and squeezes."),
    ("You swing wide and bring the {weapon} to bear in a single smooth motion.",
     "{biker} swings wide and brings the {weapon} to bear in a single smooth motion."),
]

_BIKER_PREFIXES_UNARMED = [
    ("Standing on the pegs, you launch off the bike and drive a fist forward.",
     "Standing on the pegs, {biker} launches off the bike and drives a fist forward."),
    ("You kill the throttle and swing a bare-knuckle blow from the saddle.",
     "{biker} kills the throttle and swings a bare-knuckle blow from the saddle."),
    ("The engine drops to idle as you lean in and throw a punch.",
     "The engine drops to idle as {biker} leans in and throws a punch."),
    ("You grab a fistful of jacket and yank, swinging a free elbow.",
     "{biker} grabs a fistful of jacket and yanks, swinging a free elbow."),
    ("Momentum carrying the bike forward, you hammer a strike across the gap.",
     "Momentum carrying the bike forward, {biker} hammers a strike across the gap."),
]

_MELEE_SKILLS = frozenset({"short_blades", "long_blades", "blunt_weaponry"})
_GUN_SKILLS = frozenset({"sidearms", "longarms", "automatics"})


def biker_combat_lines(attacker, weapon_key: str, weapon_obj=None) -> tuple[str, str] | tuple[None, None]:
    """
    Return (attacker_line, room_line) for a biker's attack setup, or (None, None) if not a biker.
    attacker_line uses "You"; room_line uses the third-person recog name per viewer (caller must
    substitute {biker} themselves using combat_role_name_attacker_party).
    The random choice is made once so both lines are consistent.
    """
    import random as _random

    if not _is_biker(attacker):
        return None, None

    wname = (
        getattr(weapon_obj, "key", None) or weapon_key.replace("_", " ")
        if weapon_obj else weapon_key.replace("_", " ")
    )

    wclass = _weapon_key_to_skill_class(weapon_key)
    if wclass in _MELEE_SKILLS:
        pool = _BIKER_PREFIXES_MELEE
    elif wclass in _GUN_SKILLS:
        pool = _BIKER_PREFIXES_GUN
    else:
        pool = _BIKER_PREFIXES_UNARMED

    you_tpl, room_tpl = _random.choice(pool)
    return you_tpl.format(weapon=wname), room_tpl


def biker_hit_splash(biker, damage: int, weapon_class_or_key) -> None:
    """When a biker takes HP damage, bike may take splash damage; high damage can force dismount."""
    import random

    bike = getattr(biker.db, "mounted_on", None) if biker and getattr(biker, "db", None) else None
    if not bike:
        return
    if random.random() < 0.3:
        try:
            from world.combat.vehicle_combat import apply_vehicle_damage

            bike_damage = max(1, int(damage) // 3)
            apply_vehicle_damage(bike, bike_damage)
        except Exception:
            pass
    if int(damage or 0) >= 20:
        tier, _ = biker.roll_check(["endurance"], "driving", difficulty=max(1, int(damage) // 2))
        if tier == "Failure":
            try:
                from world.vehicle_mounts import force_dismount

                force_dismount(biker, bike, reason="damage")
            except Exception:
                pass
