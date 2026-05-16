from manim_skill.llm import pipeline as pipeline_mod
from manim_skill.llm.client import FakeLLMClient
from manim_skill.llm.pipeline import generate_specs, run_pipeline
from manim_skill.spec.schema import SceneSpec

_ANALYZE_RESP = (
    '{"concepts": [{"concept": "C1", "why_suitable": "w", '
    '"storyboard": "s"}]}'
)
_SPEC_RESP = (
    '{"title": "C1", "beats": [{"component": "TextBeat", '
    '"params": {"text": "Hi"}}]}'
)


def test_generate_specs_runs_analyze_then_codegen():
    client = FakeLLMClient(responses=[_ANALYZE_RESP, _SPEC_RESP])
    specs = generate_specs(client, "paper text", "text")
    assert len(specs) == 1
    assert isinstance(specs[0], SceneSpec)
    assert specs[0].title == "C1"


def test_generate_specs_skips_concept_with_failed_codegen():
    # analyze finds 2 concepts; the first concept's codegen fails twice
    # (skipped), the second concept's codegen succeeds.
    analyze_resp = (
        '{"concepts": ['
        '{"concept": "Bad", "why_suitable": "w", "storyboard": "s"},'
        '{"concept": "Good", "why_suitable": "w", "storyboard": "s"}]}'
    )
    client = FakeLLMClient(
        responses=[analyze_resp, "garbage", "garbage again", _SPEC_RESP]
    )
    specs = generate_specs(client, "text", "text")
    assert len(specs) == 1
    assert specs[0].title == "C1"


def test_run_pipeline_passes_specs_and_repairer_to_render_batch(
    tmp_path, monkeypatch
):
    captured = {}

    def fake_render_batch(specs, workdir, *, max_workers, cache, repairer, quality):
        from manim_skill.render.jobs import BatchJob, JobStatus

        captured["specs"] = specs
        captured["repairer"] = repairer
        return BatchJob(clip_jobs=[], status=JobStatus.DONE)

    monkeypatch.setattr(pipeline_mod, "render_batch", fake_render_batch)
    client = FakeLLMClient(responses=[_ANALYZE_RESP, _SPEC_RESP])
    run_pipeline(client, "text", "text", tmp_path, repair=True)
    assert len(captured["specs"]) == 1
    assert captured["repairer"] is not None  # repair=True -> a BeatRepairer


def test_run_pipeline_repair_false_passes_no_repairer(tmp_path, monkeypatch):
    def fake_render_batch(specs, workdir, *, max_workers, cache, repairer, quality):
        from manim_skill.render.jobs import BatchJob, JobStatus

        assert repairer is None
        return BatchJob(clip_jobs=[], status=JobStatus.DONE)

    monkeypatch.setattr(pipeline_mod, "render_batch", fake_render_batch)
    client = FakeLLMClient(responses=[_ANALYZE_RESP, _SPEC_RESP])
    run_pipeline(client, "text", "text", tmp_path, repair=False)


def test_run_pipeline_propagates_quality(tmp_path, monkeypatch):
    captured = {}

    def fake_render_batch(specs, workdir, *, max_workers, cache, repairer, quality):
        from manim_skill.render.jobs import BatchJob, JobStatus

        captured["quality"] = quality
        return BatchJob(clip_jobs=[], status=JobStatus.DONE)

    monkeypatch.setattr(pipeline_mod, "render_batch", fake_render_batch)
    client = FakeLLMClient(responses=[_ANALYZE_RESP, _SPEC_RESP])
    run_pipeline(client, "text", "text", tmp_path, quality="high")
    assert captured["quality"] == "high"
