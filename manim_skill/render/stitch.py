from __future__ import annotations

import subprocess
from pathlib import Path

from manim_skill.render.docker_render import IMAGE, RenderError

STITCH_TIMEOUT_SECONDS = 180


def stitch_mp4s(mp4_paths, output_path) -> Path:
    """Concatenate mp4s into one mp4 via ffmpeg's concat demuxer.

    Constraint: every input mp4 must already live in the same
    directory as `output_path` — that directory is bind-mounted into
    the container as /work and the concat list references inputs by
    bare filename. The orchestrator (backend.render_batch) copies beat
    mp4s into the clip directory before calling this.

    `-c copy` works because manim renders every beat with identical
    settings, so the streams are concat-compatible.
    """
    mp4_paths = [Path(p) for p in mp4_paths]
    if not mp4_paths:
        raise RenderError("stitch: no input mp4s")

    output_path = Path(output_path).resolve()
    workdir = output_path.parent
    list_file = workdir / "concat_list.txt"
    list_file.write_text(
        "".join(f"file '{p.name}'\n" for p in mp4_paths),
        encoding="utf-8",
    )

    cmd = [
        "docker", "run", "--rm", "--network", "none",
        "-v", f"{workdir}:/work", "-w", "/work",
        IMAGE,
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", "concat_list.txt",
        "-c", "copy",
        output_path.name,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=STITCH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RenderError("stitch timed out") from exc

    if result.returncode != 0:
        raise RenderError(f"ffmpeg concat failed:\n{result.stderr}")
    if not output_path.exists():
        raise RenderError("stitch produced no output file")
    return output_path
