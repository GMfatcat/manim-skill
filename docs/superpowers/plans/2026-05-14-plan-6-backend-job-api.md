# Plan 6: 後端 Job API + RQ 佇列 + Workers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 Phase 2 的後端——一個 FastAPI job API + Redis/RQ 佇列 + RQ worker handler，把 Phase 1–5 的 pipeline 包成可非同步提交、輪詢、下載的多人服務後端。

**Architecture:** 新增 `manim_skill/service/` 子套件。FastAPI app（`create_app` factory）暴露 `/analyze`、`/render`、`/jobs/{id}` 等端點；端點建立 job 記錄（存 Redis，`JobStore`）並把工作丟進 RQ 佇列；RQ worker 跑兩個 handler（`handle_analyze_job` / `handle_render_job`），呼叫既有的 `analyze` / `generate_spec` / `render_batch`。LLM 併發由一個 Redis semaphore（`ThrottledLLMClient`）跨 worker 限流。

**Tech Stack:** Python ≥3.12、FastAPI、uvicorn、RQ（Redis Queue）、redis-py、Pydantic v2、pytest + fakeredis + httpx。

---

## 背景：Phase 1（已合併入 `main`，153 測試）可重用的部分

- `manim_skill/llm/input_prep.py` — `prepare_input(content, kind) -> str`（`kind` ∈ `"text"|"code"|"pdf"`；接受 bytes 或 path）。
- `manim_skill/llm/analyze.py` — `analyze(client, prepared_input, guide_prompt=None) -> list[ConceptCandidate]`、`ConceptCandidate`（Pydantic，有 `.model_dump()` / `.model_validate()`）、`AnalyzeError`。
- `manim_skill/llm/catalog.py` — `build_component_catalog() -> str`。
- `manim_skill/llm/codegen.py` — `generate_spec(client, concept, catalog) -> SceneSpec`、`CodegenError`。
- `manim_skill/llm/client.py` — `LLMClient`（Protocol，`.complete(system, user) -> str`）、`OpenAIClient(base_url, model, ...)`、`FakeLLMClient`。
- `manim_skill/llm/repair.py` — `BeatRepairer(client)`。
- `manim_skill/render/backend.py` — `render_batch(specs, workdir, *, max_workers=3, cache=None, repairer=None) -> BatchJob`。
- `manim_skill/render/jobs.py` — `BatchJob`（`.clip_jobs`、`.status`、`.zip_path`）。
- `manim_skill/spec/validate.py` — `validate_spec(raw_dict) -> SceneSpec`、`SpecValidationError`。
- `manim_skill/spec/schema.py` — `SceneSpec`。

環境：Windows + Docker Desktop（amd64 開發機），Python 3.13。**注意**：開發機上已有一個 `go-redis` 容器佔用 6379——本計畫的單元測試一律用 `fakeredis`，不碰真實 Redis；真實 Redis 留給 Plan 9 的 compose。

## 範圍界定

- **包含**：`service/` 子套件——config、ServiceJob 模型、Redis JobStore、LLM throttle、兩個 job handler、RQ 佇列整合、FastAPI app、RQ worker 進入點、docker 整合測試。
- **不包含**：`backend_client` 與 CLI remote mode（Plan 7）；Streamlit 前端（Plan 8）；docker-compose、多架構打包（Plan 9）。本計畫的 FastAPI app 用 `TestClient` 測試，不需要 compose。

## 重要：測試策略

- `config` / `ServiceJob` / `JobStore` / `ThrottledLLMClient` — 純邏輯或只碰 Redis，用 **fakeredis** 測，無 docker。
- `handlers` — 用 `FakeLLMClient`（Phase 4 既有）+ monkeypatched `render_batch` + fakeredis 的 `JobStore` 測，無 docker。
- `queue` — mock 掉 RQ `Queue` 物件，斷言 `enqueue` 被以正確參數呼叫。
- `app` — FastAPI `TestClient` + fakeredis + monkeypatched `enqueue_*`，測端點邏輯。
- `worker` — 薄進入點，只做 import / 可建構的 smoke test。
- 唯一碰 docker 的是最後的整合測試（Task 9，`@pytest.mark.docker`）：RQ sync 模式 + fakeredis + 真實 `render_batch`，驗證 API → handler → 渲染 → zip 全鏈路。

## File Structure

