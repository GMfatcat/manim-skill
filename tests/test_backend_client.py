import zipfile

import fakeredis
import pytest
from starlette.testclient import TestClient

from manim_skill.backend_client import BackendClient, BackendClientError
from manim_skill.service import app as app_mod
from manim_skill.service.app import create_app
from manim_skill.service.config import ServiceConfig
from manim_skill.service.job_store import JobStore
from manim_skill.service.jobs import JobStatus, ServiceJob


def _backend(tmp_path, monkeypatch):
    # a real FastAPI app over fakeredis, reached in-process via
    # starlette.testclient.TestClient (which extends httpx.Client and
    # wraps ASGI synchronously — ASGITransport is async-only in httpx>=0.27);
    # enqueue is a no-op so jobs are created but never actually run.
    monkeypatch.setattr(app_mod, "enqueue_analyze", lambda *a, **k: None)
    monkeypatch.setattr(app_mod, "enqueue_render", lambda *a, **k: None)
    redis_conn = fakeredis.FakeRedis()
    config = ServiceConfig(
        redis_url="redis://unused",
        llm_base_url="x",
        llm_model="x",
        llm_concurrency=4,
        render_concurrency=3,
        work_dir=tmp_path,
        job_ttl_seconds=3600,
        web_quota=5,
    )
    app = create_app(config=config, redis_conn=redis_conn)
    http_client = TestClient(app, base_url="http://testserver")
    client = BackendClient("http://testserver", http_client=http_client)
    return client, JobStore(redis_conn)


def test_submit_render_spec_returns_job_id(tmp_path, monkeypatch):
    client, store = _backend(tmp_path, monkeypatch)
    spec = {
        "title": "T",
        "beats": [{"component": "TextBeat", "params": {"text": "Hi"}}],
    }
    job_id = client.submit_render_spec(spec)
    assert store.get(job_id) is not None


def test_submit_render_concepts_returns_job_id(tmp_path, monkeypatch):
    client, store = _backend(tmp_path, monkeypatch)
    job_id = client.submit_render_concepts(
        [{"concept": "C", "why_suitable": "w", "storyboard": "s"}]
    )
    assert store.get(job_id) is not None


def test_submit_analyze_returns_job_id(tmp_path, monkeypatch):
    client, store = _backend(tmp_path, monkeypatch)
    job_id = client.submit_analyze(b"some text", "text")
    assert store.get(job_id) is not None


def test_get_job_returns_status_dict(tmp_path, monkeypatch):
    client, store = _backend(tmp_path, monkeypatch)
    store.save(
        ServiceJob(job_id="j1", type="render", status=JobStatus.RUNNING)
    )
    job = client.get_job("j1")
    assert job["status"] == "running"


def test_get_job_missing_raises(tmp_path, monkeypatch):
    client, _store = _backend(tmp_path, monkeypatch)
    with pytest.raises(BackendClientError):
        client.get_job("nope")


def test_wait_for_job_returns_when_done(tmp_path, monkeypatch):
    client, store = _backend(tmp_path, monkeypatch)
    store.save(
        ServiceJob(
            job_id="j1",
            type="render",
            status=JobStatus.DONE,
            result={"zip_path": "x"},
        )
    )
    job = client.wait_for_job("j1", poll_interval=0.01, timeout=2.0)
    assert job["status"] == "done"


def test_wait_for_job_times_out(tmp_path, monkeypatch):
    client, store = _backend(tmp_path, monkeypatch)
    store.save(
        ServiceJob(job_id="j1", type="render", status=JobStatus.RUNNING)
    )
    with pytest.raises(BackendClientError):
        client.wait_for_job("j1", poll_interval=0.01, timeout=0.05)


def test_download_result_writes_zip(tmp_path, monkeypatch):
    client, store = _backend(tmp_path, monkeypatch)
    src_zip = tmp_path / "src.zip"
    with zipfile.ZipFile(src_zip, "w") as zf:
        zf.writestr("manifest.json", "{}")
    store.save(
        ServiceJob(
            job_id="j1",
            type="render",
            status=JobStatus.DONE,
            result={"zip_path": str(src_zip)},
        )
    )
    dest = client.download_result("j1", tmp_path / "out" / "got.zip")
    assert dest.exists()
    with zipfile.ZipFile(dest) as zf:
        assert "manifest.json" in zf.namelist()


def test_delete_job(tmp_path, monkeypatch):
    client, store = _backend(tmp_path, monkeypatch)
    store.save(ServiceJob(job_id="j1", type="render"))
    client.delete_job("j1")
    assert store.get("j1") is None


def test_get_catalog(tmp_path, monkeypatch):
    client, _store = _backend(tmp_path, monkeypatch)
    catalog = client.get_catalog()
    assert "TextBeat" in catalog


def test_download_result_bytes(tmp_path, monkeypatch):
    import io

    client, store = _backend(tmp_path, monkeypatch)
    src_zip = tmp_path / "src.zip"
    with zipfile.ZipFile(src_zip, "w") as zf:
        zf.writestr("manifest.json", "{}")
    store.save(
        ServiceJob(
            job_id="j1",
            type="render",
            status=JobStatus.DONE,
            result={"zip_path": str(src_zip)},
        )
    )
    data = client.download_result_bytes("j1")
    assert isinstance(data, bytes)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert "manifest.json" in zf.namelist()


def test_close_closes_the_http_client(tmp_path, monkeypatch):
    client, _store = _backend(tmp_path, monkeypatch)
    client.close()
    assert client._client.is_closed


def test_context_manager_closes(tmp_path, monkeypatch):
    client, _store = _backend(tmp_path, monkeypatch)
    with client as entered:
        assert entered is client
    assert client._client.is_closed
