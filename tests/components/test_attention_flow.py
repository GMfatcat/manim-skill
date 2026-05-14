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
