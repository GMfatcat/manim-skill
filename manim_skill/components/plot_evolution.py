from __future__ import annotations

from manim import BLUE, UP, Axes, Create, Mobject, Scene, Text, VGroup
from pydantic import BaseModel, Field

from manim_skill.components.base import Component, register


class PlotEvolutionParams(BaseModel):
    series: list[float] = Field(min_length=2)
    title: str | None = None


@register
class PlotEvolution(Component):
    name = "PlotEvolution"
    Params = PlotEvolutionParams

    def build(self, params: PlotEvolutionParams) -> Mobject:
        n = len(params.series)
        y_min = min(params.series)
        y_max = max(params.series)
        if y_min == y_max:
            y_min, y_max = y_min - 1.0, y_max + 1.0

        axes = Axes(
            x_range=[0, n - 1, max(1, (n - 1) // 5)],
            y_range=[y_min, y_max, (y_max - y_min) / 5],
            x_length=8,
            y_length=4.5,
        )
        graph = axes.plot_line_graph(
            x_values=list(range(n)),
            y_values=params.series,
            line_color=BLUE,
            add_vertex_dots=True,
        )

        diagram = VGroup(axes, graph)
        if params.title:
            diagram.add(Text(params.title, font_size=28).next_to(axes, UP))
        return diagram

    def animate(
        self, scene: Scene, mobject: Mobject, params: PlotEvolutionParams
    ) -> None:
        scene.play(Create(mobject))
