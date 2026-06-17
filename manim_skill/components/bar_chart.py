from __future__ import annotations

from manim import DL, DOWN, DR, RIGHT, UP, Create, Line, Mobject, Rectangle, Scene, VGroup
from pydantic import BaseModel, Field, model_validator

from manim_skill.components.base import Component, register
from manim_skill.components.theme import THEME, body_text, label_text

_MAX_H = 4.0   # tallest bar, scene units
_BAR_W = 0.9   # bar width, scene units


class BarChartParams(BaseModel):
    values: list[float] = Field(min_length=1)
    labels: list[str] | None = None
    title: str | None = None
    highlight: int | None = None

    @model_validator(mode="after")
    def _check_lengths(self) -> "BarChartParams":
        if self.labels is not None and len(self.labels) != len(self.values):
            raise ValueError("labels must have the same length as values")
        if self.highlight is not None and not (
            0 <= self.highlight < len(self.values)
        ):
            raise ValueError("highlight must be a valid bar index")
        return self


@register
class BarChart(Component):
    name = "BarChart"
    Params = BarChartParams

    def build(self, params: BarChartParams) -> Mobject:
        y_max = max(params.values)
        if y_max <= 0:
            y_max = 1.0

        bars = VGroup()
        for i, value in enumerate(params.values):
            height = max((value / y_max) * _MAX_H, 0.01)
            if params.highlight is None or i == params.highlight:
                color = THEME.PRIMARY
            else:
                color = THEME.PRIMARY_SOFT
            bars.add(
                Rectangle(
                    width=_BAR_W,
                    height=height,
                    fill_color=color,
                    fill_opacity=0.9,
                    stroke_color=color,
                    stroke_width=2,
                )
            )
        bars.arrange(RIGHT, buff=0.4, aligned_edge=DOWN)

        diagram = VGroup(bars)
        diagram.add(
            Line(bars.get_corner(DL), bars.get_corner(DR), color=THEME.RULE)
        )
        if params.labels:
            for bar, name in zip(bars, params.labels):
                diagram.add(label_text(name).next_to(bar, DOWN, buff=0.2))
        if params.title:
            diagram.add(body_text(params.title, size=28).next_to(diagram, UP))
        return diagram

    def animate(self, scene: Scene, mobject: Mobject, params: BarChartParams) -> None:
        scene.play(Create(mobject))
