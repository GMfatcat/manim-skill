# manim-skill

*[English](README.md) · [繁體中文](README.zh-TW.md)*

Turn a **concept** — a paragraph of text, a code snippet, or a PDF — into a short **manim animation** (mp4 + gif), suitable for slides or a README.

It is an internal tool with two consumer paths that share one contract:

- **Web path** — upload material in a Streamlit UI → an internal LLM analyzes it and proposes concepts → you review and edit them → render → download a zip of mp4 + gif per concept.
- **Agent path** — an external agent (e.g. Claude Code) writes a "scene spec" itself and renders it via the `manim-skill` CLI. No LLM on this side; the agent *is* the intelligence.

Both produce and consume the same **scene spec** (a validated JSON object) and go through the same component library and the same Docker-backed render backend.

## Status

Complete — both the local core pipeline (Phase 1) and the deployable multi-user web service (Phase 2): scene-spec pipeline, component library, render backend, LLM layer, CLI + agent skill, FastAPI job API + RQ workers, Streamlit frontend, and ARM64 / airgapped docker-compose packaging.

## Requirements

- Python ≥ 3.12
- Docker (rendering runs in a container; the deployed service runs as a docker-compose stack)

## Install (local development)

```bash
pip install -e ".[dev]"
docker build -t manim-skill:latest -f docker/Dockerfile .
```

## Usage

### Deployed service — Streamlit UI + job API

The whole system runs as one `docker compose` stack: `redis`, a FastAPI job API, an RQ worker, and a Streamlit UI.

```bash
cp .env.example .env      # edit: LLM endpoint, work dir, concurrency, ...
docker compose up -d
```

- Web UI: `http://<host>:8501` — upload → review/edit concepts → render → download.
- Job API: `http://<host>:8000`.

For the airgapped ARM64 deployment to a DGX Spark (cross-build, `docker save` bundle, transfer, `docker load`), see **[DEPLOY.md](DEPLOY.md)**.

### Agent path — the CLI

Write a scene spec as a JSON file, then:

```bash
manim-skill catalog                                # list components + their schemas
manim-skill validate path/to/spec.json             # validate without rendering
manim-skill render path/to/spec.json --workdir out                  # render locally
manim-skill render path/to/spec.json --remote http://<host>:8000    # render via the deployed backend
```

`--remote` (or the `MANIM_SKILL_BACKEND` env var) submits the spec to the deployed service and polls for the result instead of rendering in-process. If a `raw` beat fails to render, `render` prints the traceback — fix the spec and render again.

For the LLM-driven flow (input → concepts → specs → bundle) the CLI exposes the same stages the web service uses, with a review checkpoint between analyze and codegen:

```bash
# Stage 1: LLM analyze; writes <workdir>/concepts.json
manim-skill analyze paper.pdf --kind pdf -o out

# (Optional) edit out/concepts.json — drop / reorder / rewrite concepts

# Stage 2: LLM codegen for each concept; writes <workdir>/spec_NN.json
manim-skill codegen-concepts out                    # all concepts
manim-skill codegen-concepts out --indices 0,2,4    # subset

# Stage 3: local docker render; writes <workdir>/output.zip
manim-skill bundle out --quality high               # 1080p60

# Or one-shot, with an interactive pause for review between stages 1 and 2:
manim-skill demo paper.pdf --kind pdf -o out                # prompts before codegen
manim-skill demo paper.pdf --kind pdf -o out --yes          # skip the prompt
```

LLM endpoint is read from `MANIM_SKILL_LLM_BASE_URL` (default `http://localhost:11434/v1`), `MANIM_SKILL_LLM_MODEL` (default `qwen3.5-35b`), and `MANIM_SKILL_LLM_API_KEY` env vars. When an agent (Claude Code, etc.) is the human-checkpoint driver, it should call `analyze` / `codegen-concepts` / `bundle` separately and run its own review UI between them.

### Web pipeline in Python

`manim_skill.llm.run_pipeline` runs input → analyze → codegen → render directly, for scripting:

```python
from manim_skill.llm.client import OpenAIClient
from manim_skill.llm.pipeline import run_pipeline

client = OpenAIClient(base_url="http://your-llm:8000/v1", model="qwen3.5-35b")
batch = run_pipeline(client, source_text, "text", workdir="out")
print(batch.zip_path)
```

The internal LLM is reached through any OpenAI-compatible endpoint (vLLM, Ollama).

## The scene spec

