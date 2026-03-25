"""
Cosmetics system constants: tattoo quality tiers, inkwriter tiers,
makeup type definitions, and quality resolution logic.
"""

# ── Tattoo quality ────────────────────────────────────────────────────────

TATTOO_QUALITY_TIERS = {
    "crude": {
        "name": "crude",
        "desc_prefix": "A crudely inked",
        "color_note": "The lines are uneven, the ink blotchy.",
    },
    "clean": {
        "name": "clean",
        "desc_prefix": "A cleanly inked",
        "color_note": "The lines are steady and the ink sits well.",
    },
    "fine": {
        "name": "fine",
        "desc_prefix": "A finely detailed",
        "color_note": "The detail work is precise, the shading smooth.",
    },
    "masterwork": {
        "name": "masterwork",
        "desc_prefix": "An exquisitely rendered",
        "color_note": "Every line is perfect. The ink seems to live beneath the skin.",
    },
}

QUALITY_ORDER = ["crude", "clean", "fine", "masterwork"]

# Per-code base survival probability used by _apply_color_degradation.
# Span-weighted formula reduces this further for codes that color many characters.
COLOR_SURVIVAL_CHANCE = {
    "crude":      0.30,
    "clean":      0.60,
    "fine":       0.85,
    "masterwork": 1.00,
}

QUALITY_FROM_TIER = {
    "Failure": "crude",
    "Marginal Success": "crude",
    "Full Success": "clean",
    "Critical Success": "fine",
}

# Score-based quality thresholds (min_score -> quality).
# Final quality is still capped by inkwriter tier.
TATTOO_QUALITY_SCORE_THRESHOLDS = [
    (0, "crude"),
    (55, "clean"),
    (85, "fine"),
    (115, "masterwork"),
]

INKWRITER_MAX_QUALITY = {
    1: "clean",
    2: "fine",
    3: "masterwork",
}

INKWRITER_TIERS = {
    1: {
        "name": "Scrap Needle",
        "max_quality": "clean",
        "desc": "A crude tattoo gun assembled from salvaged motor parts and sewing needles. It works. It hurts.",
    },
    2: {
        "name": "Guild Inkwriter",
        "max_quality": "fine",
        "desc": "A precision instrument with interchangeable needle cartridges and adjustable depth. Guild-manufactured.",
    },
    3: {
        "name": "Master's Inkwriter",
        "max_quality": "masterwork",
        "desc": "A Mythos-engineered tattooing device with micro-actuated needles and pigment injection. Surgical precision.",
    },
}


def resolve_tattoo_quality(skill_tier, inkwriter_tier):
    """
    Determine final tattoo quality from skill roll result and inkwriter tier.
    The skill tier sets the achieved quality; the inkwriter caps it.
    """
    achieved = QUALITY_FROM_TIER.get(skill_tier, "crude")
    max_allowed = INKWRITER_MAX_QUALITY.get(int(inkwriter_tier or 1), "clean")

    achieved_idx = QUALITY_ORDER.index(achieved)
    max_idx = QUALITY_ORDER.index(max_allowed)

    return QUALITY_ORDER[min(achieved_idx, max_idx)]


def resolve_tattoo_quality_from_score(final_score, inkwriter_tier):
    """
    Determine tattoo quality from roll final_score and inkwriter tier cap.
    """
    try:
        score = int(final_score or 0)
    except Exception:
        score = 0

    achieved = "crude"
    for min_score, quality in reversed(TATTOO_QUALITY_SCORE_THRESHOLDS):
        if score >= min_score:
            achieved = quality
            break

    max_allowed = INKWRITER_MAX_QUALITY.get(int(inkwriter_tier or 1), "clean")
    achieved_idx = QUALITY_ORDER.index(achieved)
    max_idx = QUALITY_ORDER.index(max_allowed)
    return QUALITY_ORDER[min(achieved_idx, max_idx)]


# ── Makeup type definitions ───────────────────────────────────────────────

MAKEUP_TYPES = {
    "lipstick": {
        "name": "Lipstick",
        "target_parts": ["face"],
        "fallback_rule": None,
        "desc_template": "{pronoun} lips are painted {color_code}{color_name}|n.",
        "apply_echo": "{applier} uncaps the lipstick and carefully traces {target}'s lips in {color_name}.",
        "color_changeable": True,
        "uses_default": 12,
        "wear_duration": 7200,
        "wear_rooms": 100,
    },
    "nail_polish": {
        "name": "Nail Polish",
        "target_parts": ["left hand", "right hand"],
        "fallback_rule": "left_then_right",
        "desc_template": "{pronoun} nails are lacquered in {color_code}{color_name}|n.",
        "apply_echo": "{applier} carefully paints {target}'s nails in {color_name}, one at a time.",
        "color_changeable": False,
        "uses_default": 8,
        "wear_duration": 14400,
        "wear_rooms": 200,
    },
    "eye_shadow": {
        "name": "Eye Shadow",
        "target_parts": ["left eye", "right eye"],
        "fallback_rule": "both_or_available",
        "desc_template": "{pronoun} eyelid is dusted with {color_code}{color_name}|n shadow.",
        "apply_echo": "{applier} sweeps {color_name} shadow across {target}'s eyelids with a soft brush.",
        "color_changeable": True,
        "uses_default": 15,
        "wear_duration": 5400,
        "wear_rooms": 80,
    },
    "eyeliner": {
        "name": "Eyeliner",
        "target_parts": ["left eye", "right eye"],
        "fallback_rule": "both_or_available",
        "desc_template": "{pronoun} eye is lined in {color_code}{color_name}|n.",
        "apply_echo": "{applier} draws a steady line of {color_name} along {target}'s lash line.",
        "color_changeable": True,
        "uses_default": 15,
        "wear_duration": 5400,
        "wear_rooms": 80,
    },
}
