import fakeredis

from manim_skill.llm.client import FakeLLMClient
from manim_skill.service import handlers as handlers_mod
from manim_skill.service.handlers import handle_analyze_job, handle_render_job
from manim_skill.service.job_store import JobStore
from manim_skill.service.jobs import JobStatus, ServiceJob

_ANALYZE_RESP = (
    '{"concepts": [{"concept": "C1", "why_suitable": "w", '
    '"storyboard": "s"}]}'
)
_SPEC_RESP = (
    '{"title": "C1", "beats": [{"component": "TextBeat", '
    '"params": {"text": "Hi"}}]}'
)


class _FakeBatch:
    def __init__(self, zip_path):
        self.zip_path = zip_path
        from manim_skill.render.jobs import JobStatus as RJ

        self.status = RJ.DONE


def _patch_common(monkeypatch, redis_conn, llm_responses):
    # all handlers build their own redis connection + LLM client from
    # config; redirect both to the test fakes.
    monkeypatch.setattr(
        handlers_mod, "_redis_from_config", lambda config: redis_conn
    )
    monkeypatch.setattr(
        handlers_mod,
        "_build_llm_client",
        lambda config, redis_conn: FakeLLMClient(responses=list(llm_responses)),
    )


def test_handle_analyze_job_success(tmp_path, monkeypatch):
    redis_conn = fakeredis.FakeRedis()
    _patch_common(monkeypatch, redis_conn, [_ANALYZE_RESP])
    monkeypatch.setenv("MANIM_SKILL_WORK_DIR", str(tmp_path))

    store = JobStore(redis_conn)
    store.save(ServiceJob(job_id="j1", type="analyze"))
    input_path = tmp_path / "input"
    input_path.write_text("some paper text", encoding="utf-8")

    handle_analyze_job("j1", str(input_path), "text", None)

    job = store.get("j1")
    assert job.status == JobStatus.DONE
    assert job.result["concepts"][0]["concept"] == "C1"


def test_handle_analyze_job_failure(tmp_path, monkeypatch):
    redis_conn = fakeredis.FakeRedis()
    _patch_common(monkeypatch, redis_conn, ["not json at all"])
    monkeypatch.setenv("MANIM_SKILL_WORK_DIR", str(tmp_path))

    store = JobStore(redis_conn)
    store.save(ServiceJob(job_id="j1", type="analyze"))
    input_path = tmp_path / "input"
    input_path.write_text("text", encoding="utf-8")

    handle_analyze_job("j1", str(input_path), "text", None)

    job = store.get("j1")
    assert job.status == JobStatus.FAILED
    assert job.error


def test_handle_render_job_spec_mode(tmp_path, monkeypatch):
    redis_conn = fakeredis.FakeRedis()
    _patch_common(monkeypatch, redis_conn, [])
    monkeypatch.setenv("MANIM_SKILL_WORK_DIR", str(tmp_path))
    monkeypatch.setattr(
        handlers_mod,
        "render_batch",
        lambda specs, workdir, **kw: _FakeBatch(tmp_path / "out.zip"),
    )

    store = JobStore(redis_conn)
    store.save(ServiceJob(job_id="j1", type="render"))
    spec = {
        "title": "T",
        "beats": [{"component": "TextBeat", "params": {"text": "Hi"}}],
    }

    handle_render_job("j1", "spec", spec)

    job = store.get("j1")
    assert job.status == JobStatus.DONE
    assert job.result["zip_path"].endswith("out.zip")


def test_handle_render_job_codegen_mode(tmp_path, monkeypatch):
    redis_conn = fakeredis.FakeRedis()
    _patch_common(monkeypatch, redis_conn, [_SPEC_RESP])
    monkeypatch.setenv("MANIM_SKILL_WORK_DIR", str(tmp_path))
    monkeypatch.setattr(
        handlers_mod,
        "render_batch",
        lambda specs, workdir, **kw: _FakeBatch(tmp_path / "out.zip"),
    )

    store = JobStore(redis_conn)
    store.save(ServiceJob(job_id="j1", type="render"))
    concepts = [{"concept": "C1", "why_suitable": "w", "storyboard": "s"}]

    handle_render_job("j1", "codegen", concepts)

    job = store.get("j1")
    assert job.status == JobStatus.DONE


def test_handle_render_job_codegen_all_fail(tmp_path, monkeypatch):
    redis_conn = fakeredis.FakeRedis()
    # codegen makes up to 2 LLM calls per concept (initial + re-ask); give garbage
    _patch_common(monkeypatch, redis_conn, ["garbage", "garbage"])
    monkeypatch.setenv("MANIM_SKILL_WORK_DIR", str(tmp_path))

    store = JobStore(redis_conn)
    store.save(ServiceJob(job_id="j1", type="render"))
    concepts = [{"concept": "C1", "why_suitable": "w", "storyboard": "s"}]

    handle_render_job("j1", "codegen", concepts)

    job = store.get("j1")
    assert job.status == JobStatus.FAILED


def test_handle_job_missing_record_is_a_noop(tmp_path, monkeypatch):
    redis_conn = fakeredis.FakeRedis()
    _patch_common(monkeypatch, redis_conn, [])
    monkeypatch.setenv("MANIM_SKILL_WORK_DIR", str(tmp_path))
    # job "ghost" was never saved — handler must not raise
    handle_render_job("ghost", "spec", {"title": "T", "beats": []})
