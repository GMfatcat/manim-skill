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
"component": "raw" with a non-empty "code" field.

RAW BEAT RULES — common mistakes the codegen LLM tends to make:
- The code runs INSIDE an existing scene's construct method. `self` is the
  scene. All public manim names (Circle, Text, FadeIn, VGroup, Create,
  Transform, Arrow, Line, Square, Rectangle, etc.) are pre-imported.
- DO NOT define a `class XxxScene(Scene):` or a `def construct(self):` — the
  scene already exists; write only the body, top-level statements.
- The code MUST contain at least one `self.play(...)` or `self.add(...)`.
  A beat that only computes/prints produces an empty frame and is wasted.
- Each beat runs in its own isolated process. You CANNOT reference variables
  defined in another beat. Define every name within the same beat's code.
- In the JSON output, encode newlines inside the `code` string as a single
  \\n (JSON's newline escape). Do NOT write \\\\n — that decodes to a literal
  backslash-n and Python parses it as a syntax error.
- If you need numpy or math, write `import numpy as np` / `import math` at
  the top of the same beat's code.

EXAMPLE of a correct raw beat (note the \\n in `code` is the JSON escape for
a real newline, not a literal backslash-n):
{"component": "raw",
 "code": "c = Circle(color=BLUE)\\nlabel = Text('hi').next_to(c, DOWN)\\nself.play(Create(c), FadeIn(label))\\nself.wait(1)",
 "caption": "intro circle",
 "duration": 3.0}

LATEX RULES — for `formula` strings in FormulaBreakdown and any other
LaTeX-bearing param. The same over-escape mistake hits LaTeX backslashes:
- LaTeX commands use ONE backslash: \\frac, \\sqrt, \\sum, \\alpha.
- In the JSON output, escape that single backslash exactly once as \\\\.
  The JSON decoder collapses \\\\ back to \\, so the decoded string is
  the original LaTeX command.
- DO NOT write \\\\\\\\frac — that decodes to \\\\frac (two backslashes),
  which is not a valid LaTeX command and the formula beat will fail to
  compile and render as an empty frame.
- This covers EVERY command, including spacing commands like \\quad, \\, and
  \\; — they are NOT exempt. Write \\\\quad, never a lone \\quad: a single
  backslash is dropped when the JSON is decoded and \\quad renders as the
  literal word "quad".
- Text-formatting commands too: \\mathbf, \\mathrm, \\text. Use EXACTLY one
  doubling — \\\\mathbf (four backslashes) decodes to \\mathbf, which LaTeX
  reads as a line break plus the literal word "mathbf", not bold text.

Correct:  "formula": "\\\\frac{Q K^T}{\\\\sqrt{d_k}}" or "a \\\\quad b"
Wrong:    "formula": "\\\\\\\\frac{Q K^T}{\\\\\\\\sqrt{d_k}}"

VISUAL RULES — keep output clean for a small model; the framework already
themes everything, so do NOT fight it:
- DO NOT use italics anywhere.
- Keep each beat's "caption" short — a few words, not a sentence.
- DO NOT pack many lines of text into one beat. Fewer elements, more space.
- In raw beats, the theme is in scope: use the semantic colors (PRIMARY,
  INK, INK_SOFT, WARN, HIGHLIGHT, ...) and the text factories
  (title_text(...), body_text(...), caption_text(...), label_text(...))
  instead of hardcoded colors/fonts. DO NOT set a background — the builder
  already applies the themed background.
- Layout helpers are also in scope for raw beats: wrap your top mobject with
  safe_area(...) to keep it on-screen, and stack([...]) to space items.

Output ONLY the JSON object, nothing else.

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
    CodegenError.  After obtaining a valid spec, run advisory lint; if
    warnings are found, do one additional re-ask and return the improved
    spec (or fall back to the first valid spec if the re-ask fails).
    """
    from manim_skill.spec.lint import lint_spec

    system = _CODEGEN_SYSTEM.replace("__CATALOG__", catalog)
    base_user = _build_user_prompt(concept)

    last_error = ""
    valid_spec: SceneSpec | None = None
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
            valid_spec = validate_spec(parse_spec_text(raw))
            break
        except (SpecParseError, SpecValidationError) as exc:
            last_error = str(exc)

    if valid_spec is None:
        raise CodegenError(
            f"codegen failed for concept {concept.concept!r} after 2 "
            f"attempts: {last_error}"
        )

    warnings = lint_spec(valid_spec)
    if warnings:
        issues = "; ".join(
            f"beat {w.beat_index}: {w.message}" for w in warnings
        )
        lint_user = (
            f"{base_user}\n\nYour scene spec is valid but has these issues: "
            f"{issues}\nReturn a cleaner scene spec JSON that fixes them, "
            "nothing else."
        )
        raw = client.complete(system, lint_user)
        try:
            return validate_spec(parse_spec_text(raw))
        except (SpecParseError, SpecValidationError):
            return valid_spec

    return valid_spec
