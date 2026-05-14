# Plan 3: 渲染後端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「一份輸入（多個 scene spec）」端到端渲染成「一個 zip（每概念 mp4 + gif + manifest.json）」——逐 beat 獨立平行渲染、stitch、轉 gif、打包，含 beat 級快取與 docker 沙箱強化。

**Architecture:** job 階層 batch → clip → beat。每個 beat 渲染成獨立的「1-beat spec」（重用 Plan 1 的 `render_spec_to_mp4`），由一個 concurrency-limited 的 `RenderQueue`（Phase 1 = `ThreadPoolExecutor`）平行執行；同一 clip 的 beat mp4 用 ffmpeg concat 串接成 clip mp4，再轉 gif；所有 clip 打包成一個 zip + manifest。一個壞 beat 被跳過（clip 仍 stitch 成功的 beat），一個壞 clip 不中斷 batch。

**Tech Stack:** Python ≥3.12、`concurrent.futures.ThreadPoolExecutor`、Docker（manim + ffmpeg image）、Pydantic v2、stdlib `zipfile`/`hashlib`、pytest。

---

## 背景：Plan 1 + Plan 2 已完成的部分

已存在且測試通過（`main` 分支，76 測試）：
- `manim_skill/spec/schema.py` — `SceneSpec`、`Beat`、`CameraDirective`（Pydantic v2）。`SceneSpec` 有 `title: str`、`aspect_ratio`（預設 `"16:9"`）、`beats: list[Beat]`（`min_length=1`）。
- `manim_skill/render/docker_render.py` — `render_spec_to_mp4(spec, workdir) -> Path` 在 docker 內把一份 spec 渲染成 mp4；`_find_output_mp4`；`RenderError(RuntimeError)`；`IMAGE = "manim-skill:latest"`；`RENDER_TIMEOUT_SECONDS = 300`。`subprocess.run` 已加 `encoding="utf-8", errors="replace"`（Windows cp950）。
- `manim_skill/render/convert.py` — `mp4_to_gif(mp4_path) -> Path`。
- `manim_skill/builder/spec_scene.py` — `SpecScene` 把一份 spec 的所有 beat 循序渲染在「一個」場景裡（每個 beat 結束會 fade out）。
- `docker/Dockerfile` — `manim-skill:latest`（`manimcommunity/manim:v0.20.1` + ffmpeg + 本套件，預設使用者 `manimuser`，即已是 non-root）。
- 8 個元件 + TextBeat 已註冊。
- 測試以 `tests/<subpkg>/` 組織，`tests/render/__init__.py` 已存在。`docker` pytest marker 已註冊。

環境：Windows、Docker Desktop、manim 0.20.1、Python 3.13。

## 範圍界定（Phase 1 本地版）

本計畫實作設計文件 §6 的「Phase 1 本地」渲染後端：
- **包含：** batch/clip/beat job 模型與狀態、concurrency-limited 的本地 `RenderQueue`（`ThreadPoolExecutor`）、逐 beat 平行渲染、ffmpeg stitch、zip + manifest 打包、beat 級快取、docker 沙箱強化（資源上限 + read-only fs）。
- **不包含（屬 Phase 2）：** Redis-backed queue、正式 DB、Web 框架、ID-keyed job store 與非同步輪詢。Phase 1 的 `render_batch` 是同步呼叫，回傳一個已完成的 `BatchJob`；job 狀態直接掛在 job 物件上，呼叫端直接檢視，不需要獨立的 store。

## 重要：manim/ffmpeg 與測試策略

- 大部分新模組（jobs / queue / cache / bundle）是純 Python，本地單元測試，**不需 docker**。
- `stitch.py`、`docker_render.py` 強化、端到端 orchestration 需要 docker → 對應測試標 `@pytest.mark.docker`。
- `backend.py` 的 orchestration 邏輯用 `monkeypatch` 把碰 docker 的函式（`render_spec_to_mp4`、`stitch_mp4s`、`mp4_to_gif`）換成假函式來做**確定性單元測試**；真正的 docker 端到端由最後一個 task 驗證。
- 所有碰 docker 的 `subprocess.run` 一律加 `encoding="utf-8", errors="replace"`（Windows cp950，沿用 Plan 1 慣例）。

## File Structure

```
manim_skill/render/
  docker_render.py     修改 — 加沙箱強化 flag（資源上限 + read-only fs）
  convert.py           不變
  jobs.py              新增 — JobStatus / BeatJob / ClipJob / BatchJob（dataclass）
  queue.py             新增 — RenderQueue（concurrency-limited executor）
  cache.py             新增 — beat_cache_key / BeatCache
  stitch.py            新增 — stitch_mp4s（ffmpeg concat）
  bundle.py            新增 — BundleEntry / bundle_clips（zip + manifest.json）
  backend.py           新增 — render_batch（batch 端到端 orchestration）
tests/render/
  test_jobs.py             新增
  test_queue.py            新增
  test_cache.py            新增
  test_stitch.py           新增
  test_bundle.py           新增
  test_docker_render.py    修改 — 加沙箱強化驗證測試
  test_backend.py          新增 — monkeypatch 的 orchestration 單元測試
  test_backend_e2e.py      新增 — docker 端到端整合測試
```

job 模型用 `@dataclass`（內部可變執行期狀態，非外部輸入；與 spec 的 Pydantic 模型用途不同）。

---

## Task 1: Job 模型

batch → clip → beat 三層 job 模型 + 狀態列舉。純資料，無 docker。

**Files:**
- Create: `manim_skill/render/jobs.py`
- Create: `tests/render/test_jobs.py`

- [ ] **Step 1: 寫失敗測試** — `tests/render/test_jobs.py`:

