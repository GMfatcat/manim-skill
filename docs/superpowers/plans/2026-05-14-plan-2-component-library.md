# Plan 2: 元件庫擴充 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把元件庫從 2 個元件擴充到 8 個,新增設計文件 §4.2 列出的其餘 7 個核心元件,並讓元件註冊改為自動探索（新增元件零接線）。

**Architecture:** 沿用 Plan 1 已建立的元件契約（`Component` 基底：`name`、`Params` Pydantic model、`build(params) -> Mobject`、`animate(scene, mobject, params)`、`@register` 裝飾器）。每個元件是一個獨立檔案、獨立可測試的單元。`components/__init__.py` 改為自動探索套件內所有模組，因此新增元件不需要編輯任何共用檔案。6 個不需 LaTeX 的元件以本地 `build()` 結構性單元測試驗證；`FormulaBreakdown`（唯一使用 `MathTex`，需 LaTeX）以 docker 渲染整合測試驗證，因為渲染 image 內含 LaTeX。

**Tech Stack:** Python ≥3.12、manim community 0.20.x、Pydantic v2、pytest、Docker。

---

## 背景：Plan 1 已完成的部分

已存在且測試通過：
- `manim_skill/components/base.py` — `Component` 基底類別 + registry（`register` 裝飾器、`get(name)`、`all_names()`）。
- `manim_skill/components/__init__.py` — 目前內容為兩行明確 import（`code_walkthrough`、`text_beat`）。
- `manim_skill/components/text_beat.py`、`code_walkthrough.py` — 兩個已完成的元件。
- `manim_skill/spec/`、`manim_skill/builder/`、`manim_skill/render/` — spec schema、解析、驗證、builder、docker 渲染、mp4→gif。
- `docker/Dockerfile` — 渲染 image（`manimcommunity/manim:v0.20.1` + ffmpeg + 本套件）。
- 測試以 `tests/<subpkg>/` 組織，每個子目錄有空的 `__init__.py`。`docker` pytest marker 已註冊。

本地開發環境：manim 0.20.1、Python 3.13、**無 LaTeX**。Docker `manim-skill:latest` image 內含 LaTeX。

## 重要：manim API 注意事項

本計畫的元件使用的 manim mobject / animation（`Circle`、`Line`、`Rectangle`、`RoundedRectangle`、`SurroundingRectangle`、`Triangle`、`RegularPolygon`、`Axes`、`MathTex`、`Arrow`、`Text`、`VGroup`、`Create`、`Write`、`FadeIn`、`Indicate`、`Rotate`）都是 manim 穩定 API，針對 manim 0.20.x 撰寫。若某個建構子或方法在實際安裝的版本上簽名不同而報錯，執行 `python -c "import manim, inspect; print(inspect.signature(manim.<Name>))"` 查看實際簽名並做最小調整；測試會即時抓出不符。不要因為 API 小差異就改變元件的設計意圖。

## File Structure

```
manim_skill/components/
  __init__.py                  改為自動探索（取代明確 import）
  neural_net_diagram.py        新增 — NeuralNetDiagram
  attention_flow.py            新增 — AttentionFlow
  matrix_op.py                 新增 — MatrixOp
  plot_evolution.py            新增 — PlotEvolution
  pipeline_diagram.py          新增 — PipelineDiagram
  geometry_anim.py             新增 — GeometryAnim
  formula_breakdown.py         新增 — FormulaBreakdown（使用 MathTex）
tests/components/
  test_autodiscovery.py        新增 — 驗證自動探索
  test_neural_net_diagram.py   新增
  test_attention_flow.py       新增
  test_matrix_op.py            新增
  test_plot_evolution.py       新增
  test_pipeline_diagram.py     新增
  test_geometry_anim.py        新增
  test_formula_breakdown.py    新增
```

每個元件檔案單一職責；新增元件後 **不需** 編輯 `__init__.py`（自動探索處理）。

---

## Task 1: 元件自動探索

把 `components/__init__.py` 從明確 import 改為自動探索套件內所有模組。這讓後續每個元件任務都不必編輯共用檔案（消除平行執行的衝突點）。

**Files:**
- Modify: `manim_skill/components/__init__.py`
- Create: `tests/components/test_autodiscovery.py`

- [ ] **Step 1: 寫失敗測試** — `tests/components/test_autodiscovery.py`:

