# Plan 9: ARM64 / Airgapped 打包部署 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把整個 manim-skill 系統打包成一個可在 DGX Spark（ARM64、airgapped）上 `docker compose up` 的部署成品——一個通用 docker image、一份 compose 檔、多架構建置與離線打包腳本。

**Architecture:** **一個通用 image** `manim-skill:latest`（`manimcommunity/manim` + ffmpeg + docker CLI + `pip install` 套件全依賴）同時當四種角色：render 容器（worker 逐 beat spawn）、`api`（uvicorn）、`worker`（rq，經掛載的 docker socket spawn render 容器）、`ui`（streamlit）。`docker-compose.yml` 跑 `redis` + `api` + `worker` + `ui`。多架構用 `docker buildx` 交叉建置 ARM64；airgapped 部署用 `docker save`/`load` 搬 image。

**Tech Stack:** Docker、docker compose、docker buildx、bash 腳本、pytest（compose 全鏈路 e2e 測試）。

---

## 背景：已驗證的事實（寫本計畫前查證）

- `manimcommunity/manim:v0.20.1` **有 `arm64` variant** → render image base 直接支援 ARM64，不需改 base。
- `redis:7-alpine` 為多架構官方 image（含 arm64）。
- `docker buildx` 可用，支援 `linux/arm64` 平台。
- 現有 `docker/Dockerfile`（Plan 1–2）：`FROM manimcommunity/manim:v0.20.1` → `apt-get install ffmpeg` → `COPY . /opt/manim-skill` → `pip install --no-cache-dir /opt/manim-skill` → `USER manimuser`。`pip install` 會安裝套件**與其全部 `dependencies`**——現在 `pyproject.toml` 的 `dependencies` 已含 `fastapi`/`uvicorn`/`rq`/`redis`/`python-multipart`/`httpx`/`streamlit`，所以**重建後的 image 已含所有服務依賴**；唯一缺的是 docker CLI（worker 要用它 spawn render 容器）。
- 既有程式可重用：`manim_skill/service/app.py` 的 `create_app`（uvicorn 用 `--factory` 跑）、`manim_skill/service/worker.py` 的 `main`（`python -m manim_skill.service.worker`）、`manim_skill/frontend/app.py`（`streamlit run` 跑）、`manim_skill/render/docker_render.py` 的 `IMAGE = "manim-skill:latest"`（worker spawn 的 render 容器 image 名）。

環境：Windows + Docker Desktop（amd64 開發機），Python 3.13。

## 設計偏差說明（對設計文件 §3）

設計文件 §3 原訂兩個 image（`manim-skill-service` + `manim-skill` render）。實作規劃時發現：`pip install /opt/manim-skill` 會把套件的全部依賴（含 fastapi/streamlit）拉進去，所以「精簡的 service image」其實做不到（除非拆套件依賴，屬 YAGNI），兩個 image 會幾乎一模一樣。因此**改為一個通用 `manim-skill:latest` image**——這是設計文件「方案 A：image 越少越好打包」原則的自然結論，且 airgapped + ARM64 情境下只建一個 image 最省事。其餘架構（compose 跑 api/worker/ui + redis、render 容器逐 beat spawn、host networking 連 LLM）不變。

## 範圍界定

- **包含**：`docker/Dockerfile` 加 docker CLI（成為通用 image）、`docker-compose.yml` + `.env.example`、`scripts/build-images.sh`（buildx 多架構）、`scripts/bundle-for-deploy.sh`（`docker save` 離線打包）、`DEPLOY.md`、compose 全鏈路 e2e 測試。
- **不包含**：在開發機上實際跑 ARM64 image（交叉建置會產出 arm64 image 並可 `docker save`，但執行 arm64 要 QEMU、慢且不穩——功能測試一律在 amd64；ARM64 的驗證止於「建得起來、save 得出來」）。LLM（vLLM/Ollama）本身的部署不在範圍（使用者自行在 Spark host 上跑；compose 經 `host.docker.internal` 連它）。

## 重要：work dir 必須是 Linux 路徑（docker-out-of-docker 共享）

