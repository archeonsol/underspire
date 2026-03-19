# XP curve: mathematical piecewise form (same numbers as the original table).
# Phase 1: points 0-80, cost 0.5 per point  → cumulative(p) = 0.5 * p
# Phase 2: points 81-151, cost linear within each segment → cumulative is quadratic in segment
#   cumulative(p) = C0 + n*c0 + (c1-c0)/(L-1) * n*(n-1)/2  for n = p - p_start in segment [p_start, p_end]
# Segments: (p_end, C_at_start, cost_at_first_point, cost_at_last_point). p_start = previous p_end.
LINEAR_CAP = 80
LINEAR_COST = 0.5

# (p_end, C_start, cost_start, cost_end) for each segment after LINEAR_CAP. p_start = 80 for first, then 90, 100, ...
# Cost increases linearly across segment; cumulative follows exactly.
_CURVE_SEGMENTS = [
    (90, 40.0, 0.586, 1.113),       # 81-90
    (100, 48.496, 1.172, 2.227),    # 91-100
    (110, 65.489, 2.344, 4.453),    # 101-110
    (120, 99.473, 4.688, 8.906),    # 111-120
    (130, 167.442, 9.375, 17.813),  # 121-130
    (140, 303.379, 18.75, 35.625),  # 131-140
    (150, 575.254, 37.5, 71.25),    # 141-150
    (151, 1119.004, 75.0, 75.0),    # 150-151 (single step, cost 75)
]

# Stat curve: 2.0 XP per display point from 0 to 90, then segments to hit letter table (97→207, ..., 141→2422).
STAT_LINEAR_CAP = 90
STAT_LINEAR_COST = 2.0
_STAT_CURVE_SEGMENTS = [
    (97, 180.0, 2.109, 5.605),       # 91-97
    (105, 207.0, 5.605, 14.895),    # 98-105
    (114, 289.0, 14.895, 21.994),   # 106-114
    (123, 455.0, 21.994, 46.673),   # 115-123
    (132, 764.0, 46.673, 81.771),   # 124-132
    (141, 1342.0, 81.771, 158.229), # 133-141
]


def cumulative_xp(points):
    """
    Total cumulative XP to reach `points` (float ok). For SKILLS only (0-151).
    """
    if points is None or points < 0:
        return 0.0
    if points <= LINEAR_CAP:
        return round(LINEAR_COST * points, 3)
    p = points
    if p > 151:
        p = 151.0
    p_start = LINEAR_CAP
    for p_end, C_start, cost_start, cost_end in _CURVE_SEGMENTS:
        if p <= p_end:
            L = p_end - p_start
            n = p - p_start
            if L <= 1:
                return round(C_start + n * cost_start, 3)
            # n steps: C_start + n*cost_start + (cost_end-cost_start)/(L-1) * n*(n-1)/2
            term = C_start + n * cost_start
            if n > 0 and L > 1:
                term += (cost_end - cost_start) / (L - 1) * n * (n - 1) / 2
            return round(term, 3)
        p_start = p_end
    return round(_CURVE_SEGMENTS[-1][1] + (_CURVE_SEGMENTS[-1][3] - _CURVE_SEGMENTS[-1][2]) * 0.5, 3)


def cumulative_stat_xp(points):
    """
    Total cumulative XP to reach stat display `points` (0-150). Stats: 2.0 per point to 90, then segments.
    Letter table (stored→cum) matched from 90 onward: 97→207, 105→289, ..., 141→2422.
    Levels 142-150: one final segment using the same slope as 132-141, scaling cost up to ~200 at 150.
    """
    if points is None or points < 0:
        return 0.0
    if points <= STAT_LINEAR_CAP:
        return round(STAT_LINEAR_COST * points, 3)
    p = min(float(points), 150.0)
    p_start = STAT_LINEAR_CAP
    for p_end, C_start, cost_start, cost_end in _STAT_CURVE_SEGMENTS:
        if p <= p_end:
            L = p_end - p_start
            n = p - p_start
            if L <= 1:
                return round(C_start + n * cost_start, 3)
            term = C_start + n * cost_start
            if n > 0 and L > 1:
                term += (cost_end - cost_start) / (L - 1) * n * (n - 1) / 2
            return round(term, 3)
        p_start = p_end
    # 142-150: one final segment, no hardcoded offset. Use slope from 132-141, scale cost to ~200 at 150.
    p_start_final = 141
    p_end_final = 150
    _, C_at_132, cost_133, cost_141 = _STAT_CURVE_SEGMENTS[-1]
    L_prev = 9  # segment 133-141 has 9 points
    slope = (cost_141 - cost_133) / (L_prev - 1) if L_prev > 1 else (cost_141 - cost_133)
    cost_142 = cost_141 + slope
    cost_at_150 = 200.0
    # Cumulative at 141 = C_at_132 + 9*cost_133 + (cost_141-cost_133)/(L_prev-1) * 9*8/2
    n_prev = L_prev
    C_at_141 = C_at_132 + n_prev * cost_133 + (cost_141 - cost_133) / (L_prev - 1) * n_prev * (n_prev - 1) / 2
    n = p - p_start_final
    L_final = p_end_final - p_start_final
    term = C_at_141 + n * cost_142
    if n > 0 and L_final > 1:
        term += (cost_at_150 - cost_142) / (L_final - 1) * n * (n - 1) / 2
    return round(term, 3)
