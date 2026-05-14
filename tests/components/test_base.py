import pytest
from pydantic import BaseModel

from manim_skill.components import base


def test_register_and_get_returns_instance():
    class DummyParams(BaseModel):
        x: int = 0

    @base.register
    class Dummy(base.Component):
        name = "Dummy"
        Params = DummyParams

    got = base.get("Dummy")
    assert isinstance(got, Dummy)
    assert got.name == "Dummy"
    assert got.Params is DummyParams


def test_get_unknown_raises_keyerror():
    with pytest.raises(KeyError):
        base.get("NoSuchComponentXYZ")


def test_all_names_includes_registered():
    assert "Dummy" in base.all_names()
