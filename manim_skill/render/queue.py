from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeVar

_T = TypeVar("_T")
_R = TypeVar("_R")

DEFAULT_MAX_WORKERS = 3


class RenderQueue:
    """Concurrency-limited executor for render jobs.

    Phase 1 is a local ThreadPoolExecutor; this class is the interface
    seam where a Phase 2 Redis-backed queue would slot in. Render jobs
    block on `subprocess.run` (docker), so a thread pool is the right
    tool — the OS schedules the containers, the pool caps concurrency.
    """

    def __init__(self, max_workers: int = DEFAULT_MAX_WORKERS) -> None:
        self.max_workers = max(1, max_workers)

    def run_all(
        self, fn: Callable[[_T], _R], items: list[_T]
    ) -> list[_R]:
        """Run `fn` over `items` with at most `max_workers` in flight.

        Results are returned in input order. `fn` is expected not to
        raise — callers wrap per-item failure handling inside `fn`.
        """
        if not items:
            return []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            return list(executor.map(fn, items))
