from manim_skill.backend_client import BackendClient
from manim_skill.frontend.backend import DEFAULT_BACKEND_URL, build_backend_client


def test_build_backend_client_uses_env(monkeypatch):
    monkeypatch.setenv("MANIM_SKILL_BACKEND", "http://spark:9000")
    client = build_backend_client()
    assert isinstance(client, BackendClient)
    assert client._base_url == "http://spark:9000"


def test_build_backend_client_explicit_url_wins(monkeypatch):
    monkeypatch.setenv("MANIM_SKILL_BACKEND", "http://spark:9000")
    client = build_backend_client("http://other:1234")
    assert client._base_url == "http://other:1234"


def test_build_backend_client_default(monkeypatch):
    monkeypatch.delenv("MANIM_SKILL_BACKEND", raising=False)
    client = build_backend_client()
    assert client._base_url == DEFAULT_BACKEND_URL.rstrip("/")
