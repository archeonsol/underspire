"""
Shared UI rendering helpers for text menus/panels.
"""


def fade_rule(
    width: int,
    ch: str = "─",
    start_ratio: float = 0.38,
    decay: float = 0.62,
    initial_gap: int = 1,
    gap_growth_every: int = 2,
) -> str:
    """
    Build a left-to-right fading horizontal rule at a specific width.

    Args:
        width: Total number of characters to generate.
        ch: The glyph used for each visible segment.
        start_ratio: Initial solid-run size as a ratio of width.
        decay: Multiplier applied to each subsequent run length.
        initial_gap: Spaces inserted after the first run.
        gap_growth_every: Increase gap size every N segments.
    """
    remaining = max(0, int(width))
    if remaining <= 0:
        return ""

    parts = []
    run = max(1, int(remaining * start_ratio))
    gap = max(1, int(initial_gap))
    step = 0

    while remaining > 0:
        seg = min(run, remaining)
        parts.append(ch * seg)
        remaining -= seg
        if remaining <= 0:
            break

        space = min(gap, remaining)
        parts.append(" " * space)
        remaining -= space

        run = max(1, int(run * decay))
        if gap_growth_every > 0 and step % gap_growth_every == gap_growth_every - 1:
            gap += 1
        step += 1

    return "".join(parts)
