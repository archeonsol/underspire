"""
Lore vehicle prototypes.

Spawn: |wspawnitem list vehicle|n, |wspawnitem list vehicle ground|n (or |wmotorcycle|n, |waerial|n).
Tags: |wvehicle|n (all), plus |wground|n |wmotorcycle|n |waerial|n for sub-lists.
"""

_VEHICLE_GROUND = ["vehicle", "ground"]
_VEHICLE_MOTORCYCLE = ["vehicle", "motorcycle"]
_VEHICLE_AERIAL = ["vehicle", "aerial"]

GROUND_VEHICLE_PROTOTYPES = {
    "rattler": {
        "prototype_key": "rattler",
        "prototype_tags": _VEHICLE_GROUND,
        "typeclass": "typeclasses.vehicles.Vehicle",
        "key": "buggy",
        "attrs": [
            ("vehicle_type", "ground"),
            ("vehicle_name", "a rattler buggy"),
            ("max_passengers", 4),
            ("speed_class", "normal"),
            ("driving_skill", "driving"),
            ("has_interior", True),
            ("vehicle_max_hp", 100),
            ("vehicle_hp", 100),
            (
                "desc",
                "A dented four-door sedan held together by rust, prayer, and welding slag. The paint is three colours, "
                "none of them original. The engine knocks. The seats are patched vinyl. It runs. That's the best thing "
                "anyone can say about it.",
            ),
        ],
    },
    "hauler": {
        "prototype_key": "hauler",
        "prototype_tags": _VEHICLE_GROUND,
        "typeclass": "typeclasses.vehicles.Vehicle",
        "key": "cargo hauler",
        "attrs": [
            ("vehicle_type", "ground"),
            ("vehicle_name", "a cargo hauler"),
            ("max_passengers", 2),
            ("speed_class", "slow"),
            ("driving_skill", "driving"),
            ("has_interior", True),
            ("vehicle_max_hp", 150),
            ("vehicle_hp", 150),
            (
                "desc",
                "A heavy-framed utility vehicle with a flatbed bolted to the chassis. Built for moving freight through "
                "the undercity's tunnels. The cab is armoured with scrap plate. The suspension groans under nothing — "
                "it groans worse under load.",
            ),
        ],
    },
    "prowler": {
        "prototype_key": "prowler",
        "prototype_tags": _VEHICLE_GROUND,
        "typeclass": "typeclasses.vehicles.Vehicle",
        "key": "Imperium prowler",
        "attrs": [
            ("vehicle_type", "ground"),
            ("vehicle_name", "an Imperium prowler"),
            ("max_passengers", 4),
            ("speed_class", "fast"),
            ("driving_skill", "driving"),
            ("has_interior", True),
            ("vehicle_max_hp", 120),
            ("vehicle_hp", 120),
            (
                "desc",
                "Matte black, armoured, silent engine. The Imperium Guard's patrol vehicle. Reinforced ram bar on the "
                "front. Strobing red lights recessed into the roof — they only come on when someone's about to have a "
                "bad day. The windows are tinted past legal. There is no legal.",
            ),
        ],
    },
}

MOTORCYCLE_PROTOTYPES = {
    "ratbike": {
        "prototype_key": "ratbike",
        "prototype_tags": _VEHICLE_MOTORCYCLE,
        "typeclass": "typeclasses.vehicles.Motorcycle",
        "key": "ratbike",
        "attrs": [
            ("vehicle_name", "a ratbike"),
            ("speed_class", "fast"),
            ("max_passengers", 1),
            ("vehicle_max_hp", 30),
            ("vehicle_hp", 30),
            (
                "desc",
                "A stripped-down frame with an oversized engine bolted to it. No fairings, no paint, no pretence. "
                "The handlebars are wrapped in electrical tape. The exhaust pipe is unshielded — touch it and you learn. "
                "Popular in the Warrens because it fits through alleys a car can't.",
            ),
        ],
    },
    "courier_bike": {
        "prototype_key": "courier_bike",
        "prototype_tags": _VEHICLE_MOTORCYCLE,
        "typeclass": "typeclasses.vehicles.Motorcycle",
        "key": "courier bike",
        "attrs": [
            ("vehicle_name", "a courier bike"),
            ("speed_class", "fast"),
            ("max_passengers", 1),
            ("has_pillion", False),
            (
                "desc",
                "A light electric bike with cargo panniers. Near-silent motor. Guild couriers use these to move small "
                "packages between levels. Fast, manoeuvrable, and utterly unremarkable — which is the point.",
            ),
        ],
    },
    "enforcer_bike": {
        "prototype_key": "enforcer_bike",
        "prototype_tags": _VEHICLE_MOTORCYCLE,
        "typeclass": "typeclasses.vehicles.Motorcycle",
        "key": "enforcer cycle",
        "attrs": [
            ("vehicle_name", "an enforcer cycle"),
            ("speed_class", "fast"),
            ("max_passengers", 2),
            ("has_pillion", True),
            (
                "desc",
                "Heavy-framed, armoured fairings, strobing blue lights recessed into the cowling. The Imperium Guard's "
                "pursuit vehicle. It's not the fastest bike in the undercity but nobody outruns the radio.",
            ),
        ],
    },
}

AV_PROTOTYPES = {
    "skimmer": {
        "prototype_key": "skimmer",
        "prototype_tags": _VEHICLE_AERIAL,
        "typeclass": "typeclasses.vehicles.AerialVehicle",
        "key": "personnel skimmer",
        "attrs": [
            ("vehicle_name", "a personnel skimmer"),
            ("max_passengers", 4),
            ("speed_class", "fast"),
            (
                "desc",
                "A blunt-nosed VTOL craft with ducted fans and a pressurised cabin. The kind of thing the Inquisitorate "
                "uses to move people between levels without touching the freight system. Quiet engine. Tinted canopy. "
                "No markings — which is a marking in itself.",
            ),
        ],
    },
    "cargo_lifter": {
        "prototype_key": "cargo_lifter",
        "prototype_tags": _VEHICLE_AERIAL,
        "typeclass": "typeclasses.vehicles.AerialVehicle",
        "key": "cargo lifter",
        "attrs": [
            ("vehicle_name", "a cargo lifter"),
            ("max_passengers", 2),
            ("speed_class", "slow"),
            (
                "desc",
                "An industrial flying platform with a cargo cage bolted underneath. Open cockpit, no pressurisation, "
                "manual controls. Guild logistics uses these to move heavy equipment between levels when the freight is "
                "too slow. The pilots get hazard pay. Most of them earn it.",
            ),
        ],
    },
}

ALL_VEHICLE_PROTOTYPES = {**GROUND_VEHICLE_PROTOTYPES, **MOTORCYCLE_PROTOTYPES, **AV_PROTOTYPES}

# Evennia prototype loader collects list-of-dicts (see armor_prototypes.PROTOTYPE_LIST)
PROTOTYPE_LIST = list(ALL_VEHICLE_PROTOTYPES.values())
