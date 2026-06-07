from __future__ import annotations

from typing import Literal

from manim import (
    DOWN,
    UP,
    DiGraph,
    Create,
    Graph,
    Mobject,
    Scene,
    VGroup,
)
from pydantic import BaseModel, Field, model_validator

from manim_skill.components.base import Component, register
from manim_skill.components.theme import THEME, body_text, label_text

_MAX_DIAGRAM_WIDTH = 12.0
_MAX_DIAGRAM_HEIGHT = 6.5  # camera is 8 tall; leave room for title + caption
_LAYOUTS = ("spring", "circular", "tree", "kamada_kawai", "planar")


class GraphBeatParams(BaseModel):
    nodes: list[str] = Field(min_length=1)
    edges: list[list[str]] = Field(default_factory=list)
    directed: bool = False
    layout: Literal[
        "spring", "circular", "tree", "kamada_kawai", "planar"
    ] = "spring"
    title: str | None = None

    @model_validator(mode="after")
    def _shapes_valid(self):
        if len(set(self.nodes)) != len(self.nodes):
            raise ValueError("nodes must be unique")
        node_set = set(self.nodes)
        for i, edge in enumerate(self.edges):
            if len(edge) != 2:
                raise ValueError(
                    f"edge {i} must be a [from, to] pair, got {edge}"
                )
            for endpoint in edge:
                if endpoint not in node_set:
                    raise ValueError(
                        f"edge {i} references unknown node {endpoint!r}"
                    )
        return self


def _layout_kwargs(layout: str, nodes: list[str], edges: list[tuple[str, str]]):
    """Tree layout needs a root; pick the first node."""
    if layout == "tree" and nodes:
        return {"layout": "tree", "root_vertex": nodes[0]}
    return {"layout": layout}


@register
class GraphBeat(Component):
    name = "GraphBeat"
    Params = GraphBeatParams

    def build(self, params: GraphBeatParams) -> Mobject:
        edges = [tuple(e) for e in params.edges]
        cls = DiGraph if params.directed else Graph
        # Built-in `labels=True` puts MathTex inside each vertex dot, so
        # multi-char names like "Output" or "Embedding" spill out. Use
        # small dots with external Text labels above each vertex instead.
        graph = cls(
            vertices=list(params.nodes),
            edges=edges,
            labels=False,
            vertex_config={"radius": 0.18, "color": THEME.PRIMARY},
            layout_scale=3.5,
            **_layout_kwargs(params.layout, params.nodes, edges),
        )

        external_labels = VGroup()
        for name in params.nodes:
            vertex = graph.vertices[name]
            lbl = label_text(name, size=20)
            lbl.next_to(vertex, UP, buff=0.1)
            external_labels.add(lbl)

        diagram = VGroup(graph, external_labels)
        if params.title:
            title = body_text(params.title, size=28)
            title.next_to(diagram, DOWN, buff=0.4)
            diagram.add(title)

        # Spring / tree layouts can stretch tall enough to clip the
        # title beneath; cap by whichever dimension is more constraining.
        w_scale = (
            _MAX_DIAGRAM_WIDTH / diagram.width
            if diagram.width > _MAX_DIAGRAM_WIDTH
            else 1.0
        )
        h_scale = (
            _MAX_DIAGRAM_HEIGHT / diagram.height
            if diagram.height > _MAX_DIAGRAM_HEIGHT
            else 1.0
        )
        scale = min(w_scale, h_scale)
        if scale < 1.0:
            diagram.scale(scale)
        return diagram

    def animate(
        self, scene: Scene, mobject: Mobject, params: GraphBeatParams
    ) -> None:
        scene.play(Create(mobject))
