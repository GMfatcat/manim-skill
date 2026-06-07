# Static Harness Theme Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crystallize the dlm-polish conventions into a framework-level theme (semantic palette + IBM Plex fonts + safe text factories) that the 14 styled components, the builder, raw beats, and the codegen prompt all draw from, so a weak open-source model produces consistent, kerning-safe output by default.

**Architecture:** A new deterministic `theme.py` module exposes a frozen `Theme` dataclass (NEUTRAL default + DLM_WARM preset, env-selected), font constants carrying the kerning workaround, and four safe-default text factories. Components stop hardcoding colors/fonts and read the theme; the builder sets the themed background and routes captions through the theme font; raw beats get the theme names in scope; the codegen prompt gains visual rules. No spec-schema change, no extra model calls.

**Tech Stack:** Python 3.13, manim 0.20.1, Pydantic, pytest. Spec: `docs/superpowers/specs/2026-06-07-static-harness-theme-design.md`.

---

## File Structure

- **Create** `manim_skill/components/theme.py` — the theme module (palette, fonts, factories). One responsibility: visual constants + text factories.
- **Create** `tests/components/test_theme.py` — theme unit tests.
- **Modify** `manim_skill/builder/spec_scene.py` — set themed background; caption via `caption_text`.
- **Modify** `manim_skill/builder/raw.py` — inject theme names into the raw-beat namespace.
- **Modify** `manim_skill/llm/codegen.py` — VISUAL RULES block in `_CODEGEN_SYSTEM`.
- **Modify** `manim_skill/llm/catalog.py` — append theme token/factory names to the catalog.
- **Modify** the 15 component modules under `manim_skill/components/` — read style from the theme.
- **Modify** `tests/builder/test_spec_scene.py`, `tests/builder/test_raw.py`, `tests/llm/test_codegen.py` — new behavior.
- **Regenerate** `skill/reference/*.md` via `manim-skill gen-skill-docs` if the catalog text changes.

---

## Task 1: Theme module

**Files:**
- Create: `manim_skill/components/theme.py`
- Test: `tests/components/test_theme.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/components/test_theme.py
from manim import Text

from manim_skill.components.theme import (
    DLM_WARM,
    FONT_BODY,
    FONT_DISPLAY,
    FONT_MONO,
    NEUTRAL,
    Theme,
    body_text,
    caption_text,
    get_theme,
    label_text,
    title_text,
)


def test_presets_share_the_same_token_set():
    assert set(vars(NEUTRAL)) == set(vars(DLM_WARM))


def test_every_token_is_a_hex_color():
    for theme in (NEUTRAL, DLM_WARM):
        for value in vars(theme).values():
            assert isinstance(value, str) and value.startswith("#")


def test_get_theme_resolves_names_and_falls_back_to_neutral():
    assert get_theme("dlm_warm") is DLM_WARM
    assert get_theme("DLM_WARM") is DLM_WARM
    assert get_theme("neutral") is NEUTRAL
    assert get_theme("nonsense") is NEUTRAL
    assert get_theme(None) is NEUTRAL


def test_title_text_uses_display_font_at_floor_size():
    t = title_text("Hi")
    assert isinstance(t, Text)
    assert t.font == FONT_DISPLAY
    assert t.font_size == 48


def test_body_and_caption_use_body_font_and_are_not_italic():
    for factory, font, size in (
        (body_text, FONT_BODY, 28),
        (caption_text, FONT_BODY, 22),
    ):
        t = factory("hello")
        assert t.font == font
        assert t.font_size == size
        assert getattr(t, "slant", "NORMAL") == "NORMAL"


def test_label_text_uses_mono_font():
    t = label_text("x")
    assert t.font == FONT_MONO
    assert t.font_size == 18


def test_color_override_is_honored():
    t = title_text("Hi", color="#123456")
    # manim normalizes hex to uppercase ManimColor; compare via to_hex
    assert t.color.to_hex().lower() == "#123456"


def test_theme_is_frozen():
    import dataclasses
    import pytest

    with pytest.raises(dataclasses.FrozenInstanceError):
        NEUTRAL.BG = "#000000"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/components/test_theme.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'manim_skill.components.theme'`

