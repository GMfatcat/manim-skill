import pytest

from manim_skill.llm.client import FakeLLMClient, OpenAIClient


def test_fake_client_fixed_response():
    client = FakeLLMClient(response="hello")
    assert client.complete("sys", "usr") == "hello"
    assert client.complete("sys2", "usr2") == "hello"
    assert client.calls == [("sys", "usr"), ("sys2", "usr2")]


def test_fake_client_scripted_responses_in_order():
    client = FakeLLMClient(responses=["first", "second"])
    assert client.complete("s", "u") == "first"
    assert client.complete("s", "u") == "second"


def test_fake_client_exhausted_scripted_raises():
    client = FakeLLMClient(responses=["only"])
    client.complete("s", "u")
    with pytest.raises(AssertionError):
        client.complete("s", "u")


def test_openai_client_constructs_without_network_call():
    # Constructing must not hit the network — it only builds the SDK client.
    client = OpenAIClient(base_url="http://localhost:11434/v1", model="qwen3.5-35b")
    assert client.model == "qwen3.5-35b"
