from __future__ import annotations

from typing import Literal

from manim import (
    BLUE,
    DOWN,
    PI,
    Circle,
    Create,
    Mobject,
    RegularPolygon,
    Rotate,
    Scene,
    Square,
    Text,
    Triangle,
    VGroup,
)
from pydantic import BaseModel

from manim_skill.components.base import Component, register

_SHAPES = {
    "circle": lambda: Circle(radius=1.0, color=BLUE),
    "square": lambda: Square(side_length=2.0, color=BLUE),
    "triangle": lambda: Triangle(color=BLUE).scale(1.2),
    "polygon": lambda: RegularPolygon(n=6, color=BLUE).scale(1.2),
}


class GeometryAnimParams(BaseModel):
    shape: Literal["circle", "square", "triangle", "polygon"] = "circle"
    transform: Literal["rotate", "scale", "none"] = "none"
    label: str | None = None


@register
class GeometryAnim(Component):
    name = "GeometryAnim"
    Params = GeometryAnimParams

    def build(self, params: GeometryAnimParams) -> Mobject:
        shape = _SHAPES[params.shape]()
        group = VGroup(shape)
        if params.label:
            group.add(Text(params.label, font_size=28).next_to(shape, DOWN))
        return group

    def animate(
        self, scene: Scene, mobject: Mobject, params: GeometryAnimParams
    ) -> None:
        scene.play(Create(mobject))
        if params.transform == "rotate":
            scene.play(Rotate(mobject, angle=PI / 2))
        elif params.transform == "scale":
            scene.play(mobject.animate.scale(1.5))
