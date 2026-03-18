# D:\moo\mootest\typeclasses\weapons.py
"""
Weapon typeclasses for combat. Each template maps to a weapon skill and a key in
world.combat.WEAPON_DATA. Use these as typeclasses when creating custom weapons
(e.g. create a knife, then set key/desc to "combat knife"; create from LongBladeWeapon
for a sword). weapon_key determines which skill is rolled and which moves/damage table apply.
Damage type (slashing/impact/penetrating/magical) drives trauma and injury; set db.damage_type
to override the default for this weapon class. Ranged weapons use world.ammo and require loading.
"""
from evennia import DefaultObject


# Keys must exist in world.combat.WEAPON_DATA and world.skills.WEAPON_KEY_TO_SKILL
WEAPON_KEY_UNARMED = "fists"
WEAPON_KEY_SHORT_BLADE = "knife"
WEAPON_KEY_LONG_BLADE = "long_blade"
WEAPON_KEY_BLUNT = "blunt"
WEAPON_KEY_SIDEARM = "sidearm"
WEAPON_KEY_LONGARM = "longarm"
WEAPON_KEY_AUTOMATIC = "automatic"

# Fallback: if an object has no db.weapon_key (e.g. created before typeclass ran), infer from typeclass
TYPECLASS_WEAPON_KEYS = {
    "typeclasses.weapons.UnarmedWeapon": WEAPON_KEY_UNARMED,
    "typeclasses.weapons.ShortBladeWeapon": WEAPON_KEY_SHORT_BLADE,
    "typeclasses.weapons.LongBladeWeapon": WEAPON_KEY_LONG_BLADE,
    "typeclasses.weapons.BluntWeapon": WEAPON_KEY_BLUNT,
    "typeclasses.weapons.SidearmWeapon": WEAPON_KEY_SIDEARM,
    "typeclasses.weapons.LongarmWeapon": WEAPON_KEY_LONGARM,
    "typeclasses.weapons.AutomaticWeapon": WEAPON_KEY_AUTOMATIC,
    "typeclasses.weapons.CombatWeapon": WEAPON_KEY_UNARMED,
}


def get_weapon_key(obj):
    """Return weapon_key for this object; use db.weapon_key or infer from typeclass."""
    if obj is None:
        return None
    key = getattr(obj.db, "weapon_key", None)
    if key:
        return key
    typeclass_path = getattr(obj, "typeclass_path", None)
    if not typeclass_path and hasattr(obj, "__class__"):
        typeclass_path = f"{getattr(obj.__class__, '__module__', '')}.{getattr(obj.__class__, '__name__', '')}"
    return TYPECLASS_WEAPON_KEYS.get(typeclass_path)


def get_damage_type_for_weapon(weapon_obj):
    """Return damage type for this weapon; use db.damage_type if set, else from weapon_key via world.combat.damage_types."""
    if weapon_obj is None:
        return "impact"
    try:
        from world.combat.damage_types import get_damage_type
        return get_damage_type(get_weapon_key(weapon_obj), weapon_obj)
    except Exception:
        return "impact"


def _is_ranged_weapon_key(weapon_key):
    try:
        from world.ammo import is_ranged_weapon
        return is_ranged_weapon(weapon_key)
    except Exception:
        return False


