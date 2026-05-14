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
