# Static Harness Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic layout-safety helpers + builder auto-clamp, three new theme-driven slide components (SectionDivider, TwoColumn, TokenSequence), and advisory spec lint (surfaced in the CLI and fed back into codegen for one self-correction re-ask), so a weak open-source model can't overflow the frame and gets concrete feedback on over-full specs.

**Architecture:** Builds on the merged phase-1 theme layer. A new `layout.py` holds pure geometry helpers used by components, raw beats, and a builder auto-clamp that guarantees no beat overflows the safe frame. Three new components follow the existing registered-Component pattern. A new `spec/lint.py` gives advisory warnings consumed by the CLI and by `generate_spec` for one optional re-ask.

**Tech Stack:** Python 3.13, manim 0.20.1, Pydantic, pytest. Spec: `docs/superpowers/specs/2026-06-07-static-harness-phase2-design.md`.

---

## File Structure

- **Create** `manim_skill/components/layout.py` — `fit_width`, `safe_area`, `stack`, `clamp_new_mobjects`. Geometry only.
- **Create** `manim_skill/components/section_divider.py`, `two_column.py`, `token_sequence.py` — three registered components.
- **Create** `manim_skill/spec/lint.py` — `LintWarning` + `lint_spec`.
- **Create** tests mirroring each.
- **Modify** `manim_skill/builder/spec_scene.py` — auto-clamp per beat.
- **Modify** `manim_skill/builder/raw.py` — inject layout helpers.
- **Modify** `manim_skill/llm/codegen.py` — lint re-ask + one VISUAL RULES line.
- **Modify** `manim_skill/llm/catalog.py` — add layout helper names to the hint.
- **Modify** `manim_skill/cli.py` — `validate` prints lint warnings.
- **Regenerate** `skill/reference/*.md` after the new components + catalog hint land.

Frame constants used throughout: `FRAME_WIDTH = 14.222222`, `FRAME_HEIGHT = 8.0` (manim 16:9 default).

---

## Task 1: Layout helpers

**Files:**
- Create: `manim_skill/components/layout.py`
- Test: `tests/components/test_layout.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/components/test_layout.py
from manim import Dot, Square, VGroup

from manim_skill.components.layout import (
    FRAME_HEIGHT,
    FRAME_WIDTH,
    clamp_new_mobjects,
    fit_width,
    safe_area,
    stack,
)
from manim_skill.components.theme import MARGIN


def test_fit_width_shrinks_overwide_and_leaves_narrow():
    wide = Square(side_length=20)
    fit_width(wide, 10)
    assert wide.width <= 10 + 1e-6
    narrow = Square(side_length=2)
    fit_width(narrow, 10)
    assert abs(narrow.width - 2) < 1e-6


def test_safe_area_scales_and_recenters_oversized():
    big = Square(side_length=20).shift([5, 3, 0])
    safe_area(big)
    usable_w = FRAME_WIDTH - 2 * MARGIN
    usable_h = FRAME_HEIGHT - 2 * MARGIN
    assert big.width <= usable_w + 1e-6
    assert big.height <= usable_h + 1e-6
    # fully inside the usable box
    assert big.get_left()[0] >= -usable_w / 2 - 1e-6
    assert big.get_right()[0] <= usable_w / 2 + 1e-6
    assert big.get_bottom()[1] >= -usable_h / 2 - 1e-6
    assert big.get_top()[1] <= usable_h / 2 + 1e-6


def test_safe_area_noop_for_small_centered():
    small = Dot().shift([1, 1, 0])
    before = small.get_center().copy()
    safe_area(small)
    assert (abs(small.get_center() - before) < 1e-6).all()


def test_stack_no_overlap_and_respects_gap():
    a, b, c = Square(side_length=1), Square(side_length=1), Square(side_length=1)
    group = stack([a, b, c], gap=0.5)
    assert isinstance(group, VGroup)
    assert len(group) == 3
    # adjacent members: lower's top is below upper's bottom by ~gap
    gap_ab = a.get_bottom()[1] - b.get_top()[1]
    assert abs(gap_ab - 0.5) < 1e-6


def test_clamp_new_mobjects_only_touches_new_ones():
    class FakeScene:
        def __init__(self, mobjects):
            self.mobjects = mobjects

    old = Dot()
    big = Square(side_length=20)
    scene = FakeScene([old, big])
    clamp_new_mobjects(scene, {old})
    assert big.width <= FRAME_WIDTH - 2 * MARGIN + 1e-6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/components/test_layout.py -q`
Expected: FAIL — `ModuleNotFoundError: manim_skill.components.layout`.

