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


def test_theme_font_wired():
    from manim_skill.components.theme import FONT_BODY

    comp = GeometryAnim()
    mobj = comp.build(GeometryAnimParams(shape="circle", label="unit circle"))
    # VGroup: [shape, label_text]; label_text is index 1
    label_obj = mobj.submobjects[1]
    assert label_obj.font == FONT_BODY
