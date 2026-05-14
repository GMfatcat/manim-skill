from __future__ import annotations

import json

from manim_skill.service.jobs import ServiceJob


class JobStore:
    """Redis-backed store of ServiceJob records — each job is one
    JSON-encoded key with a TTL, so abandoned jobs self-expire. `save`
    overwrites, so it doubles as the update path."""

    def __init__(self, redis_conn, ttl_seconds: int = 3600) -> None:
        self._redis = redis_conn
        self._ttl = ttl_seconds

    @staticmethod
    def _key(job_id: str) -> str:
        return f"manim-skill:job:{job_id}"

    def save(self, job: ServiceJob) -> None:
        self._redis.set(
            self._key(job.job_id),
            json.dumps(job.to_dict()),
            ex=self._ttl,
        )

    def get(self, job_id: str) -> ServiceJob | None:
        raw = self._redis.get(self._key(job_id))
        if raw is None:
            return None
        return ServiceJob.from_dict(json.loads(raw))

    def delete(self, job_id: str) -> None:
        self._redis.delete(self._key(job_id))
