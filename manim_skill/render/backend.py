from __future__ import annotations

import functools
import shutil
from pathlib import Path

from manim_skill.render.bundle import BundleEntry, bundle_clips
from manim_skill.render.cache import BeatCache
from manim_skill.render.convert import mp4_to_gif
from manim_skill.render.docker_render import RenderError, render_spec_to_mp4
from manim_skill.render.jobs import BatchJob, BeatJob, ClipJob, JobStatus
from manim_skill.render.queue import RenderQueue
from manim_skill.render.stitch import stitch_mp4s
from manim_skill.spec.schema import SceneSpec


def _render_beat_job(
    indexed_beat: tuple[int, BeatJob],
    *,
    clip: ClipJob,
    clip_dir: Path,
    cache: BeatCache | None,
) -> BeatJob:
    """Render one beat as a standalone 1-beat spec.

    On success the beat mp4 is copied into `clip_dir` as
    `beat_NN.mp4` (stitch requires all inputs in one directory). A
    RenderError is caught and recorded on the BeatJob — a failed beat
    must not stop the rest of the clip or batch.
    """
    index, beat_job = indexed_beat
    beat_job.status = JobStatus.RENDERING
    dest = clip_dir / f"beat_{index:02d}.mp4"

    try:
        if cache is not None:
            cached = cache.get(beat_job.beat)
            if cached is not None:
                shutil.copy2(cached, dest)
                beat_job.mp4_path = dest
                beat_job.status = JobStatus.DONE
                return beat_job

        one_beat_spec = SceneSpec(
            title=clip.spec.title,
            aspect_ratio=clip.spec.aspect_ratio,
            beats=[beat_job.beat],
        )
        rendered = render_spec_to_mp4(
            one_beat_spec, clip_dir / f"beat_{index:02d}_work"
        )
        shutil.copy2(rendered, dest)
        beat_job.mp4_path = dest
        beat_job.status = JobStatus.DONE
        if cache is not None:
            cache.put(beat_job.beat, dest)
    except RenderError as exc:
        beat_job.status = JobStatus.FAILED
        beat_job.error = str(exc)

    return beat_job


def render_batch(
    specs: list[SceneSpec],
    workdir,
    *,
    max_workers: int = 3,
    cache: BeatCache | None = None,
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
            _render_beat_job, clip=clip, clip_dir=clip_dir, cache=cache
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

    entries = [
        BundleEntry(
            concept=clip.concept,
            mp4_path=clip.mp4_path,
            gif_path=clip.gif_path,
            status=clip.status.value,
        )
        for clip in clip_jobs
    ]
    batch.zip_path = bundle_clips(entries, workdir / "output.zip")
    batch.status = (
        JobStatus.DONE
        if any(clip.status == JobStatus.DONE for clip in clip_jobs)
        else JobStatus.FAILED
    )
    return batch
