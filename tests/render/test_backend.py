from pathlib import Path

from manim_skill.render import backend as backend_mod
from manim_skill.render.backend import render_batch
from manim_skill.render.docker_render import RenderError
from manim_skill.render.jobs import JobStatus
from manim_skill.spec.schema import Beat, SceneSpec


def _fake_render_spec_to_mp4(spec, workdir, *, quality="medium"):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    mp4 = workdir / "fake.mp4"
    mp4.write_bytes(b"\x00\x00fake-mp4")
    return mp4


def _fake_render_raises(spec, workdir, *, quality="medium"):
    raise RenderError("simulated render failure")


def _fake_stitch_mp4s(mp4_paths, output_path):
    output_path = Path(output_path)
    output_path.write_bytes(b"\x00stitched")
    return output_path


def _fake_mp4_to_gif(mp4_path):
    gif = Path(mp4_path).with_suffix(".gif")
    gif.write_bytes(b"\x00gif")
    return gif


def _patch_docker_fns(monkeypatch, render_fn=_fake_render_spec_to_mp4):
    monkeypatch.setattr(backend_mod, "render_spec_to_mp4", render_fn)
    monkeypatch.setattr(backend_mod, "stitch_mp4s", _fake_stitch_mp4s)
    monkeypatch.setattr(backend_mod, "mp4_to_gif", _fake_mp4_to_gif)


def test_render_batch_happy_path(tmp_path, monkeypatch):
    _patch_docker_fns(monkeypatch)
    specs = [
        SceneSpec(
            title="Concept A",
            beats=[
                Beat(component="raw", code="self.wait(1)"),
                Beat(component="raw", code="self.wait(2)"),
            ],
        ),
        SceneSpec(
            title="Concept B",
            beats=[Beat(component="raw", code="self.wait(1)")],
        ),
    ]
    batch = render_batch(specs, tmp_path)

    assert batch.status == JobStatus.DONE
    assert batch.zip_path is not None and batch.zip_path.exists()
    assert len(batch.clip_jobs) == 2
    for clip in batch.clip_jobs:
        assert clip.status == JobStatus.DONE
        assert clip.mp4_path is not None and clip.gif_path is not None
        assert all(bj.status == JobStatus.DONE for bj in clip.beat_jobs)


def test_render_batch_failed_beat_is_skipped(tmp_path, monkeypatch):
    calls = {"n": 0}

    def flaky_render(spec, workdir, *, quality="medium"):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RenderError("boom")
        return _fake_render_spec_to_mp4(spec, workdir)

    _patch_docker_fns(monkeypatch, render_fn=flaky_render)
    specs = [
        SceneSpec(
            title="C",
            beats=[
                Beat(component="raw", code="bad"),
                Beat(component="raw", code="ok"),
            ],
        )
    ]
    # max_workers=1 makes the call order deterministic.
    batch = render_batch(specs, tmp_path, max_workers=1)

    clip = batch.clip_jobs[0]
    assert clip.status == JobStatus.DONE
    beat_statuses = [bj.status for bj in clip.beat_jobs]
    assert JobStatus.FAILED in beat_statuses
    assert JobStatus.DONE in beat_statuses


def test_render_batch_all_beats_fail_marks_clip_and_batch_failed(
    tmp_path, monkeypatch
):
    _patch_docker_fns(monkeypatch, render_fn=_fake_render_raises)
    specs = [
        SceneSpec(title="C", beats=[Beat(component="raw", code="bad")])
    ]
    batch = render_batch(specs, tmp_path)

    assert batch.clip_jobs[0].status == JobStatus.FAILED
    assert batch.status == JobStatus.FAILED
    # The zip is still produced — it records the failure in the manifest.
    assert batch.zip_path is not None and batch.zip_path.exists()


def test_render_batch_uses_cache_to_skip_rendering(tmp_path, monkeypatch):
    from manim_skill.render.cache import BeatCache

    _patch_docker_fns(monkeypatch)
    cache = BeatCache(tmp_path / "cache")
    spec = SceneSpec(
        title="C", beats=[Beat(component="raw", code="self.wait(1)")]
    )

    # First run populates the cache.
    render_batch([spec], tmp_path / "run1", cache=cache)

    # Second run: swap the renderer to one that always raises. If the
    # cache works, render_spec_to_mp4 is never called and the beat
    # still succeeds from the cached mp4.
    monkeypatch.setattr(backend_mod, "render_spec_to_mp4", _fake_render_raises)
    batch2 = render_batch([spec], tmp_path / "run2", cache=cache)

    assert batch2.clip_jobs[0].status == JobStatus.DONE
    assert batch2.clip_jobs[0].beat_jobs[0].status == JobStatus.DONE
    assert batch2.clip_jobs[0].beat_jobs[0].tier == "cached"


def test_render_batch_propagates_quality_to_renderer(tmp_path, monkeypatch):
    captured: list[str] = []

    def recording_render(spec, workdir, *, quality="medium"):
        captured.append(quality)
        return _fake_render_spec_to_mp4(spec, workdir)

    monkeypatch.setattr(backend_mod, "render_spec_to_mp4", recording_render)
    monkeypatch.setattr(backend_mod, "stitch_mp4s", _fake_stitch_mp4s)
    monkeypatch.setattr(backend_mod, "mp4_to_gif", _fake_mp4_to_gif)

    specs = [SceneSpec(title="C", beats=[Beat(component="raw", code="self.wait(1)")])]
    render_batch(specs, tmp_path, quality="high")

    assert captured == ["high"]


