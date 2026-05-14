import zipfile

import pytest
import redis as redis_lib
from fastapi.testclient import TestClient

from manim_skill.service import app as app_mod
from manim_skill.service.app import create_app
from manim_skill.service.config import ServiceConfig
from manim_skill.service.queue import get_queue

# Use a high-numbered DB on the local Redis so jobs are isolated from
# any real workloads.  DB 15 is reserved for this test.
_TEST_REDIS_URL = "redis://localhost:6379/15"


def _sync_client(tmp_path, monkeypatch):
    """An app whose queue runs jobs inline (is_async=False), so a POST
    that enqueues a job blocks until the real handler — and the real
    render_batch — finishes."""
    redis_conn = redis_lib.from_url(_TEST_REDIS_URL)
    redis_conn.flushdb()  # start with a clean slate
    sync_queue = get_queue(redis_conn, is_async=False)
    monkeypatch.setattr(app_mod, "get_queue", lambda conn: sync_queue)
    config = ServiceConfig(
        redis_url=_TEST_REDIS_URL,
        llm_base_url="http://unused",
        llm_model="unused",
        llm_concurrency=4,
        render_concurrency=2,
        work_dir=tmp_path,
        job_ttl_seconds=3600,
        web_quota=5,
    )
    monkeypatch.setenv("MANIM_SKILL_WORK_DIR", str(tmp_path))
    monkeypatch.setenv("MANIM_SKILL_REDIS_URL", _TEST_REDIS_URL)
    return TestClient(create_app(config=config, redis_conn=redis_conn))


@pytest.mark.docker
def test_render_spec_job_end_to_end(tmp_path, monkeypatch):
    client = _sync_client(tmp_path, monkeypatch)
    spec = {
        "title": "Service E2E",
        "beats": [
            {
                "component": "TextBeat",
                "params": {"text": "Hello"},
                "duration": 1.0,
            }
        ],
    }
    resp = client.post("/render", json={"mode": "spec", "payload": spec})
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    # is_async=False -> the handler (and the real docker render) already
    # ran inline during the POST above.
    status = client.get(f"/jobs/{job_id}").json()
    assert status["status"] == "done", status

    result = client.get(f"/jobs/{job_id}/result")
    assert result.status_code == 200
    assert result.headers["content-type"] == "application/zip"

    out = tmp_path / "downloaded.zip"
    out.write_bytes(result.content)
    with zipfile.ZipFile(out) as zf:
        assert "manifest.json" in zf.namelist()

    assert client.delete(f"/jobs/{job_id}").status_code == 200
    assert client.get(f"/jobs/{job_id}").status_code == 404