```
pyproject.toml                       修改 — 加依賴 fastapi/uvicorn/rq/redis/python-multipart + dev fakeredis/httpx
manim_skill/service/
  __init__.py                        新增（空）
  config.py                          新增 — ServiceConfig / load_config（env vars）
  jobs.py                            新增 — JobStatus / ServiceJob
  job_store.py                       新增 — JobStore（Redis-backed CRUD + TTL）
  llm_throttle.py                    新增 — ThrottledLLMClient（Redis semaphore）
  handlers.py                        新增 — handle_analyze_job / handle_render_job
  queue.py                           新增 — get_queue / enqueue_analyze / enqueue_render
  app.py                             新增 — create_app（FastAPI factory）
  worker.py                          新增 — RQ worker 進入點
tests/service/
  __init__.py                        新增（空）
  test_config.py / test_jobs.py / test_job_store.py / test_llm_throttle.py
  test_handlers.py / test_queue.py / test_app.py / test_worker.py
  test_service_e2e.py                新增 — docker 整合測試
```

---

## Task 1: Service 套件骨架 + 依賴 + Config

**Files:**
- Modify: `pyproject.toml`
- Create: `manim_skill/service/__init__.py`（空）
- Create: `tests/service/__init__.py`（空）
- Create: `manim_skill/service/config.py`
- Create: `tests/service/test_config.py`

- [ ] **Step 1: 加依賴到 `pyproject.toml`** — 把 `[project]` 的 `dependencies` 改為：

```toml
dependencies = [
    "manim>=0.19,<0.21",
    "pydantic>=2.6",
    "json5>=0.9",
    "openai>=1.0",
    "pypdf>=4.0",
    "fastapi>=0.110",
    "uvicorn>=0.29",
    "rq>=1.16",
    "redis>=5.0",
    "python-multipart>=0.0.9",
]
```

並把 `[project.optional-dependencies]` 改為：

```toml
[project.optional-dependencies]
dev = ["pytest>=8.0", "fakeredis>=2.21", "httpx>=0.27"]
```

其餘 `pyproject.toml` 不變。

- [ ] **Step 2: 重新安裝** — Run: `pip install -e ".[dev]"` → expect 成功。

- [ ] **Step 3: 建立空套件檔** — 建立空檔 `manim_skill/service/__init__.py` 與 `tests/service/__init__.py`。

- [ ] **Step 4: 寫失敗測試** — `tests/service/test_config.py`:

```python
from pathlib import Path

from manim_skill.service.config import ServiceConfig, load_config


def test_load_config_defaults(monkeypatch):
    for var in [
        "MANIM_SKILL_REDIS_URL", "MANIM_SKILL_LLM_BASE_URL",
        "MANIM_SKILL_LLM_MODEL", "MANIM_SKILL_LLM_CONCURRENCY",
        "MANIM_SKILL_RENDER_CONCURRENCY", "MANIM_SKILL_WORK_DIR",
        "MANIM_SKILL_JOB_TTL", "MANIM_SKILL_WEB_QUOTA",
    ]:
        monkeypatch.delenv(var, raising=False)
    config = load_config()
    assert isinstance(config, ServiceConfig)
    assert config.redis_url.startswith("redis://")
    assert config.llm_concurrency == 4
    assert config.render_concurrency == 3
    assert config.job_ttl_seconds == 3600
    assert config.web_quota == 5
    assert isinstance(config.work_dir, Path)


def test_load_config_reads_env(monkeypatch):
    monkeypatch.setenv("MANIM_SKILL_LLM_CONCURRENCY", "8")
    monkeypatch.setenv("MANIM_SKILL_WEB_QUOTA", "3")
    monkeypatch.setenv("MANIM_SKILL_WORK_DIR", "/tmp/custom")
    config = load_config()
    assert config.llm_concurrency == 8
    assert config.web_quota == 3
    assert config.work_dir == Path("/tmp/custom")
```

- [ ] **Step 5: 執行測試確認失敗** — `pytest tests/service/test_config.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 6: 實作** — `manim_skill/service/config.py`:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ServiceConfig:
    redis_url: str
    llm_base_url: str
    llm_model: str
    llm_concurrency: int
    render_concurrency: int
    work_dir: Path
    job_ttl_seconds: int
    web_quota: int


def load_config() -> ServiceConfig:
    """Build a ServiceConfig from environment variables (all optional;
    conservative defaults suit a single-box deployment)."""
    env = os.environ
    return ServiceConfig(
        redis_url=env.get("MANIM_SKILL_REDIS_URL", "redis://localhost:6379/0"),
        llm_base_url=env.get(
            "MANIM_SKILL_LLM_BASE_URL", "http://localhost:11434/v1"
        ),
        llm_model=env.get("MANIM_SKILL_LLM_MODEL", "qwen3.5-35b"),
        llm_concurrency=int(env.get("MANIM_SKILL_LLM_CONCURRENCY", "4")),
        render_concurrency=int(
            env.get("MANIM_SKILL_RENDER_CONCURRENCY", "3")
        ),
        work_dir=Path(env.get("MANIM_SKILL_WORK_DIR", "service_work")),
        job_ttl_seconds=int(env.get("MANIM_SKILL_JOB_TTL", "3600")),
        web_quota=int(env.get("MANIM_SKILL_WEB_QUOTA", "5")),
    )
```

