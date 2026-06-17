# Golden Examples Few-Shot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inject the 1–2 most topically-relevant curated "gold" scene specs as few-shot examples into codegen, so a small open model imitates good component-based structure instead of hand-writing fragile `raw` beats.

**Architecture:** A `examples/gold/` directory holds curated `{tags, spec}` JSON files. A dependency-free pure module (`llm/examples.py`) loads them and selects the best matches for a concept by lexical keyword overlap against the curated `tags`. `generate_spec` gains an opt-in `gold_examples` parameter; when supplied it prepends the selected specs to the user prompt. Default `None` preserves current behavior exactly.

**Tech Stack:** Python 3.13, Pydantic (existing `SceneSpec`), pytest (fast suite — `FakeLLMClient`, no Docker, no real LLM).

---

## Background for the implementer

This is the second increment of the Contract-Gated Cascade framework (spec: `docs/superpowers/specs/2026-06-17-golden-examples-design.md`). The premise, validated by the ORCA eval: a small model that *sees* a component-based example is far more likely to pick components (the cheap, robust path) than to hand-write `raw` beats. We curate a few gold specs, tag them with topical keywords, and inject the most relevant ones into the codegen prompt.

Key existing pieces:
- `ConceptCandidate` (`manim_skill/llm/analyze.py`): a Pydantic model with `concept: str`, `why_suitable: str`, `storyboard: str`.
- `generate_spec(client, concept, catalog)` (`manim_skill/llm/codegen.py`): builds a user prompt via `_build_user_prompt(concept)`, calls the LLM, validates, re-asks on failure, then lint-re-asks. We add an opt-in `gold_examples` param.
- `validate_spec(raw: dict) -> SceneSpec` (`manim_skill/spec/validate.py`): validates a raw dict into a `SceneSpec`. Raises `SpecValidationError`. `parse_spec_text` raises `SpecParseError`.
- `FakeLLMClient` (`manim_skill/llm/client.py`): records every `(system, user)` call in `.calls`; `FakeLLMClient(response=...)` returns a fixed string.
- `SceneSpec.model_dump_json(indent=2)` serializes a spec; `SceneSpec` and `Beat` are in `manim_skill/spec/schema.py`.

Run the fast suite with: `pytest -m "not docker" -q`

All behavior is **opt-in and additive**: with no gold directory, or no tag overlap, codegen behaves exactly as today.

---

## File Structure

- **Create** `manim_skill/llm/examples.py` — `GoldExample` dataclass, `GoldExampleError`, `load_gold_examples(directory)`, `select_examples(concept, gold, k=2)`. One responsibility: the gold store + selection. No LLM calls, no Docker.
- **Modify** `manim_skill/llm/codegen.py` — `_build_user_prompt(concept, examples=None)` and `generate_spec(..., *, gold_examples=None)`.
- **Modify** `manim_skill/llm/pipeline.py` — thread `gold_examples` through `generate_specs`.
- **Modify** `manim_skill/cli.py` — `_cmd_codegen_concepts` loads a `--gold-dir` (default `examples/gold`) and passes it.
- **Modify** `scripts/eval/run_smoke.py` — load `examples/gold` and pass into the `codegen` and `regen` stages.
- **Create** `examples/gold/pipeline-stages.json`, `examples/gold/results-table.json`, `examples/gold/system-graph.json` — 3 seed gold examples.
- **Test** `tests/llm/test_examples.py` (create), `tests/llm/test_codegen.py` (extend).

---

## Task 1: `GoldExample` + `load_gold_examples`

**Files:**
- Create: `manim_skill/llm/examples.py`
- Test: `tests/llm/test_examples.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/llm/test_examples.py`:

