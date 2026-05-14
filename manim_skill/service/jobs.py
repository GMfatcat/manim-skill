from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Literal


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class ServiceJob:
    """A service-level job record (analyze or render), JSON-serialized
    into Redis. Distinct from render.jobs.* which are the render
    backend's internal batch/clip/beat jobs."""

    job_id: str
    type: Literal["analyze", "render"]
    status: JobStatus = JobStatus.QUEUED
    progress: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ServiceJob":
        return cls(
            job_id=data["job_id"],
            type=data["type"],
            status=JobStatus(data["status"]),
            progress=data.get("progress"),
            result=data.get("result"),
            error=data.get("error"),
        )