- [ ] **Step 7: 執行測試確認通過** — `pytest tests/service/test_config.py -v` → expect PASS (2 passed).

- [ ] **Step 8: 執行完整非 docker 套件確認無回歸** — `pytest -m "not docker" -q` → expect 全部 PASS.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml manim_skill/service/__init__.py manim_skill/service/config.py tests/service/__init__.py tests/service/test_config.py
git commit -m "feat: service package scaffold + config"
```

---

## Task 2: ServiceJob 模型

**Files:**
- Create: `manim_skill/service/jobs.py`
- Create: `tests/service/test_jobs.py`

- [ ] **Step 1: 寫失敗測試** — `tests/service/test_jobs.py`:

```python
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
    # status survives as an enum
    assert restored.status == JobStatus.DONE


def test_to_dict_status_is_a_string():
    job = ServiceJob(job_id="abc", type="analyze", status=JobStatus.RUNNING)
    assert job.to_dict()["status"] == "running"
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/service/test_jobs.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 實作** — `manim_skill/service/jobs.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Literal


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class ServiceJob:
    """A service-level job record (analyze or render), JSON-serialized
    into Redis. Distinct from render.jobs.* which are the render
    backend's internal batch/clip/beat jobs."""

    job_id: str
    type: Literal["analyze", "render"]
    status: JobStatus = JobStatus.QUEUED
    progress: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ServiceJob":
        return cls(
            job_id=data["job_id"],
            type=data["type"],
            status=JobStatus(data["status"]),
            progress=data.get("progress"),
            result=data.get("result"),
            error=data.get("error"),
        )
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/service/test_jobs.py -v` → expect PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/service/jobs.py tests/service/test_jobs.py
git commit -m "feat: ServiceJob model (analyze/render job records)"
```

---

## Task 3: JobStore — Redis-backed job 記錄

**Files:**
- Create: `manim_skill/service/job_store.py`
- Create: `tests/service/test_job_store.py`

- [ ] **Step 1: 寫失敗測試** — `tests/service/test_job_store.py`:

```python
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
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/service/test_job_store.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 實作** — `manim_skill/service/job_store.py`:

```python
from __future__ import annotations

import json

from manim_skill.service.jobs import ServiceJob


class JobStore:
    """Redis-backed store of ServiceJob records — each job is one
    JSON-encoded key with a TTL, so abandoned jobs self-expire. `save`
    overwrites, so it doubles as the update path."""

    def __init__(self, redis_conn, ttl_seconds: int = 3600) -> None:
        self._redis = redis_conn
        self._ttl = ttl_seconds

    @staticmethod
    def _key(job_id: str) -> str:
        return f"manim-skill:job:{job_id}"

    def save(self, job: ServiceJob) -> None:
        self._redis.set(
            self._key(job.job_id),
            json.dumps(job.to_dict()),
            ex=self._ttl,
        )

    def get(self, job_id: str) -> ServiceJob | None:
        raw = self._redis.get(self._key(job_id))
        if raw is None:
            return None
        return ServiceJob.from_dict(json.loads(raw))

    def delete(self, job_id: str) -> None:
        self._redis.delete(self._key(job_id))
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/service/test_job_store.py -v` → expect PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/service/job_store.py tests/service/test_job_store.py
git commit -m "feat: Redis-backed JobStore with TTL"
```

---

## Task 4: ThrottledLLMClient — LLM 併發限流

**Files:**
- Create: `manim_skill/service/llm_throttle.py`
- Create: `tests/service/test_llm_throttle.py`

- [ ] **Step 1: 寫失敗測試** — `tests/service/test_llm_throttle.py`:

```python
import fakeredis

from manim_skill.llm.client import FakeLLMClient
from manim_skill.service.llm_throttle import ThrottledLLMClient

_SEM_KEY = "manim-skill:llm-semaphore"


def test_complete_passes_through_to_inner():
    redis_conn = fakeredis.FakeRedis()
    inner = FakeLLMClient(response="hello")
    client = ThrottledLLMClient(inner, redis_conn, limit=4)
    assert client.complete("sys", "usr") == "hello"
    assert inner.calls == [("sys", "usr")]