- [ ] **Step 3: Write minimal implementation**

```python
# manim_skill/components/theme.py
"""Framework-level visual theme: semantic palette, fonts, text factories.

Crystallizes the dlm-polish conventions (see
docs/superpowers/specs/2026-06-07-static-harness-theme-design.md) so every
component, the builder, and raw beats share one deterministic look. No model
calls — this is the static harness a weak codegen model leans on.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from manim import BOLD, Text


@dataclass(frozen=True)
class Theme:
    BG: str
    BG_CARD: str
    BG_CODE: str
    INK: str
    INK_SOFT: str
    INK_FAINT: str
    PRIMARY: str
    PRIMARY_SOFT: str
    WARN: str
    HIGHLIGHT: str
    RULE: str


NEUTRAL = Theme(
    BG="#F7F6F3",
    BG_CARD="#EEEDE8",
    BG_CODE="#E8E7E1",
    INK="#1A1A1A",
    INK_SOFT="#44443F",
    INK_FAINT="#76746C",
    PRIMARY="#34597A",
    PRIMARY_SOFT="#5E7D94",
    WARN="#9A3B2E",
    HIGHLIGHT="#E8DCA8",
    RULE="#C9C5B8",
)

DLM_WARM = Theme(
    BG="#FBF8F1",
    BG_CARD="#F4F0E6",
    BG_CODE="#ECE7D9",
    INK="#1A1A1A",
    INK_SOFT="#4A4A48",
    INK_FAINT="#7A7872",
    PRIMARY="#1E4F5C",
    PRIMARY_SOFT="#3D7480",
    WARN="#8B3A2E",
    HIGHLIGHT="#F4E9C9",
    RULE="#C8C2B0",
)

_PRESETS = {"neutral": NEUTRAL, "dlm_warm": DLM_WARM}


def get_theme(name: str | None) -> Theme:
    """Resolve a preset name (case-insensitive) to a Theme; unknown -> NEUTRAL."""
    return _PRESETS.get((name or "neutral").lower(), NEUTRAL)


# Active theme, chosen once at import from the environment (mirrors the
# MANIM_SKILL_RENDER_QUALITY env-config pattern; the spec schema is untouched).
THEME = get_theme(os.environ.get("MANIM_SKILL_THEME"))

# Fonts. IBM Plex Latin is bundled in the docker image. Use the base family
# names ("IBM Plex Sans", not "...Sans TC") — the TC variant isn't in the
# IBM/plex repo, so Pango can't resolve it and falls back per-glyph, which
# breaks Latin kerning ("parallel" -> "para llel"). CJK glyphs fall through
# to the bundled Noto CJK automatically.
FONT_DISPLAY = "IBM Plex Sans"
FONT_BODY = "IBM Plex Serif"
FONT_MONO = "IBM Plex Mono"

# Layout spacing defaults (scene units). Richer layout helpers are a later phase.
GAP = 0.35
MARGIN = 0.6


def title_text(text: str, *, size: float = 48, color: str | None = None) -> Text:
    return Text(
        text, font=FONT_DISPLAY, weight=BOLD, font_size=size,
        color=color or THEME.INK,
    )


def body_text(text: str, *, size: float = 28, color: str | None = None) -> Text:
    return Text(text, font=FONT_BODY, font_size=size, color=color or THEME.INK_SOFT)


def caption_text(text: str, *, size: float = 22, color: str | None = None) -> Text:
    return Text(text, font=FONT_BODY, font_size=size, color=color or THEME.INK_SOFT)


def label_text(text: str, *, size: float = 18, color: str | None = None) -> Text:
    return Text(text, font=FONT_MONO, font_size=size, color=color or THEME.INK_FAINT)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/components/test_theme.py -q`
