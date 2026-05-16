import subprocess
from types import SimpleNamespace

import pytest

from manim_skill.render import docker_render as docker_render_mod
from manim_skill.render.docker_render import RenderError, render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec


_TRIVIAL_SPEC = SceneSpec(
    title="T",
    beats=[Beat(component="TextBeat", params={"text": "x"}, duration=0.5)],
)


def _fake_cmd_capture(monkeypatch, tmp_path):
    """Patch subprocess.run + _find_output_mp4 so render_spec_to_mp4 runs
    without docker. Return a list that will hold the captured docker cmd."""
    captured: list[list[str]] = []
    fake_mp4 = tmp_path / "_fake_out.mp4"
    fake_mp4.write_bytes(b"fake")

    def fake_run(cmd, **kwargs):
        captured.append(list(cmd))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(docker_render_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(
        docker_render_mod, "_find_output_mp4", lambda _: fake_mp4
    )
    return captured


def test_render_quality_defaults_to_medium(tmp_path, monkeypatch):
    captured = _fake_cmd_capture(monkeypatch, tmp_path)
    render_spec_to_mp4(_TRIVIAL_SPEC, tmp_path)
    assert "-qm" in captured[0]


@pytest.mark.parametrize(
    "quality, expected_flag",
    [
        ("low", "-ql"),
        ("medium", "-qm"),
        ("high", "-qh"),
        ("production", "-qp"),
        ("fourk", "-qk"),
    ],
)
def test_render_quality_maps_to_manim_flag(
    quality, expected_flag, tmp_path, monkeypatch
):
    captured = _fake_cmd_capture(monkeypatch, tmp_path)
    render_spec_to_mp4(_TRIVIAL_SPEC, tmp_path, quality=quality)
    assert expected_flag in captured[0]


def test_render_quality_unknown_raises(tmp_path, monkeypatch):
    _fake_cmd_capture(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="quality"):
        render_spec_to_mp4(_TRIVIAL_SPEC, tmp_path, quality="ultra")


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
