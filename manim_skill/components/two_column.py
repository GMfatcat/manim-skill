from __future__ import annotations

from manim import DOWN, RIGHT, UP, FadeIn, Line, Mobject, Scene, VGroup
from pydantic import BaseModel, Field

from manim_skill.components.base import Component, register
from manim_skill.components.layout import safe_area, stack
from manim_skill.components.theme import THEME, body_text, title_text


class TwoColumnParams(BaseModel):
    left_title: str | None = None
    right_title: str | None = None
    left: list[str] = Field(default_factory=list)
    right: list[str] = Field(default_factory=list)


def _column(title: str | None, lines: list[str]) -> Mobject:
    parts = []
    if title:
        parts.append(title_text(title, size=30))
    for line in lines:
        parts.append(body_text(line, size=24))
    return stack(parts, gap=0.3) if parts else VGroup()


@register
class TwoColumn(Component):
    name = "TwoColumn"
    Params = TwoColumnParams

    def build(self, params: TwoColumnParams) -> Mobject:
        left_col = _column(params.left_title, params.left)
        right_col = _column(params.right_title, params.right)
        divider = Line(UP * 2, DOWN * 2, color=THEME.RULE, stroke_width=1)
        group = VGroup(left_col, divider, right_col).arrange(RIGHT, buff=0.8)
        return safe_area(group)

    def animate(self, scene: Scene, mobject: Mobject, params: TwoColumnParams) -> None:
        scene.play(FadeIn(mobject))
