from __future__ import annotations

from manim import (
    DOWN,
    RIGHT,
    UP,
    Circle,
    Create,
    Line,
    Mobject,
    Scene,
    VGroup,
)
from pydantic import BaseModel, Field

from manim_skill.components.base import Component, register
from manim_skill.components.theme import THEME, label_text


class NeuralNetDiagramParams(BaseModel):
    layers: list[int] = Field(min_length=1)
    layer_labels: list[str] = Field(default_factory=list)


@register
class NeuralNetDiagram(Component):
    name = "NeuralNetDiagram"
    Params = NeuralNetDiagramParams

    def build(self, params: NeuralNetDiagramParams) -> Mobject:
        layer_groups = VGroup()
        for count in params.layers:
            nodes = VGroup(
                *[Circle(radius=0.18, color=THEME.PRIMARY) for _ in range(count)]
            )
            nodes.arrange(DOWN, buff=0.3)
            layer_groups.add(nodes)
        layer_groups.arrange(RIGHT, buff=1.5)

        edges = VGroup()
        for left, right in zip(layer_groups[:-1], layer_groups[1:]):
            for node_a in left:
                for node_b in right:
                    edges.add(
                        Line(
                            node_a.get_center(),
                            node_b.get_center(),
                            stroke_width=1,
                            stroke_color=THEME.RULE,
                            stroke_opacity=0.4,
                        )
                    )

        diagram = VGroup(edges, layer_groups)

        for group, lbl_str in zip(layer_groups, params.layer_labels):
            diagram.add(label_text(lbl_str, size=24).next_to(group, UP))

        return diagram

    def animate(
        self,
        scene: Scene,
        mobject: Mobject,
        params: NeuralNetDiagramParams,
    ) -> None:
        scene.play(Create(mobject))
