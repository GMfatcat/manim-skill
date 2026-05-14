import json
from pathlib import Path

import pytest

from manim_skill.render.convert import mp4_to_gif
from manim_skill.render.docker_render import render_spec_to_mp4
from manim_skill.spec.parse import parse_spec_text
from manim_skill.spec.validate import validate_spec

FIXTURES = Path(__file__).parent / "fixtures" / "specs"


def test_parse_then_validate_noisy_text_fixture():
    # Pure data-layer end-to-end: no docker needed.
    raw_text = (FIXTURES / "text_and_code.txt").read_text(encoding="utf-8")
    data = parse_spec_text(raw_text)
    spec = validate_spec(data)
    assert spec.title == "Plan 1 端到端測試"
    assert [b.component for b in spec.beats] == ["TextBeat", "CodeWalkthrough"]


@pytest.mark.docker
def test_full_pipeline_noisy_text_to_gif(tmp_path):
    raw_text = (FIXTURES / "text_and_code.txt").read_text(encoding="utf-8")
    spec = validate_spec(parse_spec_text(raw_text))
    mp4 = render_spec_to_mp4(spec, tmp_path)
    gif = mp4_to_gif(mp4)
    assert mp4.stat().st_size > 0
    assert gif.stat().st_size > 0


@pytest.mark.docker
def test_full_pipeline_raw_beat_to_mp4(tmp_path):
    data = json.loads(
        (FIXTURES / "with_raw_beat.json").read_text(encoding="utf-8")
    )
    spec = validate_spec(data)
    mp4 = render_spec_to_mp4(spec, tmp_path)
    assert mp4.stat().st_size > 0
