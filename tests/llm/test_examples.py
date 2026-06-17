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
