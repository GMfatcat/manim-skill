import pytest
from manim import Mobject
from pydantic import ValidationError

from manim_skill.render.docker_render import render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec


def test_params_requires_expression():
    from manim_skill.components.optimization_path import (
        OptimizationPathParams,
    )

    with pytest.raises(ValidationError):
        OptimizationPathParams(
            x_range=[-2, 2, 0.5],
            y_range=[0, 4, 1],
            start_x=-1.8,
            min_x=0.0,
        )


def test_start_and_min_must_be_within_x_range():
    from manim_skill.components.optimization_path import (
        OptimizationPathParams,
    )

    with pytest.raises(ValidationError):
        OptimizationPathParams(
            expression="x**2",
            x_range=[-2, 2, 0.5],
            y_range=[0, 4, 1],
            start_x=-5.0,  # outside [-2, 2]
            min_x=0.0,
        )
    with pytest.raises(ValidationError):
        OptimizationPathParams(
            expression="x**2",
            x_range=[-2, 2, 0.5],
            y_range=[0, 4, 1],
            start_x=-1.0,
            min_x=10.0,  # outside [-2, 2]
        )


def test_n_steps_must_be_positive():
    from manim_skill.components.optimization_path import (
        OptimizationPathParams,
    )

    with pytest.raises(ValidationError):
        OptimizationPathParams(
            expression="x**2",
            x_range=[-2, 2, 0.5],
            y_range=[0, 4, 1],
            start_x=-1.8,
            min_x=0.0,
            n_steps=0,
        )


def test_invalid_expression_rejected_at_build():
    from manim_skill.components.optimization_path import (
        OptimizationPath,
        OptimizationPathParams,
    )

    with pytest.raises(ValueError, match="expression"):
        OptimizationPath().build(
            OptimizationPathParams(
                expression="undef_function(x)",
                x_range=[-2, 2, 0.5],
                y_range=[0, 4, 1],
                start_x=-1.8,
                min_x=0.0,
            )
        )


def test_build_returns_mobject():
    from manim_skill.components.optimization_path import (
        OptimizationPath,
        OptimizationPathParams,
    )

    mobj = OptimizationPath().build(
        OptimizationPathParams(
            expression="x**2",
            x_range=[-2, 2, 0.5],
            y_range=[0, 4, 1],
            start_x=-1.8,
            min_x=0.0,
        )
    )
    assert isinstance(mobj, Mobject)


def test_component_is_registered():
    import manim_skill.components.optimization_path  # noqa: F401
    from manim_skill.components import base

    assert "OptimizationPath" in base.all_names()


def test_optimization_path_uses_theme_fonts():
    """Title text must use FONT_DISPLAY (title_text) after theme wiring."""
    from manim_skill.components.optimization_path import (
        OptimizationPath,
        OptimizationPathParams,
    )
    from manim_skill.components.theme import FONT_DISPLAY

    params = OptimizationPathParams(
        expression="x**2",
        x_range=[-2, 2],
        y_range=[0, 4],
        start_x=-1.5,
        min_x=0.0,
        title="Gradient Descent",
    )
    mobj = OptimizationPath().build(params)
    # diagram = VGroup(axes, graph, dot, title)  — title is last submobject
    title = mobj.submobjects[-1]
    assert title.font == FONT_DISPLAY


@pytest.mark.docker
def test_optimization_path_renders_in_docker(tmp_path):
    spec = SceneSpec(
        title="T",
        beats=[
            Beat(
                component="OptimizationPath",
                params={
                    "expression": "0.5 * x**2",
                    "x_range": [-3, 3, 1],
                    "y_range": [0, 5, 1],
                    "start_x": -2.5,
                    "min_x": 0.0,
                    "n_steps": 6,
                    "title": "Gradient descent",
                },
                duration=1.0,
            )
        ],
    )
    mp4 = render_spec_to_mp4(spec, tmp_path, quality="low")
    assert mp4.exists()
    assert mp4.stat().st_size > 20_000
