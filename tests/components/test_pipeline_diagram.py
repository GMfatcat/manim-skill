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