```python
from manim_skill.render.jobs import BatchJob, BeatJob, ClipJob, JobStatus
from manim_skill.spec.schema import Beat, SceneSpec


def test_job_status_values():
    assert JobStatus.QUEUED.value == "queued"
    assert JobStatus.RENDERING.value == "rendering"
    assert JobStatus.DONE.value == "done"
    assert JobStatus.FAILED.value == "failed"


def test_beat_job_defaults():
    beat = Beat(component="raw", code="self.wait(1)")
    job = BeatJob(beat=beat)
    assert job.status == JobStatus.QUEUED
    assert job.mp4_path is None
    assert job.error is None


def test_clip_job_defaults():
    spec = SceneSpec(title="C", beats=[Beat(component="raw", code="pass")])
    job = ClipJob(concept="C", spec=spec)
    assert job.status == JobStatus.QUEUED
    assert job.beat_jobs == []
    assert job.mp4_path is None
    assert job.gif_path is None
    assert job.error is None


def test_batch_job_defaults():
    spec = SceneSpec(title="C", beats=[Beat(component="raw", code="pass")])
    clip = ClipJob(concept="C", spec=spec)
    batch = BatchJob(clip_jobs=[clip])
    assert batch.status == JobStatus.QUEUED
    assert batch.zip_path is None
    assert batch.clip_jobs == [clip]


def test_job_status_is_mutable_on_jobs():
    beat = Beat(component="raw", code="pass")
    job = BeatJob(beat=beat)
    job.status = JobStatus.DONE
    assert job.status == JobStatus.DONE
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/render/test_jobs.py -v` → expect FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 實作** — `manim_skill/render/jobs.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from manim_skill.spec.schema import Beat, SceneSpec


class JobStatus(str, Enum):
    QUEUED = "queued"
    RENDERING = "rendering"
    DONE = "done"
    FAILED = "failed"


@dataclass
class BeatJob:
    beat: Beat
    status: JobStatus = JobStatus.QUEUED
    mp4_path: Path | None = None
    error: str | None = None


@dataclass
class ClipJob:
    concept: str
    spec: SceneSpec
    beat_jobs: list[BeatJob] = field(default_factory=list)
    status: JobStatus = JobStatus.QUEUED
    mp4_path: Path | None = None
    gif_path: Path | None = None
    error: str | None = None


@dataclass
class BatchJob:
    clip_jobs: list[ClipJob]
    status: JobStatus = JobStatus.QUEUED
    zip_path: Path | None = None
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/render/test_jobs.py -v` → expect PASS（5 passed）。

- [ ] **Step 5: Commit**

```bash
git add manim_skill/render/jobs.py tests/render/test_jobs.py
git commit -m "feat: render job models (BatchJob/ClipJob/BeatJob, JobStatus)"
```

---

## Task 2: RenderQueue

concurrency-limited 的本地 executor。純 Python，無 docker。

**Files:**
- Create: `manim_skill/render/queue.py`
- Create: `tests/render/test_queue.py`

- [ ] **Step 1: 寫失敗測試** — `tests/render/test_queue.py`:

```python
import threading
import time

from manim_skill.render.queue import RenderQueue


def test_run_all_returns_results_in_input_order():
    queue = RenderQueue(max_workers=3)
    assert queue.run_all(lambda x: x * 2, [1, 2, 3, 4]) == [2, 4, 6, 8]


def test_run_all_empty_items():
    queue = RenderQueue(max_workers=3)
    assert queue.run_all(lambda x: x, []) == []


def test_run_all_respects_max_workers():
    queue = RenderQueue(max_workers=2)
    lock = threading.Lock()
    state = {"current": 0, "peak": 0}

    def work(_):
        with lock:
            state["current"] += 1
            state["peak"] = max(state["peak"], state["current"])
        time.sleep(0.05)
        with lock:
            state["current"] -= 1
        return None

    queue.run_all(work, list(range(8)))
    assert state["peak"] <= 2


def test_default_max_workers_is_positive():
    assert RenderQueue().max_workers >= 1
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/render/test_queue.py -v` → expect FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 實作** — `manim_skill/render/queue.py`:

```python
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeVar

_T = TypeVar("_T")
_R = TypeVar("_R")

DEFAULT_MAX_WORKERS = 3


class RenderQueue:
    """Concurrency-limited executor for render jobs.

    Phase 1 is a local ThreadPoolExecutor; this class is the interface
    seam where a Phase 2 Redis-backed queue would slot in. Render jobs
    block on `subprocess.run` (docker), so a thread pool is the right
    tool — the OS schedules the containers, the pool caps concurrency.
    """

    def __init__(self, max_workers: int = DEFAULT_MAX_WORKERS) -> None:
        self.max_workers = max(1, max_workers)

    def run_all(
        self, fn: Callable[[_T], _R], items: list[_T]
    ) -> list[_R]:
        """Run `fn` over `items` with at most `max_workers` in flight.

        Results are returned in input order. `fn` is expected not to
        raise — callers wrap per-item failure handling inside `fn`.
        """
        if not items:
            return []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            return list(executor.map(fn, items))
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/render/test_queue.py -v` → expect PASS（4 passed）。

- [ ] **Step 5: Commit**

```bash
git add manim_skill/render/queue.py tests/render/test_queue.py
git commit -m "feat: RenderQueue concurrency-limited executor"
```

---

## Task 3: Beat 級快取

把一個 beat 的內容雜湊成穩定 key，已渲染的 beat mp4 可重用。純 Python，無 docker。

**Files:**
- Create: `manim_skill/render/cache.py`
- Create: `tests/render/test_cache.py`

- [ ] **Step 1: 寫失敗測試** — `tests/render/test_cache.py`:

