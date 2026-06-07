"""Framework-level visual theme: semantic palette, fonts, text factories.

Crystallizes the dlm-polish conventions so every component, the builder, and
raw beats share one deterministic look. No model calls — this is the static
harness a weak codegen model leans on.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from manim import BOLD, Text


@dataclass(frozen=True)
class Theme:
    BG: str
    BG_CARD: str
    BG_CODE: str
    INK: str
    INK_SOFT: str
    INK_FAINT: str
    PRIMARY: str
    PRIMARY_SOFT: str
    WARN: str
    HIGHLIGHT: str
    RULE: str


NEUTRAL = Theme(
    BG="#F7F6F3",
    BG_CARD="#EEEDE8",
    BG_CODE="#E8E7E1",
    INK="#1A1A1A",
    INK_SOFT="#44443F",
    INK_FAINT="#76746C",
    PRIMARY="#34597A",
    PRIMARY_SOFT="#5E7D94",
    WARN="#9A3B2E",
    HIGHLIGHT="#E8DCA8",
    RULE="#C9C5B8",
)

DLM_WARM = Theme(
    BG="#FBF8F1",
    BG_CARD="#F4F0E6",
    BG_CODE="#ECE7D9",
    INK="#1A1A1A",
    INK_SOFT="#4A4A48",
    INK_FAINT="#7A7872",
    PRIMARY="#1E4F5C",
    PRIMARY_SOFT="#3D7480",
    WARN="#8B3A2E",
    HIGHLIGHT="#F4E9C9",
    RULE="#C8C2B0",
)

_PRESETS = {"neutral": NEUTRAL, "dlm_warm": DLM_WARM}


def get_theme(name: str | None) -> Theme:
    """Resolve a preset name (case-insensitive) to a Theme; unknown -> NEUTRAL."""
    return _PRESETS.get((name or "neutral").lower(), NEUTRAL)


# Active theme, chosen once at import from the environment (mirrors the
# MANIM_SKILL_RENDER_QUALITY env-config pattern; the spec schema is untouched).
THEME = get_theme(os.environ.get("MANIM_SKILL_THEME"))

# Fonts. IBM Plex Latin is bundled in the docker image. Use the base family
# names ("IBM Plex Sans", not "...Sans TC") — the TC variant isn't in the
# IBM/plex repo, so Pango can't resolve it and falls back per-glyph, which
# breaks Latin kerning ("parallel" -> "para llel"). CJK glyphs fall through
# to the bundled Noto CJK automatically.
FONT_DISPLAY = "IBM Plex Sans"
FONT_BODY = "IBM Plex Serif"
FONT_MONO = "IBM Plex Mono"

# Layout spacing defaults (scene units). Richer layout helpers are a later phase.
GAP = 0.35
MARGIN = 0.6


def title_text(text: str, *, size: float = 48, color: str | None = None) -> Text:
    return Text(
        text, font=FONT_DISPLAY, weight=BOLD, font_size=size,
        color=color or THEME.INK,
    )


def body_text(text: str, *, size: float = 28, color: str | None = None) -> Text:
    return Text(text, font=FONT_BODY, font_size=size, color=color or THEME.INK_SOFT)


def caption_text(text: str, *, size: float = 22, color: str | None = None) -> Text:
    return Text(text, font=FONT_BODY, font_size=size, color=color or THEME.INK_SOFT)


def label_text(text: str, *, size: float = 18, color: str | None = None) -> Text:
    return Text(text, font=FONT_MONO, font_size=size, color=color or THEME.INK_FAINT)
