# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`manim-skill` turns a "concept" (text, a code snippet, or a PDF) into a short manim animation (mp4 + gif, bundled in a zip). It is an internal tool with two consumer paths that share one contract:

- **Web path** — `manim_skill.llm.pipeline.run_pipeline`: input → internal LLM analyzes & picks concepts → LLM writes a scene spec per concept → render → zip. Uses a company-internal LLM (OpenAI-compatible endpoint).
- **Agent path** — the `manim-skill` CLI: an external agent (e.g. Claude Code) writes a scene spec itself and submits it for rendering. No LLM involved on this side.

Both produce/consume the same **scene spec** (a validated JSON object) and go through the same component library and the same docker-backed render backend.

## Commands

```bash
pip install -e ".[dev]"          # install (re-run after pyproject changes — entry point / deps)
pytest -m "not docker"           # fast suite — no Docker needed (~139 tests)
pytest                           # full suite incl. docker integration tests (~153 tests, slow)
pytest tests/llm/test_codegen.py::test_generate_spec_valid_first_try -v   # single test
docker build -t manim-skill:latest -f docker/Dockerfile .                # (re)build the render image
manim-skill catalog | validate <spec.json> | render <spec.json> --workdir DIR | gen-skill-docs
```

Docker integration tests are marked `@pytest.mark.docker` and require Docker Desktop running plus the `manim-skill:latest` image built. **Rebuild the image after changing anything under `manim_skill/`** that a render touches (components, builder, spec) — the image pip-installs the package, so it goes stale.

Environment: Windows + Docker Desktop, Python 3.13, manim 0.20.1. There is **no live internal LLM in the dev environment** — the entire `llm/` layer is tested with `FakeLLMClient`.

## Architecture

Strict one-directional layering — `spec` is pure data with no manim import; later layers depend only on earlier ones:

```
spec/      SceneSpec/Beat schema (Pydantic), lenient JSON parse, validation
components/  9 animation components, each: name + Params (Pydantic) + build()/animate(); @register + pkgutil auto-discovery
builder/    SpecScene (a MovingCameraScene that renders a spec's beats), raw-beat exec, camera, write_render_inputs
render/     docker-backed render backend — see below
llm/        the Web path — model-agnostic client, analyze, codegen, repair loop, pipeline
cli.py / skill_docs.py   the agent path — thin CLI + auto-generated skill docs
```

**The scene spec is the single contract.** A spec has a `title`, `aspect_ratio`, and a list of `beats`. A beat is either a registered **component** (`component` name + `params` matching that component's Pydantic schema) or a **`raw` beat** (a `code` string of manim Python, run with the scene as `self`). Everything downstream — builder, render backend, CLI, LLM codegen — operates on this one structure. `raw` is not a special pipeline; it's just a beat type.

**Components are the single source of truth.** Each component declares a Pydantic `Params` model. That one declaration drives: validation of beat params (`spec/validate.py`), the LLM prompt catalog (`llm/catalog.py`), and the agent skill reference docs (`skill_docs.py`). New components need zero wiring — `components/__init__.py` auto-discovers every module in the package. Adding a component therefore changes the catalog and the skill docs automatically (a drift test, `tests/test_skill_reference_current.py`, enforces that `skill/reference/*.md` stays regenerated).

**Render backend (`render/`)** — `render_batch(specs, workdir, *, repairer=None)` is the entry point. Job hierarchy: batch → clip (one per spec) → beat. Each beat is rendered **independently** as a 1-beat spec in its own docker container (`docker_render.render_spec_to_mp4`), in parallel up to a worker cap (`queue.RenderQueue`). A clip's beat mp4s are concatenated with ffmpeg (`stitch.py`), converted to gif (`convert.py`), and all clips are bundled into one zip + `manifest.json` (`bundle.py`). Failure is graceful and isolated: a failed beat is skipped, a failed clip doesn't stop the batch. `cache.py` keys rendered beats by content hash. The container is the security sandbox for `raw` LLM code (`--network none`, `--read-only`, resource caps, timeout).

**LLM layer (`llm/`)** — `LLMClient` is a structural Protocol (`.complete(system, user) -> str`); `OpenAIClient` targets any OpenAI-compatible endpoint (vLLM/Ollama) and `FakeLLMClient` is the test double. "Model-agnostic" means everything depends on the Protocol, never a model — model routing is just passing a different client. `analyze` and `codegen` are one LLM call each; codegen re-asks once on a parse/validation failure. `BeatRepairer` is the repair loop — **only for `raw` beats**: render fails → traceback fed back to the LLM → fixed code → retry up to N. It plugs into `render_batch` via the optional `repairer` arg; component beats are deterministic and never repaired.

## Phasing

The design (`docs/superpowers/specs/`) splits this into Phase 1 (local, built — everything above) and Phase 2 (not built — multi-user web frontend, the human-in-the-loop concept-review checkpoint, a Redis-backed queue, deployment). When touching `render/queue.py` or job models, note the Phase-2 seam: `RenderQueue` is deliberately a thin interface so a Redis-backed implementation can replace the local `ThreadPoolExecutor`.

## Conventions

- TDD throughout — every module has a `tests/<mirror>/` test file written before the implementation.
- LLM output is never trusted: always `parse_spec_text` (lenient) → `validate_spec` before use.
- `subprocess.run` calls that invoke docker pass `encoding="utf-8", errors="replace"` (the dev machine's console codepage is cp950).
- Design docs and the five implementation plans live in `docs/superpowers/`.
