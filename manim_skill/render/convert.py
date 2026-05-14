from __future__ import annotations

import subprocess
from pathlib import Path

from manim_skill.render.docker_render import IMAGE, RenderError

CONVERT_TIMEOUT_SECONDS = 120


def mp4_to_gif(mp4_path) -> Path:
    """Convert an mp4 to a README-friendly gif via ffmpeg in docker.

    Two-pass palette conversion for reasonable size and quality. The
    gif is written next to the mp4. ffmpeg ships inside the image.
    """
    mp4_path = Path(mp4_path).resolve()
    workdir = mp4_path.parent
    gif_path = mp4_path.with_suffix(".gif")
    palette = "palette.png"
    vf = "fps=15,scale=640:-1:flags=lanczos"

    palette_cmd = [
        "docker", "run", "--rm", "--network", "none",
        "-v", f"{workdir}:/work", "-w", "/work",
        IMAGE,
        "ffmpeg", "-y", "-i", mp4_path.name,
        "-vf", f"{vf},palettegen", palette,
    ]
    gif_cmd = [
        "docker", "run", "--rm", "--network", "none",
        "-v", f"{workdir}:/work", "-w", "/work",
        IMAGE,
        "ffmpeg", "-y", "-i", mp4_path.name, "-i", palette,
        "-lavfi", f"{vf}[x];[x][1:v]paletteuse",
        gif_path.name,
    ]

    for cmd in (palette_cmd, gif_cmd):
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=CONVERT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise RenderError("gif conversion timed out") from exc
        if result.returncode != 0:
            raise RenderError(f"ffmpeg failed:\n{result.stderr}")

    if not gif_path.exists():
        raise RenderError("gif conversion produced no file")
    return gif_path
