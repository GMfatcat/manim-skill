from __future__ import annotations

from manim import (
    RIGHT,
    Create,
    Line,
    Mobject,
    Scene,
    SurroundingRectangle,
    VGroup,
)
from pydantic import BaseModel, Field

from manim_skill.components.base import Component, register
from manim_skill.components.theme import THEME, body_text


class AttentionFlowParams(BaseModel):
    tokens: list[str] = Field(min_length=1)
    highlight: str | None = None
    weights: list[float] = Field(default_factory=list)


@register
class AttentionFlow(Component):
    name = "AttentionFlow"
    Params = AttentionFlowParams

    def build(self, params: AttentionFlowParams) -> Mobject:
        boxes = VGroup()
        for token in params.tokens:
            label = body_text(token, size=28)
            box = SurroundingRectangle(label, color=THEME.RULE, buff=0.15)
            boxes.add(VGroup(box, label))
        boxes.arrange(RIGHT, buff=0.5)

        diagram = VGroup(boxes)

        if params.highlight in params.tokens:
            src_idx = params.tokens.index(params.highlight)
            src = boxes[src_idx]
            lines = VGroup()
            for i, target in enumerate(boxes):
                if i == src_idx:
                    continue
                weight = params.weights[i] if i < len(params.weights) else 0.5
                opacity = max(0.1, min(1.0, weight))
                lines.add(
                    Line(
                        src.get_top(),
                        target.get_top(),
                        color=THEME.PRIMARY,
                        stroke_width=3,
                        stroke_opacity=opacity,
                    )
                )
            diagram.add(lines)

        return diagram

    def animate(
        self, scene: Scene, mobject: Mobject, params: AttentionFlowParams
    ) -> None:
        scene.play(Create(mobject))
