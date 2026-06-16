from manim_skill.render.jobs import BeatJob
from manim_skill.spec.schema import Beat


def test_beatjob_has_tier_field_defaulting_to_none():
    bj = BeatJob(beat=Beat(component="raw", code="self.wait(1)"))
    assert bj.tier is None
    bj.tier = "generated"
    assert bj.tier == "generated"


from manim_skill.render.jobs import BatchJob, ClipJob, BeatJob
from manim_skill.render.metrics import (
    compute_tier_metrics,
    TIER_DETERMINISTIC,
    TIER_GENERATED,
    TIER_MODEL_REPAIRED,
    TIER_UNRESOLVED,
)
from manim_skill.spec.schema import Beat, SceneSpec


def _beat_with_tier(tier):
    bj = BeatJob(beat=Beat(component="raw", code="x"))
    bj.tier = tier
    return bj


def test_compute_tier_metrics_aggregates_counts_and_rates():
    spec = SceneSpec(title="C", beats=[Beat(component="raw", code="x")])
    clip = ClipJob(
        concept="C",
        spec=spec,
        beat_jobs=[
            _beat_with_tier(TIER_DETERMINISTIC),
            _beat_with_tier(TIER_GENERATED),
            _beat_with_tier(TIER_MODEL_REPAIRED),
            _beat_with_tier(TIER_UNRESOLVED),
        ],
    )
    batch = BatchJob(clip_jobs=[clip])

    m = compute_tier_metrics(batch)

    assert m["total_beats"] == 4
    assert m["tier_counts"][TIER_UNRESOLVED] == 1
    assert m["tier_counts"][TIER_GENERATED] == 1
    assert m["escalation_rate"] == 0.25
    assert m["free_tier_rate"] == 0.75
    assert m["per_clip"][0]["concept"] == "C"
    assert m["per_clip"][0]["unresolved"] == 1


def test_compute_tier_metrics_treats_missing_tier_as_unresolved():
    spec = SceneSpec(title="C", beats=[Beat(component="raw", code="x")])
    bj = BeatJob(beat=Beat(component="raw", code="x"))  # tier left as None
    clip = ClipJob(concept="C", spec=spec, beat_jobs=[bj])
    m = compute_tier_metrics(BatchJob(clip_jobs=[clip]))
    assert m["tier_counts"][TIER_UNRESOLVED] == 1
    assert m["escalation_rate"] == 1.0


def test_compute_tier_metrics_empty_batch_is_zero():
    m = compute_tier_metrics(BatchJob(clip_jobs=[]))
    assert m["total_beats"] == 0
    assert m["escalation_rate"] == 0.0
    assert m["free_tier_rate"] == 0.0
