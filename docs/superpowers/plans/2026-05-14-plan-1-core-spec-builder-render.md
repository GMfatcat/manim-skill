# Plan 1: 核心 Spec + Builder + 渲染基元（無 LLM）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 手寫一份 scene spec JSON → 經解析與驗證 → builder 組成 manim Scene → docker 渲染 → 拿到 mp4 + gif，全程不需 LLM。

**Architecture:** scene spec 是唯一契約。元件以 registry 註冊，每個元件宣告 Pydantic 參數 schema（驗證的單一事實來源）。Builder 是一個 `MovingCameraScene` 子類 `SpecScene`，從環境變數讀 spec、逐 beat 呼叫元件或執行 raw code。渲染在 docker 內跑（image = manimcommunity/manim + 本套件），輸出 mp4 再用同一 image 內的 ffmpeg 轉 gif。

**Tech Stack:** Python ≥3.12、manim community ≥0.19、Pydantic v2、json5、pytest、Docker。

---

## File Structure

```
pyproject.toml                          專案設定與依賴
.dockerignore                           docker build context 排除清單
docker/Dockerfile                       渲染用 image：manimcommunity/manim + 本套件
manim_skill/
  __init__.py                           空
  spec/
    __init__.py                         空
    schema.py                           SceneSpec / Beat / CameraDirective（Pydantic）
    parse.py                            寬鬆解析：從文字抽出 JSON dict
    validate.py                         驗證 dict → SceneSpec，逐 beat 比對元件 schema
  components/
    __init__.py                         匯入各元件模組使其自我註冊
    base.py                             Component 基底 + registry
    text_beat.py                        TextBeat 元件
    code_walkthrough.py                 CodeWalkthrough 元件
  builder/
    __init__.py                         write_render_inputs（寫 spec.json + scene_entry.py）
    raw.py                              exec_raw：執行 raw beat 的程式碼
    camera.py                           apply_camera：套用 camera 指令
    spec_scene.py                       SpecScene（MovingCameraScene 子類）+ load_spec_from_env
  render/
    __init__.py                         空
    docker_render.py                    render_spec_to_mp4：在 docker 內渲染
    convert.py                          mp4_to_gif：ffmpeg 轉檔
tests/
  spec/test_schema.py
  spec/test_parse.py
  spec/test_validate.py
  components/test_base.py
  components/test_text_beat.py
  components/test_code_walkthrough.py
  builder/test_builder_io.py
  builder/test_raw.py
  builder/test_camera.py
  builder/test_spec_scene.py
  render/test_docker_render.py
  render/test_convert.py
  test_end_to_end.py
  fixtures/specs/text_and_code.txt
  fixtures/specs/with_raw_beat.json
```

每個檔案單一職責。`spec/` 是純資料層（無 manim 依賴），`components/` 與 `builder/` 依賴 manim，`render/` 只負責 docker 互動。

---

## Task 1: 專案骨架

**Files:**
- Create: `pyproject.toml`
- Create: `manim_skill/__init__.py` (空檔)
- Create: `manim_skill/spec/__init__.py` (空檔)
- Create: `manim_skill/components/__init__.py` (空檔)
- Create: `manim_skill/builder/__init__.py` (空檔)
- Create: `manim_skill/render/__init__.py` (空檔)
- Create: `tests/test_smoke.py`

- [ ] **Step 1: 建立 `pyproject.toml`**

```toml
[project]
name = "manim-skill"
version = "0.1.0"
description = "Concept-to-manim animation pipeline"
requires-python = ">=3.12"
dependencies = [
    "manim>=0.19",
    "pydantic>=2.6",
    "json5>=0.9",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["manim_skill*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "docker: integration tests that require a running Docker daemon and the manim-skill image",
]
```

- [ ] **Step 2: 建立空的套件檔案**

建立這些空檔（內容為空）：`manim_skill/__init__.py`、`manim_skill/spec/__init__.py`、`manim_skill/components/__init__.py`、`manim_skill/builder/__init__.py`、`manim_skill/render/__init__.py`

- [ ] **Step 3: 寫一個 smoke test**

`tests/test_smoke.py`:

```python
def test_package_imports():
    import manim_skill
    assert manim_skill is not None
```

- [ ] **Step 4: 安裝套件並執行測試**

Run:
```bash
pip install -e ".[dev]"
pytest tests/test_smoke.py -v
```
Expected: PASS（1 passed）。若 `manim` 安裝失敗，先確認系統有編譯工具；manim 的 ffmpeg 只在「渲染」時需要，import 與單元測試不需要。

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml manim_skill/ tests/test_smoke.py
git commit -m "chore: project scaffold for manim-skill"
```

---

## Task 2: Scene Spec Schema

**Files:**
- Create: `manim_skill/spec/schema.py`
- Test: `tests/spec/test_schema.py`

- [ ] **Step 1: 寫失敗測試**

`tests/spec/test_schema.py`:

```python
import pytest
from pydantic import ValidationError

from manim_skill.spec.schema import SceneSpec, Beat, CameraDirective


def test_minimal_spec_has_defaults():
    spec = SceneSpec(
        title="T",
        beats=[Beat(component="TextBeat", params={"text": "hi"})],
    )
    assert spec.aspect_ratio == "16:9"
    assert spec.beats[0].component == "TextBeat"
    assert spec.beats[0].params == {"text": "hi"}
    assert spec.beats[0].camera is None


def test_spec_requires_at_least_one_beat():
    with pytest.raises(ValidationError):
        SceneSpec(title="T", beats=[])


def test_raw_beat_carries_code():
    beat = Beat(component="raw", code="self.wait(1)")
    assert beat.code == "self.wait(1)"


def test_camera_directive_on_beat():
    beat = Beat(
        component="raw",
        code="pass",
        camera=CameraDirective(action="zoom", scale=2.0),
    )
    assert beat.camera.action == "zoom"
    assert beat.camera.scale == 2.0


def test_camera_directive_rejects_unknown_action():
    with pytest.raises(ValidationError):
        CameraDirective(action="teleport")
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/spec/test_schema.py -v`
Expected: FAIL（`ModuleNotFoundError: manim_skill.spec.schema`）

- [ ] **Step 3: 實作 schema**

`manim_skill/spec/schema.py`:

```python
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CameraDirective(BaseModel):
    action: Literal["focus", "zoom", "pan", "reset"]
    target: str | None = None
    scale: float | None = None


