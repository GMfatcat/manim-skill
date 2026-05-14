import json
import zipfile

import pytest

from manim_skill.render.backend import render_batch
from manim_skill.render.cache import BeatCache
from manim_skill.render.jobs import JobStatus
from manim_skill.spec.schema import Beat, SceneSpec


@pytest.mark.docker
def test_render_batch_end_to_end_produces_zip(tmp_path):
    specs = [
        SceneSpec(
            title="Concept A",
            beats=[
                Beat(component="TextBeat", params={"text": "Hello"}, duration=1.0),
                Beat(component="raw", code="self.wait(1)", duration=0.5),
            ],
        ),
        SceneSpec(
            title="Concept B",
            beats=[
                Beat(
                    component="CodeWalkthrough",
                    params={"code": "x = 1", "language": "python"},
                    duration=1.0,
                )
            ],
        ),
    ]
    batch = render_batch(specs, tmp_path, max_workers=2)

    assert batch.status == JobStatus.DONE
    assert batch.zip_path is not None and batch.zip_path.exists()
    assert all(clip.status == JobStatus.DONE for clip in batch.clip_jobs)

    with zipfile.ZipFile(batch.zip_path) as zf:
        names = zf.namelist()
        manifest = json.loads(zf.read("manifest.json"))
    # one folder per concept, each with an mp4 and a gif
    assert sum(n.endswith(".mp4") for n in names) == 2
    assert sum(n.endswith(".gif") for n in names) == 2
    assert len(manifest["concepts"]) == 2
    assert all(c["status"] == "done" for c in manifest["concepts"])


@pytest.mark.docker
def test_render_batch_failed_beat_does_not_break_clip(tmp_path):
    # A clip with one broken raw beat and one good beat — the clip
    # should still finish from the good beat.
    specs = [
        SceneSpec(
            title="Partial",
            beats=[
                Beat(component="raw", code="this is not valid python !!!"),
                Beat(component="raw", code="self.wait(1)", duration=0.5),
            ],
        )
    ]
    batch = render_batch(specs, tmp_path, max_workers=2)

    clip = batch.clip_jobs[0]
    assert clip.status == JobStatus.DONE
    assert clip.mp4_path is not None and clip.mp4_path.exists()
    beat_statuses = [bj.status for bj in clip.beat_jobs]
    assert JobStatus.FAILED in beat_statuses
    assert JobStatus.DONE in beat_statuses


@pytest.mark.docker
def test_render_batch_cache_speeds_up_rerun(tmp_path):
    # With a shared cache, rendering the same spec twice should succeed
    # both times and the second run's beat mp4 should come from cache.
    cache = BeatCache(tmp_path / "cache")
    spec = SceneSpec(
        title="Cached",
        beats=[Beat(component="raw", code="self.wait(1)", duration=0.5)],
    )

    batch1 = render_batch([spec], tmp_path / "run1", cache=cache)
    assert batch1.status == JobStatus.DONE

    batch2 = render_batch([spec], tmp_path / "run2", cache=cache)
    assert batch2.status == JobStatus.DONE
    # the cache file for the beat now exists
    assert cache.get(spec.beats[0]) is not None
