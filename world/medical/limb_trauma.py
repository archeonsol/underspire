"""
Limb trauma: arm/leg fracture severity and chrome replacement when a limb is unsalvageable.

Mirrors organ damage (severity 1–3, destroyed flag) but keyed by limb slot rather than bone name,
since bones like humerus/femur are shared keys for left/right in the fracture model.
"""

# Canonical keys (underscore) — match cyberware chrome_replacement_for on limb implants
LIMB_SLOTS = frozenset({"left_arm", "right_arm", "left_leg", "right_leg"})

LIMB_INFO = {
    "left_arm": ("left arm", "hairline / strain", "displaced fracture", "comminuted / open — critical"),
    "right_arm": ("right arm", "hairline / strain", "displaced fracture", "comminuted / open — critical"),
    "left_leg": ("left leg", "hairline / strain", "displaced fracture", "comminuted / open — critical"),
    "right_leg": ("right leg", "hairline / strain", "displaced fracture", "comminuted / open — critical"),
}


def body_part_to_limb_slot(body_part):
    """Map a hit location to a limb slot, or None if not an arm/leg replacement region."""
    if not body_part:
        return None
    p = (body_part or "").strip().lower()
    if p in ("left arm", "left hand", "left shoulder"):
        return "left_arm"
    if p in ("right arm", "right hand", "right shoulder"):
        return "right_arm"
    if p in ("left thigh", "left foot"):
        return "left_leg"
    if p in ("right thigh", "right foot"):
        return "right_leg"
    return None


def is_limb_destroyed(target, limb_key):
    """
    True if this limb is beyond biological repair and needs chrome replacement.
    Requires max limb_damage severity on an injury with fracture_destroyed set (same pattern as organs).
    """
    if limb_key not in LIMB_SLOTS:
        return False
    if int((target.db.limb_damage or {}).get(limb_key, 0) or 0) < 3:
        return False
    for i in (target.db.injuries or []):
        if limb_key in (i.get("limb_damage") or {}) and i.get("fracture_destroyed"):
            return True
    return False


def is_hand_usable(character, side):
    """
    False if that hand cannot hold items (matching arm unsalvageable / destroyed).
    side: 'left' or 'right'.
    """
    if side == "left":
        return not is_limb_destroyed(character, "left_arm")
    if side == "right":
        return not is_limb_destroyed(character, "right_arm")
    return True


def enforce_limb_hand_restrictions(character):
    """
    Drop anything held in a hand whose arm is destroyed. Idempotent; safe to call from trauma rebuild.
    """
    if not character or not getattr(character, "db", None):
        return
    from commands.inventory_cmds import _update_primary_wielded
    dropped = []
    for arm_key, hand_attr in (("left_arm", "left_hand_obj"), ("right_arm", "right_hand_obj")):
        if not is_limb_destroyed(character, arm_key):
            continue
        obj = getattr(character.db, hand_attr, None)
        if not obj or getattr(obj, "location", None) != character:
            setattr(character.db, hand_attr, None)
            continue
        other_attr = "right_hand_obj" if hand_attr == "left_hand_obj" else "left_hand_obj"
        other = getattr(character.db, other_attr, None)
        two_handed = other is obj
        setattr(character.db, hand_attr, None)
        if two_handed:
            setattr(character.db, other_attr, None)
        if obj.move_to(character, quiet=True):
            nm = obj.get_display_name(character) if hasattr(obj, "get_display_name") else obj.key
            dropped.append(nm)
    if dropped:
        character.msg("|rYour ruined arm won't hold.|n You drop: " + ", ".join(dropped) + ".")
    _update_primary_wielded(character)


LIMB_ALIASES = {
    "left_arm": "left_arm",
    "left arm": "left_arm",
    "l_arm": "left_arm",
    "larm": "left_arm",
    "right_arm": "right_arm",
    "right arm": "right_arm",
    "r_arm": "right_arm",
    "rarm": "right_arm",
    "left_leg": "left_leg",
    "left leg": "left_leg",
    "left thigh": "left_leg",
    "lleg": "left_leg",
    "right_leg": "right_leg",
    "right leg": "right_leg",
    "right thigh": "right_leg",
    "rleg": "right_leg",
}