def test_semaphore_released_after_call():
    redis_conn = fakeredis.FakeRedis()
    client = ThrottledLLMClient(
        FakeLLMClient(response="x"), redis_conn, limit=4
    )
    client.complete("s", "u")
    # the semaphore counter is back to 0 (or absent)
    value = redis_conn.get(_SEM_KEY)
    assert value is None or int(value) == 0


def test_limit_is_at_least_one():
    redis_conn = fakeredis.FakeRedis()
    client = ThrottledLLMClient(
        FakeLLMClient(response="x"), redis_conn, limit=0
    )
    assert client._limit >= 1
    # still works with a degenerate limit
    assert client.complete("s", "u") == "x"
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/service/test_llm_throttle.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 實作** — `manim_skill/service/llm_throttle.py`:

```python
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

from manim_skill.llm.client import LLMClient

_SEMAPHORE_KEY = "manim-skill:llm-semaphore"


@contextmanager
def _redis_semaphore(
    redis_conn, key: str, limit: int, poll: float = 0.1
) -> Iterator[None]:
    """A crude Redis counter-based semaphore: spin until the counter
    can be incremented within `limit`. Good enough for a single-box
    deployment; a worker crash mid-call leaks a slot until the service
    restarts (acceptable for the MVP — noted, not hidden)."""
    while True:
        if redis_conn.incr(key) <= limit:
            break
        redis_conn.decr(key)
        time.sleep(poll)
    try:
        yield
    finally:
        redis_conn.decr(key)


class ThrottledLLMClient:
    """Wraps an LLMClient so that total concurrent `.complete()` calls
    across every worker stay under a cap (the scarce LLM inference
    pool). Implements the LLMClient interface, so it is a drop-in."""

    def __init__(self, inner: LLMClient, redis_conn, limit: int) -> None:
        self._inner = inner
        self._redis = redis_conn
        self._limit = max(1, limit)

    def complete(self, system: str, user: str) -> str:
        with _redis_semaphore(self._redis, _SEMAPHORE_KEY, self._limit):
            return self._inner.complete(system, user)
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/service/test_llm_throttle.py -v` → expect PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/service/llm_throttle.py tests/service/test_llm_throttle.py
git commit -m "feat: ThrottledLLMClient (Redis semaphore over LLM concurrency)"
```

---

## Task 5: Job Handlers

RQ worker 跑的兩個 handler。它們從 config 自建連線與 client（worker 是獨立 process，不共用 Python 物件），更新 job 狀態，呼叫既有 pipeline。

**Files:**
- Create: `manim_skill/service/handlers.py`
- Create: `tests/service/test_handlers.py`

- [ ] **Step 1: 寫失敗測試** — `tests/service/test_handlers.py`:

```python
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
    # codegen needs 2 LLM calls per concept (initial + re-ask); give garbage
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
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/service/test_handlers.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 實作** — `manim_skill/service/handlers.py`:

