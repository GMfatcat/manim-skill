from __future__ import annotations

import numpy as np
from manim import (
    BLUE,
    DOWN,
    LEFT,
    UP,
    Create,
    ManimColor,
    Mobject,
    Scene,
    Square,
    VGroup,
    interpolate_color,
)
from pydantic import BaseModel, Field

from manim_skill.components.base import Component, register
from manim_skill.components.theme import THEME, title_text, label_text

_CELL_SIZE = 0.6
_MAX_DIAGRAM_WIDTH = 12.0


class HeatmapBeatParams(BaseModel):
    values: list[list[float]] = Field(min_length=1)
    row_labels: list[str] = Field(default_factory=list)
    col_labels: list[str] = Field(default_factory=list)
    title: str | None = None
    low_color: str = THEME.PRIMARY   # emphasis/positive end
    high_color: str = THEME.WARN     # warning/negative end


def _resolve_color(name: str):
    """Resolve a color: hex string or manim constant name; fall back to BLUE."""
    if name.startswith("#"):
        return ManimColor(name)
    import manim

    color = getattr(manim, name.upper(), None)
    if color is None:
        return BLUE
    return color


@register
class HeatmapBeat(Component):
    name = "HeatmapBeat"
    Params = HeatmapBeatParams

    def build(self, params: HeatmapBeatParams) -> Mobject:
        values = np.array(params.values, dtype=float)
        vmin = float(values.min())
        vmax = float(values.max())
        span = vmax - vmin if vmax > vmin else 1.0
        low = _resolve_color(params.low_color)
        high = _resolve_color(params.high_color)

        grid = VGroup()
        for row in values:
            cells = VGroup()
            for v in row:
                t = (v - vmin) / span if vmax > vmin else 0.5
                color = interpolate_color(low, high, t)
                cell = Square(
                    side_length=_CELL_SIZE,
                    fill_color=color,
                    fill_opacity=1.0,
                    stroke_width=0.5,
                )
                cells.add(cell)
            cells.arrange(direction=[1.0, 0.0, 0.0], buff=0)
            grid.add(cells)
        grid.arrange(DOWN, buff=0)

        diagram = VGroup(grid)

        if params.col_labels:
            col_group = VGroup()
            for lbl_str in params.col_labels:
                col_group.add(label_text(lbl_str, size=20))
            col_group.arrange(direction=[1.0, 0.0, 0.0], buff=0)
            for i, lbl in enumerate(col_group.submobjects):
                lbl.move_to(grid[0][i].get_center())
            col_group.next_to(grid, UP, buff=0.15)
            diagram.add(col_group)

        if params.row_labels:
            row_group = VGroup()
            for lbl_str in params.row_labels:
                row_group.add(label_text(lbl_str, size=20))
            row_group.arrange(DOWN, buff=0)
            for i, lbl in enumerate(row_group.submobjects):
                lbl.move_to(grid[i][0].get_center())
            row_group.next_to(grid, LEFT, buff=0.15)
            diagram.add(row_group)

        if params.title:
            title = title_text(params.title, size=28)
            title.next_to(diagram, UP, buff=0.25)
            diagram.add(title)

        if diagram.width > _MAX_DIAGRAM_WIDTH:
            diagram.scale_to_fit_width(_MAX_DIAGRAM_WIDTH)
        return diagram

    def animate(
        self, scene: Scene, mobject: Mobject, params: HeatmapBeatParams
    ) -> None:
        scene.play(Create(mobject))
