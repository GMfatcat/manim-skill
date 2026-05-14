# Phase 2：Web 服務與部署 — 設計文件

- 日期：2026-05-14
- 狀態：設計核可，待轉實作規劃
- 銜接：Phase 1（已完成並合併入 `main`）的設計文件 `2026-05-14-manim-concept-animation-service-design.md`

## 1. 目標與背景

Phase 1 已交付本地、單人、可用 `FakeLLMClient` 完整測試的核心 pipeline（spec / 元件庫 / 渲染後端 / LLM 層 / CLI + agent skill）。Phase 2 把它包成**公司內部多人共用的 Web 服務**：Web 前端上傳、使用者審核概念的人工關卡、多人 async 佇列、以及一個可在內部機器上部署的容器化打包。

## 2. 部署情境與限制（決定整體架構重量）

- **部署目標**：一台 **DGX Spark**（ARM64）。整個服務跑在一個 `docker-compose.yml` 裡。
- **LLM 同機**：vLLM / Ollama 跑在同一台 Spark 上，GPU 由 LLM 獨佔。`api` / `worker` 經 host networking 連 localhost 的 LLM。
- **渲染用 CPU**：沿用 Phase 1 的 CPU cairo renderer，渲染容器不碰 GPU。
- **Airgapped**：Spark 不聯網。所有東西（含 Redis）跑在 Docker；部署 = 把預先打包好的 image tarball 搬上去 `docker load` + `docker compose up`。
- **多架構落差**：開發/測試在 **AMD64**（Docker Desktop），Spark 是 **ARM64**。最終部署用 `docker buildx` 交叉建置 ARM64 image。
- **無帳號**：能連到這台機器的人就能用，不做登入。
- **無 Postgres**：不留產出、不存歷史；job 狀態存 Redis，歷史只進會 rotate 的 backend log。

## 3. 系統拓撲（方案 A）

單一 `manim-skill-service` image，在 compose 內以不同啟動指令跑成多個服務。

```
[Streamlit UI] ─http─┐
[manim-skill CLI] ─http─┤
                       ▼
                 [FastAPI api] ──enqueue──> [Redis：佇列 + job 狀態] <──pull── [RQ worker]
                                                                                   │ docker run（兄弟容器）
                                                                                   ▼
                                                                       [manim render 容器]（CPU）
   Spark host：vLLM / Ollama（GPU）← api / worker 經 host networking 連
```

**Compose 服務**：
- `api`、`worker`、`ui` — 皆來自 `manim-skill-service` image（Phase 1 的 `manim_skill` 套件 + FastAPI + RQ + Streamlit），啟動指令不同（`uvicorn` / `rq worker` / `streamlit run`）。
- `redis` — 官方多架構 image，直接 pull，不自建。
- `manim-skill` render image — **不是 compose 服務**；由 `worker` 透過掛載 docker socket 逐 beat spawn 成兄弟容器（沿用 Phase 1 的 spawn-per-beat 模式）。

**Volume**：一個共享 work/output volume（`api` 寫上傳檔、`worker` 讀輸入寫 zip、`api` 提供下載）。Redis 資料可為 ephemeral（job 狀態本就是暫態）。

**要建的 image（ARM64）**：`manim-skill-service`、`manim-skill`（render）。`redis` 直接 pull 多架構官方 image。

## 4. Async Job 生命週期

### 4.1 兩種 job 型別

- **AnalyzeJob** — 輸入（上傳檔案 bytes + kind + 選填 guide prompt）→ 輸出概念清單（每個含 `concept` / `why_suitable` / `storyboard`）。內部呼叫 Phase 4 的 `analyze`。
- **RenderJob** — 帶一個 `mode` 欄位：
  - `mode=codegen`（Web 來源）：收已確認/編輯過的概念清單 → 逐概念 `generate_spec`（codegen）→ `render_batch`（含 `BeatRepairer` repair loop）→ zip。
  - `mode=spec`（Agent 來源）：收一份現成 scene spec → `render_batch` 直接渲染 → zip。
  - 兩種模式共用 `render_batch` 尾段。

### 4.2 人工審核關卡

**人工關卡不是「暫停的後端 job」。** Web 流程是兩個獨立的 job，中間沒有後端狀態：

