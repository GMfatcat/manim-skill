from __future__ import annotations

from manim_skill.llm.analyze import analyze
from manim_skill.llm.catalog import build_component_catalog
from manim_skill.llm.client import LLMClient
from manim_skill.llm.codegen import CodegenError, generate_spec
from manim_skill.llm.examples import GoldExample
from manim_skill.llm.input_prep import InputKind, prepare_input
from manim_skill.llm.repair import BeatRepairer
from manim_skill.render.backend import render_batch
from manim_skill.render.cache import BeatCache
from manim_skill.render.jobs import BatchJob
from manim_skill.spec.schema import SceneSpec


def generate_specs(
    client: LLMClient,
    content,
    kind: InputKind,
    *,
    guide_prompt: str | None = None,
    gold_examples: list[GoldExample] | None = None,
) -> list[SceneSpec]:
    """Run the LLM half of the pipeline: input -> analyze -> codegen.

    Returns one SceneSpec per concept the analyze stage found. A
    concept whose codegen fails (CodegenError) is skipped so one bad
    concept does not sink the rest. `gold_examples`, when supplied, are
    offered to codegen as few-shot references.
    """
    prepared = prepare_input(content, kind)
    concepts = analyze(client, prepared, guide_prompt=guide_prompt)
    catalog = build_component_catalog()
    specs: list[SceneSpec] = []
    for concept in concepts:
        try:
            specs.append(
                generate_spec(client, concept, catalog, gold_examples=gold_examples)
            )
        except CodegenError:
            continue
    return specs


def run_pipeline(
    client: LLMClient,
    content,
    kind: InputKind,
    workdir,
    *,
    guide_prompt: str | None = None,
    max_workers: int = 3,
    cache: BeatCache | None = None,
    repair: bool = True,
    quality: str = "medium",
) -> BatchJob:
    """Full Phase-1 web-path pipeline (minus the human checkpoint):
    input -> analyze -> codegen -> render_batch -> zip bundle.

    Gold-example few-shot is intentionally not threaded here: it is a
    CLI/agent-path lever (see `generate_specs(gold_examples=...)`), so the
    web path runs codegen without injected examples.
    """
    specs = generate_specs(
        client, content, kind, guide_prompt=guide_prompt
    )
    repairer = BeatRepairer(client) if repair else None
    return render_batch(
        specs,
        workdir,
        max_workers=max_workers,
        cache=cache,
        repairer=repairer,
        quality=quality,
    )
