import pytest
from pydantic import ValidationError

from manim_skill.render.docker_render import render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec


def test_params_requires_formula():
    from manim_skill.components.formula_breakdown import FormulaBreakdownParams

    with pytest.raises(ValidationError):
        FormulaBreakdownParams()


def test_params_title_optional():
    from manim_skill.components.formula_breakdown import FormulaBreakdownParams

    params = FormulaBreakdownParams(formula="x^2 + y^2 = z^2")
    assert params.title is None


def test_component_is_registered():
    # Importing the module triggers @register; no LaTeX needed for this.
    import manim_skill.components.formula_breakdown  # noqa: F401
    from manim_skill.components import base

    assert "FormulaBreakdown" in base.all_names()


@pytest.mark.docker
def test_formula_breakdown_renders_in_docker(tmp_path):
    # build()/animate() use MathTex (LaTeX); verified inside the docker
    # image, which has a TeX distribution. Requires the image to be
    # rebuilt with this component present (see Step 5).
    spec = SceneSpec(
        title="T",
        beats=[
            Beat(
                component="FormulaBreakdown",
                params={"formula": "e^{i\\pi} + 1 = 0", "title": "Euler"},
                duration=1.0,
            )
        ],
    )
    mp4 = render_spec_to_mp4(spec, tmp_path)
    assert mp4.exists()
    assert mp4.stat().st_size > 0
