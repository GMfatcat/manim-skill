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


def test_parse_recovers_single_backslash_latex():
    # The model emitted single-backslash LaTeX commands (invalid JSON
    # escapes). The de-tox must preserve the backslash, not drop it
    # (json5 would silently turn "\quad" into "quad").
    text = '{"formula": "\\quad K = \\sqrt{x} + \\alpha"}'
    result = parse_spec_text(text)
    assert result["formula"] == "\\quad K = \\sqrt{x} + \\alpha"


def test_parse_leaves_double_backslash_latex_unchanged():
    # Correctly double-escaped LaTeX must decode to a single backslash.
    text = '{"formula": "\\\\frac{a}{b}"}'
    assert parse_spec_text(text)["formula"] == "\\frac{a}{b}"


def test_parse_detox_preserves_valid_newline_escape():
    # A lone "\quad" forces the de-tox path; a legitimate "\n" elsewhere must
    # stay a real newline (not get doubled into a literal backslash-n).
    text = '{"formula": "\\quad", "caption": "a\\nb"}'
    result = parse_spec_text(text)
    assert result["formula"] == "\\quad"
    assert result["caption"] == "a\nb"