`worker` 在容器內，透過掛載的 docker socket `docker run` 出 render 兄弟容器；render 容器的 `-v {workdir}:/work` 由 **host（或 Docker Desktop VM）的 daemon** 解析，所以 `{workdir}` 必須是「容器內與 host 上同一個路徑」。做法：work dir 用一個 **Linux 路徑**（例 `/var/lib/manim-skill/work`），compose 以 `${MANIM_SKILL_WORK_DIR}:${MANIM_SKILL_WORK_DIR}` same-path bind mount。
- 在 Spark（Linux）：就是真實 host 路徑。
- 在 Windows 開發機的 Docker Desktop：是 Docker VM 內的路徑——同樣兩邊一致，所以 same-path bind mount 與 worker spawn 的 render 容器都在 VM 內正常運作。
- e2e 測試只透過 HTTP 與 API 互動（不碰檔案系統），所以測試程序在 Windows 上跑也沒問題。

## File Structure

```
docker/Dockerfile               修改 — 加裝 docker CLI（成為通用 image）
docker-compose.yml              新增 — redis / api / worker / ui
.env.example                    新增 — 部署設定範本
scripts/build-images.sh         新增 — buildx 多架構建置
scripts/bundle-for-deploy.sh    新增 — docker save 離線打包
DEPLOY.md                       新增 — airgapped 部署說明
tests/test_compose_e2e.py       新增 — compose 全鏈路 e2e（docker）
```

---

## Task 1: 通用 Image — `docker/Dockerfile` 加裝 Docker CLI

修改既有 render image Dockerfile，加裝 docker CLI，使同一個 `manim-skill:latest` 能同時當 render 容器與 api/worker/ui 服務。重建後 image 含 manim + ffmpeg + docker CLI + 套件全依賴。

**Files:**
- Modify: `docker/Dockerfile`

這是基礎建設修改（Dockerfile），無法用 pytest TDD；驗證方式為「重建 + 冒煙檢查 + 一個既有 render 測試」。

- [ ] **Step 1: 修改 `docker/Dockerfile`** — 把現有的 `apt-get install` 行改為同時裝 `docker.io`（debian 的 docker CLI 套件，amd64/arm64 皆有）。把現有檔案：

```dockerfile
FROM manimcommunity/manim:v0.20.1

USER root
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY . /opt/manim-skill
RUN pip install --no-cache-dir /opt/manim-skill
USER manimuser
```

取代為：

```dockerfile
FROM manimcommunity/manim:v0.20.1

# Universal image: the render container the worker spawns per beat AND
# the api / worker / ui compose services all run from this one image.
# ffmpeg = gif conversion + stitch; docker.io = the worker's CLI for
# spawning sibling render containers via the mounted host socket.
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg docker.io \
    && rm -rf /var/lib/apt/lists/*
COPY . /opt/manim-skill
RUN pip install --no-cache-dir /opt/manim-skill
USER manimuser
```

- [ ] **Step 2: 重建 image** — Run: `docker build -t manim-skill:latest -f docker/Dockerfile .`
  Expected: 建置成功（這次的 `pip install` 會一併裝上 fastapi/uvicorn/rq/redis/python-multipart/httpx/streamlit，因為它們都在 `pyproject.toml` 的 `dependencies`）。

- [ ] **Step 3: 冒煙檢查 — 四種角色所需的東西都在 image 內**

```bash
docker run --rm manim-skill:latest python -c "import manim_skill.service.app, manim_skill.service.worker, manim_skill.frontend.app, manim_skill.builder.spec_scene; print('all roles importable')"
docker run --rm manim-skill:latest docker --version
```
Expected: 第一行印 `all roles importable`；第二行印 docker CLI 版本。

- [ ] **Step 4: 確認 render 仍正常（迴歸閘）** — Run: `pytest tests/render/test_docker_render.py::test_render_textbeat_spec_produces_mp4 -v -m docker`
  Expected: PASS。證明重建後的 image 仍能正常渲染。

- [ ] **Step 5: Commit**

```bash
git add docker/Dockerfile
git commit -m "build: universal manim-skill image (add docker CLI)"
```

---

