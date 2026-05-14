import pytest
from pydantic import ValidationError

from manim_skill.spec.schema import SceneSpec, Beat, CameraDirective


def test_minimal_spec_has_defaults():
    spec = SceneSpec(
        title="T",
        beats=[Beat(component="TextBeat", params={"text": "hi"})],
    )
    assert spec.aspect_ratio == "16:9"
    assert spec.beats[0].component == "TextBeat"
    assert spec.beats[0].params == {"text": "hi"}
    assert spec.beats[0].camera is None


def test_spec_requires_at_least_one_beat():
    with pytest.raises(ValidationError):
        SceneSpec(title="T", beats=[])


def test_raw_beat_carries_code():
    beat = Beat(component="raw", code="self.wait(1)")
    assert beat.code == "self.wait(1)"


def test_camera_directive_on_beat():
    beat = Beat(
        component="raw",
        code="pass",
        camera=CameraDirective(action="zoom", scale=2.0),
    )
    assert beat.camera.action == "zoom"
    assert beat.camera.scale == 2.0


def test_camera_directive_rejects_unknown_action():
    with pytest.raises(ValidationError):
        CameraDirective(action="teleport")
