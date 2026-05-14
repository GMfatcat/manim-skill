from __future__ import annotations

from pydantic import BaseModel, ValidationError

from manim_skill.llm.client import LLMClient
from manim_skill.spec.parse import SpecParseError, parse_spec_text


class ConceptCandidate(BaseModel):
    concept: str
    why_suitable: str
    storyboard: str


class AnalyzeError(RuntimeError):
    """Raised when the analyze stage cannot produce concept candidates."""


_ANALYZE_SYSTEM = """\
You analyze source material (a paper, an article, or a code snippet) and \
pick the parts that would make good short manim animations for slides or a \
README. Return ONLY a JSON object of the form:
{"concepts": [{"concept": "...", "why_suitable": "...", "storyboard": "..."}]}
- concept: a short title for the idea to animate.
- why_suitable: one sentence on why it animates well.
- storyboard: a beat-by-beat prose description of the animation, one beat \
per sentence — this is the brief the codegen stage turns into a scene spec.
Pick at most 5 concepts. Output nothing but the JSON object."""


def analyze(
    client: LLMClient,
    prepared_input: str,
    guide_prompt: str | None = None,
) -> list[ConceptCandidate]:
    """Stage 1: extract animatable concept candidates from input text.

    One LLM call. The response is leniently parsed (mid-size models
    wrap JSON in prose/fences); each concept is validated into a
    ConceptCandidate.
    """
    user = prepared_input
    if guide_prompt:
        user = (
            f"Guidance from the user: {guide_prompt}\n\n"
            f"---\n\n{prepared_input}"
        )

    raw = client.complete(_ANALYZE_SYSTEM, user)
    try:
        data = parse_spec_text(raw)
    except SpecParseError as exc:
        raise AnalyzeError(
            f"could not parse analyze response: {exc}"
        ) from exc

    concepts_raw = data.get("concepts")
    if not isinstance(concepts_raw, list) or not concepts_raw:
        raise AnalyzeError("analyze response had no non-empty 'concepts' list")

    candidates: list[ConceptCandidate] = []
    for item in concepts_raw:
        try:
            candidates.append(ConceptCandidate.model_validate(item))
        except ValidationError as exc:
            raise AnalyzeError(
                f"invalid concept candidate {item!r}: {exc}"
            ) from exc
    return candidates
