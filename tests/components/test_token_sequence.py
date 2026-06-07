import pytest
from manim import VGroup

from manim_skill.render.docker_render import render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec


def test_token_sequence_builds_one_box_per_token():
    from manim_skill.components.token_sequence import TokenSequence, TokenSequenceParams
    comp = TokenSequence()
    mobj = comp.build(TokenSequenceParams(tokens=[{"text": "the", "state": "normal"}, {"text": "?", "state": "masked"}, {"text": "cat", "state": "delete"}]))
    assert isinstance(mobj, VGroup)
    assert len(mobj) == 3


def test_token_sequence_is_registered():
    import manim_skill.components.token_sequence  # noqa: F401
    from manim_skill.components import base
    assert "TokenSequence" in base.all_names()


@pytest.mark.docker
def test_token_sequence_renders_in_docker(tmp_path):
    spec = SceneSpec(title="T", beats=[Beat(component="TokenSequence", params={"tokens": [{"text": "the", "state": "normal"}, {"text": "?", "state": "masked"}, {"text": "new", "state": "expand"}, {"text": "cat", "state": "delete"}]}, duration=1.0)])
    mp4 = render_spec_to_mp4(spec, tmp_path, quality="low")
    assert mp4.exists()
    assert mp4.stat().st_size > 20_000
