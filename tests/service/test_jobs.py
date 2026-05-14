from manim_skill.service.jobs import JobStatus, ServiceJob


def test_job_status_values():
    assert JobStatus.QUEUED.value == "queued"
    assert JobStatus.RUNNING.value == "running"
    assert JobStatus.DONE.value == "done"
    assert JobStatus.FAILED.value == "failed"


def test_service_job_defaults():
    job = ServiceJob(job_id="abc", type="analyze")
    assert job.status == JobStatus.QUEUED
    assert job.progress is None
    assert job.result is None
    assert job.error is None


def test_to_dict_and_from_dict_roundtrip():
    job = ServiceJob(
        job_id="abc",
        type="render",
        status=JobStatus.DONE,
        result={"zip_path": "/work/abc/output.zip"},
    )
    restored = ServiceJob.from_dict(job.to_dict())
    assert restored == job
    assert restored.status == JobStatus.DONE


def test_to_dict_status_is_a_string():
    job = ServiceJob(job_id="abc", type="analyze", status=JobStatus.RUNNING)
    assert job.to_dict()["status"] == "running"
