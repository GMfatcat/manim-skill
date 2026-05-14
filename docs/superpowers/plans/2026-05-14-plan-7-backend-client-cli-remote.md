# Plan 7: Backend Client + CLI Remote Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 `manim-skill render` 能連到 Phase 2 部署的後端——新增一個共用的 HTTP `BackendClient`，並讓 CLI 的 `render` 子指令在設定後端 URL 時改走遠端提交/輪詢/下載，未設定時維持 Phase 1 的本地 in-process 行為。

**Architecture:** `manim_skill/backend_client.py` 是一個薄 HTTP client（用 httpx），包住 Phase 2 後端的 job API（submit / poll / download / delete）。CLI 的 `_cmd_render` 在 `--remote URL` 或 `MANIM_SKILL_BACKEND` env var 有設定時，改用 `BackendClient` 走遠端；否則維持本地 `render_batch`。`backend_client` 也會被 Plan 8 的 Streamlit 前端共用。

**Tech Stack:** Python ≥3.12、httpx（升為 runtime 依賴）、argparse、pytest（`httpx.ASGITransport` 對 FastAPI app 做 in-process 測試）。

---

## 背景：Plan 6（已合併入 `main`）可重用的部分

- `manim_skill/service/app.py` — `create_app(config=None, redis_conn=None) -> FastAPI`。端點：`POST /analyze`（multipart：`file` + `kind` + 選填 `guide_prompt`）、`POST /render`（JSON body：`{"mode": "codegen"|"spec", "payload": ...}`）、`GET /jobs/{id}`、`GET /jobs/{id}/result`、`DELETE /jobs/{id}`、`GET /catalog`、`GET /health`。模組層級名稱 `enqueue_analyze` / `enqueue_render` / `get_queue` 可被 monkeypatch。
- `manim_skill/service/queue.py` — `get_queue(redis_conn, is_async=True)`；`is_async=False` 時 enqueue 即 inline 執行 handler。
- `manim_skill/service/config.py` / `job_store.py` / `jobs.py` — `ServiceConfig`、`JobStore`、`ServiceJob`（`.to_dict()` 含 `job_id` / `type` / `status` / `progress` / `result` / `error`）、`JobStatus`。
- `manim_skill/cli.py`（Plan 5）— argparse CLI。現有 `_cmd_render(args)`：用 `_load_spec` 解析+驗證 spec，呼叫 `render_batch([spec], Path(args.workdir))`，成功印 `mp4:`/`gif:`/`zip:` 回 0，失敗印 `RENDER FAILED` 回 1。`render` 子指令現有參數：`spec`（位置）、`--workdir`（預設 `manim_skill_out`）。`cli.py` 現有 import：`argparse`、`sys`、`Path`、`build_component_catalog`、`render_batch`、`JobStatus`、`generate_skill_docs`、`parse_spec_text`/`SpecParseError`、`validate_spec`/`SpecValidationError`。
- `manim_skill/render/backend.py` — `render_batch(specs, workdir, ...) -> BatchJob`（本地模式仍用）。
- `manim_skill/spec/parse.py` / `validate.py` — `parse_spec_text(text) -> dict` + `SpecParseError`；`validate_spec(raw) -> SceneSpec` + `SpecValidationError`。

`pyproject.toml` 現況：`dependencies` 含 `fastapi`/`uvicorn`/`rq`/`redis`/`python-multipart`（以及 manim 等）；`[project.optional-dependencies]` 的 `dev = ["pytest>=8.0", "fakeredis>=2.21", "httpx>=0.27"]`。

環境：Windows + Docker Desktop（amd64），Python 3.13。開發機上有 `go-redis` 容器在 6379（Task 3 的 docker e2e 會用到 db 15）。

## 範圍界定

- **包含**：`backend_client.py`（HTTP client）、`httpx` 從 dev 升為 runtime 依賴、CLI `render` 的 remote mode、CLI remote 的 docker 端到端測試。
- **不包含**：Streamlit 前端（Plan 8——但 `backend_client` 的 `submit_analyze` / `submit_render_concepts` 方法本計畫就一併實作，因為 client 是共用的）；compose / ARM 打包（Plan 9）。`validate` 與 `catalog` 子指令維持純本地、本計畫不動。

