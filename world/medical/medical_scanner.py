"""
Rich bioscanner readout: vitals randomized by HP state for immersion.
BP, SpO2, HR, RR, temp, status line; plausible ranges per health tier.
"""
import random
from world.medical import get_medical_detail, get_medical_summary, _ensure_medical_db, get_infection_readout, get_active_bleed_wounds


def _vital_ranges(pct):
    """
    Return (bp_sys_lo, bp_sys_hi), (bp_dia_lo, bp_dia_hi), (spo2_lo, spo2_hi),
    (hr_lo, hr_hi), (rr_lo, rr_hi), (temp_lo, temp_hi), status_key.
    All ranges inclusive; values randomized in-post.
    """
    if pct >= 100:
        return (112, 128), (68, 82), (97, 100), (58, 78), (12, 16), (365, 370), "stable"
    if pct >= 85:
        return (108, 124), (66, 80), (96, 99), (62, 88), (12, 18), (364, 369), "stable"
    if pct >= 65:
        return (98, 118), (60, 76), (94, 98), (72, 98), (14, 22), (363, 368), "compensated"
    if pct >= 45:
        return (88, 108), (54, 70), (90, 96), (88, 112), (18, 26), (362, 367), "compromised"
    if pct >= 25:
        return (78, 98), (48, 64), (85, 93), (98, 128), (22, 32), (360, 366), "critical"
    if pct >= 5:
        return (65, 85), (40, 55), (78, 88), (110, 140), (28, 38), (358, 364), "near_death"
    return (50, 75), (30, 48), (65, 82), (40, 120), (4, 12), (355, 362), "arrest"


def _rand(spec):
    lo, hi = spec
    return random.randint(lo, hi)


def _temp_c(decicelsius):
    """Convert decicelsius to display string (e.g. 368 -> 36.8 C)."""
    return "{:.1f}".format(decicelsius / 10.0)


STATUS_LABELS = {
    "stable": "|gSTABLE|n",
    "compensated": "|yCOMPENSATED|n",
    "compromised": "|yCOMPROMISED|n",
    "critical": "|rCRITICAL|n",
    "near_death": "|rNEAR DEATH|n",
    "arrest": "|RARREST / UNRESPONSIVE|n",
}


def get_scanner_readout(target):
    """
    Build a full, immersive bioscanner readout for the target.
    Vitals are randomized within plausible ranges for their current HP%.
    In arrest (0 HP): no HR, no pulse, flatline vitals.
    """
    _ensure_medical_db(target)
    hp = getattr(target, "hp", 0)
    mx = getattr(target, "max_hp", 1)
    pct = (hp / mx * 100) if mx else 0
    in_arrest = pct <= 0

    infections = get_infection_readout(target)
    max_inf_stage = max([i.get("stage", 0) for i in infections], default=0)

    if in_arrest:
        status_key = "arrest"
        status = STATUS_LABELS.get(status_key, "|RARREST|n")
        # No pulse, no HR, no respiration; BP/SpO2 meaningless
        vital_line1 = "  |wBP|n      ---/--- mmHg     |wSpO2|n   ---%     |wStatus|n " + status
        vital_line2 = "  |wHR|n      --- bpm           |wRR|n     ---/min   |wTemp|n   (cooling)"
    else:
        (bp_sys_r, bp_dia_r, spo2_r, hr_r, rr_r, temp_r, status_key) = _vital_ranges(pct)
        if max_inf_stage >= 2:
            # Fever/tachycardia signature for active infection.
            temp_r = (max(temp_r[0], 374), max(temp_r[1], 389 if max_inf_stage >= 3 else 382))
            hr_r = (max(hr_r[0], 94), max(hr_r[1], 150 if max_inf_stage >= 3 else 130))
            if status_key in ("stable", "compensated"):
                status_key = "compromised"
            if max_inf_stage >= 4:
                status_key = "critical"
        bp_sys = _rand(bp_sys_r)
        bp_dia = _rand(bp_dia_r)
        spo2 = _rand(spo2_r)
        hr = _rand(hr_r)
        rr = _rand(rr_r)
        temp_c = _rand(temp_r)
        status = STATUS_LABELS.get(status_key, status_key.upper())
        vital_line1 = f"  |wBP|n      {bp_sys:3d}/{bp_dia:<3d} mmHg     |wSpO2|n   {spo2:2d}%     |wStatus|n {status}"
        vital_line2 = f"  |wHR|n      {hr:3d} bpm           |wRR|n     {rr:2d}/min    |wTemp|n   {_temp_c(temp_c)} C"

    # HP bar
    if in_arrest:
        bar = "|R" + "|" * 0 + "| " * 10 + "|n"
    elif pct >= 80:
        bar = "|g" + "|" * 10 + "|n"
    elif pct >= 50:
        bar = "|y" + "|" * 6 + "| " * 4 + "|n"
    elif pct >= 25:
        bar = "|y" + "|" * 3 + "| " * 7 + "|n"
    else:
        n = max(1, int(10 * pct / 100))
        bar = "|r" + "|" * n + "| " * (10 - n) + "|n"

    detail = get_medical_detail(target)

    lines = [
        "",
        "|c" + "=" * 54 + "|n",
        "|W  B I O S C A N N E R   R E A D O U T|n",
        "|c" + "=" * 54 + "|n",
        f"  |wSubject|n: {target.name}",
        "",
        "  |wVITAL SIGNS|n",
        "  " + "-" * 50,
        vital_line1,
        vital_line2,
        "",
        "  |wPERFUSION / EST. BLOOD VOLUME|n",
        f"  HP  {hp:3d}/{mx:<3d}  {bar}  ({pct:.0f}%)",
        "",
        "  |wTRAUMA / INTERNAL ASSESSMENT|n",
        "  " + "-" * 50,
    ]
    for line in detail.split("\n"):
        lines.append("  " + line if line.strip() else "")
    lines.extend(["", "  |wINFECTION ALERTS|n", "  " + "-" * 50])
    if infections:
        for inf in infections:
            lines.append(
                f"  {inf['body_part'].title()}: {inf['label']} - {inf['stage_label']} "
                f"(risk {int(inf['risk'] * 100)}%)"
            )
    else:
        lines.append("  None detected.")
    lines.extend(["", "  |wACTIVE BLEED SOURCES|n", "  " + "-" * 50])
    active_bleeds = get_active_bleed_wounds(target)
    if active_bleeds:
        for w in active_bleeds:
            lines.append(
                f"  {(w.get('body_part') or 'unknown').title()}: "
                f"rate {float(w.get('bleed_rate', 0.0) or 0.0):.1f}, "
                f"{(w.get('vessel_type') or 'capillary')}"
            )
    else:
        lines.append("  None detected.")
    lines.append("|c" + "=" * 54 + "|n")
    return "\n".join(lines)
