from __future__ import annotations

import json
from pathlib import Path

from manim_skill.llm.catalog import build_component_catalog
from manim_skill.spec.schema import Beat, SceneSpec

_EXAMPLE_SPEC: dict = {
    "title": "Self-Attention",
    "aspect_ratio": "16:9",
    "beats": [
        {
            "component": "TextBeat",
            "params": {"text": "Self-Attention", "style": "title"},
            "caption": "Intro",
            "duration": 2.0,
        },
        {
            "component": "raw",
            "code": "c = Circle()\nself.play(Create(c))",
            "duration": 3.0,
        },
    ],
}


def render_components_doc() -> str:
    """The component reference: every component's params schema.

    Reuses build_component_catalog() so this never drifts from the code.
    """
    return (
        "# Component Reference\n\n"
        "Each component below can be used as a beat's `component` in a "
        "scene spec. A beat's `params` must match the component's "
        "params schema.\n\n"
        + build_component_catalog()
        + "\n"
    )


def render_spec_format_doc() -> str:
    """The scene spec format reference: schema + a worked example."""
    scene_schema = json.dumps(
        SceneSpec.model_json_schema(), ensure_ascii=False, indent=2
    )
    beat_schema = json.dumps(
        Beat.model_json_schema(), ensure_ascii=False, indent=2
    )
    example = json.dumps(_EXAMPLE_SPEC, ensure_ascii=False, indent=2)
    return (
        "# Scene Spec Format\n\n"
        "A scene spec is a JSON object describing one animation clip. "
        "It has a `title`, an optional `aspect_ratio` (default "
        "`16:9`), and a non-empty list of `beats`. Each beat names a "
        "`component` (see the component reference) or `raw` with a "
        "`code` field of manim Python where the scene is `self`.\n\n"
        "## SceneSpec schema\n\n```json\n" + scene_schema + "\n```\n\n"
        "## Beat schema\n\n```json\n" + beat_schema + "\n```\n\n"
        "## Example\n\n```json\n" + example + "\n```\n"
    )


def generate_skill_docs(skill_dir) -> list[Path]:
    """Write the auto-generated reference docs under <skill_dir>/reference/.

    Returns the list of written file paths. SKILL.md itself is
    hand-written and is not touched here.
    """
    reference_dir = Path(skill_dir) / "reference"
    reference_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, content in (
        ("components.md", render_components_doc()),
        ("spec-format.md", render_spec_format_doc()),
    ):
        path = reference_dir / name
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written