## Task 2: docker-compose.yml + .env.example

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`

Compose 檔無法用 pytest TDD；驗證方式為 `docker compose config` 能以範本 env 正確解析。

- [ ] **Step 1: 建立 `docker-compose.yml`**

```yaml
services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped

  api:
    image: manim-skill:latest
    # run as root: the api writes uploads/results to the shared work
    # volume. The security boundary is the per-beat render containers
    # (still non-root, --network none, read-only, resource-capped).
    user: root
    command: >
      uvicorn manim_skill.service.app:create_app --factory
      --host 0.0.0.0 --port 8000
    ports:
      - "${MANIM_SKILL_API_PORT:-8000}:8000"
    environment:
      MANIM_SKILL_REDIS_URL: redis://redis:6379/0
      MANIM_SKILL_LLM_BASE_URL: ${MANIM_SKILL_LLM_BASE_URL}
      MANIM_SKILL_LLM_MODEL: ${MANIM_SKILL_LLM_MODEL}
      MANIM_SKILL_LLM_CONCURRENCY: ${MANIM_SKILL_LLM_CONCURRENCY:-4}
      MANIM_SKILL_RENDER_CONCURRENCY: ${MANIM_SKILL_RENDER_CONCURRENCY:-3}
      MANIM_SKILL_WEB_QUOTA: ${MANIM_SKILL_WEB_QUOTA:-5}
      MANIM_SKILL_WORK_DIR: ${MANIM_SKILL_WORK_DIR}
    volumes:
      - ${MANIM_SKILL_WORK_DIR}:${MANIM_SKILL_WORK_DIR}
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on:
      - redis
    restart: unless-stopped

  worker:
    image: manim-skill:latest
    # run as root: needs the mounted docker socket to spawn render
    # containers, and writes to the shared work volume.
    user: root
    command: python -m manim_skill.service.worker
    environment:
      MANIM_SKILL_REDIS_URL: redis://redis:6379/0
      MANIM_SKILL_LLM_BASE_URL: ${MANIM_SKILL_LLM_BASE_URL}
      MANIM_SKILL_LLM_MODEL: ${MANIM_SKILL_LLM_MODEL}
      MANIM_SKILL_LLM_CONCURRENCY: ${MANIM_SKILL_LLM_CONCURRENCY:-4}
      MANIM_SKILL_RENDER_CONCURRENCY: ${MANIM_SKILL_RENDER_CONCURRENCY:-3}
      MANIM_SKILL_WORK_DIR: ${MANIM_SKILL_WORK_DIR}
    volumes:
      - ${MANIM_SKILL_WORK_DIR}:${MANIM_SKILL_WORK_DIR}
      - /var/run/docker.sock:/var/run/docker.sock
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on:
      - redis
    restart: unless-stopped

  ui:
    image: manim-skill:latest
    command: >
      streamlit run manim_skill/frontend/app.py
      --server.port 8501 --server.address 0.0.0.0
    ports:
      - "${MANIM_SKILL_UI_PORT:-8501}:8501"
    environment:
      MANIM_SKILL_BACKEND: http://api:8000
    depends_on:
      - api
    restart: unless-stopped
```

- [ ] **Step 2: 建立 `.env.example`**

```
# Where vLLM / Ollama listens on the Spark host (reached from the
# containers via host.docker.internal).
MANIM_SKILL_LLM_BASE_URL=http://host.docker.internal:11434/v1
MANIM_SKILL_LLM_MODEL=qwen3.5-35b

# Shared work/output directory. MUST be a Linux path (a real host path
# on the Spark; a Docker-VM path on a Docker Desktop dev machine) and
# is bind-mounted at the SAME path inside the containers — the worker
# spawns render containers that bind-mount sub-paths of it, resolved by
# the host docker daemon. `mkdir -p` it on the host before `up`.
MANIM_SKILL_WORK_DIR=/var/lib/manim-skill/work

# Conservative concurrency for the single-box deployment (all tunable).
MANIM_SKILL_LLM_CONCURRENCY=4
MANIM_SKILL_RENDER_CONCURRENCY=3
MANIM_SKILL_WEB_QUOTA=5

