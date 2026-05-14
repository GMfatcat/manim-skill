from __future__ import annotations

from typing import Any

from manim_skill.spec.schema import CameraDirective


def apply_camera(scene: Any, directive: CameraDirective) -> None:
    """Apply a camera directive to a MovingCameraScene.

    Plan 1 supports `zoom` and `reset`. `focus` and `pan` need named
    element targeting and are no-ops until a later plan. `reset`
    assumes the scene saved camera frame state at construct() start.
    """
    frame = scene.camera.frame

    if directive.action == "zoom":
        scale = directive.scale or 1.0
        scene.play(frame.animate.scale(1.0 / scale))
    elif directive.action == "reset":
        scene.play(frame.animate.restore())
    # focus / pan: deferred to a later plan