class CombatWeapon(DefaultObject):
    """
    Base typeclass for all combat weapons. Set db.weapon_key to a key in
    world.combat.WEAPON_DATA (e.g. "knife", "long_blade"). Subclasses set a
    default weapon_key so you can create custom weapons by choosing the right
    template and renaming/describing the object.
    Ranged weapons also have db.ammo_type, db.ammo_capacity, db.ammo_current.
    """
    def at_object_creation(self):
        self.db.weapon_key = WEAPON_KEY_UNARMED
        self.db.damage_type = "impact"  # slashing, impact, penetrating, burn/freeze/arc/void via overrides
        self.db.damage_mod = 0  # Future: quality modifier applied to move damage
        # Subclasses will normally set weapon_key and then bind to a concrete template.
        if not getattr(self.db, "weapon_template", None):
            self.db.weapon_template = self.key

    def _apply_weapon_template_defaults(self):
        """
        Populate this object's damage_type, weapon_tier, and desc from world.combat.weapon_tiers
        based on db.weapon_key and db.weapon_template (or key as a fallback).
        This makes spawning e.g. 'Scrap Knife' immediately use the Scrap Knife template.
        """
        weapon_key = getattr(self.db, "weapon_key", None)
        template_name = getattr(self.db, "weapon_template", None) or self.key
        if not weapon_key or not template_name:
            return
        try:
            from world.combat.weapon_tiers import find_weapon_template
        except Exception:
            return
        entry, tier = find_weapon_template(weapon_key, template_name)
        if not entry:
            return
        # Ensure we store the canonical template name and tier
        self.db.weapon_template = entry.get("name", template_name)
        self.db.weapon_tier = entry.get("tier", tier or 1)
        # Use template damage_type if provided
        dt = entry.get("damage_type")
        if dt:
            self.db.damage_type = dt
        # Only override description if none was set yet
        if not getattr(self.db, "desc", None):
            desc = entry.get("desc")
            if desc:
                self.db.desc = desc

    def has_ammo(self):
        """True if this weapon is ranged and has at least one round loaded."""
        if not _is_ranged_weapon_key(self.db.weapon_key):
            return True
        return (self.db.ammo_current or 0) > 0

    def rounds_remaining(self):
        """Current rounds in magazine; 0 for melee or unloaded ranged."""
        if not _is_ranged_weapon_key(self.db.weapon_key):
            return None  # N/A
        return int(self.db.ammo_current or 0)


# --- Template classes: one per weapon skill ---

class UnarmedWeapon(CombatWeapon):
    """
    Unarmed / fists. Use for brass knuckles, claws, shock gloves, or other
    "unarmed" style weapons that still use the Unarmed skill and fist move set.
    """
    def at_object_creation(self):
        super().at_object_creation()
        self.db.weapon_key = WEAPON_KEY_UNARMED
        self.db.damage_type = "impact"
        if not getattr(self.db, "weapon_template", None):
            self.db.weapon_template = self.key
        self._apply_weapon_template_defaults()
        if not self.db.desc:
            self.db.desc = "A weapon that augments or counts as unarmed combat."


class ShortBladeWeapon(CombatWeapon):
    """
    Short Blades skill. Knives, daggers, machetes, tanto. Use this typeclass
    then set key/desc to your specific weapon (e.g. "combat knife", "stiletto").
    """
    def at_object_creation(self):
        super().at_object_creation()
        self.db.weapon_key = WEAPON_KEY_SHORT_BLADE
        self.db.damage_type = "slashing"
        if not getattr(self.db, "weapon_template", None):
            self.db.weapon_template = self.key
        self._apply_weapon_template_defaults()
        if not self.db.desc:
            self.db.desc = "A short blade: knife, dagger, or similar."


class LongBladeWeapon(CombatWeapon):
    """
    Long Blades skill. Swords, katanas, cutlasses, long knives. Create from this
    template and customize key/desc (e.g. "katana", "military saber").
    """
    def at_object_creation(self):
        super().at_object_creation()
        self.db.weapon_key = WEAPON_KEY_LONG_BLADE
        self.db.damage_type = "slashing"
        if not getattr(self.db, "weapon_template", None):
            self.db.weapon_template = self.key
        self._apply_weapon_template_defaults()
        # Generic long blade defaults to a basic tunnel sword.
        self.db.weapon_template = "Tunnel Shortsword"
        if not self.db.desc:
            self.db.desc = "A long blade: sword or similar."