## 重要：測試策略

- `backend_client` 用 `httpx.ASGITransport` 對**真實的 FastAPI app**（`create_app` + fakeredis）做 in-process 測試——不需要真的開 server，也不需要 docker。app 的 `enqueue_*` 被 monkeypatch 成 no-op（job 記錄會建立但不實際執行），job 狀態用 `JobStore` 直接操作來模擬。
- CLI remote mode 用一個 `_FakeBackendClient` 測試替身測 `_cmd_render` 的 remote 分支邏輯。
- 唯一碰 docker 的是 Task 3：在背景 thread 跑真實 uvicorn（sync queue + 真實 Redis）、以 subprocess 跑 `manim-skill render --remote`，驗證真實 socket + 真實渲染的全鏈路。

## File Structure

```
pyproject.toml                      修改 — httpx 從 dev 移到 runtime dependencies
manim_skill/backend_client.py       新增 — BackendClient / BackendClientError
manim_skill/cli.py                  修改 — render 子指令加 --remote、_cmd_render 分流、_render_remote
tests/test_backend_client.py        新增
tests/test_cli.py                   修改 — 加 autouse fixture + remote mode 測試
tests/test_cli_remote_e2e.py        新增 — docker 端到端
```

---

## Task 1: backend_client.py + httpx 升為 runtime 依賴

**Files:**
- Modify: `pyproject.toml`
- Create: `manim_skill/backend_client.py`
- Create: `tests/test_backend_client.py`

- [ ] **Step 1: 把 `httpx` 從 dev 移到 runtime 依賴** — `pyproject.toml`：把 `dependencies` 區塊最後一行 `"python-multipart>=0.0.9",` 之後加上 `"httpx>=0.27",`，並把 `[project.optional-dependencies]` 改為：

```toml
[project.optional-dependencies]
dev = ["pytest>=8.0", "fakeredis>=2.21"]
```

（`httpx` 現在是 runtime 依賴，因為 `backend_client` 在正式執行時就要用；`pytest`/`fakeredis` 仍是 dev。）其餘 `pyproject.toml` 不變。

- [ ] **Step 2: 重新安裝** — Run: `pip install -e ".[dev]"` → expect 成功。

- [ ] **Step 3: 寫失敗測試** — `tests/test_backend_client.py`:

```python
import zipfile

import fakeredis
import httpx
import pytest

from manim_skill.backend_client import BackendClient, BackendClientError
from manim_skill.service import app as app_mod
from manim_skill.service.app import create_app
from manim_skill.service.config import ServiceConfig
from manim_skill.service.job_store import JobStore
from manim_skill.service.jobs import JobStatus, ServiceJob


def _backend(tmp_path, monkeypatch):
    # a real FastAPI app over fakeredis, reached in-process via ASGITransport;
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
    http_client = httpx.Client(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    )
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
```

- [ ] **Step 4: 執行測試確認失敗** — `pytest tests/test_backend_client.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 5: 實作** — `manim_skill/backend_client.py`:

```python
from __future__ import annotations

import time
from pathlib import Path

import httpx


class BackendClientError(RuntimeError):
    """Raised when a call to the manim-skill backend fails (transport
    error, non-2xx status, or a poll timeout)."""


