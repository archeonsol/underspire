"""
Combat roll math (System 2): logistic opposed checks + quality score.

This module is intentionally combat-only: it doesn't replace the generic
roll_check used by other systems (performance, medical, crafting, etc.).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def sigmoid(x: float) -> float:
    # Numerically stable sigmoid
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


@dataclass(frozen=True)
class CombatRollConfig:
    # Rating computation
    # - "additive": w_skill*skill + w_stats*stat_sum + modifier
    # - "multiplicative": c_mul * stat_eff * (1 + alpha*(skill/150)) + modifier
    rating_model: str = "additive"

    # Weighting for rating computation
    w_skill: float = 1.0
    w_stats: float = 1.0

    # Multiplicative model coefficients (used when rating_model="multiplicative")
    c_mul: float = 1.0
    alpha: float = 1.0

    # Diminishing returns transform for stats before rating.
    # - "none": stat_eff = stat_sum
    # - "log": stat_eff = dr_scale * ln(1 + stat_sum/dr_scale)
    dr_mode: str = "none"
    dr_scale: float = 150.0

    # Logistic steepness: applied to (attacker_rating - defender_rating)
    # With ratings typically in ~0..450, k ~ 0.01-0.03 gives usable curves.
    k: float = 0.015

    # Floors/ceilings keep outcomes from becoming truly impossible/guaranteed.
    min_p: float = 0.05
    max_p: float = 0.95

    # Quality score noise (in rating-delta units). Higher = more swingy damage/crit/body-part bias.
    quality_sigma: float = 18.0

    # Optional biases for specific defensive reactions.
    # Positive bias helps defender (makes parry/dodge more likely).
    parry_bias: float = 0.0
    dodge_bias: float = 0.0
    body_shield_bias: float = -0.5  # make body-shield slightly harder than a normal dodge


DEFAULT_CFG = CombatRollConfig()

def _dr_transform(stat_sum: float, cfg: CombatRollConfig) -> float:
    s = float(stat_sum or 0.0)
    if cfg.dr_mode == "log":
        scale = float(cfg.dr_scale or 150.0)
        if scale <= 0:
            scale = 150.0
        # 150*ln(1 + s/150) keeps early gains meaningful and compresses high-end stacking.
        return scale * math.log(1.0 + (s / scale))
    return s

def load_cfg() -> CombatRollConfig:
    """
    Load combat roll tuning from Evennia/Django settings if available.

    Settings key (optional):
        COMBAT_ROLLS = {
            "w_skill": 1.0,
            "w_stats": 1.0,
            "k": 0.015,
            "min_p": 0.05,
            "max_p": 0.95,
            "quality_sigma": 18.0,
            "parry_bias": 0.0,
            "dodge_bias": 0.0,
            "body_shield_bias": -0.5,
        }
    """
    try:
        from django.conf import settings  # type: ignore

        data = getattr(settings, "COMBAT_ROLLS", None)
        if not isinstance(data, Mapping):
            return DEFAULT_CFG
        kw: dict[str, Any] = {}
        for field in CombatRollConfig.__dataclass_fields__.keys():  # type: ignore[attr-defined]
            if field in data:
                kw[field] = data[field]
        return CombatRollConfig(**kw)
    except Exception:
        return DEFAULT_CFG


def combat_rating(
    actor,
    stat_list: Sequence[str] | str,
    skill_key: str,
    modifier: float = 0.0,
    cfg: CombatRollConfig = DEFAULT_CFG,
) -> float:
    """Compute a deterministic rating used for opposed combat checks."""
    if isinstance(stat_list, str):
        stat_list = [stat_list]

    skill = 0
    if actor and hasattr(actor, "get_skill_level"):
        try:
            skill = int(actor.get_skill_level(skill_key) or 0)
        except Exception:
            skill = 0

    stat_sum = 0
    if actor and hasattr(actor, "get_display_stat"):
        try:
            stat_sum = int(sum(actor.get_display_stat(s) for s in stat_list))
        except Exception:
            stat_sum = 0

    stat_eff = _dr_transform(stat_sum, cfg)

    if (cfg.rating_model or "additive").lower() == "multiplicative":
        # Model B (+ D if dr_mode != "none"):
        # R = c_mul * stat_eff * (1 + alpha*(skill/150)) + modifier
        # skill still matters even if stat_eff is small, but its impact is proportional to stat_eff.
        return (float(cfg.c_mul) * float(stat_eff) * (1.0 + float(cfg.alpha) * (float(skill) / 150.0))) + float(
            modifier or 0.0
        )

    # Default additive model
    return (cfg.w_skill * skill) + (cfg.w_stats * stat_eff) + float(modifier or 0.0)


def opposed_probability(
    attacker_rating: float,
    defender_rating: float,
    cfg: CombatRollConfig = DEFAULT_CFG,
    bias: float = 0.0,
) -> float:
    """
    Return P(attacker succeeds) under a logistic model.
    """
    delta = float(attacker_rating) - float(defender_rating)
    p = sigmoid(cfg.k * delta + bias)
    return _clamp(p, cfg.min_p, cfg.max_p)


def quality_value(
    attacker_rating: float,
    defender_rating: float,
    cfg: CombatRollConfig = DEFAULT_CFG,
) -> int:
    """
    Produce a 1..100 quality number used downstream for body-part bias, damage multipliers,
    and crit chance. This is *not* a probability; it's a presentation-friendly scalar.
    """
    delta = float(attacker_rating) - float(defender_rating)
    noisy = delta + random.gauss(0.0, float(cfg.quality_sigma))
    # Map to 1..100 using the same logistic steepness.
    q = sigmoid(cfg.k * noisy)
    return int(1 + round(99 * _clamp(q, 0.0, 1.0)))


def combat_debug_snapshot(
    *,
    cfg: CombatRollConfig,
    attack_skill: str,
    defense_skill: str,
    atk_mod: float,
    def_mod: float,
    atk_stance_mod: float | None = None,
    atk_trauma_mod: float | None = None,
    def_stance_mod: float | None = None,
    def_trauma_mod: float | None = None,
    attacker_rating: float,
    dodge_rating: float,
    parry_skill: str | None = None,
    parry_rating: float | None = None,
    best_kind: str = "dodge",
    best_rating: float | None = None,
    p_defend: float | None = None,
    outcome: str | None = None,
    quality: int | None = None,
    crit_chance: float | None = None,
) -> str:
    """
    Return a compact, staff-friendly debug line (no player-facing flavor).
    """
    best_rating = dodge_rating if best_rating is None else best_rating
    def _fmt_components(total: float, stance: float | None, trauma: float | None) -> str:
        if stance is None and trauma is None:
            return str(int(total))
        s = int(stance or 0)
        t = int(trauma or 0)
        return f"{int(total)} ({s:+d} stance {t:+d} trauma)"

    parts = [
        f"atk_skill={attack_skill}",
        f"def_skill={defense_skill}",
        f"atk_mod={_fmt_components(atk_mod, atk_stance_mod, atk_trauma_mod)}",
        f"def_mod={_fmt_components(def_mod, def_stance_mod, def_trauma_mod)}",
        f"atkR={attacker_rating:.1f}",
        f"dodgeR={dodge_rating:.1f}",
    ]
    if parry_skill and parry_rating is not None:
        parts.append(f"parry({parry_skill})R={parry_rating:.1f}")
    parts.append(f"best={best_kind}:{best_rating:.1f}")
    if p_defend is not None:
        parts.append(f"p_defend={p_defend:.3f}")
    if outcome:
        parts.append(f"outcome={outcome}")
    if quality is not None:
        parts.append(f"Q={quality}")
    if crit_chance is not None:
        parts.append(f"p_crit={crit_chance:.3f}")
    parts.append(f"k={cfg.k:g}")
    parts.append(f"sigma={cfg.quality_sigma:g}")
    parts.append(f"model={cfg.rating_model}")
    if cfg.dr_mode != "none":
        parts.append(f"dr={cfg.dr_mode}:{cfg.dr_scale:g}")
    return " | ".join(parts)

