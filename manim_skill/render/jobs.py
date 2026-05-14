from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from manim_skill.spec.schema import Beat, SceneSpec


class JobStatus(str, Enum):
    QUEUED = "queued"
    RENDERING = "rendering"
    DONE = "done"
    FAILED = "failed"


@dataclass
class BeatJob:
    beat: Beat
    status: JobStatus = JobStatus.QUEUED
    mp4_path: Path | None = None
    error: str | None = None


@dataclass
class ClipJob:
    concept: str
    spec: SceneSpec
    beat_jobs: list[BeatJob] = field(default_factory=list)
    status: JobStatus = JobStatus.QUEUED
    mp4_path: Path | None = None
    gif_path: Path | None = None
    error: str | None = None


@dataclass
class BatchJob:
    clip_jobs: list[ClipJob]
    status: JobStatus = JobStatus.QUEUED
    zip_path: Path | None = None
