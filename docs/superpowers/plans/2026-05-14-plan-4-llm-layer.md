# Plan 4: LLM 層 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 LLM 層——把輸入（text / code / PDF）經內部 LLM 分析成概念清單、把每個概念 codegen 成 scene spec、raw beat 渲染失敗時跑 repair loop——並接上 Plan 3 的渲染後端，形成「輸入 → 一個 zip」的完整 Phase 1 Web 路徑（不含人工審核關卡）。

**Architecture:** model-agnostic 的 `LLMClient`（OpenAI 相容介面，vLLM / Ollama 都支援）；analyze 與 codegen 各是一次 LLM call，輸出用 Plan 1 的寬鬆解析器解析、用 Plan 1 的驗證器驗證；codegen 解析/驗證失敗時帶錯誤回問一次；`BeatRepairer` 只對 raw beat 做 repair loop（渲染失敗 → traceback 回餵 LLM → 重試上限 N）。整層用腳本化的 `FakeLLMClient` 即可完整測試，CI 不需要真實 LLM。

**Tech Stack:** Python ≥3.12、`openai` SDK（指向任何 OpenAI 相容 endpoint）、`pypdf`（PDF 文字抽取）、Pydantic v2、pytest、Docker（僅端到端測試）。

---

## 背景：Plan 1–3 已完成的部分（`main` 分支，105 測試）

- `manim_skill/spec/` — `SceneSpec`/`Beat`/`CameraDirective`（schema.py）；`parse_spec_text(text) -> dict` + `SpecParseError`（parse.py，從雜訊文字抽出 JSON 物件）；`validate_spec(raw) -> SceneSpec` + `SpecValidationError`（validate.py）。
- `manim_skill/components/` — `base.py` registry：`get(name) -> Component`、`all_names() -> list[str]`；每個 component 有 class 屬性 `name`、`Params`（Pydantic model class）。`__init__.py` 自動探索全部 9 個元件。
- `manim_skill/render/` — `docker_render.py`：`render_spec_to_mp4(spec, workdir) -> Path`、`RenderError`；`backend.py`：`render_batch(specs, workdir, *, max_workers=3, cache=None) -> BatchJob` 與內部的 `_render_beat_job`；`jobs.py`：`JobStatus`/`BeatJob`/`ClipJob`/`BatchJob`；`cache.py`：`BeatCache`；`queue.py`、`stitch.py`、`bundle.py`、`convert.py`。
- 測試以 `tests/<subpkg>/` 組織。`docker` pytest marker 已註冊。

環境：Windows、Docker Desktop、manim 0.20.1、Python 3.13。本機**沒有**真實的內部 LLM；所有 Plan 4 的測試用 `FakeLLMClient`。

## 範圍界定

- **包含：** `LLMClient` 介面 + OpenAI 相容實作 + `FakeLLMClient`、輸入前處理（PDF/text/code）、元件目錄生成、analyze 階段、codegen 階段（含失敗回問一次）、`BeatRepairer` repair loop、`render_batch` 整合 repairer、`run_pipeline` 端到端 orchestrator。
- **不包含：** 人工審核關卡 UI（Phase 2 Web）；模型路由（小模型 analyze / 大模型 codegen——設計上 `LLMClient` 已是 model-agnostic，路由只是「傳不同的 client」，不需額外程式碼）；live eval suite（需要真實公司 LLM 才有意義，屬部署期；Plan 4 的 CI 測試策略已由 `FakeLLMClient` 完整覆蓋）。

## 重要：測試策略

- 整個 LLM 層的測試用 `FakeLLMClient`——它實作與真實 client 相同的 `.complete(system, user) -> str` 介面，可回傳固定回應或依序吐出腳本化回應（多次 call 的流程，如 codegen 回問、repair loop），並記錄每次 call 供斷言。
- 唯一碰 docker 的是最後的端到端測試（Task 9，標 `@pytest.mark.docker`）——用 `FakeLLMClient` 腳本化出真實可渲染的 spec，搭配真實 `render_batch` 驗證 LLM 層產出真的能渲染。
- `OpenAIClient` 的建構不會發網路請求（openai SDK 建構是惰性的），所以「能建構」可在無網路下測試；真正的 LLM 呼叫不在 CI 測試範圍。

## File Structure

```
pyproject.toml                  修改 — 加依賴 openai、pypdf
manim_skill/llm/
  __init__.py                   新增（空）
  client.py                     新增 — LLMClient 介面 / OpenAIClient / FakeLLMClient
  input_prep.py                 新增 — prepare_input（PDF/text/code → 純文字）
  catalog.py                    新增 — build_component_catalog（元件 → LLM prompt 文字）
  analyze.py                    新增 — ConceptCandidate / analyze（階段 1）
  codegen.py                    新增 — generate_spec（階段 2，含回問）
  repair.py                     新增 — BeatRepairer / RepairResult（raw beat repair loop）
  pipeline.py                   新增 — generate_specs / run_pipeline（端到端 orchestrator）
manim_skill/render/backend.py   修改 — render_batch / _render_beat_job 接上 repairer
tests/llm/
  __init__.py                   新增（空）
  test_client.py / test_input_prep.py / test_catalog.py / test_analyze.py
  test_codegen.py / test_repair.py / test_pipeline.py
  test_pipeline_e2e.py          新增 — docker 端到端
tests/render/test_backend.py    修改 — 加 repairer 整合測試
```

---

## Task 1: LLM 模組骨架 + 依賴 + LLMClient

建立 `llm/` 套件、加 `openai`/`pypdf` 依賴、實作 `LLMClient` 介面與 `OpenAIClient`/`FakeLLMClient`。本任務 owns pyproject 的依賴變更（後續任務不再碰 pyproject）。

**Files:**
- Modify: `pyproject.toml`
- Create: `manim_skill/llm/__init__.py`（空）
- Create: `tests/llm/__init__.py`（空）
- Create: `manim_skill/llm/client.py`
- Create: `tests/llm/test_client.py`

- [ ] **Step 1: 加依賴到 `pyproject.toml`** — 把 `[project]` 的 `dependencies` 區塊改為：

```toml
dependencies = [
    "manim>=0.19,<0.21",
    "pydantic>=2.6",
    "json5>=0.9",
    "openai>=1.0",
    "pypdf>=4.0",
]
```

其餘 `pyproject.toml` 內容不變。

- [ ] **Step 2: 重新安裝套件** — Run: `pip install -e ".[dev]"`
  Expected: 成功，安裝 `openai` 與 `pypdf`。

