# BarChart Component Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a themed `BarChart` component (hand-built bars, no LaTeX) so bar-chart beats render via the robust component path instead of fragile `raw`, and seed a gold example so the few-shot mechanism offers it — closing the ORCA cost-cascade flywheel.

**Architecture:** A new auto-discovered component `manim_skill/components/bar_chart.py` modeled on `plot_evolution.py`: `values/labels/title/highlight` params validated by a Pydantic `model_validator`, rendered as themed `Rectangle` bars on a common baseline (NOT `manim.BarChart`, which pulls in LaTeX). Registration auto-updates the LLM catalog and the agent skill docs (regenerated, drift-tested). A `bar-comparison` gold example connects it to the golden-examples few-shot mechanism.

**Tech Stack:** Python 3.13, manim 0.20.1 (`Rectangle`/`Line`/`VGroup`), Pydantic, pytest (fast suite — building mobjects needs no Docker and no LaTeX).

---

## Background for the implementer

This is the third increment of the Contract-Gated Cascade framework (spec: `docs/superpowers/specs/2026-06-17-barchart-component-design.md`). The ORCA eval showed `gemma-4-31b` repeatedly failing the "performance gain" bar chart as `raw` code because there was no bar-chart component. Adding one moves those beats to the deterministic component path.

**Why hand-built bars, not `manim.BarChart`:** the built-in `BarChart` mobject renders y-axis numbers via LaTeX (`Tex`). On a box without LaTeX it raises `FileNotFoundError` at construction, it can't be unit-tested in the fast suite, and it contradicts the framework's deliberate LaTeX-avoidance. Hand-built `Rectangle` bars are pure mobjects: fast-suite testable and fully theme-controlled. (Verified: building the bars below triggers no LaTeX.)

Component conventions (from `manim_skill/components/plot_evolution.py`):
- A `<Name>Params(BaseModel)` and `@register class <Name>(Component)` with `name`, `Params`, `build(params) -> Mobject`, `animate(scene, mobject, params)`.
- `components/__init__.py` auto-discovers every module — no manual wiring.
- Theme via `manim_skill.components.theme`: `THEME.PRIMARY`, `THEME.PRIMARY_SOFT`, `THEME.RULE`, and text factories `body_text`, `label_text`.
- `spec/validate.py` validates each beat's params against the component's `Params`, so a `model_validator` error surfaces at spec-validation time.

Adding a component is drift-tested: `tests/test_skill_reference_current.py` fails unless `skill/reference/*.md` is regenerated via `manim-skill gen-skill-docs`.

Run the fast suite with: `pytest -m "not docker" -q`

---

## File Structure

- **Create** `manim_skill/components/bar_chart.py` — the `BarChart` component (one responsibility; ~50 lines, mirrors `plot_evolution.py`).
- **Create** `tests/components/test_bar_chart.py` — build + validation tests (fast suite).
- **Regenerate** `skill/reference/*.md` via `manim-skill gen-skill-docs` (do not hand-edit).
- **Create** `examples/gold/bar-comparison.json` — a BarChart gold example.
- **Modify** `tests/llm/test_examples.py` — add `bar-comparison` to the seed-name assertion.
- **Modify** `README.md`, `README.en.md`, `CLAUDE.md` — component count 18 → 19 + a `BarChart` table row.

---

## Task 1: The `BarChart` component

**Files:**
- Create: `manim_skill/components/bar_chart.py`
- Test: `tests/components/test_bar_chart.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/components/test_bar_chart.py`:

```python
import pytest
from manim import Mobject
from pydantic import ValidationError

from manim_skill.components.bar_chart import BarChart, BarChartParams
from manim_skill.components.theme import THEME


def test_build_returns_non_empty_mobject():
    comp = BarChart()
    mobj = comp.build(BarChartParams(values=[1.0, 4.0, 9.0]))
    assert isinstance(mobj, Mobject)
    assert len(mobj.submobjects) > 0


def test_build_with_labels_title_highlight():
    comp = BarChart()
    mobj = comp.build(
        BarChartParams(
            values=[1.0, 5.0, 36.9],
            labels=["Baseline", "v1", "Ours"],
            title="Requests per second",
            highlight=2,
        )
    )
    assert isinstance(mobj, Mobject)
    assert len(mobj.submobjects) > 0


def test_highlight_dims_other_bars():
    comp = BarChart()
    mobj = comp.build(BarChartParams(values=[1.0, 2.0, 3.0], highlight=2))
    bars = mobj.submobjects[0]  # first submobject is the bars VGroup
    assert bars[2].get_fill_color().to_hex().lower() == THEME.PRIMARY.lower()
    assert bars[0].get_fill_color().to_hex().lower() == THEME.PRIMARY_SOFT.lower()


def test_no_highlight_all_bars_primary():
    comp = BarChart()
    mobj = comp.build(BarChartParams(values=[1.0, 2.0]))
    bars = mobj.submobjects[0]
    assert bars[0].get_fill_color().to_hex().lower() == THEME.PRIMARY.lower()
    assert bars[1].get_fill_color().to_hex().lower() == THEME.PRIMARY.lower()


def test_build_all_zero_values_does_not_crash():
    comp = BarChart()
    mobj = comp.build(BarChartParams(values=[0.0, 0.0]))
    assert isinstance(mobj, Mobject)


def test_values_requires_at_least_one():
    with pytest.raises(ValidationError):
        BarChartParams(values=[])


def test_labels_length_must_match_values():
    with pytest.raises(ValidationError):
        BarChartParams(values=[1.0, 2.0], labels=["only one"])


def test_highlight_out_of_range_rejected():
    with pytest.raises(ValidationError):
        BarChartParams(values=[1.0, 2.0], highlight=5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/components/test_bar_chart.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'manim_skill.components.bar_chart'`

