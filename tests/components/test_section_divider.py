import pytest
from manim import Text, VGroup

from manim_skill.render.docker_render import render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec


def test_section_divider_builds_title_with_display_font():
    from manim_skill.components.section_divider import SectionDivider, SectionDividerParams
    from manim_skill.components.theme import FONT_DISPLAY

    comp = SectionDivider()
    mobj = comp.build(SectionDividerParams(number=1, title="Intro", subtitle="x"))
    assert isinstance(mobj, VGroup)
    texts = [m for m in mobj.get_family() if isinstance(m, Text)]
    assert any("Intro" in t.text and t.font == FONT_DISPLAY for t in texts)


def test_section_divider_is_registered():
    import manim_skill.components.section_divider  # noqa: F401
    from manim_skill.components import base
    assert "SectionDivider" in base.all_names()


@pytest.mark.docker
def test_section_divider_renders_in_docker(tmp_path):
    spec = SceneSpec(title="T", beats=[Beat(component="SectionDivider", params={"number": 1, "title": "Chapter One", "subtitle": "intro"}, duration=1.0)])
    mp4 = render_spec_to_mp4(spec, tmp_path, quality="low")
    assert mp4.exists()
    assert mp4.stat().st_size > 20_000
