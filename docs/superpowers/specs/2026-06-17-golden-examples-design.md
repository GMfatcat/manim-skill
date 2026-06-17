# 黃金範例 few-shot 機制 — Golden Examples

**日期**：2026-06-17
**狀態**：設計（brainstorming 產出，待實作計畫）
**所屬框架**：Contract-Gated Cascade（`docs/superpowers/specs/2026-06-16-agent-openmodel-cost-cascade-design.md`）的「黃金範例一物兩用」與 roadmap 項目 1。承接已完成的 tier-metrics 量測層。

## 問題與情境

成本階梯框架的核心是讓免費的 L1（本地開源模型）盡量多解決工作。ORCA 實測顯示：小模型在沒有範例時偏好手寫 `raw`（nemotron 全 raw、59%），但**看得到「用元件」的範例就更可能挑元件**。本機制把 copilot 在設計期親手寫的高品質產物存成「黃金範例」，在 codegen 時挑最相關的 1–2 個當 few-shot 注入，用範例釘住「挑元件、照結構」的偏好——比改 prompt 規則更有效，且不需訓練、不需新依賴。

### 決策（來自情境問答）

- **比對方式**：詞彙重疊（lexical keyword overlap）——無依賴、確定性、可測；不走 embedding（避免多一個 endpoint 能力與非確定性）。
- **標籤來源**：手動策展 `tags`——黃金集本就少且由 copilot/人手寫，curated tags 透明可控。
- **向後相容**：機制全程選用（opt-in），預設不啟用即現狀。

### 不在範圍

- service / docker 的 gold 路徑載入（部署議題，預設 None 不影響，延後）。
- embedding / 語意相似度比對。
- 自動產生 tags（本期用手動策展）。
- 自動把失敗模式回流成黃金範例（屬 roadmap 項目 4「契約缺口回流」）。

## §1 黃金範例儲存（`examples/gold/`）

每個範例一個檔 `examples/gold/<name>.json`，採**包裝格式**（SceneSpec schema 無 `tags` 欄位，故不能直接塞進 spec）：

```json
{
  "tags": ["scheduling", "pipeline", "stages"],
  "spec": { "title": "...", "aspect_ratio": "16:9", "beats": [ ... ] }
}
```

- 資料結構 `GoldExample` = `name: str`（檔名去副檔名，供穩定排序與標示）+ `tags: list[str]` + `spec: SceneSpec`。
- `load_gold_examples(dir) -> list[GoldExample]`：glob `*.json` → 解析 → `validate_spec` 驗 `spec` 部分 → 依 `name` 升序回傳。**目錄不存在或無檔 → 回 `[]`**（優雅退化＝現狀，不綁定部署）。壞檔（缺 `tags`/`spec`、spec 驗不過）→ 拋明確錯誤（載入期就抓，不留到 codegen）。
- **種子**：用既有 `tests/realworld-test/out/orca-agent/` 那幾份手寫、100% 乾淨、已主題化的 spec 當初始黃金範例，各配一份手寫 tags：
  - `pipeline-stages`（PipelineDiagram）— tags 如 `["pipeline","stages","flow","sequence","scheduling"]`
  - `results-table`（TableBeat + PlotEvolution）— tags 如 `["table","comparison","results","benchmark","throughput","metrics"]`
  - `system-graph`（GraphBeat）— tags 如 `["architecture","graph","components","nodes","system","dataflow"]`

## §2 選取（`llm/examples.py`，純函式、無依賴）

`select_examples(concept: ConceptCandidate, gold: list[GoldExample], k: int = 2) -> list[GoldExample]`：

1. `concept_text` = `f"{concept.concept} {concept.why_suitable} {concept.storyboard}"`，小寫。
2. `tokens` = concept_text 切出的詞集合（`\w+`、小寫）。
3. 每個範例算 `score` = 「**所有詞都出現在 `tokens` 裡**的 tag 數」（多詞 tag 如 `"pipeline parallelism"` 需每個詞都中）。
4. 保留 `score > 0` 者，依 `(score 降序, name 升序)` 穩定排序，取前 `k`。
5. **全不中 → 回 `[]`**：寧可不注入，也不塞不相關範例（不相關範例會誤導小模型）。

