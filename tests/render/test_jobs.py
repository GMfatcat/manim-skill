from manim_skill.render.jobs import BatchJob, BeatJob, ClipJob, JobStatus
from manim_skill.spec.schema import Beat, SceneSpec


def test_job_status_values():
    assert JobStatus.QUEUED.value == "queued"
    assert JobStatus.RENDERING.value == "rendering"
    assert JobStatus.DONE.value == "done"
    assert JobStatus.FAILED.value == "failed"


def test_beat_job_defaults():
    beat = Beat(component="raw", code="self.wait(1)")
    job = BeatJob(beat=beat)
    assert job.status == JobStatus.QUEUED
    assert job.mp4_path is None
    assert job.error is None


def test_clip_job_defaults():
    spec = SceneSpec(title="C", beats=[Beat(component="raw", code="pass")])
    job = ClipJob(concept="C", spec=spec)
    assert job.status == JobStatus.QUEUED
    assert job.beat_jobs == []
    assert job.mp4_path is None
    assert job.gif_path is None
    assert job.error is None


def test_batch_job_defaults():
    spec = SceneSpec(title="C", beats=[Beat(component="raw", code="pass")])
    clip = ClipJob(concept="C", spec=spec)
    batch = BatchJob(clip_jobs=[clip])
    assert batch.status == JobStatus.QUEUED
    assert batch.zip_path is None
    assert batch.clip_jobs == [clip]


def test_job_status_is_mutable_on_jobs():
    beat = Beat(component="raw", code="pass")
    job = BeatJob(beat=beat)
    job.status = JobStatus.DONE
    assert job.status == JobStatus.DONE
