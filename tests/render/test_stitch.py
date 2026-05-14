import pytest

from manim_skill.render.docker_render import RenderError, render_spec_to_mp4
from manim_skill.render.stitch import stitch_mp4s
from manim_skill.spec.schema import Beat, SceneSpec


def test_stitch_empty_list_raises():
    with pytest.raises(RenderError):
        stitch_mp4s([], "out.mp4")


@pytest.mark.docker
def test_stitch_two_beat_mp4s(tmp_path):
    import shutil

    workdir = tmp_path / "clip"
    workdir.mkdir()
    beat_mp4s = []
    for i, code in enumerate(["self.wait(1)", "self.wait(1)"]):
        spec = SceneSpec(
            title="T", beats=[Beat(component="raw", code=code)]
        )
        rendered = render_spec_to_mp4(spec, tmp_path / f"beat_{i}")
        dest = workdir / f"beat_{i:02d}.mp4"
        shutil.copy2(rendered, dest)
        beat_mp4s.append(dest)

    clip_mp4 = stitch_mp4s(beat_mp4s, workdir / "clip.mp4")
    assert clip_mp4.exists()
    assert clip_mp4.stat().st_size > 0


@pytest.mark.docker
def test_stitch_single_mp4(tmp_path):
    import shutil

    workdir = tmp_path / "clip"
    workdir.mkdir()
    spec = SceneSpec(
        title="T", beats=[Beat(component="raw", code="self.wait(1)")]
    )
    rendered = render_spec_to_mp4(spec, tmp_path / "beat")
    dest = workdir / "beat_00.mp4"
    shutil.copy2(rendered, dest)

    clip_mp4 = stitch_mp4s([dest], workdir / "clip.mp4")
    assert clip_mp4.exists()
    assert clip_mp4.stat().st_size > 0
