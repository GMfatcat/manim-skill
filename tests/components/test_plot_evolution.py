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
