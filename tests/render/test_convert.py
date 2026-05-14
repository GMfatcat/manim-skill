import pytest

from manim_skill.render.convert import mp4_to_gif
from manim_skill.render.docker_render import render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec


@pytest.mark.docker
def test_mp4_to_gif_produces_gif(tmp_path):
    spec = SceneSpec(
        title="T",
        beats=[
            Beat(component="TextBeat", params={"text": "Hi"}, duration=1.0)
        ],
    )
    mp4 = render_spec_to_mp4(spec, tmp_path)
    gif = mp4_to_gif(mp4)
    assert gif.exists()
    assert gif.suffix == ".gif"
    assert gif.stat().st_size > 0
