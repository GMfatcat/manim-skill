from manim_skill.skill_docs import (
    generate_skill_docs,
    render_components_doc,
    render_spec_format_doc,
)


def test_components_doc_lists_components():
    doc = render_components_doc()
    assert doc.startswith("# Component Reference")
    assert "TextBeat" in doc
    assert "FormulaBreakdown" in doc


def test_spec_format_doc_has_schema_and_example():
    doc = render_spec_format_doc()
    assert doc.startswith("# Scene Spec Format")
    assert "SceneSpec schema" in doc
    assert "Beat schema" in doc
    assert "## Example" in doc


def test_example_spec_is_valid():
    # The example embedded in the spec-format doc must itself validate.
    from manim_skill.skill_docs import _EXAMPLE_SPEC
    from manim_skill.spec.validate import validate_spec

    validate_spec(_EXAMPLE_SPEC)  # must not raise


def test_generate_skill_docs_writes_reference_files(tmp_path):
    written = generate_skill_docs(tmp_path)
    assert len(written) == 2
    components = tmp_path / "reference" / "components.md"
    spec_format = tmp_path / "reference" / "spec-format.md"
    assert components.exists()
    assert spec_format.exists()
    assert "TextBeat" in components.read_text(encoding="utf-8")


def test_generate_skill_docs_creates_missing_dir(tmp_path):
    target = tmp_path / "nested" / "skill"
    generate_skill_docs(target)
    assert (target / "reference" / "components.md").exists()
