from __future__ import annotations

from manim import DOWN, Indicate, MathTex, Mobject, Scene, VGroup, Write
from pydantic import BaseModel

from manim_skill.components.base import Component, register
from manim_skill.components.theme import THEME, body_text
from manim_skill.spec.latex import repair_latex


class FormulaBreakdownParams(BaseModel):
    formula: str
    title: str | None = None


@register
class FormulaBreakdown(Component):
    name = "FormulaBreakdown"
    Params = FormulaBreakdownParams

    def build(self, params: FormulaBreakdownParams) -> Mobject:
        formula = MathTex(repair_latex(params.formula), color=THEME.INK)
        group = VGroup(formula)
        if params.title:
            group.add(body_text(params.title, size=28).next_to(formula, DOWN))
        return group

    def animate(
        self, scene: Scene, mobject: Mobject, params: FormulaBreakdownParams
    ) -> None:
        scene.play(Write(mobject))
        scene.play(Indicate(mobject))
