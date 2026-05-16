"""CJK rendering smoke test.

The docker image must carry a CJK-capable font (Noto CJK) or every
Chinese codepoint comes out as a tofu box. This test renders a spec
containing CJK text and asserts a non-trivial mp4 came out — drift
gets caught at CI time, not after a slide presentation.
"""

from pathlib import Path

import pytest

from manim_skill.render.docker_render import render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec


@pytest.mark.docker
def test_render_cjk_text_in_textbeat_produces_mp4(tmp_path):
    spec = SceneSpec(
        title="CJK smoke",
        beats=[
            Beat(
                component="TextBeat",
                params={
                    "text": "中文字渲染",
                    "subtitle": "繁體 / 簡體 / 中英 Hybrid",
                    "style": "title",
                },
                duration=1.0,
            )
        ],
    )
    mp4 = render_spec_to_mp4(spec, tmp_path, quality="low")
    assert mp4.exists()
    # A tofu-box render would still produce an mp4, but it would be
    # tiny — Pango falls back to an empty glyph. Real CJK glyphs add
    # bytes. The MHA TextBeat at low/15fps lands around 30 KB; an
    # all-tofu render is typically <10 KB. Pick a conservative floor.
    assert mp4.stat().st_size > 20_000, (
        "rendered mp4 is suspiciously small — CJK font may be missing"
    )


@pytest.mark.docker
def test_render_cjk_in_pipeline_diagram(tmp_path):
    spec = SceneSpec(
        title="CJK pipeline",
        beats=[
            Beat(
                component="PipelineDiagram",
                params={
                    "stages": ["輸入", "編碼", "注意力", "解碼", "輸出"],
                    "title": "中文流程",
                },
                duration=1.0,
            )
        ],
    )
    mp4 = render_spec_to_mp4(spec, tmp_path, quality="low")
    assert mp4.exists()
    assert mp4.stat().st_size > 20_000
