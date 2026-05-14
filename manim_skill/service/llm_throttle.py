from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

from manim_skill.llm.client import LLMClient

_SEMAPHORE_KEY = "manim-skill:llm-semaphore"


@contextmanager
def _redis_semaphore(
    redis_conn, key: str, limit: int, poll: float = 0.1
) -> Iterator[None]:
    """A crude Redis counter-based semaphore: spin until the counter
    can be incremented within `limit`. Good enough for a single-box
    deployment; a worker crash mid-call leaks a slot until the service
    restarts (acceptable for the MVP — noted, not hidden)."""
    while True:
        if redis_conn.incr(key) <= limit:
            break
        redis_conn.decr(key)
        time.sleep(poll)
    try:
        yield
    finally:
        redis_conn.decr(key)


class ThrottledLLMClient:
    """Wraps an LLMClient so that total concurrent `.complete()` calls
    across every worker stay under a cap (the scarce LLM inference
    pool). Implements the LLMClient interface, so it is a drop-in."""

    def __init__(self, inner: LLMClient, redis_conn, limit: int) -> None:
        self._inner = inner
        self._redis = redis_conn
        self._limit = max(1, limit)

    def complete(self, system: str, user: str) -> str:
        with _redis_semaphore(self._redis, _SEMAPHORE_KEY, self._limit):
            return self._inner.complete(system, user)
