"""Bundle a set of saved spec JSONs into one render_batch output zip.

Used to produce a single end-to-end deliverable (mp4 + gif per concept
+ a top-level manifest.json) from a directory of validated specs.

With --repair, raw beats that fail to render are re-asked to an LLM with
their traceback (up to --max-attempts times) via the same BeatRepairer the
web service uses; component beats are deterministic and never repaired.
Repair fires one LLM call per failing attempt, so on a free/rate-limited
endpoint pair it with --max-workers 1 to serialize the calls.

Usage:
    python scripts/eval/bundle_specs.py <specs-dir> <out-dir> [--quality medium]
        [--max-workers 3]
        [--repair --model <slug> [--max-attempts 3] [--base-url URL]]

Examples:
    python scripts/eval/bundle_specs.py out/orca out/orca-bundle
    python scripts/eval/bundle_specs.py out/orca out/orca-repair \\
        --repair --model nvidia/nemotron-3-nano-30b-a3b:free --max-workers 1

The LLM key (for --repair) is read from the OpenRouterKey env var, falling
back to tests/realworld-test/key.txt.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Force UTF-8 so Unicode in concept titles doesn't crash a cp950 console.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

from manim_skill.render.backend import render_batch
from manim_skill.render.metrics import compute_tier_metrics, format_tier_line
from manim_skill.spec.parse import parse_spec_text
from manim_skill.spec.validate import validate_spec

_KEY_FILE = Path(__file__).resolve().parents[2] / "tests" / "realworld-test" / "key.txt"
_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


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
        f"--repair needs an OpenRouter key. Set OpenRouterKey env var or "
        f"write the key into {_KEY_FILE}"
    )


def _build_repairer(model: str, base_url: str, max_attempts: int):
    from manim_skill.llm.client import OpenAIClient
    from manim_skill.llm.repair import BeatRepairer

    client = OpenAIClient(
        base_url=base_url, model=model, api_key=_api_key(), timeout=180.0
    )
    return BeatRepairer(client, max_attempts=max_attempts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("specs_dir")
    parser.add_argument("out_dir")
    parser.add_argument("--quality", default="medium")
    parser.add_argument(
        "--max-workers",
        type=int,
        default=3,
        help="parallel beat renders (use 1 with --repair on a rate-limited endpoint)",
    )
    parser.add_argument(
        "--repair",
        action="store_true",
        help="re-ask the LLM to fix raw beats that fail to render",
    )
    parser.add_argument("--model", help="LLM slug for --repair (required with --repair)")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument(
        "--escalation-quota",
        type=float,
        default=None,
        help="warn if the unresolved (escalation) beat rate exceeds this fraction, e.g. 0.1",
    )
    parser.add_argument(
        "--base-url",
        default=_DEFAULT_BASE_URL,
        help=f"OpenAI-compatible endpoint for --repair (default {_DEFAULT_BASE_URL})",
    )
    args = parser.parse_args()

    specs_dir = Path(args.specs_dir)
    out_dir = Path(args.out_dir)

    repairer = None
    if args.repair:
        if not args.model:
            parser.error("--repair requires --model")
        repairer = _build_repairer(args.model, args.base_url, args.max_attempts)

    specs = []
    for path in sorted(specs_dir.glob("spec_*.json")):
        text = path.read_text(encoding="utf-8")
        specs.append(validate_spec(parse_spec_text(text)))
        print(f"loaded {path.name}: {specs[-1].title}")
    if not specs:
        raise SystemExit(f"no spec_*.json under {specs_dir}")

    mode = (
        f"repair via {args.model} (<={args.max_attempts} attempts)"
        if repairer
        else "no repair"
    )
    print(
        f"\nrendering {len(specs)} clip(s) into {out_dir} @ {args.quality} "
        f"[{mode}, max_workers={args.max_workers}]"
    )
    batch = render_batch(
        specs,
        out_dir,
        repairer=repairer,
        quality=args.quality,
        max_workers=args.max_workers,
        escalation_quota=args.escalation_quota,
    )

    print(f"\nbatch status: {batch.status.value}")
    total_ok = total = 0
    for i, clip in enumerate(batch.clip_jobs):
        ok = sum(1 for bj in clip.beat_jobs if bj.mp4_path)
        total_ok += ok
        total += len(clip.beat_jobs)
        print(
            f"  [{i}] {clip.spec.title}: {ok}/{len(clip.beat_jobs)} beats, "
            f"status={clip.status.value}"
        )
    print(format_tier_line(compute_tier_metrics(batch)))
    if batch.over_quota:
        print(
            "WARNING: escalation rate over quota — strengthen the contract "
            "(add components / repair rules) before the next batch"
        )
    print(f"\nTOTAL: {total_ok}/{total} beats")
    print(f"zip:   {batch.zip_path}")


if __name__ == "__main__":
    main()
