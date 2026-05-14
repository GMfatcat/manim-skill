from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from manim_skill.llm.client import LLMClient
from manim_skill.render.docker_render import RenderError, render_spec_to_mp4
from manim_skill.spec.schema import Beat, SceneSpec

DEFAULT_MAX_ATTEMPTS = 3

_REPAIR_SYSTEM = """\
You fix broken manim Python code. You are given a code snippet that runs
inside a manim scene's construct() (the scene is `self`) and the error it
produced. Return ONLY the corrected code snippet — no explanation, no fences."""


@dataclass
class RepairResult:
    mp4_path: Path
    final_beat: Beat
    attempts: int


class BeatRepairer:
    """Renders a raw beat, repairing its code via the LLM on failure.

    The repair loop only applies to `raw` beats — component beats are
    deterministic, so a failure there is a builder bug the LLM can't
    fix. On a RenderError the traceback is fed back to the LLM, which
    returns corrected code; this retries up to max_attempts.
    """

    def __init__(
        self, client: LLMClient, max_attempts: int = DEFAULT_MAX_ATTEMPTS
    ) -> None:
        self.client = client
        self.max_attempts = max(1, max_attempts)

    def render_with_repair(
        self,
        beat: Beat,
        work_dir,
        *,
        title: str = "clip",
        aspect_ratio: str = "16:9",
    ) -> RepairResult:
        """Render `beat` as a 1-beat spec, repairing raw code on failure.

        Returns a RepairResult on success. Raises RenderError if a
        component beat fails (no repair attempted) or a raw beat still
        fails after max_attempts.
        """
        work_dir = Path(work_dir)
        current = beat
        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            spec = SceneSpec(
                title=title, aspect_ratio=aspect_ratio, beats=[current]
            )
            try:
                mp4 = render_spec_to_mp4(
                    spec, work_dir / f"attempt_{attempt}"
                )
                return RepairResult(
                    mp4_path=mp4, final_beat=current, attempts=attempt
                )
            except RenderError as exc:
                last_error = str(exc)
                if (
                    current.component != "raw"
                    or attempt == self.max_attempts
                ):
                    raise RenderError(
                        f"repair gave up after {attempt} attempt(s): "
                        f"{last_error}"
                    ) from exc
                fixed = self.client.complete(
                    _REPAIR_SYSTEM,
                    f"Code:\n{current.code}\n\nError:\n{last_error}",
                )
                current = current.model_copy(
                    update={"code": fixed.strip()}
                )

        # Defensive: the loop always returns or raises above.
        raise RenderError(f"repair gave up: {last_error}")