```python
def test_autodiscovery_registers_existing_components():
    # Importing the package triggers auto-discovery of all component modules.
    import importlib

    import manim_skill.components  # noqa: F401
    from manim_skill.components import base

    importlib.reload(manim_skill.components)
    names = base.all_names()
    assert "TextBeat" in names
    assert "CodeWalkthrough" in names


def test_autodiscovery_skips_base_module():
    # `base` is infrastructure, not a component — it must not be treated
    # as a component module (it has no @register call, so this just
    # confirms discovery doesn't choke on it).
    import manim_skill.components  # noqa: F401
    from manim_skill.components import base

    assert isinstance(base.all_names(), list)
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/components/test_autodiscovery.py -v`
  目前 `__init__.py` 是明確 import，`TextBeat`/`CodeWalkthrough` 其實會被註冊，所以這兩個測試「現在就可能通過」。這是少數無法先看到紅燈的情況：本任務是把實作機制從明確 import 換成自動探索，行為等價但更穩健。請改為先做 Step 3，再用測試確認行為維持正確（綠燈），並確認 `__init__.py` 內已不再有明確 import 行。

- [ ] **Step 3: 改寫 `__init__.py` 為自動探索** — 用以下內容完整取代 `manim_skill/components/__init__.py`:

```python
"""Auto-discovers and imports every component module in this package so
each component self-registers via the @register decorator. New component
files need no wiring here — just add the file to this package.
"""

from __future__ import annotations

import importlib
import pkgutil

for _module_info in pkgutil.iter_modules(__path__):
    if _module_info.name != "base":
        importlib.import_module(f"{__name__}.{_module_info.name}")
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/components/test_autodiscovery.py -v`
  Expected: PASS（2 passed）。

- [ ] **Step 5: 執行完整非 docker 測試確認無回歸** — `pytest -m "not docker" -q`
  Expected: 全部 PASS（Plan 1 的元件、builder、spec、render 單元測試都仍通過——驗證器仍能 `get("TextBeat")`）。

- [ ] **Step 6: Commit**

```bash
git add manim_skill/components/__init__.py tests/components/test_autodiscovery.py
git commit -m "refactor: auto-discover component modules in components package"
```

---

## Task 2: NeuralNetDiagram 元件

分層節點 + 全連接邊。

**Files:**
- Create: `manim_skill/components/neural_net_diagram.py`
- Create: `tests/components/test_neural_net_diagram.py`

- [ ] **Step 1: 寫失敗測試** — `tests/components/test_neural_net_diagram.py`:

```python
import pytest
from manim import Mobject
from pydantic import ValidationError

from manim_skill.components.neural_net_diagram import (
    NeuralNetDiagram,
    NeuralNetDiagramParams,
)


def test_build_returns_non_empty_mobject():
    comp = NeuralNetDiagram()
    mobj = comp.build(NeuralNetDiagramParams(layers=[3, 4, 2]))
    assert isinstance(mobj, Mobject)
    assert len(mobj.submobjects) > 0


def test_build_with_layer_labels():
    comp = NeuralNetDiagram()
    mobj = comp.build(
        NeuralNetDiagramParams(layers=[2, 2], layer_labels=["in", "out"])
    )
    assert isinstance(mobj, Mobject)
    assert len(mobj.submobjects) > 0


def test_layers_requires_at_least_one():
    with pytest.raises(ValidationError):
        NeuralNetDiagramParams(layers=[])
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/components/test_neural_net_diagram.py -v`
  Expected: FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 實作元件** — `manim_skill/components/neural_net_diagram.py`:

```python
from __future__ import annotations

from manim import (
    BLUE,
    DOWN,
    RIGHT,
    UP,
    Circle,
    Create,
    Line,
    Mobject,
    Scene,
    Text,
    VGroup,
)
from pydantic import BaseModel, Field

from manim_skill.components.base import Component, register


class NeuralNetDiagramParams(BaseModel):
    layers: list[int] = Field(min_length=1)
    layer_labels: list[str] = Field(default_factory=list)


@register
class NeuralNetDiagram(Component):
    name = "NeuralNetDiagram"
    Params = NeuralNetDiagramParams

    def build(self, params: NeuralNetDiagramParams) -> Mobject:
        layer_groups = VGroup()
        for count in params.layers:
            nodes = VGroup(
                *[Circle(radius=0.18, color=BLUE) for _ in range(count)]
            )
            nodes.arrange(DOWN, buff=0.3)
            layer_groups.add(nodes)
        layer_groups.arrange(RIGHT, buff=1.5)

        edges = VGroup()
        for left, right in zip(layer_groups[:-1], layer_groups[1:]):
            for node_a in left:
                for node_b in right:
                    edges.add(
                        Line(
                            node_a.get_center(),
                            node_b.get_center(),
                            stroke_width=1,
                            stroke_opacity=0.4,
                        )
                    )

        diagram = VGroup(edges, layer_groups)

        for group, label in zip(layer_groups, params.layer_labels):
            diagram.add(Text(label, font_size=24).next_to(group, UP))

        return diagram

    def animate(
        self,
        scene: Scene,
        mobject: Mobject,
        params: NeuralNetDiagramParams,
    ) -> None:
        scene.play(Create(mobject))
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/components/test_neural_net_diagram.py -v`
  Expected: PASS（3 passed）。

