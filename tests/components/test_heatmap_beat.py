import pytest
from manim import Mobject
from pydantic import ValidationError

from manim_skill.components.heatmap_beat import (
    HeatmapBeat,
    HeatmapBeatParams,
)


def test_build_returns_non_empty_mobject():
    comp = HeatmapBeat()
    mobj = comp.build(
        HeatmapBeatParams(values=[[0.1, 0.8], [0.5, 0.2]])
    )
    assert isinstance(mobj, Mobject)
    assert len(mobj.submobjects) > 0


def test_grid_has_one_square_per_value():
    comp = HeatmapBeat()
    mobj = comp.build(
        HeatmapBeatParams(values=[[0.1, 0.8, 0.3], [0.5, 0.2, 0.9]])
    )
    # the grid VGroup is the first submobject; it has n_rows * n_cols cells.
    grid = mobj.submobjects[0]
    cell_count = sum(len(row.submobjects) for row in grid.submobjects)
    assert cell_count == 6


def test_row_and_col_labels_added_when_provided():
    comp = HeatmapBeat()
    mobj = comp.build(
        HeatmapBeatParams(
            values=[[0.1, 0.2], [0.3, 0.4]],
            row_labels=["a", "b"],
            col_labels=["x", "y"],
        )
    )
    # Without labels we expect just the grid; with both, more children.
    bare = HeatmapBeat().build(
        HeatmapBeatParams(values=[[0.1, 0.2], [0.3, 0.4]])
    )
    assert len(mobj.submobjects) > len(bare.submobjects)


def test_empty_values_rejected():
    with pytest.raises(ValidationError):
        HeatmapBeatParams(values=[])


def test_diagram_fits_camera_width():
    comp = HeatmapBeat()
    # A very wide grid (1x20) should still fit within the safe 12u width
    mobj = comp.build(
        HeatmapBeatParams(values=[[i * 0.05 for i in range(20)]])
    )
    assert mobj.width <= 12.0


def test_uniform_values_render_without_crashing():
    # All same value -> vmin == vmax; the brightness math must not /0.
    comp = HeatmapBeat()
    mobj = comp.build(
        HeatmapBeatParams(values=[[0.5, 0.5], [0.5, 0.5]])
    )
    assert isinstance(mobj, Mobject)
