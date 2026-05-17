"""Bundle a set of saved spec JSONs into one render_batch output zip.

Used to produce a single end-to-end deliverable (mp4 + gif per concept
+ a top-level manifest.json) from a directory of validated specs.

Usage:
    python scripts/eval/bundle_specs.py <specs-dir> <out-dir> [--quality medium]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from manim_skill.render.backend import render_batch
from manim_skill.spec.parse import parse_spec_text
from manim_skill.spec.validate import validate_spec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("specs_dir")
    parser.add_argument("out_dir")
    parser.add_argument("--quality", default="medium")
    args = parser.parse_args()

    specs_dir = Path(args.specs_dir)
    out_dir = Path(args.out_dir)

    specs = []
    for path in sorted(specs_dir.glob("spec_*.json")):
        text = path.read_text(encoding="utf-8")
        specs.append(validate_spec(parse_spec_text(text)))
        print(f"loaded {path.name}: {specs[-1].title}")
    if not specs:
        raise SystemExit(f"no spec_*.json under {specs_dir}")

    print(f"\nrendering {len(specs)} clip(s) into {out_dir} @ {args.quality}")
    batch = render_batch(specs, out_dir, quality=args.quality)

    print(f"\nbatch status: {batch.status.value}")
    print(f"zip:          {batch.zip_path}")
    for i, clip in enumerate(batch.clip_jobs):
        ok = sum(1 for bj in clip.beat_jobs if bj.mp4_path)
        total = len(clip.beat_jobs)
        print(f"  [{i}] {clip.spec.title}: {ok}/{total} beats, status={clip.status.value}")
    print(f"\nmanifest: {(out_dir / 'output.zip').stat().st_size} bytes zip")


if __name__ == "__main__":
    main()