class BackendClient:
    """HTTP client for the manim-skill backend job API. Shared by the
    CLI's remote render mode and the Streamlit frontend. Pass a custom
    `http_client` (e.g. an httpx.Client over an ASGITransport) for
    in-process testing."""

    def __init__(
        self,
        base_url: str,
        *,
        http_client: httpx.Client | None = None,
        timeout: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = http_client or httpx.Client(
            base_url=self._base_url, timeout=timeout
        )

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            resp = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise BackendClientError(
                f"{method} {path} failed: {exc}"
            ) from exc
        if resp.status_code >= 400:
            raise BackendClientError(
                f"{method} {path} -> HTTP {resp.status_code}: {resp.text}"
            )
        return resp

    def submit_render_spec(self, spec: dict) -> str:
        resp = self._request(
            "POST", "/render", json={"mode": "spec", "payload": spec}
        )
        return resp.json()["job_id"]

    def submit_render_concepts(self, concepts: list) -> str:
        resp = self._request(
            "POST",
            "/render",
            json={"mode": "codegen", "payload": concepts},
        )
        return resp.json()["job_id"]

    def submit_analyze(
        self, content: bytes, kind: str, guide_prompt: str | None = None
    ) -> str:
        data = {"kind": kind}
        if guide_prompt:
            data["guide_prompt"] = guide_prompt
        resp = self._request(
            "POST",
            "/analyze",
            files={"file": ("input", content)},
            data=data,
        )
        return resp.json()["job_id"]

    def get_job(self, job_id: str) -> dict:
        return self._request("GET", f"/jobs/{job_id}").json()

    def wait_for_job(
        self,
        job_id: str,
        *,
        poll_interval: float = 2.0,
        timeout: float = 1800.0,
    ) -> dict:
        """Poll until the job is done or failed; return its status doc.
        Raises BackendClientError on timeout."""
        deadline = time.monotonic() + timeout
        while True:
            job = self.get_job(job_id)
            if job["status"] in ("done", "failed"):
                return job
            if time.monotonic() > deadline:
                raise BackendClientError(
                    f"timed out waiting for job {job_id}"
                )
            time.sleep(poll_interval)

    def download_result(self, job_id: str, dest_path) -> Path:
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        resp = self._request("GET", f"/jobs/{job_id}/result")
        dest_path.write_bytes(resp.content)
        return dest_path

    def delete_job(self, job_id: str) -> None:
        self._request("DELETE", f"/jobs/{job_id}")

    def get_catalog(self) -> str:
        return self._request("GET", "/catalog").json()["catalog"]
```

- [ ] **Step 6: 執行測試確認通過** — `pytest tests/test_backend_client.py -v` → expect PASS (10 passed).

- [ ] **Step 7: 執行完整非 docker 套件確認無回歸** — `pytest -m "not docker" -q` → expect 全部 PASS.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml manim_skill/backend_client.py tests/test_backend_client.py
git commit -m "feat: BackendClient HTTP client for the job API"
```

---

## Task 2: CLI Remote Mode

**Files:**
- Modify: `manim_skill/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: 在 `tests/test_cli.py` 加 import 與 autouse fixture**

`tests/test_cli.py` 目前頂部是：
```python
import json
from pathlib import Path

from manim_skill import cli as cli_mod
from manim_skill.cli import main
```
把它改為（加 `import pytest` 與一個 autouse fixture，讓既有的本地 render 測試不受環境變數干擾）：
```python
import json
from pathlib import Path

import pytest

from manim_skill import cli as cli_mod
from manim_skill.cli import main


@pytest.fixture(autouse=True)
def _no_backend_env(monkeypatch):
    """Keep render tests in local mode unless they opt into remote."""
    monkeypatch.delenv("MANIM_SKILL_BACKEND", raising=False)
```
其餘既有測試（`test_validate_*`、`test_catalog_*`、`test_render_command_*`、`test_gen_skill_docs_command`）保持不變。

- [ ] **Step 2: 在 `tests/test_cli.py` 末尾追加 remote mode 測試**

```python
class _FakeBackendClient:
    """Test double for BackendClient — records the submitted spec and
    returns a scripted job outcome."""

    last_spec = None

    def __init__(self, base_url, **kwargs):
        self.base_url = base_url

    def submit_render_spec(self, spec):
        _FakeBackendClient.last_spec = spec
        return "fake-job-id"

    def wait_for_job(self, job_id):
        return {"status": "done", "result": {}}

    def download_result(self, job_id, dest_path):
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"PK\x03\x04fake-zip")
        return dest

    def delete_job(self, job_id):
        pass


