import fakeredis

from manim_skill.llm.client import FakeLLMClient
from manim_skill.service.llm_throttle import ThrottledLLMClient

_SEM_KEY = "manim-skill:llm-semaphore"


def test_complete_passes_through_to_inner():
    redis_conn = fakeredis.FakeRedis()
    inner = FakeLLMClient(response="hello")
    client = ThrottledLLMClient(inner, redis_conn, limit=4)
    assert client.complete("sys", "usr") == "hello"
    assert inner.calls == [("sys", "usr")]


def test_semaphore_released_after_call():
    redis_conn = fakeredis.FakeRedis()
    client = ThrottledLLMClient(
        FakeLLMClient(response="x"), redis_conn, limit=4
    )
    client.complete("s", "u")
    # the semaphore counter is back to 0 (or absent)
    value = redis_conn.get(_SEM_KEY)
    assert value is None or int(value) == 0


def test_limit_is_at_least_one():
    redis_conn = fakeredis.FakeRedis()
    client = ThrottledLLMClient(
        FakeLLMClient(response="x"), redis_conn, limit=0
    )
    assert client._limit >= 1
    # still works with a degenerate limit
    assert client.complete("s", "u") == "x"