- [ ] **Step 5: Commit**

```bash
git add manim_skill/components/neural_net_diagram.py tests/components/test_neural_net_diagram.py
git commit -m "feat: NeuralNetDiagram component"
```

---

## Task 3: AttentionFlow 元件

token 序列 + 注意力權重連線。

**Files:**
- Create: `manim_skill/components/attention_flow.py`
- Create: `tests/components/test_attention_flow.py`

- [ ] **Step 1: 寫失敗測試** — `tests/components/test_attention_flow.py`:

```python
import pytest
from manim import Mobject
from pydantic import ValidationError

from manim_skill.components.attention_flow import (
    AttentionFlow,
    AttentionFlowParams,
)


def test_build_tokens_only():
    comp = AttentionFlow()
    mobj = comp.build(AttentionFlowParams(tokens=["The", "cat", "sat"]))
    assert isinstance(mobj, Mobject)
    assert len(mobj.submobjects) > 0


def test_highlight_adds_lines():
    comp = AttentionFlow()
    plain = comp.build(AttentionFlowParams(tokens=["a", "b", "c"]))
    highlighted = comp.build(
        AttentionFlowParams(
            tokens=["a", "b", "c"], highlight="b", weights=[0.2, 1.0, 0.5]
        )
    )
    assert len(highlighted.submobjects) > len(plain.submobjects)


def test_unknown_highlight_is_ignored():
    comp = AttentionFlow()
    plain = comp.build(AttentionFlowParams(tokens=["a", "b"]))
    with_bad_highlight = comp.build(
        AttentionFlowParams(tokens=["a", "b"], highlight="zzz")
    )
    assert len(with_bad_highlight.submobjects) == len(plain.submobjects)


def test_tokens_requires_at_least_one():
    with pytest.raises(ValidationError):
        AttentionFlowParams(tokens=[])
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/components/test_attention_flow.py -v`
  Expected: FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 實作元件** — `manim_skill/components/attention_flow.py`:

```python
from __future__ import annotations

from manim import (
    RIGHT,
    WHITE,
    YELLOW,
    Create,
    Line,
    Mobject,
    Scene,
    SurroundingRectangle,
    Text,
    VGroup,
)
from pydantic import BaseModel, Field

from manim_skill.components.base import Component, register


class AttentionFlowParams(BaseModel):
    tokens: list[str] = Field(min_length=1)
    highlight: str | None = None
    weights: list[float] = Field(default_factory=list)


@register
class AttentionFlow(Component):
    name = "AttentionFlow"
    Params = AttentionFlowParams

    def build(self, params: AttentionFlowParams) -> Mobject:
        boxes = VGroup()
        for token in params.tokens:
            label = Text(token, font_size=28)
            box = SurroundingRectangle(label, color=WHITE, buff=0.15)
            boxes.add(VGroup(box, label))
        boxes.arrange(RIGHT, buff=0.5)

        diagram = VGroup(boxes)

        if params.highlight in params.tokens:
            src_idx = params.tokens.index(params.highlight)
            src = boxes[src_idx]
            lines = VGroup()
            for i, target in enumerate(boxes):
                if i == src_idx:
                    continue
                weight = params.weights[i] if i < len(params.weights) else 0.5
                opacity = max(0.1, min(1.0, weight))
                lines.add(
                    Line(
                        src.get_top(),
                        target.get_top(),
                        color=YELLOW,
                        stroke_width=3,
                        stroke_opacity=opacity,
                    )
                )
            diagram.add(lines)

        return diagram

    def animate(
        self, scene: Scene, mobject: Mobject, params: AttentionFlowParams
    ) -> None:
        scene.play(Create(mobject))
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/components/test_attention_flow.py -v`
  Expected: PASS（4 passed）。

