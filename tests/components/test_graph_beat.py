import pytest
from pydantic import ValidationError

from manim_skill.render.docker_render import render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec


def test_params_requires_nodes():
    from manim_skill.components.graph_beat import GraphBeatParams

    with pytest.raises(ValidationError):
        GraphBeatParams()


def test_empty_nodes_rejected():
    from manim_skill.components.graph_beat import GraphBeatParams

    with pytest.raises(ValidationError):
        GraphBeatParams(nodes=[])


def test_edge_must_have_two_endpoints():
    from manim_skill.components.graph_beat import GraphBeatParams

    with pytest.raises(ValidationError):
        GraphBeatParams(nodes=["a", "b"], edges=[["a"]])


def test_edge_endpoints_must_reference_existing_nodes():
    from manim_skill.components.graph_beat import GraphBeatParams

    with pytest.raises(ValidationError):
        GraphBeatParams(
            nodes=["a", "b"],
            edges=[["a", "ghost"]],
        )


def test_node_labels_unique():
    from manim_skill.components.graph_beat import GraphBeatParams

    with pytest.raises(ValidationError):
        GraphBeatParams(nodes=["a", "a", "b"])


def test_layout_choices():
    from manim_skill.components.graph_beat import GraphBeatParams

    # Each acceptable layout should not raise.
    for layout in ("spring", "circular", "tree"):
        GraphBeatParams(nodes=["a", "b", "c"], layout=layout)

    with pytest.raises(ValidationError):
        GraphBeatParams(nodes=["a"], layout="bogus")


def test_component_is_registered():
    import manim_skill.components.graph_beat  # noqa: F401
    from manim_skill.components import base

    assert "GraphBeat" in base.all_names()


@pytest.mark.docker
def test_graph_beat_renders_in_docker(tmp_path):
    spec = SceneSpec(
        title="T",
        beats=[
            Beat(
                component="GraphBeat",
                params={
                    "nodes": ["A", "B", "C", "D"],
                    "edges": [["A", "B"], ["A", "C"], ["B", "D"], ["C", "D"]],
                    "directed": True,
                    "layout": "spring",
                    "title": "Computation graph",
                },
                duration=1.0,
            )
        ],
    )
    mp4 = render_spec_to_mp4(spec, tmp_path, quality="low")
    assert mp4.exists()
    assert mp4.stat().st_size > 20_000
