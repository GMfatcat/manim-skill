import threading
import time

from manim_skill.render.queue import RenderQueue


def test_run_all_returns_results_in_input_order():
    queue = RenderQueue(max_workers=3)
    assert queue.run_all(lambda x: x * 2, [1, 2, 3, 4]) == [2, 4, 6, 8]


def test_run_all_empty_items():
    queue = RenderQueue(max_workers=3)
    assert queue.run_all(lambda x: x, []) == []


def test_run_all_respects_max_workers():
    queue = RenderQueue(max_workers=2)
    lock = threading.Lock()
    state = {"current": 0, "peak": 0}

    def work(_):
        with lock:
            state["current"] += 1
            state["peak"] = max(state["peak"], state["current"])
        time.sleep(0.05)
        with lock:
            state["current"] -= 1
        return None

    queue.run_all(work, list(range(8)))
    assert state["peak"] <= 2


def test_default_max_workers_is_positive():
    assert RenderQueue().max_workers >= 1
