from manim import Dot, Square, VGroup

from manim_skill.components.layout import (
    FRAME_HEIGHT,
    FRAME_WIDTH,
    clamp_new_mobjects,
    fit_width,
    safe_area,
    stack,
)
from manim_skill.components.theme import MARGIN


def test_fit_width_shrinks_overwide_and_leaves_narrow():
    wide = Square(side_length=20)
    fit_width(wide, 10)
    assert wide.width <= 10 + 1e-6
    narrow = Square(side_length=2)
    fit_width(narrow, 10)
    assert abs(narrow.width - 2) < 1e-6


def test_safe_area_scales_and_recenters_oversized():
    big = Square(side_length=20).shift([5, 3, 0])
    safe_area(big)
    usable_w = FRAME_WIDTH - 2 * MARGIN
    usable_h = FRAME_HEIGHT - 2 * MARGIN
    assert big.width <= usable_w + 1e-6
    assert big.height <= usable_h + 1e-6
    assert big.get_left()[0] >= -usable_w / 2 - 1e-6
    assert big.get_right()[0] <= usable_w / 2 + 1e-6
    assert big.get_bottom()[1] >= -usable_h / 2 - 1e-6
    assert big.get_top()[1] <= usable_h / 2 + 1e-6


def test_safe_area_noop_for_small_centered():
    small = Dot().shift([1, 1, 0])
    before = small.get_center().copy()
    safe_area(small)
    assert (abs(small.get_center() - before) < 1e-6).all()


def test_stack_no_overlap_and_respects_gap():
    a, b, c = Square(side_length=1), Square(side_length=1), Square(side_length=1)
    group = stack([a, b, c], gap=0.5)
    assert isinstance(group, VGroup)
    assert len(group) == 3
    gap_ab = a.get_bottom()[1] - b.get_top()[1]
    assert abs(gap_ab - 0.5) < 1e-6


def test_clamp_new_mobjects_only_touches_new_ones():
    class FakeScene:
        def __init__(self, mobjects):
            self.mobjects = mobjects

    old = Dot()
    big = Square(side_length=20)
    scene = FakeScene([old, big])
    clamp_new_mobjects(scene, {old})
    assert big.width <= FRAME_WIDTH - 2 * MARGIN + 1e-6
