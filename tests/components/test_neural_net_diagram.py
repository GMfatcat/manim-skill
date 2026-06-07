import pytest
from manim import Mobject
from pydantic import ValidationError

from manim_skill.components.neural_net_diagram import (
    NeuralNetDiagram,
    NeuralNetDiagramParams,
)


def test_build_returns_non_empty_mobject():
    comp = NeuralNetDiagram()
    mobj = comp.build(NeuralNetDiagramParams(layers=[3, 4, 2]))
    assert isinstance(mobj, Mobject)
    assert len(mobj.submobjects) > 0


def test_build_with_layer_labels():
    comp = NeuralNetDiagram()
    mobj = comp.build(
        NeuralNetDiagramParams(layers=[2, 2], layer_labels=["in", "out"])
    )
    assert isinstance(mobj, Mobject)
    assert len(mobj.submobjects) > 0


def test_layers_requires_at_least_one():
    with pytest.raises(ValidationError):
        NeuralNetDiagramParams(layers=[])


def test_neural_net_diagram_uses_theme_fonts():
    """Layer labels must use FONT_MONO (label_text) after theme wiring."""
    from manim_skill.components.theme import FONT_MONO

    mobj = NeuralNetDiagram().build(
        NeuralNetDiagramParams(layers=[2, 2], layer_labels=["in", "out"])
    )
    # diagram = VGroup(edges, layer_groups, label_0, label_1, ...)
    # submobjects[2] is the first layer label Text
    first_label = mobj.submobjects[2]
    assert first_label.font == FONT_MONO
