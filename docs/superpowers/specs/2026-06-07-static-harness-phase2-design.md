# Static Harness Phase 2: layout safety, slide components, spec lint

**Date:** 2026-06-07
**Status:** approved design, pending implementation plan
**Builds on:** `2026-06-07-static-harness-theme-design.md` (phase 1 — the theme layer, now merged)

## Problem

Phase 1 gave the framework a deterministic theme (palette + fonts + safe text
factories) and refactored every component to use it. That fixed palette and
typography consistency — the bulk of what dlm-polish fought — but explicitly
deferred three things that also separate "a weak model's raw output" from "a
polished result":

1. **Geometric layout** — content that overflows the frame or overlaps. The
   theme can't prevent a model from placing too much, too wide.
2. **Higher-level building blocks** — dlm-polish hand-built section dividers,
   two-column comparisons, and masked-token rows; the framework has no
   deterministic component for these, so a model must hand-roll them as raw
   beats (the error-prone path).
3. **No feedback on spec-level smells** — over-long captions, text-packed
   beats: nothing tells the model (or the author) when a spec is over-full.

Phase 2 closes these as **static, deterministic harness** (no new model
besides reusing the existing codegen client for one extra re-ask). The factory
runs open-source models, so the leverage is the same as phase 1: make the
deterministic layer carry the quality.

## Scope

In scope (one spec, one plan, three independent parts on the phase-1 theme):

- **A. Layout-safety helpers** — `fit_width`, `safe_area`, `stack`.
- **A'. Builder auto-clamp** — every beat's content is clamped into the safe
  frame as a final net.
- **B. Three new components** — `SectionDivider`, `TwoColumn`, `TokenSequence`.
- **C. Spec lint** — `lint_spec` advisory warnings, surfaced in the CLI and
  fed back into codegen for one self-correction re-ask.

Out of scope: any spec-schema change to existing beats/components (new
components only ADD params models); any dynamic render→critique loop; vision
models; new dependencies.

## Design

### A. `manim_skill/components/layout.py`

Pure geometry helpers, separate from `theme.py` (theme owns color/font;
layout owns geometry). They operate on already-built manim mobjects and read
`GAP` / `MARGIN` from the theme.

- `fit_width(mobj, max_width)` — if `mobj.width > max_width`, call
  `mobj.scale_to_fit_width(max_width)`. Returns `mobj` (mutated, for chaining).
- `safe_area(mobj, *, frame_width=14.22, frame_height=8.0, margin=MARGIN)` —
  compute the usable box `(frame_width - 2*margin, frame_height - 2*margin)`.
  If `mobj` exceeds either dimension, uniformly scale it down to fit (preserve
  aspect). Then shift so the mobject's bounding box lies within the usable box
  (clamp center). Returns `mobj`. A mobject already inside the box is
  untouched (no-op) — this is what makes the builder auto-clamp jank-free in
  the common case.
- `stack(mobjs, *, gap=GAP, center=True)` — arrange a list of mobjects
  vertically (`VGroup(*mobjs).arrange(DOWN, buff=gap)`), optionally centered,
  guaranteeing a minimum gap so they never overlap. Returns the `VGroup`.

Frame defaults match manim's 16:9 config (`frame_width ≈ 14.22`,
`frame_height = 8.0`), the same numbers `spec_scene._CAPTION_MAX_WIDTH = 13.0`
already assumes.

### A'. Builder auto-clamp (`manim_skill/builder/spec_scene.py`)

`_render_beat` wraps each beat so its content cannot overflow:

1. Before rendering the beat, snapshot `before = set(self.mobjects)`.
2. Render the beat (component build+animate, or raw exec) as today.
3. Compute `new = [m for m in self.mobjects if m not in before]`.
4. If `new` is non-empty, group them (`VGroup(*new)`) and call `safe_area(...)`
   on the group using the scene's frame dims. A group already within the safe
   box is unchanged (no-op); only genuinely-overflowing content is scaled and
   re-centered — strictly better than the current edge-clipping.
5. Then add the caption (unchanged — `_build_caption` already width-fits it,
   and the caption is excluded from the clamp because it is added after the
   snapshot/clamp).

This gives a uniform "can't overflow" guarantee across component and raw beats
without per-component work, and is a no-op for well-behaved content.

### B. Three new components

Each is a standard registered `Component` (auto-discovered, theme-driven,
with a Pydantic `Params`), mirroring the existing 14. Each gets a `build`
(theme colors/fonts, layout helpers) and an `animate` (FadeIn / stagger).

**`SectionDivider`** (`section_divider.py`) — generalizes the dlm chapter card.
- Params: `number: int | None = None`, `title: str`, `subtitle: str | None = None`.
- build: a top rule line, `§ NN` label in `FONT_MONO`/`THEME.PRIMARY` (omitted
  if `number is None`), the title via `title_text`, an optional subtitle via
  `body_text`/`THEME.INK_SOFT`, a bottom rule line; `stack`ed.
- animate: `FadeIn(card, shift=UP*0.3)`.

**`TwoColumn`** (`two_column.py`) — side-by-side comparison.
- Params: `left_title: str | None = None`, `right_title: str | None = None`,
  `left: list[str] = []`, `right: list[str] = []`.
- build: each column is a `stack` of an optional column title (`title_text`,
  smaller) over its `body_text` lines; the two columns are placed left/right of
  a central vertical `Line(color=THEME.RULE)`; the whole group is passed
  through `safe_area`.
- animate: `FadeIn`.

**`TokenSequence`** (`token_sequence.py`) — generalizes the dlm token row.
- Params: `tokens: list[Token]` where `Token` is a Pydantic model
  `{text: str = "", state: Literal["normal","masked","expand","delete","defer"] = "normal"}`.