- [ ] **Step 3: Create the component**

Create `manim_skill/components/bar_chart.py`:

```python
from __future__ import annotations

from manim import DL, DOWN, DR, RIGHT, UP, Create, Line, Mobject, Rectangle, Scene, VGroup
from pydantic import BaseModel, Field, model_validator

from manim_skill.components.base import Component, register
from manim_skill.components.theme import THEME, body_text, label_text

_MAX_H = 4.0   # tallest bar, scene units
_BAR_W = 0.9   # bar width, scene units


class BarChartParams(BaseModel):
    values: list[float] = Field(min_length=1)
    labels: list[str] | None = None
    title: str | None = None
    highlight: int | None = None

    @model_validator(mode="after")
    def _check_lengths(self) -> "BarChartParams":
        if self.labels is not None and len(self.labels) != len(self.values):
            raise ValueError("labels must have the same length as values")
        if self.highlight is not None and not (
            0 <= self.highlight < len(self.values)
        ):
            raise ValueError("highlight must be a valid bar index")
        return self


@register
class BarChart(Component):
    name = "BarChart"
    Params = BarChartParams

    def build(self, params: BarChartParams) -> Mobject:
        y_max = max(params.values)
        if y_max <= 0:
            y_max = 1.0

        bars = VGroup()
        for i, value in enumerate(params.values):
            height = max((value / y_max) * _MAX_H, 0.01)
            if params.highlight is None or i == params.highlight:
                color = THEME.PRIMARY
            else:
                color = THEME.PRIMARY_SOFT
            bars.add(
                Rectangle(
                    width=_BAR_W,
                    height=height,
                    fill_color=color,
                    fill_opacity=0.9,
                    stroke_color=color,
                    stroke_width=2,
                )
            )
        bars.arrange(RIGHT, buff=0.4, aligned_edge=DOWN)

        diagram = VGroup(bars)
        diagram.add(
            Line(bars.get_corner(DL), bars.get_corner(DR), color=THEME.RULE)
        )
        if params.labels:
            for bar, name in zip(bars, params.labels):
                diagram.add(label_text(name).next_to(bar, DOWN, buff=0.2))
        if params.title:
            diagram.add(body_text(params.title, size=28).next_to(diagram, UP))
        return diagram

    def animate(self, scene: Scene, mobject: Mobject, params: BarChartParams) -> None:
        scene.play(Create(mobject))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/components/test_bar_chart.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Confirm auto-discovery registered it**

Run: `python -c "import manim_skill.components; from manim_skill.components import base; print('BarChart' in base.all_names())"`
Expected: prints `True`

- [ ] **Step 6: Commit**

```bash
git add manim_skill/components/bar_chart.py tests/components/test_bar_chart.py
git commit -m "feat(components): add BarChart (hand-built themed bars, no LaTeX)"
```

---

## Task 2: Regenerate the agent skill reference docs

**Files:**
- Regenerate: `skill/reference/*.md` (via the CLI; do not hand-edit)

- [ ] **Step 1: Confirm the drift test currently fails**

The new component is in the catalog but not yet in the committed skill docs.
Run: `pytest tests/test_skill_reference_current.py -v`
Expected: FAIL (the regenerated docs would now include `BarChart`, so the committed copy is stale).

- [ ] **Step 2: Regenerate the skill docs**

Run: `manim-skill gen-skill-docs`
Expected: it rewrites `skill/reference/components.md` (and any sibling reference files) to include `BarChart`.

- [ ] **Step 3: Run the drift test to verify it passes**

Run: `pytest tests/test_skill_reference_current.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add skill/reference
git commit -m "docs(skill): regenerate reference for BarChart component"
```

---

## Task 3: Seed a `BarChart` gold example

**Files:**
- Create: `examples/gold/bar-comparison.json`
- Test: `tests/llm/test_examples.py` (extend the seed assertion)

- [ ] **Step 1: Update the seed test to expect the new gold example**

In `tests/llm/test_examples.py`, in `test_seed_gold_examples_are_valid`, change the expected-names assertion line:

```python
    assert {"pipeline-stages", "results-table", "system-graph"} <= names
```

to:

```python
    assert {
        "pipeline-stages",
        "results-table",
        "system-graph",
        "bar-comparison",
    } <= names
```

- [ ] **Step 2: Run the seed test to verify it fails**

Run: `pytest tests/llm/test_examples.py::test_seed_gold_examples_are_valid -v`
Expected: FAIL — `bar-comparison` is not in `names` yet.

- [ ] **Step 3: Create the gold example**

Create `examples/gold/bar-comparison.json`:

```json
{
  "tags": ["throughput", "comparison", "benchmark", "speedup", "performance", "bars", "chart", "baseline"],
  "spec": {
    "title": "Throughput Comparison",
    "aspect_ratio": "16:9",
    "beats": [
      {"component": "TextBeat", "params": {"text": "Throughput Comparison", "subtitle": "baseline vs ours", "style": "title"}, "duration": 2.0},
      {"component": "BarChart", "params": {"title": "Requests per second", "values": [1, 5, 14, 36.9], "labels": ["Baseline", "v1", "v2", "Ours"], "highlight": 3}, "duration": 4.5},
      {"component": "TextBeat", "params": {"text": "Takeaway", "style": "bullets", "bullets": ["Each version lifts throughput", "The final design wins by a wide margin"]}, "duration": 3.5}
    ]
  }
}
```

- [ ] **Step 4: Run the seed test to verify it passes**

Run: `pytest tests/llm/test_examples.py::test_seed_gold_examples_are_valid -v`
Expected: PASS (the loader validates the BarChart beat against the new component)

- [ ] **Step 5: Commit**

```bash
git add examples/gold/bar-comparison.json tests/llm/test_examples.py
git commit -m "feat(examples): add bar-comparison gold example (BarChart few-shot)"
```

---

## Task 4: Bump the component count + table in the docs

**Files:**
- Modify: `README.md`, `README.en.md`, `CLAUDE.md`

- [ ] **Step 1: Update `README.en.md`**

Change the count sentence (currently "The library ships 18 components."):

```
The library ships 19 components. Each declares a Pydantic parameter schema — that one declaration is the single source of truth for validation, the LLM prompt catalog, and the agent skill docs.
```

Add a row to the component table, right after the `| `TwoColumn` | ... |` row:

```
| `BarChart` | a labeled bar chart, optional highlighted bar (comparisons / throughput) |
```

- [ ] **Step 2: Update `README.md`** (Traditional Chinese)

Change the count sentence (currently "元件庫內含 18 個元件。…"):

```
元件庫內含 19 個元件。每個元件宣告一份 Pydantic 參數 schema——這份宣告是驗證、LLM prompt 目錄、agent skill 文件三者的單一事實來源。
```

Add a row to the component table, right after the `| `TwoColumn` | 左右兩欄並排，用於對照 |` row:

```
| `BarChart` | 帶標籤的長條圖，可選強調某一根（比較 / 吞吐量） |
```

- [ ] **Step 3: Update `CLAUDE.md`**

Change the layer-map line (currently "components/  18 animation components, …"):

```
components/  19 animation components, each: name + Params (Pydantic) + build()/animate(); @register + pkgutil auto-discovery
```

- [ ] **Step 4: Verify no stale "18 components" reference remains**

Run: `git grep -n "18 component\|18 個元件\|18 animation"`
Expected: no output (all three bumped to 19).

- [ ] **Step 5: Run the full fast suite (no regressions)**

Run: `pytest -m "not docker" -q`
Expected: PASS (all fast tests green)

- [ ] **Step 6: Commit**

```bash
git add README.md README.en.md CLAUDE.md
git commit -m "docs: component count 18 -> 19, add BarChart to the component table"
```

---

## Self-Review notes (already applied)

- **Spec coverage:** §1 component → Task 1. §2 validation (`model_validator`) → Task 1 (Params + the two ValidationError tests). §3 catalog/skill-docs drift → Task 2. §4 tests → Task 1; flywheel gold example → Task 3; component-count doc sync (the spec's "18→19") → Task 4.
- **Deviation from spec, intentional:** the spec mentioned an optional `@pytest.mark.docker` render test "沿用既有 docker 元件測試的手法" — but no existing component has a docker test (`PlotEvolution`/`TableBeat` etc. are build+validation only in the fast suite). To follow the established convention, this plan uses build + validation tests only; real rendering is exercised generically through `render_batch`. (The controller can do a one-off `manim-skill render` of a BarChart spec to confirm visually.)
- **Rendering deviation, intentional:** hand-built `Rectangle` bars instead of `manim.BarChart` — the latter triggers LaTeX (`FileNotFoundError` on a LaTeX-less box, and against the framework's LaTeX-avoidance). Verified the hand-built path builds with no LaTeX.
- **Type consistency:** `BarChartParams(values, labels, title, highlight)` and `BarChart(name, Params, build, animate)` match across the component, its tests, and the gold example. The gold example's BarChart params (`values` len 4, `labels` len 4, `highlight` 3) satisfy the `model_validator`.
- **Seed test:** the existing `<=` subset assertion already tolerates the extra file; Task 3 makes the new name explicit rather than relying on the loop alone.
- **No placeholders:** every code/test step has complete content and exact run/expected lines.
