from __future__ import annotations

from rq import Queue

from manim_skill.service.handlers import handle_analyze_job, handle_render_job

QUEUE_NAME = "manim-skill"


def get_queue(redis_conn, is_async: bool = True) -> Queue:
    """The RQ queue every job goes through. `is_async=False` runs jobs
    inline on enqueue — used by the integration test."""
    return Queue(QUEUE_NAME, connection=redis_conn, is_async=is_async)


def enqueue_analyze(
    queue: Queue,
    job_id: str,
    input_path: str,
    kind: str,
    guide_prompt: str | None,
) -> None:
    queue.enqueue(
        handle_analyze_job, job_id, input_path, kind, guide_prompt
    )


def enqueue_render(queue: Queue, job_id: str, mode: str, payload) -> None:
    queue.enqueue(handle_render_job, job_id, mode, payload)