class Beat(BaseModel):
    component: str
    params: dict[str, Any] = Field(default_factory=dict)
    code: str | None = None
    caption: str | None = None
    duration: float | None = None
    camera: CameraDirective | None = None


class SceneSpec(BaseModel):
    title: str
    aspect_ratio: Literal["16:9", "1:1", "9:16"] = "16:9"
    beats: list[Beat] = Field(min_length=1)
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/spec/test_schema.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: Commit**

```bash
git add manim_skill/spec/schema.py tests/spec/test_schema.py
git commit -m "feat: scene spec schema (SceneSpec, Beat, CameraDirective)"
```

---

## Task 3: Component 基底與 Registry

**Files:**
- Create: `manim_skill/components/base.py`
- Test: `tests/components/test_base.py`

- [ ] **Step 1: 寫失敗測試**

`tests/components/test_base.py`:

```python
import pytest
from pydantic import BaseModel

from manim_skill.components import base


def test_register_and_get_returns_instance():
    class DummyParams(BaseModel):
        x: int = 0

    @base.register
    class Dummy(base.Component):
        name = "Dummy"
        Params = DummyParams

    got = base.get("Dummy")
    assert isinstance(got, Dummy)
    assert got.name == "Dummy"
    assert got.Params is DummyParams


def test_get_unknown_raises_keyerror():
    with pytest.raises(KeyError):
        base.get("NoSuchComponentXYZ")


def test_all_names_includes_registered():
    assert "Dummy" in base.all_names()
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/components/test_base.py -v`
Expected: FAIL（`ModuleNotFoundError` 或 `AttributeError`）

- [ ] **Step 3: 實作 base**

`manim_skill/components/base.py`:

```python
from __future__ import annotations

from typing import ClassVar

from manim import Mobject, Scene
from pydantic import BaseModel


class Component:
    """Base class for animation components.

    A component turns validated params into manim mobjects (`build`)
    and plays the beat's animation on a scene (`animate`).
    """

    name: ClassVar[str]
    Params: ClassVar[type[BaseModel]]

    def build(self, params: BaseModel) -> Mobject:
        raise NotImplementedError

    def animate(self, scene: Scene, mobject: Mobject, params: BaseModel) -> None:
        raise NotImplementedError


_REGISTRY: dict[str, Component] = {}


def register(component_cls: type[Component]) -> type[Component]:
    _REGISTRY[component_cls.name] = component_cls()
    return component_cls


def get(name: str) -> Component:
    if name not in _REGISTRY:
        raise KeyError(f"unknown component: {name!r}")
    return _REGISTRY[name]


def all_names() -> list[str]:
    return sorted(_REGISTRY)
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/components/test_base.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add manim_skill/components/base.py tests/components/test_base.py
git commit -m "feat: component base class and registry"
```

---

## Task 4: TextBeat 元件

**Files:**
- Create: `manim_skill/components/text_beat.py`
- Modify: `manim_skill/components/__init__.py`
- Test: `tests/components/test_text_beat.py`

- [ ] **Step 1: 寫失敗測試**

`tests/components/test_text_beat.py`:

```python
from manim import Text, VGroup

from manim_skill.components.text_beat import TextBeat, TextBeatParams


def test_title_style_builds_header_text():
    comp = TextBeat()
    mobj = comp.build(TextBeatParams(text="Hello", style="title"))
    assert isinstance(mobj, VGroup)
    texts = [m for m in mobj if isinstance(m, Text)]
    assert any("Hello" in t.text for t in texts)


def test_title_with_subtitle_has_two_texts():
    comp = TextBeat()
    mobj = comp.build(
        TextBeatParams(text="Hello", subtitle="world", style="title")
    )
    texts = [m for m in mobj if isinstance(m, Text)]
    assert len(texts) == 2


def test_bullets_style_builds_header_plus_one_per_bullet():
    comp = TextBeat()
    mobj = comp.build(
        TextBeatParams(text="Topics", style="bullets", bullets=["a", "b", "c"])
    )
    texts = [m for m in mobj if isinstance(m, Text)]
    assert len(texts) == 4  # header + 3 bullets
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/components/test_text_beat.py -v`
Expected: FAIL（`ModuleNotFoundError: manim_skill.components.text_beat`）

- [ ] **Step 3: 實作 TextBeat**

`manim_skill/components/text_beat.py`:

```python
from __future__ import annotations

from typing import Literal

from manim import DOWN, LEFT, FadeIn, Mobject, Scene, Text, VGroup
from pydantic import BaseModel, Field

from manim_skill.components.base import Component, register


class TextBeatParams(BaseModel):
    text: str
    subtitle: str | None = None
    style: Literal["title", "caption", "bullets"] = "title"
    bullets: list[str] = Field(default_factory=list)


@register
class TextBeat(Component):
    name = "TextBeat"
    Params = TextBeatParams

    def build(self, params: TextBeatParams) -> Mobject:
        group = VGroup()
        if params.style == "bullets":
            group.add(Text(params.text, font_size=44))
            for bullet in params.bullets:
                group.add(Text(f"• {bullet}", font_size=32))
            group.arrange(DOWN, aligned_edge=LEFT, buff=0.4)
        else:
            header_size = 56 if params.style == "title" else 36
            group.add(Text(params.text, font_size=header_size))
            if params.subtitle:
                group.add(Text(params.subtitle, font_size=32))
            group.arrange(DOWN, buff=0.4)
        return group

    def animate(
        self, scene: Scene, mobject: Mobject, params: TextBeatParams
    ) -> None:
        scene.play(FadeIn(mobject))
```

- [ ] **Step 4: 更新 components 套件匯入**

`manim_skill/components/__init__.py`（取代空內容）:

```python
from manim_skill.components import text_beat  # noqa: F401
```

- [ ] **Step 5: 執行測試確認通過**

Run: `pytest tests/components/test_text_beat.py -v`
Expected: PASS（3 passed）

- [ ] **Step 6: Commit**

```bash
git add manim_skill/components/text_beat.py manim_skill/components/__init__.py tests/components/test_text_beat.py
git commit -m "feat: TextBeat component"
```

