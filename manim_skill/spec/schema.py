from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CameraDirective(BaseModel):
    action: Literal["focus", "zoom", "pan", "reset"]
    target: str | None = None
    scale: float | None = None


class Beat(BaseModel):
    component: str
    params: dict[str, Any] = Field(default_factory=dict)
    code: str | None = None
    caption: str | None = None
    duration: float | None = None
    camera: CameraDirective | None = None


class SceneSpec(BaseModel):
    title: str
    aspect_ratio: Literal["16:9", "1:1", "9:16"] = "16:9"
    beats: list[Beat] = Field(min_length=1)
