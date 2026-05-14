import fakeredis

from manim_skill.service.job_store import JobStore
from manim_skill.service.jobs import JobStatus, ServiceJob


def _store(ttl=3600):
    return JobStore(fakeredis.FakeRedis(), ttl_seconds=ttl)


def test_save_then_get_roundtrips():
    store = _store()
    job = ServiceJob(job_id="j1", type="analyze")
    store.save(job)
    loaded = store.get("j1")
    assert loaded == job


def test_get_missing_returns_none():
    store = _store()
    assert store.get("nope") is None


def test_save_overwrites_existing():
    store = _store()
    store.save(ServiceJob(job_id="j1", type="render"))
    store.save(
        ServiceJob(job_id="j1", type="render", status=JobStatus.DONE)
    )
    assert store.get("j1").status == JobStatus.DONE


def test_delete_removes_job():
    store = _store()
    store.save(ServiceJob(job_id="j1", type="analyze"))
    store.delete("j1")
    assert store.get("j1") is None


def test_saved_job_has_a_ttl():
    redis_conn = fakeredis.FakeRedis()
    store = JobStore(redis_conn, ttl_seconds=123)
    store.save(ServiceJob(job_id="j1", type="analyze"))
    ttl = redis_conn.ttl("manim-skill:job:j1")
    assert 0 < ttl <= 123
