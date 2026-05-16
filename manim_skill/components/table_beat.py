from __future__ import annotations

from manim import (
    DOWN,
    YELLOW,
    Create,
    FadeIn,
    Indicate,
    Mobject,
    Scene,
    Table,
    Text,
    VGroup,
)
from pydantic import BaseModel, Field, model_validator

from manim_skill.components.base import Component, register

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
            "col_labels": [Text(h) for h in params.headers],
        }
        if params.row_labels:
            kwargs["row_labels"] = [Text(r) for r in params.row_labels]
            kwargs["top_left_entry"] = Text("")
        table = Table(**kwargs)

        diagram = VGroup(table)
        if params.title:
            title = Text(params.title, font_size=28)
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
                    (r + row_offset, c + col_offset), color=YELLOW
                )
                scene.play(FadeIn(cell), run_time=0.4)
                scene.play(Indicate(cell), run_time=0.6)
            except Exception:
                # Defensive: cell-coordinate API can still occasionally
                # disagree with our offset math. Skip rather than tank
                # the whole beat.
                continue
