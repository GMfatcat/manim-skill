from __future__ import annotations

from typing import Literal

from manim import RIGHT, FadeIn, LaggedStart, Mobject, Rectangle, Scene, VGroup
from pydantic import BaseModel, Field

from manim_skill.components.base import Component, register
from manim_skill.components.layout import safe_area
from manim_skill.components.theme import THEME, label_text

_State = Literal["normal", "masked", "expand", "delete", "defer"]

_STYLES: dict[str, tuple[str, str, str]] = {
    "normal": (THEME.PRIMARY, THEME.BG, THEME.INK),
    "masked": (THEME.RULE, THEME.BG_CODE, THEME.INK_FAINT),
    "expand": (THEME.PRIMARY_SOFT, THEME.HIGHLIGHT, THEME.INK),
    "delete": (THEME.WARN, THEME.BG_CARD, THEME.WARN),
    "defer": (THEME.INK_FAINT, THEME.BG_CODE, THEME.INK_FAINT),
}


class Token(BaseModel):
    text: str = ""
    state: _State = "normal"


class TokenSequenceParams(BaseModel):
    tokens: list[Token] = Field(default_factory=list)


def _token_box(token: Token) -> Mobject:
    stroke, fill, text_color = _STYLES.get(token.state, _STYLES["normal"])
    box = Rectangle(width=0.9, height=0.7, stroke_color=stroke, stroke_width=2, fill_color=fill, fill_opacity=1)
    if token.text:
        label = label_text(token.text, size=18, color=text_color)
        label.move_to(box.get_center())
        return VGroup(box, label)
    return box


@register
class TokenSequence(Component):
    name = "TokenSequence"
    Params = TokenSequenceParams

    def build(self, params: TokenSequenceParams) -> Mobject:
        row = VGroup(*[_token_box(t) for t in params.tokens])
        if len(row) > 0:
            row.arrange(RIGHT, buff=0.15)
        return safe_area(row)

    def animate(self, scene: Scene, mobject: Mobject, params: TokenSequenceParams) -> None:
        if len(mobject) > 0:
            scene.play(LaggedStart(*[FadeIn(b) for b in mobject], lag_ratio=0.15))