```python
from __future__ import annotations

from pathlib import Path

import redis as redis_lib

from manim_skill.llm.analyze import ConceptCandidate, analyze
from manim_skill.llm.catalog import build_component_catalog
from manim_skill.llm.client import OpenAIClient
from manim_skill.llm.codegen import CodegenError, generate_spec
from manim_skill.llm.input_prep import prepare_input
from manim_skill.llm.repair import BeatRepairer
from manim_skill.render.backend import render_batch
from manim_skill.service.config import ServiceConfig, load_config
from manim_skill.service.job_store import JobStore
from manim_skill.service.jobs import JobStatus, ServiceJob
from manim_skill.service.llm_throttle import ThrottledLLMClient
from manim_skill.spec.validate import validate_spec


def _redis_from_config(config: ServiceConfig):
    return redis_lib.from_url(config.redis_url)


def _build_llm_client(config: ServiceConfig, redis_conn):
    return ThrottledLLMClient(
        OpenAIClient(config.llm_base_url, config.llm_model),
        redis_conn,
        config.llm_concurrency,
    )


def _run_job(job_id: str, work) -> None:
    """Shared scaffolding: load the job, mark RUNNING, run `work(job,
    config, redis_conn, client)`, persist DONE/FAILED. A missing job
    record (expired/deleted) is a no-op."""
    config = load_config()
    redis_conn = _redis_from_config(config)
    store = JobStore(redis_conn, config.job_ttl_seconds)
    job = store.get(job_id)
    if job is None:
        return
    job.status = JobStatus.RUNNING
    store.save(job)
    try:
        client = _build_llm_client(config, redis_conn)
        work(job, config, redis_conn, client)
        job.status = JobStatus.DONE
    except Exception as exc:  # noqa: BLE001 - any failure → FAILED job
        job.status = JobStatus.FAILED
        job.error = str(exc)
    store.save(job)


def handle_analyze_job(
    job_id: str, input_path: str, kind: str, guide_prompt: str | None
) -> None:
    def work(job: ServiceJob, config, redis_conn, client) -> None:
        text = prepare_input(Path(input_path).read_bytes(), kind)
        concepts = analyze(client, text, guide_prompt=guide_prompt)
        job.result = {"concepts": [c.model_dump() for c in concepts]}

    _run_job(job_id, work)


def handle_render_job(job_id: str, mode: str, payload) -> None:
    def work(job: ServiceJob, config, redis_conn, client) -> None:
        if mode == "codegen":
            catalog = build_component_catalog()
            specs = []
            for item in payload:
                concept = ConceptCandidate.model_validate(item)
                try:
                    specs.append(generate_spec(client, concept, catalog))
                except CodegenError:
                    continue
            if not specs:
                raise RuntimeError("codegen failed for all concepts")
        else:  # mode == "spec"
            specs = [validate_spec(payload)]

        job_workdir = config.work_dir / job_id
        batch = render_batch(
            specs,
            job_workdir,
            max_workers=config.render_concurrency,
            repairer=BeatRepairer(client),
        )
        if batch.zip_path is None:
            raise RuntimeError("render produced no output")
        job.result = {
            "zip_path": str(batch.zip_path),
            "render_status": batch.status.value,
        }

    _run_job(job_id, work)
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/service/test_handlers.py -v` → expect PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/service/handlers.py tests/service/test_handlers.py
git commit -m "feat: analyze + render job handlers"
```

---

## Task 6: RQ 佇列整合

**Files:**
- Create: `manim_skill/service/queue.py`
- Create: `tests/service/test_queue.py`

- [ ] **Step 1: 寫失敗測試** — `tests/service/test_queue.py`:

```python
from unittest.mock import MagicMock

import fakeredis

from manim_skill.service import queue as queue_mod
from manim_skill.service.handlers import handle_analyze_job, handle_render_job
from manim_skill.service.queue import enqueue_analyze, enqueue_render, get_queue


def test_get_queue_builds_a_queue_on_the_connection():
    redis_conn = fakeredis.FakeRedis()
    q = get_queue(redis_conn)
    assert q.name == "manim-skill"
    assert q.connection is redis_conn


def test_enqueue_analyze_calls_queue_with_handler_and_args():
    fake_queue = MagicMock()
    enqueue_analyze(fake_queue, "j1", "/work/j1/input", "text", "guide")
    fake_queue.enqueue.assert_called_once_with(
        handle_analyze_job, "j1", "/work/j1/input", "text", "guide"
    )


def test_enqueue_render_calls_queue_with_handler_and_args():
    fake_queue = MagicMock()
    payload = [{"concept": "C1"}]
    enqueue_render(fake_queue, "j2", "codegen", payload)
    fake_queue.enqueue.assert_called_once_with(
        handle_render_job, "j2", "codegen", payload
    )
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/service/test_queue.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 實作** — `manim_skill/service/queue.py`:

```python
from __future__ import annotations

from rq import Queue

from manim_skill.service.handlers import handle_analyze_job, handle_render_job

QUEUE_NAME = "manim-skill"


def get_queue(redis_conn, is_async: bool = True) -> Queue:
    """The RQ queue every job goes through. `is_async=False` runs jobs
    inline on enqueue — used by the integration test."""
    return Queue(QUEUE_NAME, connection=redis_conn, is_async=is_async)


def enqueue_analyze(
    queue: Queue,
    job_id: str,
    input_path: str,
    kind: str,
    guide_prompt: str | None,
) -> None:
    queue.enqueue(
        handle_analyze_job, job_id, input_path, kind, guide_prompt
    )


def enqueue_render(queue: Queue, job_id: str, mode: str, payload) -> None:
    queue.enqueue(handle_render_job, job_id, mode, payload)
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/service/test_queue.py -v` → expect PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/service/queue.py tests/service/test_queue.py
git commit -m "feat: RQ queue integration (enqueue analyze/render)"
```

---

## Task 7: FastAPI App

**Files:**
- Create: `manim_skill/service/app.py`
- Create: `tests/service/test_app.py`

- [ ] **Step 1: 寫失敗測試** — `tests/service/test_app.py`:

```python
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
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/service/test_app.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 實作** — `manim_skill/service/app.py`:

