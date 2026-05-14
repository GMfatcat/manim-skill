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
