import pytest

from manim_skill.builder.raw import exec_raw


class FakeScene:
    def __init__(self):
        self.calls = []

    def play(self, *args, **kwargs):
        self.calls.append(("play", args, kwargs))

    def wait(self, *args, **kwargs):
        self.calls.append(("wait", args, kwargs))


def test_exec_raw_binds_self_to_scene():
    scene = FakeScene()
    exec_raw("self.wait(2)", scene)
    assert ("wait", (2,), {}) in scene.calls


def test_exec_raw_exposes_manim_names_without_import():
    scene = FakeScene()
    # Circle is a manim name; must be available in the exec namespace.
    exec_raw("c = Circle()", scene)  # must not raise NameError


def test_exec_raw_propagates_errors():
    scene = FakeScene()
    with pytest.raises(ZeroDivisionError):
        exec_raw("x = 1 / 0", scene)