```python
from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any, Literal

import redis as redis_lib
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from manim_skill.llm.catalog import build_component_catalog
from manim_skill.service.config import ServiceConfig, load_config
from manim_skill.service.job_store import JobStore
from manim_skill.service.jobs import JobStatus, ServiceJob
from manim_skill.service.queue import enqueue_analyze, enqueue_render, get_queue


class RenderRequest(BaseModel):
    mode: Literal["codegen", "spec"]
    payload: Any


def create_app(
    config: ServiceConfig | None = None, redis_conn=None
) -> FastAPI:
    """FastAPI app factory. uvicorn runs it via `--factory`; tests call
    it directly with a fakeredis connection. Nothing connects to Redis
    at import time."""
    config = config or load_config()
    redis_conn = redis_conn or redis_lib.from_url(config.redis_url)
    store = JobStore(redis_conn, config.job_ttl_seconds)
    queue = get_queue(redis_conn)
    app = FastAPI(title="manim-skill")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/catalog")
    def catalog() -> dict:
        return {"catalog": build_component_catalog()}

    @app.post("/analyze")
    async def analyze_endpoint(
        file: UploadFile = File(...),
        kind: str = Form(...),
        guide_prompt: str | None = Form(None),
    ) -> dict:
        if kind not in ("text", "code", "pdf"):
            raise HTTPException(400, f"invalid kind: {kind!r}")
        job_id = uuid.uuid4().hex
        job_dir = config.work_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        input_path = job_dir / "input"
        input_path.write_bytes(await file.read())
        store.save(ServiceJob(job_id=job_id, type="analyze"))
        enqueue_analyze(queue, job_id, str(input_path), kind, guide_prompt)
        return {"job_id": job_id}

    @app.post("/render")
    def render_endpoint(body: RenderRequest) -> dict:
        if body.mode == "codegen":
            if not isinstance(body.payload, list):
                raise HTTPException(
                    400, "codegen payload must be a list of concepts"
                )
            if len(body.payload) > config.web_quota:
                raise HTTPException(
                    400,
                    f"web quota exceeded: {len(body.payload)} > "
                    f"{config.web_quota}",
                )
        job_id = uuid.uuid4().hex
        store.save(ServiceJob(job_id=job_id, type="render"))
        enqueue_render(queue, job_id, body.mode, body.payload)
        return {"job_id": job_id}

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        job = store.get(job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        return job.to_dict()

    @app.get("/jobs/{job_id}/result")
    def get_result(job_id: str) -> FileResponse:
        job = store.get(job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        if job.status != JobStatus.DONE or not job.result:
            raise HTTPException(409, "job result not ready")
        zip_path = job.result.get("zip_path")
        if not zip_path or not Path(zip_path).exists():
            raise HTTPException(404, "result file missing")
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=f"{job_id}.zip",
        )

    @app.delete("/jobs/{job_id}")
    def delete_job(job_id: str) -> dict:
        job = store.get(job_id)
        if job is not None and job.result:
            zip_path = job.result.get("zip_path")
            if zip_path and Path(zip_path).exists():
                Path(zip_path).unlink()
        store.delete(job_id)
        job_dir = config.work_dir / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        return {"deleted": job_id}

    return app
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/service/test_app.py -v` → expect PASS (12 passed).

- [ ] **Step 5: 執行完整非 docker 套件確認無回歸** — `pytest -m "not docker" -q` → expect 全部 PASS.

- [ ] **Step 6: Commit**

```bash
git add manim_skill/service/app.py tests/service/test_app.py
git commit -m "feat: FastAPI job API (create_app factory)"
```

---

## Task 8: RQ Worker 進入點

**Files:**
- Create: `manim_skill/service/worker.py`
- Create: `tests/service/test_worker.py`

- [ ] **Step 1: 寫失敗測試** — `tests/service/test_worker.py`:

```python
import fakeredis

from manim_skill.service import worker as worker_mod


def test_worker_module_exposes_main():
    assert callable(worker_mod.main)


def test_build_worker_constructs_an_rq_worker():
    # _build_worker wires an RQ Worker onto the manim-skill queue
    # without entering the blocking .work() loop.
    redis_conn = fakeredis.FakeRedis()
    worker = worker_mod._build_worker(redis_conn)
    assert "manim-skill" in worker.queue_names()
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/service/test_worker.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 實作** — `manim_skill/service/worker.py`:

```python
from __future__ import annotations

import redis as redis_lib
from rq import Worker

