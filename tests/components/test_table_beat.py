import pytest
from pydantic import ValidationError

from manim_skill.render.docker_render import render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec


def test_params_requires_rows():
    from manim_skill.components.table_beat import TableBeatParams

    with pytest.raises(ValidationError):
        TableBeatParams(headers=["a", "b"])


def test_params_requires_headers():
    from manim_skill.components.table_beat import TableBeatParams

    with pytest.raises(ValidationError):
        TableBeatParams(rows=[["1", "2"]])


def test_row_widths_must_match_header_count():
    from manim_skill.components.table_beat import TableBeatParams

    with pytest.raises(ValidationError):
        TableBeatParams(
            headers=["a", "b", "c"],
            rows=[["1", "2"]],  # 2 cols vs 3-col header
        )


def test_row_labels_must_match_row_count_when_provided():
    from manim_skill.components.table_beat import TableBeatParams

    with pytest.raises(ValidationError):
        TableBeatParams(
            headers=["a", "b"],
            rows=[["1", "2"], ["3", "4"]],
            row_labels=["only-one"],
        )


def test_highlight_indices_must_be_in_range():
    from manim_skill.components.table_beat import TableBeatParams

    with pytest.raises(ValidationError):
        TableBeatParams(
            headers=["a", "b"],
            rows=[["1", "2"]],
            highlight_cells=[[5, 0]],
        )


def test_valid_params_accepted():
    from manim_skill.components.table_beat import TableBeatParams

    p = TableBeatParams(
        headers=["acc", "params"],
        rows=[["72.1", "8M"], ["79.5", "32M"]],
        row_labels=["small", "large"],
        title="Benchmark",
        highlight_cells=[[1, 0]],
    )
    assert p.title == "Benchmark"
    assert len(p.rows) == 2


def test_component_is_registered():
    import manim_skill.components.table_beat  # noqa: F401
    from manim_skill.components import base

    assert "TableBeat" in base.all_names()


def test_title_uses_theme_font():
    from manim_skill.components.table_beat import TableBeat, TableBeatParams
    from manim_skill.components.theme import FONT_BODY

    comp = TableBeat()
    mobj = comp.build(
        TableBeatParams(
            headers=["Metric", "Value"],
            rows=[["72.1", "8M"]],
            title="Results",
        )
    )
    # diagram = VGroup(table, title); title is submobjects[1]
    title = mobj.submobjects[1]
    assert title.font == FONT_BODY


def test_col_labels_use_theme_font():
    from manim_skill.components.table_beat import TableBeat, TableBeatParams
    from manim_skill.components.theme import FONT_MONO

    comp = TableBeat()
    mobj = comp.build(
        TableBeatParams(
            headers=["Metric", "Value"],
            rows=[["72.1", "8M"]],
        )
    )
    table = mobj.submobjects[0]
    col_labels = table.get_col_labels()
    assert col_labels[0].font == FONT_MONO


@pytest.mark.docker
def test_table_beat_renders_in_docker(tmp_path):
    spec = SceneSpec(
        title="T",
        beats=[
            Beat(
                component="TableBeat",
                params={
                    "headers": ["acc", "params"],
                    "rows": [["72.1", "8M"], ["79.5", "32M"]],
                    "row_labels": ["small", "large"],
                    "title": "Benchmark",
                },
                duration=1.0,
            )
        ],
    )
    mp4 = render_spec_to_mp4(spec, tmp_path, quality="low")
    assert mp4.exists()
    assert mp4.stat().st_size > 20_000