```python
from manim_skill.render.cache import BeatCache, beat_cache_key
from manim_skill.spec.schema import Beat


def test_cache_key_is_stable_for_same_content():
    beat_a = Beat(component="raw", code="self.wait(1)")
    beat_b = Beat(component="raw", code="self.wait(1)")
    assert beat_cache_key(beat_a) == beat_cache_key(beat_b)


def test_cache_key_differs_for_different_content():
    beat_a = Beat(component="raw", code="self.wait(1)")
    beat_b = Beat(component="raw", code="self.wait(2)")
    assert beat_cache_key(beat_a) != beat_cache_key(beat_b)


def test_get_returns_none_when_absent(tmp_path):
    cache = BeatCache(tmp_path / "cache")
    beat = Beat(component="raw", code="pass")
    assert cache.get(beat) is None


def test_put_then_get_roundtrips(tmp_path):
    cache = BeatCache(tmp_path / "cache")
    beat = Beat(component="raw", code="pass")
    source = tmp_path / "source.mp4"
    source.write_bytes(b"\x00\x00video-bytes")

    stored = cache.put(beat, source)
    assert stored.exists()

    retrieved = cache.get(beat)
    assert retrieved is not None
    assert retrieved.read_bytes() == b"\x00\x00video-bytes"


def test_cache_dir_is_created(tmp_path):
    target = tmp_path / "nested" / "cache"
    BeatCache(target)
    assert target.is_dir()
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/render/test_cache.py -v` → expect FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 實作** — `manim_skill/render/cache.py`:

```python
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from manim_skill.spec.schema import Beat


def beat_cache_key(beat: Beat) -> str:
    """A stable content hash of a beat.

    `model_dump(mode="json")` plus `sort_keys=True` makes the hash
    independent of dict key insertion order, so two beats with the
    same content always map to the same key.
    """
    payload = json.dumps(beat.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class BeatCache:
    """Filesystem cache of rendered beat mp4s, keyed by beat content."""

    def __init__(self, cache_dir) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, beat: Beat) -> Path:
        return self.cache_dir / f"{beat_cache_key(beat)}.mp4"

    def get(self, beat: Beat) -> Path | None:
        path = self._path_for(beat)
        return path if path.exists() else None

    def put(self, beat: Beat, mp4_path) -> Path:
        dest = self._path_for(beat)
        shutil.copy2(mp4_path, dest)
        return dest
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/render/test_cache.py -v` → expect PASS（5 passed）。

- [ ] **Step 5: Commit**

```bash
git add manim_skill/render/cache.py tests/render/test_cache.py
git commit -m "feat: beat-level render cache"
```

---

## Task 4: Stitch — ffmpeg concat

把同一個 clip 的多個 beat mp4 用 ffmpeg concat demuxer 串接成一支 clip mp4，在 docker image 內執行。

**Files:**
- Create: `manim_skill/render/stitch.py`
- Create: `tests/render/test_stitch.py`

- [ ] **Step 1: 寫失敗測試** — `tests/render/test_stitch.py`:

```python
import pytest

from manim_skill.render.docker_render import RenderError, render_spec_to_mp4
from manim_skill.render.stitch import stitch_mp4s
from manim_skill.spec.schema import Beat, SceneSpec


def test_stitch_empty_list_raises():
    with pytest.raises(RenderError):
        stitch_mp4s([], "out.mp4")


@pytest.mark.docker
def test_stitch_two_beat_mp4s(tmp_path):
    # Render two single-beat specs, copy both mp4s into one workdir,
    # then stitch them into a clip mp4.
    import shutil

    workdir = tmp_path / "clip"
    workdir.mkdir()
    beat_mp4s = []
    for i, code in enumerate(["self.wait(1)", "self.wait(1)"]):
        spec = SceneSpec(
            title="T", beats=[Beat(component="raw", code=code)]
        )
        rendered = render_spec_to_mp4(spec, tmp_path / f"beat_{i}")
        dest = workdir / f"beat_{i:02d}.mp4"
        shutil.copy2(rendered, dest)
        beat_mp4s.append(dest)

    clip_mp4 = stitch_mp4s(beat_mp4s, workdir / "clip.mp4")
    assert clip_mp4.exists()
    assert clip_mp4.stat().st_size > 0


@pytest.mark.docker
def test_stitch_single_mp4(tmp_path):
    import shutil

    workdir = tmp_path / "clip"
    workdir.mkdir()
    spec = SceneSpec(
        title="T", beats=[Beat(component="raw", code="self.wait(1)")]
    )
    rendered = render_spec_to_mp4(spec, tmp_path / "beat")
    dest = workdir / "beat_00.mp4"
    shutil.copy2(rendered, dest)

    clip_mp4 = stitch_mp4s([dest], workdir / "clip.mp4")
    assert clip_mp4.exists()
    assert clip_mp4.stat().st_size > 0
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/render/test_stitch.py -v` → expect FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 實作** — `manim_skill/render/stitch.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

from manim_skill.render.docker_render import IMAGE, RenderError

STITCH_TIMEOUT_SECONDS = 180


def stitch_mp4s(mp4_paths, output_path) -> Path:
    """Concatenate mp4s into one mp4 via ffmpeg's concat demuxer.

    Constraint: every input mp4 must already live in the same
    directory as `output_path` — that directory is bind-mounted into
    the container as /work and the concat list references inputs by
    bare filename. The orchestrator (backend.render_batch) copies beat
    mp4s into the clip directory before calling this.

    `-c copy` works because manim renders every beat with identical
    settings, so the streams are concat-compatible.
    """
    mp4_paths = [Path(p) for p in mp4_paths]
    if not mp4_paths:
        raise RenderError("stitch: no input mp4s")

    output_path = Path(output_path).resolve()
    workdir = output_path.parent
    list_file = workdir / "concat_list.txt"
    list_file.write_text(
        "".join(f"file '{p.name}'\n" for p in mp4_paths),
        encoding="utf-8",
    )

    cmd = [
        "docker", "run", "--rm", "--network", "none",
        "-v", f"{workdir}:/work", "-w", "/work",
        IMAGE,
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", "concat_list.txt",
        "-c", "copy",
        output_path.name,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=STITCH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RenderError("stitch timed out") from exc

    if result.returncode != 0:
        raise RenderError(f"ffmpeg concat failed:\n{result.stderr}")
    if not output_path.exists():
        raise RenderError("stitch produced no output file")
    return output_path
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/render/test_stitch.py -v` → expect PASS（3 passed；docker 測試較慢，要耐心）。