from manim_skill.service.config import load_config
from manim_skill.service.queue import get_queue


def _build_worker(redis_conn) -> Worker:
    """Build (but do not start) an RQ Worker bound to the manim-skill
    queue — split out so it can be tested without entering .work()."""
    queue = get_queue(redis_conn)
    return Worker([queue], connection=redis_conn)


def main() -> None:
    """Entry point for the `worker` compose service:
    `python -m manim_skill.service.worker`."""
    config = load_config()
    redis_conn = redis_lib.from_url(config.redis_url)
    _build_worker(redis_conn).work()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/service/test_worker.py -v` → expect PASS (2 passed).
  注意：若 `Worker.queue_names()` 在安裝的 RQ 版本上方法名不同，執行 `python -c "import rq, inspect; print([m for m in dir(rq.Worker) if 'queue' in m.lower()])"` 找到對應方法並調整測試斷言（實作的 `_build_worker` 不需改）。

- [ ] **Step 5: Commit**

```bash
git add manim_skill/service/worker.py tests/service/test_worker.py
git commit -m "feat: RQ worker entry point"
```

---

## Task 9: 端到端整合測試（docker）

用 RQ sync 模式（`is_async=False`，enqueue 即 inline 執行 handler）+ fakeredis + 真實 `render_batch`，驗證 API → handler → docker 渲染 → zip 全鏈路。

**Files:**
- Create: `tests/service/test_service_e2e.py`

- [ ] **Step 1: 寫測試** — `tests/service/test_service_e2e.py`:

```python
import time
import zipfile

import fakeredis
import pytest
from fastapi.testclient import TestClient

from manim_skill.service import app as app_mod
from manim_skill.service.app import create_app
from manim_skill.service.config import ServiceConfig
from manim_skill.service.queue import get_queue


