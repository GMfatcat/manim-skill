from __future__ import annotations

import os

import streamlit as st

from manim_skill.backend_client import BackendClient

DEFAULT_BACKEND_URL = "http://localhost:8000"


def build_backend_client(url: str | None = None) -> BackendClient:
    """Build a BackendClient. The URL is the explicit `url` arg, else
    the MANIM_SKILL_BACKEND env var, else the local default."""
    resolved = url or os.environ.get(
        "MANIM_SKILL_BACKEND", DEFAULT_BACKEND_URL
    )
    return BackendClient(resolved)


@st.cache_resource
def get_backend_client() -> BackendClient:
    """One long-lived BackendClient shared across all Streamlit
    sessions and reruns — httpx clients are designed to be reused. The
    app body imports and calls this; tests monkeypatch it."""
    return build_backend_client()
