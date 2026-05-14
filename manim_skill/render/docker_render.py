from __future__ import annotations

import subprocess
from pathlib import Path

from manim_skill.builder import write_render_inputs
from manim_skill.spec.schema import SceneSpec

IMAGE = "manim-skill:latest"
RENDER_TIMEOUT_SECONDS = 300
MEMORY_LIMIT = "2g"
CPU_LIMIT = "2"
PIDS_LIMIT = "256"


class RenderError(RuntimeError):
    """Raised when a docker render fails, times out, or produces no output."""


def _find_output_mp4(out_dir: Path) -> Path | None:
    """Return the final rendered mp4 under out_dir, ignoring manim's
    intermediate partial-movie-file fragments. Returns None if none found.
    """
    candidates = [
        p
        for p in out_dir.rglob("*.mp4")
        if "partial_movie_files" not in p.parts
    ]
    if not candidates:
        return None
    return sorted(candidates)[0]


def render_spec_to_mp4(spec: SceneSpec, workdir) -> Path:
    """Render a spec to an mp4 inside the manim-skill docker image.

    Plan 1 sandboxing: --network none, --rm, and a hard timeout.
    Stricter hardening (non-root, read-only fs, resource caps) is
    added in a later plan.
    """
    workdir = Path(workdir).resolve()
    write_render_inputs(spec, workdir)
    out_dir = workdir / "out"
    out_dir.mkdir(exist_ok=True)

    cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", MEMORY_LIMIT,
        "--cpus", CPU_LIMIT,
        "--pids-limit", PIDS_LIMIT,
        "--read-only",
        "--tmpfs", "/tmp",
        "-v", f"{workdir}:/work",
        "-e", "MANIM_SKILL_SPEC=/work/spec.json",
        "-e", "HOME=/tmp",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-w", "/work",
        IMAGE,
        "manim", "-ql",
        "--media_dir", "/work/out",
        "--format", "mp4",
        "/work/scene_entry.py", "SpecScene",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=RENDER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RenderError(
            f"render timed out after {RENDER_TIMEOUT_SECONDS}s"
        ) from exc

    if result.returncode != 0:
        raise RenderError(f"manim render failed:\n{result.stderr}")

    mp4 = _find_output_mp4(out_dir)
    if mp4 is None:
        raise RenderError(
            f"render produced no mp4. stderr:\n{result.stderr}"
        )
    return mp4
