from __future__ import annotations

from pathlib import Path

from manim_skill.spec.schema import SceneSpec

_ENTRY_SOURCE = (
    "from manim_skill.builder.spec_scene import SpecScene\n"
    "\n"
    "__all__ = ['SpecScene']\n"
)


def write_render_inputs(spec: SceneSpec, workdir) -> tuple[Path, Path]:
    """Write the two files manim needs to render a spec.

    Returns (spec_path, entry_path). The entry file is what `manim`
    is pointed at; it imports SpecScene, which reads spec.json via
    the MANIM_SKILL_SPEC environment variable at render time.
    """
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    spec_path = workdir / "spec.json"
    spec_path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")

    entry_path = workdir / "scene_entry.py"
    entry_path.write_text(_ENTRY_SOURCE, encoding="utf-8")

    return spec_path, entry_path
