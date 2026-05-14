from __future__ import annotations

from manim import (
    BLUE,
    RIGHT,
    UP,
    Arrow,
    Create,
    Mobject,
    RoundedRectangle,
    Scene,
    Text,
    VGroup,
)
from pydantic import BaseModel, Field

from manim_skill.components.base import Component, register


class PipelineDiagramParams(BaseModel):
    stages: list[str] = Field(min_length=1)
    title: str | None = None


@register
class PipelineDiagram(Component):
    name = "PipelineDiagram"
    Params = PipelineDiagramParams

    def build(self, params: PipelineDiagramParams) -> Mobject:
        boxes = VGroup()
        for stage in params.stages:
            label = Text(stage, font_size=24)
            box = RoundedRectangle(
                corner_radius=0.15,
                width=max(1.5, label.width + 0.4),
                height=1.0,
                color=BLUE,
            )
            label.move_to(box)
            boxes.add(VGroup(box, label))
        boxes.arrange(RIGHT, buff=1.0)

        arrows = VGroup()
        for left, right in zip(boxes[:-1], boxes[1:]):
            arrows.add(Arrow(left.get_right(), right.get_left(), buff=0.1))

        diagram = VGroup(boxes, arrows)
        if params.title:
            diagram.add(
                Text(params.title, font_size=28).next_to(diagram, UP)
            )
        return diagram

    def animate(
        self, scene: Scene, mobject: Mobject, params: PipelineDiagramParams
    ) -> None:
        scene.play(Create(mobject))
