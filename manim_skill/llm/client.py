from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    """Structural interface for an LLM text-completion client.

    The internal company LLMs are served via vLLM or Ollama, both of
    which expose an OpenAI-compatible API. Everything in this package
    depends only on this `.complete` interface, never on a specific
    model — that is what "model-agnostic" means here. Model routing
    (small model for analyze, large for codegen) is just "pass a
    different client", needing no extra code.
    """

    def complete(self, system: str, user: str) -> str:
        ...


class OpenAIClient:
    """LLMClient backed by any OpenAI-compatible endpoint (vLLM, Ollama)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "not-needed",
        temperature: float = 0.2,
        timeout: float = 120.0,
    ) -> None:
        from openai import OpenAI

        self.model = model
        self.temperature = temperature
        self._client = OpenAI(
            base_url=base_url, api_key=api_key, timeout=timeout
        )

    def complete(self, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""


class FakeLLMClient:
    """Deterministic LLMClient for tests.

    Either returns a fixed `response` for every call, or pops scripted
    `responses` in order (for multi-call flows like the codegen re-ask
    or the repair loop). Records every (system, user) call for asserts.
    """

    def __init__(
        self,
        response: str | None = None,
        responses: list[str] | None = None,
    ) -> None:
        if responses is not None:
            self._responses: list[str] | None = list(responses)
            self._fixed: str | None = None
        else:
            self._responses = None
            self._fixed = response if response is not None else ""
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if self._responses is not None:
            if not self._responses:
                raise AssertionError(
                    "FakeLLMClient: no scripted responses left"
                )
            return self._responses.pop(0)
        assert self._fixed is not None
        return self._fixed
