from __future__ import annotations

from manim_skill.render.jobs import BatchJob

# Cost tiers a beat can resolve at (set by the render backend).
TIER_DETERMINISTIC = "deterministic"   # component beat — free L0 win
TIER_CACHED = "cached"                 # served from the beat cache — free
TIER_GENERATED = "generated"           # raw beat rendered first try — L1 generation
TIER_MODEL_REPAIRED = "model_repaired" # raw beat fixed by the repair loop — L1 repair
TIER_UNRESOLVED = "unresolved"         # failed every tier — escalation candidate (L2)

_FREE_TIERS = (
    TIER_DETERMINISTIC,
    TIER_CACHED,
    TIER_GENERATED,
    TIER_MODEL_REPAIRED,
)


def compute_tier_metrics(batch: BatchJob) -> dict:
    """Aggregate per-beat resolution tier into a batch cost summary.

    Returns total beats, the tier histogram, the escalation rate
    (unresolved / total — the share that would need the expensive L2
    copilot), the free-tier rate (everything resolved without L2), and a
    per-clip breakdown. A beat with no tier set counts as unresolved.
    """
    per_clip = []
    overall: dict[str, int] = {}
    total = 0
    unresolved = 0
    for clip in batch.clip_jobs:
        counts: dict[str, int] = {}
        for bj in clip.beat_jobs:
            tier = bj.tier or TIER_UNRESOLVED
            counts[tier] = counts.get(tier, 0) + 1
            overall[tier] = overall.get(tier, 0) + 1
            total += 1
            if tier == TIER_UNRESOLVED:
                unresolved += 1
        per_clip.append(
            {
                "concept": clip.concept,
                "tier_counts": counts,
                "unresolved": counts.get(TIER_UNRESOLVED, 0),
            }
        )

    escalation_rate = (unresolved / total) if total else 0.0
    free = sum(overall.get(t, 0) for t in _FREE_TIERS)
    free_tier_rate = (free / total) if total else 0.0
    return {
        "total_beats": total,
        "tier_counts": overall,
        "escalation_rate": round(escalation_rate, 4),
        "free_tier_rate": round(free_tier_rate, 4),
        "per_clip": per_clip,
    }


def format_tier_line(metrics: dict) -> str:
    """One-line human summary of a tier-metrics dict for CLI output."""
    counts = ", ".join(
        f"{tier}={n}" for tier, n in sorted(metrics["tier_counts"].items())
    )
    return (
        f"tiers: {counts}  "
        f"free={metrics['free_tier_rate'] * 100:.0f}%  "
        f"escalation={metrics['escalation_rate'] * 100:.0f}%"
    )