```python
import json

import pytest

from manim_skill.llm.examples import (
    GoldExample,
    GoldExampleError,
    load_gold_examples,
)

_VALID_SPEC = {
    "title": "Demo",
    "aspect_ratio": "16:9",
    "beats": [
        {"component": "TextBeat", "params": {"text": "Hi", "style": "title"}, "duration": 2.0}
    ],
}


def _write(dirpath, name, payload):
    p = dirpath / name
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_load_gold_examples_missing_dir_returns_empty(tmp_path):
    assert load_gold_examples(tmp_path / "nope") == []


def test_load_gold_examples_loads_and_validates(tmp_path):
    _write(tmp_path, "a.json", {"tags": ["foo", "bar"], "spec": _VALID_SPEC})
    examples = load_gold_examples(tmp_path)
    assert len(examples) == 1
    ex = examples[0]
    assert isinstance(ex, GoldExample)
    assert ex.name == "a"
    assert ex.tags == ["foo", "bar"]
    assert ex.spec.title == "Demo"


def test_load_gold_examples_sorted_by_name(tmp_path):
    _write(tmp_path, "b.json", {"tags": ["x"], "spec": _VALID_SPEC})
    _write(tmp_path, "a.json", {"tags": ["y"], "spec": _VALID_SPEC})
    names = [e.name for e in load_gold_examples(tmp_path)]
    assert names == ["a", "b"]


def test_load_gold_examples_missing_keys_raises(tmp_path):
    _write(tmp_path, "bad.json", {"spec": _VALID_SPEC})  # no tags
    with pytest.raises(GoldExampleError, match="bad.json"):
        load_gold_examples(tmp_path)


def test_load_gold_examples_bad_tags_raises(tmp_path):
    _write(tmp_path, "bad.json", {"tags": "notalist", "spec": _VALID_SPEC})
    with pytest.raises(GoldExampleError, match="tags"):
        load_gold_examples(tmp_path)


def test_load_gold_examples_invalid_spec_raises(tmp_path):
    _write(tmp_path, "bad.json", {"tags": ["x"], "spec": {"title": "no beats"}})
    with pytest.raises(GoldExampleError, match="bad.json"):
        load_gold_examples(tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/llm/test_examples.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'manim_skill.llm.examples'`

- [ ] **Step 3: Create the module (loader half)**

Create `manim_skill/llm/examples.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from manim_skill.spec.schema import SceneSpec
from manim_skill.spec.validate import SpecValidationError, validate_spec


class GoldExampleError(RuntimeError):
    """Raised when a gold-example file is malformed."""


@dataclass
class GoldExample:
    name: str
    tags: list[str]
    spec: SceneSpec


def load_gold_examples(directory) -> list[GoldExample]:
    """Load curated gold examples from a directory of {tags, spec} JSON files.

    Returns them sorted by file stem. A missing directory yields an empty
    list (the feature is opt-in and degrades to current behavior). A
    malformed file (bad JSON, missing keys, non-string tags, or a spec
    that fails validation) raises GoldExampleError naming the file — bad
    gold is caught at load time, never silently injected.
    """
    directory = Path(directory)
    if not directory.is_dir():
        return []

    examples: list[GoldExample] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise GoldExampleError(f"{path.name}: invalid JSON: {exc}") from exc
        if not isinstance(data, dict) or "tags" not in data or "spec" not in data:
            raise GoldExampleError(
                f"{path.name}: must be an object with 'tags' and 'spec'"
            )
        tags = data["tags"]
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            raise GoldExampleError(f"{path.name}: 'tags' must be a list of strings")
        try:
            spec = validate_spec(data["spec"])
        except SpecValidationError as exc:
            raise GoldExampleError(f"{path.name}: invalid spec: {exc}") from exc
        examples.append(GoldExample(name=path.stem, tags=tags, spec=spec))
    return examples
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/llm/test_examples.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add manim_skill/llm/examples.py tests/llm/test_examples.py
git commit -m "feat(llm): gold-example store loader"
```

---

## Task 2: `select_examples` (lexical-overlap selection)

**Files:**
- Modify: `manim_skill/llm/examples.py`
- Test: `tests/llm/test_examples.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/llm/test_examples.py`:

```python
from manim_skill.llm.analyze import ConceptCandidate
from manim_skill.llm.examples import select_examples
from manim_skill.spec.schema import SceneSpec


def _gold(name, tags):
    spec = SceneSpec.model_validate(_VALID_SPEC)
    return GoldExample(name=name, tags=tags, spec=spec)


def _concept(text):
    return ConceptCandidate(concept=text, why_suitable="", storyboard="")


def test_select_examples_ranks_by_tag_overlap():
    gold = [
        _gold("pipeline", ["pipeline", "stages"]),
        _gold("table", ["table", "results"]),
        _gold("graph", ["graph", "nodes"]),
    ]
    picked = select_examples(_concept("a pipeline of stages and steps"), gold, k=2)
    assert [e.name for e in picked] == ["pipeline"]  # only 'pipeline' overlaps


def test_select_examples_topk_and_score_order():
    gold = [
        _gold("a", ["pipeline"]),               # score 1
        _gold("b", ["pipeline", "stages"]),     # score 2
        _gold("c", ["stages"]),                 # score 1
    ]
    picked = select_examples(_concept("pipeline stages flow"), gold, k=2)
    # b (score 2) first; then a vs c tie on score 1 -> name asc -> a
    assert [e.name for e in picked] == ["b", "a"]


def test_select_examples_multiword_tag_needs_all_words():
    gold = [_gold("x", ["pipeline parallelism"])]
    assert select_examples(_concept("pipeline of stages"), gold) == []  # 'parallelism' missing
    picked = select_examples(_concept("pipeline parallelism across gpus"), gold)
    assert [e.name for e in picked] == ["x"]


def test_select_examples_no_overlap_returns_empty():
    gold = [_gold("x", ["table", "results"])]
    assert select_examples(_concept("a graph of nodes"), gold) == []


def test_select_examples_empty_gold_returns_empty():
    assert select_examples(_concept("anything"), []) == []


def test_select_examples_matches_across_all_concept_fields():
    gold = [_gold("x", ["throughput"])]
    c = ConceptCandidate(concept="Perf", why_suitable="", storyboard="shows throughput growth")
    assert [e.name for e in select_examples(c, gold)] == ["x"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/llm/test_examples.py -k select -v`
Expected: FAIL with `ImportError: cannot import name 'select_examples'`

- [ ] **Step 3: Add `select_examples` to the module**

Append to `manim_skill/llm/examples.py`:

```python
import re

from manim_skill.llm.analyze import ConceptCandidate

_WORD = re.compile(r"\w+")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def _tag_matches(tag: str, tokens: set[str]) -> bool:
    tag_words = _tokens(tag)
    return bool(tag_words) and tag_words <= tokens


def select_examples(
    concept: ConceptCandidate, gold: list[GoldExample], k: int = 2
) -> list[GoldExample]:
    """Pick the k most topically-relevant gold examples for a concept.

    Scores each example by how many of its tags fully overlap the
    concept's text (concept + why_suitable + storyboard), tokenized to
    lowercase words; a multi-word tag matches only if every word is
    present. Returns the top-k by (score desc, name asc); examples with
    zero overlap are dropped, and an empty result means "inject nothing"
    rather than something irrelevant.
    """
    tokens = _tokens(
        f"{concept.concept} {concept.why_suitable} {concept.storyboard}"
    )
    scored: list[tuple[int, GoldExample]] = []
    for ex in gold:
        score = sum(1 for tag in ex.tags if _tag_matches(tag, tokens))
        if score > 0:
            scored.append((score, ex))
    scored.sort(key=lambda se: (-se[0], se[1].name))
    return [ex for _, ex in scored[:k]]
```