A scene spec is a JSON object: a `title`, an `aspect_ratio`, and a list of `beats`. Each beat is either a **component** (a name + `params` matching that component's schema) or a **`raw` beat** (a `code` string of manim Python, where the scene is `self`).

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

## Components

The library ships 15 components. Each declares a Pydantic parameter schema — that one declaration is the single source of truth for validation, the LLM prompt catalog, and the agent skill docs.

| Component | For |
|-----------|-----|
| `CodeWalkthrough` | code with line highlighting |
| `NeuralNetDiagram` | layered nodes + connections |
| `AttentionFlow` | token sequence + attention weights |
| `MatrixOp` | matrix multiply / transpose / reshape |
| `PlotEvolution` | a numeric series as a line graph |
| `FunctionPlot` | y = f(x) on labeled axes (sigmoid/tanh/loss curves/…) |
| `HeatmapBeat` | a 2D array as a colored grid (attention / confusion matrices) |
| `PipelineDiagram` | linear labeled boxes + arrows |
| `GraphBeat` | arbitrary nodes + edges (directed or undirected), pick a layout |
| `TableBeat` | paper-style results table, optional cell highlight |
| `OptimizationPath` | dot follows f(x) curve toward a minimum, leaves a trace |
| `FormulaBreakdown` | a LaTeX formula |
| `FormulaWalkthrough` | a LaTeX formula whose parts get boxed + captioned step by step |
| `GeometryAnim` | basic shapes + transforms |
| `TextBeat` | title cards / captions / bullet lists |

Adding a component is a single file in `manim_skill/components/` — it is auto-discovered, and the catalog and skill docs update automatically.

CJK note: the docker image bundles Noto CJK, so plain-text components (TextBeat, PipelineDiagram labels, captions, anything that flows through manim's Pango `Text()`) render Chinese / Japanese / Korean. LaTeX (`FormulaBreakdown.formula`, raw `Tex` / `MathTex`) is English-only — keep formulas pure math and put localized text in the title and caption fields.

## Architecture

Two consumer paths produce or consume the same **scene spec** and share one render backend:

```mermaid
flowchart TB
    AG["External agent / Claude Code"]
    UI["Streamlit UI<br/>frontend/"]

    AG -->|"writes a scene spec"| SPEC
    AG --> CLI["manim-skill CLI · cli.py"]
    UI -->|"upload material"| BC["backend_client.py<br/>(shared HTTP client)"]
    CLI -->|"--remote / MANIM_SKILL_BACKEND"| BC
    CLI -->|"local, in-process"| RB

    BC -->|"REST /analyze /render /jobs"| API["FastAPI job API<br/>service/app.py"]
    API <--> RJ[("Redis<br/>job store + RQ queue")]
    RJ --> W["RQ worker<br/>service/worker.py · handlers.py"]
    W --> AN["analyze · concepts"]
    W --> CG["generate_spec · lint re-ask"]
    AN --> LLM[("internal LLM<br/>OpenAI-compatible (vLLM/Ollama)")]
    CG --> LLM
    CG --> SPEC

    SPEC{{"scene spec — the single contract"}}
    SPEC --> RB["render_batch<br/>render/backend.py"]
    RB --> BEAT["per-beat docker render<br/>sandboxed: --network none, read-only, capped"]
    BEAT --> STITCH["ffmpeg stitch → gif"]
    STITCH --> ZIP["output.zip + manifest.json"]
```

- **Web path** — Streamlit → `backend_client` → the FastAPI job API → Redis/RQ → worker. It is **two independent jobs**: an `analyze` job, then (after the human review checkpoint, which lives in the Streamlit session) a `render` job that runs `generate_spec` (`mode=codegen`) then `render_batch`.
- **Agent path** — the agent writes the spec itself (no LLM); the CLI renders it locally, or (`--remote`) submits it to the same API as a `mode=spec` render job.

Strictly one-directional layers:

```
spec/         scene spec schema (Pydantic), lenient JSON parsing, validation
components/   the component library (auto-discovered, schema-bearing)
builder/      turns a spec into a manim Scene
render/       Docker-backed render backend — per-beat parallel render → stitch → gif → zip
llm/          the LLM half — model-agnostic client, analyze, codegen, repair loop, pipeline
service/      FastAPI job API + RQ worker + Redis-backed job store (the deployed backend)
frontend/     the Streamlit web UI
backend_client.py   HTTP client for the job API — shared by the CLI's remote mode and the frontend
cli.py        the manim-skill CLI
```

The render backend renders each beat independently in its own sandboxed container, in parallel, with graceful per-beat / per-clip failure handling. The service backend turns that into an async job API; the Streamlit frontend and the CLI's remote mode are both thin clients of it. The whole thing deploys as one universal Docker image via docker-compose.

See `docs/architecture.md` for the full architecture (runtime diagram + layers + render backend + service), `CLAUDE.md` for the working conventions, `docs/superpowers/` for the design specs and implementation plans, and `DEPLOY.md` for deployment.

## Development

```bash
pytest -m "not docker"     # fast suite, no Docker
pytest                     # full suite incl. Docker integration tests
```

The whole `llm/` layer and the `service/` backend are tested with fakes (`FakeLLMClient`, `fakeredis`) — no live LLM or Redis is needed for the fast suite. Docker-marked tests require Docker running and the `manim-skill:latest` image built; rebuild that image after changing anything a render touches.

### Live eval against a real LLM

`scripts/eval/run_smoke.py` points `OpenAIClient` at any OpenAI-compatible endpoint (here: OpenRouter free models) and exercises the LLM half — `analyze` / `codegen` / full pipeline — on the materials in `tests/realworld-test/` (a code snippet; the paper/report inputs aren't shipped with the repo). Two stages report per-concept success and dump the validated specs; `scripts/eval/render_specs.py` then renders them and reports per-beat results. `scripts/eval/bundle_specs.py` takes any directory of validated specs and renders them as one `render_batch`, producing a single zip + `manifest.json` — the natural end-to-end deliverable.

This is the harness the design doc deferred. A round against `nvidia/nemotron-3-super-120b-a12b:free` surfaced five raw-beat failure modes the LLM kept hitting (Scene-class wrappers, no `self.play` calls, double-escaped `\n` in JSON, cross-beat variable references, and the LaTeX sibling case) — each is now an explicit DO/DO NOT in the codegen system prompt, locked in by `tests/llm/test_codegen.py`. Re-running the broken concepts under the tightened prompt took beat-level render success from **58% → 93%**. A full end-to-end run on a Chinese DLM research report (not shipped with the repo; 64K chars → 5 concepts → 5 validated specs → 24 beats) hit **87.5 % beat success** and produced a 7.1 MB combined bundle.
