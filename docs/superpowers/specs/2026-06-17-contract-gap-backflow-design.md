# 契約缺口回流 — Contract-Gap Backflow

**日期**：2026-06-17
**狀態**：設計（brainstorming 產出，待實作計畫）
**所屬框架**：Contract-Gated Cascade（`docs/superpowers/specs/2026-06-16-agent-openmodel-cost-cascade-design.md`）roadmap 項目 4，最後一塊。承接 tier-metrics（量測升級率）、golden-examples（few-shot）、BarChart（飛輪示範）。

## 問題與情境

框架飛輪：升級配額被打爆 → 強化契約（補元件）→ 該類產物沉到免費層。tier-metrics 已能**偵測**升級率過高（`escalation_quota` / `over_quota`），但「**到底該補什麼元件**」目前要人工翻失敗的 raw beat 去歸納。本增量把這一步自動化：跨多次 render 累積 unresolved（升級）的 raw beat，依共用關鍵字分群，產出一份「待補元件」候選報告。工具**浮現訊號**（哪些主題反覆失敗），agent/人**讀報告命名並建立元件**——與框架其餘部分一致的分工（確定性免費層 + agent 判斷）。

### 決策（來自情境問答）

- **分析方式**：確定性詞彙分群（lexical），不走 LLM。與 tier-metrics / golden-examples 的確定性風格一致；「命名缺的元件」是判斷，交給 agent（L2）。
- **資料來源**：擴充 manifest 記錄每個 unresolved beat 的細節，backflow 掃目錄樹下所有 `output.zip` 彙總（跨 run 累積「反覆」訊號）。

### 不在範圍

- LLM 自動命名/生成候選元件（命名是 agent 的判斷）。
- 自動建立元件（只產報告，建立由 agent 走既有「加一個 `components/` 檔」流程）。
- 嵌入式語意分群（用確定性詞彙，無依賴）。

## §1 在 manifest 留存 unresolved beat 細節

目前 manifest 每個 concept record 只有 `{concept, status, tier_counts, files}`——記了「有幾個 unresolved」但沒記「是哪個 beat、內容是什麼」。本節補上：

- `render/bundle.py` 的 `BundleEntry` 加欄位 `unresolved_beats: list[dict] | None = None`；`bundle_clips` 把它寫進該 concept 的 manifest record（`"unresolved_beats": [...]`，無則省略或空）。
- 每筆 unresolved 記錄：`{"index": int, "component": str, "caption": str | None, "error": str, "code": str}`。`code`、`error` 各截斷到約 500 字（避免 manifest 膨脹）。
- `render/backend.py` 的 `render_batch` 在組 `BundleEntry` 時，從該 clip 中 `tier == TIER_UNRESOLVED` 的 `BeatJob` 收集：`index`、`beat.component`（多為 `"raw"`——正是「本該有個元件」的訊號）、`beat.caption`、`beat_job.error`、`beat.code`。
- 向後相容：無 unresolved beat 時欄位為空列；舊 manifest 無此欄位，backflow 端優雅略過。

## §2 分析模組（`manim_skill/backflow.py`，確定性、無模型）

純資料處理，無 LLM、無 docker。

- `Escalation`（dataclass）：`source: str`（來源 zip 路徑）、`concept: str`、`index: int`、`component: str`、`caption: str | None`、`code: str`、`error: str`。
- `collect_escalations(paths: list[str | Path]) -> list[Escalation]`：對每個 path，若是目錄則 rglob 找所有 `output.zip`，若直接是 zip 就用它；讀各 zip 內的 `manifest.json`，攤平每個 concept 的 `unresolved_beats` 成 `Escalation`。manifest 無 `unresolved_beats` 欄位（舊版）→ 略過該檔，不報錯。讀不開的 zip / 無 manifest → 略過。
- `cluster_escalations(escalations, *, min_count: int = 2) -> list[Cluster]`：依**共用關鍵字**分群。
  - 每筆取 `f"{caption} {code}"` 的詞集合：小寫 `\w+`、長度 ≥ 3、扣掉一組停用詞 `_STOPWORDS`（manim/python 常見噪音：`self play add create wait scene vgroup text color animate import numpy math return self_play run_time` 等 + 常見英文虛詞）。
  - 建 `keyword -> [Escalation, ...]`（含該關鍵字者）。保留 `len(group) >= min_count` 的關鍵字。
  - `Cluster`：`keyword: str`、`count: int`、`samples: list[Escalation]`（最多 N 筆樣本）。依 `(count desc, keyword asc)` 排序回傳。
  - 不做硬分群演算法（脆弱）；改以「反覆出現的關鍵字 → 其失敗樣本群」——穩健、確定性，本質即詞彙分群。