- [ ] **Step 5: Commit**

```bash
git add manim_skill/components/attention_flow.py tests/components/test_attention_flow.py
git commit -m "feat: AttentionFlow component"
```

---

## Task 4: MatrixOp 元件

矩陣運算示意（matmul / transpose / reshape），以帶標籤的方塊表示矩陣。使用 `Text` 標籤（不用 `MathTex`，避免 LaTeX 依賴）。

**Files:**
- Create: `manim_skill/components/matrix_op.py`
- Create: `tests/components/test_matrix_op.py`

- [ ] **Step 1: 寫失敗測試** — `tests/components/test_matrix_op.py`:

```python
from manim import Mobject

from manim_skill.components.matrix_op import MatrixOp, MatrixOpParams


def test_default_op_is_matmul():
    assert MatrixOpParams().op == "matmul"


def test_build_matmul_has_three_boxes_and_two_operators():
    comp = MatrixOp()
    mobj = comp.build(
        MatrixOpParams(op="matmul", a_label="Q", b_label="K", result_label="S")
    )
    assert isinstance(mobj, Mobject)
    # 3 labeled boxes + 2 operator texts
    assert len(mobj.submobjects) == 5


def test_build_transpose_has_two_boxes_and_one_operator():
    comp = MatrixOp()
    mobj = comp.build(MatrixOpParams(op="transpose", a_label="A"))
    # 1 labeled box + 1 operator + 1 result box
    assert len(mobj.submobjects) == 3


def test_build_reshape_has_two_boxes_and_one_operator():
    comp = MatrixOp()
    mobj = comp.build(MatrixOpParams(op="reshape", a_label="A"))
    assert len(mobj.submobjects) == 3
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/components/test_matrix_op.py -v`
  Expected: FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 實作元件** — `manim_skill/components/matrix_op.py`:

```python
from __future__ import annotations

from typing import Literal

from manim import (
    BLUE,
    GREEN,
    ORANGE,
    RIGHT,
    Create,
    Mobject,
    Rectangle,
    Scene,
    Text,
    VGroup,
)
from pydantic import BaseModel

from manim_skill.components.base import Component, register


def _labeled_box(label: str, color) -> VGroup:
    box = Rectangle(width=1.2, height=1.2, color=color)
    text = Text(label, font_size=32).move_to(box)
    return VGroup(box, text)


class MatrixOpParams(BaseModel):
    op: Literal["matmul", "transpose", "reshape"] = "matmul"
    a_label: str = "A"
    b_label: str | None = None
    result_label: str | None = None


@register
class MatrixOp(Component):
    name = "MatrixOp"
    Params = MatrixOpParams

    def build(self, params: MatrixOpParams) -> Mobject:
        parts: list = [_labeled_box(params.a_label, BLUE)]

        if params.op == "matmul":
            parts.append(Text("x", font_size=40))
            parts.append(_labeled_box(params.b_label or "B", GREEN))
            parts.append(Text("=", font_size=40))
            parts.append(_labeled_box(params.result_label or "C", ORANGE))
        else:
            operator = "T" if params.op == "transpose" else "->"
            suffix = "_T" if params.op == "transpose" else "'"
            default_result = params.a_label + suffix
            parts.append(Text(operator, font_size=40))
            parts.append(
                _labeled_box(params.result_label or default_result, ORANGE)
            )

        row = VGroup(*parts)
        row.arrange(RIGHT, buff=0.4)
        return row

    def animate(
        self, scene: Scene, mobject: Mobject, params: MatrixOpParams
    ) -> None:
        scene.play(Create(mobject))
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/components/test_matrix_op.py -v`
  Expected: PASS（4 passed）。

- [ ] **Step 5: Commit**

```bash
git add manim_skill/components/matrix_op.py tests/components/test_matrix_op.py
git commit -m "feat: MatrixOp component"
```

---

## Task 5: PlotEvolution 元件

把一串數值（loss curve、梯度下降軌跡等）畫成座標軸上的折線圖。

**Files:**
- Create: `manim_skill/components/plot_evolution.py`
- Create: `tests/components/test_plot_evolution.py`

- [ ] **Step 1: 寫失敗測試** — `tests/components/test_plot_evolution.py`:

