---
name: manim-skill
description: Turn a concept into a manim animation. Use when you need an explanatory animation (for slides or a README) of a math concept, an AI/ML paper idea, or a code snippet — you write a "scene spec" JSON and this skill renders it to mp4 + gif.
---

# manim-skill

Produce a short manim animation by writing a **scene spec** (a JSON file) and rendering it with the `manim-skill` CLI. You (the agent) write the spec; this skill validates and renders it. There is no model dependency — the intelligence is you.

## Workflow

1. **Learn the vocabulary.** Run `manim-skill catalog` to see the available components and their parameter schemas. Read `reference/spec-format.md` for the scene spec format and `reference/components.md` for the full component reference.
2. **Write a scene spec** — a JSON file with a `title` and a non-empty list of `beats`. Each beat is either a library component (preferred) or a `raw` beat with manim Python code. Use `raw` only when no component fits.
3. **Validate it.** Run `manim-skill validate path/to/spec.json`. Fix anything it reports.
4. **Render it.** Run `manim-skill render path/to/spec.json --workdir OUTDIR`. On success it prints the mp4, gif, and zip paths. On a render failure it prints the error — fix the spec (most often a `raw` beat's code) and render again.

## Commands

- `manim-skill catalog` — print the component catalog.
- `manim-skill validate <spec.json>` — validate a spec without rendering.
- `manim-skill render <spec.json> [--workdir DIR]` — render a spec to mp4 + gif (also bundled in a zip).
- `manim-skill gen-skill-docs [--skill-dir DIR]` — regenerate `reference/` from the current component code.

## Notes

- A `raw` beat runs arbitrary manim Python inside a sandboxed Docker container; the scene is `self`.
- If a `raw` beat fails to render, `manim-skill render` reports the traceback — that is your repair signal: rewrite the code and render again.
- The `reference/` docs are generated from the component code (`manim-skill gen-skill-docs`), so they never drift.
