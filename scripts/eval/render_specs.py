"""Render all saved scene specs under a directory tree, one per workdir.

For every `spec_NN.json` (or similar) found, run manim-skill render and
capture a per-spec result (mp4 size, beat count, error). Writes a JSON
report at <out-root>/render_report.json.

Usage:
    python scripts/eval/render_specs.py <specs-dir> <out-root>

Example:
    python scripts/eval/render_specs.py tests/realworld-test/out/smoke \\
        tests/realworld-test/out/smoke-rendered
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path


def find_specs(root: Path) -> list[Path]:
    return sorted(
        p for p in root.rglob("spec_*.json") if p.is_file()
    )


def render_one(spec_path: Path, workdir: Path) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    proc = subprocess.run(
        [
            "manim-skill", "render",
            str(spec_path),
            "--workdir", str(workdir),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = time.perf_counter() - t0

    mp4 = workdir / "clip_00" / "clip.mp4"
    gif = workdir / "clip_00" / "clip.gif"
    zipp = workdir / "output.zip"

    return {
        "spec": str(spec_path),
        "workdir": str(workdir),
        "elapsed_s": round(elapsed, 1),
        "returncode": proc.returncode,
        "mp4_size": mp4.stat().st_size if mp4.exists() else 0,
        "gif_size": gif.stat().st_size if gif.exists() else 0,
        "zip_size": zipp.stat().st_size if zipp.exists() else 0,
        "stdout_tail": proc.stdout[-400:] if proc.stdout else "",
        "stderr_tail": proc.stderr[-400:] if proc.stderr else "",
    }


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    specs_dir = Path(sys.argv[1])
    out_root = Path(sys.argv[2])
    out_root.mkdir(parents=True, exist_ok=True)

    specs = find_specs(specs_dir)
    if not specs:
        sys.exit(f"no specs found under {specs_dir}")

    print(f"Rendering {len(specs)} spec(s) into {out_root}\n")
    results = []
    for spec in specs:
        rel = spec.relative_to(specs_dir).with_suffix("")
        workdir = out_root / str(rel).replace("/", "_").replace("\\", "_")
        print(f"[render] {spec}")
        try:
            r = render_one(spec, workdir)
        except Exception as exc:
            r = {"spec": str(spec), "workdir": str(workdir), "error": repr(exc)}
        ok = r.get("returncode") == 0 and r.get("mp4_size", 0) > 0
        flag = "OK  " if ok else "FAIL"
        print(f"  {flag} {r.get('elapsed_s', '?')}s  mp4={r.get('mp4_size', 0):>9} bytes")
        if not ok:
            print(f"        stderr: {r.get('stderr_tail', '').splitlines()[-1:] if r.get('stderr_tail') else '?'}")
        results.append(r)

    report = out_root / "render_report.json"
    report.write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    ok_count = sum(1 for r in results if r.get("returncode") == 0 and r.get("mp4_size", 0) > 0)
    print(f"\nSummary: {ok_count}/{len(results)} rendered successfully")
    print(f"Report:  {report}")


if __name__ == "__main__":
    main()