```python
import pytest
from manim import Mobject
from pydantic import ValidationError

from manim_skill.components.plot_evolution import (
    PlotEvolution,
    PlotEvolutionParams,
)


def test_build_returns_non_empty_mobject():
    comp = PlotEvolution()
    mobj = comp.build(
        PlotEvolutionParams(series=[1.0, 0.7, 0.5, 0.4, 0.35])
    )
    assert isinstance(mobj, Mobject)
    assert len(mobj.submobjects) > 0


def test_build_with_title():
    comp = PlotEvolution()
    mobj = comp.build(
        PlotEvolutionParams(series=[1.0, 0.5], title="training loss")
    )
    assert isinstance(mobj, Mobject)
    assert len(mobj.submobjects) > 0


def test_build_with_flat_series_does_not_crash():
    # All-equal values would make y_range degenerate; the component
    # must guard against that.
    comp = PlotEvolution()
    mobj = comp.build(PlotEvolutionParams(series=[2.0, 2.0, 2.0]))
    assert isinstance(mobj, Mobject)


def test_series_requires_at_least_two_points():
    with pytest.raises(ValidationError):
        PlotEvolutionParams(series=[1.0])
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/components/test_plot_evolution.py -v`
  Expected: FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 實作元件** — `manim_skill/components/plot_evolution.py`:

```python
from __future__ import annotations

from manim import BLUE, UP, Axes, Create, Mobject, Scene, Text, VGroup
from pydantic import BaseModel, Field

from manim_skill.components.base import Component, register


class PlotEvolutionParams(BaseModel):
    series: list[float] = Field(min_length=2)
    title: str | None = None


@register
class PlotEvolution(Component):
    name = "PlotEvolution"
    Params = PlotEvolutionParams

    def build(self, params: PlotEvolutionParams) -> Mobject:
        n = len(params.series)
        y_min = min(params.series)
        y_max = max(params.series)
        if y_min == y_max:
            y_min, y_max = y_min - 1.0, y_max + 1.0

        axes = Axes(
            x_range=[0, n - 1, max(1, (n - 1) // 5)],
            y_range=[y_min, y_max, (y_max - y_min) / 5],
            x_length=8,
            y_length=4.5,
        )
        graph = axes.plot_line_graph(
            x_values=list(range(n)),
            y_values=params.series,
            line_color=BLUE,
            add_vertex_dots=True,
        )

        diagram = VGroup(axes, graph)
        if params.title:
            diagram.add(Text(params.title, font_size=28).next_to(axes, UP))
        return diagram

    def animate(
        self, scene: Scene, mobject: Mobject, params: PlotEvolutionParams
    ) -> None:
        scene.play(Create(mobject))
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/components/test_plot_evolution.py -v`
  Expected: PASS（4 passed）。

- [ ] **Step 5: Commit**

```bash
git add manim_skill/components/plot_evolution.py tests/components/test_plot_evolution.py
git commit -m "feat: PlotEvolution component"
```

---

## Task 6: PipelineDiagram 元件

標籤方塊 + 箭頭，表示資料流經各階段。

**Files:**
- Create: `manim_skill/components/pipeline_diagram.py`
- Create: `tests/components/test_pipeline_diagram.py`

- [ ] **Step 1: 寫失敗測試** — `tests/components/test_pipeline_diagram.py`:

```python
import pytest
from manim import Mobject
from pydantic import ValidationError

from manim_skill.components.pipeline_diagram import (
    PipelineDiagram,
    PipelineDiagramParams,
)


def test_build_returns_non_empty_mobject():
    comp = PipelineDiagram()
    mobj = comp.build(
        PipelineDiagramParams(stages=["load", "train", "eval"])
    )
    assert isinstance(mobj, Mobject)
    assert len(mobj.submobjects) > 0


def test_single_stage_has_no_arrows():
    comp = PipelineDiagram()
    mobj = comp.build(PipelineDiagramParams(stages=["only"]))
    # diagram = VGroup(boxes, arrows); the arrows group is the 2nd submobject
    boxes, arrows = mobj.submobjects[0], mobj.submobjects[1]
    assert len(boxes.submobjects) == 1
    assert len(arrows.submobjects) == 0


def test_three_stages_have_two_arrows():
    comp = PipelineDiagram()
    mobj = comp.build(PipelineDiagramParams(stages=["a", "b", "c"]))
    arrows = mobj.submobjects[1]
    assert len(arrows.submobjects) == 2


def test_stages_requires_at_least_one():
    with pytest.raises(ValidationError):
        PipelineDiagramParams(stages=[])
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/components/test_pipeline_diagram.py -v`
  Expected: FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 實作元件** — `manim_skill/components/pipeline_diagram.py`:

