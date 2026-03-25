"""
Artistry E-tier specialization: one permanent branch, roll bonus in that area only.
Branches: tailoring (garment finalize), stage (music performance commands), visual (tattoos / painting).
"""
from world.constants import SKILL_GRADE_THRESHOLDS

SPECIALIZATION_E_THRESHOLD = int(SKILL_GRADE_THRESHOLDS["E"])
ARTISTRY_SPECIALIZATION_ROLL_BONUS = 5

SPECIALIZATION_TAILORING = "tailoring"
SPECIALIZATION_STAGE = "stage"
SPECIALIZATION_VISUAL = "visual"

_VALID_KEYS = frozenset({SPECIALIZATION_TAILORING, SPECIALIZATION_STAGE, SPECIALIZATION_VISUAL})


def get_artistry_specialization(character):
    return getattr(character.db, "artistry_specialization", None)


def set_artistry_specialization(character, key: str):
    if key not in _VALID_KEYS:
        return False
    character.db.artistry_specialization = key
    return True


def needs_artistry_specialization_choice(character):
    if not character or not hasattr(character, "get_skill_level"):
        return False
    if get_artistry_specialization(character):
        return False
    lvl = int(character.get_skill_level("artistry") or 0)
    return lvl >= SPECIALIZATION_E_THRESHOLD


def get_specialization_roll_bonus(character, branch: str) -> int:
    if get_artistry_specialization(character) != branch:
        return 0
    return ARTISTRY_SPECIALIZATION_ROLL_BONUS


def open_artistry_specialization_menu(caller):
    """Open EvMenu to pick specialization. No-op if not needed."""
    if not needs_artistry_specialization_choice(caller):
        return
    from evennia.utils.evmenu import EvMenu

    EvMenu(
        caller,
        "world.rpg.artistry_specialization",
        startnode="node_artistry_spec_start",
        persistent=False,
    )


# --- EvMenu nodes ---


def node_artistry_spec_start(caller, raw_string, **kwargs):
    text = (
        "|yArtistry|n has reached grade |wE|n. Choose a permanent specialization.\n\n"
        "|w1|n — |cTailoring|n — bonus to finalizing garments from bolts.\n"
        "|w2|n — |cStage performance|n — bonus to musical performances and improv.\n"
        "|w3|n — |cVisual arts|n — bonus to tattoos, painting, and drawing.\n\n"
        "|wq|n — Close (use |wartistry specialize|n later).\n"
    )
    options = [
        {"key": "1", "desc": "Tailoring", "goto": "node_artistry_spec_tailoring"},
        {"key": "2", "desc": "Stage performance", "goto": "node_artistry_spec_stage"},
        {"key": "3", "desc": "Visual arts", "goto": "node_artistry_spec_visual"},
        {"key": "q", "desc": "Close", "goto": "node_artistry_spec_exit"},
    ]
    return text, options


def _apply_spec(caller, key):
    set_artistry_specialization(caller, key)
    labels = {
        SPECIALIZATION_TAILORING: "tailoring",
        SPECIALIZATION_STAGE: "stage performance",
        SPECIALIZATION_VISUAL: "visual arts",
    }
    caller.msg("|gYou specialize in %s.|n" % labels.get(key, key))


def node_artistry_spec_tailoring(caller, raw_string, **kwargs):
    _apply_spec(caller, SPECIALIZATION_TAILORING)
    return None, None


def node_artistry_spec_stage(caller, raw_string, **kwargs):
    _apply_spec(caller, SPECIALIZATION_STAGE)
    return None, None


def node_artistry_spec_visual(caller, raw_string, **kwargs):
    _apply_spec(caller, SPECIALIZATION_VISUAL)
    return None, None


def node_artistry_spec_exit(caller, raw_string, **kwargs):
    caller.msg(
        "|xYou can choose later with |wartistry specialize|n or |wartistry specialize <tailoring|stage|visual>|n.|n"
    )
    return None, None
