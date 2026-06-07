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


def test_exec_raw_recovers_double_escaped_newlines():
    """Some LLMs over-escape newlines in the JSON `code` field: real
    newlines that should be \\n in JSON come out as \\\\n, decoding to a
    literal backslash+n in Python source. That's a SyntaxError. If
    compile fails and the code contains a literal backslash+n, retry
    after converting them to real newlines."""
    scene = FakeScene()
    # Two statements joined by a literal backslash+n — would normally
    # be a SyntaxError. The defensive fix replaces it with a real
    # newline so both statements execute.
    code = "self.wait(1)\\nself.wait(2)"
    exec_raw(code, scene)
    assert ("wait", (1,), {}) in scene.calls
    assert ("wait", (2,), {}) in scene.calls


def test_exec_raw_preserves_backslash_n_inside_string_literal():
    """A legitimate \\n inside a Python string literal (which compiles
    fine on the first try) must not be touched by the recovery path."""
    scene = FakeScene()
    captured = {}

    def fake_log(msg):
        captured["msg"] = msg

    scene.log = fake_log
    # \\n inside a Python string is an escape sequence meaning newline.
    # The source compiles cleanly; the recovery heuristic must not run.
    exec_raw('self.log("a\\nb")', scene)
    assert captured["msg"] == "a\nb"  # real newline, not backslash+n


def test_exec_raw_still_raises_when_recovery_does_not_help():
    """If the code has neither literal \\n nor any other recoverable
    pattern, an original SyntaxError still propagates."""
    scene = FakeScene()
    with pytest.raises(SyntaxError):
        exec_raw("def(", scene)


def test_theme_names_available_in_raw_namespace():
    from unittest.mock import MagicMock
    from manim_skill.builder.raw import exec_raw

    scene = MagicMock()
    # PRIMARY (a token), title_text (a factory), and FONT_MONO must resolve.
    exec_raw(
        "t = title_text('hi', color=PRIMARY)\n"
        "f = FONT_MONO\n"
        "self.add(t)",
        scene,
    )
    scene.add.assert_called_once()