- [ ] **Step 3: 建立空套件檔** — 建立空檔 `manim_skill/llm/__init__.py` 與 `tests/llm/__init__.py`（內容皆為空）。

- [ ] **Step 4: 寫失敗測試** — `tests/llm/test_client.py`:

```python
import pytest

from manim_skill.llm.client import FakeLLMClient, OpenAIClient


def test_fake_client_fixed_response():
    client = FakeLLMClient(response="hello")
    assert client.complete("sys", "usr") == "hello"
    assert client.complete("sys2", "usr2") == "hello"
    assert client.calls == [("sys", "usr"), ("sys2", "usr2")]


def test_fake_client_scripted_responses_in_order():
    client = FakeLLMClient(responses=["first", "second"])
    assert client.complete("s", "u") == "first"
    assert client.complete("s", "u") == "second"


def test_fake_client_exhausted_scripted_raises():
    client = FakeLLMClient(responses=["only"])
    client.complete("s", "u")
    with pytest.raises(AssertionError):
        client.complete("s", "u")


def test_openai_client_constructs_without_network_call():
    # Constructing must not hit the network — it only builds the SDK client.
    client = OpenAIClient(base_url="http://localhost:11434/v1", model="qwen3.5-35b")
    assert client.model == "qwen3.5-35b"
```

- [ ] **Step 5: 執行測試確認失敗** — `pytest tests/llm/test_client.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 6: 實作** — `manim_skill/llm/client.py`:

```python
from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    """Structural interface for an LLM text-completion client.

    The internal company LLMs are served via vLLM or Ollama, both of
    which expose an OpenAI-compatible API. Everything in this package
    depends only on this `.complete` interface, never on a specific
    model — that is what "model-agnostic" means here. Model routing
    (small model for analyze, large for codegen) is just "pass a
    different client", needing no extra code.
    """

    def complete(self, system: str, user: str) -> str:
        ...


