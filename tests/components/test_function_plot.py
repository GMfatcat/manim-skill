import pytest
from manim import Mobject
from pydantic import ValidationError

from manim_skill.components.function_plot import (
    FunctionPlot,
    FunctionPlotParams,
)


def test_build_returns_non_empty_mobject():
    comp = FunctionPlot()
    mobj = comp.build(
        FunctionPlotParams(expression="x**2", x_range=[-3, 3, 1], y_range=[0, 9, 2])
    )
    assert isinstance(mobj, Mobject)
    assert len(mobj.submobjects) > 0


def test_supports_math_module_functions():
    # The expression namespace should expose `exp`, `sin`, `cos`, `log`...
    comp = FunctionPlot()
    mobj = comp.build(
        FunctionPlotParams(
            expression="1 / (1 + exp(-x))",
            x_range=[-5, 5, 1],
            y_range=[0, 1, 0.25],
        )
    )
    assert isinstance(mobj, Mobject)


def test_supports_curated_math_function_names():
    # tanh, sin, cos, exp, log etc. are exposed directly — no need to
    # qualify with `math.` or `np.`. Keeping the namespace small +
    # picklable avoids breaking manim's plot caching.
    comp = FunctionPlot()
    mobj = comp.build(
        FunctionPlotParams(
            expression="tanh(x)",
            x_range=[-3, 3, 1],
            y_range=[-1, 1, 0.5],
        )
    )
    assert isinstance(mobj, Mobject)


def test_title_and_axis_labels_added():
    comp = FunctionPlot()
    bare = comp.build(
        FunctionPlotParams(expression="x", x_range=[-3, 3, 1], y_range=[-3, 3, 1])
    )
    decorated = comp.build(
        FunctionPlotParams(
            expression="x",
            x_range=[-3, 3, 1],
            y_range=[-3, 3, 1],
            x_label="x axis",
            y_label="y axis",
            title="A linear function",
        )
    )
    assert len(decorated.submobjects) > len(bare.submobjects)


def test_invalid_expression_rejected_at_build_time():
    comp = FunctionPlot()
    with pytest.raises(ValueError, match="expression"):
        comp.build(
            FunctionPlotParams(
                expression="this is not python",
                x_range=[-1, 1, 0.5],
                y_range=[-1, 1, 0.5],
            )
        )


def test_expression_with_unsafe_names_rejected():
    comp = FunctionPlot()
    with pytest.raises(ValueError, match="expression"):
        comp.build(
            FunctionPlotParams(
                expression="__import__('os').system('echo hi')",
                x_range=[-1, 1, 0.5],
                y_range=[-1, 1, 0.5],
            )
        )


def test_x_range_must_have_2_or_3_entries():
    with pytest.raises(ValidationError):
        FunctionPlotParams(
            expression="x", x_range=[0], y_range=[0, 1, 0.5]
        )
    with pytest.raises(ValidationError):
        FunctionPlotParams(
            expression="x",
            x_range=[0, 1, 0.1, 99],
            y_range=[0, 1, 0.5],
        )