# Host ports.
MANIM_SKILL_API_PORT=8000
MANIM_SKILL_UI_PORT=8501
```

- [ ] **Step 3: 驗證 compose 檔可解析** — Run: `docker compose --env-file .env.example config`
  Expected: 印出解析後的完整 compose 設定、exit 0（所有 `${...}` 變數都解析成功，YAML 合法）。

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "build: docker-compose for the Phase 2 service stack"
```

---

## Task 3: 建置與打包腳本 + DEPLOY.md

**Files:**
- Create: `scripts/build-images.sh`
- Create: `scripts/bundle-for-deploy.sh`
- Create: `DEPLOY.md`

腳本無法用 pytest TDD；驗證方式為 `bash -n` 語法檢查 + 實際跑 amd64 建置冒煙。

- [ ] **Step 1: 建立 `scripts/build-images.sh`**

```bash
#!/usr/bin/env bash
# Build the manim-skill image for a target platform and fetch redis.
# Usage: scripts/build-images.sh [linux/arm64|linux/amd64]   (default: linux/arm64)
set -euo pipefail
PLATFORM="${1:-linux/arm64}"
cd "$(dirname "$0")/.."

echo "Building manim-skill:latest for ${PLATFORM} ..."
docker buildx build --platform "${PLATFORM}" \
    -t manim-skill:latest -f docker/Dockerfile --load .

echo "Pulling redis:7-alpine for ${PLATFORM} ..."
docker pull --platform "${PLATFORM}" redis:7-alpine

echo "Done — ${PLATFORM} images are in the local docker image store."
```

- [ ] **Step 2: 建立 `scripts/bundle-for-deploy.sh`**

```bash
#!/usr/bin/env bash
# Bundle the images + compose file into a directory for airgapped deploy.
# Run AFTER scripts/build-images.sh has built the target-platform images.
# Usage: scripts/bundle-for-deploy.sh [output-dir]   (default: deploy-bundle)
set -euo pipefail
cd "$(dirname "$0")/.."
OUT_DIR="${1:-deploy-bundle}"
mkdir -p "${OUT_DIR}"

echo "Saving docker images to ${OUT_DIR}/images.tar ..."
docker save manim-skill:latest redis:7-alpine -o "${OUT_DIR}/images.tar"

echo "Copying compose file, env template, and deploy guide ..."
cp docker-compose.yml "${OUT_DIR}/"
cp .env.example "${OUT_DIR}/"
cp DEPLOY.md "${OUT_DIR}/"

echo "Deploy bundle ready in ${OUT_DIR}/"
echo "  images.tar  docker-compose.yml  .env.example  DEPLOY.md"
```

- [ ] **Step 3: 建立 `DEPLOY.md`**

```markdown
# Deploying manim-skill to the DGX Spark (ARM64, airgapped)

The whole system runs as one `docker compose` stack from a single
universal image. vLLM / Ollama run separately on the Spark host; the
stack reaches them via `host.docker.internal`.

## On the build machine (amd64, has internet)

1. `scripts/build-images.sh linux/arm64`
   — cross-builds `manim-skill:latest` and pulls `redis:7-alpine`,
   both for ARM64, into the local image store.
2. `scripts/bundle-for-deploy.sh`
   — produces `deploy-bundle/` containing `images.tar`,
   `docker-compose.yml`, `.env.example`, `DEPLOY.md`.
3. Copy `deploy-bundle/` to the Spark (USB / scp / etc.).

## On the Spark (ARM64, airgapped)

1. `docker load -i images.tar`
2. `cp .env.example .env` and edit `.env`:
   - `MANIM_SKILL_LLM_BASE_URL` — where vLLM / Ollama listens on the host.
   - `MANIM_SKILL_LLM_MODEL` — the served model name.
   - `MANIM_SKILL_WORK_DIR` — an absolute host path for shared work/output.
3. `mkdir -p "$MANIM_SKILL_WORK_DIR"` (the value you set in `.env`).
4. `docker compose up -d`
5. Web UI: `http://<spark>:8501`. Job API: `http://<spark>:8000`.
   Agents using the CLI set `MANIM_SKILL_BACKEND=http://<spark>:8000`.

## Updating

Rebuild + re-bundle on the build machine, copy over, `docker load -i
images.tar`, then `docker compose up -d` (recreates changed services).