1. 上傳 → `api` 建 AnalyzeJob → 進 Redis 佇列 → 回 `job_id`。
2. Streamlit 輪詢 → AnalyzeJob done → 拿到概念清單。
3. **【人工關卡】** 概念清單進 Streamlit `session_state`；使用者編輯分鏡 / 勾選 / 改概念文字。
4. 使用者按「開始渲染」→ Streamlit 提交已確認概念 → `api` 檢查配額 → 建 RenderJob(`mode=codegen`)。
5. `worker` 跑 codegen + `render_batch` → 產出 zip。
6. Streamlit 輪詢 → done → 下載 zip → 確認收到 → `DELETE /jobs/{id}`。

Agent 流程只有一個 RenderJob(`mode=spec`)，無關卡。

### 4.3 Job 狀態、配額、產出生命週期

- **狀態存 Redis**：`job_id → {type, status, progress, result_ref, error}`；status：`queued → running → done / failed`。RQ 管佇列，另存一份較豐富的 status doc（含 progress、哪些 clip 失敗）。
- **配額**：`mode` 即來源信號。`mode=codegen` 且已確認概念 > 5 → `api` 回 `400`（「網頁服務每任務最多 5 個概念」）。`mode=spec`（agent，一次一份 spec）不限。
- **產出生命週期**：zip 寫在共享 volume，status doc 指向它。client 確認下載後呼叫 `DELETE /jobs/{id}` 刪 zip + 狀態；另有 TTL 安全網（預設 1 小時）清掉沒被確認刪除的殘留。
- **失敗不致命**：沿用 Phase 1 — 壞 beat 跳過、壞 clip 不中斷 batch；RenderJob 即使部分失敗仍產出 zip，`manifest.json` 記錄每個 clip 狀態。

## 5. 後端 API（FastAPI）

| Method | Path | 用途 |
|--------|------|------|
| `POST` | `/analyze` | 上傳檔案（multipart + kind + 選填 guide_prompt）→ 建 AnalyzeJob → `{job_id}` |
| `POST` | `/render` | 建 RenderJob → `{job_id}`；body 帶 `mode`（`codegen` 帶概念清單 / `spec` 帶 scene spec） |
| `GET` | `/jobs/{id}` | job 狀態 doc；done 的 AnalyzeJob 在回應裡附概念清單 |
| `GET` | `/jobs/{id}/result` | 下載 zip（done 的 RenderJob） |
| `DELETE` | `/jobs/{id}` | client 確認收到 → 刪 zip + 狀態 |
| `GET` | `/catalog` | 元件目錄（與 CLI `catalog` 對等） |
| `GET` | `/health` | compose healthcheck / 維運 |

- **`mode` 同時是來源信號**，不需另外的 source 參數。配額在 `POST /render` 對 `mode=codegen` 生效。
- **LLM 設定走環境變數**：`worker` 從 `MANIM_SKILL_LLM_BASE_URL` / `MANIM_SKILL_LLM_MODEL` 建 `OpenAIClient`；`api` 不碰 LLM（只入列）。

## 6. Streamlit 前端

四個 stage，用 `session_state` 存目前 stage，每次 rerun 畫當前 stage：

1. **`upload`** — 檔案上傳（text/code/pdf）+ kind 選擇 + 選填 guide prompt + 「分析」按鈕。
2. **`reviewing`** — 概念審核畫面（見下）。
3. **`rendering`** — 輪詢 RenderJob，顯示進度。
4. **`done`** — 「下載 zip」按鈕 → 下載後「確認收到」→ `DELETE` → 回到 `upload`。

**概念審核 UX**：
- **全部就地可編輯，沒有獨立的編輯模式** — 每個概念是一張卡片，分鏡描述是可直接改的 textarea，旁邊一個 checkbox 決定要不要這個概念。使用者不一定要改任何東西。
- **「開始渲染」按鈕是唯一的 commit 點**（最後一步）；在它之前的編輯都只改 `session_state`，不送後端。
- **配額即時反映**：底部顯示「已選 N / 5」；選超過 5 → 按鈕 disabled + 提示。
- **「重新分析」連結**回到 `upload`。MVP 不做「手動新增概念」（YAGNI）。

`session_state` 持有：`stage`、`analyze_job_id`、概念清單（含使用者編輯）、`render_job_id`。Streamlit 邏輯盡量薄——只呼叫 backend client + 管 `session_state`。

## 7. CLI Remote Mode

Phase 1 的 `manim-skill render` 是本地 in-process 呼叫 `render_batch`。Phase 2 加上 remote mode：

