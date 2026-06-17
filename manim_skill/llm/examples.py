from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from manim_skill.llm.analyze import ConceptCandidate
from manim_skill.spec.schema import SceneSpec
from manim_skill.spec.validate import SpecValidationError, validate_spec


class GoldExampleError(RuntimeError):
    """Raised when a gold-example file is malformed."""


@dataclass
class GoldExample:
    name: str
    tags: list[str]
    spec: SceneSpec


def load_gold_examples(directory) -> list[GoldExample]:
    """Load curated gold examples from a directory of {tags, spec} JSON files.

    Returns them sorted by file stem. A missing directory yields an empty
    list (the feature is opt-in and degrades to current behavior). A
    malformed file (bad JSON, missing keys, non-string tags, or a spec
    that fails validation) raises GoldExampleError naming the file — bad
    gold is caught at load time, never silently injected.
    """
    directory = Path(directory)
    if not directory.is_dir():
        return []

    examples: list[GoldExample] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise GoldExampleError(f"{path.name}: invalid JSON: {exc}") from exc
        if not isinstance(data, dict) or "tags" not in data or "spec" not in data:
            raise GoldExampleError(
                f"{path.name}: must be an object with 'tags' and 'spec'"
            )
        tags = data["tags"]
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            raise GoldExampleError(f"{path.name}: 'tags' must be a list of strings")
        try:
            spec = validate_spec(data["spec"])
        except SpecValidationError as exc:
            raise GoldExampleError(f"{path.name}: invalid spec: {exc}") from exc
        examples.append(GoldExample(name=path.stem, tags=tags, spec=spec))
    return examples


_WORD = re.compile(r"\w+")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def _tag_matches(tag: str, tokens: set[str]) -> bool:
    tag_words = _tokens(tag)
    return bool(tag_words) and tag_words <= tokens


def select_examples(
    concept: ConceptCandidate, gold: list[GoldExample], k: int = 2
) -> list[GoldExample]:
    """Pick the k most topically-relevant gold examples for a concept.

    Scores each example by how many of its tags fully overlap the
    concept's text (concept + why_suitable + storyboard), tokenized to
    lowercase words; a multi-word tag matches only if every word is
    present. Returns the top-k by (score desc, name asc); examples with
    zero overlap are dropped, and an empty result means "inject nothing"
    rather than something irrelevant.
    """
    tokens = _tokens(
        f"{concept.concept} {concept.why_suitable} {concept.storyboard}"
    )
    scored: list[tuple[int, GoldExample]] = []
    for ex in gold:
        score = sum(1 for tag in ex.tags if _tag_matches(tag, tokens))
        if score > 0:
            scored.append((score, ex))
    scored.sort(key=lambda se: (-se[0], se[1].name))
    return [ex for _, ex in scored[:k]]
