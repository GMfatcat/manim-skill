from __future__ import annotations

from typing import Literal

from manim import DOWN, LEFT, FadeIn, Mobject, Scene, Text, VGroup
from pydantic import BaseModel, Field

from manim_skill.components.base import Component, register
from manim_skill.components.theme import body_text, title_text


class TextBeatParams(BaseModel):
    text: str
    subtitle: str | None = None
    style: Literal["title", "caption", "bullets"] = "title"
    bullets: list[str] = Field(default_factory=list)


@register
class TextBeat(Component):
    name = "TextBeat"
    Params = TextBeatParams

    def build(self, params: TextBeatParams) -> Mobject:
        group = VGroup()
        if params.style == "bullets":
            group.add(title_text(params.text, size=44))
            for bullet in params.bullets:
                group.add(body_text(f"• {bullet}", size=32))
            group.arrange(DOWN, aligned_edge=LEFT, buff=0.4)
        else:
            header_size = 56 if params.style == "title" else 36
            group.add(title_text(params.text, size=header_size))
            if params.subtitle:
                group.add(body_text(params.subtitle, size=32))
            group.arrange(DOWN, buff=0.4)
        return group

    def animate(
        self, scene: Scene, mobject: Mobject, params: TextBeatParams
    ) -> None:
        scene.play(FadeIn(mobject))