- [ ] **Step 5: Commit**

```bash
git add manim_skill/render/stitch.py tests/render/test_stitch.py
git commit -m "feat: stitch_mp4s (ffmpeg concat in docker)"
```

---

## Task 5: Bundle — zip + manifest

把多個 clip 的 mp4 + gif 打包成單一 zip，每個概念一個資料夾，外加 `manifest.json`。純 Python，無 docker。

**Files:**
- Create: `manim_skill/render/bundle.py`
- Create: `tests/render/test_bundle.py`

- [ ] **Step 1: 寫失敗測試** — `tests/render/test_bundle.py`:

```python
import json
import zipfile

from manim_skill.render.bundle import BundleEntry, bundle_clips


def _make_file(path, content=b"data"):
    path.write_bytes(content)
    return path


def test_bundle_creates_zip_with_manifest(tmp_path):
    mp4 = _make_file(tmp_path / "a.mp4")
    gif = _make_file(tmp_path / "a.gif")
    entries = [
        BundleEntry(concept="Concept A", mp4_path=mp4, gif_path=gif, status="done")
    ]
    zip_path = bundle_clips(entries, tmp_path / "out" / "bundle.zip")

    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert "manifest.json" in names
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["concepts"][0]["concept"] == "Concept A"
    assert manifest["concepts"][0]["status"] == "done"
    assert len(manifest["concepts"][0]["files"]) == 2


def test_bundle_puts_each_concept_in_its_own_folder(tmp_path):
    mp4_a = _make_file(tmp_path / "a.mp4")
    mp4_b = _make_file(tmp_path / "b.mp4")
    entries = [
        BundleEntry(concept="First", mp4_path=mp4_a, gif_path=None, status="done"),
        BundleEntry(concept="Second", mp4_path=mp4_b, gif_path=None, status="done"),
    ]
    zip_path = bundle_clips(entries, tmp_path / "bundle.zip")

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    folders = {n.split("/")[0] for n in names if "/" in n}
    assert len(folders) == 2  # one folder per concept


def test_bundle_handles_failed_clip_with_no_files(tmp_path):
    entries = [
        BundleEntry(concept="Broken", mp4_path=None, gif_path=None, status="failed")
    ]
    zip_path = bundle_clips(entries, tmp_path / "bundle.zip")

    with zipfile.ZipFile(zip_path) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["concepts"][0]["status"] == "failed"
    assert manifest["concepts"][0]["files"] == []


def test_bundle_creates_missing_output_dir(tmp_path):
    mp4 = _make_file(tmp_path / "a.mp4")
    entries = [BundleEntry(concept="A", mp4_path=mp4, gif_path=None, status="done")]
    zip_path = bundle_clips(entries, tmp_path / "deep" / "nested" / "b.zip")
    assert zip_path.exists()
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/render/test_bundle.py -v` → expect FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 實作** — `manim_skill/render/bundle.py`:

```python
from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BundleEntry:
    concept: str
    mp4_path: Path | None
    gif_path: Path | None
    status: str


def _safe_name(name: str) -> str:
    cleaned = "".join(
        c if (c.isalnum() or c in "-_") else "_" for c in name
    )
    return cleaned[:40] or "concept"


def bundle_clips(entries: list[BundleEntry], output_zip) -> Path:
    """Bundle per-concept mp4 + gif into one zip with a manifest.json.

    Each concept gets its own folder (`NN_<safe-name>/`). Missing or
    failed-clip files are simply omitted; the manifest records the
    status and which files made it in.
    """
    output_zip = Path(output_zip).resolve()
    output_zip.parent.mkdir(parents=True, exist_ok=True)

    manifest: dict = {"concepts": []}
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for index, entry in enumerate(entries):
            folder = f"{index:02d}_{_safe_name(entry.concept)}"
            record: dict = {
                "concept": entry.concept,
                "status": entry.status,
                "files": [],
            }
            for path in (entry.mp4_path, entry.gif_path):
                if path is not None and Path(path).exists():
                    arcname = f"{folder}/{Path(path).name}"
                    zf.write(path, arcname)
                    record["files"].append(arcname)
            manifest["concepts"].append(record)
        zf.writestr(
            "manifest.json",
            json.dumps(manifest, indent=2, ensure_ascii=False),
        )

    return output_zip
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/render/test_bundle.py -v` → expect PASS（4 passed）。

- [ ] **Step 5: Commit**

```bash
git add manim_skill/render/bundle.py tests/render/test_bundle.py
git commit -m "feat: bundle_clips (zip + manifest.json)"
```

---

## Task 6: Docker 沙箱強化

`render_spec_to_mp4` 跑的是可能含 LLM 生成 raw code 的容器；加上資源上限與 read-only 根檔案系統。容器預設已是 non-root（image 的 `manimuser`）且已有 `--network none` + timeout。本任務不寫新的 TDD 紅燈測試（修改既有 `docker run` 旗標屬基礎建設變更）；驗證方式是「既有的 docker 渲染測試在強化後仍全數通過」（迴歸閘）外加一個新的旗標存在性測試。