def test_render_batch_repairer_recovers_failed_raw_beat(tmp_path, monkeypatch):
    # render_spec_to_mp4 always fails; the repairer "fixes" the beat and
    # produces an mp4, so the clip still completes.
    monkeypatch.setattr(backend_mod, "render_spec_to_mp4", _fake_render_raises)
    monkeypatch.setattr(backend_mod, "stitch_mp4s", _fake_stitch_mp4s)
    monkeypatch.setattr(backend_mod, "mp4_to_gif", _fake_mp4_to_gif)

    class _FakeRepairer:
        def render_with_repair(
            self, beat, work_dir, *, title, aspect_ratio, quality="medium"
        ):
            from manim_skill.llm.repair import RepairResult

            work_dir = Path(work_dir)
            work_dir.mkdir(parents=True, exist_ok=True)
            mp4 = work_dir / "repaired.mp4"
            mp4.write_bytes(b"\x00repaired")
            return RepairResult(mp4_path=mp4, final_beat=beat, attempts=2)

    specs = [
        SceneSpec(title="C", beats=[Beat(component="raw", code="broken")])
    ]
    batch = render_batch(specs, tmp_path, repairer=_FakeRepairer())
    assert batch.clip_jobs[0].status == JobStatus.DONE
    assert batch.clip_jobs[0].beat_jobs[0].status == JobStatus.DONE


def test_render_batch_tier_deterministic_for_component_generated_for_raw(
    tmp_path, monkeypatch
):
    _patch_docker_fns(monkeypatch)
    specs = [
        SceneSpec(
            title="C",
            beats=[
                Beat(component="TextBeat", params={"text": "hi"}),
                Beat(component="raw", code="self.wait(1)"),
            ],
        )
    ]
    batch = render_batch(specs, tmp_path, max_workers=1)
    tiers = [bj.tier for bj in batch.clip_jobs[0].beat_jobs]
    assert tiers == ["deterministic", "generated"]


def test_render_batch_tier_unresolved_on_failure(tmp_path, monkeypatch):
    _patch_docker_fns(monkeypatch, render_fn=_fake_render_raises)
    specs = [SceneSpec(title="C", beats=[Beat(component="raw", code="bad")])]
    batch = render_batch(specs, tmp_path)
    assert batch.clip_jobs[0].beat_jobs[0].tier == "unresolved"


def test_render_batch_tier_model_repaired_when_repairer_fixes(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(backend_mod, "render_spec_to_mp4", _fake_render_raises)
    monkeypatch.setattr(backend_mod, "stitch_mp4s", _fake_stitch_mp4s)
    monkeypatch.setattr(backend_mod, "mp4_to_gif", _fake_mp4_to_gif)

    class _FakeRepairer:
        def render_with_repair(
            self, beat, work_dir, *, title, aspect_ratio, quality="medium"
        ):
            from manim_skill.llm.repair import RepairResult

            work_dir = Path(work_dir)
            work_dir.mkdir(parents=True, exist_ok=True)
            mp4 = work_dir / "repaired.mp4"
            mp4.write_bytes(b"\x00repaired")
            return RepairResult(mp4_path=mp4, final_beat=beat, attempts=2)

    specs = [SceneSpec(title="C", beats=[Beat(component="raw", code="broken")])]
    batch = render_batch(specs, tmp_path, repairer=_FakeRepairer())
    assert batch.clip_jobs[0].beat_jobs[0].tier == "model_repaired"


def test_render_batch_sets_escalation_rate_and_over_quota_flag(
    tmp_path, monkeypatch
):
    calls = {"n": 0}

    def flaky_render(spec, workdir, *, quality="medium"):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RenderError("boom")
        return _fake_render_spec_to_mp4(spec, workdir)

    _patch_docker_fns(monkeypatch, render_fn=flaky_render)
    specs = [
        SceneSpec(
            title="C",
            beats=[
                Beat(component="raw", code="bad"),
                Beat(component="raw", code="ok"),
            ],
        )
    ]
    batch = render_batch(
        specs, tmp_path, max_workers=1, escalation_quota=0.1
    )
    assert batch.escalation_rate == 0.5
    assert batch.over_quota is True


def test_render_batch_over_quota_false_without_quota(tmp_path, monkeypatch):
    _patch_docker_fns(monkeypatch, render_fn=_fake_render_raises)
    specs = [SceneSpec(title="C", beats=[Beat(component="raw", code="bad")])]
    batch = render_batch(specs, tmp_path)  # no quota passed
    assert batch.escalation_rate == 1.0
    assert batch.over_quota is False


def test_render_batch_writes_summary_into_manifest(tmp_path, monkeypatch):
    _patch_docker_fns(monkeypatch)
    specs = [
        SceneSpec(
            title="C",
            beats=[Beat(component="raw", code="self.wait(1)")],
        )
    ]
    batch = render_batch(specs, tmp_path)
    import json
    import zipfile

    with zipfile.ZipFile(batch.zip_path) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["summary"]["total_beats"] == 1
    assert manifest["summary"]["tier_counts"]["generated"] == 1
    assert manifest["concepts"][0]["tier_counts"]["generated"] == 1
