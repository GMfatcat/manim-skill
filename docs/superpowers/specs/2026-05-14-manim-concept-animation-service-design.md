# manim 概念動畫服務 — 設計文件

- 日期：2026-05-14
- 狀態：設計核可，待轉實作規劃
- 採用方案：方案 3（混合 / 分層 codegen）

## 1. 目標與背景

公司內部工具，把輸入素材中的「概念」轉成 manim 動畫片段，供團隊製作說明素材使用。

主要使用情境（提案團隊）：
- AI 論文新概念拆解（attention、模型架構、訓練動態、擴散過程等）
- 關鍵程式碼片段講解（執行流程、資料結構變化、控制流）

產出最終用途：
- mp4 → 放進 PPT（16:9）
- gif → 嵌入 Gitea README 輔助說明

由此推導的設計前提：
- **不需要旁白/配音**：純視覺輔助，省去 TTS 與字幕對齊。
- **產出是短的、自足的片段**（單一概念約 5–20 秒），不是長影片。
- **一份輸入 → 多個概念片段** 是常態。

## 2. 範圍與階段切分

開發策略：先在本地把元件庫養到一定規模，再進公司部署。

- **Phase 1（本地優先）**：LLM codegen + 元件庫/Builder + 渲染後端 + 產出。這條垂直切片在開發者本機即可完整跑通與測試。元件庫在此階段持續擴充。
- **Phase 2（公司部署）**：Web 前端上傳、使用者審核 UI、多人佇列/併發、後端 Web 框架。等核心穩定後再包上。

關鍵設計性質：**LLM 是「產出 scene spec 的可抽換外層」**。渲染與元件相關的核心元件吃的是 scene spec，不是 LLM —— 因此元件庫、Builder、解析層、渲染、repair loop 全部可在無 LLM 下以 TDD 開發。

## 3. 系統架構

一條 pipeline，兩個入口，共用三個核心資產（元件庫+Builder、渲染後端、產出格式）。

### Web 路徑（Phase 1 的 ②④ + Phase 2 的 ①③ + 共用 ⑤⑥⑦）

```
① 輸入（text / PDF / code 段落 + 選填引導 prompt）        [Phase 2 前端]
② LLM 分析 → 概念清單 + beat 化的分鏡描述                  [Phase 1]
③ 使用者審核 / 討論 / 修改 / 確認                          [Phase 2 UI]
④ LLM codegen → scene spec（路由：元件組合為主，raw 為輔）  [Phase 1]
⑤ 元件庫 + Builder：scene spec → manim Scene               [共用核心]
⑥ 渲染後端：docker manim + repair loop + 佇列              [Phase 1]
⑦ 產出：mp4 + gif，打包成 zip                              [Phase 1]
```

寫 scene spec 的是公司內部 LLM。

### Agent 路徑

Agent 自己的 LLM（如 Claude Code）把元件庫當 skill，直接產出 scene spec，跳過 ①②③，直接進 ⑤⑥⑦。不經過內部 LLM，但共用同一套 scene spec 契約、元件庫、Builder、渲染後端。

## 4. 元件庫與 Scene Spec

### 4.1 Scene Spec 格式

一份 spec = 一個概念片段。內部 LLM 無 tool use，輸出純文字，由系統解析。

```json
{
  "title": "Self-Attention 計算流程",
  "aspect_ratio": "16:9",
  "beats": [
    {
      "component": "MatrixOp",
      "params": { "op": "matmul", "a_label": "Q", "b_label": "Kᵀ", "result_label": "scores" },
      "caption": "Query 與 Key 轉置相乘得到分數",
      "duration": 4,
      "camera": { "action": "focus", "target": "result" }
    },
    {
      "component": "raw",
      "code": "self.play(...)  # 元件庫沒涵蓋時的逃生艙",
      "duration": 3
    }
  ]
}
```

