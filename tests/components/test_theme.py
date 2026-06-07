from manim import Text

from manim_skill.components.theme import (
    DLM_WARM,
    FONT_BODY,
    FONT_DISPLAY,
    FONT_MONO,
    NEUTRAL,
    Theme,
    body_text,
    caption_text,
    get_theme,
    label_text,
    title_text,
)


def test_presets_share_the_same_token_set():
    assert set(vars(NEUTRAL)) == set(vars(DLM_WARM))


def test_every_token_is_a_hex_color():
    for theme in (NEUTRAL, DLM_WARM):
        for value in vars(theme).values():
            assert isinstance(value, str) and value.startswith("#")


def test_get_theme_resolves_names_and_falls_back_to_neutral():
    assert get_theme("dlm_warm") is DLM_WARM
    assert get_theme("DLM_WARM") is DLM_WARM
    assert get_theme("neutral") is NEUTRAL
    assert get_theme("nonsense") is NEUTRAL
    assert get_theme(None) is NEUTRAL


def test_title_text_uses_display_font_at_floor_size():
    t = title_text("Hi")
    assert isinstance(t, Text)
    assert t.font == FONT_DISPLAY
    assert t.font_size == 48


def test_body_and_caption_use_body_font_and_are_not_italic():
    for factory, font, size in (
        (body_text, FONT_BODY, 28),
        (caption_text, FONT_BODY, 22),
    ):
        t = factory("hello")
        assert t.font == font
        assert t.font_size == size
        assert getattr(t, "slant", "NORMAL") == "NORMAL"


def test_label_text_uses_mono_font():
    t = label_text("x")
    assert t.font == FONT_MONO
    assert t.font_size == 18


def test_color_override_is_honored():
    t = title_text("Hi", color="#123456")
    # manim 0.20: color propagates to submobjects (glyphs), not to Text itself
    assert t[0].color.to_hex().lower() == "#123456"


def test_theme_is_frozen():
    import dataclasses
    import pytest

    with pytest.raises(dataclasses.FrozenInstanceError):
        NEUTRAL.BG = "#000000"