def _sync_client(tmp_path, monkeypatch):
    """An app whose queue runs jobs inline (is_async=False), so a POST
    that enqueues a job blocks until the real handler — and the real
    render_batch — finishes."""
    redis_conn = fakeredis.FakeRedis()
    sync_queue = get_queue(redis_conn, is_async=False)
    monkeypatch.setattr(
        app_mod, "get_queue", lambda conn: sync_queue
    )
    config = ServiceConfig(
        redis_url="redis://unused",
        llm_base_url="http://unused",
        llm_model="unused",
        llm_concurrency=4,
        render_concurrency=2,
        work_dir=tmp_path,
        job_ttl_seconds=3600,
        web_quota=5,
    )
    monkeypatch.setenv("MANIM_SKILL_WORK_DIR", str(tmp_path))
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

    # is_async=False → the handler (and the real docker render) already
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
```

- [ ] **Step 2: 執行端到端測試** — `pytest tests/service/test_service_e2e.py -v -m docker`
  Expected: PASS (1 passed)。會跑真實 docker 渲染，較慢，要耐心。
  若 RQ 的 `is_async=False` 與 `fakeredis` 不相容（enqueue 報錯），改用真實 Redis：本機已有 `go-redis` 容器在 6379，把 `_sync_client` 的 `redis_conn` 換成 `redis.from_url("redis://localhost:6379/15")`（用 db 15 避免污染）。回報你採用了哪種方式。

- [ ] **Step 3: 執行完整測試套件** — `pytest -q`
  Expected: 全部 PASS（含所有 docker 測試）。

- [ ] **Step 4: Commit**

```bash
git add tests/service/test_service_e2e.py
git commit -m "test: service backend end-to-end integration test"
```

---

## Self-Review

**1. Spec coverage（對照 Phase 2 設計文件 §4 §5 §8）**

- §4.1 兩種 job 型別（AnalyzeJob / RenderJob，RenderJob 有 `mode`）→ Task 5 `handle_analyze_job` / `handle_render_job`（`mode` ∈ codegen/spec）✓
- §4.3 Job 狀態存 Redis（`job_id → {type,status,progress,result,error}`、`queued→running→done/failed`）→ Task 2 `ServiceJob` + `JobStatus`、Task 3 `JobStore` ✓
- §4.3 配額（`mode=codegen` 概念 > 5 → 400；`mode=spec` 不限）→ Task 7 `render_endpoint` ✓
- §4.3 產出生命週期（DELETE 刪 zip + 狀態 + work dir；TTL 安全網）→ Task 7 `delete_job`、Task 3 `JobStore` 的 `ex=ttl` ✓
- §4.3 失敗不致命（沿用 Phase 1，render job 部分失敗仍產出 zip）→ Task 5 直接用 `render_batch`（Phase 3 既有的優雅失敗）；codegen 全失敗才 raise ✓
- §5 API 端點（/analyze、/render、/jobs/{id}、/jobs/{id}/result、DELETE、/catalog、/health）→ Task 7 ✓
- §5 `mode` 即來源信號、LLM 設定走 env → Task 7（render_endpoint 用 mode 判配額）、Task 1 config + Task 5 handler 從 config 建 client ✓
- §8 Worker（RQ worker、兩個 handler、從 env 建 OpenAIClient）→ Task 8 + Task 5 ✓
- §8 兩個資源池 + 保守併發（RQ worker 數、per-job beat 平行 `render_concurrency` 預設 3、LLM `llm_concurrency` 預設 4）→ Task 1 config + Task 4 `ThrottledLLMClient` + Task 5 傳 `max_workers=config.render_concurrency` ✓
- §8 beat 層維持 in-process → Task 5 直接呼叫 `render_batch`（未改為分散式）✓

**不在本計畫範圍（後續計畫）：** backend_client、CLI remote mode（Plan 7）；Streamlit（Plan 8）；docker-compose、ARM64 打包（Plan 9）。已在範圍界定說明。

**2. Placeholder scan：** 無 TBD/TODO。每個 step 有完整程式碼或精確指令。Task 8 Step 4 對 RQ 版本可能的方法名差異給了具體查證指令；Task 9 Step 2 對 RQ+fakeredis 可能的不相容給了具體 fallback（改用本機 `go-redis` 的 db 15）。`ThrottledLLMClient` 的 semaphore 在 worker 崩潰時會洩漏一個 slot——已在 docstring 明確標註為 MVP 可接受、非隱藏的取捨。

**3. Type consistency：**
- `ServiceConfig` 欄位（`redis_url`/`llm_base_url`/`llm_model`/`llm_concurrency`/`render_concurrency`/`work_dir`/`job_ttl_seconds`/`web_quota`）（Task 1）→ Task 5 handler、Task 7 app、Task 9 e2e 一致使用。
- `JobStatus`（QUEUED/RUNNING/DONE/FAILED）、`ServiceJob`（`job_id`/`type`/`status`/`progress`/`result`/`error` + `to_dict`/`from_dict`）（Task 2）→ Task 3/5/7 一致。
- `JobStore(redis_conn, ttl_seconds)` + `.save`/`.get`/`.delete`（Task 3）→ Task 5/7/e2e 一致。
- `ThrottledLLMClient(inner, redis_conn, limit)` + `.complete`（Task 4）→ Task 5 `_build_llm_client` 一致；實作 `LLMClient` 的 `.complete` 介面（Phase 4 既有 Protocol）。
- `handle_analyze_job(job_id, input_path, kind, guide_prompt)` / `handle_render_job(job_id, mode, payload)`（Task 5）→ Task 6 `enqueue_*` 以相同簽名 enqueue、Task 7 透過 enqueue 間接呼叫、Task 5 測試直接呼叫，全部一致。Task 5 測試 monkeypatch 的對象（`handlers._redis_from_config`、`handlers._build_llm_client`、`handlers.render_batch`）都是 `handlers.py` 的模組層級名稱。
- `get_queue(redis_conn, is_async=True)` / `enqueue_analyze` / `enqueue_render`（Task 6）→ Task 7 `create_app`、Task 8 `_build_worker`、Task 9 e2e 一致。
- `create_app(config=None, redis_conn=None) -> FastAPI`（Task 7）→ Task 9 e2e 一致呼叫；`RenderRequest`（`mode`/`payload`）對應 `/render` body。
- 重用 Phase 1–4：`prepare_input`、`analyze`/`ConceptCandidate`、`build_component_catalog`、`generate_spec`/`CodegenError`、`OpenAIClient`、`BeatRepairer`、`render_batch`、`BatchJob`（`.zip_path`/`.status`）、`validate_spec` — 簽名與既有程式一致。

無不一致。

---

## Execution Handoff

Plan 完成並存於 `docs/superpowers/plans/2026-05-14-plan-6-backend-job-api.md`。兩種執行方式：

**1. Subagent-Driven（推薦，與 Phase 1 各計畫一致）** — 每 task 一個 subagent，task 之間由我審核。相依鏈大致是線性的（jobs → store → handlers → queue → app/worker），平行空間有限：Task 1 先行；Task 2 單獨；Task 3、Task 4 可平行；Task 5、6、7、8 大致循序（7、8 可平行）；Task 9 殿後。

**2. Inline Execution** — 在本對話 session 內逐 task 執行，分批設檢查點審核。

要用哪一種？
