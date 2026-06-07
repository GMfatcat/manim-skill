"""Advisory static lint for a scene spec. Never raises, never blocks —
surfaced in the CLI and fed back into codegen for one self-correction re-ask.
"""
from __future__ import annotations

from dataclasses import dataclass

from manim_skill.spec.schema import SceneSpec

CAPTION_MAX_CHARS = 60
MAX_BULLETS = 6
MAX_RAW_TEXT_CALLS = 4
_RAW_TEXT_TOKENS = (
    "Text(", "MathTex(", "Tex(",
    "title_text(", "body_text(", "caption_text(", "label_text(",
)


@dataclass
class LintWarning:
    beat_index: int
    code: str
    message: str


def lint_spec(spec: SceneSpec) -> list[LintWarning]:
    warnings: list[LintWarning] = []
    for i, beat in enumerate(spec.beats):
        if beat.caption and len(beat.caption) > CAPTION_MAX_CHARS:
            warnings.append(LintWarning(i, "caption_too_long", f"caption is {len(beat.caption)} chars (>{CAPTION_MAX_CHARS}); keep it to a few words"))
        if beat.component == "TextBeat":
            bullets = (beat.params or {}).get("bullets") or []
            if len(bullets) > MAX_BULLETS:
                warnings.append(LintWarning(i, "beat_text_overload", f"{len(bullets)} bullets (>{MAX_BULLETS}); split across beats"))
        if beat.component == "raw":
            code = beat.code or ""
            n = sum(code.count(tok) for tok in _RAW_TEXT_TOKENS)
            if n > MAX_RAW_TEXT_CALLS:
                warnings.append(LintWarning(i, "beat_text_overload", f"{n} text elements in one raw beat (>{MAX_RAW_TEXT_CALLS}); fewer per beat"))
            if "background_color" in code:
                warnings.append(LintWarning(i, "raw_sets_background", "raw beat sets background_color; the builder owns the themed background"))
            if "ITALIC" in code or "italic=True" in code:
                warnings.append(LintWarning(i, "raw_uses_italic", "raw beat uses italics; the visual rules ban italics"))
    return warnings