---

## Task 5: CodeWalkthrough 元件

**Files:**
- Create: `manim_skill/components/code_walkthrough.py`
- Modify: `manim_skill/components/__init__.py`
- Test: `tests/components/test_code_walkthrough.py`

注意：manim 的 `Code` mobject 建構 API 在不同版本略有差異。本任務針對 manim ≥0.19 撰寫（`Code(code_string=..., language=...)`）。若 Step 4 建構失敗，執行 `python -c "import manim, inspect; print(inspect.signature(manim.Code))"` 查看實際簽名並調整關鍵字參數；測試會即時抓出不符。

- [ ] **Step 1: 寫失敗測試**

`tests/components/test_code_walkthrough.py`:

```python
from manim import Mobject

from manim_skill.components.code_walkthrough import (
    CodeWalkthrough,
    CodeWalkthroughParams,
)


def test_build_returns_non_empty_mobject():
    comp = CodeWalkthrough()
    mobj = comp.build(
        CodeWalkthroughParams(code="print('hi')\nx = 1", language="python")
    )
    assert isinstance(mobj, Mobject)
    assert len(mobj.submobjects) > 0


def test_highlight_lines_default_is_empty():
    params = CodeWalkthroughParams(code="x = 1")
    assert params.language == "python"
    assert params.highlight_lines == []
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/components/test_code_walkthrough.py -v`
Expected: FAIL（`ModuleNotFoundError: manim_skill.components.code_walkthrough`）

- [ ] **Step 3: 實作 CodeWalkthrough**

`manim_skill/components/code_walkthrough.py`:

```python
from __future__ import annotations

from manim import Code, Create, Indicate, Mobject, Scene
from pydantic import BaseModel, Field

from manim_skill.components.base import Component, register


class CodeWalkthroughParams(BaseModel):
    code: str
    language: str = "python"
    # 每個元素是一組要依序強調的行號（1-based）。
    # Plan 1 為粗粒度：每組對整個程式碼區塊做一次 Indicate。
    # 逐行精準高亮留待 Plan 2。
    highlight_lines: list[list[int]] = Field(default_factory=list)


@register
class CodeWalkthrough(Component):
    name = "CodeWalkthrough"
    Params = CodeWalkthroughParams

    def build(self, params: CodeWalkthroughParams) -> Mobject:
        return Code(code_string=params.code, language=params.language)

    def animate(
        self, scene: Scene, mobject: Mobject, params: CodeWalkthroughParams
    ) -> None:
        scene.play(Create(mobject))
        for _group in params.highlight_lines:
            scene.play(Indicate(mobject))
```

- [ ] **Step 4: 更新 components 套件匯入**

`manim_skill/components/__init__.py`（取代內容）:

```python
from manim_skill.components import code_walkthrough  # noqa: F401
from manim_skill.components import text_beat  # noqa: F401
```

- [ ] **Step 5: 執行測試確認通過**

Run: `pytest tests/components/test_code_walkthrough.py -v`
Expected: PASS（2 passed）。若 `Code(...)` 建構報錯，依任務開頭說明調整關鍵字參數。

- [ ] **Step 6: Commit**

```bash
git add manim_skill/components/code_walkthrough.py manim_skill/components/__init__.py tests/components/test_code_walkthrough.py
git commit -m "feat: CodeWalkthrough component"
```

---

## Task 6: 寬鬆 Spec 解析器

**Files:**
- Create: `manim_skill/spec/parse.py`
- Test: `tests/spec/test_parse.py`

- [ ] **Step 1: 寫失敗測試**

`tests/spec/test_parse.py`:

```python
import pytest

from manim_skill.spec.parse import SpecParseError, parse_spec_text


def test_parse_clean_json():
    assert parse_spec_text('{"title": "T", "beats": []}') == {
        "title": "T",
        "beats": [],
    }


def test_parse_markdown_fenced_json():
    text = 'Sure, here it is:\n```json\n{"title": "T"}\n```\nhope that helps'
    assert parse_spec_text(text) == {"title": "T"}


def test_parse_prose_wrapped_object():
    text = 'blah blah {"title": "T"} trailing words'
    assert parse_spec_text(text) == {"title": "T"}


def test_parse_trailing_comma_recovered_via_json5():
    assert parse_spec_text('{"title": "T", "beats": [],}') == {
        "title": "T",
        "beats": [],
    }


def test_parse_no_json_object_raises():
    with pytest.raises(SpecParseError):
        parse_spec_text("there is no json here at all")


def test_parse_unrecoverable_garbage_raises():
    with pytest.raises(SpecParseError):
        parse_spec_text('{"title": "T" "beats" oops }')
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/spec/test_parse.py -v`
Expected: FAIL（`ModuleNotFoundError: manim_skill.spec.parse`）

- [ ] **Step 3: 實作解析器**

`manim_skill/spec/parse.py`:

```python
from __future__ import annotations

import json
import re

_FENCE = re.compile(r"```(?:json5?|JSON)?\s*(.*?)```", re.DOTALL)


class SpecParseError(ValueError):
    """Raised when text cannot be parsed into a spec dict."""


def parse_spec_text(text: str) -> dict:
    """Extract a JSON object from possibly-noisy text.

    Tolerates markdown fences, surrounding prose, and (via json5)
    trailing commas. Raises SpecParseError if nothing usable is found.
    """
    candidate = text.strip()

    fence_match = _FENCE.search(candidate)
    if fence_match:
        candidate = fence_match.group(1).strip()

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise SpecParseError("no JSON object found in text")
    candidate = candidate[start : end + 1]

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    try:
        import json5

        return json5.loads(candidate)
    except Exception as exc:  # noqa: BLE001 - json5 raises various types
        raise SpecParseError(f"could not parse spec JSON: {exc}") from exc
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/spec/test_parse.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: Commit**

```bash
git add manim_skill/spec/parse.py tests/spec/test_parse.py
git commit -m "feat: lenient spec text parser"
```

---

## Task 7: Spec 驗證器

**Files:**
- Create: `manim_skill/spec/validate.py`
- Test: `tests/spec/test_validate.py`

- [ ] **Step 1: 寫失敗測試**

`tests/spec/test_validate.py`:

```python
import pytest

