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


def _patch_completion(client, response_obj, monkeypatch):
    monkeypatch.setattr(
        client._client.chat.completions,
        "create",
        lambda **_: response_obj,
    )


class _Choice:
    def __init__(self, content):
        class _Msg:
            pass
        msg = _Msg()
        msg.content = content
        self.message = msg


class _Resp:
    def __init__(self, choices):
        self.choices = choices


def test_openai_client_null_choices_returns_empty(monkeypatch):
    # Some providers (e.g. OpenRouter free models) occasionally return
    # `choices: null` on 200 OK responses — the client must not crash.
    client = OpenAIClient(base_url="http://localhost/v1", model="x")
    _patch_completion(client, _Resp(choices=None), monkeypatch)
    assert client.complete("sys", "usr") == ""


def test_openai_client_empty_choices_returns_empty(monkeypatch):
    client = OpenAIClient(base_url="http://localhost/v1", model="x")
    _patch_completion(client, _Resp(choices=[]), monkeypatch)
    assert client.complete("sys", "usr") == ""


def test_openai_client_null_content_returns_empty(monkeypatch):
    client = OpenAIClient(base_url="http://localhost/v1", model="x")
    _patch_completion(client, _Resp(choices=[_Choice(content=None)]), monkeypatch)
    assert client.complete("sys", "usr") == ""


def test_openai_client_normal_content_returned(monkeypatch):
    client = OpenAIClient(base_url="http://localhost/v1", model="x")
    _patch_completion(client, _Resp(choices=[_Choice(content="hello")]), monkeypatch)
    assert client.complete("sys", "usr") == "hello"