設計決定：
- **scene spec 永遠是唯一契約**。free-form fallback 不是另一條 pipeline，而是一種特殊 beat（`"component": "raw"` + 一段 manim code）。Builder 同時處理元件 beat 與 raw beat。
- **beat 預設循序**：一次畫面上一個 scene unit，beat 之間做轉場。MVP 不做多元件同屏排版。
- **每個元件的參數 schema 是單一事實來源**：一份 schema 同時驅動 (a) 驗證 LLM 輸出、(b) 自動生成餵給 LLM 的元件目錄、(c) agent skill 的 reference 文件。一處定義、三處消費，避免 drift。

### 4.2 初版元件庫（8 核心元件 + 2 機制）

核心元件：
1. **CodeWalkthrough** — 程式碼、逐行高亮、箭頭註解、步進執行。
2. **NeuralNetDiagram** — 分層節點、連線、forward/backward 流動高亮。
3. **AttentionFlow** — token 序列、注意力權重連線/熱圖、query 高亮。
4. **MatrixOp** — 矩陣相乘 / reshape / transpose / 切塊動畫。
5. **PlotEvolution** — 函數圖、曲線演變、梯度下降路徑、loss curve。
6. **PipelineDiagram** — 標籤方塊 + 箭頭、資料流經各階段、方塊高亮。
7. **FormulaBreakdown** — MathTex 公式、逐項高亮/框選、公式 A→B 變換、項目註解。
8. **GeometryAnim** — 點線面、形狀、變換、角度、幾何證明步驟。

輔助/機制：
- **TextBeat / TitleCard** — 標題卡、文字說明、章節分隔、重點條列。
- **raw** — 逃生艙機制（非元件）。元件庫沒涵蓋時 LLM 直接寫 manim code，走 repair loop。

每個元件可獨立渲染與快照測試；Builder 吃手寫 spec 測試。完全不需要 LLM。

### 4.3 運鏡（camera）

運鏡是橫切關注點，設計為 **beat 的可選屬性**，非元件。
- Builder 的 base scene 採 `MovingCameraScene`。
- 每個 beat 可掛一個收斂詞彙的 camera 指令：`focus`（對準某元素）、`zoom`（縮放倍率）、`pan`、`reset`。
- 大部分運鏡由元件自己內建管理；明確的 camera 指令是「強調用」的例外 —— 刻意收斂以避免 LLM 在運鏡上出包。

## 5. LLM Codegen Pipeline

目標：用稀缺的內部 LLM 推論槽，穩定產出可渲染的 scene spec。

### 內部 LLM 環境（限制）

- 模型：Qwen3.5-35B / Gemma4-26B / Nemotron3-Nano，自架 vLLM 或 Ollama。
- **無 tool use / function calling**：純文字進出。
- context window：32k–128k。
- 併發瓶頸：Ollama 約 2–3、vLLM（如 Nemotron3-Nano）約 7–8。LLM 推論槽本身是稀缺資源，與渲染 worker 是兩個各自要排隊的瓶頸。

### ① Analyze 階段（1 次 LLM call）

- 輸入前處理：PDF → 純文字抽取；code 保留原樣 + 語言偵測。
- context 策略：論文若 fit 進 window 就整篇餵；超過則 section-based 抽取（優先 method/結果段落）。
- 輸出：結構化概念清單 `[{概念, 為何適合動畫化, 分鏡描述}]`。
- **分鏡描述寫成「一條條 beat 的散文」**，使下一階段 codegen 只需「翻譯每個散文 beat → spec beat」，被緊約束、可靠度提升。
- 這是中型模型相對擅長的階段（理解 + 規劃，非寫 code）。

### ② Codegen 階段（每個概念 1 次 LLM call）

- **單一 prompt 直出整份 spec**：不做多步規劃，因為每多一步就多吃一個稀缺槽。元件目錄（從 schema 自動生成）放進 system prompt，LLM 逐 beat 選元件或選 `raw`。

### ③ 寬鬆解析 + schema 驗證

- 中型模型常吐壞 JSON → 永不信任原始輸出。流程：抽取 → json5 寬鬆 parse → 用元件 schema 驗證 params。
- parse 或驗證失敗 → 帶錯誤訊息回問一次。

