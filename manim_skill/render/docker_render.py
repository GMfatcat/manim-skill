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

# Manim's quality presets — see manim --help.
# low=480p15, medium=720p30, high=1080p60, production=1440p60, fourk=2160p60.
_QUALITY_FLAGS = {
    "low": "-ql",
    "medium": "-qm",
    "high": "-qh",
    "production": "-qp",
    "fourk": "-qk",
}
DEFAULT_QUALITY = "medium"


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


def render_spec_to_mp4(
    spec: SceneSpec, workdir, *, quality: str = DEFAULT_QUALITY
) -> Path:
    """Render a spec to an mp4 inside the manim-skill docker image.

    The container is the sandbox boundary for LLM-generated raw beat
    code: --rm, --network none, non-root (the image's default user),
    a hard timeout, resource caps (memory/cpus/pids), and a read-only
    root filesystem with a /tmp tmpfs for manim/Python cache writes.
    """
    if quality not in _QUALITY_FLAGS:
        raise ValueError(
            f"unknown quality {quality!r}; expected one of "
            f"{sorted(_QUALITY_FLAGS)}"
        )
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
        "manim", _QUALITY_FLAGS[quality],
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
