import pytest
from manim import Mobject
from pydantic import ValidationError

from manim_skill.components.bar_chart import BarChart, BarChartParams
from manim_skill.components.theme import THEME


def test_build_returns_non_empty_mobject():
    comp = BarChart()
    mobj = comp.build(BarChartParams(values=[1.0, 4.0, 9.0]))
    assert isinstance(mobj, Mobject)
    assert len(mobj.submobjects) > 0


def test_build_with_labels_title_highlight():
    comp = BarChart()
    mobj = comp.build(
        BarChartParams(
            values=[1.0, 5.0, 36.9],
            labels=["Baseline", "v1", "Ours"],
            title="Requests per second",
            highlight=2,
        )
    )
    assert isinstance(mobj, Mobject)
    assert len(mobj.submobjects) > 0


def test_highlight_dims_other_bars():
    comp = BarChart()
    mobj = comp.build(BarChartParams(values=[1.0, 2.0, 3.0], highlight=2))
    bars = mobj.submobjects[0]  # first submobject is the bars VGroup
    assert bars[2].get_fill_color().to_hex().lower() == THEME.PRIMARY.lower()
    assert bars[0].get_fill_color().to_hex().lower() == THEME.PRIMARY_SOFT.lower()


def test_no_highlight_all_bars_primary():
    comp = BarChart()
    mobj = comp.build(BarChartParams(values=[1.0, 2.0]))
    bars = mobj.submobjects[0]
    assert bars[0].get_fill_color().to_hex().lower() == THEME.PRIMARY.lower()
    assert bars[1].get_fill_color().to_hex().lower() == THEME.PRIMARY.lower()


def test_build_all_zero_values_does_not_crash():
    comp = BarChart()
    mobj = comp.build(BarChartParams(values=[0.0, 0.0]))
    assert isinstance(mobj, Mobject)


def test_values_requires_at_least_one():
    with pytest.raises(ValidationError):
        BarChartParams(values=[])


def test_labels_length_must_match_values():
    with pytest.raises(ValidationError):
        BarChartParams(values=[1.0, 2.0], labels=["only one"])


def test_highlight_out_of_range_rejected():
    with pytest.raises(ValidationError):
        BarChartParams(values=[1.0, 2.0], highlight=5)