from manim_skill.spec.schema import SceneSpec
from manim_skill.spec.validate import SpecValidationError, validate_spec


def test_validate_good_spec_returns_scenespec():
    raw = {
        "title": "T",
        "beats": [{"component": "TextBeat", "params": {"text": "hi"}}],
    }
    spec = validate_spec(raw)
    assert isinstance(spec, SceneSpec)
    assert spec.title == "T"


def test_validate_unknown_component_raises():
    raw = {"title": "T", "beats": [{"component": "NopeNotReal", "params": {}}]}
    with pytest.raises(SpecValidationError):
        validate_spec(raw)


def test_validate_bad_component_params_raises():
    raw = {
        "title": "T",
        "beats": [
            {"component": "TextBeat", "params": {"text": "hi", "style": "bogus"}}
        ],
    }
    with pytest.raises(SpecValidationError):
        validate_spec(raw)


def test_validate_raw_beat_without_code_raises():
    raw = {"title": "T", "beats": [{"component": "raw"}]}
    with pytest.raises(SpecValidationError):
        validate_spec(raw)


def test_validate_raw_beat_with_code_ok():
    raw = {"title": "T", "beats": [{"component": "raw", "code": "self.wait(1)"}]}
    spec = validate_spec(raw)
    assert spec.beats[0].code == "self.wait(1)"


def test_validate_bad_top_level_schema_raises():
    with pytest.raises(SpecValidationError):
        validate_spec({"title": "T", "beats": []})
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/spec/test_validate.py -v`
Expected: FAIL（`ModuleNotFoundError: manim_skill.spec.validate`）

- [ ] **Step 3: 實作驗證器**

`manim_skill/spec/validate.py`:

```python
from __future__ import annotations

from pydantic import ValidationError

from manim_skill.components import base as registry
from manim_skill.spec.schema import Beat, SceneSpec


class SpecValidationError(ValueError):
    """Raised when a spec dict fails schema or component validation."""


def validate_spec(raw: dict) -> SceneSpec:
    """Validate a raw dict into a SceneSpec.

    Checks the top-level schema, then for each beat checks that the
    component exists and its params match the component's schema.
    Raw beats are checked for a non-empty `code` field.
    """
    try:
        spec = SceneSpec.model_validate(raw)
    except ValidationError as exc:
        raise SpecValidationError(f"spec schema invalid: {exc}") from exc

    for index, beat in enumerate(spec.beats):
        _validate_beat(index, beat)
    return spec


def _validate_beat(index: int, beat: Beat) -> None:
    if beat.component == "raw":
        if not beat.code:
            raise SpecValidationError(
                f"beat {index}: raw beat requires a non-empty 'code' field"
            )
        return

    try:
        component = registry.get(beat.component)
    except KeyError as exc:
        raise SpecValidationError(f"beat {index}: {exc}") from exc

    try:
        component.Params.model_validate(beat.params)
    except ValidationError as exc:
        raise SpecValidationError(
            f"beat {index}: invalid params for {beat.component}: {exc}"
        ) from exc
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/spec/test_validate.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: Commit**

```bash
git add manim_skill/spec/validate.py tests/spec/test_validate.py
git commit -m "feat: spec validator with per-beat component checks"
```

---

## Task 8: Builder I/O — 寫渲染輸入檔

**Files:**
- Modify: `manim_skill/builder/__init__.py`
- Test: `tests/builder/test_builder_io.py`

- [ ] **Step 1: 寫失敗測試**

`tests/builder/test_builder_io.py`:

```python
import json

from manim_skill.builder import write_render_inputs
from manim_skill.spec.schema import Beat, SceneSpec


def test_write_render_inputs_creates_both_files(tmp_path):
    spec = SceneSpec(title="T", beats=[Beat(component="raw", code="pass")])
    spec_path, entry_path = write_render_inputs(spec, tmp_path)

    assert spec_path.exists()
    assert entry_path.exists()


def test_written_spec_json_roundtrips(tmp_path):
    spec = SceneSpec(title="My Title", beats=[Beat(component="raw", code="pass")])
    spec_path, _ = write_render_inputs(spec, tmp_path)

    loaded = json.loads(spec_path.read_text(encoding="utf-8"))
    assert loaded["title"] == "My Title"
    assert loaded["beats"][0]["component"] == "raw"


def test_entry_file_references_specscene(tmp_path):
    spec = SceneSpec(title="T", beats=[Beat(component="raw", code="pass")])
    _, entry_path = write_render_inputs(spec, tmp_path)

    content = entry_path.read_text(encoding="utf-8")
    assert "SpecScene" in content


def test_write_creates_missing_workdir(tmp_path):
    target = tmp_path / "nested" / "workdir"
    spec = SceneSpec(title="T", beats=[Beat(component="raw", code="pass")])
    spec_path, _ = write_render_inputs(spec, target)
    assert spec_path.parent == target
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/builder/test_builder_io.py -v`
Expected: FAIL（`ImportError: cannot import name 'write_render_inputs'`）

- [ ] **Step 3: 實作 write_render_inputs**

`manim_skill/builder/__init__.py`（取代空內容）:

```python
from __future__ import annotations

from pathlib import Path

from manim_skill.spec.schema import SceneSpec

_ENTRY_SOURCE = (
    "from manim_skill.builder.spec_scene import SpecScene\n"
    "\n"
    "__all__ = ['SpecScene']\n"
)


def write_render_inputs(spec: SceneSpec, workdir) -> tuple[Path, Path]:
    """Write the two files manim needs to render a spec.

    Returns (spec_path, entry_path). The entry file is what `manim`
    is pointed at; it imports SpecScene, which reads spec.json via
    the MANIM_SKILL_SPEC environment variable at render time.
    """
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    spec_path = workdir / "spec.json"
    spec_path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")

    entry_path = workdir / "scene_entry.py"
    entry_path.write_text(_ENTRY_SOURCE, encoding="utf-8")

    return spec_path, entry_path
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/builder/test_builder_io.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add manim_skill/builder/__init__.py tests/builder/test_builder_io.py
git commit -m "feat: builder write_render_inputs (spec.json + entry file)"
```

---

