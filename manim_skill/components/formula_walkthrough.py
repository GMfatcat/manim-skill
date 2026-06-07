from __future__ import annotations

from manim import (
    DOWN,
    Create,
    FadeIn,
    FadeOut,
    MathTex,
    Mobject,
    Scene,
    SurroundingRectangle,
    VGroup,
    Write,
)
from pydantic import BaseModel, Field, model_validator

from manim_skill.components.base import Component, register
from manim_skill.components.theme import THEME, body_text, caption_text

_BEAT_PAUSE = 1.2


class FormulaStep(BaseModel):
    indices: list[int] = Field(min_length=1)
    caption: str | None = None

    @model_validator(mode="after")
    def _indices_non_negative(self):
        if any(i < 0 for i in self.indices):
            raise ValueError("step indices must be non-negative")
        return self


class FormulaWalkthroughParams(BaseModel):
    segments: list[str] = Field(min_length=1)
    steps: list[FormulaStep] = Field(default_factory=list)
    title: str | None = None

    @model_validator(mode="after")
    def _step_indices_in_range(self):
        n = len(self.segments)
        for s in self.steps:
            for i in s.indices:
                if i >= n:
                    raise ValueError(
                        f"step index {i} out of range for {n} segments"
                    )
        return self


@register
class FormulaWalkthrough(Component):
    name = "FormulaWalkthrough"
    Params = FormulaWalkthroughParams

    def build(self, params: FormulaWalkthroughParams) -> Mobject:
        formula = MathTex(*params.segments)
        group = VGroup(formula)
        if params.title:
            group.add(body_text(params.title, size=28).next_to(formula, DOWN))
        return group

    def animate(
        self,
        scene: Scene,
        mobject: Mobject,
        params: FormulaWalkthroughParams,
    ) -> None:
        # The formula is the first child of the returned VGroup.
        formula = mobject.submobjects[0]
        scene.play(Write(mobject))

        for step in params.steps:
            parts = VGroup(*[formula[i] for i in step.indices])
            box = SurroundingRectangle(parts, color=THEME.PRIMARY, buff=0.08)
            mobjs_to_play = [Create(box)]
            caption_mobj = None
            if step.caption:
                caption_mobj = caption_text(step.caption, size=24)
                caption_mobj.next_to(formula, DOWN, buff=0.6)
                mobjs_to_play.append(FadeIn(caption_mobj))
            scene.play(*mobjs_to_play)
            scene.wait(_BEAT_PAUSE)
            fade_outs = [FadeOut(box)]
            if caption_mobj is not None:
                fade_outs.append(FadeOut(caption_mobj))
            scene.play(*fade_outs)