## Notes

- The `api` and `worker` services run as root: `api` writes to the
  shared work volume, `worker` needs the mounted docker socket to spawn
  render containers. The security boundary is each per-beat render
  container — those run non-root, `--network none`, read-only rootfs,
  with memory/cpu/pids caps.
- Concurrency (`MANIM_SKILL_LLM_CONCURRENCY` / `_RENDER_CONCURRENCY`)
  starts conservative; raise it in `.env` + `docker compose up -d` once
  the box's load profile is known.
```

- [ ] **Step 4: 標記腳本可執行 + 語法檢查**

```bash
chmod +x scripts/build-images.sh scripts/bundle-for-deploy.sh
bash -n scripts/build-images.sh
bash -n scripts/bundle-for-deploy.sh
```
Expected: `bash -n` 無輸出、exit 0（語法正確）。

- [ ] **Step 5: 跑 amd64 建置冒煙** — Run: `bash scripts/build-images.sh linux/amd64`
  Expected: 成功——buildx 以 amd64 建出 `manim-skill:latest`、`docker pull` 取得 `redis:7-alpine`。這驗證 buildx 指令正確（amd64 可在開發機上實際執行；arm64 同一指令、僅差 `--platform`）。

- [ ] **Step 6: Commit**

```bash
git add scripts/build-images.sh scripts/bundle-for-deploy.sh DEPLOY.md
git commit -m "build: multi-arch build + airgapped bundle scripts + DEPLOY.md"
```

---

## Task 4: Compose 全鏈路 E2E 測試（docker）

用真實 `docker compose` 把 `redis` + `api` + `worker` 起起來，透過 HTTP 提交一個 `mode=spec` 的 render job，驗證 worker（在容器內、經 docker socket）spawn render 兄弟容器、產出 zip、可下載。只透過 HTTP 互動，所以在 Windows 開發機的 Docker Desktop 上也能跑（docker 端全是 Linux-VM 路徑）。

**Files:**
- Create: `tests/test_compose_e2e.py`

- [ ] **Step 1: 寫測試** — `tests/test_compose_e2e.py`:

```python
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
    import os

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
                logs = _compose(["logs", "worker"], env, check=False).stdout
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
```

- [ ] **Step 2: 執行 e2e 測試** — `pytest tests/test_compose_e2e.py -v -m docker`
  Expected: PASS (1 passed)。會起整個 stack 並渲染真實影片，較慢，要耐心（用寬裕的 timeout，數分鐘）。
  - 若 `docker compose up` 因 `${MANIM_SKILL_WORK_DIR}` 的 bind mount source 不存在而失敗：在 `up` 之前先用 `_compose(["run", "--rm", "api", "mkdir", "-p", _WORK_DIR], env)` 建立該目錄，或在測試開頭用 `subprocess` 跑一次性容器 `docker run --rm -v ...` 建立它；回報你採用的方式。
  - 若 worker 無法 spawn render 容器（docker socket 權限 / DooD 路徑問題），抓 `docker compose logs worker` 的確切錯誤，回報 DONE_WITH_CONCERNS 或 BLOCKED——這代表 compose 設定有真正的 bug，正是這個測試要抓的。

- [ ] **Step 3: 執行完整測試套件** — `pytest -q`
  Expected: 全部 PASS（含所有 docker 測試）。

- [ ] **Step 4: Commit**

```bash
git add tests/test_compose_e2e.py
git commit -m "test: full-stack docker compose end-to-end test"
```

---

## Self-Review

**1. Spec coverage（對照 Phase 2 設計文件 §3 拓撲 + §9 打包部署）**

- §3 compose 服務 `api` / `worker` / `ui` + `redis`，皆用同一 image → Task 1（通用 image）+ Task 2（compose 四服務）✓
- §3 `manim-skill` render image 由 worker 逐 beat spawn 兄弟容器 → 沿用既有 `docker_render.py`（`IMAGE = "manim-skill:latest"`）；Task 1 讓 worker image 含 docker CLI、Task 2 給 worker 掛 docker socket ✓
- §3 共享 work/output volume → Task 2 的 same-path bind mount（`${MANIM_SKILL_WORK_DIR}:${MANIM_SKILL_WORK_DIR}`），「重要：work dir 必須是 Linux 路徑」一節說明 DooD 共享原理 ✓
- §3 vLLM/Ollama 在 host、經 host networking 連 → Task 2 的 `extra_hosts: host.docker.internal:host-gateway` + `MANIM_SKILL_LLM_BASE_URL` env ✓
- §3 redis 用官方多架構 image → Task 2 `redis:7-alpine` ✓
- §9 開發/測試在 amd64、部署到 Spark(arm64) → Task 3 `build-images.sh` 吃 platform 參數（預設 arm64、amd64 可在開發機跑）；Task 4 e2e 在 amd64 跑 ✓
- §9 `docker buildx` 交叉建置 arm64 → Task 3 `build-images.sh` ✓
- §9 `docker save` 打成 tarball + 搬上 Spark `docker load` → Task 3 `bundle-for-deploy.sh` + `DEPLOY.md` ✓
- §9 部署產物 = compose 檔 + image tarball + 部署腳本/說明 → Task 3 的 `deploy-bundle/`（images.tar + docker-compose.yml + .env.example + DEPLOY.md）✓
- §9 待查項「manimcommunity/manim 是否有 ARM64 variant」→ 已於「背景」一節查證確認**有**，故 render image base 不需改 ✓
- 設計偏差（兩 image → 一個通用 image）→ 已於「設計偏差說明」一節明確記錄與論證 ✓

**不在範圍：** 在開發機跑 arm64 image、LLM 自身部署——已在範圍界定說明。

**2. Placeholder scan：** 無 TBD/TODO。Task 1–3 是基礎建設任務（Dockerfile / compose / 腳本，無法 pytest TDD），各自以「重建+冒煙」「`docker compose config` 解析」「`bash -n` + amd64 建置冒煙」明確驗證（比照 Plan 1 Task 12、Plan 2 Task 8、Plan 3 Task 6 的先例）。Task 4 Step 2 對 work dir 不存在、worker spawn 失敗兩種情況給了具體處理方向。

**3. Type consistency / 一致性：**
- `manim-skill:latest` 這個 image 名：Task 1 建置它、Task 2 compose 四服務都引用它、Task 3 腳本 build/save 它、既有 `docker_render.py` 的 `IMAGE` 常數也是它——一致。
- compose 服務指令對應既有進入點：`api` → `uvicorn manim_skill.service.app:create_app --factory`（Plan 6 `create_app` 是 factory）；`worker` → `python -m manim_skill.service.worker`（Plan 6 `worker.py` 有 `if __name__ == "__main__": main()`）；`ui` → `streamlit run manim_skill/frontend/app.py`（Plan 8 `app.py` 是頂層 Streamlit 腳本）——一致。
- env 變數名（`MANIM_SKILL_REDIS_URL` / `_LLM_BASE_URL` / `_LLM_MODEL` / `_LLM_CONCURRENCY` / `_RENDER_CONCURRENCY` / `_WEB_QUOTA` / `_WORK_DIR`）與 Plan 6 `service/config.py` 的 `load_config()` 讀取的名稱一致；`ui` 的 `MANIM_SKILL_BACKEND` 與 Plan 8 `frontend/backend.py` 讀取的名稱一致。
- `redis://redis:6379/0` — compose 內 `redis` 服務名即 hostname，Plan 6 的 `JobStore`/`get_queue` 吃 `redis_url`，一致。
- e2e 測試打的端點（`/health`、`POST /render` body `{"mode":"spec","payload":...}`、`GET /jobs/{id}`、`GET /jobs/{id}/result`、`DELETE /jobs/{id}`）與 Plan 6 `app.py` 一致。

無不一致。

---

## Execution Handoff

Plan 完成並存於 `docs/superpowers/plans/2026-05-14-plan-9-packaging-deployment.md`。將以 subagent-driven-development 執行（依使用者既定偏好，不再詢問）。波次：Task 1 → Task 2 循序（compose 依賴 image）；Task 3 與 Task 4 互相獨立、皆依賴 Task 1+2，可平行。