## Task 9: exec_raw — 執行 raw beat 程式碼

**Files:**
- Create: `manim_skill/builder/raw.py`
- Test: `tests/builder/test_raw.py`

- [ ] **Step 1: 寫失敗測試**

`tests/builder/test_raw.py`:

```python
import pytest

from manim_skill.builder.raw import exec_raw


class FakeScene:
    def __init__(self):
        self.calls = []

    def play(self, *args, **kwargs):
        self.calls.append(("play", args, kwargs))

    def wait(self, *args, **kwargs):
        self.calls.append(("wait", args, kwargs))


def test_exec_raw_binds_self_to_scene():
    scene = FakeScene()
    exec_raw("self.wait(2)", scene)
    assert ("wait", (2,), {}) in scene.calls


def test_exec_raw_exposes_manim_names_without_import():
    scene = FakeScene()
    # Circle is a manim name; must be available in the exec namespace.
    exec_raw("c = Circle()", scene)  # must not raise NameError


def test_exec_raw_propagates_errors():
    scene = FakeScene()
    with pytest.raises(ZeroDivisionError):
        exec_raw("x = 1 / 0", scene)
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/builder/test_raw.py -v`
Expected: FAIL（`ModuleNotFoundError: manim_skill.builder.raw`）

- [ ] **Step 3: 實作 exec_raw**

`manim_skill/builder/raw.py`:

```python
from __future__ import annotations

from typing import Any

import manim


def exec_raw(code: str, scene: Any) -> None:
    """Execute a raw beat's code with `self`/`scene` bound to the scene.

    All public manim names are injected into the namespace so the code
    can use `Circle`, `Text`, `FadeIn`, etc. without imports. The code
    runs inside the render container; the container is the sandbox
    boundary (no network, --rm). Errors propagate to the caller so the
    repair loop (Plan 4) can react.
    """
    namespace: dict[str, Any] = {"self": scene, "scene": scene}
    for name in getattr(manim, "__all__", dir(manim)):
        namespace[name] = getattr(manim, name)
    exec(compile(code, "<raw-beat>", "exec"), namespace)
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/builder/test_raw.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add manim_skill/builder/raw.py tests/builder/test_raw.py
git commit -m "feat: exec_raw for raw beat code execution"
```

---

## Task 10: apply_camera — 套用 camera 指令

**Files:**
- Create: `manim_skill/builder/camera.py`
- Test: `tests/builder/test_camera.py`

說明：Plan 1 只實作 `zoom` 與 `reset` 兩個 camera 動作；`focus` 與 `pan` 需要元件對外暴露具名元素，留待後續計畫。`apply_camera` 對 `focus`/`pan` 為 no-op。

- [ ] **Step 1: 寫失敗測試**

`tests/builder/test_camera.py`:

```python
from manim_skill.builder.camera import apply_camera
from manim_skill.spec.schema import CameraDirective


class FakeFrame:
    def __init__(self):
        self.ops = []

    @property
    def animate(self):
        self.ops.append("animate")
        return self

    def scale(self, factor):
        self.ops.append(("scale", factor))
        return self

    def restore(self):
        self.ops.append("restore")
        return self


class FakeCamera:
    def __init__(self):
        self.frame = FakeFrame()


class FakeScene:
    def __init__(self):
        self.camera = FakeCamera()
        self.played = []

    def play(self, *args, **kwargs):
        self.played.append((args, kwargs))


def test_zoom_scales_frame_by_inverse_and_plays():
    scene = FakeScene()
    apply_camera(scene, CameraDirective(action="zoom", scale=2.0))
    assert ("scale", 0.5) in scene.camera.frame.ops
    assert len(scene.played) == 1


def test_reset_restores_frame_and_plays():
    scene = FakeScene()
    apply_camera(scene, CameraDirective(action="reset"))
    assert "restore" in scene.camera.frame.ops
    assert len(scene.played) == 1


def test_focus_is_noop_in_plan_1():
    scene = FakeScene()
    apply_camera(scene, CameraDirective(action="focus", target="x"))
    assert scene.played == []


def test_pan_is_noop_in_plan_1():
    scene = FakeScene()
    apply_camera(scene, CameraDirective(action="pan"))
    assert scene.played == []
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/builder/test_camera.py -v`
Expected: FAIL（`ModuleNotFoundError: manim_skill.builder.camera`）

- [ ] **Step 3: 實作 apply_camera**

`manim_skill/builder/camera.py`:

```python
from __future__ import annotations

from typing import Any

from manim_skill.spec.schema import CameraDirective


def apply_camera(scene: Any, directive: CameraDirective) -> None:
    """Apply a camera directive to a MovingCameraScene.

    Plan 1 supports `zoom` and `reset`. `focus` and `pan` need named
    element targeting and are no-ops until a later plan. `reset`
    assumes the scene saved camera frame state at construct() start.
    """
    frame = scene.camera.frame

    if directive.action == "zoom":
        scale = directive.scale or 1.0
        scene.play(frame.animate.scale(1.0 / scale))
    elif directive.action == "reset":
        scene.play(frame.animate.restore())
    # focus / pan: deferred to a later plan
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/builder/test_camera.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add manim_skill/builder/camera.py tests/builder/test_camera.py
git commit -m "feat: apply_camera (zoom + reset)"
```

---

## Task 11: SpecScene — 組裝 builder

**Files:**
- Create: `manim_skill/builder/spec_scene.py`
- Test: `tests/builder/test_spec_scene.py`

說明：`SpecScene` 完整渲染行為由 Task 15 的 docker 整合測試覆蓋。本任務的單元測試只驗證可匯入、繼承關係，以及 `load_spec_from_env` 的讀取邏輯。

- [ ] **Step 1: 寫失敗測試**

`tests/builder/test_spec_scene.py`:

```python
import json

import pytest
from manim import MovingCameraScene

from manim_skill.builder.spec_scene import (
    SPEC_ENV_VAR,
    SpecScene,
    load_spec_from_env,
)


def test_spec_scene_is_moving_camera_scene():
    assert issubclass(SpecScene, MovingCameraScene)


def test_load_spec_from_env_reads_and_validates(tmp_path, monkeypatch):
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(
        json.dumps(
            {
                "title": "T",
                "beats": [{"component": "raw", "code": "self.wait(1)"}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(SPEC_ENV_VAR, str(spec_file))

    spec = load_spec_from_env()
    assert spec.title == "T"
    assert spec.beats[0].component == "raw"


def test_load_spec_from_env_missing_var_raises(monkeypatch):
    monkeypatch.delenv(SPEC_ENV_VAR, raising=False)
    with pytest.raises(RuntimeError):
        load_spec_from_env()
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/builder/test_spec_scene.py -v`
Expected: FAIL（`ModuleNotFoundError: manim_skill.builder.spec_scene`）

- [ ] **Step 3: 實作 SpecScene**

`manim_skill/builder/spec_scene.py`:

```python
from __future__ import annotations

import json
import os
from pathlib import Path

from manim import DOWN, FadeOut, MovingCameraScene, Text

from manim_skill.builder.camera import apply_camera
from manim_skill.builder.raw import exec_raw
from manim_skill.components import base as registry
from manim_skill.spec.schema import Beat, SceneSpec
from manim_skill.spec.validate import validate_spec

SPEC_ENV_VAR = "MANIM_SKILL_SPEC"


def load_spec_from_env() -> SceneSpec:
    """Load and validate the spec pointed to by MANIM_SKILL_SPEC."""
    path = os.environ.get(SPEC_ENV_VAR)
    if not path:
        raise RuntimeError(f"{SPEC_ENV_VAR} environment variable is not set")
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_spec(raw)


class SpecScene(MovingCameraScene):
    """Renders a SceneSpec: every beat played sequentially in one scene.

    Per-beat isolated rendering + stitching is a render-backend concern
    introduced in Plan 3; Plan 1 plays all beats in a single scene.
    """

    def construct(self) -> None:
        spec = load_spec_from_env()
        self.camera.frame.save_state()
        for beat in spec.beats:
            self._render_beat(beat)

    def _render_beat(self, beat: Beat) -> None:
        if beat.component == "raw":
            exec_raw(beat.code or "", self)
        else:
            component = registry.get(beat.component)
            params = component.Params.model_validate(beat.params)
            mobject = component.build(params)
            component.animate(self, mobject, params)

        if beat.caption:
            caption = Text(beat.caption, font_size=28).to_edge(DOWN)
            self.play(FadeIn(caption))

        if beat.camera:
            apply_camera(self, beat.camera)

        if beat.duration:
            self.wait(beat.duration)

        if self.mobjects:
            self.play(*[FadeOut(m) for m in list(self.mobjects)])
```

注意：上面用到 `FadeIn`，需補進 import。將第一行 manim import 改為：
`from manim import DOWN, FadeIn, FadeOut, MovingCameraScene, Text`

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/builder/test_spec_scene.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 執行全套單元測試（排除 docker）**

Run: `pytest -v -m "not docker"`
Expected: PASS（目前所有非 docker 測試皆通過）

- [ ] **Step 6: Commit**

```bash
git add manim_skill/builder/spec_scene.py tests/builder/test_spec_scene.py
git commit -m "feat: SpecScene builder assembling beats into one scene"
```

---

## Task 12: 渲染用 Docker Image

**Files:**
- Create: `docker/Dockerfile`
- Create: `.dockerignore`

說明：Dockerfile 無法用 pytest 做 TDD，本任務以「建置 + 冒煙執行」作為驗證。

- [ ] **Step 1: 建立 `.dockerignore`**

`.dockerignore`:

```
.git
.superpowers
docs
tests
**/__pycache__
*.pyc
.pytest_cache
*.egg-info
```

- [ ] **Step 2: 建立 `docker/Dockerfile`**

`docker/Dockerfile`:

```dockerfile
FROM manimcommunity/manim:v0.19.0

USER root
COPY . /opt/manim-skill
RUN pip install --no-cache-dir /opt/manim-skill
USER manimuser
```

說明：若 `manimcommunity/manim:v0.19.0` tag 不存在，改用 `docker pull manimcommunity/manim:stable` 確認可用版本後填回（需為 0.19.x 以支援 Python 3.13）。base image 的非 root 使用者通常為 `manimuser`；若 `USER manimuser` 報錯，執行 `docker run --rm manimcommunity/manim:v0.19.0 whoami` 確認實際使用者名稱。

- [ ] **Step 3: 建置 image**

Run:
```bash
docker build -t manim-skill:latest -f docker/Dockerfile .
```
Expected: 建置成功，最後輸出 `naming to docker.io/library/manim-skill:latest`。

- [ ] **Step 4: 冒煙測試 — 套件可在 image 內匯入**

Run:
```bash
docker run --rm manim-skill:latest python -c "import manim_skill.builder.spec_scene; print('ok')"
```
Expected: 印出 `ok`。

- [ ] **Step 5: Commit**

```bash
git add docker/Dockerfile .dockerignore
git commit -m "build: render docker image (manim + manim-skill)"
```

---

## Task 13: render_spec_to_mp4 — 在 Docker 內渲染

**Files:**
- Create: `manim_skill/render/docker_render.py`
- Test: `tests/render/test_docker_render.py`

- [ ] **Step 1: 寫失敗測試（標記為 docker 整合測試）**

`tests/render/test_docker_render.py`:

```python
import pytest

from manim_skill.render.docker_render import RenderError, render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec


@pytest.mark.docker
def test_render_textbeat_spec_produces_mp4(tmp_path):
    spec = SceneSpec(
        title="T",
        beats=[
            Beat(
                component="TextBeat",
                params={"text": "Hello"},
                duration=1.0,
            )
        ],
    )
    mp4 = render_spec_to_mp4(spec, tmp_path)
    assert mp4.exists()
    assert mp4.stat().st_size > 0


@pytest.mark.docker
def test_render_raw_beat_failure_raises_render_error(tmp_path):
    spec = SceneSpec(
        title="T",
        beats=[Beat(component="raw", code="this is not valid python !!!")],
    )
    with pytest.raises(RenderError):
        render_spec_to_mp4(spec, tmp_path)
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/render/test_docker_render.py -v`
Expected: FAIL（`ModuleNotFoundError: manim_skill.render.docker_render`）

- [ ] **Step 3: 實作 render_spec_to_mp4**

