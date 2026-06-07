from __future__ import annotations

from typing import Any

import manim
from manim_skill.components import theme as _theme


def _compile_raw(code: str):
    """Compile raw-beat code, recovering from the common LLM mistake of
    over-escaping newlines in the JSON `code` field.

    Some LLMs write real newlines as \\\\n in JSON; the decoded string then
    contains literal backslash+n (two chars) which Python parses as a
    line-continuation followed by an identifier — a SyntaxError. When
    compile fails and the source contains a literal backslash+n, retry
    with those sequences converted to real newlines. Code that compiles
    cleanly on the first try is left alone, so legitimate \\n inside a
    Python string literal is preserved.
    """
    try:
        return compile(code, "<raw-beat>", "exec")
    except SyntaxError:
        if "\\n" not in code:
            raise
        fixed = code.replace("\\n", "\n")
        return compile(fixed, "<raw-beat>", "exec")


def exec_raw(code: str, scene: Any) -> None:
    """Execute a raw beat's code with `self`/`scene` bound to the scene.

    All public manim names are injected into the namespace so the code
    can use `Circle`, `Text`, `FadeIn`, etc. without imports. The code
    runs inside the render container; the container is the sandbox
    boundary (no network, --rm). Errors propagate to the caller so the
    repair loop (a later plan) can react.
    """
    namespace: dict[str, Any] = {"self": scene, "scene": scene}
    for name in getattr(manim, "__all__", dir(manim)):
        namespace[name] = getattr(manim, name)
    for _name in (
        "THEME",
        "FONT_DISPLAY", "FONT_BODY", "FONT_MONO",
        "GAP", "MARGIN",
        "title_text", "body_text", "caption_text", "label_text",
    ):
        namespace[_name] = getattr(_theme, _name)
    # the active theme's color tokens, by their semantic names:
    for _token, _value in vars(_theme.THEME).items():
        namespace[_token] = _value
    exec(_compile_raw(code), namespace)