```python
from __future__ import annotations

from manim import (
    BLUE,
    RIGHT,
    UP,
    Arrow,
    Create,
    Mobject,
    RoundedRectangle,
    Scene,
    Text,
    VGroup,
)
from pydantic import BaseModel, Field

from manim_skill.components.base import Component, register


class PipelineDiagramParams(BaseModel):
    stages: list[str] = Field(min_length=1)
    title: str | None = None


@register
class PipelineDiagram(Component):
    name = "PipelineDiagram"
    Params = PipelineDiagramParams

    def build(self, params: PipelineDiagramParams) -> Mobject:
        boxes = VGroup()
        for stage in params.stages:
            label = Text(stage, font_size=24)
            box = RoundedRectangle(
                corner_radius=0.15,
                width=max(1.5, label.width + 0.4),
                height=1.0,
                color=BLUE,
            )
            label.move_to(box)
            boxes.add(VGroup(box, label))
        boxes.arrange(RIGHT, buff=1.0)

        arrows = VGroup()
        for left, right in zip(boxes[:-1], boxes[1:]):
            arrows.add(Arrow(left.get_right(), right.get_left(), buff=0.1))

        diagram = VGroup(boxes, arrows)
        if params.title:
            diagram.add(
                Text(params.title, font_size=28).next_to(diagram, UP)
            )
        return diagram

    def animate(
        self, scene: Scene, mobject: Mobject, params: PipelineDiagramParams
    ) -> None:
        scene.play(Create(mobject))
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/components/test_pipeline_diagram.py -v`
  Expected: PASS（4 passed）。

- [ ] **Step 5: Commit**

```bash
git add manim_skill/components/pipeline_diagram.py tests/components/test_pipeline_diagram.py
git commit -m "feat: PipelineDiagram component"
```

---

## Task 7: GeometryAnim 元件

基本幾何形狀 + 選填變換（旋轉 / 縮放）。

**Files:**
- Create: `manim_skill/components/geometry_anim.py`
- Create: `tests/components/test_geometry_anim.py`

- [ ] **Step 1: 寫失敗測試** — `tests/components/test_geometry_anim.py`:

```python
from manim import Mobject

from manim_skill.components.geometry_anim import (
    GeometryAnim,
    GeometryAnimParams,
)


def test_defaults():
    params = GeometryAnimParams()
    assert params.shape == "circle"
    assert params.transform == "none"
    assert params.label is None


def test_build_each_shape():
    comp = GeometryAnim()
    for shape in ("circle", "square", "triangle", "polygon"):
        mobj = comp.build(GeometryAnimParams(shape=shape))
        assert isinstance(mobj, Mobject)
        assert len(mobj.submobjects) >= 1


def test_build_with_label_adds_text():
    comp = GeometryAnim()
    plain = comp.build(GeometryAnimParams(shape="circle"))
    labeled = comp.build(
        GeometryAnimParams(shape="circle", label="unit circle")
    )
    assert len(labeled.submobjects) > len(plain.submobjects)
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/components/test_geometry_anim.py -v`
  Expected: FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 實作元件** — `manim_skill/components/geometry_anim.py`:

```python
from __future__ import annotations

from typing import Literal

from manim import (
    BLUE,
    DOWN,
    PI,
    Circle,
    Create,
    Mobject,
    RegularPolygon,
    Rotate,
    Scene,
    Square,
    Text,
    Triangle,
    VGroup,
)
from pydantic import BaseModel

from manim_skill.components.base import Component, register

_SHAPES = {
    "circle": lambda: Circle(radius=1.0, color=BLUE),
    "square": lambda: Square(side_length=2.0, color=BLUE),
    "triangle": lambda: Triangle(color=BLUE).scale(1.2),
    "polygon": lambda: RegularPolygon(n=6, color=BLUE).scale(1.2),
}


class GeometryAnimParams(BaseModel):
    shape: Literal["circle", "square", "triangle", "polygon"] = "circle"
    transform: Literal["rotate", "scale", "none"] = "none"
    label: str | None = None


@register
class GeometryAnim(Component):
    name = "GeometryAnim"
    Params = GeometryAnimParams

    def build(self, params: GeometryAnimParams) -> Mobject:
        shape = _SHAPES[params.shape]()
        group = VGroup(shape)
        if params.label:
            group.add(Text(params.label, font_size=28).next_to(shape, DOWN))
        return group

    def animate(
        self, scene: Scene, mobject: Mobject, params: GeometryAnimParams
    ) -> None:
        scene.play(Create(mobject))
        if params.transform == "rotate":
            scene.play(Rotate(mobject, angle=PI / 2))
        elif params.transform == "scale":
            scene.play(mobject.animate.scale(1.5))
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/components/test_geometry_anim.py -v`
  Expected: PASS（3 passed）。

