import pytest
from manim import Text

from manim_skill.render.docker_render import render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec


def test_two_column_builds_all_lines():
    from manim_skill.components.two_column import TwoColumn, TwoColumnParams
    comp = TwoColumn()
    mobj = comp.build(TwoColumnParams(left_title="A", right_title="B", left=["a1", "a2"], right=["b1"]))
    texts = [t.text for t in mobj.get_family() if isinstance(t, Text)]
    joined = " ".join(texts)
    for token in ("a1", "a2", "b1"):
        assert token in joined


def test_two_column_is_registered():
    import manim_skill.components.two_column  # noqa: F401
    from manim_skill.components import base
    assert "TwoColumn" in base.all_names()


@pytest.mark.docker
def test_two_column_renders_in_docker(tmp_path):
    spec = SceneSpec(title="T", beats=[Beat(component="TwoColumn", params={"left_title": "AR", "right_title": "dLM", "left": ["sequential", "slow"], "right": ["parallel", "fast"]}, duration=1.0)])
    mp4 = render_spec_to_mp4(spec, tmp_path, quality="low")
    assert mp4.exists()
    assert mp4.stat().st_size > 20_000