- [ ] **Step 3: Write minimal implementation**

```python
# manim_skill/components/layout.py
"""Deterministic geometry helpers — keep content inside the safe frame.

Separate from theme.py (color/font); this owns geometry. Used by components,
raw beats, and the builder's per-beat auto-clamp.
"""
from __future__ import annotations

from manim import DOWN, ORIGIN, RIGHT, UP, VGroup

from manim_skill.components.theme import GAP, MARGIN

FRAME_WIDTH = 14.222222
FRAME_HEIGHT = 8.0


def fit_width(mobj, max_width):
    """Scale mobj down so its width <= max_width (no-op if already narrower)."""
    if mobj.width > max_width and mobj.width > 0:
        mobj.scale_to_fit_width(max_width)
    return mobj


def safe_area(mobj, *, frame_width=FRAME_WIDTH, frame_height=FRAME_HEIGHT, margin=MARGIN):
    """Scale + recenter mobj so its bounding box lies within the margin-safe
    frame. No-op when it already fits."""
    usable_w = frame_width - 2 * margin
    usable_h = frame_height - 2 * margin
    if mobj.width > usable_w or mobj.height > usable_h:
        if mobj.width > 0 and mobj.height > 0:
            scale = min(usable_w / mobj.width, usable_h / mobj.height)
            mobj.scale(scale)
    cx, cy, _ = mobj.get_center()
    max_cx = max(0.0, usable_w / 2 - mobj.width / 2)
    max_cy = max(0.0, usable_h / 2 - mobj.height / 2)
    new_cx = max(-max_cx, min(max_cx, cx))
    new_cy = max(-max_cy, min(max_cy, cy))
    mobj.shift(RIGHT * (new_cx - cx) + UP * (new_cy - cy))
    return mobj


def stack(mobjs, *, gap=GAP, center=True):
    """Vertically arrange mobjs with a guaranteed gap so they never overlap."""
    group = VGroup(*mobjs)
    group.arrange(DOWN, buff=gap)
    if center:
        group.move_to(ORIGIN)
    return group


def clamp_new_mobjects(scene, before):
    """Clamp the mobjects added since `before` into the safe frame, as a group."""
    new = [m for m in scene.mobjects if m not in before]
    if new:
        safe_area(VGroup(*new))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/components/test_layout.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/components/layout.py tests/components/test_layout.py
git commit -m "feat(layout): fit_width, safe_area, stack, clamp_new_mobjects"
```

---

## Task 2: Builder auto-clamp

**Files:**
- Modify: `manim_skill/builder/spec_scene.py` (`_render_beat`)
- Test: `tests/builder/test_spec_scene.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/builder/test_spec_scene.py`:

```python
def test_render_beat_clamps_oversized_new_mobject(monkeypatch):
    from manim import Square
    from manim_skill.builder.spec_scene import SpecScene
    from manim_skill.components.layout import FRAME_WIDTH
    from manim_skill.components.theme import MARGIN
    from manim_skill.spec.schema import Beat

    scene = SpecScene()
    # stub the scene's play/wait/camera so _render_beat runs without a full render
    monkeypatch.setattr(scene, "play", lambda *a, **k: None)
    monkeypatch.setattr(scene, "wait", lambda *a, **k: None)

    # a raw beat that adds an oversized square
    beat = Beat(component="raw", code="self.add(Square(side_length=30))")
    scene._render_beat(beat)

    squares = [m for m in scene.mobjects if m.__class__.__name__ == "Square"]
    assert squares, "square should be on the scene"
    assert squares[0].width <= FRAME_WIDTH - 2 * MARGIN + 1e-6
```

Note: if `_render_beat`'s final `FadeOut` loop (it fades out all mobjects at the end) removes the square before the assertion, the stubbed `play` (a no-op) prevents the fade from actually clearing `self.mobjects` only if removal is done via `self.remove`. Read `_render_beat`: it calls `self.play(*[FadeOut(m) ...])` — with `play` stubbed to no-op, mobjects are NOT removed, so the square remains for the assertion. If the method also calls `self.remove(...)`, stub that to no-op too.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/builder/test_spec_scene.py -q -k clamp`
Expected: FAIL — the square keeps width 30 (no clamp yet).

- [ ] **Step 3: Write minimal implementation**

In `manim_skill/builder/spec_scene.py`, add the import and wrap `_render_beat` so it snapshots before, renders, then clamps the new mobjects before the caption:

