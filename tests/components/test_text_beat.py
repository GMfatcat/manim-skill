from manim import Text, VGroup

from manim_skill.components.text_beat import TextBeat, TextBeatParams


def test_title_style_builds_header_text():
    comp = TextBeat()
    mobj = comp.build(TextBeatParams(text="Hello", style="title"))
    assert isinstance(mobj, VGroup)
    texts = [m for m in mobj if isinstance(m, Text)]
    assert any("Hello" in t.text for t in texts)


def test_title_with_subtitle_has_two_texts():
    comp = TextBeat()
    mobj = comp.build(
        TextBeatParams(text="Hello", subtitle="world", style="title")
    )
    texts = [m for m in mobj if isinstance(m, Text)]
    assert len(texts) == 2


def test_bullets_style_builds_header_plus_one_per_bullet():
    comp = TextBeat()
    mobj = comp.build(
        TextBeatParams(text="Topics", style="bullets", bullets=["a", "b", "c"])
    )
    texts = [m for m in mobj if isinstance(m, Text)]
    assert len(texts) == 4  # header + 3 bullets


def test_textbeat_uses_theme_display_font():
    from manim_skill.components.theme import FONT_DISPLAY
    comp = TextBeat()
    mobj = comp.build(TextBeatParams(text="Hello", style="title"))
    texts = [m for m in mobj if isinstance(m, Text)]
    assert texts and all(t.font == FONT_DISPLAY for t in texts)
