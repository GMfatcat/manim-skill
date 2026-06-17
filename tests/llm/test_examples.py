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


from pathlib import Path


def test_seed_gold_examples_are_valid():
    gold_dir = Path(__file__).resolve().parents[2] / "examples" / "gold"
    examples = load_gold_examples(gold_dir)
    names = {e.name for e in examples}
    assert {"pipeline-stages", "results-table", "system-graph"} <= names
    for e in examples:
        assert e.tags, f"{e.name} has no tags"
        assert e.spec.beats, f"{e.name} has no beats"