class BluntWeapon(CombatWeapon):
    """
    Blunt Weaponry skill. Clubs, bats, hammers, staves, saps. Create from this
    template and set key/desc (e.g. "tire iron", "crowbar", "stun baton").
    """
    def at_object_creation(self):
        super().at_object_creation()
        self.db.weapon_key = WEAPON_KEY_BLUNT
        self.db.damage_type = "impact"
        if not getattr(self.db, "weapon_template", None):
            self.db.weapon_template = self.key
        self._apply_weapon_template_defaults()
        # Generic blunt weapon defaults to an early crafted cudgel.
        self.db.weapon_template = "Bound Cudgel"
        if not self.db.desc:
            self.db.desc = "A blunt weapon: club, bat, hammer, or similar."


class _RangedWeaponMixin:
    """Shared ammo fields for sidearm, longarm, automatic. Not used alone."""
    def at_object_creation_ranged(self, ammo_type, default_capacity):
        self.db.ammo_type = ammo_type
        self.db.ammo_capacity = default_capacity
        self.db.ammo_current = 0


class SidearmWeapon(CombatWeapon, _RangedWeaponMixin):
    """
    Sidearms skill. Pistols, revolvers, holdouts. Requires pistol ammo to fire.
    Create from this template and set key/desc (e.g. "heavy pistol", "revolver").
    """
    def at_object_creation(self):
        super().at_object_creation()
        self.db.weapon_key = WEAPON_KEY_SIDEARM
        self.db.damage_type = "penetrating"
        from world.ammo import AMMO_TYPE_SIDEARM, DEFAULT_AMMO_CAPACITY
        self.at_object_creation_ranged(AMMO_TYPE_SIDEARM, DEFAULT_AMMO_CAPACITY["sidearm"])
        if not getattr(self.db, "weapon_template", None):
            self.db.weapon_template = self.key
        self._apply_weapon_template_defaults()
        if not self.db.desc:
            self.db.desc = "A sidearm: pistol or revolver. It needs pistol ammo to fire."


class LongarmWeapon(CombatWeapon, _RangedWeaponMixin):
    """
    Longarms skill. Rifles, shotguns, carbines (semi or bolt). Requires rifle ammo.
    Create from this template and set key/desc (e.g. "sniper rifle", "shotgun").
    """
    def at_object_creation(self):
        super().at_object_creation()
        self.db.weapon_key = WEAPON_KEY_LONGARM
        self.db.damage_type = "penetrating"
        from world.ammo import AMMO_TYPE_LONGARM, DEFAULT_AMMO_CAPACITY
        self.at_object_creation_ranged(AMMO_TYPE_LONGARM, DEFAULT_AMMO_CAPACITY["longarm"])
        if not getattr(self.db, "weapon_template", None):
            self.db.weapon_template = self.key
        self._apply_weapon_template_defaults()
        if not self.db.desc:
            self.db.desc = "A longarm: rifle or shotgun. It needs rifle ammo to fire."


class AutomaticWeapon(CombatWeapon, _RangedWeaponMixin):
    """
    Automatics skill. SMGs, assault rifles, LMGs. Requires automatic ammo.
    Create from this template and set key/desc (e.g. "SMG", "assault rifle").
    """
    def at_object_creation(self):
        super().at_object_creation()
        self.db.weapon_key = WEAPON_KEY_AUTOMATIC
        self.db.damage_type = "penetrating"
        from world.ammo import AMMO_TYPE_AUTOMATIC, DEFAULT_AMMO_CAPACITY
        self.at_object_creation_ranged(AMMO_TYPE_AUTOMATIC, DEFAULT_AMMO_CAPACITY["automatic"])
        if not getattr(self.db, "weapon_template", None):
            self.db.weapon_template = self.key
        self._apply_weapon_template_defaults()
        if not self.db.desc:
            self.db.desc = "An automatic weapon: SMG, assault rifle, or similar. It needs automatic ammo to fire."
