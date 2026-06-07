import pytest
from pydantic import ValidationError

from manim_skill.render.docker_render import render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec


_SEGMENTS = [
    "\\frac{",
    "Q K^T",
    "}{",
    "\\sqrt{d_k}",
    "}",
]


def test_params_requires_segments():
    from manim_skill.components.formula_walkthrough import (
        FormulaWalkthroughParams,
    )

    with pytest.raises(ValidationError):
        FormulaWalkthroughParams()


def test_params_empty_segments_rejected():
    from manim_skill.components.formula_walkthrough import (
        FormulaWalkthroughParams,
    )

    with pytest.raises(ValidationError):
        FormulaWalkthroughParams(segments=[])


def test_params_title_optional():
    from manim_skill.components.formula_walkthrough import (
        FormulaWalkthroughParams,
    )

    params = FormulaWalkthroughParams(segments=_SEGMENTS)
    assert params.title is None
    assert params.steps == []


def test_step_negative_index_rejected():
    from manim_skill.components.formula_walkthrough import FormulaStep

    with pytest.raises(ValidationError):
        FormulaStep(indices=[-1], caption="x")


def test_step_empty_indices_rejected():
    from manim_skill.components.formula_walkthrough import FormulaStep

    with pytest.raises(ValidationError):
        FormulaStep(indices=[], caption="x")


def test_step_index_out_of_range_rejected_at_params_validation():
    from manim_skill.components.formula_walkthrough import (
        FormulaStep,
        FormulaWalkthroughParams,
    )

    with pytest.raises(ValidationError):
        FormulaWalkthroughParams(
            segments=_SEGMENTS,
            steps=[FormulaStep(indices=[99], caption="bad")],
        )


def test_step_index_in_range_accepted():
    from manim_skill.components.formula_walkthrough import (
        FormulaStep,
        FormulaWalkthroughParams,
    )

    params = FormulaWalkthroughParams(
        segments=_SEGMENTS,
        steps=[
            FormulaStep(indices=[1], caption="dot product"),
            FormulaStep(indices=[3], caption="scale by sqrt(d_k)"),
        ],
    )
    assert len(params.steps) == 2


def test_component_is_registered():
    import manim_skill.components.formula_walkthrough  # noqa: F401
    from manim_skill.components import base

    assert "FormulaWalkthrough" in base.all_names()


def test_theme_font_wired():
    from unittest.mock import patch

    from manim import Dot

    from manim_skill.components.formula_walkthrough import (
        FormulaWalkthrough,
        FormulaWalkthroughParams,
    )
    from manim_skill.components.theme import FONT_BODY

    with patch(
        "manim_skill.components.formula_walkthrough.MathTex", return_value=Dot()
    ):
        comp = FormulaWalkthrough()
        mobj = comp.build(
            FormulaWalkthroughParams(segments=["x"], title="Attention Score")
        )

    # VGroup: [formula, title_text]; title_text is index 1
    title_obj = mobj.submobjects[1]
    assert title_obj.font == FONT_BODY


@pytest.mark.docker
def test_formula_walkthrough_renders_in_docker(tmp_path):
    spec = SceneSpec(
        title="T",
        beats=[
            Beat(
                component="FormulaWalkthrough",
                params={
                    "segments": _SEGMENTS,
                    "title": "Scaled attention scores",
                    "steps": [
                        {"indices": [1], "caption": "dot product"},
                        {"indices": [3], "caption": "scale by sqrt(d_k)"},
                    ],
                },
                duration=1.0,
            )
        ],
    )
    mp4 = render_spec_to_mp4(spec, tmp_path, quality="low")
    assert mp4.exists()
    assert mp4.stat().st_size > 0
