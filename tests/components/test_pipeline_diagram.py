import pytest
from manim import Mobject
from pydantic import ValidationError

from manim_skill.components.pipeline_diagram import (
    PipelineDiagram,
    PipelineDiagramParams,
)


def test_build_returns_non_empty_mobject():
    comp = PipelineDiagram()
    mobj = comp.build(
        PipelineDiagramParams(stages=["load", "train", "eval"])
    )
    assert isinstance(mobj, Mobject)
    assert len(mobj.submobjects) > 0


def test_single_stage_has_no_arrows():
    comp = PipelineDiagram()
    mobj = comp.build(PipelineDiagramParams(stages=["only"]))
    # diagram = VGroup(boxes, arrows); the arrows group is the 2nd submobject
    boxes, arrows = mobj.submobjects[0], mobj.submobjects[1]
    assert len(boxes.submobjects) == 1
    assert len(arrows.submobjects) == 0


def test_three_stages_have_two_arrows():
    comp = PipelineDiagram()
    mobj = comp.build(PipelineDiagramParams(stages=["a", "b", "c"]))
    arrows = mobj.submobjects[1]
    assert len(arrows.submobjects) == 2


def test_stages_requires_at_least_one():
    with pytest.raises(ValidationError):
        PipelineDiagramParams(stages=[])


def test_diagram_fits_camera_width_with_many_stages():
    comp = PipelineDiagram()
    mobj = comp.build(
        PipelineDiagramParams(
            stages=["load", "tokenize", "embed", "encode", "attend", "decode", "emit"]
        )
    )
    assert mobj.width <= 12.0


def test_diagram_fits_camera_width_with_long_title():
    comp = PipelineDiagram()
    long_title = (
        "Hyper-Connections (HC) - widen the residual stream, add learnable mixing layer here"
    )
    assert len(long_title) >= 80
    mobj = comp.build(
        PipelineDiagramParams(stages=["a", "b", "c"], title=long_title)
    )
    assert mobj.width <= 12.0


def test_stage_label_uses_theme_font():
    from manim_skill.components.theme import FONT_MONO

    comp = PipelineDiagram()
    mobj = comp.build(PipelineDiagramParams(stages=["load", "train"]))
    # mobj[0] = boxes VGroup; boxes[0] = VGroup(box, label); label = boxes[0][1]
    label = mobj.submobjects[0].submobjects[0].submobjects[1]
    assert label.font == FONT_MONO


def test_box_border_uses_primary_color():
    from manim_skill.components.theme import THEME

    comp = PipelineDiagram()
    mobj = comp.build(PipelineDiagramParams(stages=["load"]))
    # mobj[0] = boxes VGroup; boxes[0] = VGroup(box, label); box = boxes[0][0]
    box = mobj.submobjects[0].submobjects[0].submobjects[0]
    assert box.get_color().to_hex().lower() == THEME.PRIMARY.lower()


def test_title_uses_theme_font():
    from manim_skill.components.theme import FONT_BODY

    comp = PipelineDiagram()
    mobj = comp.build(PipelineDiagramParams(stages=["a", "b"], title="My Pipeline"))
    # diagram = VGroup(boxes, arrows, title); title is submobjects[2]
    title = mobj.submobjects[2]
    assert title.font == FONT_BODY
