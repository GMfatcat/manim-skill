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


def test_find_output_mp4_ignores_partial_movie_files(tmp_path):
    from manim_skill.render.docker_render import _find_output_mp4

    final = tmp_path / "videos" / "scene_entry" / "480p15" / "SpecScene.mp4"
    partial = (
        tmp_path
        / "videos"
        / "scene_entry"
        / "480p15"
        / "partial_movie_files"
        / "SpecScene"
        / "abc123.mp4"
    )
    final.parent.mkdir(parents=True, exist_ok=True)
    partial.parent.mkdir(parents=True, exist_ok=True)
    final.write_bytes(b"final")
    partial.write_bytes(b"partial")

    assert _find_output_mp4(tmp_path) == final


def test_find_output_mp4_returns_none_when_empty(tmp_path):
    from manim_skill.render.docker_render import _find_output_mp4

    assert _find_output_mp4(tmp_path) is None


def test_sandbox_hardening_constants_defined():
    from manim_skill.render import docker_render

    assert docker_render.MEMORY_LIMIT
    assert docker_render.CPU_LIMIT
    assert docker_render.PIDS_LIMIT