- build: a horizontal row of fixed-size boxes (one per token), state → theme
  styling: normal = `THEME.PRIMARY` border on `THEME.BG`; masked = dashed
  `THEME.RULE` on `THEME.BG_CODE` with a `?`-style faint label; expand =
  `THEME.HIGHLIGHT` fill + `THEME.PRIMARY_SOFT` border; delete = `THEME.WARN`
  border on a warn-tinted fill; defer = dashed `THEME.INK_FAINT`. Token text in
  `FONT_MONO`. Row `arrange(RIGHT)` then `safe_area`.
- animate: staggered `FadeIn` (e.g. `LaggedStart`).

The dashed-box helper and the box factory live inside `token_sequence.py`
(not exported) — this component owns that detail.

### C. `manim_skill/spec/lint.py`

`lint_spec(spec: SceneSpec) -> list[LintWarning]` where
`LintWarning` is a small dataclass `(beat_index: int, code: str, message: str)`.
All warnings are advisory — `lint_spec` never raises and never blocks.

Rules (deterministic, static — no rendering). Thresholds are module-level
constants, tunable in one place:
- `caption_too_long` — a beat's `caption` length > `60` characters. One per
  offending beat.
- `beat_text_overload` — a beat carries too much text: a `TextBeat` with
  `len(bullets) > 6`, OR a `raw` beat whose `code` contains more than `4`
  combined occurrences of `Text(`, `MathTex(`, `Tex(`, `title_text(`,
  `body_text(`, `caption_text(`, `label_text(`. Conservative heuristic.
- `raw_sets_background` — a `raw` beat's `code` contains the substring
  `background_color` (the builder owns the background; setting it fights the
  theme).
- `raw_uses_italic` — a `raw` beat's `code` contains `ITALIC` or `italic=True`
  (italics are banned by the visual rules).

**CLI** (`cli.py`): the `validate` command, after a spec validates, runs
`lint_spec` and prints each warning (`beat N: <code> — <message>`) to stderr;
exit code stays 0 (warnings are advisory). A clean spec prints nothing extra.

**Codegen integration** (`llm/codegen.py` `generate_spec`): after a response
parses and validates, run `lint_spec`. If it is the first attempt and there
are warnings, re-ask once with the warnings appended to the prompt
(`"Your spec is valid but has these issues: ...; return a cleaner spec JSON"`),
reusing the existing re-ask machinery. Use the second response if it parses and
validates; otherwise **fall back to the first (valid) spec** — lint must never
turn a valid spec into a `CodegenError`. Net effect: at most one extra LLM call,
and lint can only improve, never break, codegen. The existing parse/validate
re-ask budget and behavior are unchanged for invalid responses.

### Connected changes

- `builder/raw.py` — inject `fit_width`, `safe_area`, `stack` into the
  raw-beat namespace alongside the phase-1 theme names.
- `llm/codegen.py` `_CODEGEN_SYSTEM` — one line in VISUAL RULES noting the
  layout helpers are available in raw beats (`safe_area(...)`, `stack(...)`).
- `llm/catalog.py` — the raw-beat theme-names hint line gains the three layout
  helper names. The three new components appear in the catalog automatically
  (auto-discovery), so `skill/reference/*.md` must be regenerated (drift test).

## Testing (TDD — tests first)

- **layout** (`tests/components/test_layout.py`): `fit_width` shrinks an
  over-wide mobject and leaves a narrow one; `safe_area` scales+recenters an
  oversized mobject to within the box and is a no-op for a small one; `stack`
  produces a VGroup whose adjacent members don't overlap and respects `gap`.
- **builder auto-clamp** (`tests/builder/test_spec_scene.py`): a beat that adds
  an oversized mobject ends with that mobject within the safe frame; a normal
  beat's mobject is left at its original size/position (no-op).
- **new components** (`tests/components/test_section_divider.py`,
  `test_two_column.py`, `test_token_sequence.py`): each `build` returns the
  expected structure (Texts present with theme fonts, token count matches,
  columns present), mirroring existing component tests. Plus a
  `@pytest.mark.docker` render-to-mp4 test per component, mirroring the
  existing docker component tests.
- **lint** (`tests/spec/test_lint.py`): each rule fires on a triggering spec
  and stays silent on a clean one; `lint_spec` returns `[]` for a good spec and
  never raises.
- **codegen lint re-ask** (`tests/llm/test_codegen.py`): a `FakeLLMClient`
  scripted to return a valid-but-long-caption spec first and a clean spec
  second causes exactly one extra call and yields the clean spec; a
  `FakeLLMClient` whose second response is invalid falls back to the first
  valid spec (no `CodegenError`).
- **CLI** (`tests/test_cli_e2e.py` or the cli test file): `validate` on a
  linty spec prints warnings and still exits 0.
- **drift** (`tests/test_skill_reference_current.py`): regenerate
  `skill/reference/*.md` after the three new components join the catalog.

## Risks / non-goals

- Auto-clamp is post-hoc: it scales an overflowing group after it's on screen.
  For component beats the mobject is clamped before animation only if we clamp
  in build; the chosen design clamps after the beat renders, so a genuinely
  oversized component could show one frame at full size before the clamp. This
  is acceptable — the common case is a no-op, and the alternative (clipping) is
  worse. If jank appears in the eval, a follow-up can clamp component builds
  pre-animation.
- Lint heuristics (char counts, `Text(` counting) are conservative and
  advisory; false negatives are fine, false positives only cost one re-ask.
- `TokenSequence` is the one domain-flavored component; it is generalized to
  any masked-sequence concept (mask/expand/delete/defer states), not tied to
  dLM, so it earns its place in a general framework.
