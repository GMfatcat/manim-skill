from __future__ import annotations

from manim import LEFT, RIGHT, UP, FadeIn, Line, Mobject, Scene
from pydantic import BaseModel

from manim_skill.components.base import Component, register
from manim_skill.components.layout import safe_area, stack
from manim_skill.components.theme import THEME, body_text, label_text, title_text


class SectionDividerParams(BaseModel):
    number: int | None = None
    title: str
    subtitle: str | None = None


@register
class SectionDivider(Component):
    name = "SectionDivider"
    Params = SectionDividerParams

    def build(self, params: SectionDividerParams) -> Mobject:
        parts = [Line(LEFT * 3, RIGHT * 3, color=THEME.RULE, stroke_width=1)]
        if params.number is not None:
            parts.append(label_text(f"§ {params.number:02d}", color=THEME.PRIMARY))
        parts.append(title_text(params.title, size=44))
        if params.subtitle:
            parts.append(body_text(params.subtitle, size=24))
        parts.append(Line(LEFT * 3, RIGHT * 3, color=THEME.RULE, stroke_width=1))
        return safe_area(stack(parts, gap=0.35))

    def animate(self, scene: Scene, mobject: Mobject, params: SectionDividerParams) -> None:
        scene.play(FadeIn(mobject, shift=UP * 0.3))
