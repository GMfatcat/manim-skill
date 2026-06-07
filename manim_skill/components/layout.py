"""Deterministic geometry helpers — keep content inside the safe frame.

Separate from theme.py (color/font); this owns geometry. Used by components,
raw beats, and the builder's per-beat auto-clamp.
"""
from __future__ import annotations

from manim import DOWN, ORIGIN, RIGHT, UP, VGroup

from manim_skill.components.theme import GAP, MARGIN

FRAME_WIDTH = 14.222222
FRAME_HEIGHT = 8.0


def fit_width(mobj, max_width):
    """Scale mobj down so its width <= max_width (no-op if already narrower)."""
    if mobj.width > max_width and mobj.width > 0:
        mobj.scale_to_fit_width(max_width)
    return mobj


def safe_area(mobj, *, frame_width=FRAME_WIDTH, frame_height=FRAME_HEIGHT, margin=MARGIN):
    """Scale + recenter mobj so its bounding box lies within the margin-safe
    frame. No-op when it already fits."""
    usable_w = frame_width - 2 * margin
    usable_h = frame_height - 2 * margin
    if mobj.width > usable_w or mobj.height > usable_h:
        if mobj.width > 0 and mobj.height > 0:
            scale = min(usable_w / mobj.width, usable_h / mobj.height)
            mobj.scale(scale)
    cx, cy, _ = mobj.get_center()
    max_cx = max(0.0, usable_w / 2 - mobj.width / 2)
    max_cy = max(0.0, usable_h / 2 - mobj.height / 2)
    new_cx = max(-max_cx, min(max_cx, cx))
    new_cy = max(-max_cy, min(max_cy, cy))
    mobj.shift(RIGHT * (new_cx - cx) + UP * (new_cy - cy))
    return mobj


def stack(mobjs, *, gap=GAP, center=True):
    """Vertically arrange mobjs with a guaranteed gap so they never overlap."""
    group = VGroup(*mobjs)
    group.arrange(DOWN, buff=gap)
    if center:
        group.move_to(ORIGIN)
    return group


def clamp_new_mobjects(scene, before):
    """Clamp the mobjects added since `before` into the safe frame, as a group."""
    new = [m for m in scene.mobjects if m not in before]
    if new:
        safe_area(VGroup(*new))
