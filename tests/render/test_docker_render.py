import pytest

from manim_skill.render.docker_render import RenderError, render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec


@pytest.mark.docker
def test_render_textbeat_spec_produces_mp4(tmp_path):
    spec = SceneSpec(
        title="T",
        beats=[
            Beat(
                component="TextBeat",
                params={"text": "Hello"},
                duration=1.0,
            )
        ],
    )
    mp4 = render_spec_to_mp4(spec, tmp_path)
    assert mp4.exists()
    assert mp4.stat().st_size > 0


@pytest.mark.docker
def test_render_raw_beat_failure_raises_render_error(tmp_path):
    spec = SceneSpec(
        title="T",
        beats=[Beat(component="raw", code="this is not valid python !!!")],
    )
    with pytest.raises(RenderError):
        render_spec_to_mp4(spec, tmp_path)
