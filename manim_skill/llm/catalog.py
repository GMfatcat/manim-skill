from __future__ import annotations

import json

from manim_skill.components import base as registry


def build_component_catalog() -> str:
    """Render the registered components as a text catalog for an LLM prompt.

    Each component's params schema comes straight from its Pydantic
    `Params` model — the single source of truth — so the catalog never
    drifts from the actual code.
    """
    blocks: list[str] = []
    for name in registry.all_names():
        component = registry.get(name)
        schema = component.Params.model_json_schema()
        blocks.append(
            f"### {name}\n"
            + json.dumps(schema, ensure_ascii=False, indent=2)
        )
    return "\n\n".join(blocks)
