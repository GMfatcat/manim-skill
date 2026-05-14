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