**Files:**
- Modify: `manim_skill/render/docker_render.py`
- Modify: `tests/render/test_docker_render.py`（新增一個測試）

- [ ] **Step 1: 加沙箱強化旗標到 `docker_render.py`**

在 `manim_skill/render/docker_render.py` 的 `IMAGE` / `RENDER_TIMEOUT_SECONDS` 常數附近，加入三個強化常數：

```python
IMAGE = "manim-skill:latest"
RENDER_TIMEOUT_SECONDS = 300
MEMORY_LIMIT = "2g"
CPU_LIMIT = "2"
PIDS_LIMIT = "256"
```

然後把 `render_spec_to_mp4` 內的 `cmd` 串列取代為以下（加入資源上限、`--read-only`、`--tmpfs /tmp`，以及讓 manim/Python 的快取寫到 tmpfs 的環境變數）：

```python
    cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", MEMORY_LIMIT,
        "--cpus", CPU_LIMIT,
        "--pids-limit", PIDS_LIMIT,
        "--read-only",
        "--tmpfs", "/tmp",
        "-v", f"{workdir}:/work",
        "-e", "MANIM_SKILL_SPEC=/work/spec.json",
        "-e", "HOME=/tmp",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-w", "/work",
        IMAGE,
        "manim", "-ql",
        "--media_dir", "/work/out",
        "--format", "mp4",
        "/work/scene_entry.py", "SpecScene",
    ]
```

`render_spec_to_mp4` 其餘部分（`write_render_inputs`、`out_dir` 建立、`subprocess.run` 的 `encoding`/`timeout`、`_find_output_mp4` 收尾）保持不變。

- [ ] **Step 2: 新增旗標存在性測試到 `tests/render/test_docker_render.py`**

在 `tests/render/test_docker_render.py` 檔尾新增（這個測試不需 docker，純檢查強化常數已定義且為合理值）：

```python
def test_sandbox_hardening_constants_defined():
    from manim_skill.render import docker_render

    assert docker_render.MEMORY_LIMIT
    assert docker_render.CPU_LIMIT
    assert docker_render.PIDS_LIMIT
```

- [ ] **Step 3: 執行新測試確認通過** — `pytest tests/render/test_docker_render.py::test_sandbox_hardening_constants_defined -v` → expect PASS。

- [ ] **Step 4: 執行既有 docker 渲染測試作為迴歸閘** — `pytest tests/render/test_docker_render.py -v -m docker`
  Expected: PASS（既有的 `test_render_textbeat_spec_produces_mp4`、`test_render_raw_beat_failure_raises_render_error`、加上 `_find_output_mp4` 的兩個非 docker 測試）。這證明沙箱強化（資源上限 + read-only fs + tmpfs）沒有破壞渲染。
  若 `--read-only` 導致 manim 因為某個寫入路徑而失敗，stderr 會顯示是哪個路徑；最小修正是為該路徑多加一個 `--tmpfs <path>` 或對應的環境變數，不要移除整個 `--read-only`。若試過仍無法在合理範圍內解決，回報 DONE_WITH_CONCERNS 並附上 stderr，保留資源上限與 `--network none`。

- [ ] **Step 5: Commit**

```bash
git add manim_skill/render/docker_render.py tests/render/test_docker_render.py
git commit -m "feat: docker sandbox hardening (resource limits, read-only fs)"
```

---

## Task 7: Backend orchestration — render_batch

把前面所有零件接起來：batch → clips → 平行渲染 beats（經快取）→ stitch → gif → 打包 zip。orchestration 邏輯用 monkeypatch 假掉碰 docker 的函式來做確定性單元測試。

**Files:**
- Create: `manim_skill/render/backend.py`
- Create: `tests/render/test_backend.py`

- [ ] **Step 1: 寫失敗測試** — `tests/render/test_backend.py`:

```python
from pathlib import Path

from manim_skill.render import backend as backend_mod
from manim_skill.render.backend import render_batch
from manim_skill.render.docker_render import RenderError
from manim_skill.render.jobs import JobStatus
from manim_skill.spec.schema import Beat, SceneSpec


def _fake_render_spec_to_mp4(spec, workdir):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    mp4 = workdir / "fake.mp4"
    mp4.write_bytes(b"\x00\x00fake-mp4")
    return mp4


def _fake_render_raises(spec, workdir):
    raise RenderError("simulated render failure")


def _fake_stitch_mp4s(mp4_paths, output_path):
    output_path = Path(output_path)
    output_path.write_bytes(b"\x00stitched")
    return output_path


def _fake_mp4_to_gif(mp4_path):
    gif = Path(mp4_path).with_suffix(".gif")
    gif.write_bytes(b"\x00gif")
    return gif


def _patch_docker_fns(monkeypatch, render_fn=_fake_render_spec_to_mp4):
    monkeypatch.setattr(backend_mod, "render_spec_to_mp4", render_fn)
    monkeypatch.setattr(backend_mod, "stitch_mp4s", _fake_stitch_mp4s)
    monkeypatch.setattr(backend_mod, "mp4_to_gif", _fake_mp4_to_gif)


def test_render_batch_happy_path(tmp_path, monkeypatch):
    _patch_docker_fns(monkeypatch)
    specs = [
        SceneSpec(
            title="Concept A",
            beats=[
                Beat(component="raw", code="self.wait(1)"),
                Beat(component="raw", code="self.wait(2)"),
            ],
        ),
        SceneSpec(
            title="Concept B",
            beats=[Beat(component="raw", code="self.wait(1)")],
        ),
    ]
    batch = render_batch(specs, tmp_path)

    assert batch.status == JobStatus.DONE
    assert batch.zip_path is not None and batch.zip_path.exists()
    assert len(batch.clip_jobs) == 2
    for clip in batch.clip_jobs:
        assert clip.status == JobStatus.DONE
        assert clip.mp4_path is not None and clip.gif_path is not None
        assert all(bj.status == JobStatus.DONE for bj in clip.beat_jobs)


def test_render_batch_failed_beat_is_skipped(tmp_path, monkeypatch):
    calls = {"n": 0}

    def flaky_render(spec, workdir):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RenderError("boom")
        return _fake_render_spec_to_mp4(spec, workdir)

    _patch_docker_fns(monkeypatch, render_fn=flaky_render)
    specs = [
        SceneSpec(
            title="C",
            beats=[
                Beat(component="raw", code="bad"),
                Beat(component="raw", code="ok"),
            ],
        )
    ]
    # max_workers=1 makes the call order deterministic.
    batch = render_batch(specs, tmp_path, max_workers=1)

    clip = batch.clip_jobs[0]
    assert clip.status == JobStatus.DONE
    beat_statuses = [bj.status for bj in clip.beat_jobs]
    assert JobStatus.FAILED in beat_statuses
    assert JobStatus.DONE in beat_statuses


def test_render_batch_all_beats_fail_marks_clip_and_batch_failed(
    tmp_path, monkeypatch
):
    _patch_docker_fns(monkeypatch, render_fn=_fake_render_raises)
    specs = [
        SceneSpec(title="C", beats=[Beat(component="raw", code="bad")])
    ]
    batch = render_batch(specs, tmp_path)

    assert batch.clip_jobs[0].status == JobStatus.FAILED
    assert batch.status == JobStatus.FAILED
    # The zip is still produced — it records the failure in the manifest.
    assert batch.zip_path is not None and batch.zip_path.exists()


def test_render_batch_uses_cache_to_skip_rendering(tmp_path, monkeypatch):
    from manim_skill.render.cache import BeatCache

    _patch_docker_fns(monkeypatch)
    cache = BeatCache(tmp_path / "cache")
    spec = SceneSpec(
        title="C", beats=[Beat(component="raw", code="self.wait(1)")]
    )

    # First run populates the cache.
    render_batch([spec], tmp_path / "run1", cache=cache)

    # Second run: swap the renderer to one that always raises. If the
    # cache works, render_spec_to_mp4 is never called and the beat
    # still succeeds from the cached mp4.
    monkeypatch.setattr(backend_mod, "render_spec_to_mp4", _fake_render_raises)
    batch2 = render_batch([spec], tmp_path / "run2", cache=cache)

    assert batch2.clip_jobs[0].status == JobStatus.DONE
    assert batch2.clip_jobs[0].beat_jobs[0].status == JobStatus.DONE
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/render/test_backend.py -v` → expect FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 實作** — `manim_skill/render/backend.py`:

```python
from __future__ import annotations

import functools
import shutil
from pathlib import Path

from manim_skill.render.bundle import BundleEntry, bundle_clips
from manim_skill.render.cache import BeatCache
from manim_skill.render.convert import mp4_to_gif
from manim_skill.render.docker_render import RenderError, render_spec_to_mp4
from manim_skill.render.jobs import BatchJob, BeatJob, ClipJob, JobStatus
from manim_skill.render.queue import RenderQueue
from manim_skill.render.stitch import stitch_mp4s
from manim_skill.spec.schema import SceneSpec


def _render_beat_job(
    indexed_beat: tuple[int, BeatJob],
    *,
    clip: ClipJob,
    clip_dir: Path,
    cache: BeatCache | None,
) -> BeatJob:
    """Render one beat as a standalone 1-beat spec.

    On success the beat mp4 is copied into `clip_dir` as
    `beat_NN.mp4` (stitch requires all inputs in one directory). A
    RenderError is caught and recorded on the BeatJob — a failed beat
    must not stop the rest of the clip or batch.
    """
    index, beat_job = indexed_beat
    beat_job.status = JobStatus.RENDERING
    dest = clip_dir / f"beat_{index:02d}.mp4"

    try:
        if cache is not None:
            cached = cache.get(beat_job.beat)
            if cached is not None:
                shutil.copy2(cached, dest)
                beat_job.mp4_path = dest
                beat_job.status = JobStatus.DONE
                return beat_job

        one_beat_spec = SceneSpec(
            title=clip.spec.title,
            aspect_ratio=clip.spec.aspect_ratio,
            beats=[beat_job.beat],
        )
        rendered = render_spec_to_mp4(
            one_beat_spec, clip_dir / f"beat_{index:02d}_work"
        )
        shutil.copy2(rendered, dest)
        beat_job.mp4_path = dest
        beat_job.status = JobStatus.DONE
        if cache is not None:
            cache.put(beat_job.beat, dest)
    except RenderError as exc:
        beat_job.status = JobStatus.FAILED
        beat_job.error = str(exc)

    return beat_job


def render_batch(
    specs: list[SceneSpec],
    workdir,
    *,
    max_workers: int = 3,
    cache: BeatCache | None = None,
) -> BatchJob:
    """Render a batch of scene specs into one zip bundle.

    Each spec is a clip; each beat is rendered independently (as a
    1-beat spec) in parallel up to `max_workers`; a clip's beat mp4s
    are stitched into a clip mp4 then converted to gif; all clips are
    bundled into one zip with a manifest. A failed beat is skipped
    (the clip still stitches the beats that succeeded); a failed clip
    does not stop the batch.
    """
    workdir = Path(workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    queue = RenderQueue(max_workers=max_workers)

    clip_jobs = [
        ClipJob(
            concept=spec.title,
            spec=spec,
            beat_jobs=[BeatJob(beat=beat) for beat in spec.beats],
        )
        for spec in specs
    ]
    batch = BatchJob(clip_jobs=clip_jobs, status=JobStatus.RENDERING)

    for clip_index, clip in enumerate(clip_jobs):
        clip.status = JobStatus.RENDERING
        clip_dir = workdir / f"clip_{clip_index:02d}"
        clip_dir.mkdir(parents=True, exist_ok=True)

        worker = functools.partial(
            _render_beat_job, clip=clip, clip_dir=clip_dir, cache=cache
        )
        queue.run_all(worker, list(enumerate(clip.beat_jobs)))

        rendered = [
            bj.mp4_path
            for bj in clip.beat_jobs
            if bj.status == JobStatus.DONE and bj.mp4_path is not None
        ]
        if not rendered:
            clip.status = JobStatus.FAILED
            clip.error = "all beats failed to render"
            continue

        try:
            clip.mp4_path = stitch_mp4s(rendered, clip_dir / "clip.mp4")
            clip.gif_path = mp4_to_gif(clip.mp4_path)
            clip.status = JobStatus.DONE
        except RenderError as exc:
            clip.status = JobStatus.FAILED
            clip.error = str(exc)

    entries = [
        BundleEntry(
            concept=clip.concept,
            mp4_path=clip.mp4_path,
            gif_path=clip.gif_path,
            status=clip.status.value,
        )
        for clip in clip_jobs
    ]
    batch.zip_path = bundle_clips(entries, workdir / "output.zip")
    batch.status = (
        JobStatus.DONE
        if any(clip.status == JobStatus.DONE for clip in clip_jobs)
        else JobStatus.FAILED
    )
    return batch
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/render/test_backend.py -v` → expect PASS（4 passed）。

