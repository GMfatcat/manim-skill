import pytest
from manim import Mobject
from pydantic import ValidationError

from manim_skill.components.plot_evolution import (
    PlotEvolution,
    PlotEvolutionParams,
)


def test_build_returns_non_empty_mobject():
    comp = PlotEvolution()
    mobj = comp.build(
        PlotEvolutionParams(series=[1.0, 0.7, 0.5, 0.4, 0.35])
    )
    assert isinstance(mobj, Mobject)
    assert len(mobj.submobjects) > 0


def test_build_with_title():
    comp = PlotEvolution()
    mobj = comp.build(
        PlotEvolutionParams(series=[1.0, 0.5], title="training loss")
    )
    assert isinstance(mobj, Mobject)
    assert len(mobj.submobjects) > 0


def test_build_with_flat_series_does_not_crash():
    # All-equal values would make y_range degenerate; the component
    # must guard against that.
    comp = PlotEvolution()
    mobj = comp.build(PlotEvolutionParams(series=[2.0, 2.0, 2.0]))
    assert isinstance(mobj, Mobject)


def test_series_requires_at_least_two_points():
    with pytest.raises(ValidationError):
        PlotEvolutionParams(series=[1.0])


def test_graph_line_uses_primary_color():
    from manim_skill.components.theme import THEME

    comp = PlotEvolution()
    mobj = comp.build(PlotEvolutionParams(series=[1.0, 0.7, 0.4]))
    # diagram = VGroup(axes, graph); graph["line_graph"] is the line VMobject
    graph = mobj.submobjects[1]
    line = graph["line_graph"]
    assert line.get_color().to_hex().lower() == THEME.PRIMARY.lower()


def test_title_uses_theme_font():
    from manim_skill.components.theme import FONT_BODY

    comp = PlotEvolution()
    mobj = comp.build(PlotEvolutionParams(series=[1.0, 0.5], title="Loss Curve"))
    # diagram = VGroup(axes, graph, title); title is submobjects[2]
    title = mobj.submobjects[2]
    assert title.font == FONT_BODY