純函式，無 I/O、無模型呼叫，完全確定性。

## §3 注入 codegen

- `generate_spec(client, concept, catalog, *, gold_examples: list[GoldExample] | None = None)` 新增選用關鍵字參數，預設 `None` = 完全現狀、向後相容。
- 流程：當 `gold_examples` 非空 → `selected = select_examples(concept, gold_examples)` → 把 `selected` 併入 `base_user`（讓首次、重試、lint re-ask 三條路徑都看得到）。
- `_build_user_prompt(concept, examples=None)` 擴充：當有 examples，在 concept 區塊**之前**前置一段：
  > `Reference specs for SIMILAR concepts — imitate their structure and component choices, do NOT copy their content:`
  > 接著每個範例：`// <name> (tags: a, b, c)` + 該範例 `spec.model_dump_json(indent=2)`。
- 放 **user prompt**（system 已塞滿 catalog + raw/LaTeX/visual 規則，不動）。
- `selected == []`（無 gold 或全不中）→ user prompt 與現狀完全相同（零差異）。

### 接線範圍

LLM 驅動入口載入 gold dir 並傳入；gold dir 由 `--gold-dir` 提供，預設 `examples/gold`：

- CLI `codegen-concepts`（agent 審核點路徑，主要使用面）。
- `pipeline.generate_specs`（web in-process pipeline）：加 `gold_examples` 參數穿透到 `generate_spec`。
- eval `run_smoke.py`（codegen / regen / full 階段）：載入 gold dir 傳入，方便對真實模型量測效果。

service handlers（docker）的 gold 載入延後（預設 None，不影響）。

## §4 錯誤處理與測試

### 錯誤處理
- `load_gold_examples`：目錄不存在 → `[]`；單檔壞掉（JSON 壞、缺 `tags`/`spec`、`validate_spec` 失敗）→ 拋帶檔名的明確錯誤（fail fast，不讓壞範例污染 codegen）。
- `select_examples`：純函式，空 gold → `[]`；無重疊 → `[]`。
- 注入是純加法：gold 機制任何環節「沒有結果」都退回現狀，不會讓本來能成的 codegen 變差。

### 測試（全 fast-suite、無 docker、無真實模型）
- `select_examples`：重疊計分正確、top-k 截斷、`score` 降序 + `name` 升序穩定排序、多詞 tag 需全中、全不中回 `[]`、空 gold 回 `[]`。
- `load_gold_examples`：正常載入並驗證、目錄不存在回 `[]`、壞檔（缺欄位 / spec 驗不過）拋錯。
- `generate_spec` 帶 `gold_examples`：用 `FakeLLMClient`，斷言選中的範例 `name`/spec 內容出現在它收到的 user prompt（`FakeLLMClient.calls`）；`gold_examples=None` 時 prompt 與現狀一致。
- 種子檔：一個測試載入 `examples/gold/` 確認每個種子都 `load`/`validate` 得過（防種子腐壞，類似 `test_skill_reference_current` 的精神）。

## 對應到 manim-skill

| 概念 | 對應 / 動作 |
|---|---|
| 黃金範例儲存 | **新建** `examples/gold/*.json` + 3 個種子（取自 orca-agent） |
| GoldExample + load + select | **新建** `manim_skill/llm/examples.py`（純函式） |
| 注入點 | `manim_skill/llm/codegen.py`：`generate_spec` + `_build_user_prompt` 加選用 `gold_examples` |
| 接線 | `manim_skill/cli.py`（codegen-concepts，`--gold-dir`）、`manim_skill/llm/pipeline.py`（generate_specs 穿透）、`scripts/eval/run_smoke.py` |
| concept 欄位 | `ConceptCandidate.concept / why_suitable / storyboard`（既有） |

## 後續（不在本期）

- service/docker 的 gold dir 載入（部署時把 `examples/gold` 進 image 或掛載）。
- 對真實模型量測黃金範例的效果：用 tier-metrics（escalation rate / free-tier rate）比較「有/無 gold」的 codegen，驗證 L1 成功率是否提升——這正是上一個增量建好的量測層的用途。