class OpenAIClient:
    """LLMClient backed by any OpenAI-compatible endpoint (vLLM, Ollama)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "not-needed",
        temperature: float = 0.2,
        timeout: float = 120.0,
    ) -> None:
        from openai import OpenAI

        self.model = model
        self.temperature = temperature
        self._client = OpenAI(
            base_url=base_url, api_key=api_key, timeout=timeout
        )

    def complete(self, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""


class FakeLLMClient:
    """Deterministic LLMClient for tests.

    Either returns a fixed `response` for every call, or pops scripted
    `responses` in order (for multi-call flows like the codegen re-ask
    or the repair loop). Records every (system, user) call for asserts.
    """

    def __init__(
        self,
        response: str | None = None,
        responses: list[str] | None = None,
    ) -> None:
        if responses is not None:
            self._responses: list[str] | None = list(responses)
            self._fixed: str | None = None
        else:
            self._responses = None
            self._fixed = response if response is not None else ""
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if self._responses is not None:
            if not self._responses:
                raise AssertionError(
                    "FakeLLMClient: no scripted responses left"
                )
            return self._responses.pop(0)
        assert self._fixed is not None
        return self._fixed
```

- [ ] **Step 7: 執行測試確認通過** — `pytest tests/llm/test_client.py -v` → expect PASS (4 passed).

- [ ] **Step 8: 執行完整非 docker 套件確認無回歸** — `pytest -m "not docker" -q` → expect 全部 PASS.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml manim_skill/llm/__init__.py manim_skill/llm/client.py tests/llm/__init__.py tests/llm/test_client.py
git commit -m "feat: LLM client interface (OpenAIClient + FakeLLMClient)"
```

---

## Task 2: 輸入前處理

把原始輸入（text / code / PDF）正規化成純文字給 analyze 階段。

**Files:**
- Create: `manim_skill/llm/input_prep.py`
- Create: `tests/llm/test_input_prep.py`

- [ ] **Step 1: 寫失敗測試** — `tests/llm/test_input_prep.py`:

```python
from manim_skill.llm.input_prep import prepare_input


def test_text_passthrough():
    assert prepare_input("hello world", "text") == "hello world"


def test_code_passthrough():
    code = "def f():\n    return 1"
    assert prepare_input(code, "code") == code


def test_bytes_text_decoded():
    assert prepare_input(b"hi there", "text") == "hi there"


def test_pdf_extraction(monkeypatch):
    import pypdf

    class _FakePage:
        def __init__(self, text):
            self._text = text

        def extract_text(self):
            return self._text

    class _FakeReader:
        def __init__(self, _src):
            self.pages = [_FakePage("page one"), _FakePage("page two")]

    monkeypatch.setattr(pypdf, "PdfReader", _FakeReader)
    result = prepare_input(b"%PDF-fake-bytes", "pdf")
    assert "page one" in result
    assert "page two" in result
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/llm/test_input_prep.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 實作** — `manim_skill/llm/input_prep.py`:

```python
from __future__ import annotations

import io
from typing import Literal

InputKind = Literal["text", "code", "pdf"]


def prepare_input(content, kind: InputKind) -> str:
    """Normalize raw input into plain text for the analyze stage.

    - "text" / "code": returned as-is (decoded from bytes if needed).
    - "pdf": text extracted from every page via pypdf; `content` may be
      raw PDF bytes or a path.
    """
    if kind == "pdf":
        import pypdf

        if isinstance(content, (bytes, bytearray)):
            reader = pypdf.PdfReader(io.BytesIO(content))
        else:
            reader = pypdf.PdfReader(content)
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages).strip()

    if isinstance(content, (bytes, bytearray)):
        return content.decode("utf-8", errors="replace")
    return str(content)
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/llm/test_input_prep.py -v` → expect PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/llm/input_prep.py tests/llm/test_input_prep.py
git commit -m "feat: input preprocessing (text/code/pdf -> plain text)"
```

---

## Task 3: 元件目錄生成

把已註冊的元件渲染成 LLM prompt 用的文字目錄，每個元件附其 Pydantic params JSON schema（單一事實來源，不會 drift）。

**Files:**
- Create: `manim_skill/llm/catalog.py`
- Create: `tests/llm/test_catalog.py`

- [ ] **Step 1: 寫失敗測試** — `tests/llm/test_catalog.py`:

```python
from manim_skill.llm.catalog import build_component_catalog


def test_catalog_includes_all_registered_components():
    catalog = build_component_catalog()
    for name in [
        "TextBeat", "CodeWalkthrough", "NeuralNetDiagram", "AttentionFlow",
        "MatrixOp", "PlotEvolution", "PipelineDiagram", "GeometryAnim",
        "FormulaBreakdown",
    ]:
        assert name in catalog


def test_catalog_includes_params_schema():
    catalog = build_component_catalog()
    # TextBeat's params model has a "text" field; the JSON schema has
    # a "properties" key.
    assert "text" in catalog
    assert "properties" in catalog


def test_catalog_is_non_empty_string():
    catalog = build_component_catalog()
    assert isinstance(catalog, str)
    assert len(catalog) > 0
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/llm/test_catalog.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 實作** — `manim_skill/llm/catalog.py`:

```python
from __future__ import annotations

import json

from manim_skill.components import base as registry


def build_component_catalog() -> str:
    """Render the registered components as a text catalog for an LLM prompt.

    Each component's params schema comes straight from its Pydantic
    `Params` model — the single source of truth — so the catalog never
    drifts from the actual code.
    """
    blocks: list[str] = []
    for name in registry.all_names():
        component = registry.get(name)
        schema = component.Params.model_json_schema()
        blocks.append(
            f"### {name}\n"
            + json.dumps(schema, ensure_ascii=False, indent=2)
        )
    return "\n\n".join(blocks)
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/llm/test_catalog.py -v` → expect PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/llm/catalog.py tests/llm/test_catalog.py
git commit -m "feat: component catalog generation for LLM prompts"
```

---

## Task 4: Analyze 階段

階段 1：一次 LLM call，從輸入文字抽出「適合做動畫的概念」清單。

**Files:**
- Create: `manim_skill/llm/analyze.py`
- Create: `tests/llm/test_analyze.py`

- [ ] **Step 1: 寫失敗測試** — `tests/llm/test_analyze.py`:

```python
import pytest

from manim_skill.llm.analyze import AnalyzeError, ConceptCandidate, analyze
from manim_skill.llm.client import FakeLLMClient


def test_analyze_parses_clean_json():
    response = (
        '{"concepts": [{"concept": "Attention", '
        '"why_suitable": "visual flow", '
        '"storyboard": "Show tokens. Draw weights."}]}'
    )
    client = FakeLLMClient(response=response)
    result = analyze(client, "some paper text")
    assert len(result) == 1
    assert isinstance(result[0], ConceptCandidate)
    assert result[0].concept == "Attention"
    assert result[0].storyboard == "Show tokens. Draw weights."


def test_analyze_tolerates_prose_wrapped_json():
    response = (
        "Sure! Here are the concepts:\n```json\n"
        '{"concepts": [{"concept": "X", "why_suitable": "y", '
        '"storyboard": "z"}]}\n```\nHope that helps."
    )
    client = FakeLLMClient(response=response)
    result = analyze(client, "text")
    assert result[0].concept == "X"


def test_analyze_includes_guide_prompt_in_user_message():
    response = (
        '{"concepts": [{"concept": "X", "why_suitable": "y", '
        '"storyboard": "z"}]}'
    )
    client = FakeLLMClient(response=response)
    analyze(client, "paper text", guide_prompt="focus on the loss function")
    _system, user = client.calls[0]
    assert "focus on the loss function" in user
    assert "paper text" in user


def test_analyze_raises_on_unparseable_response():
    client = FakeLLMClient(response="no json here at all")
    with pytest.raises(AnalyzeError):
        analyze(client, "text")


def test_analyze_raises_on_missing_concepts_list():
    client = FakeLLMClient(response='{"something_else": 1}')
    with pytest.raises(AnalyzeError):
        analyze(client, "text")
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/llm/test_analyze.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 實作** — `manim_skill/llm/analyze.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, ValidationError

from manim_skill.llm.client import LLMClient
from manim_skill.spec.parse import SpecParseError, parse_spec_text


class ConceptCandidate(BaseModel):
    concept: str
    why_suitable: str
    storyboard: str


class AnalyzeError(RuntimeError):
    """Raised when the analyze stage cannot produce concept candidates."""


_ANALYZE_SYSTEM = """\
You analyze source material (a paper, an article, or a code snippet) and \
pick the parts that would make good short manim animations for slides or a \
README. Return ONLY a JSON object of the form:
{"concepts": [{"concept": "...", "why_suitable": "...", "storyboard": "..."}]}
- concept: a short title for the idea to animate.
- why_suitable: one sentence on why it animates well.
- storyboard: a beat-by-beat prose description of the animation, one beat \
per sentence — this is the brief the codegen stage turns into a scene spec.
Pick at most 5 concepts. Output nothing but the JSON object."""


def analyze(
    client: LLMClient,
    prepared_input: str,
    guide_prompt: str | None = None,
) -> list[ConceptCandidate]:
    """Stage 1: extract animatable concept candidates from input text.

    One LLM call. The response is leniently parsed (mid-size models
    wrap JSON in prose/fences); each concept is validated into a
    ConceptCandidate.
    """
    user = prepared_input
    if guide_prompt:
        user = (
            f"Guidance from the user: {guide_prompt}\n\n"
            f"---\n\n{prepared_input}"
        )

    raw = client.complete(_ANALYZE_SYSTEM, user)
    try:
        data = parse_spec_text(raw)
    except SpecParseError as exc:
        raise AnalyzeError(
            f"could not parse analyze response: {exc}"
        ) from exc

    concepts_raw = data.get("concepts")
    if not isinstance(concepts_raw, list) or not concepts_raw:
        raise AnalyzeError("analyze response had no non-empty 'concepts' list")

    candidates: list[ConceptCandidate] = []
    for item in concepts_raw:
        try:
            candidates.append(ConceptCandidate.model_validate(item))
        except ValidationError as exc:
            raise AnalyzeError(
                f"invalid concept candidate {item!r}: {exc}"
            ) from exc
    return candidates
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/llm/test_analyze.py -v` → expect PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/llm/analyze.py tests/llm/test_analyze.py
git commit -m "feat: analyze stage (input text -> concept candidates)"
```

---

## Task 5: Codegen 階段

階段 2：一個概念 → 一份驗證過的 `SceneSpec`。一次 LLM call；解析或驗證失敗時帶錯誤回問一次；再失敗則 `CodegenError`。

**Files:**
- Create: `manim_skill/llm/codegen.py`
- Create: `tests/llm/test_codegen.py`

- [ ] **Step 1: 寫失敗測試** — `tests/llm/test_codegen.py`:

```python
import pytest

from manim_skill.llm.analyze import ConceptCandidate
from manim_skill.llm.client import FakeLLMClient
from manim_skill.llm.codegen import CodegenError, generate_spec
from manim_skill.spec.schema import SceneSpec

_CONCEPT = ConceptCandidate(
    concept="Demo", why_suitable="y", storyboard="Show a title."
)
_VALID_SPEC = (
    '{"title": "Demo", "beats": [{"component": "TextBeat", '
    '"params": {"text": "Hello"}}]}'
)


def test_generate_spec_valid_first_try():
    client = FakeLLMClient(response=_VALID_SPEC)
    spec = generate_spec(client, _CONCEPT, catalog="(catalog)")
    assert isinstance(spec, SceneSpec)
    assert spec.title == "Demo"
    assert len(client.calls) == 1


def test_generate_spec_reasks_after_unparseable_response():
    client = FakeLLMClient(responses=["not json at all", _VALID_SPEC])
    spec = generate_spec(client, _CONCEPT, catalog="(catalog)")
    assert isinstance(spec, SceneSpec)
    assert len(client.calls) == 2
    # the re-ask prompt mentions the rejection
    assert "rejected" in client.calls[1][1]


def test_generate_spec_reasks_on_invalid_component():
    bad = (
        '{"title": "X", "beats": [{"component": "NopeComponent", '
        '"params": {}}]}'
    )
    client = FakeLLMClient(responses=[bad, _VALID_SPEC])
    spec = generate_spec(client, _CONCEPT, catalog="(catalog)")
    assert isinstance(spec, SceneSpec)
    assert len(client.calls) == 2


def test_generate_spec_raises_after_two_failures():
    client = FakeLLMClient(responses=["garbage one", "garbage two"])
    with pytest.raises(CodegenError):
        generate_spec(client, _CONCEPT, catalog="(catalog)")


def test_generate_spec_passes_catalog_into_system_prompt():
    client = FakeLLMClient(response=_VALID_SPEC)
    generate_spec(client, _CONCEPT, catalog="UNIQUE_CATALOG_MARKER")
    system, _user = client.calls[0]
    assert "UNIQUE_CATALOG_MARKER" in system
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/llm/test_codegen.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 實作** — `manim_skill/llm/codegen.py`:

```python
from __future__ import annotations

from manim_skill.llm.analyze import ConceptCandidate
from manim_skill.llm.client import LLMClient
from manim_skill.spec.parse import SpecParseError, parse_spec_text
from manim_skill.spec.schema import SceneSpec
from manim_skill.spec.validate import SpecValidationError, validate_spec


class CodegenError(RuntimeError):
    """Raised when the codegen stage cannot produce a valid SceneSpec."""


# __CATALOG__ is a literal marker replaced via str.replace (not str.format)
# so the literal { } in the JSON examples below need no escaping.
_CODEGEN_SYSTEM = """\
You turn a concept storyboard into a manim "scene spec" — a JSON object.
Schema:
{"title": "...", "aspect_ratio": "16:9",
 "beats": [{"component": "<name>|raw", "params": {...}, "code": "<for raw>",
            "caption": "...", "duration": 4.0}]}