- 設定 `MANIM_SKILL_BACKEND=http://spark-host:port`（env var）或 `--remote URL` 時 → `render` 變成 HTTP client：`POST /render`(`mode=spec`) → 輪詢 `/jobs/{id}` → 下載 `/jobs/{id}/result` → `DELETE /jobs/{id}`。
- 未設定時 → 維持 Phase 1 的本地 in-process 行為（開發測試用，不需起整個 stack）。
- `validate`、`catalog` 維持純本地（不需後端）。
- **共用 HTTP client 模組** `manim_skill/backend_client.py`（submit / poll / download / delete）— CLI 的 remote render 與 Streamlit 都用它。單一 client、兩個消費者。

## 8. Worker、併發

**Worker**：RQ worker process，兩個 job handler — `handle_analyze_job`、`handle_render_job`。從 env 建 `OpenAIClient`，呼叫既有的 `analyze` / `generate_spec` / `render_batch`。

**兩個資源池 + 併發設定（保守預設、全部 env 可調）**：
- **RQ worker 數**（同時幾個 job）— 預設 2–3。
- **每個 render job 內的 per-beat 平行度** — 沿用 Phase 1 的 `RenderQueue`（in-process ThreadPoolExecutor），預設 3–4。
- **LLM 併發** — 一個 Redis semaphore 包住每次 `client.complete`，跨所有並行的 analyze/codegen 限流；`MANIM_SKILL_LLM_CONCURRENCY` 預設 3–4。
- 保守理由：Spark 單機、渲染 CPU-bound、機器的 GPU 與部分 CPU 還要分給 LLM，保守預設避免 thrash；穩定後再往上調。

**範圍決定 — beat 層平行維持 in-process**：Phase 1 設計文件 §6 原寫「Phase 2 = Redis-backed RenderQueue」，那是在還不知道單機部署時寫的。**單機**情況下 beat 層 in-process thread 已用滿該機器核心，把 beat 變成 RQ job 只對「跨多台機器分散」有意義——他們沒有。因此 YAGNI：只有頂層 job（analyze / render）走 RQ/Redis（async + 多人所需），beat 層不動。

## 9. 打包與部署

- **開發/測試（AMD64）**：Docker Desktop 上 build AMD64 image，本機把整個 compose 跑起來測。
- **部署到 Spark（ARM64）**：
  1. 在 AMD64 開發機上用 `docker buildx`（QEMU 模擬）交叉建置 ARM64 的 `manim-skill-service`、`manim-skill`（render）image。
  2. `docker save` 把 ARM64 image（含 `redis` 多架構官方 image 的 arm64 變體）打成 tarball。
  3. 搬上 Spark → `docker load` → `docker compose up`。
- **部署產物** = `docker-compose.yml` + image tarball + 一支部署腳本。
- **待查項（實作計畫處理）**：`manimcommunity/manim` 是否有官方 ARM64 variant；若無，render image 的 Dockerfile 改為「ARM64 python base + `pip install manim`」。

## 10. 測試策略

- **API**：FastAPI `TestClient` + `fakeredis` + RQ sync 模式，測端點邏輯，不需真 Redis。
- **Worker job handlers**：`FakeLLMClient`（Phase 4 既有）+ monkeypatched `render_batch` / `analyze`，測 `handle_analyze_job` / `handle_render_job` 的邏輯。
- **backend_client**：對 FastAPI `TestClient` 測 submit / poll / download / delete。
- **Streamlit**：邏輯薄（只呼叫 backend_client + 管 `session_state`）；用 `streamlit.testing.AppTest` 做輕量 smoke test。誠實說明：Streamlit UI 不易深測，因此 backend + client 測透、Streamlit 為薄殼。
- **整合**：docker-compose 起整個 stack（api + worker + redis）→ 提交 job → 拿到 zip，標 `docker`。
- **多架構**：一個 `docker buildx` 能產出 ARM64 image 的建置檢查。

## 11. 待定 / 延後項目

- `manimcommunity/manim` 的 ARM64 支援方式（實作計畫第一步確認）。
- 「手動新增概念」前端功能 — YAGNI，延後。
- beat 層分散式佇列 — 單機不需要，若未來多機再說。
- 併發參數的最佳值 — 部署後依實際負載調整（全為 env var）。
- LLM 模型路由（小模型 analyze / 大模型 codegen）— `OpenAIClient` 已 model-agnostic，需要時傳不同 client 即可，非 Phase 2 必要。
