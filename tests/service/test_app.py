import json
import zipfile

import fakeredis
from fastapi.testclient import TestClient

from manim_skill.service import app as app_mod
from manim_skill.service.app import create_app
from manim_skill.service.config import ServiceConfig
from manim_skill.service.job_store import JobStore
from manim_skill.service.jobs import JobStatus, ServiceJob


def _client(tmp_path, monkeypatch, redis_conn):
    # isolate the API from RQ: record enqueue calls instead of running them
    monkeypatch.setattr(app_mod, "enqueue_analyze", lambda *a, **k: None)
    monkeypatch.setattr(app_mod, "enqueue_render", lambda *a, **k: None)
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
    return TestClient(app), JobStore(redis_conn), config


def test_health(tmp_path, monkeypatch):
    client, _store, _config = _client(tmp_path, monkeypatch, fakeredis.FakeRedis())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_catalog_lists_components(tmp_path, monkeypatch):
    client, _store, _config = _client(tmp_path, monkeypatch, fakeredis.FakeRedis())
    resp = client.get("/catalog")
    assert resp.status_code == 200
    assert "TextBeat" in resp.json()["catalog"]


def test_analyze_creates_job(tmp_path, monkeypatch):
    redis_conn = fakeredis.FakeRedis()
    client, store, _config = _client(tmp_path, monkeypatch, redis_conn)
    resp = client.post(
        "/analyze",
        files={"file": ("paper.txt", b"some text", "text/plain")},
        data={"kind": "text"},
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    job = store.get(job_id)
    assert job is not None and job.type == "analyze"


def test_analyze_rejects_bad_kind(tmp_path, monkeypatch):
    client, _store, _config = _client(tmp_path, monkeypatch, fakeredis.FakeRedis())
    resp = client.post(
        "/analyze",
        files={"file": ("x.bin", b"data", "application/octet-stream")},
        data={"kind": "spreadsheet"},
    )
    assert resp.status_code == 400


def test_render_codegen_within_quota(tmp_path, monkeypatch):
    redis_conn = fakeredis.FakeRedis()
    client, store, _config = _client(tmp_path, monkeypatch, redis_conn)
    concepts = [
        {"concept": f"C{i}", "why_suitable": "w", "storyboard": "s"}
        for i in range(3)
    ]
    resp = client.post(
        "/render", json={"mode": "codegen", "payload": concepts}
    )
    assert resp.status_code == 200
    assert store.get(resp.json()["job_id"]).type == "render"


def test_render_codegen_over_quota_rejected(tmp_path, monkeypatch):
    client, _store, _config = _client(tmp_path, monkeypatch, fakeredis.FakeRedis())
    concepts = [
        {"concept": f"C{i}", "why_suitable": "w", "storyboard": "s"}
        for i in range(6)
    ]
    resp = client.post(
        "/render", json={"mode": "codegen", "payload": concepts}
    )
    assert resp.status_code == 400


def test_render_spec_mode_ok(tmp_path, monkeypatch):
    client, _store, _config = _client(tmp_path, monkeypatch, fakeredis.FakeRedis())
    spec = {
        "title": "T",
        "beats": [{"component": "TextBeat", "params": {"text": "Hi"}}],
    }
    resp = client.post("/render", json={"mode": "spec", "payload": spec})
    assert resp.status_code == 200


def test_get_job_not_found(tmp_path, monkeypatch):
    client, _store, _config = _client(tmp_path, monkeypatch, fakeredis.FakeRedis())
    assert client.get("/jobs/nope").status_code == 404


def test_get_job_returns_status(tmp_path, monkeypatch):
    redis_conn = fakeredis.FakeRedis()
    client, store, _config = _client(tmp_path, monkeypatch, redis_conn)
    store.save(ServiceJob(job_id="j1", type="analyze", status=JobStatus.RUNNING))
    resp = client.get("/jobs/j1")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


def test_get_result_not_ready(tmp_path, monkeypatch):
    redis_conn = fakeredis.FakeRedis()
    client, store, _config = _client(tmp_path, monkeypatch, redis_conn)
    store.save(ServiceJob(job_id="j1", type="render", status=JobStatus.RUNNING))
    assert client.get("/jobs/j1/result").status_code == 409


def test_get_result_returns_zip(tmp_path, monkeypatch):
    redis_conn = fakeredis.FakeRedis()
    client, store, _config = _client(tmp_path, monkeypatch, redis_conn)
    zip_path = tmp_path / "out.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"concepts": []}))
    store.save(
        ServiceJob(
            job_id="j1",
            type="render",
            status=JobStatus.DONE,
            result={"zip_path": str(zip_path)},
        )
    )
    resp = client.get("/jobs/j1/result")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"


def test_delete_job_removes_record_and_zip(tmp_path, monkeypatch):
    redis_conn = fakeredis.FakeRedis()
    client, store, _config = _client(tmp_path, monkeypatch, redis_conn)
    zip_path = tmp_path / "out.zip"
    zip_path.write_bytes(b"PK\x03\x04zip")
    store.save(
        ServiceJob(
            job_id="j1",
            type="render",
            status=JobStatus.DONE,
            result={"zip_path": str(zip_path)},
        )
    )
    resp = client.delete("/jobs/j1")
    assert resp.status_code == 200
    assert store.get("j1") is None
    assert not zip_path.exists()
