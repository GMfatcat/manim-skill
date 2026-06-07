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
    blocks.append(
        "### (raw-beat theme names)\n"
        "Available in raw beats: colors PRIMARY, PRIMARY_SOFT, INK, INK_SOFT, "
        "INK_FAINT, WARN, HIGHLIGHT, BG, BG_CARD, BG_CODE, RULE; fonts "
        "FONT_DISPLAY, FONT_BODY, FONT_MONO; factories title_text, body_text, "
        "caption_text, label_text."
    )
    return "\n\n".join(blocks)
