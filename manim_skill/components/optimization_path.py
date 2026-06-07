from __future__ import annotations

from manim import (
    DOWN,
    Axes,
    Create,
    Dot,
    FadeIn,
    Mobject,
    Scene,
    TracedPath,
    VGroup,
)
from pydantic import BaseModel, Field, model_validator

from manim_skill.components.base import Component, register
from manim_skill.components.function_plot import _compile_expression
from manim_skill.components.theme import THEME, title_text, label_text

_MAX_DIAGRAM_WIDTH = 12.0


class OptimizationPathParams(BaseModel):
    expression: str
    x_range: list[float] = Field(min_length=2, max_length=3)
    y_range: list[float] = Field(min_length=2, max_length=3)
    start_x: float
    min_x: float
    n_steps: int = Field(default=8, ge=1)
    x_label: str | None = None
    y_label: str | None = None
    title: str | None = None

    @model_validator(mode="after")
    def _start_and_min_in_range(self):
        x_lo, x_hi = self.x_range[0], self.x_range[1]
        if not (x_lo <= self.start_x <= x_hi):
            raise ValueError(
                f"start_x {self.start_x} outside x_range [{x_lo}, {x_hi}]"
            )
        if not (x_lo <= self.min_x <= x_hi):
            raise ValueError(
                f"min_x {self.min_x} outside x_range [{x_lo}, {x_hi}]"
            )
        return self


def _resolve_range(r: list[float]) -> list[float]:
    if len(r) == 2:
        return [r[0], r[1], (r[1] - r[0]) / 5.0]
    return list(r)


@register
class OptimizationPath(Component):
    name = "OptimizationPath"
    Params = OptimizationPathParams

    def build(self, params: OptimizationPathParams) -> Mobject:
        fn = _compile_expression(params.expression)

        axes = Axes(
            x_range=_resolve_range(params.x_range),
            y_range=_resolve_range(params.y_range),
            x_length=8.0,
            y_length=4.5,
            tips=False,
        )
        graph = axes.plot(fn, color=THEME.PRIMARY)

        start_point = axes.c2p(params.start_x, fn(params.start_x))
        dot = Dot(point=start_point, color=THEME.WARN, radius=0.1)

        diagram = VGroup(axes, graph, dot)
        if params.x_label:
            x_lbl = label_text(params.x_label, size=22)
            x_lbl.next_to(axes.x_axis.get_end(), DOWN, buff=0.2)
            diagram.add(x_lbl)
        if params.y_label:
            y_lbl = label_text(params.y_label, size=22)
            y_lbl.next_to(axes.y_axis.get_end(), DOWN, buff=0.2)
            diagram.add(y_lbl)
        if params.title:
            diagram.add(
                title_text(params.title, size=28).next_to(axes, DOWN, buff=0.4)
            )

        if diagram.width > _MAX_DIAGRAM_WIDTH:
            diagram.scale_to_fit_width(_MAX_DIAGRAM_WIDTH)

        # Stash data we need at animate-time on the returned VGroup.
        # build/animate are split, so we can't recompute fn there.
        diagram._opt_axes = axes  # type: ignore[attr-defined]
        diagram._opt_dot = dot  # type: ignore[attr-defined]
        diagram._opt_fn = fn  # type: ignore[attr-defined]
        diagram._opt_params = params  # type: ignore[attr-defined]
        return diagram

    def animate(
        self, scene: Scene, mobject: Mobject, params: OptimizationPathParams
    ) -> None:
        axes = mobject._opt_axes  # type: ignore[attr-defined]
        dot = mobject._opt_dot  # type: ignore[attr-defined]
        fn = mobject._opt_fn  # type: ignore[attr-defined]

        scene.play(Create(mobject))

        # TracedPath leaves a yellow trail behind the dot as it walks
        # toward the minimum.
        trace = TracedPath(dot.get_center, stroke_color=THEME.HIGHLIGHT, stroke_width=4)
        scene.add(trace)

        for i in range(1, params.n_steps + 1):
            t = i / params.n_steps
            x = params.start_x + (params.min_x - params.start_x) * t
            target = axes.c2p(x, fn(x))
            scene.play(dot.animate.move_to(target), run_time=0.3)
