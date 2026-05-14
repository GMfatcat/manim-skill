from __future__ import annotations

from manim import Code, Create, Indicate, Mobject, Scene
from pydantic import BaseModel, Field

from manim_skill.components.base import Component, register


class CodeWalkthroughParams(BaseModel):
    code: str
    language: str = "python"
    # Each element is a group of 1-based line numbers to emphasize in order.
    # Plan 1 is coarse-grained: each group does one Indicate over the whole
    # code block. Precise per-line highlighting is a later plan.
    highlight_lines: list[list[int]] = Field(default_factory=list)


@register
class CodeWalkthrough(Component):
    name = "CodeWalkthrough"
    Params = CodeWalkthroughParams

    def build(self, params: CodeWalkthroughParams) -> Mobject:
        return Code(code_string=params.code, language=params.language)

    def animate(
        self, scene: Scene, mobject: Mobject, params: CodeWalkthroughParams
    ) -> None:
        scene.play(Create(mobject))
        for _group in params.highlight_lines:
            scene.play(Indicate(mobject))
