"""Run the LLM half of manim-skill against an OpenRouter free model.

Two stages:

  analyze   — read input, call LLM `analyze`, dump the concepts it found
  codegen   — analyze + LLM `generate_spec` per concept, dump validated specs
  full      — codegen + render_batch (Docker required)

Reads the API key from the OpenRouterKey env var.

Usage:
    python scripts/eval/run_smoke.py <stage> <model> <input-path> <kind> <workdir>

Examples:
    python scripts/eval/run_smoke.py analyze nvidia/nemotron-nano-9b-v2:free \\
        tests/realworld-test/multihead_attention.py code out/smoke/mha-nano
    python scripts/eval/run_smoke.py codegen openai/gpt-oss-120b:free \\
        path/to/your_report.html text out/smoke/report-gptoss
    python scripts/eval/run_smoke.py full nvidia/nemotron-nano-9b-v2:free \\
        path/to/your_paper.pdf pdf out/smoke/paper-nano
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

# Force stdout/stderr to UTF-8 so Unicode in concept titles (em-dashes,
# non-breaking hyphens) doesn't crash on Windows cp950 consoles.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

from manim_skill.llm.analyze import analyze
from manim_skill.llm.catalog import build_component_catalog
from manim_skill.llm.client import OpenAIClient
from manim_skill.llm.codegen import CodegenError, generate_spec
from manim_skill.llm.examples import load_gold_examples
from manim_skill.llm.input_prep import prepare_input
from manim_skill.llm.pipeline import generate_specs, run_pipeline


_KEY_FILE = Path(__file__).resolve().parents[2] / "tests" / "realworld-test" / "key.txt"


def _api_key() -> str:
    key = os.environ.get("OpenRouterKey")
    if key:
        return key.strip()
    if _KEY_FILE.exists():
        for line in _KEY_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    sys.exit(
        f"No OpenRouter key found. Set OpenRouterKey env var or write the "
        f"key into {_KEY_FILE}"
    )


def _make_client(model: str) -> OpenAIClient:
    return OpenAIClient(
        base_url="https://openrouter.ai/api/v1",
        model=model,
        api_key=_api_key(),
        timeout=180.0,
    )


def _read_input(path: Path, kind: str):
    if kind == "pdf":
        return path.read_bytes()
    return path.read_text(encoding="utf-8")


def stage_analyze(model: str, input_path: Path, kind: str, workdir: Path) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    client = _make_client(model)
    content = _read_input(input_path, kind)
    prepared = prepare_input(content, kind)
    print(f"[prepare_input] {len(prepared)} chars")

    t0 = time.perf_counter()
    concepts = analyze(client, prepared)
    elapsed = time.perf_counter() - t0
    print(f"[analyze] {len(concepts)} concept(s) in {elapsed:.1f}s")

    out = workdir / "concepts.json"
    out.write_text(
        json.dumps([c.model_dump() for c in concepts], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    for i, c in enumerate(concepts):
        print(f"  [{i}] {c.concept}")
    print(f"→ {out}")


def stage_codegen(model: str, input_path: Path, kind: str, workdir: Path) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    client = _make_client(model)
    content = _read_input(input_path, kind)

    prepared = prepare_input(content, kind)
    print(f"[prepare_input] {len(prepared)} chars")

    t0 = time.perf_counter()
    concepts = analyze(client, prepared)
    print(f"[analyze] {len(concepts)} concept(s) in {time.perf_counter() - t0:.1f}s")
    (workdir / "concepts.json").write_text(
        json.dumps([c.model_dump() for c in concepts], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    catalog = build_component_catalog()
    gold = load_gold_examples("examples/gold")
    if gold:
        print(f"[gold] {len(gold)} example(s) loaded")
    specs = []
    fails = []
    for i, concept in enumerate(concepts):
        t0 = time.perf_counter()
        try:
            spec = generate_spec(client, concept, catalog, gold_examples=gold)
            specs.append((i, concept.concept, spec))
            (workdir / f"spec_{i:02d}.json").write_text(
                spec.model_dump_json(indent=2), encoding="utf-8"
            )
            print(f"  [{i}] OK  {concept.concept} — {len(spec.beats)} beats ({time.perf_counter() - t0:.1f}s)")
        except CodegenError as e:
            fails.append((i, concept.concept, str(e)))
            print(f"  [{i}] FAIL {concept.concept} — {e}")

    summary = {
        "model": model,
        "input": str(input_path),
        "kind": kind,
        "concepts": len(concepts),
        "specs_ok": len(specs),
        "specs_failed": len(fails),
        "failures": [{"i": i, "title": t, "error": e} for i, t, e in fails],
    }
    (workdir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n[summary] {len(specs)}/{len(concepts)} specs validated")


def stage_regen(model: str, concepts_path: Path, out_dir: Path, indices: list[int]) -> None:
    """Re-run codegen on a subset of saved concepts.

    Useful after a prompt or client fix: skip the (slow) analyze stage,
    pull cached concepts.json, and regenerate the specs for the indices
    that were previously broken.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    client = _make_client(model)
    raw = json.loads(concepts_path.read_text(encoding="utf-8"))
    from manim_skill.llm.analyze import ConceptCandidate

    concepts = [ConceptCandidate.model_validate(c) for c in raw]
    catalog = build_component_catalog()
    gold = load_gold_examples("examples/gold")
    if gold:
        print(f"[gold] {len(gold)} example(s) loaded")

    print(f"[regen] {len(indices)} concept(s) from {concepts_path}")
    fails = []
    for i in indices:
        if i < 0 or i >= len(concepts):
            print(f"  [{i}] SKIP (out of range, only {len(concepts)} concepts)")
            continue
        concept = concepts[i]
        t0 = time.perf_counter()
        try:
            spec = generate_spec(client, concept, catalog, gold_examples=gold)
            (out_dir / f"spec_{i:02d}.json").write_text(
                spec.model_dump_json(indent=2), encoding="utf-8"
            )
            print(f"  [{i}] OK   {concept.concept} — {len(spec.beats)} beats ({time.perf_counter() - t0:.1f}s)")
        except CodegenError as e:
            fails.append((i, concept.concept, str(e)))
            print(f"  [{i}] FAIL {concept.concept} — {e}")
    summary = {
        "model": model,
        "concepts_source": str(concepts_path),
        "indices": indices,
        "specs_ok": len(indices) - len(fails),
        "specs_failed": len(fails),
        "failures": [{"i": i, "title": t, "error": e} for i, t, e in fails],
    }
    (out_dir / "regen_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def stage_full(model: str, input_path: Path, kind: str, workdir: Path) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    client = _make_client(model)
    content = _read_input(input_path, kind)

    print(f"[full pipeline] model={model} input={input_path} kind={kind}")
    t0 = time.perf_counter()
    batch = run_pipeline(client, content, kind, str(workdir), max_workers=2)
    elapsed = time.perf_counter() - t0
    print(f"[done] {elapsed:.1f}s")
    print(f"  clips: {len(batch.clip_jobs)}")
    print(f"  zip:   {batch.zip_path}")
    for clip in batch.clip_jobs:
        ok_beats = sum(1 for b in clip.beat_jobs if b.mp4_path)
        print(f"  - {clip.spec.title}: {ok_beats}/{len(clip.beat_jobs)} beats ok, mp4={clip.mp4_path}")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    stage = sys.argv[1]

    if stage == "regen":
        # regen <model> <concepts.json> <out-dir> <i1,i2,...>
        if len(sys.argv) != 6:
            sys.exit(
                "regen requires: <model> <concepts.json> <out-dir> <i1,i2,...>"
            )
        model = sys.argv[2]
        concepts_path = Path(sys.argv[3])
        out_dir = Path(sys.argv[4])
        indices = [int(x) for x in sys.argv[5].split(",") if x.strip()]
        try:
            stage_regen(model, concepts_path, out_dir, indices)
        except Exception:
            traceback.print_exc()
            sys.exit(1)
        return

    if len(sys.argv) < 6:
        sys.exit(__doc__)
    model, input_path, kind, workdir = sys.argv[2:6]
    if kind not in ("text", "code", "pdf"):
        sys.exit(f"kind must be text|code|pdf, got {kind!r}")

    fn = {"analyze": stage_analyze, "codegen": stage_codegen, "full": stage_full}.get(stage)
    if fn is None:
        sys.exit(f"stage must be analyze|codegen|full|regen, got {stage!r}")

    try:
        fn(model, Path(input_path), kind, Path(workdir))
    except Exception:
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
