from __future__ import annotations

import json
import os
from pathlib import Path

from manim import DOWN, FadeIn, FadeOut, MovingCameraScene, Text

from manim_skill.builder.camera import apply_camera
from manim_skill.builder.raw import exec_raw
from manim_skill.components import base as registry
from manim_skill.spec.schema import Beat, SceneSpec
from manim_skill.spec.validate import validate_spec

SPEC_ENV_VAR = "MANIM_SKILL_SPEC"

# Max caption width in manim units. 16:9 camera frame is 14.22 wide; keep some
# horizontal padding so long captions don't clip at the edges.
_CAPTION_MAX_WIDTH = 13.0


def _build_caption(text: str) -> Text:
    """Build a bottom caption Text, shrinking it to fit if too wide.

    Single-line Text with no max-width clips long captions at the camera
    edges. We keep the single-line look (no manual line breaks needed from
    the LLM) and just scale the mobject down when it exceeds the safe width.
    """
    caption = Text(text, font_size=28)
    if caption.width > _CAPTION_MAX_WIDTH:
        caption.scale_to_fit_width(_CAPTION_MAX_WIDTH)
    caption.to_edge(DOWN)
    return caption


def load_spec_from_env() -> SceneSpec:
    """Load and validate the spec pointed to by MANIM_SKILL_SPEC."""
    path = os.environ.get(SPEC_ENV_VAR)
    if not path:
        raise RuntimeError(f"{SPEC_ENV_VAR} environment variable is not set")
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_spec(raw)


class SpecScene(MovingCameraScene):
    """Renders a SceneSpec: every beat played sequentially in one scene.

    Per-beat isolated rendering + stitching is a render-backend concern
    introduced in a later plan; Plan 1 plays all beats in a single scene.
    """

    def construct(self) -> None:
        spec = load_spec_from_env()
        self.camera.frame.save_state()
        for beat in spec.beats:
            self._render_beat(beat)

    def _render_beat(self, beat: Beat) -> None:
        if beat.component == "raw":
            exec_raw(beat.code or "", self)
        else:
            component = registry.get(beat.component)
            params = component.Params.model_validate(beat.params)
            mobject = component.build(params)
            component.animate(self, mobject, params)

        if beat.caption:
            caption = _build_caption(beat.caption)
            self.play(FadeIn(caption))

        if beat.camera:
            apply_camera(self, beat.camera)

        if beat.duration:
            self.wait(beat.duration)

        if self.mobjects:
            self.play(*[FadeOut(m) for m in list(self.mobjects)])
