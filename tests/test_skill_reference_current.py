from pathlib import Path

from manim_skill.skill_docs import render_components_doc, render_spec_format_doc

_SKILL_REF = Path(__file__).resolve().parent.parent / "skill" / "reference"


def test_committed_components_doc_is_current():
    committed = (_SKILL_REF / "components.md").read_text(encoding="utf-8")
    assert committed == render_components_doc(), (
        "skill/reference/components.md is stale — "
        "run `manim-skill gen-skill-docs`"
    )


def test_committed_spec_format_doc_is_current():
    committed = (_SKILL_REF / "spec-format.md").read_text(encoding="utf-8")
    assert committed == render_spec_format_doc(), (
        "skill/reference/spec-format.md is stale — "
        "run `manim-skill gen-skill-docs`"
    )