- [ ] **Step 5: 執行完整非 docker 套件確認無回歸** — `pytest -m "not docker" -q` → expect 全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add manim_skill/render/backend.py tests/render/test_backend.py
git commit -m "feat: render_batch backend orchestration"
```

---

## Task 8: 端到端 docker 整合測試

用真實 docker 跑完整的渲染後端：多個 scene spec → 平行渲染 → stitch → gif → zip。

**Files:**
- Create: `tests/render/test_backend_e2e.py`

- [ ] **Step 1: 寫測試** — `tests/render/test_backend_e2e.py`:

```python
import json
import zipfile

import pytest

from manim_skill.render.backend import render_batch
from manim_skill.render.cache import BeatCache
from manim_skill.render.jobs import JobStatus
from manim_skill.spec.schema import Beat, SceneSpec


@pytest.mark.docker
def test_render_batch_end_to_end_produces_zip(tmp_path):
    specs = [
        SceneSpec(
            title="Concept A",
            beats=[
                Beat(component="TextBeat", params={"text": "Hello"}, duration=1.0),
                Beat(component="raw", code="self.wait(1)", duration=0.5),
            ],
        ),
        SceneSpec(
            title="Concept B",
            beats=[
                Beat(
                    component="CodeWalkthrough",
                    params={"code": "x = 1", "language": "python"},
                    duration=1.0,
                )
            ],
        ),
    ]
    batch = render_batch(specs, tmp_path, max_workers=2)

    assert batch.status == JobStatus.DONE
    assert batch.zip_path is not None and batch.zip_path.exists()
    assert all(clip.status == JobStatus.DONE for clip in batch.clip_jobs)

    with zipfile.ZipFile(batch.zip_path) as zf:
        names = zf.namelist()
        manifest = json.loads(zf.read("manifest.json"))
    # one folder per concept, each with an mp4 and a gif
    assert sum(n.endswith(".mp4") for n in names) == 2
    assert sum(n.endswith(".gif") for n in names) == 2
    assert len(manifest["concepts"]) == 2
    assert all(c["status"] == "done" for c in manifest["concepts"])


@pytest.mark.docker
def test_render_batch_failed_beat_does_not_break_clip(tmp_path):
    # A clip with one broken raw beat and one good beat — the clip
    # should still finish from the good beat.
    specs = [
        SceneSpec(
            title="Partial",
            beats=[
                Beat(component="raw", code="this is not valid python !!!"),
                Beat(component="raw", code="self.wait(1)", duration=0.5),
            ],
        )
    ]
    batch = render_batch(specs, tmp_path, max_workers=2)

    clip = batch.clip_jobs[0]
    assert clip.status == JobStatus.DONE
    assert clip.mp4_path is not None and clip.mp4_path.exists()
    beat_statuses = [bj.status for bj in clip.beat_jobs]
    assert JobStatus.FAILED in beat_statuses
    assert JobStatus.DONE in beat_statuses


@pytest.mark.docker
def test_render_batch_cache_speeds_up_rerun(tmp_path):
    # With a shared cache, rendering the same spec twice should succeed
    # both times and the second run's beat mp4 should come from cache.
    cache = BeatCache(tmp_path / "cache")
    spec = SceneSpec(
        title="Cached",
        beats=[Beat(component="raw", code="self.wait(1)", duration=0.5)],
    )

    batch1 = render_batch([spec], tmp_path / "run1", cache=cache)
    assert batch1.status == JobStatus.DONE

    batch2 = render_batch([spec], tmp_path / "run2", cache=cache)
    assert batch2.status == JobStatus.DONE
    # the cache file for the beat now exists
    assert cache.get(spec.beats[0]) is not None
