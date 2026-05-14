from __future__ import annotations

from typing import Literal

from manim import (
    BLUE,
    GREEN,
    ORANGE,
    RIGHT,
    Create,
    Mobject,
    Rectangle,
    Scene,
    Text,
    VGroup,
)
from pydantic import BaseModel

from manim_skill.components.base import Component, register


def _labeled_box(label: str, color) -> VGroup:
    box = Rectangle(width=1.2, height=1.2, color=color)
    text = Text(label, font_size=32).move_to(box)
    return VGroup(box, text)


class MatrixOpParams(BaseModel):
    op: Literal["matmul", "transpose", "reshape"] = "matmul"
    a_label: str = "A"
    b_label: str | None = None
    result_label: str | None = None


@register
class MatrixOp(Component):
    name = "MatrixOp"
    Params = MatrixOpParams

    def build(self, params: MatrixOpParams) -> Mobject:
        parts: list = [_labeled_box(params.a_label, BLUE)]

        if params.op == "matmul":
            parts.append(Text("x", font_size=40))
            parts.append(_labeled_box(params.b_label or "B", GREEN))
            parts.append(Text("=", font_size=40))
            parts.append(_labeled_box(params.result_label or "C", ORANGE))
        else:
            operator = "T" if params.op == "transpose" else "->"
            suffix = "_T" if params.op == "transpose" else "'"
            default_result = params.a_label + suffix
            parts.append(Text(operator, font_size=40))
            parts.append(
                _labeled_box(params.result_label or default_result, ORANGE)
            )

        row = VGroup(*parts)
        row.arrange(RIGHT, buff=0.4)
        return row

    def animate(
        self, scene: Scene, mobject: Mobject, params: MatrixOpParams
    ) -> None:
        scene.play(Create(mobject))
