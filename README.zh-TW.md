# manim-skill

*[English](README.md) · [繁體中文](README.zh-TW.md)*

把一個**概念**——一段文字、一段程式碼、或一份 PDF——轉成一支簡短的 **manim 動畫**（mp4 + gif），適合放進簡報或 README。

這是一個內部工具，有兩條共用同一份契約的消費路徑：

- **Web 路徑** — 在 Streamlit 介面上傳素材 → 內部 LLM 分析、提出概念 → 使用者審核並編輯 → 渲染 → 下載每個概念一份 mp4 + gif 的 zip。
- **Agent 路徑** — 外部 agent（例如 Claude Code）自己寫「scene spec」，透過 `manim-skill` CLI 渲染。這條路徑不涉及 LLM；agent 本身就是智慧來源。

兩條路徑產出與消費的是同一份 **scene spec**（一個驗證過的 JSON 物件），走的是同一套元件庫與同一個 Docker 渲染後端。

## 進度

已完成——本地核心 pipeline（Phase 1）與可部署的多人 Web 服務（Phase 2）都做完了：scene-spec pipeline、元件庫、渲染後端、LLM 層、CLI + agent skill、FastAPI job API + RQ workers、Streamlit 前端、以及 ARM64 / airgapped 的 docker-compose 打包。

## 環境需求

- Python ≥ 3.12
- Docker（渲染在容器內執行；部署的服務以 docker-compose stack 運行）

## 安裝（本地開發）

```bash
pip install -e ".[dev]"
docker build -t manim-skill:latest -f docker/Dockerfile .
```

## 使用方式

### 部署的服務 — Streamlit 介面 + job API

整個系統以一個 `docker compose` stack 運行：`redis`、一個 FastAPI job API、一個 RQ worker、一個 Streamlit 介面。

```bash
cp .env.example .env      # 編輯：LLM endpoint、work dir、併發數…
docker compose up -d
```

- Web 介面：`http://<host>:8501` — 上傳 → 審核/編輯概念 → 渲染 → 下載。
- Job API：`http://<host>:8000`。

要部署到 DGX Spark 的 airgapped ARM64 環境（交叉建置、`docker save` 打包、搬移、`docker load`），見 **[DEPLOY.md](DEPLOY.md)**。

### Agent 路徑 — CLI

把 scene spec 寫成一個 JSON 檔，然後：

```bash
manim-skill catalog                                # 列出元件與其 schema
manim-skill validate path/to/spec.json             # 只驗證、不渲染
manim-skill render path/to/spec.json --workdir out                  # 本地渲染
manim-skill render path/to/spec.json --remote http://<host>:8000    # 透過部署的後端渲染
```

`--remote`（或 `MANIM_SKILL_BACKEND` 環境變數）會把 spec 提交給部署的服務並輪詢結果，而非在本機 in-process 渲染。若某個 `raw` beat 渲染失敗，`render` 會印出 traceback——修正 spec 後再渲染一次。

### 在 Python 裡跑 Web pipeline

`manim_skill.llm.run_pipeline` 直接跑「輸入 → analyze → codegen → render」，適合腳本化：

```python
from manim_skill.llm.client import OpenAIClient
from manim_skill.llm.pipeline import run_pipeline

client = OpenAIClient(base_url="http://your-llm:8000/v1", model="qwen3.5-35b")
batch = run_pipeline(client, source_text, "text", workdir="out")
print(batch.zip_path)
```

內部 LLM 透過任何 OpenAI 相容 endpoint（vLLM、Ollama）存取。

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
spec/         scene spec schema（Pydantic）、寬鬆 JSON 解析、驗證
components/   元件庫（自動探索、自帶 schema）
builder/      把一份 spec 轉成 manim Scene
render/       Docker 渲染後端 — 逐 beat 平行渲染 → stitch → gif → zip
llm/          LLM 半邊 — model-agnostic client、analyze、codegen、repair loop、pipeline
service/      FastAPI job API + RQ worker + Redis-backed job store（部署的後端）
frontend/     Streamlit Web 介面
backend_client.py   job API 的 HTTP client — CLI 的 remote mode 與前端共用
cli.py        manim-skill CLI
```

渲染後端把每個 beat 在各自的沙箱容器內獨立、平行渲染，並對 beat / clip 層級的失敗做優雅處理。服務後端把它包成一個非同步的 job API；Streamlit 前端與 CLI 的 remote mode 都是它的薄 client。整個系統以一個通用 Docker image 透過 docker-compose 部署。

完整架構見 `CLAUDE.md`，設計規格與九份實作計畫見 `docs/superpowers/`，部署見 `DEPLOY.md`。

## 開發

```bash
pytest -m "not docker"     # 快速套件，不需 Docker
pytest                     # 完整套件，含 Docker 整合測試
```

整個 `llm/` 層與 `service/` 後端都用假件測試（`FakeLLMClient`、`fakeredis`）——快速套件不需要真實 LLM 或 Redis。標 docker 的測試需要 Docker 運行中且 `manim-skill:latest` image 已建置；改了任何會被渲染碰到的東西後要重建該 image。
```