def test_render_remote_via_env(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli_mod, "BackendClient", _FakeBackendClient)
    monkeypatch.setenv("MANIM_SKILL_BACKEND", "http://spark:8000")
    spec_path = _write_spec(tmp_path, _VALID_SPEC)
    rc = main(["render", spec_path, "--workdir", str(tmp_path / "out")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "submitted:" in out
    assert "zip:" in out
    assert _FakeBackendClient.last_spec == _VALID_SPEC


def test_render_remote_via_flag(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli_mod, "BackendClient", _FakeBackendClient)
    spec_path = _write_spec(tmp_path, _VALID_SPEC)
    rc = main([
        "render", spec_path, "--remote", "http://spark:8000",
        "--workdir", str(tmp_path / "out"),
    ])
    assert rc == 0
    assert "zip:" in capsys.readouterr().out


def test_render_remote_reports_job_failure(tmp_path, monkeypatch, capsys):
    class _FailingClient(_FakeBackendClient):
        def wait_for_job(self, job_id):
            return {"status": "failed", "error": "boom"}

    monkeypatch.setattr(cli_mod, "BackendClient", _FailingClient)
    spec_path = _write_spec(tmp_path, _VALID_SPEC)
    rc = main([
        "render", spec_path, "--remote", "http://spark:8000",
        "--workdir", str(tmp_path / "out"),
    ])
    assert rc == 1
    assert "RENDER FAILED" in capsys.readouterr().err


def test_render_remote_reports_backend_error(tmp_path, monkeypatch, capsys):
    from manim_skill.backend_client import BackendClientError

    class _BrokenClient(_FakeBackendClient):
        def submit_render_spec(self, spec):
            raise BackendClientError("connection refused")

    monkeypatch.setattr(cli_mod, "BackendClient", _BrokenClient)
    spec_path = _write_spec(tmp_path, _VALID_SPEC)
    rc = main([
        "render", spec_path, "--remote", "http://spark:8000",
        "--workdir", str(tmp_path / "out"),
    ])
    assert rc == 1
    assert "BACKEND ERROR" in capsys.readouterr().err


def test_render_remote_rejects_unparseable_spec(tmp_path, monkeypatch, capsys):
    # malformed JSON is caught locally before any backend call
    monkeypatch.setattr(cli_mod, "BackendClient", _FakeBackendClient)
    bad = tmp_path / "bad.json"
    bad.write_text("this is not json", encoding="utf-8")
    rc = main([
        "render", str(bad), "--remote", "http://spark:8000",
        "--workdir", str(tmp_path / "out"),
    ])
    assert rc == 1
    assert "INVALID" in capsys.readouterr().err
```

- [ ] **Step 3: 執行測試確認失敗** — `pytest tests/test_cli.py -v` → expect FAIL（新測試因 `cli.py` 還沒有 `BackendClient` / `--remote` 而失敗；`AttributeError` 或 `SystemExit`）。

- [ ] **Step 4: 修改 `manim_skill/cli.py`**

4a. 把頂部 import 區
```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path
```
改為（加 `os` 與 `BackendClient` import）：
```python
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from manim_skill.backend_client import BackendClient, BackendClientError
```
（其餘既有 import 行不變。）

4b. 把整個 `_cmd_render` 函式取代為：
```python
def _cmd_render(args) -> int:
    try:
        text = Path(args.spec).read_text(encoding="utf-8")
        raw = parse_spec_text(text)
    except (SpecParseError, OSError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    backend_url = args.remote or os.environ.get("MANIM_SKILL_BACKEND")
    if backend_url:
        return _render_remote(raw, backend_url, args.workdir)

    try:
        spec = validate_spec(raw)
    except SpecValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    batch = render_batch([spec], Path(args.workdir))
    clip = batch.clip_jobs[0]
    if clip.status == JobStatus.DONE:
        print(f"mp4: {clip.mp4_path}")
        print(f"gif: {clip.gif_path}")
        print(f"zip: {batch.zip_path}")
        return 0
    print(f"RENDER FAILED: {clip.error}", file=sys.stderr)
    return 1


def _render_remote(raw_spec: dict, backend_url: str, workdir: str) -> int:
    """Submit a spec to a deployed backend, poll, download the result.
    The backend validates the spec — the agent path's 'repair loop' is
    the agent rewriting the spec and re-running render."""
    client = BackendClient(backend_url)
    try:
        job_id = client.submit_render_spec(raw_spec)
        print(f"submitted: {job_id} (backend: {backend_url})")
        job = client.wait_for_job(job_id)
        if job["status"] != "done":
            print(
                f"RENDER FAILED: {job.get('error')}", file=sys.stderr
            )
            return 1
        zip_path = client.download_result(
            job_id, Path(workdir) / f"{job_id}.zip"
        )
        client.delete_job(job_id)
        print(f"zip: {zip_path}")
        return 0
    except BackendClientError as exc:
        print(f"BACKEND ERROR: {exc}", file=sys.stderr)
        return 1
```

4c. 在 `build_parser` 內，`render` 子指令的 `--workdir` 參數**之後**，加一個 `--remote` 參數。把
```python
    p_render.add_argument(
        "--workdir",
        default="manim_skill_out",
        help="working/output directory (default: manim_skill_out)",
    )
    p_render.set_defaults(func=_cmd_render)
```
改為：
```python
    p_render.add_argument(
        "--workdir",
        default="manim_skill_out",
        help="working/output directory (default: manim_skill_out)",
    )
    p_render.add_argument(
        "--remote",
        default=None,
        help=(
            "backend URL for remote rendering (or set "
            "MANIM_SKILL_BACKEND); if unset, renders locally in-process"
        ),
    )
    p_render.set_defaults(func=_cmd_render)
```

`cli.py` 其餘部分（`_load_spec`、`_cmd_validate`、`_cmd_catalog`、`_cmd_gen_skill_docs`、`build_parser` 的其他子指令、`main`）保持不變。注意 `_load_spec` 仍被 `_cmd_validate` 使用——不要刪除它。

- [ ] **Step 5: 執行測試確認通過** — `pytest tests/test_cli.py -v` → expect PASS（既有測試 + 5 個新 remote 測試全過）。

- [ ] **Step 6: 執行完整非 docker 套件確認無回歸** — `pytest -m "not docker" -q` → expect 全部 PASS.

- [ ] **Step 7: Commit**

```bash
git add manim_skill/cli.py tests/test_cli.py
git commit -m "feat: CLI remote render mode (--remote / MANIM_SKILL_BACKEND)"
```

---

## Task 3: CLI Remote 端到端測試（docker）

在背景 thread 跑真實 uvicorn（sync queue + 真實 Redis），以 subprocess 跑 `manim-skill render --remote`，驗證真實 socket + 真實渲染的全鏈路。

**Files:**
- Create: `tests/test_cli_remote_e2e.py`

- [ ] **Step 1: 寫測試** — `tests/test_cli_remote_e2e.py`:

```python
import json
import socket
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

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
        deadline = time.monotonic() + 15
        while not server.started:
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
```

- [ ] **Step 2: 執行端到端測試** — `pytest tests/test_cli_remote_e2e.py -v -m docker`
  Expected: PASS (1 passed)。會渲染真實影片，較慢，要耐心。背景 uvicorn 用 `is_async=False` 的 sync queue，所以渲染在 `POST /render` 請求內 inline 執行，CLI 的輪詢第一次就看到 done。
  若 uvicorn server 起不來或 `server.started` 屬性在安裝的 uvicorn 版本上不存在，執行 `python -c "import uvicorn, inspect; print([a for a in dir(uvicorn.Server) if not a.startswith('_')])"` 確認可用的「已啟動」判斷方式並做最小調整（例如改成輪詢 `GET /health`）。

- [ ] **Step 3: 執行完整測試套件** — `pytest -q`
  Expected: 全部 PASS（含所有 docker 測試）。

- [ ] **Step 4: Commit**

```bash
git add tests/test_cli_remote_e2e.py
git commit -m "test: CLI remote render end-to-end docker integration test"
```

---

## Self-Review

**1. Spec coverage（對照 Phase 2 設計文件 §7 CLI Remote Mode）**

- 共用 HTTP client 模組 `manim_skill/backend_client.py`（submit / poll / download / delete）→ Task 1（`BackendClient`，含 `submit_render_spec`/`submit_render_concepts`/`submit_analyze`/`get_job`/`wait_for_job`/`download_result`/`delete_job`/`get_catalog`）✓
- CLI 與 Streamlit 共用同一 client → Task 1 實作了 Streamlit 會用到的 `submit_analyze`/`submit_render_concepts`（Plan 8 直接重用）✓
- `manim-skill render` 在 `--remote URL` 或 `MANIM_SKILL_BACKEND` env var 設定時走遠端：`POST /render`(mode=spec) → 輪詢 → 下載 → `DELETE` → Task 2（`_render_remote`）✓
- 未設定時維持 Phase 1 本地 in-process 行為 → Task 2（`_cmd_render` 的 backend_url 為 None 時走 `render_batch` 分支，邏輯與 Phase 1 等價）✓
- `validate`、`catalog` 維持純本地 → 本計畫不動這兩個子指令（範圍界定已說明）✓
- agent 路徑的「repair」= agent 重寫 spec 重送（無內部 repair loop）→ `_render_remote` 用 `mode=spec`、後端 `render_batch` 不帶 repairer（Plan 6 既有行為），job 失敗時 CLI 回報錯誤、由 agent 重送 ✓

**不在本計畫範圍（後續計畫）：** Streamlit 前端（Plan 8，會 import `backend_client`）；compose / ARM64 打包（Plan 9）。已在範圍界定說明。

**2. Placeholder scan：** 無 TBD/TODO。每個 step 有完整程式碼或精確指令。Task 2 對既有 `tests/test_cli.py` 的修改以「把 X 改為 Y」的精確前後內容呈現，並明確說明既有測試不變、`_load_spec` 不可刪。Task 3 對 uvicorn `server.started` 可能的版本差異給了具體的查證與 fallback 方向（改輪詢 `/health`）。

**3. Type consistency：**
- `BackendClient(base_url, *, http_client=None, timeout=120.0)` 與方法 `submit_render_spec(spec) -> str`、`submit_render_concepts(concepts) -> str`、`submit_analyze(content, kind, guide_prompt=None) -> str`、`get_job(job_id) -> dict`、`wait_for_job(job_id, *, poll_interval, timeout) -> dict`、`download_result(job_id, dest_path) -> Path`、`delete_job(job_id)`、`get_catalog() -> str`、`BackendClientError`（Task 1）→ Task 2 的 `_render_remote` 使用 `submit_render_spec`/`wait_for_job`/`download_result`/`delete_job`/`BackendClientError`，Task 2 測試的 `_FakeBackendClient` 對應同樣的方法簽名，Task 1 測試一致。
- `_cmd_render` / `_render_remote`（Task 2）— `_render_remote(raw_spec, backend_url, workdir)`；`_cmd_render` 以 `args.remote` / `MANIM_SKILL_BACKEND` 決定分流。`--remote` 對應 `args.remote`。
- 後端 API 形狀（`POST /render` body `{"mode","payload"}`、`GET /jobs/{id}` 回 status doc、`GET /jobs/{id}/result` 回 zip、`DELETE /jobs/{id}`、`GET /catalog` 回 `{"catalog": ...}`）— 與 Plan 6 的 `app.py` 一致；`BackendClient` 的方法對應這些端點。
- 重用既有：`create_app`、`ServiceConfig`、`JobStore`、`ServiceJob`/`JobStatus`、`get_queue`、`app_mod.enqueue_*` / `app_mod.get_queue`（monkeypatch 對象）、`parse_spec_text`/`SpecParseError`、`validate_spec`/`SpecValidationError`、`render_batch`、`JobStatus`(render) — 簽名與 Plan 1–6 既有程式一致。

無不一致。

---

## Execution Handoff

Plan 完成並存於 `docs/superpowers/plans/2026-05-14-plan-7-backend-client-cli-remote.md`。將以 subagent-driven-development 執行（依使用者既定偏好，不再詢問執行方式）。3 個 task 循序相依（Task 2 依賴 Task 1、Task 3 依賴 Task 2），各自單獨執行，無平行波次。
