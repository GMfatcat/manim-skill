import json

import pytest
from manim import MovingCameraScene

from manim_skill.builder.spec_scene import (
    SPEC_ENV_VAR,
    SpecScene,
    load_spec_from_env,
)


def test_spec_scene_is_moving_camera_scene():
    assert issubclass(SpecScene, MovingCameraScene)


def test_load_spec_from_env_reads_and_validates(tmp_path, monkeypatch):
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(
        json.dumps(
            {
                "title": "T",
                "beats": [{"component": "raw", "code": "self.wait(1)"}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(SPEC_ENV_VAR, str(spec_file))

    spec = load_spec_from_env()
    assert spec.title == "T"
    assert spec.beats[0].component == "raw"


def test_load_spec_from_env_missing_var_raises(monkeypatch):
    monkeypatch.delenv(SPEC_ENV_VAR, raising=False)
    with pytest.raises(RuntimeError):
        load_spec_from_env()
