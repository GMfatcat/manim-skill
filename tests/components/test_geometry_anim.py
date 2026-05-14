from manim import Mobject

from manim_skill.components.geometry_anim import (
    GeometryAnim,
    GeometryAnimParams,
)


def test_defaults():
    params = GeometryAnimParams()
    assert params.shape == "circle"
    assert params.transform == "none"
    assert params.label is None


def test_build_each_shape():
    comp = GeometryAnim()
    for shape in ("circle", "square", "triangle", "polygon"):
        mobj = comp.build(GeometryAnimParams(shape=shape))
        assert isinstance(mobj, Mobject)
        assert len(mobj.submobjects) >= 1


def test_build_with_label_adds_text():
    comp = GeometryAnim()
    plain = comp.build(GeometryAnimParams(shape="circle"))
    labeled = comp.build(
        GeometryAnimParams(shape="circle", label="unit circle")
    )
    assert len(labeled.submobjects) > len(plain.submobjects)