- 停用詞用 DF 直覺挑選的小固定集合（長度 ≥ 3 已濾掉 `a/of/to`）；目標是讓領域詞（`bar` / `chart` / `timeline` / `tree` / `matrix`…）浮上來，不是完備的 NLP 停用詞表。

## §3 CLI `manim-skill backflow`

`manim-skill backflow <paths...> [--min-count N] [-o report.md]`：
- `collect_escalations(paths)` → `cluster_escalations(..., min_count=N)`（預設 2）。
- 產出 markdown **契約缺口報告**：
  - 標頭：總計 K 個 unresolved beat、來自 M 個 run、其中 raw beat 佔比。
  - 「反覆模式（候選元件）」清單：每個關鍵字一列，`**<keyword>** (<count>×)` + 幾個樣本 caption + 來源檔（去重）。
  - 若無達門檻的群：印「no recurring contract gaps found」。
- 印到 stdout；給 `-o` 則寫檔。
- 子命令加進 `cli.py` 的 argparse（`paths` nargs="+"、`--min-count` type=int default 2、`-o/--output`）。

## §4 錯誤處理與測試

### 錯誤處理
- `collect_escalations`：path 不存在 / 非 zip 且無 output.zip → 該 path 貢獻 0 筆（不報錯）；壞 zip / 無 manifest / 舊版無欄位 → 略過。
- `cluster_escalations`：空輸入 → `[]`；全不到 `min_count` → `[]`。
- 純加法、確定性：任何環節「沒資料」都安靜回空，不影響既有 render。

### 測試（全 fast-suite、無 docker、無模型）
- §1：用既有 fake-render 手法（`tests/render/test_backend.py` 的 `_patch_docker_fns` + `_fake_render_raises`）讓一個 raw beat 失敗 → 從 `batch.zip_path` 讀 manifest，斷言該 concept 的 `unresolved_beats` 含其 `code`/`caption`/`error`/`index`。
- §2 `collect_escalations`：手造含 `unresolved_beats` 的 manifest 寫進一個 zip → 讀回；舊 manifest（無欄位）→ 0 筆；壞 zip → 略過。
- §2 `cluster_escalations`：共用關鍵字成群、停用詞被濾、`min_count` 門檻、`(count desc, keyword asc)` 排序、空輸入 → `[]`。
- §3 CLI：對含已知反覆關鍵字的 zip 目錄跑 `backflow`，斷言報告字串含該關鍵字與次數；無資料時印 no-gaps 訊息。

## 對應到 manim-skill

| 概念 | 對應 / 動作 |
|---|---|
| 留存 unresolved 細節 | `render/bundle.py`：`BundleEntry.unresolved_beats` + manifest；`render/backend.py`：`render_batch` 從 `TIER_UNRESOLVED` 的 BeatJob 收集 |
| 分析 | **新建** `manim_skill/backflow.py`（`Escalation` / `collect_escalations` / `cluster_escalations`，純函式） |
| tier 來源 | `render/metrics.py` 的 `TIER_UNRESOLVED`（既有） |
| CLI | `manim_skill/cli.py`：新增 `backflow` 子命令 |
| 測試手法 | `tests/render/test_backend.py` 的 fake-render；`zipfile` 手造 manifest |

## 後續（不在本期）

- 把報告接回 golden-examples / 元件開發：agent 讀 backflow 報告 → 補元件（走既有 BarChart 式流程）→ 新元件 + 黃金範例 → 該類 beat 沉到免費層。這正是飛輪的「強化契約」回手，本增量把「該補什麼」自動浮現出來，閉合整個迴圈。
- 服務端（worker）跑完 render 後自動累積 escalation 到一個中央位置供 backflow 掃（部署議題，預設不影響）。