```

- [ ] **Step 2: 執行端到端測試** — `pytest tests/render/test_backend_e2e.py -v -m docker`
  Expected: PASS（3 passed）。這些會渲染多支真實影片，較慢，要耐心。

- [ ] **Step 3: 執行完整測試套件** — `pytest -q`
  Expected: 全部 PASS（含所有 docker 測試）。

- [ ] **Step 4: Commit**

```bash
git add tests/render/test_backend_e2e.py
git commit -m "test: render backend end-to-end docker integration tests"
```

---

## Self-Review

**1. Spec coverage（對照設計文件 §6 渲染後端）**

- batch → clip → beat job 階層 → Task 1（`jobs.py`）+ Task 7（`render_batch` 建立階層）✓
- Job 狀態追蹤 queued→rendering→done/failed → Task 1（`JobStatus`）+ Task 7（狀態轉移）✓
- 逐 beat 獨立渲染（spawn-per-job）→ Task 7（`_render_beat_job` 把每個 beat 渲染成 1-beat spec，重用 Plan 1 的 `render_spec_to_mp4`，每次一個容器）✓
- 平行渲染 + 並發控制（semaphore）→ Task 2（`RenderQueue` 的 `max_workers` = `ThreadPoolExecutor` 上限）+ Task 7 ✓
- RenderQueue 介面（Phase 1 本地 executor，Phase 2 可換 Redis）→ Task 2（class 即介面接縫，docstring 註明）✓
- fan-in → stitch（ffmpeg 串接）→ Task 4（`stitch_mp4s`）+ Task 7 ✓
- mp4 + gif 產出 → Task 7 重用 Plan 1 的 `mp4_to_gif` ✓
- 全部 clip 完成 → 打包單一 zip + manifest.json，每概念一資料夾 → Task 5（`bundle_clips`）+ Task 7 ✓
- 一個壞 beat 不毀整片 → Task 7（`_render_beat_job` 捕捉 `RenderError`，stitch 只用成功的 beat）+ Task 8 docker 驗證 ✓
- 一個壞 clip 不中斷 batch → Task 7（clip 失敗 `continue`，batch 仍打包）✓
- beat 級快取（spec hash）→ Task 3（`BeatCache` / `beat_cache_key`）+ Task 7 整合 ✓
- Docker 沙箱強化（non-root 已是預設、資源上限、read-only fs、timeout 已有、--network none 已有）→ Task 6 ✓
- 兩個獨立稀缺資源池 → 本計畫管渲染 worker pool（`RenderQueue`）；LLM pool 屬 Plan 4 ✓
- MVP CPU cairo renderer → 已是 manim 預設，無需變更 ✓

**明確不在範圍（Phase 2 / 後續計畫）：** Redis-backed queue、正式 DB、ID-keyed job store 與非同步輪詢、Web 框架（皆 Phase 2）；LLM analyze/codegen/repair loop（Plan 4）；CLI/agent skill（Plan 5）。已在「範圍界定」一節說明。

**2. Placeholder scan：** 無 TBD/TODO。每個 step 都有完整程式碼或精確指令。Task 6 是「修改既有 docker 旗標」型基礎建設任務，已明確說明它不寫新紅燈測試的原因，並以「既有 docker 測試作為迴歸閘 + 一個新的常數存在性測試」驗證（比照 Plan 1 Task 12 Dockerfile 的先例）；Task 6 Step 4 對 `--read-only` 可能的失敗給了具體的最小修正方向（多加 `--tmpfs`），非佔位。

**3. Type consistency：**
- `JobStatus`、`BeatJob`、`ClipJob`、`BatchJob`（Task 1）的欄位名（`status`、`mp4_path`、`gif_path`、`error`、`beat_jobs`、`clip_jobs`、`zip_path`、`concept`、`spec`、`beat`）在 Task 7 的 `render_batch`/`_render_beat_job` 與 Task 8 測試中一致使用。
- `RenderQueue(max_workers=...)` 與 `.run_all(fn, items)`（Task 2）→ Task 7 `RenderQueue(max_workers=max_workers)` + `queue.run_all(worker, ...)` 一致。
- `BeatCache(cache_dir)`、`.get(beat) -> Path | None`、`.put(beat, mp4_path) -> Path`、`beat_cache_key(beat)`（Task 3）→ Task 7 與 Task 8 一致使用。
- `stitch_mp4s(mp4_paths, output_path) -> Path`（Task 4）→ Task 7 `stitch_mp4s(rendered, clip_dir / "clip.mp4")` 一致。
- `BundleEntry(concept, mp4_path, gif_path, status)` 與 `bundle_clips(entries, output_zip) -> Path`（Task 5）→ Task 7 一致建構與呼叫。
- `IMAGE`、`RenderError`、`render_spec_to_mp4`（Plan 1 既有）+ Task 6 新增的 `MEMORY_LIMIT`/`CPU_LIMIT`/`PIDS_LIMIT` — Task 4 import `IMAGE`/`RenderError`，Task 7 import `RenderError`/`render_spec_to_mp4`，名稱一致。
- `mp4_to_gif`（Plan 1 既有，`convert.py`）→ Task 7 import 並呼叫，簽名一致。
- Task 7 的 monkeypatch 對象（`backend_mod.render_spec_to_mp4`、`backend_mod.stitch_mp4s`、`backend_mod.mp4_to_gif`）對應 `backend.py` 頂層 import 的同名模組層級名稱，可被正確替換。

無不一致。

---

## Execution Handoff

Plan 完成並存於 `docs/superpowers/plans/2026-05-14-plan-3-render-backend.md`。兩種執行方式：

**1. Subagent-Driven（推薦，與 Plan 1/2 一致）** — 每 task 一個 subagent，task 之間由我審核。Task 1/2/3 互相獨立（純 Python，不同檔案），可平行（一波 ≤3）；Task 4/5/6 互相獨立（不同檔案，stitch/hardening 含 docker 測試），可平行；Task 7、Task 8 各自單獨執行（皆有依賴）。

**2. Inline Execution** — 在本對話 session 內逐 task 執行，分批設檢查點審核。

要用哪一種？
