# manim-skill

*[English](README.md) · [繁體中文](README.zh-TW.md)*

Turn a **concept** — a paragraph of text, a code snippet, or a PDF — into a short **manim animation** (mp4 + gif), suitable for slides or a README.

It is an internal tool with two consumer paths that share one contract:

- **Web path** — input → an internal LLM analyzes the material and picks the parts worth animating → the LLM writes a "scene spec" per concept → render → a zip of mp4 + gif per concept.
- **Agent path** — an external agent (e.g. Claude Code) writes a scene spec itself and renders it via the `manim-skill` CLI. No LLM on this side; the agent *is* the intelligence.

Both produce and consume the same **scene spec** (a validated JSON object) and go through the same component library and the same Docker-backed render backend.

## Status

**Phase 1 (local) is complete** — the full pipeline, component library, render backend, LLM layer, CLI, and agent skill. **Phase 2 is not built** — a multi-user web frontend, the human-in-the-loop concept-review checkpoint, a Redis-backed queue, and deployment.

## Requirements

- Python ≥ 3.12
- Docker (rendering runs in a container)

## Install

```bash
pip install -e ".[dev]"
docker build -t manim-skill:latest -f docker/Dockerfile .
```

## Usage

### Agent path — the CLI

Write a scene spec as a JSON file, then:

```bash
manim-skill catalog                          # list components + their parameter schemas
manim-skill validate path/to/spec.json       # validate without rendering
manim-skill render path/to/spec.json --workdir out   # render → prints mp4 / gif / zip paths
```

If a `raw` beat fails to render, `render` prints the traceback — fix the spec and render again.

### Web path — the LLM pipeline

```python
from manim_skill.llm.client import OpenAIClient
from manim_skill.llm.pipeline import run_pipeline

client = OpenAIClient(base_url="http://your-llm:8000/v1", model="qwen3.5-35b")
batch = run_pipeline(client, source_text, "text", workdir="out")
print(batch.zip_path)
```

`run_pipeline` accepts `"text"`, `"code"`, or `"pdf"` input. The internal LLM is reached through any OpenAI-compatible endpoint (vLLM, Ollama).

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

The library ships 8 core components plus a text helper. Each declares a Pydantic parameter schema — that one declaration is the single source of truth for validation, the LLM prompt catalog, and the agent skill docs.

| Component | For |
|-----------|-----|
| `CodeWalkthrough` | code with line highlighting |
| `NeuralNetDiagram` | layered nodes + connections |
| `AttentionFlow` | token sequence + attention weights |
| `MatrixOp` | matrix multiply / transpose / reshape |
| `PlotEvolution` | a numeric series as a line graph |
| `PipelineDiagram` | labeled boxes + arrows |
| `FormulaBreakdown` | a LaTeX formula |
| `GeometryAnim` | basic shapes + transforms |
| `TextBeat` | title cards / captions / bullet lists |

Adding a component is a single file in `manim_skill/components/` — it is auto-discovered, and the catalog and skill docs update automatically.

## Architecture

Strictly one-directional layers:

```
spec/        scene spec schema (Pydantic), lenient JSON parsing, validation
components/  the component library (auto-discovered, schema-bearing)
builder/     turns a spec into a manim Scene
render/      Docker-backed render backend — per-beat parallel render → stitch → gif → zip
llm/         the Web path — model-agnostic client, analyze, codegen, repair loop
cli.py       the agent path — a thin CLI over the layers above
```

The render backend renders each beat independently in its own sandboxed container, in parallel, with graceful per-beat / per-clip failure handling. The LLM layer's `BeatRepairer` retries failed `raw` beats by feeding the traceback back to the LLM. See `CLAUDE.md` for the full architecture and `docs/superpowers/` for the design spec and the five implementation plans.

## Development

```bash
pytest -m "not docker"     # fast suite, no Docker (~139 tests)
pytest                     # full suite incl. Docker integration tests (~153 tests)
```

The whole `llm/` layer is tested with a `FakeLLMClient` — no live LLM is needed for CI. Docker-marked tests require Docker running and the `manim-skill:latest` image built; rebuild that image after changing anything a render touches.
