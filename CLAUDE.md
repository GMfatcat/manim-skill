# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`manim-skill` turns a "concept" (text, a code snippet, or a PDF) into a short manim animation (mp4 + gif, bundled in a zip). It is an internal tool with two consumer paths that share one contract:

- **Web path** — the deployed service: a Streamlit UI → a FastAPI job API → an RQ worker. Upload material → an internal LLM (OpenAI-compatible endpoint) analyzes it and proposes concepts → the user reviews/edits → the worker codegens a scene spec per concept and renders → zip. `manim_skill.llm.pipeline.run_pipeline` is the equivalent run in-process, for scripting.
- **Agent path** — the `manim-skill` CLI: an external agent (e.g. Claude Code) writes a scene spec itself and renders it — locally in-process, or (`--remote` / `MANIM_SKILL_BACKEND`) submitted to the deployed service. No LLM involved on this side.

Both produce/consume the same **scene spec** (a validated JSON object) and go through the same component library and the same docker-backed render backend.

## Commands

```bash
pip install -e ".[dev]"          # install (re-run after pyproject changes — entry point / deps)
pytest -m "not docker"           # fast suite — no Docker needed (~285 tests)
pytest                           # full suite incl. docker integration tests (~310 tests, slow)
pytest tests/llm/test_codegen.py::test_generate_spec_valid_first_try -v   # single test
docker build -t manim-skill:latest -f docker/Dockerfile .                # (re)build the universal image
docker compose --env-file .env.example up -d    # run the full service stack locally (redis/api/worker/ui)
manim-skill catalog | validate <spec.json> | render <spec.json> [--remote URL] [--quality ...] | gen-skill-docs
manim-skill analyze <input> --kind text|code|pdf -o <wd>   # LLM stage 1: input -> concepts.json
manim-skill codegen-concepts <wd> [--indices 0,2]          # LLM stage 2: concepts -> spec_NN.json
manim-skill bundle <wd> [--quality medium]                 # local docker render -> output.zip
manim-skill demo <input> --kind ... -o <wd> [--yes]        # 3 stages, interactive pause before codegen unless --yes
```

Docker integration tests are marked `@pytest.mark.docker` and require Docker Desktop running plus the `manim-skill:latest` image built. **Rebuild the image after changing anything under `manim_skill/`** — `docker/Dockerfile` pip-installs the whole package, so it goes stale (the same universal image is the render container *and* the api/worker/ui services). The `tests/test_compose_e2e.py` test additionally needs a Redis on the dev box.

Environment: Windows + Docker Desktop, Python 3.13, manim 0.20.1. There is **no live internal LLM in the dev environment** — the entire `llm/` layer is tested with `FakeLLMClient`, and the `service/` layer with `fakeredis`.

## Architecture

`docs/architecture.md` has the runtime data-flow diagram (the two consumer paths + the shared spec contract + render backend). The layering below is the module map.

Strict one-directional layering — `spec` is pure data with no manim import; later layers depend only on earlier ones:

```
spec/        SceneSpec/Beat schema (Pydantic), lenient JSON parse, validation
components/  15 animation components, each: name + Params (Pydantic) + build()/animate(); @register + pkgutil auto-discovery
builder/     SpecScene (a MovingCameraScene that renders a spec's beats), raw-beat exec, camera, write_render_inputs
render/      docker-backed render backend — see below
llm/         model-agnostic client, analyze, codegen, repair loop, pipeline
service/     FastAPI job API + RQ worker + Redis job store — the deployed backend; see below
frontend/    the Streamlit web UI (a thin 5-stage state machine over backend_client)
backend_client.py   HTTP client for the job API — shared by the CLI's --remote mode and the frontend
cli.py / skill_docs.py   the agent path — thin CLI + auto-generated skill docs
```