- [ ] **Step 5: Commit**

```bash
git add manim_skill/components/geometry_anim.py tests/components/test_geometry_anim.py
git commit -m "feat: GeometryAnim component"
```

---

## Task 8: FormulaBreakdown 元件（需 LaTeX，docker 驗證）

`MathTex` 公式 + 選填標題。這是唯一使用 `MathTex` 的元件，`MathTex` 在 `build()` 時會呼叫 LaTeX。本地開發環境無 LaTeX，因此：
- `FormulaBreakdownParams` 的 schema 用一般本地測試驗證（pydantic 不需 LaTeX）。
- 元件的 `build()`/`animate()` 用 **docker 渲染整合測試** 驗證（渲染 image 內含 LaTeX）。
- 模組本身可在本地匯入（`MathTex` 只在 `build()` 內被呼叫，import 時不會觸發 LaTeX），所以自動探索與 `pytest -m "not docker"` 不受影響。

本任務必須在 Task 1–7 都完成並 commit 後執行（它會重建 docker image，使 image 含全部 8 個元件）。

**Files:**
- Create: `manim_skill/components/formula_breakdown.py`
- Create: `tests/components/test_formula_breakdown.py`

- [ ] **Step 1: 寫失敗測試（schema 部分 + docker 部分）** — `tests/components/test_formula_breakdown.py`:

```python
import pytest
from pydantic import ValidationError

from manim_skill.render.docker_render import render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec


def test_params_requires_formula():
    from manim_skill.components.formula_breakdown import FormulaBreakdownParams

    with pytest.raises(ValidationError):
        FormulaBreakdownParams()


def test_params_title_optional():
    from manim_skill.components.formula_breakdown import FormulaBreakdownParams

    params = FormulaBreakdownParams(formula="x^2 + y^2 = z^2")
    assert params.title is None


def test_component_is_registered():
    # Importing the module triggers @register; no LaTeX needed for this.
    import manim_skill.components.formula_breakdown  # noqa: F401
    from manim_skill.components import base

    assert "FormulaBreakdown" in base.all_names()


@pytest.mark.docker
def test_formula_breakdown_renders_in_docker(tmp_path):
    # build()/animate() use MathTex (LaTeX); verified inside the docker
    # image, which has a TeX distribution. Requires the image to be
    # rebuilt with this component present (see Step 5).
    spec = SceneSpec(
        title="T",
        beats=[
            Beat(
                component="FormulaBreakdown",
                params={"formula": "e^{i\\pi} + 1 = 0", "title": "Euler"},
                duration=1.0,
            )
        ],
    )
    mp4 = render_spec_to_mp4(spec, tmp_path)
    assert mp4.exists()
    assert mp4.stat().st_size > 0
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/components/test_formula_breakdown.py -v -m "not docker"`
  Expected: FAIL（`ModuleNotFoundError: manim_skill.components.formula_breakdown`）。

- [ ] **Step 3: 實作元件** — `manim_skill/components/formula_breakdown.py`:

```python
from __future__ import annotations

from manim import DOWN, Indicate, MathTex, Mobject, Scene, Text, VGroup, Write
from pydantic import BaseModel

from manim_skill.components.base import Component, register


class FormulaBreakdownParams(BaseModel):
    formula: str
    title: str | None = None


@register
class FormulaBreakdown(Component):
    name = "FormulaBreakdown"
    Params = FormulaBreakdownParams

    def build(self, params: FormulaBreakdownParams) -> Mobject:
        formula = MathTex(params.formula)
        group = VGroup(formula)
        if params.title:
            group.add(Text(params.title, font_size=28).next_to(formula, DOWN))
        return group

    def animate(
        self, scene: Scene, mobject: Mobject, params: FormulaBreakdownParams
    ) -> None:
        scene.play(Write(mobject))
        scene.play(Indicate(mobject))
```

- [ ] **Step 4: 執行 schema 測試確認通過** — `pytest tests/components/test_formula_breakdown.py -v -m "not docker"`
  Expected: PASS（3 passed — `test_params_requires_formula`、`test_params_title_optional`、`test_component_is_registered`）。