### ④ 渲染 + repair loop

- **元件 beat**：Builder 確定性渲染。元件已預先測過，幾乎不失敗。真失敗 = builder bug，直接報錯，不進 loop。
- **raw beat**：repair loop 只活在這裡。渲染失敗 → 抓 traceback → 帶失敗的 code + 錯誤回餵 LLM → 修 → 重試，上限 N=3。N 次後該 beat 優雅失敗，不拖垮整個片段。

### ⑤ 逐 beat 獨立渲染 + stitch

- 一個壞 beat 不毀整片；可平行渲染，對 render 佇列友善。

### 跨階段設計

- LLM client **model-agnostic**（config 切換）→ 後續可做模型路由：小模型（Nemotron-Nano）做 analyze、大模型（Qwen-35B）做 codegen。
- repair loop 是唯一會「加 call」的地方，且只對 raw beat。

## 6. 渲染後端

### Job 層級

```
batch job（1 份輸入，使用者確認後）
  └─ clip job × N（每個確認的概念一個 = 一份 scene spec）
       └─ beat job × M（fan-out，平行渲染，受 worker 數上限）
       └─ fan-in → stitch（ffmpeg 串接）→ mp4 → 轉 gif（palette 最佳化）
  └─ 全部 clip job 完成 → 打包成單一 zip → 回前端
```

zip 內容：每個概念一個資料夾，放 mp4 + gif，外加 `manifest.json`（列出概念、對應檔名、使用的 scene spec，便於追溯與重生）。

### 核心元件

- **Render worker**：用官方 `manimcommunity/manim` image。MVP 採 **spawn-per-job**（一個 beat 開一個容器，跑完即丟）—— 隔離乾淨、實作簡單；容器啟動開銷相對渲染時間可忽略。長駐 worker pool 留作 Phase 2 最佳化。
- **並發控制**：semaphore 限制同時運行的容器數（CPU 核心數綁定）。
- **RenderQueue 介面**：Phase 1 = 本地 concurrency-limited executor + sqlite/in-memory job store；Phase 2 = Redis-backed（RQ/Celery）+ 正式 DB。介面固定、實作可換。
- **Job 狀態追蹤**：queued → rendering → done/failed，供 Phase 2 Web UI 與 agent 路徑輪詢。

### Docker 作為安全沙箱

`raw` beat 跑的是 LLM 生成的任意程式碼，docker 是安全邊界：
- 容器內無網路、non-root、檔案系統除 output dir 外 read-only。
- 每個容器資源上限（CPU/mem），一個 job 不能餓死其他 job。
- 單 job 渲染 timeout（manim 遇爛 code 會卡死）→ 超時 kill 視為失敗 → 對 raw beat 餵回 repair loop。

### 其他決定

- **MVP 用 CPU cairo renderer**（預設、最穩）；GPU/OpenGL renderer 留作後期最佳化。
- **兩個各自獨立的稀缺資源池**：LLM 推論槽（codegen 層管理）vs 渲染 worker（渲染後端管理），分開排隊、分開限流。
- **beat 級快取**（nice-to-have）：spec hash 相同 → 直接取快取結果，repair loop 重跑時受益。
- 釘死 docker image tag，確保渲染環境與視覺回歸測試穩定。

## 7. Agent Skill 封裝

agent 路徑 = agent 自己的 LLM 產出 scene spec，直接送渲染後端。skill 提供兩樣東西：

### ① 知識（怎麼寫合法的 scene spec）

- `SKILL.md`：指示「要做 manim 動畫 → 照格式寫一份 scene spec → 跑 `manim-skill render`」。
- `reference/components.md`：元件目錄 + 每個元件的參數 schema —— **從元件 schema 自動生成**（4.1 的單一事實來源決定，使這份文件不會 drift）。
- `reference/spec-format.md`：spec 格式 + 範例。

### ② 介面（提交 + 取回）