**The scene spec is the single contract.** A spec has a `title`, `aspect_ratio`, and a list of `beats`. A beat is either a registered **component** (`component` name + `params` matching that component's Pydantic schema) or a **`raw` beat** (a `code` string of manim Python, run with the scene as `self`). Everything downstream — builder, render backend, CLI, LLM codegen — operates on this one structure. `raw` is not a special pipeline; it's just a beat type. The exec_raw entry point also defensively recovers the most common LLM packing mistake — newlines double-escaped in JSON as `\\n` (a literal backslash+n in the decoded Python source) — by retrying compile with those sequences replaced by real newlines whenever the first compile raises SyntaxError. Clean code on the first try is left untouched, so a legitimate `\n` inside a Python string literal is preserved.

**Components are the single source of truth.** Each component declares a Pydantic `Params` model. That one declaration drives: validation of beat params (`spec/validate.py`), the LLM prompt catalog (`llm/catalog.py`), and the agent skill reference docs (`skill_docs.py`). New components need zero wiring — `components/__init__.py` auto-discovers every module in the package. Adding a component therefore changes the catalog and the skill docs automatically (a drift test, `tests/test_skill_reference_current.py`, enforces that `skill/reference/*.md` stays regenerated).

**Render backend (`render/`)** — `render_batch(specs, workdir, *, repairer=None, quality="medium")` is the entry point. Job hierarchy: batch → clip (one per spec) → beat. Each beat is rendered **independently** as a 1-beat spec in its own docker container (`docker_render.render_spec_to_mp4`), in parallel up to a worker cap (`queue.RenderQueue`). A clip's beat mp4s are concatenated with ffmpeg (`stitch.py`), converted to gif (`convert.py`), and all clips are bundled into one zip + `manifest.json` (`bundle.py`). Failure is graceful and isolated: a failed beat is skipped, a failed clip doesn't stop the batch. `cache.py` keys rendered beats by content hash. The container is the security sandbox for `raw` LLM code (`--network none`, `--read-only`, resource caps, timeout). `quality` maps to manim's `-ql / -qm / -qh / -qp / -qk` flags (480p15 → 4K); default `medium` (720p30) is the production baseline, overridable per render call, CLI flag (`--quality`), or service env var (`MANIM_SKILL_RENDER_QUALITY`).

**LLM layer (`llm/`)** — `LLMClient` is a structural Protocol (`.complete(system, user) -> str`); `OpenAIClient` targets any OpenAI-compatible endpoint (vLLM/Ollama) and `FakeLLMClient` is the test double. "Model-agnostic" means everything depends on the Protocol, never a model — model routing is just passing a different client. `analyze` and `codegen` are one LLM call each; codegen re-asks once on a parse/validation failure. `BeatRepairer` is the repair loop — **only for `raw` beats**: render fails → traceback fed back to the LLM → fixed code → retry up to N. It plugs into `render_batch` via the optional `repairer` arg; component beats are deterministic and never repaired.

**Service layer (`service/`)** — the deployed backend. `app.py` is a FastAPI `create_app` factory exposing the job API (`/analyze`, `/render`, `/jobs/{id}`, `/jobs/{id}/result`, `DELETE /jobs/{id}`, `/catalog`, `/health`); `worker.py` is an RQ worker whose `handlers.py` reuse `analyze`/`generate_spec`/`render_batch` unchanged. Job records live in Redis (`job_store.py`, JSON + TTL — no SQL DB); a Redis semaphore (`llm_throttle.py`) caps LLM concurrency. The web flow is **two independent jobs** — an `analyze` job, then (after the human review checkpoint, which lives entirely in the Streamlit session) a `render` job — never a paused server-side job. `mode=codegen` (web, quota-enforced) vs `mode=spec` (agent, unlimited) is the only render-job branch. Tested with `fakeredis`; the docker-out-of-docker render path (worker container spawns sibling render containers) is covered by `tests/test_compose_e2e.py`.

## Deployment

The whole system ships as **one universal `manim-skill:latest` image** (manim + ffmpeg + docker CLI + Noto CJK fonts + IBM Plex Latin + the package) running four roles via `docker-compose.yml`: `redis`, `api`, `worker`, `ui`. Noto CJK is bundled so `Text("中文")` (TextBeat / PipelineDiagram / captions etc., everything that flows through manim's Pango path) renders Trad/Simp Chinese, Japanese, and Korean correctly. IBM Plex Sans / Serif / Mono (Latin) is also bundled — pulled from the IBM/plex GitHub release via jsdelivr at build time — because Pango's per-glyph fallback chain otherwise hands adjacent Latin chars to different fonts and you end up with uneven kerning (`parallel` rendered as `para llel`). The LaTeX path (`FormulaBreakdown.formula`, `Tex`, `MathTex`) is **English only** — adding `\text{中文}` to a formula needs an XeLaTeX + xeCJK setup we have not wired up; keep formulas pure math and put Chinese in the title/caption. The `worker` mounts the host docker socket and spawns render containers as siblings; the shared work dir is a **same-path bind mount** (must be a Linux path) so those sibling containers' bind mounts resolve on the host daemon. `scripts/build-images.sh` cross-builds for ARM64 via buildx; `scripts/bundle-for-deploy.sh` + `DEPLOY.md` cover the airgapped `docker save`/`load` deploy to the DGX Spark. Dev/test happens on amd64; ARM64 is built-and-saved, not run, on the dev box.

## Conventions

- TDD throughout — every module has a `tests/<mirror>/` test file written before the implementation.
- LLM output is never trusted: always `parse_spec_text` (lenient) → `validate_spec` before use.
- `subprocess.run` calls that invoke docker pass `encoding="utf-8", errors="replace"` (the dev machine's console codepage is cp950).
- The design specs and the nine implementation plans (Phase 1 = plans 1–5, Phase 2 = plans 6–9) live in `docs/superpowers/`.

## Live LLM eval

The fast suite is all fakes. For real evidence against a real LLM there is `scripts/eval/`: `probe_openrouter.py` (list/hello any OpenAI-compatible model), `run_smoke.py` (run `analyze`/`codegen`/full pipeline stages, plus `regen` to re-codegen specific concept indices from a cached `concepts.json` without re-paying for analyze), `render_specs.py` (one-spec-per-zip batch render of every `spec_*.json` under a directory tree), and `bundle_specs.py` (load every `spec_*.json` under a directory, pass them as one batch to `render_batch`, get a single zip with all clips + a top-level `manifest.json` — the natural "end-to-end demo deliverable"). The OpenRouter key is read from `OpenRouterKey` env var or, as fallback, a gitignored `tests/realworld-test/key.txt`. Source materials and the saved smoke outputs live under `tests/realworld-test/`. A full end-to-end run against a DLM research report (Chinese, 64K chars; not committed) on `nemotron-3-super` cleared the pipeline at 87.5% beat success and produced a 7.1 MB combined bundle.

The current `_CODEGEN_SYSTEM` prompt in `manim_skill/llm/codegen.py` is **shaped by this eval** — five raw-beat failure modes (Scene-class wrappers, missing `self.play`/`add`, double-escaped `\n` in JSON, cross-beat variable references) and the sibling LaTeX-backslash mistake were observed against `nvidia/nemotron-3-super-120b-a12b:free` and turned into explicit DO/DO NOT rules. Two tests in `tests/llm/test_codegen.py` (`test_codegen_system_prompt_includes_raw_beat_guards`, `test_codegen_system_prompt_includes_latex_backslash_guard`) assert the rules stay in the prompt — they are guards on prompt content, not on model behavior. If you change the prompt, run the live eval again before assuming the change is safe.

The **static harness** (the deterministic theme/layout/component/lint layers, see `docs/superpowers/specs/2026-06-07-*` and `2026-06-08-*`) was validated by repeated full runs against `nemotron-3-super` on `tests/realworld-test/multihead_attention.py` (v1–v4). Findings that should outlive the run: (1) the model leans **entirely on registered components — zero raw beats** across all rounds, which is the whole point (the error-prone raw path is avoided, and every beat gets the theme + safe layout by construction); beat success ran 87.5% → 100%. (2) The model **persistently mis-escapes LaTeX in both directions** (under-escape `\quad`→`quad`; over-escape `\\mathbf`/`\\rightarrow`→ a line break + literal word) and **does not self-correct even after the lint re-ask** — so correctness is carried by the *deterministic* layer (`spec/parse.py` de-tox + `spec/latex.py` `repair_latex` at component build), not by the prompt or the re-ask. `repair_latex` only fixes commands in its `_COMMANDS` whitelist; the limiting factor is whitelist completeness, so **when a future eval renders a `\command` as a literal word, add that command to `_COMMANDS` (one edit)** rather than reaching for the model. (Process note: scripts/one-liners that embed LaTeX backslashes must be written with the Write tool, not a `<<'EOF'` heredoc — the heredoc silently halves backslashes and produces misleading eval analysis.)

The harness payoff is **strongly model-dependent**, and a same-input codegen sweep makes the rule concrete: `nemotron-3-super` picks registered components and clears 87.5–100% beat success; `gpt-oss-120b`/`gpt-oss-20b` are capable enough to emit valid specs but **prefer hand-writing `raw` beats (~80% of beats)** and routinely break the no-cross-beat-variables rule, so they land around **62.5% beat success** (a `NameError` from referencing a variable defined in an earlier beat — each raw beat execs in a fresh namespace); `nemotron-nano-9b` (9B) can't even produce parseable concepts at the analyze stage. The theme still reaches the raw-heavy models (their raw code uses the injected `PRIMARY_SOFT`/`label_text`, so what *does* render is themed), but the deterministic component-layout guarantees only land when the model actually picks components. Practical guidance: **prefer a mid/large open model that uses components (nemotron-3-super class)**; pushing `gpt-oss`-style models harder toward components (and reinforcing the no-cross-beat-variable raw guard) is the obvious next lever if such models must be used.
