"""Smoke-probe OpenRouter: list candidate free models, then hello-world a chosen one.

Usage:
    python scripts/eval/probe_openrouter.py list-models
    python scripts/eval/probe_openrouter.py hello <model-slug>

Reads the API key from the OpenRouterKey environment variable.
"""

from __future__ import annotations

import json
import os
import sys

import httpx


BASE_URL = "https://openrouter.ai/api/v1"


def _api_key() -> str:
    key = os.environ.get("OpenRouterKey")
    if not key:
        sys.exit("OpenRouterKey env var is not set")
    return key


def list_models() -> None:
    """List OpenRouter models that match our priority keywords AND are free.

    Priority terms: nemotron (super > nano), gpt-oss.
    A model is considered 'free' here if its slug ends with ':free' or
    its prompt cost is 0.
    """
    resp = httpx.get(f"{BASE_URL}/models", headers={"Authorization": f"Bearer {_api_key()}"}, timeout=30)
    resp.raise_for_status()
    models = resp.json()["data"]

    def is_free(m: dict) -> bool:
        if m["id"].endswith(":free"):
            return True
        pricing = m.get("pricing", {})
        try:
            return float(pricing.get("prompt", "1")) == 0.0
        except (TypeError, ValueError):
            return False

    keywords = ["nemotron", "gpt-oss"]
    matches: dict[str, list[dict]] = {k: [] for k in keywords}
    for m in models:
        mid = m["id"].lower()
        for k in keywords:
            if k in mid and is_free(m):
                matches[k].append(m)

    for k, ms in matches.items():
        print(f"\n=== {k} (free) ===")
        for m in sorted(ms, key=lambda x: x["id"]):
            ctx = m.get("context_length", "?")
            print(f"  {m['id']}  ctx={ctx}")


def hello(model: str) -> None:
    """Send a single hello-world chat completion to verify the slug works."""
    from openai import OpenAI

    client = OpenAI(base_url=BASE_URL, api_key=_api_key(), timeout=60.0)
    resp = client.chat.completions.create(
        model=model,
        temperature=0.0,
        messages=[
            {"role": "system", "content": "Reply with exactly one word: pong"},
            {"role": "user", "content": "ping"},
        ],
    )
    print(f"model: {resp.model}")
    print(f"reply: {resp.choices[0].message.content!r}")
    print(f"usage: {resp.usage}")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "list-models":
        list_models()
    elif cmd == "hello":
        if len(sys.argv) < 3:
            sys.exit("hello requires a <model-slug>")
        hello(sys.argv[2])
    else:
        sys.exit(f"unknown command: {cmd}")


if __name__ == "__main__":
    main()
