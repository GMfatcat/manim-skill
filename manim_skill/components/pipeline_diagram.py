from __future__ import annotations

from manim import (
    RIGHT,
    UP,
    Arrow,
    Create,
    Mobject,
    RoundedRectangle,
    Scene,
    VGroup,
)
from pydantic import BaseModel, Field

from manim_skill.components.base import Component, register
from manim_skill.components.theme import THEME, body_text, label_text


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
            lbl = label_text(stage, size=24)
            box = RoundedRectangle(
                corner_radius=0.15,
                width=max(1.5, lbl.width + 0.4),
                height=1.0,
                color=THEME.PRIMARY,
            )
            lbl.move_to(box)
            boxes.add(VGroup(box, lbl))
        boxes.arrange(RIGHT, buff=1.0)

        arrows = VGroup()
        for left, right in zip(boxes[:-1], boxes[1:]):
            arrows.add(Arrow(left.get_right(), right.get_left(), buff=0.1))

        diagram = VGroup(boxes, arrows)
        if params.title:
            diagram.add(
                body_text(params.title, size=28).next_to(diagram, UP)
            )
        # Auto-fit to camera width (16:9 frame is 14.22 units; target safe 12.0).
        if diagram.width > 12.0:
            diagram.scale_to_fit_width(12.0)
        return diagram

    def animate(
        self, scene: Scene, mobject: Mobject, params: PipelineDiagramParams
    ) -> None:
        scene.play(Create(mobject))
