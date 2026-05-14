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