Note: place the `import re` and `from manim_skill.llm.analyze import ConceptCandidate` with the other imports at the top of the file rather than mid-file (move them up when you add them).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/llm/test_examples.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add manim_skill/llm/examples.py tests/llm/test_examples.py
git commit -m "feat(llm): lexical-overlap gold-example selection"
```

---

## Task 3: Inject selected examples into `generate_spec`

**Files:**
- Modify: `manim_skill/llm/codegen.py` (`_build_user_prompt`, `generate_spec`)
- Test: `tests/llm/test_codegen.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/llm/test_codegen.py` (the file already imports/uses `FakeLLMClient`, `ConceptCandidate`, `generate_spec`, and `build_component_catalog`; if any import is missing, add it):

```python
def test_generate_spec_injects_selected_gold_examples():
    from manim_skill.llm.examples import GoldExample
    from manim_skill.spec.schema import SceneSpec

    gold_spec = SceneSpec.model_validate(
        {
            "title": "Gold Pipeline",
            "aspect_ratio": "16:9",
            "beats": [
                {"component": "PipelineDiagram",
                 "params": {"stages": ["A", "B", "C"]}, "duration": 4.0}
            ],
        }
    )
    gold = [GoldExample(name="pipeline-stages", tags=["pipeline", "stages"], spec=gold_spec)]
    concept = ConceptCandidate(
        concept="A pipeline of stages",
        why_suitable="it has clear sequential stages",
        storyboard="boxes flow left to right",
    )
    valid = (
        '{"title":"X","aspect_ratio":"16:9","beats":'
        '[{"component":"TextBeat","params":{"text":"hi","style":"title"},"duration":2.0}]}'
    )
    client = FakeLLMClient(response=valid)
    generate_spec(client, concept, build_component_catalog(), gold_examples=gold)

    user_prompt = client.calls[0][1]
    assert "Reference specs for SIMILAR concepts" in user_prompt
    assert "pipeline-stages" in user_prompt
    assert "Gold Pipeline" in user_prompt  # the gold spec's title made it in


