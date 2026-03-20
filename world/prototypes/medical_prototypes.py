# Medical tools: typeclasses set db fields in at_object_creation; optional key for display.

_MED = ["medical"]
_MED_CONS = ["medical", "consumable"]

MED_BIOSCANNER = {
    "prototype_key": "MED_BIOSCANNER",
    "prototype_tags": _MED,
    "key": "hand bioscanner",
    "typeclass": "typeclasses.medical_tools.Bioscanner",
}

MED_BANDAGES = {
    "prototype_key": "MED_BANDAGES",
    "prototype_tags": _MED_CONS,
    "key": "bandages",
    "typeclass": "typeclasses.medical_tools.Bandages",
}

MED_MEDKIT = {
    "prototype_key": "MED_MEDKIT",
    "prototype_tags": _MED_CONS,
    "key": "medkit",
    "typeclass": "typeclasses.medical_tools.Medkit",
}

MED_SUTURE_KIT = {
    "prototype_key": "MED_SUTURE_KIT",
    "prototype_tags": _MED_CONS,
    "key": "suture kit",
    "typeclass": "typeclasses.medical_tools.SutureKit",
}

MED_SPLINT = {
    "prototype_key": "MED_SPLINT",
    "prototype_tags": _MED_CONS,
    "key": "splint",
    "typeclass": "typeclasses.medical_tools.Splint",
}

MED_HEMOSTATIC = {
    "prototype_key": "MED_HEMOSTATIC",
    "prototype_tags": _MED_CONS,
    "key": "hemostatic agent",
    "typeclass": "typeclasses.medical_tools.HemostaticAgent",
}

MED_TOURNIQUET = {
    "prototype_key": "MED_TOURNIQUET",
    "prototype_tags": _MED_CONS,
    "key": "tourniquet",
    "typeclass": "typeclasses.medical_tools.Tourniquet",
}

MED_SURGICAL_KIT = {
    "prototype_key": "MED_SURGICAL_KIT",
    "prototype_tags": _MED_CONS,
    "key": "surgical kit",
    "typeclass": "typeclasses.medical_tools.SurgicalKit",
}

MED_CO_AMOXICLAV = {
    "prototype_key": "MED_CO_AMOXICLAV",
    "prototype_tags": _MED_CONS,
    "key": "co-amoxiclav",
    "typeclass": "typeclasses.medical_tools.CoAmoxiclav",
}

MED_CEPHALEXIN = {
    "prototype_key": "MED_CEPHALEXIN",
    "prototype_tags": _MED_CONS,
    "key": "cephalexin",
    "typeclass": "typeclasses.medical_tools.Cephalexin",
}

MED_DOXYCYCLINE = {
    "prototype_key": "MED_DOXYCYCLINE",
    "prototype_tags": _MED_CONS,
    "key": "doxycycline",
    "typeclass": "typeclasses.medical_tools.Doxycycline",
}

MED_METRONIDAZOLE = {
    "prototype_key": "MED_METRONIDAZOLE",
    "prototype_tags": _MED_CONS,
    "key": "metronidazole",
    "typeclass": "typeclasses.medical_tools.Metronidazole",
}

MED_CLINDAMYCIN = {
    "prototype_key": "MED_CLINDAMYCIN",
    "prototype_tags": _MED_CONS,
    "key": "clindamycin",
    "typeclass": "typeclasses.medical_tools.Clindamycin",
}

MED_PIP_TAZO = {
    "prototype_key": "MED_PIP_TAZO",
    "prototype_tags": _MED_CONS,
    "key": "piperacillin/tazobactam",
    "typeclass": "typeclasses.medical_tools.PiperacillinTazobactam",
}

MED_VANCOMYCIN = {
    "prototype_key": "MED_VANCOMYCIN",
    "prototype_tags": _MED_CONS,
    "key": "vancomycin",
    "typeclass": "typeclasses.medical_tools.Vancomycin",
}

MED_OR_STATION = {
    "prototype_key": "MED_OR_STATION",
    "prototype_tags": _MED,
    "key": "operating theatre",
    "typeclass": "typeclasses.medical_tools.ORStation",
}

MED_OPERATING_TABLE = {
    "prototype_key": "MED_OPERATING_TABLE",
    "prototype_tags": _MED,
    "key": "operating table",
    "typeclass": "typeclasses.medical_tools.OperatingTable",
}

MED_DEFIBRILLATOR = {
    "prototype_key": "MED_DEFIBRILLATOR",
    "prototype_tags": _MED_CONS,
    "key": "defibrillator",
    "typeclass": "typeclasses.medical_tools.Defibrillator",
}

MED_SCALPEL = {
    "prototype_key": "MED_SCALPEL",
    "prototype_tags": _MED_CONS,
    "key": "scalpel",
    "desc": "A thin-handled surgical blade. Clinic-grade steel made for fine, ugly work.",
    "typeclass": "typeclasses.items.Item",
    "attrs": [
        ("is_scalpel", True),
        ("uses_remaining", 10),
        ("uses_max", 10),
        ("item_type", "scalpel"),
    ],
    "tags": [("scalpel", "item_type"), ("medical", "item_type")],
}
