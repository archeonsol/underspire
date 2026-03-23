"""Vehicle-mounted weapon objects."""

from typeclasses.objects import Object


class VehicleWeapon(Object):
    """
    A weapon that can be installed on a vehicle mount point.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.weapon_key = ""
        self.db.weapon_name = ""
        self.db.damage = 10
        self.db.personnel_damage = 10
        self.db.damage_type = "kinetic"
        self.db.accuracy = 0
        self.db.fire_rate = 1
        self.db.ammo_capacity = 0
        self.db.ammo_current = 0
        self.db.reload_time = 0
        self.db.weapon_condition = 100
        self.db.wear_per_shot = 0.5
        self.db.mount_types = ["turret"]
        self.db.vehicle_types = ["ground", "motorcycle", "aerial"]
        self.db.anti_personnel_mod = 0
        self.db.anti_vehicle_mod = 0
        self.db.special = []
        self.db.installed_on = None
        self.db.desc_addon = ""
        self.db.fire_message_hit = ""
        self.db.fire_message_miss = ""
        self.db.fire_message_crit = ""
        self.db.fire_hit = ""
        self.db.fire_miss = ""
        self.db.fire_crit = ""

    def apply_catalog(self, key: str) -> None:
        from world.combat.vehicle_weapons import VEHICLE_WEAPONS

        data = VEHICLE_WEAPONS.get(key)
        if not data:
            return
        self.db.weapon_key = key
        self.db.weapon_name = data.get("name", key)
        self.db.damage = int(data.get("damage", 10))
        self.db.personnel_damage = int(data.get("personnel_damage", self.db.damage))
        self.db.damage_type = data.get("damage_type", "kinetic")
        self.db.accuracy = int(data.get("accuracy", 0))
        self.db.fire_rate = int(data.get("fire_rate", 1))
        self.db.ammo_capacity = int(data.get("ammo_capacity", 0))
        self.db.ammo_current = self.db.ammo_capacity
        self.db.reload_time = int(data.get("reload_time", 0))
        self.db.wear_per_shot = float(data.get("wear_per_shot", 0.5))
        self.db.mount_types = list(data.get("mount_types", ["turret"]))
        self.db.vehicle_types = list(data.get("vehicle_types", ["ground"]))
        self.db.anti_personnel_mod = int(data.get("anti_personnel_mod", 0))
        self.db.anti_vehicle_mod = int(data.get("anti_vehicle_mod", 0))
        self.db.special = list(data.get("special", []))
        self.db.desc_addon = data.get("desc_addon", "")
        self.db.fire_hit = data.get("fire_hit", "")
        self.db.fire_miss = data.get("fire_miss", "")
        self.db.fire_crit = data.get("fire_crit", "")
        self.db.fire_message_hit = self.db.fire_hit
        self.db.fire_message_miss = self.db.fire_miss
        self.db.fire_message_crit = self.db.fire_crit


class DeployedMine(Object):
    """Contact mine dropped by mine_dropper."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.damage = 40
        self.db.damage_type = "explosive"
        self.db.deployed_by = None