def test_generate_spec_no_gold_examples_leaves_prompt_unchanged():
    concept = ConceptCandidate(concept="C", why_suitable="w", storyboard="s")
    valid = (
        '{"title":"X","aspect_ratio":"16:9","beats":'
        '[{"component":"TextBeat","params":{"text":"hi","style":"title"},"duration":2.0}]}'
    )
    client = FakeLLMClient(response=valid)
    generate_spec(client, concept, build_component_catalog())
    assert "Reference specs for SIMILAR concepts" not in client.calls[0][1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/llm/test_codegen.py -k "gold or unchanged" -v`
Expected: FAIL — `generate_spec` has no `gold_examples` keyword.

- [ ] **Step 3: Update `_build_user_prompt` and `generate_spec`**

In `manim_skill/llm/codegen.py`, add the import near the top imports:

```python
from manim_skill.llm.examples import GoldExample, select_examples
```

Replace `_build_user_prompt` with:

```python
def _build_user_prompt(
    concept: ConceptCandidate, examples: list[GoldExample] | None = None
) -> str:
    prefix = ""
    if examples:
        blocks = [
            f"// {ex.name} (tags: {', '.join(ex.tags)})\n"
            f"{ex.spec.model_dump_json(indent=2)}"
            for ex in examples
        ]
        prefix = (
            "Reference specs for SIMILAR concepts — imitate their structure "
            "and component choices, do NOT copy their content:\n\n"
            + "\n\n".join(blocks)
            + "\n\n"
        )
    return (
        f"{prefix}"
        f"Concept: {concept.concept}\n"
        f"Why it animates well: {concept.why_suitable}\n"
        f"Storyboard:\n{concept.storyboard}\n\n"
        "Produce the scene spec JSON for this concept."
    )
```

Change the `generate_spec` signature and the `base_user` line. The signature becomes:

```python
def generate_spec(
    client: LLMClient,
    concept: ConceptCandidate,
    catalog: str,
    *,
    gold_examples: list[GoldExample] | None = None,
) -> SceneSpec:
```

And replace the `base_user = _build_user_prompt(concept)` line (just after `system = _CODEGEN_SYSTEM.replace(...)`) with:

```python
    selected = select_examples(concept, gold_examples) if gold_examples else []
    base_user = _build_user_prompt(concept, selected)
```

(Everything else in `generate_spec` is unchanged — the re-ask and lint-re-ask both build off `base_user`, so they inherit the injected examples.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/llm/test_codegen.py -k "gold or unchanged" -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full codegen test file (no regressions)**

Run: `pytest tests/llm/test_codegen.py -v`
Expected: PASS (all existing tests still green)

- [ ] **Step 6: Commit**

```bash
git add manim_skill/llm/codegen.py tests/llm/test_codegen.py
git commit -m "feat(llm): inject selected gold examples into codegen prompt"
```

---

## Task 4: Seed `examples/gold/` + seed-validity test

**Files:**
- Create: `examples/gold/pipeline-stages.json`, `examples/gold/results-table.json`, `examples/gold/system-graph.json`
- Test: `tests/llm/test_examples.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/llm/test_examples.py`:

```python
from pathlib import Path


def test_seed_gold_examples_are_valid():
    gold_dir = Path(__file__).resolve().parents[2] / "examples" / "gold"
    examples = load_gold_examples(gold_dir)
    names = {e.name for e in examples}
    assert {"pipeline-stages", "results-table", "system-graph"} <= names
    for e in examples:
        assert e.tags, f"{e.name} has no tags"
        assert e.spec.beats, f"{e.name} has no beats"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm/test_examples.py::test_seed_gold_examples_are_valid -v`
Expected: FAIL — the `examples/gold/` directory does not exist yet, so `load_gold_examples` returns `[]` and the subset assertion fails.

- [ ] **Step 3: Create the three seed files**

Create `examples/gold/pipeline-stages.json`:

```json
{
  "tags": ["pipeline", "stages", "flow", "sequence", "scheduling", "iteration", "steps", "loop"],
  "spec": {
    "title": "Iteration-Level Scheduling",
    "aspect_ratio": "16:9",
    "beats": [
      {"component": "TextBeat", "params": {"text": "Iteration-Level Scheduling", "subtitle": "one step at a time", "style": "title"}, "duration": 2.0},
      {"component": "PipelineDiagram", "params": {"title": "One model iteration at a time", "stages": ["Request pool", "Scheduler picks batch", "Engine runs 1 iteration", "Emit 1 token", "Return done / reschedule"]}, "duration": 5.0},
      {"component": "TextBeat", "params": {"text": "Why it matters", "style": "bullets", "bullets": ["Schedule at iteration granularity, not whole requests", "Finished requests return immediately", "New requests join the next iteration"]}, "duration": 4.0}
    ]
  }
}
```

Create `examples/gold/results-table.json`:

```json
{
  "tags": ["table", "comparison", "results", "benchmark", "throughput", "performance", "metrics", "speedup", "latency"],
  "spec": {
    "title": "End-to-End Performance Gain",
    "aspect_ratio": "16:9",
    "beats": [
      {"component": "TextBeat", "params": {"text": "End-to-End Performance Gain", "subtitle": "baseline vs improved", "style": "title"}, "duration": 2.0},
      {"component": "TableBeat", "params": {"title": "Same latency budget, far more throughput", "headers": ["Throughput (req/s)", "Tail latency"], "row_labels": ["Baseline", "Ours"], "rows": [["1x (baseline)", "spikes under load"], ["36.9x", "stays flat"]], "highlight_cells": [[1, 0]]}, "duration": 4.5},
      {"component": "PlotEvolution", "params": {"title": "Throughput scales with load", "series": [1, 4, 9, 18, 28, 36.9]}, "duration": 4.0}
    ]
  }
}
```

Create `examples/gold/system-graph.json`:

```json
{
  "tags": ["architecture", "graph", "components", "nodes", "system", "dataflow", "loop", "pipeline", "scheduler", "engine"],
  "spec": {
    "title": "System Architecture",
    "aspect_ratio": "16:9",
    "beats": [
      {"component": "TextBeat", "params": {"text": "System Architecture", "subtitle": "where the pieces sit", "style": "title"}, "duration": 2.0},
      {"component": "GraphBeat", "params": {"title": "The end-to-end serving loop", "nodes": ["Clients", "Endpoint", "Request pool", "Scheduler", "Execution engine"], "edges": [["Clients", "Endpoint"], ["Endpoint", "Request pool"], ["Request pool", "Scheduler"], ["Scheduler", "Execution engine"], ["Execution engine", "Scheduler"], ["Scheduler", "Clients"]], "directed": true, "layout": "circular"}, "duration": 5.0},
      {"component": "TextBeat", "params": {"text": "How a request flows", "style": "bullets", "bullets": ["Requests enter a shared pool", "The scheduler picks a batch each step", "The engine runs one iteration, then yields", "Finished results stream back"]}, "duration": 4.5}
    ]
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/llm/test_examples.py::test_seed_gold_examples_are_valid -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add examples/gold/pipeline-stages.json examples/gold/results-table.json examples/gold/system-graph.json tests/llm/test_examples.py
git commit -m "feat(examples): seed gold examples (pipeline / table / graph)"
```

---

## Task 5: Wire into `pipeline.generate_specs` and the CLI `codegen-concepts`

**Files:**
- Modify: `manim_skill/llm/pipeline.py` (`generate_specs`)
- Modify: `manim_skill/cli.py` (`_cmd_codegen_concepts` + its subparser)
- Test: `tests/llm/test_pipeline.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/llm/test_pipeline.py` (the file already uses `FakeLLMClient`; add imports if missing):

```python
def test_generate_specs_threads_gold_examples(monkeypatch):
    from manim_skill.llm import pipeline as pipeline_mod
    from manim_skill.llm.examples import GoldExample
    from manim_skill.spec.schema import SceneSpec
    from manim_skill.llm.analyze import ConceptCandidate

    captured = {}

    def fake_generate_spec(client, concept, catalog, *, gold_examples=None):
        captured["gold_examples"] = gold_examples
        return SceneSpec.model_validate(
            {"title": "X", "aspect_ratio": "16:9",
             "beats": [{"component": "TextBeat", "params": {"text": "hi", "style": "title"}, "duration": 2.0}]}
        )

    monkeypatch.setattr(pipeline_mod, "analyze", lambda *a, **k: [ConceptCandidate(concept="c", why_suitable="w", storyboard="s")])
    monkeypatch.setattr(pipeline_mod, "generate_spec", fake_generate_spec)

    gold = [GoldExample(name="g", tags=["t"], spec=SceneSpec.model_validate(
        {"title": "G", "aspect_ratio": "16:9",
         "beats": [{"component": "TextBeat", "params": {"text": "g", "style": "title"}, "duration": 2.0}]}))]

    from manim_skill.llm.client import FakeLLMClient
    pipeline_mod.generate_specs(FakeLLMClient(response=""), "text", "text", gold_examples=gold)
    assert captured["gold_examples"] is gold
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm/test_pipeline.py::test_generate_specs_threads_gold_examples -v`
Expected: FAIL — `generate_specs` has no `gold_examples` keyword.

- [ ] **Step 3: Thread the parameter through `generate_specs`**

In `manim_skill/llm/pipeline.py`, add the import near the top:

```python
from manim_skill.llm.examples import GoldExample
```

Change `generate_specs` to accept and forward `gold_examples`:

```python
def generate_specs(
    client: LLMClient,
    content,
    kind: InputKind,
    *,
    guide_prompt: str | None = None,
    gold_examples: list[GoldExample] | None = None,
) -> list[SceneSpec]:
    """Run the LLM half of the pipeline: input -> analyze -> codegen.

    Returns one SceneSpec per concept the analyze stage found. A
    concept whose codegen fails (CodegenError) is skipped so one bad
    concept does not sink the rest. `gold_examples`, when supplied, are
    offered to codegen as few-shot references.
    """
    prepared = prepare_input(content, kind)
    concepts = analyze(client, prepared, guide_prompt=guide_prompt)
    catalog = build_component_catalog()
    specs: list[SceneSpec] = []
    for concept in concepts:
        try:
            specs.append(
                generate_spec(client, concept, catalog, gold_examples=gold_examples)
            )
        except CodegenError:
            continue
    return specs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/llm/test_pipeline.py::test_generate_specs_threads_gold_examples -v`
Expected: PASS

- [ ] **Step 5: Add `--gold-dir` to the CLI and load it in `_cmd_codegen_concepts`**

In `manim_skill/cli.py`, add the import near the top imports:

```python
from manim_skill.llm.examples import load_gold_examples
```

In the `codegen-concepts` subparser block (where `--indices` is added), add another argument right after the `--indices` block:

```python
    p_codegen.add_argument(
        "--gold-dir", default="examples/gold",
        help="directory of curated gold example specs to use as few-shot "
             "(default: examples/gold; ignored if it doesn't exist)",
    )
```

In `_cmd_codegen_concepts`, just after `client = _build_llm_client_from_env()`, add:

```python
    gold_examples = load_gold_examples(args.gold_dir)
    if gold_examples:
        print(f"gold examples: {len(gold_examples)} loaded from {args.gold_dir}")
```

And change the `generate_spec(client, concept, catalog)` call inside the loop to:

```python
            spec = generate_spec(
                client, concept, catalog, gold_examples=gold_examples
            )
```

- [ ] **Step 6: Verify the CLI imports and the new flag parse**

Run: `python -c "import manim_skill.cli"` then `python -m manim_skill.cli codegen-concepts --help`
Expected: no import error; `--help` lists `--gold-dir`. (If `python -m manim_skill.cli` is not wired, use `manim-skill codegen-concepts --help`.)

- [ ] **Step 7: Run the pipeline test file (no regressions)**

Run: `pytest tests/llm/test_pipeline.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add manim_skill/llm/pipeline.py manim_skill/cli.py tests/llm/test_pipeline.py
git commit -m "feat(cli,llm): wire gold examples into codegen-concepts and generate_specs"
```

---

## Task 6: Wire into the live-eval smoke script

**Files:**
- Modify: `scripts/eval/run_smoke.py` (`stage_codegen`, `stage_regen`)

- [ ] **Step 1: Add gold loading and pass it to `generate_spec`**

This script has no unit test (it is a live-eval harness); verify by import + `--help`-style dry parse at the end. In `scripts/eval/run_smoke.py`:

Add to the imports block (with the other `from manim_skill.llm...` imports):

```python
from manim_skill.llm.examples import load_gold_examples
```

In `stage_codegen`, just after `catalog = build_component_catalog()`, add:

```python
    gold = load_gold_examples("examples/gold")
    if gold:
        print(f"[gold] {len(gold)} example(s) loaded")
```

and change the `spec = generate_spec(client, concept, catalog)` call to:

```python
            spec = generate_spec(client, concept, catalog, gold_examples=gold)
```

In `stage_regen`, just after `catalog = build_component_catalog()`, add the same loading:

```python
    gold = load_gold_examples("examples/gold")
    if gold:
        print(f"[gold] {len(gold)} example(s) loaded")
```

and change its `spec = generate_spec(client, concept, catalog)` call to:

```python
            spec = generate_spec(client, concept, catalog, gold_examples=gold)
```

- [ ] **Step 2: Verify the script still imports/parses**

Run: `python -c "import ast,io; ast.parse(io.open('scripts/eval/run_smoke.py',encoding='utf-8').read()); print('ok')"`
Expected: prints `ok` (no syntax error).

- [ ] **Step 3: Run the full fast suite (no regressions)**

Run: `pytest -m "not docker" -q`
Expected: PASS (all fast tests green)

- [ ] **Step 4: Commit**

```bash
git add scripts/eval/run_smoke.py
git commit -m "feat(eval): load gold examples in run_smoke codegen/regen stages"
```

---

## Self-Review notes (already applied)

- **Spec coverage:** §1 store → Task 1 (loader) + Task 4 (seeds). §2 selection → Task 2. §3 injection → Task 3; caller wiring → Tasks 5 (pipeline + CLI) and 6 (run_smoke). §4 testing → tests in every task + the seed-validity test (Task 4). Out-of-scope per spec (service/docker gold loading, embedding match, auto-tags) is correctly absent.
- **Backward compatibility:** `gold_examples`/`examples` params default to `None`; `select_examples` and `load_gold_examples` return `[]` on no-match / missing dir; Task 3's second test asserts the prompt is unchanged without gold. Nothing breaks existing callers.
- **Type consistency:** `GoldExample(name, tags, spec)`, `load_gold_examples(directory) -> list[GoldExample]`, `select_examples(concept, gold, k=2) -> list[GoldExample]`, and `generate_spec(..., gold_examples=...)` / `generate_specs(..., gold_examples=...)` names and signatures match across Tasks 1–6.
- **Seeds validate:** seed JSON params match the component schemas (`TextBeat` text/subtitle/style/bullets, `PipelineDiagram` title/stages, `TableBeat` headers/rows/row_labels/highlight_cells/title, `PlotEvolution` series/title, `GraphBeat` nodes/edges/directed/layout/title) used elsewhere in the repo; Task 4's test loads them through the real `validate_spec`.
- **No placeholders:** every code/test step contains complete code and exact run/expected lines.
