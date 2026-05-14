from __future__ import annotations

from typing import Any

import manim


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
    exec(compile(code, "<raw-beat>", "exec"), namespace)
