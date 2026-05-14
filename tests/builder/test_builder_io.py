import json

from manim_skill.builder import write_render_inputs
from manim_skill.spec.schema import Beat, SceneSpec


def test_write_render_inputs_creates_both_files(tmp_path):
    spec = SceneSpec(title="T", beats=[Beat(component="raw", code="pass")])
    spec_path, entry_path = write_render_inputs(spec, tmp_path)

    assert spec_path.exists()
    assert entry_path.exists()


def test_written_spec_json_roundtrips(tmp_path):
    spec = SceneSpec(title="My Title", beats=[Beat(component="raw", code="pass")])
    spec_path, _ = write_render_inputs(spec, tmp_path)

    loaded = json.loads(spec_path.read_text(encoding="utf-8"))
    assert loaded["title"] == "My Title"
    assert loaded["beats"][0]["component"] == "raw"


def test_entry_file_references_specscene(tmp_path):
    spec = SceneSpec(title="T", beats=[Beat(component="raw", code="pass")])
    _, entry_path = write_render_inputs(spec, tmp_path)

    content = entry_path.read_text(encoding="utf-8")
    assert "SpecScene" in content


def test_write_creates_missing_workdir(tmp_path):
    target = tmp_path / "nested" / "workdir"
    spec = SceneSpec(title="T", beats=[Beat(component="raw", code="pass")])
    spec_path, _ = write_render_inputs(spec, target)
    assert spec_path.parent == target
