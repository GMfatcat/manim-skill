from __future__ import annotations

from manim import (
    DOWN,
    Create,
    FadeIn,
    Indicate,
    Mobject,
    Scene,
    Table,
    VGroup,
)
from pydantic import BaseModel, Field, model_validator

from manim_skill.components.base import Component, register
from manim_skill.components.theme import THEME, body_text, label_text

_MAX_DIAGRAM_WIDTH = 12.0


class TableBeatParams(BaseModel):
    headers: list[str] = Field(min_length=1)
    rows: list[list[str]] = Field(min_length=1)
    row_labels: list[str] = Field(default_factory=list)
    title: str | None = None
    highlight_cells: list[list[int]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _shapes_match(self):
        n_cols = len(self.headers)
        for i, row in enumerate(self.rows):
            if len(row) != n_cols:
                raise ValueError(
                    f"row {i} has {len(row)} cells but headers has {n_cols}"
                )
        if self.row_labels and len(self.row_labels) != len(self.rows):
            raise ValueError(
                f"row_labels has {len(self.row_labels)} entries but "
                f"rows has {len(self.rows)}"
            )
        n_rows = len(self.rows)
        for pair in self.highlight_cells:
            if len(pair) != 2:
                raise ValueError(
                    f"highlight_cells entries must be [row, col] pairs, "
                    f"got {pair}"
                )
            r, c = pair
            if not (0 <= r < n_rows and 0 <= c < n_cols):
                raise ValueError(
                    f"highlight_cells {pair} out of range "
                    f"({n_rows} rows x {n_cols} cols)"
                )
        return self


@register
class TableBeat(Component):
    name = "TableBeat"
    Params = TableBeatParams

    def build(self, params: TableBeatParams) -> Mobject:
        kwargs: dict = {
            "table": params.rows,
            "col_labels": [label_text(h) for h in params.headers],
        }
        if params.row_labels:
            kwargs["row_labels"] = [label_text(r) for r in params.row_labels]
            kwargs["top_left_entry"] = label_text("")
        table = Table(**kwargs, line_config={"stroke_color": THEME.RULE})
        table.get_horizontal_lines().set_color(THEME.RULE)
        table.get_vertical_lines().set_color(THEME.RULE)
        table.get_entries().set_color(THEME.INK)

        diagram = VGroup(table)
        if params.title:
            title = body_text(params.title, size=28)
            title.next_to(table, DOWN, buff=0.3)
            diagram.add(title)

        if diagram.width > _MAX_DIAGRAM_WIDTH:
            diagram.scale_to_fit_width(_MAX_DIAGRAM_WIDTH)
        return diagram

    def animate(
        self, scene: Scene, mobject: Mobject, params: TableBeatParams
    ) -> None:
        scene.play(Create(mobject))
        # manim Table.get_cell((row, col)) is 1-indexed and counts label
        # rows/cols as cells. col_labels are always present here (we pass
        # headers), so data row 0 lives at cell row 2. row_labels shift
        # the column index when present.
        table = mobject.submobjects[0]
        row_offset = 2  # col_labels always present
        col_offset = 2 if params.row_labels else 1
        for r, c in params.highlight_cells:
            try:
                cell = table.get_cell(
                    (r + row_offset, c + col_offset), color=THEME.WARN
                )
                scene.play(FadeIn(cell), run_time=0.4)
                scene.play(Indicate(cell), run_time=0.6)
            except Exception:
                # Defensive: cell-coordinate API can still occasionally
                # disagree with our offset math. Skip rather than tank
                # the whole beat.
                continue