Prefer the components in the catalog below; each beat's "params" must match
that component's params schema. If no component fits a beat, use
"component": "raw" with a "code" field containing manim Python (the scene is
`self`). Output ONLY the JSON object, nothing else.

COMPONENT CATALOG:
__CATALOG__"""


def _build_user_prompt(concept: ConceptCandidate) -> str:
    return (
        f"Concept: {concept.concept}\n"
        f"Why it animates well: {concept.why_suitable}\n"
        f"Storyboard:\n{concept.storyboard}\n\n"
        "Produce the scene spec JSON for this concept."
    )


def generate_spec(
    client: LLMClient,
    concept: ConceptCandidate,
    catalog: str,
) -> SceneSpec:
    """Stage 2: turn one concept into a validated SceneSpec.

    One LLM call; on a parse or validation failure, re-ask once with
    the error fed back. If the second attempt still fails, raise
    CodegenError.
    """
    system = _CODEGEN_SYSTEM.replace("__CATALOG__", catalog)
    base_user = _build_user_prompt(concept)

    last_error = ""
    for attempt in range(2):
        if attempt == 0:
            user = base_user
        else:
            user = (
                f"{base_user}\n\nYour previous response was rejected: "
                f"{last_error}\nReturn a corrected scene spec JSON, "
                "nothing else."
            )
        raw = client.complete(system, user)
        try:
            return validate_spec(parse_spec_text(raw))
        except (SpecParseError, SpecValidationError) as exc:
            last_error = str(exc)

    raise CodegenError(
        f"codegen failed for concept {concept.concept!r} after 2 "
        f"attempts: {last_error}"
    )
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/llm/test_codegen.py -v` → expect PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/llm/codegen.py tests/llm/test_codegen.py
git commit -m "feat: codegen stage (concept -> validated SceneSpec, with re-ask)"
```

---

## Task 6: Repair Loop

`BeatRepairer`：渲染一個 raw beat，失敗時把 traceback 回餵 LLM 取得修正後的 code，重試上限 `max_attempts`（預設 3）。只對 raw beat 適用——元件 beat 是確定性的，失敗代表 builder bug，不是 LLM 能修的。

**Files:**
- Create: `manim_skill/llm/repair.py`
- Create: `tests/llm/test_repair.py`

- [ ] **Step 1: 寫失敗測試** — `tests/llm/test_repair.py`:

```python
from pathlib import Path

import pytest

from manim_skill.llm import repair as repair_mod
from manim_skill.llm.client import FakeLLMClient
from manim_skill.llm.repair import BeatRepairer, RepairResult
from manim_skill.render.docker_render import RenderError
from manim_skill.spec.schema import Beat


def _fake_mp4(workdir):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    mp4 = workdir / "out.mp4"
    mp4.write_bytes(b"\x00mp4")
    return mp4


def test_repair_succeeds_on_first_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(
        repair_mod, "render_spec_to_mp4",
        lambda spec, workdir: _fake_mp4(workdir),
    )
    client = FakeLLMClient(response="should not be called")
    repairer = BeatRepairer(client)
    beat = Beat(component="raw", code="self.wait(1)")
    result = repairer.render_with_repair(beat, tmp_path)
    assert isinstance(result, RepairResult)
    assert result.attempts == 1
    assert result.mp4_path.exists()
    assert client.calls == []  # no repair needed -> no LLM call


def test_repair_fixes_code_then_succeeds(tmp_path, monkeypatch):
    calls = {"n": 0}

    def flaky(spec, workdir):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RenderError("NameError: bad")
        return _fake_mp4(workdir)

    monkeypatch.setattr(repair_mod, "render_spec_to_mp4", flaky)
    client = FakeLLMClient(response="self.wait(2)")
    repairer = BeatRepairer(client)
    beat = Beat(component="raw", code="brokn code")
    result = repairer.render_with_repair(beat, tmp_path)
    assert result.attempts == 2
    assert result.final_beat.code == "self.wait(2)"
    assert len(client.calls) == 1


def test_repair_gives_up_after_max_attempts(tmp_path, monkeypatch):
    def always_fails(spec, workdir):
        raise RenderError("always broken")

    monkeypatch.setattr(repair_mod, "render_spec_to_mp4", always_fails)
    client = FakeLLMClient(response="still broken")
    repairer = BeatRepairer(client, max_attempts=3)
    beat = Beat(component="raw", code="broken")
    with pytest.raises(RenderError):
        repairer.render_with_repair(beat, tmp_path)
    # 3 render attempts -> 2 repair calls
    assert len(client.calls) == 2


def test_repair_does_not_retry_non_raw_beat(tmp_path, monkeypatch):
    def always_fails(spec, workdir):
        raise RenderError("component bug")

    monkeypatch.setattr(repair_mod, "render_spec_to_mp4", always_fails)
    client = FakeLLMClient(response="x")
    repairer = BeatRepairer(client)
    beat = Beat(component="TextBeat", params={"text": "hi"})
    with pytest.raises(RenderError):
        repairer.render_with_repair(beat, tmp_path)
    assert client.calls == []  # non-raw beat: no repair attempted
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/llm/test_repair.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 實作** — `manim_skill/llm/repair.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from manim_skill.llm.client import LLMClient
from manim_skill.render.docker_render import RenderError, render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec

DEFAULT_MAX_ATTEMPTS = 3

_REPAIR_SYSTEM = """\
You fix broken manim Python code. You are given a code snippet that runs
inside a manim scene's construct() (the scene is `self`) and the error it
produced. Return ONLY the corrected code snippet — no explanation, no fences."""


@dataclass
class RepairResult:
    mp4_path: Path
    final_beat: Beat
    attempts: int


class BeatRepairer:
    """Renders a raw beat, repairing its code via the LLM on failure.

    The repair loop only applies to `raw` beats — component beats are
    deterministic, so a failure there is a builder bug the LLM can't
    fix. On a RenderError the traceback is fed back to the LLM, which
    returns corrected code; this retries up to max_attempts.
    """

    def __init__(
        self, client: LLMClient, max_attempts: int = DEFAULT_MAX_ATTEMPTS
    ) -> None:
        self.client = client
        self.max_attempts = max(1, max_attempts)

    def render_with_repair(
        self,
        beat: Beat,
        work_dir,
        *,
        title: str = "clip",
        aspect_ratio: str = "16:9",
    ) -> RepairResult:
        """Render `beat` as a 1-beat spec, repairing raw code on failure.

        Returns a RepairResult on success. Raises RenderError if a
        component beat fails (no repair attempted) or a raw beat still
        fails after max_attempts.
        """
        work_dir = Path(work_dir)
        current = beat
        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            spec = SceneSpec(
                title=title, aspect_ratio=aspect_ratio, beats=[current]
            )
            try:
                mp4 = render_spec_to_mp4(
                    spec, work_dir / f"attempt_{attempt}"
                )
                return RepairResult(
                    mp4_path=mp4, final_beat=current, attempts=attempt
                )
            except RenderError as exc:
                last_error = str(exc)
                if (
                    current.component != "raw"
                    or attempt == self.max_attempts
                ):
                    raise RenderError(
                        f"repair gave up after {attempt} attempt(s): "
                        f"{last_error}"
                    ) from exc
                fixed = self.client.complete(
                    _REPAIR_SYSTEM,
                    f"Code:\n{current.code}\n\nError:\n{last_error}",
                )
                current = current.model_copy(
                    update={"code": fixed.strip()}
                )

        # Defensive: the loop always returns or raises above.
        raise RenderError(f"repair gave up: {last_error}")
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/llm/test_repair.py -v` → expect PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/llm/repair.py tests/llm/test_repair.py
git commit -m "feat: BeatRepairer repair loop for raw beats"
```

---

## Task 7: 渲染後端接上 Repairer

修改 Plan 3 的 `render/backend.py`：`render_batch` 與 `_render_beat_job` 加一個可選的 `repairer` 參數；raw beat 渲染時若有 repairer 就走 repair loop。

**Files:**
- Modify: `manim_skill/render/backend.py`
- Modify: `tests/render/test_backend.py`

- [ ] **Step 1: 在 `tests/render/test_backend.py` 末尾新增 repairer 整合測試**

```python
def test_render_batch_repairer_recovers_failed_raw_beat(tmp_path, monkeypatch):
    # render_spec_to_mp4 always fails; the repairer "fixes" the beat and
    # produces an mp4, so the clip still completes.
    monkeypatch.setattr(backend_mod, "render_spec_to_mp4", _fake_render_raises)
    monkeypatch.setattr(backend_mod, "stitch_mp4s", _fake_stitch_mp4s)
    monkeypatch.setattr(backend_mod, "mp4_to_gif", _fake_mp4_to_gif)

    class _FakeRepairer:
        def render_with_repair(self, beat, work_dir, *, title, aspect_ratio):
            from manim_skill.llm.repair import RepairResult

            work_dir = Path(work_dir)
            work_dir.mkdir(parents=True, exist_ok=True)
            mp4 = work_dir / "repaired.mp4"
            mp4.write_bytes(b"\x00repaired")
            return RepairResult(mp4_path=mp4, final_beat=beat, attempts=2)

    specs = [
        SceneSpec(title="C", beats=[Beat(component="raw", code="broken")])
    ]
    batch = render_batch(specs, tmp_path, repairer=_FakeRepairer())
    assert batch.clip_jobs[0].status == JobStatus.DONE
    assert batch.clip_jobs[0].beat_jobs[0].status == JobStatus.DONE
```

(`Path`, `backend_mod`, `_fake_render_raises`, `_fake_stitch_mp4s`, `_fake_mp4_to_gif`, `render_batch`, `JobStatus`, `SceneSpec`, `Beat` are all already imported/defined at the top of `tests/render/test_backend.py` from Plan 3 — do not re-import them.)

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/render/test_backend.py::test_render_batch_repairer_recovers_failed_raw_beat -v`
  Expected: FAIL — `render_batch` does not yet accept a `repairer` keyword argument (`TypeError`).

- [ ] **Step 3: 修改 `manim_skill/render/backend.py`**

3a. 在檔案頂端的 import 區，加入 `TYPE_CHECKING` 匯入（避免 `backend` ↔ `llm.repair` 的執行期循環匯入；`backend` 只 duck-typed 呼叫 `.render_with_repair`）。把現有的
```python
from __future__ import annotations

import functools
import shutil
from pathlib import Path
```
改為：
```python
from __future__ import annotations

import functools
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from manim_skill.llm.repair import BeatRepairer
```

3b. 把 `_render_beat_job` 整個函式取代為（加 `repairer` 參數、raw beat 走 repair、以「原始 beat」為快取鍵）：

```python
def _render_beat_job(
    indexed_beat: tuple[int, BeatJob],
    *,
    clip: ClipJob,
    clip_dir: Path,
    cache: BeatCache | None,
    repairer: "BeatRepairer | None",
) -> BeatJob:
    """Render one beat as a standalone 1-beat spec.

    On success the beat mp4 is copied into `clip_dir` as `beat_NN.mp4`
    (stitch requires all inputs in one directory). A raw beat is
    rendered through `repairer` when one is supplied — the repair loop
    may rewrite the beat's code, which is recorded back on the BeatJob.
    A RenderError is caught and recorded — a failed beat must not stop
    the rest of the clip or batch. The cache is keyed on the ORIGINAL
    beat, so a re-run skips both render and repair.
    """
    index, beat_job = indexed_beat
    beat_job.status = JobStatus.RENDERING
    dest = clip_dir / f"beat_{index:02d}.mp4"
    original_beat = beat_job.beat

    try:
        if cache is not None:
            cached = cache.get(original_beat)
            if cached is not None:
                shutil.copy2(cached, dest)
                beat_job.mp4_path = dest
                beat_job.status = JobStatus.DONE
                return beat_job

        beat_work = clip_dir / f"beat_{index:02d}_work"
        if repairer is not None and original_beat.component == "raw":
            result = repairer.render_with_repair(
                original_beat,
                beat_work,
                title=clip.spec.title,
                aspect_ratio=clip.spec.aspect_ratio,
            )
            rendered = result.mp4_path
            beat_job.beat = result.final_beat
        else:
            one_beat_spec = SceneSpec(
                title=clip.spec.title,
                aspect_ratio=clip.spec.aspect_ratio,
                beats=[original_beat],
            )
            rendered = render_spec_to_mp4(one_beat_spec, beat_work)

        shutil.copy2(rendered, dest)
        beat_job.mp4_path = dest
        beat_job.status = JobStatus.DONE
        if cache is not None:
            cache.put(original_beat, dest)
    except RenderError as exc:
        beat_job.status = JobStatus.FAILED
        beat_job.error = str(exc)

    return beat_job
```

3c. 在 `render_batch` 的簽名加入 `repairer` 參數。把簽名
```python
def render_batch(
    specs: list[SceneSpec],
    workdir,
    *,
    max_workers: int = 3,
    cache: BeatCache | None = None,
) -> BatchJob:
```
改為：
```python
def render_batch(
    specs: list[SceneSpec],
    workdir,
    *,
    max_workers: int = 3,
    cache: BeatCache | None = None,
    repairer: "BeatRepairer | None" = None,
) -> BatchJob:
```

3d. 在 `render_batch` 內，把建立 `worker` 的那行
```python
        worker = functools.partial(
            _render_beat_job, clip=clip, clip_dir=clip_dir, cache=cache
        )
```
改為：
```python
        worker = functools.partial(
            _render_beat_job,
            clip=clip,
            clip_dir=clip_dir,
            cache=cache,
            repairer=repairer,
        )
```

`render_batch` 的其餘部分（docstring、clip/beat job 建立、stitch/gif、bundle、status 收尾）保持不變。

- [ ] **Step 4: 執行新測試確認通過** — `pytest tests/render/test_backend.py::test_render_batch_repairer_recovers_failed_raw_beat -v` → expect PASS。

- [ ] **Step 5: 執行完整非 docker 套件確認無回歸** — `pytest -m "not docker" -q` → expect 全部 PASS（Plan 3 既有的 backend 測試——`repairer` 預設 `None`，行為不變）。

- [ ] **Step 6: Commit**

```bash
git add manim_skill/render/backend.py tests/render/test_backend.py
git commit -m "feat: wire BeatRepairer into render_batch for raw beats"
```

---

## Task 8: Pipeline Orchestrator

把 LLM 層接成端到端：輸入 → analyze → 每個概念 codegen → `render_batch`（帶 repairer）→ zip。

**Files:**
- Create: `manim_skill/llm/pipeline.py`
- Create: `tests/llm/test_pipeline.py`

- [ ] **Step 1: 寫失敗測試** — `tests/llm/test_pipeline.py`:

```python
from manim_skill.llm import pipeline as pipeline_mod
from manim_skill.llm.client import FakeLLMClient
from manim_skill.llm.pipeline import generate_specs, run_pipeline
from manim_skill.spec.schema import SceneSpec

_ANALYZE_RESP = (
    '{"concepts": [{"concept": "C1", "why_suitable": "w", '
    '"storyboard": "s"}]}'
)
_SPEC_RESP = (
    '{"title": "C1", "beats": [{"component": "TextBeat", '
    '"params": {"text": "Hi"}}]}'
)


def test_generate_specs_runs_analyze_then_codegen():
    client = FakeLLMClient(responses=[_ANALYZE_RESP, _SPEC_RESP])
    specs = generate_specs(client, "paper text", "text")
    assert len(specs) == 1
    assert isinstance(specs[0], SceneSpec)
    assert specs[0].title == "C1"


def test_generate_specs_skips_concept_with_failed_codegen():
    # analyze finds 2 concepts; the first concept's codegen fails twice
    # (skipped), the second concept's codegen succeeds.
    analyze_resp = (
        '{"concepts": ['
        '{"concept": "Bad", "why_suitable": "w", "storyboard": "s"},'
        '{"concept": "Good", "why_suitable": "w", "storyboard": "s"}]}'
    )
    client = FakeLLMClient(
        responses=[analyze_resp, "garbage", "garbage again", _SPEC_RESP]
    )
    specs = generate_specs(client, "text", "text")
    assert len(specs) == 1
    assert specs[0].title == "C1"


def test_run_pipeline_passes_specs_and_repairer_to_render_batch(
    tmp_path, monkeypatch
):
    captured = {}

    def fake_render_batch(specs, workdir, *, max_workers, cache, repairer):
        from manim_skill.render.jobs import BatchJob, JobStatus

        captured["specs"] = specs
        captured["repairer"] = repairer
        return BatchJob(clip_jobs=[], status=JobStatus.DONE)

    monkeypatch.setattr(pipeline_mod, "render_batch", fake_render_batch)
    client = FakeLLMClient(responses=[_ANALYZE_RESP, _SPEC_RESP])
    run_pipeline(client, "text", "text", tmp_path, repair=True)
    assert len(captured["specs"]) == 1
    assert captured["repairer"] is not None  # repair=True -> a BeatRepairer


def test_run_pipeline_repair_false_passes_no_repairer(tmp_path, monkeypatch):
    def fake_render_batch(specs, workdir, *, max_workers, cache, repairer):
        from manim_skill.render.jobs import BatchJob, JobStatus

        assert repairer is None
        return BatchJob(clip_jobs=[], status=JobStatus.DONE)

    monkeypatch.setattr(pipeline_mod, "render_batch", fake_render_batch)
    client = FakeLLMClient(responses=[_ANALYZE_RESP, _SPEC_RESP])
    run_pipeline(client, "text", "text", tmp_path, repair=False)
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/llm/test_pipeline.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 實作** — `manim_skill/llm/pipeline.py`:

```python
from __future__ import annotations

from manim_skill.llm.analyze import analyze
from manim_skill.llm.catalog import build_component_catalog
from manim_skill.llm.client import LLMClient
from manim_skill.llm.codegen import CodegenError, generate_spec
from manim_skill.llm.input_prep import InputKind, prepare_input
from manim_skill.llm.repair import BeatRepairer
from manim_skill.render.backend import render_batch
from manim_skill.render.cache import BeatCache
from manim_skill.render.jobs import BatchJob
from manim_skill.spec.schema import SceneSpec


def generate_specs(
    client: LLMClient,
    content,
    kind: InputKind,
    *,
    guide_prompt: str | None = None,
) -> list[SceneSpec]:
    """Run the LLM half of the pipeline: input -> analyze -> codegen.

    Returns one SceneSpec per concept the analyze stage found. A
    concept whose codegen fails (CodegenError) is skipped so one bad
    concept does not sink the rest.
    """
    prepared = prepare_input(content, kind)
    concepts = analyze(client, prepared, guide_prompt=guide_prompt)
    catalog = build_component_catalog()
    specs: list[SceneSpec] = []
    for concept in concepts:
        try:
            specs.append(generate_spec(client, concept, catalog))
        except CodegenError:
            continue
    return specs


def run_pipeline(
    client: LLMClient,
    content,
    kind: InputKind,
    workdir,
    *,
    guide_prompt: str | None = None,
    max_workers: int = 3,
    cache: BeatCache | None = None,
    repair: bool = True,
) -> BatchJob:
    """Full Phase-1 web-path pipeline (minus the human checkpoint):
    input -> analyze -> codegen -> render_batch -> zip bundle.
    """
    specs = generate_specs(
        client, content, kind, guide_prompt=guide_prompt
    )
    repairer = BeatRepairer(client) if repair else None
    return render_batch(
        specs,
        workdir,
        max_workers=max_workers,
        cache=cache,
        repairer=repairer,
    )
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/llm/test_pipeline.py -v` → expect PASS (4 passed).

- [ ] **Step 5: 執行完整非 docker 套件確認無回歸** — `pytest -m "not docker" -q` → expect 全部 PASS.

- [ ] **Step 6: Commit**

```bash
git add manim_skill/llm/pipeline.py tests/llm/test_pipeline.py
git commit -m "feat: LLM pipeline orchestrator (input -> analyze -> codegen -> render)"
```

---

## Task 9: 端到端 Docker 整合測試

用 `FakeLLMClient` 腳本化出真實可渲染的 spec，搭配真實 `render_batch`，驗證 LLM 層的產出真的能渲染成 zip——包含 repair loop 修好真實壞掉的 raw beat 的路徑。

**Files:**
- Create: `tests/llm/test_pipeline_e2e.py`

- [ ] **Step 1: 寫測試** — `tests/llm/test_pipeline_e2e.py`:

```python
import json
import zipfile

import pytest

from manim_skill.llm.client import FakeLLMClient
from manim_skill.llm.pipeline import run_pipeline
from manim_skill.render.jobs import JobStatus

_ANALYZE = (
    '{"concepts": [{"concept": "Greeting", "why_suitable": "simple", '
    '"storyboard": "Show a title card."}]}'
)
_SPEC = (
    '{"title": "Greeting", "beats": ['
    '{"component": "TextBeat", "params": {"text": "Hello"}, '
    '"duration": 1.0}]}'
)


@pytest.mark.docker
def test_run_pipeline_end_to_end_produces_zip(tmp_path):
    client = FakeLLMClient(responses=[_ANALYZE, _SPEC])
    batch = run_pipeline(
        client, "some source text", "text", tmp_path, repair=False
    )
    assert batch.status == JobStatus.DONE
    assert batch.zip_path is not None and batch.zip_path.exists()
    with zipfile.ZipFile(batch.zip_path) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert len(manifest["concepts"]) == 1
    assert manifest["concepts"][0]["status"] == "done"


@pytest.mark.docker
def test_run_pipeline_repair_loop_recovers_broken_raw_beat(tmp_path):
    # codegen produces a spec with a BROKEN raw beat (valid per schema,
    # since validation only checks that raw beats carry code); the
    # repair loop feeds the render error back to the LLM, which returns
    # working code.
    analyze = (
        '{"concepts": [{"concept": "Raw", "why_suitable": "w", '
        '"storyboard": "s"}]}'
    )
    broken_spec = (
        '{"title": "Raw", "beats": ['
        '{"component": "raw", "code": "this is not valid python !!!", '
        '"duration": 0.5}]}'
    )
    fixed_code = "self.wait(0.5)"
    client = FakeLLMClient(responses=[analyze, broken_spec, fixed_code])
    batch = run_pipeline(client, "text", "text", tmp_path, repair=True)

    assert batch.status == JobStatus.DONE
    clip = batch.clip_jobs[0]
    assert clip.status == JobStatus.DONE
    assert clip.beat_jobs[0].beat.code == "self.wait(0.5)"
```

- [ ] **Step 2: 執行端到端測試** — `pytest tests/llm/test_pipeline_e2e.py -v -m docker`
  Expected: PASS (2 passed)。會渲染真實影片，較慢，要耐心。

- [ ] **Step 3: 執行完整測試套件** — `pytest -q`
  Expected: 全部 PASS（含所有 docker 測試）。

- [ ] **Step 4: Commit**

```bash
git add tests/llm/test_pipeline_e2e.py
git commit -m "test: LLM pipeline end-to-end docker integration tests"
```

---

## Self-Review

**1. Spec coverage（對照設計文件 §5 LLM Codegen Pipeline）**

- 內部 LLM 環境（無 tool use、純文字進出）→ `LLMClient.complete(system, user) -> str` 純文字介面（Task 1）✓
- model-agnostic（config 切換）→ `OpenAIClient` 以 base_url/model 設定，所有程式只依賴 `LLMClient` 介面（Task 1）；模型路由 = 傳不同 client，無需額外程式碼（已在範圍界定說明）✓
- 輸入前處理（PDF → 文字、code 保留）→ `prepare_input`（Task 2）✓
- ① Analyze 階段（1 次 LLM call、輸出 beat 化分鏡的概念清單）→ `analyze`（Task 4）✓
- 元件目錄（schema 自動生成、單一事實來源）→ `build_component_catalog`（Task 3）✓
- ② Codegen 階段（每概念 1 次 call、單一 prompt 直出整份 spec）→ `generate_spec`（Task 5）✓
- ③ 寬鬆解析 + schema 驗證、失敗回問一次 → `generate_spec` 重用 Plan 1 的 `parse_spec_text` + `validate_spec`，失敗帶錯誤回問一次（Task 5）✓
- ④ repair loop 只對 raw beat、渲染失敗 → traceback 回餵 → 重試上限 N=3、N 次後優雅失敗 → `BeatRepairer`（Task 6）+ 接進 `render_batch`（Task 7，失敗的 beat 由 Plan 3 既有邏輯標 FAILED 不拖垮整片）✓
- 元件 beat 不進 repair loop（確定性、失敗是 builder bug）→ `BeatRepairer` 對非 raw beat 直接 raise 不重試（Task 6）✓
- repair loop 是唯一會加 call 的地方、只對 raw beat → 設計如此（Task 6/7）✓
- 端到端 Web 路徑（input → analyze → codegen → render，Phase 1 無人工關卡）→ `run_pipeline`（Task 8）+ docker 驗證（Task 9）✓
- 測試策略：錄製 fixture 的 mock LLM、LLM 層契約是「產出能 parse+validate 的 spec」→ `FakeLLMClient` 貫穿所有 LLM 測試；Task 9 用 fake client + 真實渲染驗證產出能渲染 ✓

**不在範圍（已在範圍界定說明）：** 人工審核關卡 UI（Phase 2）；live eval suite（需真實公司 LLM、屬部署期）。

**2. Placeholder scan：** 無 TBD/TODO。每個 step 都有完整程式碼或精確指令。Task 7 是修改既有檔案的整合任務，每個子步驟（3a–3d）都給出「把 X 改成 Y」的精確前後內容。`_CODEGEN_SYSTEM` 用 `__CATALOG__` 字面標記 + `str.replace`（非 `str.format`），已註明原因——避免 JSON 範例裡的字面 `{ }` 需要轉義。

**3. Type consistency：**
- `LLMClient`（Protocol，`.complete(system, user) -> str`）、`OpenAIClient`、`FakeLLMClient`（`response=` / `responses=` / `.calls`）（Task 1）→ Task 4/5/6/8 的型別標註與測試一致使用。
- `prepare_input(content, kind: InputKind) -> str`、`InputKind`（Task 2）→ Task 8 `generate_specs`/`run_pipeline` 一致 import 與呼叫。
- `build_component_catalog() -> str`（Task 3）→ Task 5 測試的概念性使用 + Task 8 一致呼叫。
- `ConceptCandidate`（concept/why_suitable/storyboard）、`analyze(client, prepared_input, guide_prompt=None) -> list[ConceptCandidate]`、`AnalyzeError`（Task 4）→ Task 5 `generate_spec` 收 `ConceptCandidate`、Task 8 一致。
- `generate_spec(client, concept, catalog) -> SceneSpec`、`CodegenError`（Task 5）→ Task 8 `generate_specs` 一致 import 與呼叫（catch `CodegenError`）。
- `BeatRepairer(client, max_attempts=3)`、`.render_with_repair(beat, work_dir, *, title, aspect_ratio) -> RepairResult`、`RepairResult`（mp4_path/final_beat/attempts）（Task 6）→ Task 7 `_render_beat_job` 一致呼叫並讀 `.mp4_path`/`.final_beat`、Task 7 測試的 `_FakeRepairer` 與 Task 8 `run_pipeline` 一致。
- `render_batch(..., repairer=None)`（Task 7 修改後簽名）→ Task 8 `run_pipeline` 以關鍵字傳入、Task 8 測試的 `fake_render_batch` 簽名一致。
- 重用既有：`parse_spec_text`/`SpecParseError`（Plan 1）、`validate_spec`/`SpecValidationError`/`SceneSpec`（Plan 1）、`render_spec_to_mp4`/`RenderError`（Plan 1）、`Beat`/`SceneSpec`（Plan 1）、`render_batch`/`BatchJob`/`JobStatus`/`BeatCache`（Plan 3）——名稱與簽名與既有程式一致。

無不一致。

---

## Execution Handoff

Plan 完成並存於 `docs/superpowers/plans/2026-05-14-plan-4-llm-layer.md`。兩種執行方式：

**1. Subagent-Driven（推薦，與 Plan 1–3 一致）** — 每 task 一個 subagent，task 之間由我審核。Task 1 須先行（建立 `llm/` 套件 + 依賴，後續任務都依賴它）；Task 2/3/4 互相獨立可平行（一波 ≤3）；Task 5/6 互相獨立可平行；Task 7（改 backend.py）、Task 8（pipeline）、Task 9（e2e）各自單獨執行。

**2. Inline Execution** — 在本對話 session 內逐 task 執行，分批設檢查點審核。

要用哪一種？