`manim_skill/render/docker_render.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

from manim_skill.builder import write_render_inputs
from manim_skill.spec.schema import SceneSpec

IMAGE = "manim-skill:latest"
RENDER_TIMEOUT_SECONDS = 300


class RenderError(RuntimeError):
    """Raised when a docker render fails, times out, or produces no output."""


def render_spec_to_mp4(spec: SceneSpec, workdir) -> Path:
    """Render a spec to an mp4 inside the manim-skill docker image.

    Plan 1 sandboxing: --network none, --rm, and a hard timeout.
    Stricter hardening (non-root, read-only fs, resource caps) is
    added in Plan 3.
    """
    workdir = Path(workdir).resolve()
    write_render_inputs(spec, workdir)
    out_dir = workdir / "out"
    out_dir.mkdir(exist_ok=True)

    cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "-v", f"{workdir}:/work",
        "-e", "MANIM_SKILL_SPEC=/work/spec.json",
        "-w", "/work",
        IMAGE,
        "manim", "-ql",
        "--media_dir", "/work/out",
        "--format", "mp4",
        "/work/scene_entry.py", "SpecScene",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=RENDER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RenderError(
            f"render timed out after {RENDER_TIMEOUT_SECONDS}s"
        ) from exc

    if result.returncode != 0:
        raise RenderError(f"manim render failed:\n{result.stderr}")

    mp4s = sorted(out_dir.rglob("*.mp4"))
    if not mp4s:
        raise RenderError(
            f"render produced no mp4. stderr:\n{result.stderr}"
        )
    return mp4s[0]
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/render/test_docker_render.py -v -m docker`
Expected: PASS（2 passed）。第一次執行較慢（docker 啟動 + 渲染）。
若在 Windows 出現掛載目錄寫入權限錯誤，確認 Docker Desktop 已將該磁碟機加入 file sharing；本任務不加 `--user`，非 root 強化留待 Plan 3。

- [ ] **Step 5: Commit**

```bash
git add manim_skill/render/docker_render.py tests/render/test_docker_render.py
git commit -m "feat: render_spec_to_mp4 via docker"
```

---

## Task 14: mp4_to_gif — 轉檔

**Files:**
- Create: `manim_skill/render/convert.py`
- Test: `tests/render/test_convert.py`

- [ ] **Step 1: 寫失敗測試（docker 整合測試）**

`tests/render/test_convert.py`:

```python
import pytest

from manim_skill.render.convert import mp4_to_gif
from manim_skill.render.docker_render import render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec


@pytest.mark.docker
def test_mp4_to_gif_produces_gif(tmp_path):
    spec = SceneSpec(
        title="T",
        beats=[
            Beat(component="TextBeat", params={"text": "Hi"}, duration=1.0)
        ],
    )
    mp4 = render_spec_to_mp4(spec, tmp_path)
    gif = mp4_to_gif(mp4)
    assert gif.exists()
    assert gif.suffix == ".gif"
    assert gif.stat().st_size > 0
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/render/test_convert.py -v`
Expected: FAIL（`ModuleNotFoundError: manim_skill.render.convert`）

- [ ] **Step 3: 實作 mp4_to_gif**

`manim_skill/render/convert.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

from manim_skill.render.docker_render import IMAGE, RenderError

CONVERT_TIMEOUT_SECONDS = 120


def mp4_to_gif(mp4_path) -> Path:
    """Convert an mp4 to a README-friendly gif via ffmpeg in docker.

    Two-pass palette conversion for reasonable size and quality. The
    gif is written next to the mp4. ffmpeg ships inside the image.
    """
    mp4_path = Path(mp4_path).resolve()
    workdir = mp4_path.parent
    gif_path = mp4_path.with_suffix(".gif")
    palette = "palette.png"
    vf = "fps=15,scale=640:-1:flags=lanczos"

    palette_cmd = [
        "docker", "run", "--rm", "--network", "none",
        "-v", f"{workdir}:/work", "-w", "/work",
        IMAGE,
        "ffmpeg", "-y", "-i", mp4_path.name,
        "-vf", f"{vf},palettegen", palette,
    ]
    gif_cmd = [
        "docker", "run", "--rm", "--network", "none",
        "-v", f"{workdir}:/work", "-w", "/work",
        IMAGE,
        "ffmpeg", "-y", "-i", mp4_path.name, "-i", palette,
        "-lavfi", f"{vf}[x];[x][1:v]paletteuse",
        gif_path.name,
    ]

    for cmd in (palette_cmd, gif_cmd):
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=CONVERT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise RenderError("gif conversion timed out") from exc
        if result.returncode != 0:
            raise RenderError(f"ffmpeg failed:\n{result.stderr}")

    if not gif_path.exists():
        raise RenderError("gif conversion produced no file")
    return gif_path
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/render/test_convert.py -v -m docker`
Expected: PASS（1 passed）

- [ ] **Step 5: Commit**

```bash
git add manim_skill/render/convert.py tests/render/test_convert.py
git commit -m "feat: mp4_to_gif conversion via ffmpeg in docker"
```

---

## Task 15: 端到端整合測試 + fixtures

**Files:**
- Create: `tests/fixtures/specs/text_and_code.txt`
- Create: `tests/fixtures/specs/with_raw_beat.json`
- Create: `tests/test_end_to_end.py`

- [ ] **Step 1: 建立 fixture — 帶 prose 與 markdown fence 的 spec 文字**

`tests/fixtures/specs/text_and_code.txt`:

```
這是模擬 LLM 輸出的文字，外面包了一些散文。

```json
{
  "title": "Plan 1 端到端測試",
  "aspect_ratio": "16:9",
  "beats": [
    {
      "component": "TextBeat",
      "params": {"text": "Self-Attention", "subtitle": "概念示範", "style": "title"},
      "caption": "開場標題",
      "duration": 1.0
    },
    {
      "component": "CodeWalkthrough",
      "params": {"code": "scores = Q @ K.T\nweights = softmax(scores)", "language": "python"},
      "caption": "關鍵程式碼",
      "duration": 1.0
    }
  ]
}
```

希望這份動畫有幫助。
```

- [ ] **Step 2: 建立 fixture — 含 raw beat 的 spec**