Expected: PASS (8 tests). If `t.color.to_hex()` errors on the manim version, switch the assertion to `t.color == ManimColor("#123456")` (`from manim import ManimColor`).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/components/theme.py tests/components/test_theme.py
git commit -m "feat(theme): framework-level palette, fonts, and text factories"
```

---

## Task 2: Builder sets themed background and routes caption through the theme

**Files:**
- Modify: `manim_skill/builder/spec_scene.py:22-33` (`_build_caption`), `:52-56` (`construct`)
- Test: `tests/builder/test_spec_scene.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/builder/test_spec_scene.py` (read the file first for its existing imports/fixtures; it already constructs a `SpecScene` against a spec env var):

```python
def test_caption_uses_theme_body_font():
    from manim_skill.builder.spec_scene import _build_caption
    from manim_skill.components.theme import FONT_BODY

    cap = _build_caption("a short caption")
    assert cap.font == FONT_BODY


def test_construct_sets_themed_background(tmp_path, monkeypatch):
    # Reuse whatever spec-writing helper the existing tests use; if there is
    # none, write a minimal one-beat spec to a temp file and point the env var
    # at it, mirroring the existing test setup in this file.
    import json
    from manim_skill.builder.spec_scene import SPEC_ENV_VAR, SpecScene
    from manim_skill.components.theme import THEME

    spec = {
        "title": "t",
        "aspect_ratio": "16:9",
        "beats": [{"component": "TextBeat", "params": {"text": "hi"}}],
    }
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    monkeypatch.setenv(SPEC_ENV_VAR, str(p))

    scene = SpecScene()
    scene.render()  # writes to a temp media dir; manim default config
    assert scene.camera.background_color.to_hex().lower() == THEME.BG.lower()
```

Note for the executor: if `scene.render()` is too heavy in unit context, assert the background another way — e.g. set it in a small `setup()`-style hook and assert after calling `construct` with a patched `load_spec_from_env`. Match the existing file's approach; keep it non-docker.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/builder/test_spec_scene.py -q -k "theme or background"`
Expected: FAIL — caption font is the manim default, background not set.

- [ ] **Step 3: Write minimal implementation**

In `manim_skill/builder/spec_scene.py`, change the caption builder to use the theme font and set the background in `construct`:

```python
# at top, with the other imports:
from manim_skill.components.theme import THEME, caption_text

# replace _build_caption's body:
def _build_caption(text: str) -> Text:
    """Build a bottom caption, in the theme body font, shrunk to fit if wide."""
    caption = caption_text(text, size=28)
    if caption.width > _CAPTION_MAX_WIDTH:
        caption.scale_to_fit_width(_CAPTION_MAX_WIDTH)
    caption.to_edge(DOWN)
    return caption

# in construct(), set the background before rendering beats:
    def construct(self) -> None:
        spec = load_spec_from_env()
        self.camera.background_color = THEME.BG
        self.camera.frame.save_state()
        for beat in spec.beats:
            self._render_beat(beat)
```

