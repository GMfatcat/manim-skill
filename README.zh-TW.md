# manim-skill

*[English](README.md) · [繁體中文](README.zh-TW.md)*

把一個**概念**——一段文字、一段程式碼、或一份 PDF——轉成一支簡短的 **manim 動畫**（mp4 + gif），適合放進簡報或 README。

這是一個內部工具，有兩條共用同一份契約的消費路徑：

- **Web 路徑** — 輸入 → 內部 LLM 分析素材、挑出適合動畫化的部分 → LLM 為每個概念寫一份「scene spec」→ 渲染 → 每個概念一份 mp4 + gif 的 zip。
- **Agent 路徑** — 外部 agent（例如 Claude Code）自己寫 scene spec，透過 `manim-skill` CLI 渲染。這條路徑不涉及 LLM；agent 本身就是智慧來源。

兩條路徑產出與消費的是同一份 **scene spec**（一個驗證過的 JSON 物件），走的是同一套元件庫與同一個 Docker 渲染後端。

## 進度

**Phase 1（本地）已完成** — 完整 pipeline、元件庫、渲染後端、LLM 層、CLI、agent skill。**Phase 2 尚未建置** — 多人 Web 前端、人工審核概念的關卡、Redis-backed 佇列、部署。

## 環境需求

- Python ≥ 3.12
- Docker（渲染在容器內執行）

## 安裝

```bash
pip install -e ".[dev]"
docker build -t manim-skill:latest -f docker/Dockerfile .
```

## 使用方式

### Agent 路徑 — CLI

把 scene spec 寫成一個 JSON 檔，然後：

```bash
manim-skill catalog                          # 列出元件與其參數 schema
manim-skill validate path/to/spec.json       # 只驗證、不渲染
manim-skill render path/to/spec.json --workdir out   # 渲染 → 印出 mp4 / gif / zip 路徑
```

若某個 `raw` beat 渲染失敗，`render` 會印出 traceback——修正 spec 後再渲染一次即可。

### Web 路徑 — LLM pipeline

```python
from manim_skill.llm.client import OpenAIClient
from manim_skill.llm.pipeline import run_pipeline

client = OpenAIClient(base_url="http://your-llm:8000/v1", model="qwen3.5-35b")
batch = run_pipeline(client, source_text, "text", workdir="out")
print(batch.zip_path)
```

`run_pipeline` 接受 `"text"`、`"code"`、`"pdf"` 三種輸入。內部 LLM 透過任何 OpenAI 相容 endpoint（vLLM、Ollama）存取。

## Scene spec

一份 scene spec 是一個 JSON 物件：一個 `title`、一個 `aspect_ratio`、和一串 `beats`。每個 beat 不是一個**元件**（元件名稱 + 符合該元件 schema 的 `params`），就是一個 **`raw` beat**（一段 manim Python 的 `code` 字串，場景即 `self`）。

```json
{
  "title": "Self-Attention",
  "aspect_ratio": "16:9",
  "beats": [
    { "component": "TextBeat", "params": {"text": "Self-Attention", "style": "title"}, "duration": 2.0 },
    { "component": "MatrixOp", "params": {"op": "matmul", "a_label": "Q", "b_label": "Kᵀ", "result_label": "scores"}, "duration": 4.0 },
    { "component": "raw", "code": "c = Circle()\nself.play(Create(c))", "duration": 3.0 }
  ]
}
```

## 元件

元件庫內含 8 個核心元件加一個文字輔助元件。每個元件宣告一份 Pydantic 參數 schema——這份宣告是驗證、LLM prompt 目錄、agent skill 文件三者的單一事實來源。

| 元件 | 用途 |
|------|------|
| `CodeWalkthrough` | 程式碼，含逐行高亮 |
| `NeuralNetDiagram` | 分層節點 + 連線 |
| `AttentionFlow` | token 序列 + 注意力權重 |
| `MatrixOp` | 矩陣相乘 / 轉置 / reshape |
| `PlotEvolution` | 把數值序列畫成折線圖 |
| `PipelineDiagram` | 標籤方塊 + 箭頭 |
| `FormulaBreakdown` | LaTeX 公式 |
| `GeometryAnim` | 基本形狀 + 變換 |
| `TextBeat` | 標題卡 / 字幕 / 條列 |

新增一個元件只需要在 `manim_skill/components/` 放一個檔案——會被自動探索，目錄與 skill 文件也會自動更新。

## 架構

嚴格的單向分層：

```
spec/        scene spec schema（Pydantic）、寬鬆 JSON 解析、驗證
components/  元件庫（自動探索、自帶 schema）
builder/     把一份 spec 轉成 manim Scene
render/      Docker 渲染後端 — 逐 beat 平行渲染 → stitch → gif → zip
llm/         Web 路徑 — model-agnostic client、analyze、codegen、repair loop
cli.py       Agent 路徑 — 在上述各層之上的薄 CLI
```

渲染後端把每個 beat 在各自的沙箱容器內獨立、平行渲染，並對 beat / clip 層級的失敗做優雅處理。LLM 層的 `BeatRepairer` 會把 traceback 回餵給 LLM 來重試失敗的 `raw` beat。完整架構見 `CLAUDE.md`，設計規格與五份實作計畫見 `docs/superpowers/`。

## 開發

```bash
pytest -m "not docker"     # 快速套件，不需 Docker（約 139 個測試）
pytest                     # 完整套件，含 Docker 整合測試（約 153 個測試）
```

整個 `llm/` 層用 `FakeLLMClient` 測試——CI 不需要真實 LLM。標 docker 的測試需要 Docker 運行中且 `manim-skill:latest` image 已建置；改了任何會被渲染碰到的東西後要重建該 image。
