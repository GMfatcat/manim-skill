from __future__ import annotations

import functools
import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from manim_skill.llm.repair import BeatRepairer

from manim_skill.render.bundle import BundleEntry, bundle_clips
from manim_skill.render.cache import BeatCache
from manim_skill.render.convert import mp4_to_gif
from manim_skill.render.docker_render import RenderError, render_spec_to_mp4
from manim_skill.render.jobs import BatchJob, BeatJob, ClipJob, JobStatus
from manim_skill.render.metrics import (
    TIER_CACHED,
    TIER_DETERMINISTIC,
    TIER_GENERATED,
    TIER_MODEL_REPAIRED,
    TIER_UNRESOLVED,
    compute_tier_metrics,
)
from manim_skill.render.queue import RenderQueue
from manim_skill.render.stitch import stitch_mp4s
from manim_skill.spec.schema import SceneSpec


def _render_beat_job(
    indexed_beat: tuple[int, BeatJob],
    *,
    clip: ClipJob,
    clip_dir: Path,
    cache: BeatCache | None,
    repairer: "BeatRepairer | None",
    quality: str,
) -> BeatJob:
    """Render one beat as a standalone 1-beat spec.

    On success the beat mp4 is copied into `clip_dir` as `beat_NN.mp4`
    (stitch requires all inputs in one directory). A raw beat is
    rendered through `repairer` when one is supplied — the repair loop
    may rewrite the beat's code, which is recorded back on the BeatJob.
    A RenderError is caught and recorded — a failed beat must not stop
    the rest of the clip or batch. The cache is keyed on the ORIGINAL
    beat, so a re-run skips both render and repair.
    """
    index, beat_job = indexed_beat
    beat_job.status = JobStatus.RENDERING
    dest = clip_dir / f"beat_{index:02d}.mp4"
    original_beat = beat_job.beat

    try:
        if cache is not None:
            cached = cache.get(original_beat)
            if cached is not None:
                shutil.copy2(cached, dest)
                beat_job.mp4_path = dest
                beat_job.status = JobStatus.DONE
                beat_job.tier = TIER_CACHED
                return beat_job

        beat_work = clip_dir / f"beat_{index:02d}_work"
        if repairer is not None and original_beat.component == "raw":
            result = repairer.render_with_repair(
                original_beat,
                beat_work,
                title=clip.spec.title,
                aspect_ratio=clip.spec.aspect_ratio,
                quality=quality,
            )
            rendered = result.mp4_path
            beat_job.beat = result.final_beat
            beat_job.tier = (
                TIER_MODEL_REPAIRED if result.attempts > 1 else TIER_GENERATED
            )
        else:
            one_beat_spec = SceneSpec(
                title=clip.spec.title,
                aspect_ratio=clip.spec.aspect_ratio,
                beats=[original_beat],
            )
            rendered = render_spec_to_mp4(
                one_beat_spec, beat_work, quality=quality
            )
            beat_job.tier = (
                TIER_GENERATED
                if original_beat.component == "raw"
                else TIER_DETERMINISTIC
            )

        shutil.copy2(rendered, dest)
        beat_job.mp4_path = dest
        beat_job.status = JobStatus.DONE
        if cache is not None:
            cache.put(original_beat, dest)
    except RenderError as exc:
        beat_job.status = JobStatus.FAILED
        beat_job.error = str(exc)
        beat_job.tier = TIER_UNRESOLVED

    return beat_job


def render_batch(
    specs: list[SceneSpec],
    workdir,
    *,
    max_workers: int = 3,
    cache: BeatCache | None = None,
    repairer: "BeatRepairer | None" = None,
    quality: str = "medium",
    escalation_quota: float | None = None,
) -> BatchJob:
    """Render a batch of scene specs into one zip bundle.

    Each spec is a clip; each beat is rendered independently (as a
    1-beat spec) in parallel up to `max_workers`; a clip's beat mp4s
    are stitched into a clip mp4 then converted to gif; all clips are
    bundled into one zip with a manifest. A failed beat is skipped
    (the clip still stitches the beats that succeeded); a failed clip
    does not stop the batch.
    """
    workdir = Path(workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    queue = RenderQueue(max_workers=max_workers)

    clip_jobs = [
        ClipJob(
            concept=spec.title,
            spec=spec,
            beat_jobs=[BeatJob(beat=beat) for beat in spec.beats],
        )
        for spec in specs
    ]
    batch = BatchJob(clip_jobs=clip_jobs, status=JobStatus.RENDERING)

    for clip_index, clip in enumerate(clip_jobs):
        clip.status = JobStatus.RENDERING
        clip_dir = workdir / f"clip_{clip_index:02d}"
        clip_dir.mkdir(parents=True, exist_ok=True)

        worker = functools.partial(
            _render_beat_job,
            clip=clip,
            clip_dir=clip_dir,
            cache=cache,
            repairer=repairer,
            quality=quality,
        )
        queue.run_all(worker, list(enumerate(clip.beat_jobs)))

        rendered = [
            bj.mp4_path
            for bj in clip.beat_jobs
            if bj.status == JobStatus.DONE and bj.mp4_path is not None
        ]
        if not rendered:
            clip.status = JobStatus.FAILED
            clip.error = "all beats failed to render"
            continue

        try:
            clip.mp4_path = stitch_mp4s(rendered, clip_dir / "clip.mp4")
            clip.gif_path = mp4_to_gif(clip.mp4_path)
            clip.status = JobStatus.DONE
        except RenderError as exc:
            clip.status = JobStatus.FAILED
            clip.error = str(exc)

    metrics = compute_tier_metrics(batch)
    batch.escalation_rate = metrics["escalation_rate"]
    batch.over_quota = (
        escalation_quota is not None
        and metrics["escalation_rate"] > escalation_quota
    )
    if batch.over_quota:
        logger.warning(
            "escalation rate %.0f%% exceeds quota %.0f%% — strengthen the "
            "contract (add components / repair rules) before the next batch",
            metrics["escalation_rate"] * 100,
            escalation_quota * 100,
        )

    entries = [
        BundleEntry(
            concept=clip.concept,
            mp4_path=clip.mp4_path,
            gif_path=clip.gif_path,
            status=clip.status.value,
            tier_counts=per_clip["tier_counts"],
        )
        for clip, per_clip in zip(clip_jobs, metrics["per_clip"])
    ]
    batch.zip_path = bundle_clips(
        entries, workdir / "output.zip", summary=metrics
    )
    batch.status = (
        JobStatus.DONE
        if any(clip.status == JobStatus.DONE for clip in clip_jobs)
        else JobStatus.FAILED
    )
    return batch
