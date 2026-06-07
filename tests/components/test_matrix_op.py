from manim import Mobject

from manim_skill.components.matrix_op import MatrixOp, MatrixOpParams


def test_default_op_is_matmul():
    assert MatrixOpParams().op == "matmul"


def test_build_matmul_has_three_boxes_and_two_operators():
    comp = MatrixOp()
    mobj = comp.build(
        MatrixOpParams(op="matmul", a_label="Q", b_label="K", result_label="S")
    )
    assert isinstance(mobj, Mobject)
    # 3 labeled boxes + 2 operator texts
    assert len(mobj.submobjects) == 5


def test_build_transpose_has_two_boxes_and_one_operator():
    comp = MatrixOp()
    mobj = comp.build(MatrixOpParams(op="transpose", a_label="A"))
    # 1 labeled box + 1 operator + 1 result box
    assert len(mobj.submobjects) == 3


def test_build_reshape_has_two_boxes_and_one_operator():
    comp = MatrixOp()
    mobj = comp.build(MatrixOpParams(op="reshape", a_label="A"))
    assert len(mobj.submobjects) == 3


def test_matrix_op_uses_theme_fonts():
    """Box labels must use FONT_MONO (label_text) after theme wiring."""
    from manim_skill.components.theme import FONT_MONO

    mobj = MatrixOp().build(MatrixOpParams(op="matmul"))
    # mobj[0] = first labeled box VGroup(Rectangle, Text)
    # mobj[0][1] = the Text label inside
    box_label = mobj.submobjects[0].submobjects[1]
    assert box_label.font == FONT_MONO