- [ ] **Step 5: 重建 docker image**（使 image 含全部 8 個元件）

```bash
docker build -t manim-skill:latest -f docker/Dockerfile .
```
Expected: 建置成功。

- [ ] **Step 6: 執行 docker 渲染測試確認通過** — `pytest tests/components/test_formula_breakdown.py -v -m docker`
  Expected: PASS（1 passed）。這證明 `FormulaBreakdown` 的 `build()`/`animate()` 在含 LaTeX 的 image 內正常運作。
  若 LaTeX 編譯失敗，檢查 stderr——可能是 `formula` 字串的 LaTeX 語法問題，或 image 的 TeX 套件不足；回報 stderr，不要默默改測試。

- [ ] **Step 7: 執行完整測試套件** — `pytest -q`
  Expected: 全部 PASS（含所有 docker 測試；應為約 70 個測試）。

- [ ] **Step 8: Commit**

```bash
git add manim_skill/components/formula_breakdown.py tests/components/test_formula_breakdown.py
git commit -m "feat: FormulaBreakdown component (MathTex, docker-verified)"
```

---

## Self-Review

**1. Spec coverage（對照設計文件 §4.2 的 8 個核心元件）**

- CodeWalkthrough → Plan 1 已完成 ✓
- TextBeat（輔助）→ Plan 1 已完成 ✓
- NeuralNetDiagram → Task 2 ✓
- AttentionFlow → Task 3 ✓
- MatrixOp → Task 4 ✓
- PlotEvolution → Task 5 ✓
- PipelineDiagram → Task 6 ✓
- GeometryAnim → Task 7 ✓
- FormulaBreakdown → Task 8 ✓

8 個核心元件全數覆蓋。設計文件 §4.2 的「每個元件宣告 Params schema 作為單一事實來源」——每個 Task 的元件都有對應的 `*Params` Pydantic model。「元件可獨立渲染與快照測試」——6 個本地 `build()` 結構性測試 + FormulaBreakdown 的 docker 渲染測試。`__init__.py` 自動探索（Task 1）對應「新增元件零接線」的精神。

**不在 Plan 2 範圍（後續計畫）：** 元件的精緻動畫（如 NeuralNetDiagram 的 forward flow 高亮、AttentionFlow 的權重動畫過場、CodeWalkthrough/FormulaBreakdown 的逐行/逐項精準高亮）——Plan 2 的 `animate()` 一律是 MVP 等級（`Create`/`Write` + 視需要一個 `Indicate`/`Rotate`/`scale`）。camera 的 focus/pan、render 後端佇列、LLM 層、CLI——分屬 Plan 3–5。

**2. Placeholder scan：** 無 TBD/TODO/「之後實作」。每個 step 都有完整可執行的程式碼或精確指令。Task 1 Step 2 說明了「無法先看紅燈」的情況及原因（機制替換，行為等價），非佔位。Task 8 的 docker 步驟有明確的重建指令。

**3. Type consistency：**
- 每個元件一律遵循 Plan 1 的 `Component` 契約：class 屬性 `name`（str）、`Params`（Pydantic model class）、`build(self, params) -> Mobject`、`animate(self, scene, mobject, params) -> None`、`@register` 裝飾。跨 8 個 Task 一致。
- 每個 `*Params` 與其元件的 `Params` 類別屬性指向同一個 model，測試中 import 的名稱（`NeuralNetDiagram`/`NeuralNetDiagramParams` 等）與實作檔案 export 的名稱一致。
- Task 4 的 `_labeled_box` helper 在 `matrix_op.py` 內定義並使用，未跨檔案。
- Task 8 的 docker 測試使用 Plan 1 的 `render_spec_to_mp4`、`SceneSpec`、`Beat`，簽名一致。
- registry 函式 `base.all_names()`（Task 1、Task 8 測試使用）與 Plan 1 定義一致。

無不一致。

---

## Execution Handoff

Plan 完成並存於 `docs/superpowers/plans/2026-05-14-plan-2-component-library.md`。兩種執行方式：

**1. Subagent-Driven（推薦）** — 每個 task 派一個全新 subagent，task 之間由我審核。Task 2–7 互相獨立（自動探索消除了共用檔案衝突），可分波平行（每波 ≤3）；Task 1 與 Task 8 為單獨執行（Task 1 先行、Task 8 殿後並重建 image）。

**2. Inline Execution** — 在本對話 session 內逐 task 執行，分批設檢查點審核。

要用哪一種？
