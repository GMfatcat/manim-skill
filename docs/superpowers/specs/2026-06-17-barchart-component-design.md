# BarChart 元件 — 示範「配額訊號 → 補元件」飛輪

**日期**：2026-06-17
**狀態**：設計（brainstorming 產出，待實作計畫）
**所屬框架**：Contract-Gated Cascade（`docs/superpowers/specs/2026-06-16-agent-openmodel-cost-cascade-design.md`）roadmap 項目 5。承接 tier-metrics（量測）與 golden-examples（few-shot）兩個增量。

## 問題與情境

成本階梯框架的飛輪是：**升級配額被打爆 = 該強化契約的訊號** → 補一個元件 → 該類產物從此沉到免費的 L0/L1。ORCA 實測提供了現成訊號：`gemma-4-31b` 的「端到端效能提升」長條圖反覆失敗（2/4 beat、稀疏凌亂），因為當時**沒有長條圖元件**，模型只能手寫脆弱的 `raw`。本增量補上 `BarChart` 元件，把長條圖從 raw 路徑（脆弱、易進升級佇列）移到 component 路徑（確定性、主題化、安全版面），並用一個黃金範例讓 few-shot 機制把它推給模型——完整走一遍飛輪。

### 決策（來自情境問答）

- **Params 範圍**：`values + labels + title + highlight`——`highlight` 正對應 ORCA「標記勝出那根（36.9×）」的需求。
- 仿最相近的既有元件 `PlotEvolution` 的結構與慣例。
- 用 manim 內建 `BarChart` mobject，不手刻長條。

### 不在範圍

- 橫向長條 / 每根數值標註（YAGNI，超出示範所需）。
- 對真實模型重跑 eval「驗證飛輪」（屬 live-eval，需線上模型；本增量在程式碼層把元件 + 黃金範例就緒，eval 重跑為手動後續）。

## §1 元件本體（`manim_skill/components/bar_chart.py`）

仿 `PlotEvolution`：`@register class BarChart(Component)`，`name = "BarChart"`，`Params = BarChartParams`，實作 `build` / `animate`。檔案放進 `manim_skill/components/`，由 `components/__init__.py` 的 pkgutil 自動探索，零額外接線。

**`BarChartParams(BaseModel)`**：
- `values: list[float]`，`Field(min_length=1)` — 長條高度。
- `labels: list[str] | None = None` — 每根標籤。
- `title: str | None = None`。
- `highlight: int | None = None` — 要強調的長條索引。

**`build(params) -> Mobject`**：用 manim 內建 `BarChart`。
- 一般長條 `THEME.PRIMARY`；當 `highlight` 有值，其餘長條改 `THEME.PRIMARY_SOFT`（淡化）、被選那根維持 `THEME.PRIMARY`（滿強度）——「淡化其餘、強調一根」，語意中性（不誤用 WARN 表示警告）。
- `y_range` 由 values 自動算：`y_max = max(values)`（若全為 0 則退化處理避免 0 範圍），`[0, y_max * 1.1, y_max / 5 or 1]`，避免 step 為 0。
- 軸顏色 `THEME.INK_SOFT`；`bar_names = labels or []`。
- 有 `title` 時用 `body_text(title, size=28)` 置於圖上方（`next_to(chart, UP)`）。
- 全部包進 `VGroup` 回傳。

**`animate(scene, mobject, params)`**：`scene.play(Create(mobject))`（與 `PlotEvolution` 一致）。

## §2 驗證（Pydantic `model_validator`）

`BarChartParams` 用一個 `model_validator(mode="after")` 做跨欄位檢查（schema 本身無法表達）：
- `labels` 非 `None` 且 `len(labels) != len(values)` → `ValueError`（明確訊息）。
- `highlight` 非 `None` 且不在 `range(len(values))` → `ValueError`。

這些在 `validate_spec`（`spec/validate.py` 對每個 beat 的 params 套用該元件的 `Params`）階段就會被擋下，壞 params 不會進到 render。

## §3 catalog / skill docs（drift 測試）

新增元件自動進兩處：LLM prompt 目錄（`llm/catalog.py`，codegen 看得到）與 agent skill 參考文件（`skill_docs.py` → `skill/reference/components.md`）。後者有 drift 測試 `tests/test_skill_reference_current.py`，所以**必須跑 `manim-skill gen-skill-docs` 重新產生 `skill/reference/*.md`**，否則該測試會紅。實作計畫須含此步驟並把產生的檔一起 commit。

元件數會從 18 → 19；README/CLAUDE 的「ships 18 / 內含 18 個元件」與元件表需同步（屬本增量收尾的文件更新，比照前例）。

## §4 測試 + 串起飛輪

### 測試
- `tests/components/test_bar_chart.py`（fast-suite，建構 mobject 不需 docker）：
  - `build` 用合法 params（含 highlight、含 labels）回傳非 `None` Mobject。
  - `labels` 長度與 `values` 不符 → `validate`/`Params` 拋 `ValidationError`。
  - `highlight` 越界 → `ValidationError`。
  - `highlight=None` / `labels=None` 的最小 params 也能 build。
- 一個 `@pytest.mark.docker` 測試：把 1-beat BarChart spec 實際渲染成 mp4（沿用既有 docker 元件測試的手法），確認端到端可渲染。

### 串飛輪
新增黃金範例 `examples/gold/bar-comparison.json`：一份用 `BarChart` 的 `{tags, spec}`，tags 取 `throughput / comparison / benchmark / speedup / performance / bars` 等主題詞，讓 golden-examples 機制能在「比較吞吐/效能」類概念把 BarChart 當 few-shot 推給模型。既有的 `test_seed_gold_examples_are_valid` 會自動涵蓋它的載入/驗證（必要時把斷言放寬為「包含」而非固定集合，或把新檔名加入預期集合）。

這把「補元件（§1–§3）」與「golden-examples（前一增量）」接起來：配額訊號（ORCA 長條圖反覆失敗）→ 補 `BarChart` 元件 + 黃金範例 → 該類 beat 走 component 路徑、沉到免費層。

## 對應到 manim-skill

| 概念 | 對應 / 動作 |
|---|---|
| 元件本體 | **新建** `manim_skill/components/bar_chart.py`（仿 `plot_evolution.py`） |
| 主題色 / 文字 | `components/theme.py`：`THEME.PRIMARY / PRIMARY_SOFT / INK_SOFT`、`body_text` |
| 渲染 | manim 內建 `BarChart` mobject |
| 驗證 | `BarChartParams` 的 `model_validator`；`spec/validate.py` 既有逐 beat 驗證會套用 |
| catalog / skill docs | 自動探索；**跑 `gen-skill-docs`** 過 drift 測試（`tests/test_skill_reference_current.py`） |
| 飛輪連結 | **新建** `examples/gold/bar-comparison.json`（用 golden-examples 機制） |
| 文件 | README（中/英）+ CLAUDE 的元件數 18→19 與元件表同步 |

## 後續（不在本期）

- 對真實 `gemma-4-31b` 重跑 ORCA「端到端效能提升」codegen（BarChart 元件 + 黃金範例就緒後），用 tier-metrics 比較長條圖 beat 是否從 raw（易失敗）轉為 component（成功），量化飛輪效果。