- 一支 **CLI**：`manim-skill render <spec.json>`、`manim-skill catalog`、`manim-skill validate <spec.json>`。
- CLI 是渲染後端的薄 client —— Phase 1 連本地後端，Phase 2 連公司部署的後端。
- 採 CLI 而非 MCP：最通用、任何 agent 環境皆可用、實作最簡單。

核心性質：**agent skill 與 Web 路徑共用完全相同的 scene spec 契約、元件庫、渲染後端。** skill 不是另一套 codebase，而是「spec 契約 + 一支 CLI」加上為 LLM 消費而寫的文件。raw .py 不另立特例，包成「一個 raw beat 的 spec」即可，永遠單一契約。

## 8. 測試策略（TDD）

測試金字塔建立在「LLM 是可抽換外層、核心可在無 LLM 下測試」的性質上。

### 無需 LLM（主體，純 TDD）

1. **元件測試** — 8 個元件各自獨立渲染；視覺回歸（render 到已知 frame 與 golden reference 比對）+ 參數 schema 驗證測試。
2. **Builder 測試** — 手寫 scene spec → builder → 斷言產出合法 Scene、beat 順序、camera 指令、raw beat 處理正確。
3. **解析層測試** — 餵故意壞掉的 JSON（壞引號、trailing comma、markdown fence、夾雜散文）→ 斷言寬鬆 parser 能救回或乾淨失敗。此層需以大量擬真垃圾輸入猛打。
4. **渲染後端測試** — 佇列、fan-out/in、stitch、zip 打包、timeout、docker 沙箱。docker 整合測試（真容器）+ 邊界 mock 的快速單元測試並存。
5. **Repair loop 測試** — 壞 raw beat + 假 LLM（回傳修好版）→ 斷言會重試收斂；不可修的 → 斷言 N 次後優雅失敗。

### 需要 LLM（薄外層）

6. **Analyze / Codegen** — 無法 deterministic。策略：
   - CI 用**錄製 fixture 的 mock LLM**（錄一次真實回應、重播，快又穩）。
   - 另備小型 **live eval suite**，手動偶爾跑：真論文/真 code 餵真 LLM，量「spec 驗證通過率」「渲染成功率」當品質指標（非 pass/fail）。此指標也是判斷元件庫是否「養到一定規模」的量尺。
   - LLM 層的契約是「產出能通過驗證的 spec」→ 即使輸出有變異，「能否 parse + validate」永遠 deterministic 可檢查。

### 注意事項

- 視覺回歸跨 manim 版本/平台會 flaky → 釘死 docker image tag；比對採 tolerance，或盡量比結構性質（mobject 位置/數量）而非逐像素。
- 架構天然適合 subagent 開發：8 個元件是孤立單元，builder/解析層/渲染後端各自可分離，每個單元有清楚契約，可由一個 subagent 連測試端到端擁有。

## 9. Tech Stack 與 Repo 結構

- **Phase 1 全部純 Python**：元件庫、builder、解析層、渲染後端、CLI、LLM client。
- **Phase 2** 才加：後端 Web 框架（建議 FastAPI）、前端（框架待 Phase 2 brainstorm）。

Repo 大致結構：

```
components/    8 個核心元件 + TextBeat
builder/       scene spec → manim Scene；raw beat 處理；camera
spec/          scene spec schema、寬鬆解析、驗證
render/        渲染後端：佇列、docker worker、stitch、zip、快取
llm/           analyze + codegen + model-agnostic client + repair loop
cli/           manim-skill CLI
skill/         SKILL.md + 自動生成的 reference
tests/         對應上述各模組
```

## 10. 待定 / 延後項目

- 本地開發用哪個模型（受開發者本機 GPU 限制；LLM client 設計為 model-agnostic，此為 config 問題）。
- Phase 2 前端框架選型（待 Phase 2 brainstorm）。
- beat 級快取為 nice-to-have，非 MVP 必要。
- GPU/OpenGL renderer 為後期效能最佳化，非 MVP。
- 長駐 worker pool 為 Phase 2 最佳化。
