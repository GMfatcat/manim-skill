from __future__ import annotations

from manim import DOWN, Indicate, MathTex, Mobject, Scene, Text, VGroup, Write
from pydantic import BaseModel

from manim_skill.components.base import Component, register


class FormulaBreakdownParams(BaseModel):
    formula: str
    title: str | None = None


@register
class FormulaBreakdown(Component):
    name = "FormulaBreakdown"
    Params = FormulaBreakdownParams

    def build(self, params: FormulaBreakdownParams) -> Mobject:
        formula = MathTex(params.formula)
        group = VGroup(formula)
        if params.title:
            group.add(Text(params.title, font_size=28).next_to(formula, DOWN))
        return group

    def animate(
        self, scene: Scene, mobject: Mobject, params: FormulaBreakdownParams
    ) -> None:
        scene.play(Write(mobject))
        scene.play(Indicate(mobject))