`tests/fixtures/specs/with_raw_beat.json`:

```json
{
  "title": "Raw beat 示範",
  "beats": [
    {
      "component": "raw",
      "code": "circle = Circle()\nself.play(Create(circle))\nself.wait(1)",
      "duration": 0.5
    }
  ]
}
```

- [ ] **Step 3: 寫端到端測試**

`tests/test_end_to_end.py`:

```python
import json
from pathlib import Path

import pytest

from manim_skill.render.convert import mp4_to_gif
from manim_skill.render.docker_render import render_spec_to_mp4
from manim_skill.spec.parse import parse_spec_text
from manim_skill.spec.validate import validate_spec

FIXTURES = Path(__file__).parent / "fixtures" / "specs"


def test_parse_then_validate_noisy_text_fixture():
    # 純資料層的端到端：不需 docker。
    raw_text = (FIXTURES / "text_and_code.txt").read_text(encoding="utf-8")
    data = parse_spec_text(raw_text)
    spec = validate_spec(data)
    assert spec.title == "Plan 1 端到端測試"
    assert [b.component for b in spec.beats] == ["TextBeat", "CodeWalkthrough"]


@pytest.mark.docker
def test_full_pipeline_noisy_text_to_gif(tmp_path):
    raw_text = (FIXTURES / "text_and_code.txt").read_text(encoding="utf-8")
    spec = validate_spec(parse_spec_text(raw_text))
    mp4 = render_spec_to_mp4(spec, tmp_path)
    gif = mp4_to_gif(mp4)
    assert mp4.stat().st_size > 0
    assert gif.stat().st_size > 0


@pytest.mark.docker
def test_full_pipeline_raw_beat_to_mp4(tmp_path):
    data = json.loads(
        (FIXTURES / "with_raw_beat.json").read_text(encoding="utf-8")
    )
    spec = validate_spec(data)
    mp4 = render_spec_to_mp4(spec, tmp_path)
    assert mp4.stat().st_size > 0
```

- [ ] **Step 4: 執行純資料層測試**

Run: `pytest tests/test_end_to_end.py::test_parse_then_validate_noisy_text_fixture -v`
Expected: PASS

- [ ] **Step 5: 執行完整 docker 端到端測試**

Run: `pytest tests/test_end_to_end.py -v -m docker`
Expected: PASS（2 passed）

- [ ] **Step 6: 執行全套測試**

Run: `pytest -v`
Expected: 全部 PASS（含 docker 標記）。

- [ ] **Step 7: Commit**

```bash
git add tests/fixtures/ tests/test_end_to_end.py
git commit -m "test: end-to-end pipeline integration tests with fixtures"
```

---

## Self-Review

**1. Spec coverage（對照設計文件 §4–§9）**

- §4.1 scene spec 格式（component/params/code/caption/duration/camera）→ Task 2 ✓
- §4.1 spec 為唯一契約、raw 為特殊 beat → Task 2 + Task 11 `_render_beat` ✓
- §4.2 元件庫單一事實來源（每元件宣告 Params schema）→ Task 3 + Task 4/5 ✓
- §4.2 初版元件（Plan 1 範圍：TextBeat + CodeWalkthrough，其餘 6 個元件為 Plan 2）→ Task 4, 5 ✓（範圍內）
- §4.3 運鏡為 beat 屬性、收斂詞彙、base scene = MovingCameraScene → Task 2 + Task 10 + Task 11 ✓（focus/pan 明確延後）
- §5 寬鬆解析（抽取、json5、夾雜散文/fence/trailing comma）→ Task 6 ✓
- §5 schema 驗證 → Task 7 ✓
- §6 docker 渲染、官方 manim image + 本套件、--network none/--rm/timeout → Task 12, 13 ✓
- §6 mp4 + gif 產出 → Task 13, 14 ✓
- §8 測試策略：元件結構性斷言（非逐像素）、解析層用擬真垃圾猛打、docker 整合測試與單元測試分離（`docker` marker）→ Task 4–7, 13–15 ✓
- §9 repo 結構（components/ builder/ spec/ render/）→ File Structure ✓

**明確不在 Plan 1 範圍（依計畫切分屬後續計畫）：** 其餘 6 個元件（Plan 2）；batch/clip/beat job 階層、佇列、平行渲染、stitch、zip+manifest、快取、沙箱強化（Plan 3）；LLM analyze/codegen/repair loop（Plan 4）；CLI 與 agent skill 封裝（Plan 5）。Plan 1 的 SpecScene 一次渲染所有 beat，per-beat 隔離為 Plan 3，已在 Task 11 註明。

**2. Placeholder scan：** 無 TBD/TODO/「實作後續」。Task 5 的 `highlight_lines` 粗粒度行為與 Task 10 的 focus/pan no-op 皆有明確說明與後續歸屬，非佔位。Task 12 為建置驗證型任務（Dockerfile 無法 pytest TDD），已說明。

**3. Type consistency：** `SceneSpec`/`Beat`/`CameraDirective`（Task 2）貫穿 Task 7/8/11/13。`Component.build/animate`、`register`/`get`/`all_names`（Task 3）一致用於 Task 4/5/11。`write_render_inputs`（Task 8）回傳 `(spec_path, entry_path)`，Task 13 呼叫一致。`IMAGE`/`RenderError`（Task 13）被 Task 14 匯入重用，名稱一致。`SPEC_ENV_VAR`/`load_spec_from_env`/`SpecScene`（Task 11）與 Task 8 寫入的 entry 檔內容一致（`from manim_skill.builder.spec_scene import SpecScene`）。`SpecParseError`（Task 6）、`SpecValidationError`（Task 7）名稱一致。

**已修正項：** Task 11 Step 3 程式碼用到 `FadeIn` 但 import 行原本遺漏，已於該步驟下方明確補上修正後的 import 行。

---

## Execution Handoff

Plan 完成並存於 `docs/superpowers/plans/2026-05-14-plan-1-core-spec-builder-render.md`。兩種執行方式：

**1. Subagent-Driven（推薦）** — 每個 task 派一個全新的 subagent，task 之間由我審核，迭代快、context 乾淨。

**2. Inline Execution** — 在本對話 session 內逐 task 執行，分批設檢查點審核。

要用哪一種？
