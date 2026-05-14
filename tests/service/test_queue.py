from unittest.mock import MagicMock

import fakeredis

from manim_skill.service.handlers import handle_analyze_job, handle_render_job
from manim_skill.service.queue import enqueue_analyze, enqueue_render, get_queue


def test_get_queue_builds_a_queue_on_the_connection():
    redis_conn = fakeredis.FakeRedis()
    q = get_queue(redis_conn)
    assert q.name == "manim-skill"
    assert q.connection is redis_conn


def test_enqueue_analyze_calls_queue_with_handler_and_args():
    fake_queue = MagicMock()
    enqueue_analyze(fake_queue, "j1", "/work/j1/input", "text", "guide")
    fake_queue.enqueue.assert_called_once_with(
        handle_analyze_job, "j1", "/work/j1/input", "text", "guide"
    )


def test_enqueue_render_calls_queue_with_handler_and_args():
    fake_queue = MagicMock()
    payload = [{"concept": "C1"}]
    enqueue_render(fake_queue, "j2", "codegen", payload)
    fake_queue.enqueue.assert_called_once_with(
        handle_render_job, "j2", "codegen", payload
    )
