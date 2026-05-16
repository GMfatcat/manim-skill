from __future__ import annotations

import math
from typing import Callable

from manim import (
    BLUE,
    DOWN,
    LEFT,
    UP,
    Axes,
    Create,
    Mobject,
    Scene,
    Text,
    VGroup,
)
from pydantic import BaseModel, Field

from manim_skill.components.base import Component, register

_MAX_DIAGRAM_WIDTH = 12.0


class FunctionPlotParams(BaseModel):
    expression: str
    x_range: list[float] = Field(default_factory=lambda: [-5.0, 5.0, 1.0], min_length=2, max_length=3)
    y_range: list[float] = Field(default_factory=lambda: [-2.0, 2.0, 1.0], min_length=2, max_length=3)
    x_label: str | None = None
    y_label: str | None = None
    title: str | None = None


# Restrict the eval namespace to picklable built-ins + a curated list of
# `math` functions. Putting `numpy` (or even just `math` as a module) in
# the closure makes manim's plot-caching serializer trip over cyfunctions
# (TypeError: <cyfunction RandomState.beta> is not a Python function),
# silently failing the whole beat. Individual builtin_function_or_method
# references from `math` serialize cleanly.
_SAFE_NAMES: dict = {
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
}
for _name in (
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "sinh", "cosh", "tanh",
    "exp", "log", "log2", "log10", "sqrt",
    "pi", "e", "tau", "inf",
    "floor", "ceil", "trunc",
):
    if hasattr(math, _name):
        _SAFE_NAMES[_name] = getattr(math, _name)


def _compile_expression(expr: str) -> Callable[[float], float]:
    """Compile `expr` (Python expression in variable `x`) into a callable.

    Sandbox: builtins disabled, only math / numpy and a small whitelist
    of names visible. The container is the security boundary, but
    blocking obvious shells (`__import__`, `eval`, file IO) keeps the
    rendered traceback informative when an LLM passes garbage.
    """
    forbidden = ["__", "import ", "open(", "exec(", "eval(", "globals(", "locals("]
    for f in forbidden:
        if f in expr:
            raise ValueError(
                f"expression rejected: contains forbidden token {f!r}"
            )
    try:
        code = compile(f"({expr})", "<function-plot-expr>", "eval")
    except SyntaxError as exc:
        raise ValueError(f"expression failed to parse: {exc}") from exc

    namespace = {"__builtins__": {}, **_SAFE_NAMES}

    def f(x: float) -> float:
        return eval(code, namespace, {"x": x})

    # Smoke-test at a benign sample point so undefined names surface
    # as ValueError at build time, not as a NameError deep inside
    # manim's plot loop.
    try:
        f(1.0)
    except Exception as exc:
        raise ValueError(
            f"expression evaluation failed: {exc}"
        ) from exc

    return f


def _resolve_range(r: list[float]) -> list[float]:
    """Manim's Axes accepts [min, max] or [min, max, step]."""
    if len(r) == 2:
        return [r[0], r[1], (r[1] - r[0]) / 5.0]
    return list(r)


@register
class FunctionPlot(Component):
    name = "FunctionPlot"
    Params = FunctionPlotParams

    def build(self, params: FunctionPlotParams) -> Mobject:
        fn = _compile_expression(params.expression)

        x_range = _resolve_range(params.x_range)
        y_range = _resolve_range(params.y_range)

        axes = Axes(
            x_range=x_range,
            y_range=y_range,
            x_length=8.0,
            y_length=4.5,
            tips=False,
        )
        graph = axes.plot(fn, color=BLUE)

        diagram = VGroup(axes, graph)

        # Use Text (Pango) for axis labels — avoids requiring a host
        # LaTeX install during tests; renders fine in the container too.
        if params.x_label:
            x_lbl = Text(params.x_label, font_size=22)
            x_lbl.next_to(axes.x_axis.get_end(), DOWN, buff=0.2)
            diagram.add(x_lbl)
        if params.y_label:
            y_lbl = Text(params.y_label, font_size=22)
            y_lbl.next_to(axes.y_axis.get_end(), LEFT, buff=0.2)
            diagram.add(y_lbl)
        if params.title:
            diagram.add(Text(params.title, font_size=28).next_to(axes, UP))

        if diagram.width > _MAX_DIAGRAM_WIDTH:
            diagram.scale_to_fit_width(_MAX_DIAGRAM_WIDTH)
        return diagram

    def animate(
        self, scene: Scene, mobject: Mobject, params: FunctionPlotParams
    ) -> None:
        scene.play(Create(mobject))
