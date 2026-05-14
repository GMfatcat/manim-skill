import os
import socket
import subprocess
import time
import zipfile
from pathlib import Path

import httpx
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_COMPOSE_FILE = str(_REPO_ROOT / "docker-compose.yml")
# a Linux path: a real path on a Linux host, a Docker-VM path on Docker
# Desktop — valid on both sides of the same-path bind mount.
_WORK_DIR = "/var/lib/manim-skill-e2e"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _compose(args, env, *, check=True, timeout=300):
    return subprocess.run(
        ["docker", "compose", "-f", _COMPOSE_FILE, *args],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
        timeout=timeout,
    )


@pytest.mark.docker
def test_compose_stack_renders_a_spec(tmp_path):
    api_port = _free_port()
    env = {
        **os.environ,
        "MANIM_SKILL_LLM_BASE_URL": "http://host.docker.internal:11434/v1",
        "MANIM_SKILL_LLM_MODEL": "unused-for-spec-mode",
        "MANIM_SKILL_WORK_DIR": _WORK_DIR,
        "MANIM_SKILL_API_PORT": str(api_port),
        "MANIM_SKILL_UI_PORT": str(_free_port()),
        "COMPOSE_PROJECT_NAME": "manim-skill-e2e",
    }
    base = f"http://127.0.0.1:{api_port}"

    # Ensure the bind-mount source directory exists in the Docker VM.
    # On Docker Desktop (Windows/Mac), /var/lib/... only exists in the
    # Linux VM, not on the Windows host. Use a throwaway container to
    # create it so docker compose up doesn't fail with a bind-mount error.
    subprocess.run(
        [
            "docker", "run", "--rm",
            "-v", "/var/lib:/var/lib",
            "alpine",
            "mkdir", "-p", _WORK_DIR,
        ],
        check=True,
    )

    _compose(["up", "-d", "redis", "api", "worker"], env)
    try:
        # wait for the api to be healthy
        deadline = time.monotonic() + 90
        while True:
            try:
                if httpx.get(f"{base}/health", timeout=3).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.monotonic() > deadline:
                logs = _compose(["logs"], env, check=False).stdout
                raise RuntimeError(f"api did not come up:\n{logs}")
            time.sleep(2)

        # submit a spec-mode render job (no LLM needed)
        spec = {
            "title": "Compose E2E",
            "beats": [
                {
                    "component": "TextBeat",
                    "params": {"text": "Hello"},
                    "duration": 1.0,
                }
            ],
        }
        resp = httpx.post(
            f"{base}/render",
            json={"mode": "spec", "payload": spec},
            timeout=10,
        )
        assert resp.status_code == 200, resp.text
        job_id = resp.json()["job_id"]

        # poll until done — the worker spawns a render container for the beat
        deadline = time.monotonic() + 360
        while True:
            job = httpx.get(f"{base}/jobs/{job_id}", timeout=5).json()
            if job["status"] in ("done", "failed"):
                break
            if time.monotonic() > deadline:
                logs = _compose(
                    ["logs", "worker"], env, check=False
                ).stdout
                raise RuntimeError(f"render job stuck: {job}\n{logs}")
            time.sleep(3)
        assert job["status"] == "done", job

        # download + verify the result zip
        result = httpx.get(f"{base}/jobs/{job_id}/result", timeout=30)
        assert result.status_code == 200
        zip_path = tmp_path / "result.zip"
        zip_path.write_bytes(result.content)
        with zipfile.ZipFile(zip_path) as zf:
            assert "manifest.json" in zf.namelist()

        # delete cleans up
        deleted = httpx.request(
            "DELETE", f"{base}/jobs/{job_id}", timeout=10
        )
        assert deleted.status_code == 200
    finally:
        _compose(["down", "-v"], env, check=False)
