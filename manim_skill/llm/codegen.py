from __future__ import annotations

from manim_skill.llm.analyze import ConceptCandidate
from manim_skill.llm.client import LLMClient
from manim_skill.spec.parse import SpecParseError, parse_spec_text
from manim_skill.spec.schema import SceneSpec
from manim_skill.spec.validate import SpecValidationError, validate_spec


class CodegenError(RuntimeError):
    """Raised when the codegen stage cannot produce a valid SceneSpec."""


# __CATALOG__ is a literal marker replaced via str.replace (not str.format)
# so the literal { } in the JSON examples below need no escaping.
_CODEGEN_SYSTEM = """\
You turn a concept storyboard into a manim "scene spec" — a JSON object.
Schema:
{"title": "...", "aspect_ratio": "16:9",
 "beats": [{"component": "<name>|raw", "params": {...}, "code": "<for raw>",
            "caption": "...", "duration": 4.0}]}
Prefer the components in the catalog below; each beat's "params" must match
that component's params schema. If no component fits a beat, use
"component": "raw" with a "code" field containing manim Python (the scene is
`self`). Output ONLY the JSON object, nothing else.

COMPONENT CATALOG:
__CATALOG__"""


def _build_user_prompt(concept: ConceptCandidate) -> str:
    return (
        f"Concept: {concept.concept}\n"
        f"Why it animates well: {concept.why_suitable}\n"
        f"Storyboard:\n{concept.storyboard}\n\n"
        "Produce the scene spec JSON for this concept."
    )


def generate_spec(
    client: LLMClient,
    concept: ConceptCandidate,
    catalog: str,
) -> SceneSpec:
    """Stage 2: turn one concept into a validated SceneSpec.

    One LLM call; on a parse or validation failure, re-ask once with
    the error fed back. If the second attempt still fails, raise
    CodegenError.
    """
    system = _CODEGEN_SYSTEM.replace("__CATALOG__", catalog)
    base_user = _build_user_prompt(concept)

    last_error = ""
    for attempt in range(2):
        if attempt == 0:
            user = base_user
        else:
            user = (
                f"{base_user}\n\nYour previous response was rejected: "
                f"{last_error}\nReturn a corrected scene spec JSON, "
                "nothing else."
            )
        raw = client.complete(system, user)
        try:
            return validate_spec(parse_spec_text(raw))
        except (SpecParseError, SpecValidationError) as exc:
            last_error = str(exc)

    raise CodegenError(
        f"codegen failed for concept {concept.concept!r} after 2 "
        f"attempts: {last_error}"
    )
