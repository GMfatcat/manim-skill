from __future__ import annotations

import json
import re

_FENCE = re.compile(r"```(?:json5?|JSON)?\s*(.*?)```", re.DOTALL)


class SpecParseError(ValueError):
    """Raised when text cannot be parsed into a spec dict."""


def parse_spec_text(text: str) -> dict:
    """Extract a JSON object from possibly-noisy text.

    Tolerates markdown fences, surrounding prose, and (via json5)
    trailing commas. Raises SpecParseError if nothing usable is found.
    """
    candidate = text.strip()

    fence_match = _FENCE.search(candidate)
    if fence_match:
        candidate = fence_match.group(1).strip()

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise SpecParseError("no JSON object found in text")
    candidate = candidate[start : end + 1]

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    try:
        import json5

        return json5.loads(candidate)
    except Exception as exc:  # noqa: BLE001 - json5 raises various types
        raise SpecParseError(f"could not parse spec JSON: {exc}") from exc