(`caption_text` returns a `Text`, so the `_CAPTION_MAX_WIDTH` scaling still applies. Keep the `Text` import — other code in the file may use it.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/builder/test_spec_scene.py -q`
Expected: PASS (existing + 2 new). 

- [ ] **Step 5: Commit**

```bash
git add manim_skill/builder/spec_scene.py tests/builder/test_spec_scene.py
git commit -m "feat(builder): themed background and theme-font captions"
```

---

## Task 3: Raw-beat namespace exposes the theme

**Files:**
- Modify: `manim_skill/builder/raw.py:29-41` (`exec_raw`)
- Test: `tests/builder/test_raw.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/builder/test_raw.py`:

```python
def test_theme_names_available_in_raw_namespace():
    from unittest.mock import MagicMock
    from manim_skill.builder.raw import exec_raw

    scene = MagicMock()
    # PRIMARY (a token), title_text (a factory), and FONT_MONO must resolve.
    exec_raw(
        "t = title_text('hi', color=PRIMARY)\n"
        "f = FONT_MONO\n"
        "self.add(t)",
        scene,
    )
    scene.add.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/builder/test_raw.py -q -k theme`
Expected: FAIL — `NameError: name 'title_text' is not defined`.

- [ ] **Step 3: Write minimal implementation**

In `manim_skill/builder/raw.py`, inject the theme names alongside the manim names:

```python
from manim_skill.components import theme as _theme

# inside exec_raw, after the manim-name loop:
    for _name in (
        "THEME",
        "FONT_DISPLAY", "FONT_BODY", "FONT_MONO",
        "GAP", "MARGIN",
        "title_text", "body_text", "caption_text", "label_text",
    ):
        namespace[_name] = getattr(_theme, _name)
    # the active theme's color tokens, by their semantic names:
    for _token, _value in vars(_theme.THEME).items():
        namespace[_token] = _value
    exec(_compile_raw(code), namespace)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/builder/test_raw.py -q`
Expected: PASS (existing + 1 new).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/builder/raw.py tests/builder/test_raw.py
git commit -m "feat(raw): expose theme tokens and text factories to raw beats"
```

---

## Task 4: Codegen prompt VISUAL RULES + catalog hints

**Files:**
- Modify: `manim_skill/llm/codegen.py:16-65` (`_CODEGEN_SYSTEM`)
- Modify: `manim_skill/llm/catalog.py:8-23` (`build_component_catalog`)
- Test: `tests/llm/test_codegen.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/llm/test_codegen.py` (reuse the existing `FakeLLMClient`, `_VALID_SPEC`, `_CONCEPT`, `generate_spec` imports at the top of that file):

```python
def test_codegen_system_prompt_includes_visual_rules():
    """Lock in the dlm-polish-derived visual guardrails for a weak model."""
    client = FakeLLMClient(response=_VALID_SPEC)
    generate_spec(client, _CONCEPT, catalog="(catalog)")
    system = client.calls[0][0]
    s = system.lower()

    # no italics
    assert "italic" in s
    # keep captions short
    assert "caption" in s and ("short" in s or "few words" in s)
    # use the theme colors / factories in raw beats, not hardcoded styling
    assert "theme" in s
    assert "title_text" in system or "PRIMARY" in system
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm/test_codegen.py::test_codegen_system_prompt_includes_visual_rules -v`
Expected: FAIL — the prompt has no visual-rules text yet.

- [ ] **Step 3: Write minimal implementation**

In `manim_skill/llm/codegen.py`, insert a VISUAL RULES block into `_CODEGEN_SYSTEM` just before the `Output ONLY the JSON object` line:

```python
VISUAL RULES — keep output clean for a small model; the framework already
themes everything, so do NOT fight it:
- DO NOT use italics anywhere.
- Keep each beat's "caption" short — a few words, not a sentence.
- DO NOT pack many lines of text into one beat. Fewer elements, more space.
- In raw beats, the theme is in scope: use the semantic colors (PRIMARY,
  INK, INK_SOFT, WARN, HIGHLIGHT, ...) and the text factories
  (title_text(...), body_text(...), caption_text(...), label_text(...))
  instead of hardcoded colors/fonts. DO NOT set a background — the builder
  already applies the themed background.
```

In `manim_skill/llm/catalog.py`, append a trailing hint block after the component blocks so the model knows the names exist:

```python
def build_component_catalog() -> str:
    blocks: list[str] = []
    for name in registry.all_names():
        component = registry.get(name)
        schema = component.Params.model_json_schema()
        blocks.append(
            f"### {name}\n"
            + json.dumps(schema, ensure_ascii=False, indent=2)
        )
    blocks.append(
        "### (raw-beat theme names)\n"
        "Available in raw beats: colors PRIMARY, PRIMARY_SOFT, INK, INK_SOFT, "
        "INK_FAINT, WARN, HIGHLIGHT, BG, BG_CARD, BG_CODE, RULE; fonts "
        "FONT_DISPLAY, FONT_BODY, FONT_MONO; factories title_text, body_text, "
        "caption_text, label_text."
    )
    return "\n\n".join(blocks)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/llm/test_codegen.py -q`
Expected: PASS (existing guard tests + the new one). The existing
`test_codegen_system_prompt_includes_raw_beat_guards` and
`..._latex_backslash_guard` must still pass — do not remove their text.

- [ ] **Step 5: Regenerate skill docs and commit**

```bash
manim-skill gen-skill-docs
pytest tests/test_skill_reference_current.py -q   # drift test must be green
git add manim_skill/llm/codegen.py manim_skill/llm/catalog.py tests/llm/test_codegen.py skill/reference
git commit -m "feat(prompt): visual rules + theme hints for raw-beat codegen"
```

---

## Task 5: Component refactor — worked example (TextBeat) + procedure

**The mapping rule (applies to every component in Tasks 5–6):**

| current style in a component | replace with |
|------------------------------|--------------|
| a body/header `Text(..., font_size=N)` | `title_text(..., size=N)` / `body_text(..., size=N)` / `caption_text` / `label_text` per role |
| primary/emphasis color (e.g. `BLUE`, a brand hex) | `THEME.PRIMARY` (secondary emphasis → `THEME.PRIMARY_SOFT`) |
| error/delete/red highlight | `THEME.WARN` |
| main text color / `WHITE`/`BLACK` body | `THEME.INK` (softer → `THEME.INK_SOFT`) |
| faint label/annotation color | `THEME.INK_FAINT` |
| highlight fill / banner | `THEME.HIGHLIGHT` |
| card/box fill | `THEME.BG_CARD`; code/cell fill `THEME.BG_CODE` |
| divider/grid line color | `THEME.RULE` |
| any `font=...` literal | the matching `FONT_*` constant |
| a component setting its own `camera.background_color` | **remove it** — the builder owns the background |

Preserve each component's geometry and animation; only the color/font/size
*sources* change. Do not invent new visual elements.

**Files:**
- Modify: `manim_skill/components/text_beat.py`
- Test: `tests/components/test_text_beat.py` (existing tests stay green)

- [ ] **Step 1: Write the failing test**

Append to `tests/components/test_text_beat.py`:

```python
def test_textbeat_uses_theme_display_font():
    from manim_skill.components.theme import FONT_DISPLAY
    comp = TextBeat()
    mobj = comp.build(TextBeatParams(text="Hello", style="title"))
    texts = [m for m in mobj if isinstance(m, Text)]
    assert texts and all(t.font == FONT_DISPLAY for t in texts)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/components/test_text_beat.py -q -k theme`
Expected: FAIL — current `Text(...)` calls use the manim default font.

- [ ] **Step 3: Write minimal implementation**

Rewrite `text_beat.py`'s `build` to use the factories:

```python
from manim_skill.components.theme import title_text

    def build(self, params: TextBeatParams) -> Mobject:
        group = VGroup()
        if params.style == "bullets":
            group.add(title_text(params.text, size=44))
            for bullet in params.bullets:
                group.add(title_text(f"• {bullet}", size=32))
            group.arrange(DOWN, aligned_edge=LEFT, buff=0.4)
        else:
            header_size = 56 if params.style == "title" else 36
            group.add(title_text(params.text, size=header_size))
            if params.subtitle:
                group.add(title_text(params.subtitle, size=32))
            group.arrange(DOWN, buff=0.4)
        return group
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/components/test_text_beat.py -q`
Expected: PASS (3 existing + 1 new).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/components/text_beat.py tests/components/test_text_beat.py
git commit -m "refactor(TextBeat): draw fonts from the theme"
```

---

## Task 6: Component refactor — remaining 14 modules

Apply the Task 5 mapping rule to each module below. **Each is its own
test-first cycle and its own commit.** For each component:

1. Read the module; note its hardcoded colors/fonts/sizes (`grep` for
   `font=`, `font_size`, `color=`, `fill_color`, `stroke_color`, color
   constants like `BLUE`, and any `background_color`).
2. **Write/extend a test** in the mirror `tests/components/test_<name>.py`
   asserting it pulls from the theme — assert on a **font constant** (e.g.
   `t.font == FONT_DISPLAY`) or that an emphasis mobject's color equals
   `THEME.PRIMARY` (`mobj.color.to_hex().lower() == THEME.PRIMARY.lower()`).
   **Assert on font/token, never on a raw hex literal** — the palette must
   stay tunable.
3. Run it, watch it fail.
4. Apply the mapping (import from `manim_skill.components.theme`), remove any
   self-set background.
5. Run `pytest tests/components/test_<name>.py -q` — existing + new green.
6. Commit: `refactor(<Name>): draw colors/fonts from the theme`.

Modules (each a sub-task — check off as completed):

- [ ] `attention_flow.py`
- [ ] `formula_breakdown.py`
- [ ] `formula_walkthrough.py`
- [ ] `function_plot.py`
- [ ] `geometry_anim.py`
- [ ] `graph_beat.py`
- [ ] `heatmap_beat.py`
- [ ] `matrix_op.py`
- [ ] `neural_net_diagram.py`
- [ ] `optimization_path.py`
- [ ] `pipeline_diagram.py`
- [ ] `plot_evolution.py`
- [ ] `table_beat.py`
- [ ] `code_walkthrough.py` — likely uses manim's `Code` mobject (no `font=`
  hardcode per the earlier grep); if so, only set `Code` theme params if
  trivially available, otherwise leave a one-line comment that `Code`
  styling is out of scope for phase 1 and commit no-op-free (skip if nothing
  to change).

**Note on `formula_breakdown.py` / `formula_walkthrough.py`:** these carry
LaTeX (`Tex`/`MathTex`). LaTeX color is set via `.set_color(THEME.PRIMARY)` /
the `color=` kwarg, not a font; do NOT change the formula font (the LaTeX
path is English-only and unrelated to the Pango kerning issue). Only theme
the surrounding labels/titles and any accent colors.

---

## Task 7: Full-suite verification

- [ ] **Step 1: Run the fast suite**

Run: `pytest -m "not docker" -q`
Expected: PASS — all previously-green tests plus the new theme/builder/raw/
codegen/component tests. Investigate any failure before proceeding; a
component test asserting an old hardcoded color is a test that must be
updated to the token assertion, not a reason to revert the refactor.

- [ ] **Step 2: Rebuild the image and run the docker suite (render-truth check)**

The theme changes how every component renders (fonts/colors), so the docker
render path must be re-verified.

Run:
```bash
docker build -t manim-skill:latest -f docker/Dockerfile .
pytest -m docker -q
```
Expected: PASS (23 tests, incl. `test_cjk_rendering` and the e2e/compose
tests). The IBM Plex fonts are already bundled in the image, so the theme's
font names resolve inside the container.

- [ ] **Step 3: Final commit (if any docs/skill-reference drifted)**

```bash
pytest tests/test_skill_reference_current.py -q
git add -A
git commit -m "test: verify static-harness theme across fast and docker suites"
```

---

## Self-Review (completed by plan author)

- **Spec coverage:** A=Task 1; B (component refactor)=Tasks 5–6; C (builder
  background)=Task 2; D (raw namespace)=Task 3; E (prompt+catalog)=Task 4;
  testing section=tests embedded per task + Task 7. All spec sections mapped.
- **Placeholders:** none — every code step shows the code; the component
  refactor is rule-driven (mapping table + worked example) because the
  per-file source colors are discovered by reading each file, which is the
  honest unit of work, not an omission.
- **Type consistency:** `Theme` fields, `get_theme`, `THEME`, `FONT_*`,
  `GAP`/`MARGIN`, and the four `*_text` factories are defined in Task 1 and
  referenced verbatim in Tasks 2–6.