```python
from manim_skill.components.layout import clamp_new_mobjects

    def _render_beat(self, beat: Beat) -> None:
        before = set(self.mobjects)
        if beat.component == "raw":
            exec_raw(beat.code or "", self)
        else:
            component = registry.get(beat.component)
            params = component.Params.model_validate(beat.params)
            mobject = component.build(params)
            component.animate(self, mobject, params)

        clamp_new_mobjects(self, before)

        if beat.caption:
            caption = _build_caption(beat.caption)
            self.play(FadeIn(caption))

        if beat.camera:
            apply_camera(self, beat.camera)

        if beat.duration:
            self.wait(beat.duration)

        if self.mobjects:
            self.play(*[FadeOut(m) for m in list(self.mobjects)])
```

(Only the `before = ...` snapshot and the `clamp_new_mobjects(self, before)` call are new; the rest is the existing body.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/builder/test_spec_scene.py -q`
Expected: PASS (existing + new).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/builder/spec_scene.py tests/builder/test_spec_scene.py
git commit -m "feat(builder): auto-clamp each beat's content into the safe frame"
```

---

## Task 3: SectionDivider component

**Files:**
- Create: `manim_skill/components/section_divider.py`
- Test: `tests/components/test_section_divider.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/components/test_section_divider.py
import pytest
from manim import Text, VGroup

from manim_skill.render.docker_render import render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec


def test_section_divider_builds_title_with_display_font():
    from manim_skill.components.section_divider import (
        SectionDivider,
        SectionDividerParams,
    )
    from manim_skill.components.theme import FONT_DISPLAY

    comp = SectionDivider()
    mobj = comp.build(SectionDividerParams(number=1, title="Intro", subtitle="x"))
    assert isinstance(mobj, VGroup)
    texts = [m for m in mobj if isinstance(m, Text)]
    assert any("Intro" in t.text and t.font == FONT_DISPLAY for t in texts)


def test_section_divider_is_registered():
    import manim_skill.components.section_divider  # noqa: F401
    from manim_skill.components import base

    assert "SectionDivider" in base.all_names()


@pytest.mark.docker
def test_section_divider_renders_in_docker(tmp_path):
    spec = SceneSpec(
        title="T",
        beats=[
            Beat(
                component="SectionDivider",
                params={"number": 1, "title": "Chapter One", "subtitle": "intro"},
                duration=1.0,
            )
        ],
    )
    mp4 = render_spec_to_mp4(spec, tmp_path, quality="low")
    assert mp4.exists()
    assert mp4.stat().st_size > 20_000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/components/test_section_divider.py -q -k "not docker"`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Write minimal implementation**

```python
# manim_skill/components/section_divider.py
from __future__ import annotations

from manim import LEFT, RIGHT, UP, FadeIn, Line, Mobject, Scene
from pydantic import BaseModel

from manim_skill.components.base import Component, register
from manim_skill.components.layout import safe_area, stack
from manim_skill.components.theme import (
    THEME,
    body_text,
    label_text,
    title_text,
)


class SectionDividerParams(BaseModel):
    number: int | None = None
    title: str
    subtitle: str | None = None


@register
class SectionDivider(Component):
    name = "SectionDivider"
    Params = SectionDividerParams

    def build(self, params: SectionDividerParams) -> Mobject:
        parts = [Line(LEFT * 3, RIGHT * 3, color=THEME.RULE, stroke_width=1)]
        if params.number is not None:
            parts.append(label_text(f"§ {params.number:02d}", color=THEME.PRIMARY))
        parts.append(title_text(params.title, size=44))
        if params.subtitle:
            parts.append(body_text(params.subtitle, size=24))
        parts.append(Line(LEFT * 3, RIGHT * 3, color=THEME.RULE, stroke_width=1))
        return safe_area(stack(parts, gap=0.35))

    def animate(self, scene: Scene, mobject: Mobject, params: SectionDividerParams) -> None:
        scene.play(FadeIn(mobject, shift=UP * 0.3))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/components/test_section_divider.py -q -k "not docker"`
Expected: PASS (2 non-docker tests).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/components/section_divider.py tests/components/test_section_divider.py
git commit -m "feat(SectionDivider): themed chapter-divider component"
```

---

## Task 4: TwoColumn component

**Files:**
- Create: `manim_skill/components/two_column.py`
- Test: `tests/components/test_two_column.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/components/test_two_column.py
import pytest
from manim import Text, VGroup

from manim_skill.render.docker_render import render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec


def test_two_column_builds_all_lines():
    from manim_skill.components.two_column import TwoColumn, TwoColumnParams

    comp = TwoColumn()
    mobj = comp.build(
        TwoColumnParams(
            left_title="A", right_title="B", left=["a1", "a2"], right=["b1"]
        )
    )
    texts = [t.text for t in mobj.get_family() if isinstance(t, Text)]
    joined = " ".join(texts)
    for token in ("a1", "a2", "b1"):
        assert token in joined


def test_two_column_is_registered():
    import manim_skill.components.two_column  # noqa: F401
    from manim_skill.components import base

    assert "TwoColumn" in base.all_names()


@pytest.mark.docker
def test_two_column_renders_in_docker(tmp_path):
    spec = SceneSpec(
        title="T",
        beats=[
            Beat(
                component="TwoColumn",
                params={
                    "left_title": "AR",
                    "right_title": "dLM",
                    "left": ["sequential", "slow"],
                    "right": ["parallel", "fast"],
                },
                duration=1.0,
            )
        ],
    )
    mp4 = render_spec_to_mp4(spec, tmp_path, quality="low")
    assert mp4.exists()
    assert mp4.stat().st_size > 20_000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/components/test_two_column.py -q -k "not docker"`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Write minimal implementation**

```python
# manim_skill/components/two_column.py
from __future__ import annotations

from manim import DOWN, RIGHT, UP, FadeIn, Line, Mobject, Scene, VGroup
from pydantic import BaseModel, Field

from manim_skill.components.base import Component, register
from manim_skill.components.layout import safe_area, stack
from manim_skill.components.theme import THEME, body_text, title_text


class TwoColumnParams(BaseModel):
    left_title: str | None = None
    right_title: str | None = None
    left: list[str] = Field(default_factory=list)
    right: list[str] = Field(default_factory=list)


def _column(title: str | None, lines: list[str]) -> Mobject:
    parts = []
    if title:
        parts.append(title_text(title, size=30))
    for line in lines:
        parts.append(body_text(line, size=24))
    return stack(parts, gap=0.3) if parts else VGroup()


@register
class TwoColumn(Component):
    name = "TwoColumn"
    Params = TwoColumnParams

    def build(self, params: TwoColumnParams) -> Mobject:
        left_col = _column(params.left_title, params.left)
        right_col = _column(params.right_title, params.right)
        divider = Line(UP * 2, DOWN * 2, color=THEME.RULE, stroke_width=1)
        group = VGroup(left_col, divider, right_col).arrange(RIGHT, buff=0.8)
        return safe_area(group)

    def animate(self, scene: Scene, mobject: Mobject, params: TwoColumnParams) -> None:
        scene.play(FadeIn(mobject))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/components/test_two_column.py -q -k "not docker"`
Expected: PASS (2 non-docker tests).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/components/two_column.py tests/components/test_two_column.py
git commit -m "feat(TwoColumn): themed two-column comparison component"
```

---

## Task 5: TokenSequence component

**Files:**
- Create: `manim_skill/components/token_sequence.py`
- Test: `tests/components/test_token_sequence.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/components/test_token_sequence.py
import pytest
from manim import VGroup

from manim_skill.render.docker_render import render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec


def test_token_sequence_builds_one_box_per_token():
    from manim_skill.components.token_sequence import (
        TokenSequence,
        TokenSequenceParams,
    )

    comp = TokenSequence()
    mobj = comp.build(
        TokenSequenceParams(
            tokens=[
                {"text": "the", "state": "normal"},
                {"text": "?", "state": "masked"},
                {"text": "cat", "state": "delete"},
            ]
        )
    )
    assert isinstance(mobj, VGroup)
    assert len(mobj) == 3


def test_token_sequence_is_registered():
    import manim_skill.components.token_sequence  # noqa: F401
    from manim_skill.components import base

    assert "TokenSequence" in base.all_names()


@pytest.mark.docker
def test_token_sequence_renders_in_docker(tmp_path):
    spec = SceneSpec(
        title="T",
        beats=[
            Beat(
                component="TokenSequence",
                params={
                    "tokens": [
                        {"text": "the", "state": "normal"},
                        {"text": "?", "state": "masked"},
                        {"text": "new", "state": "expand"},
                        {"text": "cat", "state": "delete"},
                    ]
                },
                duration=1.0,
            )
        ],
    )
    mp4 = render_spec_to_mp4(spec, tmp_path, quality="low")
    assert mp4.exists()
    assert mp4.stat().st_size > 20_000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/components/test_token_sequence.py -q -k "not docker"`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Write minimal implementation**

```python
# manim_skill/components/token_sequence.py
from __future__ import annotations

from typing import Literal

from manim import RIGHT, FadeIn, LaggedStart, Mobject, Rectangle, Scene, VGroup
from pydantic import BaseModel, Field

from manim_skill.components.base import Component, register
from manim_skill.components.layout import safe_area
from manim_skill.components.theme import THEME, label_text

_State = Literal["normal", "masked", "expand", "delete", "defer"]

# state -> (stroke_color, fill_color, text_color)
_STYLES: dict[str, tuple[str, str, str]] = {
    "normal": (THEME.PRIMARY, THEME.BG, THEME.INK),
    "masked": (THEME.RULE, THEME.BG_CODE, THEME.INK_FAINT),
    "expand": (THEME.PRIMARY_SOFT, THEME.HIGHLIGHT, THEME.INK),
    "delete": (THEME.WARN, THEME.BG_CARD, THEME.WARN),
    "defer": (THEME.INK_FAINT, THEME.BG_CODE, THEME.INK_FAINT),
}


class Token(BaseModel):
    text: str = ""
    state: _State = "normal"


class TokenSequenceParams(BaseModel):
    tokens: list[Token] = Field(default_factory=list)


def _token_box(token: Token) -> Mobject:
    stroke, fill, text_color = _STYLES.get(token.state, _STYLES["normal"])
    box = Rectangle(
        width=0.9,
        height=0.7,
        stroke_color=stroke,
        stroke_width=2,
        fill_color=fill,
        fill_opacity=1,
    )
    if token.text:
        label = label_text(token.text, size=18, color=text_color)
        label.move_to(box.get_center())
        return VGroup(box, label)
    return box


@register
class TokenSequence(Component):
    name = "TokenSequence"
    Params = TokenSequenceParams

    def build(self, params: TokenSequenceParams) -> Mobject:
        row = VGroup(*[_token_box(t) for t in params.tokens])
        if len(row) > 0:
            row.arrange(RIGHT, buff=0.15)
        return safe_area(row)

    def animate(self, scene: Scene, mobject: Mobject, params: TokenSequenceParams) -> None:
        if len(mobject) > 0:
            scene.play(LaggedStart(*[FadeIn(b) for b in mobject], lag_ratio=0.15))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/components/test_token_sequence.py -q -k "not docker"`
Expected: PASS (2 non-docker tests).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/components/token_sequence.py tests/components/test_token_sequence.py
git commit -m "feat(TokenSequence): themed masked-token-row component"
```

---

## Task 6: Spec lint

**Files:**
- Create: `manim_skill/spec/lint.py`
- Test: `tests/spec/test_lint.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/spec/test_lint.py
from manim_skill.spec.lint import lint_spec
from manim_skill.spec.schema import Beat, SceneSpec


def _spec(beats):
    return SceneSpec(title="t", beats=beats)


def test_clean_spec_has_no_warnings():
    spec = _spec([Beat(component="TextBeat", params={"text": "hi"}, caption="short")])
    assert lint_spec(spec) == []


def test_long_caption_warns():
    spec = _spec([Beat(component="TextBeat", params={"text": "x"}, caption="w " * 40)])
    codes = [w.code for w in lint_spec(spec)]
    assert "caption_too_long" in codes


def test_too_many_bullets_warns():
    spec = _spec(
        [Beat(component="TextBeat", params={"text": "x", "bullets": [str(i) for i in range(7)]})]
    )
    codes = [w.code for w in lint_spec(spec)]
    assert "beat_text_overload" in codes


def test_raw_background_and_italic_warn():
    spec = _spec(
        [
            Beat(component="raw", code="self.camera.background_color = '#000000'"),
            Beat(component="raw", code="t = Text('x', slant=ITALIC)\nself.add(t)"),
        ]
    )
    codes = [w.code for w in lint_spec(spec)]
    assert "raw_sets_background" in codes
    assert "raw_uses_italic" in codes


def test_lint_never_raises_on_empty_beats():
    assert lint_spec(SceneSpec(title="t", beats=[])) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/spec/test_lint.py -q`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Write minimal implementation**

```python
# manim_skill/spec/lint.py
"""Advisory static lint for a scene spec. Never raises, never blocks —
surfaced in the CLI and fed back into codegen for one self-correction re-ask.
"""
from __future__ import annotations

from dataclasses import dataclass

from manim_skill.spec.schema import SceneSpec

CAPTION_MAX_CHARS = 60
MAX_BULLETS = 6
MAX_RAW_TEXT_CALLS = 4
_RAW_TEXT_TOKENS = (
    "Text(", "MathTex(", "Tex(",
    "title_text(", "body_text(", "caption_text(", "label_text(",
)


@dataclass
class LintWarning:
    beat_index: int
    code: str
    message: str


def lint_spec(spec: SceneSpec) -> list[LintWarning]:
    warnings: list[LintWarning] = []
    for i, beat in enumerate(spec.beats):
        if beat.caption and len(beat.caption) > CAPTION_MAX_CHARS:
            warnings.append(
                LintWarning(
                    i, "caption_too_long",
                    f"caption is {len(beat.caption)} chars (>{CAPTION_MAX_CHARS}); "
                    "keep it to a few words",
                )
            )
        if beat.component == "TextBeat":
            bullets = (beat.params or {}).get("bullets") or []
            if len(bullets) > MAX_BULLETS:
                warnings.append(
                    LintWarning(
                        i, "beat_text_overload",
                        f"{len(bullets)} bullets (>{MAX_BULLETS}); split across beats",
                    )
                )
        if beat.component == "raw":
            code = beat.code or ""
            n = sum(code.count(tok) for tok in _RAW_TEXT_TOKENS)
            if n > MAX_RAW_TEXT_CALLS:
                warnings.append(
                    LintWarning(
                        i, "beat_text_overload",
                        f"{n} text elements in one raw beat (>{MAX_RAW_TEXT_CALLS}); "
                        "fewer per beat",
                    )
                )
            if "background_color" in code:
                warnings.append(
                    LintWarning(
                        i, "raw_sets_background",
                        "raw beat sets background_color; the builder owns the "
                        "themed background",
                    )
                )
            if "ITALIC" in code or "italic=True" in code:
                warnings.append(
                    LintWarning(
                        i, "raw_uses_italic",
                        "raw beat uses italics; the visual rules ban italics",
                    )
                )
    return warnings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/spec/test_lint.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/spec/lint.py tests/spec/test_lint.py
git commit -m "feat(lint): advisory static spec lint"
```

---

## Task 7: CLI validate prints lint warnings

**Files:**
- Modify: `manim_skill/cli.py` (`_cmd_validate`, ~lines 49-55)
- Test: `tests/test_cli_e2e.py`

- [ ] **Step 1: Write the failing test**

First read `tests/test_cli_e2e.py` for how it invokes the CLI (`from manim_skill.cli import main` and `main([...])`, capturing output via `capsys`). Append, matching that style:

```python
def test_validate_prints_lint_warnings_but_exits_zero(tmp_path, capsys):
    import json
    from manim_skill.cli import main

    spec = {
        "title": "t",
        "aspect_ratio": "16:9",
        "beats": [{"component": "TextBeat", "params": {"text": "x"}, "caption": "w " * 40}],
    }
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(spec), encoding="utf-8")

    rc = main(["validate", str(p)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "caption_too_long" in (captured.out + captured.err)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_e2e.py -q -k lint`
Expected: FAIL — no warning printed.

- [ ] **Step 3: Write minimal implementation**

In `manim_skill/cli.py`, extend `_cmd_validate` to run lint after a successful validate:

```python
def _cmd_validate(args) -> int:
    try:
        spec = _load_spec(args.spec)
    except (SpecParseError, SpecValidationError, OSError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {len(spec.beats)} beat(s), title={spec.title!r}")
    from manim_skill.spec.lint import lint_spec

    for w in lint_spec(spec):
        print(f"  warning: beat {w.beat_index}: {w.code} — {w.message}", file=sys.stderr)
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli_e2e.py -q -k lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add manim_skill/cli.py tests/test_cli_e2e.py
git commit -m "feat(cli): validate surfaces advisory lint warnings"
```

---

## Task 8: Codegen lint re-ask

**Files:**
- Modify: `manim_skill/llm/codegen.py` (`generate_spec`)
- Test: `tests/llm/test_codegen.py`

Read `tests/llm/test_codegen.py` and `tests/llm/test_client.py`/`tests/conftest.py` first for the `FakeLLMClient` definition. The existing `FakeLLMClient(response=...)` returns one fixed string. For this task you need a multi-response double. If `FakeLLMClient` already supports a `responses` list (queue), use it; otherwise define a tiny local double in the test:

```python
class _ScriptedClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def complete(self, system, user):
        self.calls.append((system, user))
        return self._responses.pop(0)
```

- [ ] **Step 1: Write the failing test**

Append to `tests/llm/test_codegen.py` (reuse `_CONCEPT`; build spec JSON strings inline):

```python
def test_lint_warning_triggers_one_reask_and_returns_clean_spec():
    long_caption = "word " * 40
    linty = (
        '{"title":"D","aspect_ratio":"16:9","beats":'
        '[{"component":"TextBeat","params":{"text":"x"},"caption":"' + long_caption + '"}]}'
    )
    clean = (
        '{"title":"D","aspect_ratio":"16:9","beats":'
        '[{"component":"TextBeat","params":{"text":"x"},"caption":"short"}]}'
    )
    client = _ScriptedClient([linty, clean])
    spec = generate_spec(client, _CONCEPT, catalog="(catalog)")
    assert len(client.calls) == 2  # first valid+linty, then the lint re-ask
    assert spec.beats[0].caption == "short"


def test_lint_reask_falls_back_to_first_valid_when_second_invalid():
    long_caption = "word " * 40
    linty = (
        '{"title":"D","aspect_ratio":"16:9","beats":'
        '[{"component":"TextBeat","params":{"text":"x"},"caption":"' + long_caption + '"}]}'
    )
    client = _ScriptedClient([linty, "not json at all"])
    spec = generate_spec(client, _CONCEPT, catalog="(catalog)")
    assert len(client.calls) == 2
    assert spec.beats[0].caption.startswith("word")  # fell back to the first valid spec
```

(Put the `_ScriptedClient` class near the top of the test file if not already present.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/llm/test_codegen.py -q -k lint`
Expected: FAIL — only one call made; no re-ask logic.

- [ ] **Step 3: Write minimal implementation**

Rewrite `generate_spec` in `manim_skill/llm/codegen.py` to add the advisory lint re-ask after a valid spec:

```python
from manim_skill.spec.lint import lint_spec


def generate_spec(
    client: LLMClient,
    concept: ConceptCandidate,
    catalog: str,
) -> SceneSpec:
    """Stage 2: turn one concept into a validated SceneSpec.

    One LLM call; on a parse/validation failure, re-ask once with the error.
    After a valid spec, run advisory lint; if it has warnings, re-ask once
    more with the warnings — but never let lint turn a valid spec into an
    error (fall back to the first valid spec if the lint re-ask fails).
    """
    system = _CODEGEN_SYSTEM.replace("__CATALOG__", catalog)
    base_user = _build_user_prompt(concept)

    last_error = ""
    valid_spec: SceneSpec | None = None
    for attempt in range(2):
        if attempt == 0:
            user = base_user
        else:
            user = (
                f"{base_user}\n\nYour previous response was rejected: "
                f"{last_error}\nReturn a corrected scene spec JSON, nothing else."
            )
        raw = client.complete(system, user)
        try:
            valid_spec = validate_spec(parse_spec_text(raw))
            break
        except (SpecParseError, SpecValidationError) as exc:
            last_error = str(exc)

    if valid_spec is None:
        raise CodegenError(
            f"codegen failed for concept {concept.concept!r} after 2 "
            f"attempts: {last_error}"
        )

    warnings = lint_spec(valid_spec)
    if warnings:
        issues = "; ".join(f"beat {w.beat_index}: {w.message}" for w in warnings)
        lint_user = (
            f"{base_user}\n\nYour scene spec is valid but has these issues: "
            f"{issues}\nReturn a cleaner scene spec JSON that fixes them, "
            "nothing else."
        )
        raw = client.complete(system, lint_user)
        try:
            return validate_spec(parse_spec_text(raw))
        except (SpecParseError, SpecValidationError):
            return valid_spec

    return valid_spec
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/llm/test_codegen.py -q`
Expected: PASS — the two new lint tests AND all existing tests. The existing
`test_generate_spec_valid_first_try` expects exactly 1 call: confirm the
existing `_VALID_SPEC` is lint-clean (short/no caption, ≤6 bullets). If it now
triggers a lint warning, that is a real signal — but `_VALID_SPEC` is a minimal
spec and should be clean; if a pre-existing test breaks on call count, inspect
`_VALID_SPEC` and confirm it has no long caption before adjusting anything.

- [ ] **Step 5: Commit**

```bash
git add manim_skill/llm/codegen.py tests/llm/test_codegen.py
git commit -m "feat(codegen): one advisory-lint self-correction re-ask"
```

---

## Task 9: Raw-beat layout helpers + prompt/catalog + regenerate docs

**Files:**
- Modify: `manim_skill/builder/raw.py`
- Modify: `manim_skill/llm/codegen.py` (`_CODEGEN_SYSTEM` — one line)
- Modify: `manim_skill/llm/catalog.py` (hint line)
- Test: `tests/builder/test_raw.py`, `tests/llm/test_codegen.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/builder/test_raw.py`:

```python
def test_layout_helpers_available_in_raw_namespace():
    from unittest.mock import MagicMock
    from manim_skill.builder.raw import exec_raw

    scene = MagicMock()
    exec_raw(
        "sq = Square()\nsafe_area(sq)\nstack([sq])\nfit_width(sq, 5)\nself.add(sq)",
        scene,
    )
    scene.add.assert_called_once()
```

Append to `tests/llm/test_codegen.py`:

```python
def test_prompt_mentions_layout_helpers():
    client = FakeLLMClient(response=_VALID_SPEC)
    generate_spec(client, _CONCEPT, catalog="(catalog)")
    system = client.calls[0][0]
    assert "safe_area" in system or "stack(" in system
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/builder/test_raw.py -q -k layout` and `python -m pytest tests/llm/test_codegen.py -q -k layout_helpers`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

(a) In `manim_skill/builder/raw.py`, add a layout import and inject the three helpers. After the existing theme-name injection loop, add:

```python
from manim_skill.components import layout as _layout

    for _name in ("fit_width", "safe_area", "stack"):
        namespace[_name] = getattr(_layout, _name)
```

(b) In `manim_skill/llm/codegen.py` `_CODEGEN_SYSTEM`, add one line to the VISUAL RULES block (after the theme-colors line):

```
- Layout helpers are also in scope for raw beats: wrap your top mobject with
  safe_area(...) to keep it on-screen, and stack([...]) to space items.
```

(c) In `manim_skill/llm/catalog.py`, extend the raw-beat hint line to mention the helpers — append to that string: `" Layout helpers: safe_area, stack, fit_width."`

- [ ] **Step 4: Run tests + regenerate skill docs**

```bash
python -m pytest tests/builder/test_raw.py tests/llm/test_codegen.py -q
python -m manim_skill.cli gen-skill-docs
python -m pytest tests/test_skill_reference_current.py -q
```
Expected: all PASS. `gen-skill-docs` regenerates `skill/reference/*.md` to include the three new components (SectionDivider, TwoColumn, TokenSequence) and the updated hint; the drift test must be green.

- [ ] **Step 5: Commit**

```bash
git add manim_skill/builder/raw.py manim_skill/llm/codegen.py manim_skill/llm/catalog.py tests/builder/test_raw.py tests/llm/test_codegen.py skill/reference
git commit -m "feat(raw,prompt): expose layout helpers + regenerate skill docs"
```

---

## Task 10: Full-suite verification

- [ ] **Step 1: Fast suite**

Run: `python -m pytest -m "not docker" -q`
Expected: PASS — all phase-1 tests plus the new layout/builder/component/lint/
codegen/cli tests. A failing skill-reference drift test means `gen-skill-docs`
wasn't committed in Task 9 — re-run it and commit.

- [ ] **Step 2: Rebuild image + docker suite**

The three new components render in containers, so re-verify the docker path.

```bash
docker build -t manim-skill:latest -f docker/Dockerfile .
python -m pytest -m docker -q
```
Expected: PASS — now 26 docker tests (23 prior + the 3 new component render
tests). IBM Plex fonts are already in the image.

- [ ] **Step 3: Final commit (only if anything drifted)**

```bash
python -m pytest tests/test_skill_reference_current.py -q
git add -A
git commit -m "test: verify phase-2 harness across fast and docker suites" || echo "nothing to commit"
```

---

## Self-Review (completed by plan author)

- **Spec coverage:** A (helpers)=Task 1; A' (builder auto-clamp)=Task 2;
  B (SectionDivider/TwoColumn/TokenSequence)=Tasks 3/4/5; C lint module=Task 6,
  CLI surface=Task 7, codegen re-ask=Task 8; connected changes (raw namespace,
  prompt line, catalog hint, doc regen)=Task 9; verification=Task 10. All spec
  sections mapped.
- **Placeholders:** none — every code step shows complete code and exact
  commands. The one conditional (Task 8 call-count of `_VALID_SPEC`) names the
  exact thing to check rather than hand-waving.
- **Type consistency:** `fit_width`, `safe_area`, `stack`, `clamp_new_mobjects`,
  `FRAME_WIDTH`/`FRAME_HEIGHT` (Task 1) are referenced verbatim in Tasks 2/3/4/5/9;
  `LintWarning`/`lint_spec` (Task 6) referenced verbatim in Tasks 7/8; component
  `Params` names match their tests; `_ScriptedClient` defined and used in Task 8.
