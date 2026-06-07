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


def test_build_caption_short_text_unchanged_width():
    from manim_skill.builder.spec_scene import _build_caption

    caption = _build_caption("short caption")
    assert caption.width <= 13.0


def test_build_caption_long_text_fits_width():
    from manim_skill.builder.spec_scene import _build_caption

    long_text = (
        "Stream width n×C; H^res, H^pre, H^post are learnable — "
        "identity mapping is now broken and we keep expanding the explanation"
    )
    caption = _build_caption(long_text)
    assert caption.width <= 13.0


def test_caption_uses_theme_body_font():
    from manim_skill.builder.spec_scene import _build_caption
    from manim_skill.components.theme import FONT_BODY

    cap = _build_caption("a short caption")
    assert cap.font == FONT_BODY


def test_construct_sets_themed_background(monkeypatch):
    from unittest.mock import patch

    from manim_skill.builder.spec_scene import SpecScene
    from manim_skill.components.theme import THEME
    from manim_skill.spec.validate import validate_spec

    minimal_spec = validate_spec(
        {
            "title": "t",
            "beats": [{"component": "raw", "code": "pass"}],
        }
    )

    scene = SpecScene()
    with patch(
        "manim_skill.builder.spec_scene.load_spec_from_env", return_value=minimal_spec
    ), patch.object(scene, "_render_beat"):
        try:
            scene.construct()
        except Exception:
            pass

    # manim stores background_color as whatever was assigned; compare hex case-insensitively
    assert scene.camera.background_color.upper() == THEME.BG.upper()


def test_render_beat_clamps_oversized_new_mobject(monkeypatch):
    from manim_skill.builder.spec_scene import SpecScene
    from manim_skill.components.layout import FRAME_WIDTH
    from manim_skill.components.theme import MARGIN
    from manim_skill.spec.schema import Beat

    scene = SpecScene()
    monkeypatch.setattr(scene, "play", lambda *a, **k: None)
    monkeypatch.setattr(scene, "wait", lambda *a, **k: None)

    beat = Beat(component="raw", code="self.add(Square(side_length=30))")
    scene._render_beat(beat)

    squares = [m for m in scene.mobjects if m.__class__.__name__ == "Square"]
    assert squares, "square should be on the scene"
    assert squares[0].width <= FRAME_WIDTH - 2 * MARGIN + 1e-6
