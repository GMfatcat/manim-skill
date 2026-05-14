import json
import socket
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

import httpx
import pytest
import redis as redis_lib
import uvicorn

from manim_skill.service import app as app_mod
from manim_skill.service.app import create_app
from manim_skill.service.config import ServiceConfig
from manim_skill.service.queue import get_queue

# real Redis on the dev machine's go-redis container; db 15 is isolated
_TEST_REDIS_URL = "redis://localhost:6379/15"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.mark.docker
def test_cli_render_remote_end_to_end(tmp_path, monkeypatch):
    # the handler builds its own Redis connection from env, so the
    # uvicorn thread, the handler, and this test must share a real
    # Redis (fakeredis can't be shared across the connection the
    # handler re-derives). go-redis db 15, flushed for isolation.
    redis_conn = redis_lib.from_url(_TEST_REDIS_URL)
    redis_conn.flushdb()
    sync_queue = get_queue(redis_conn, is_async=False)
    monkeypatch.setattr(app_mod, "get_queue", lambda conn: sync_queue)
    service_work = tmp_path / "service_work"
    monkeypatch.setenv("MANIM_SKILL_REDIS_URL", _TEST_REDIS_URL)
    monkeypatch.setenv("MANIM_SKILL_WORK_DIR", str(service_work))

    config = ServiceConfig(
        redis_url=_TEST_REDIS_URL,
        llm_base_url="http://unused",
        llm_model="unused",
        llm_concurrency=4,
        render_concurrency=2,
        work_dir=service_work,
        job_ttl_seconds=3600,
        web_quota=5,
    )
    app = create_app(config=config, redis_conn=redis_conn)

    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="warning"
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        # NOTE: the installed uvicorn does not expose server.started, so
        # we poll GET /health with httpx until the server responds or we
        # time out (15 s).
        health_url = f"http://127.0.0.1:{port}/health"
        deadline = time.monotonic() + 15
        while True:
            try:
                resp = httpx.get(health_url, timeout=1.0)
                if resp.status_code == 200:
                    break
            except Exception:
                pass
            if time.monotonic() > deadline:
                raise RuntimeError("uvicorn did not start in time")
            time.sleep(0.1)

        spec = {
            "title": "CLI Remote E2E",
            "beats": [
                {
                    "component": "TextBeat",
                    "params": {"text": "Hello"},
                    "duration": 1.0,
                }
            ],
        }
        spec_path = tmp_path / "spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        out_dir = tmp_path / "cli_out"

        result = subprocess.run(
            [
                sys.executable, "-m", "manim_skill.cli", "render",
                str(spec_path),
                "--remote", f"http://127.0.0.1:{port}",
                "--workdir", str(out_dir),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
        assert result.returncode == 0, f"stderr:\n{result.stderr}"
        assert "submitted:" in result.stdout
        assert "zip:" in result.stdout

        zip_line = next(
            line for line in result.stdout.splitlines()
            if line.startswith("zip:")
        )
        zip_path = Path(zip_line.split("zip:", 1)[1].strip())
        assert zip_path.exists()
        with zipfile.ZipFile(zip_path) as zf:
            assert "manifest.json" in zf.namelist()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
