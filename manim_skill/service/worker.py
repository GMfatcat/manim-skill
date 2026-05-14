from __future__ import annotations

import redis as redis_lib
from rq import Worker

from manim_skill.service.config import load_config
from manim_skill.service.queue import get_queue


def _build_worker(redis_conn) -> Worker:
    """Build (but do not start) an RQ Worker bound to the manim-skill
    queue — split out so it can be tested without entering .work()."""
    queue = get_queue(redis_conn)
    return Worker([queue], connection=redis_conn)


def main() -> None:
    """Entry point for the `worker` compose service:
    `python -m manim_skill.service.worker`."""
    config = load_config()
    redis_conn = redis_lib.from_url(config.redis_url)
    _build_worker(redis_conn).work()


if __name__ == "__main__":
    main()
