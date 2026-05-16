from __future__ import annotations

from pathlib import Path

import redis as redis_lib

from manim_skill.llm.analyze import ConceptCandidate, analyze
from manim_skill.llm.catalog import build_component_catalog
from manim_skill.llm.client import OpenAIClient
from manim_skill.llm.codegen import CodegenError, generate_spec
from manim_skill.llm.input_prep import prepare_input
from manim_skill.llm.repair import BeatRepairer
from manim_skill.render.backend import render_batch
from manim_skill.service.config import ServiceConfig, load_config
from manim_skill.service.job_store import JobStore
from manim_skill.service.jobs import JobStatus, ServiceJob
from manim_skill.service.llm_throttle import ThrottledLLMClient
from manim_skill.spec.validate import validate_spec


def _redis_from_config(config: ServiceConfig):
    return redis_lib.from_url(config.redis_url)


def _build_llm_client(config: ServiceConfig, redis_conn):
    return ThrottledLLMClient(
        OpenAIClient(config.llm_base_url, config.llm_model),
        redis_conn,
        config.llm_concurrency,
    )


def _run_job(job_id: str, work) -> None:
    """Shared scaffolding: load the job, mark RUNNING, run
    `work(job, config, redis_conn, client)`, persist DONE/FAILED. A
    missing job record (expired/deleted) is a no-op."""
    config = load_config()
    redis_conn = _redis_from_config(config)
    store = JobStore(redis_conn, config.job_ttl_seconds)
    job = store.get(job_id)
    if job is None:
        return
    job.status = JobStatus.RUNNING
    store.save(job)
    try:
        client = _build_llm_client(config, redis_conn)
        work(job, config, redis_conn, client)
        job.status = JobStatus.DONE
    except Exception as exc:  # noqa: BLE001 - any failure -> FAILED job
        job.status = JobStatus.FAILED
        job.error = str(exc)
    store.save(job)


def handle_analyze_job(
    job_id: str, input_path: str, kind: str, guide_prompt: str | None
) -> None:
    def work(job: ServiceJob, config, redis_conn, client) -> None:
        text = prepare_input(Path(input_path).read_bytes(), kind)
        concepts = analyze(client, text, guide_prompt=guide_prompt)
        job.result = {"concepts": [c.model_dump() for c in concepts]}

    _run_job(job_id, work)


def handle_render_job(job_id: str, mode: str, payload) -> None:
    def work(job: ServiceJob, config, redis_conn, client) -> None:
        if mode == "codegen":
            catalog = build_component_catalog()
            specs = []
            for item in payload:
                concept = ConceptCandidate.model_validate(item)
                try:
                    specs.append(generate_spec(client, concept, catalog))
                except CodegenError:
                    continue
            if not specs:
                raise RuntimeError("codegen failed for all concepts")
        else:  # mode == "spec"
            specs = [validate_spec(payload)]

        job_workdir = config.work_dir / job_id
        batch = render_batch(
            specs,
            job_workdir,
            max_workers=config.render_concurrency,
            repairer=BeatRepairer(client),
            quality=config.render_quality,
        )
        if batch.zip_path is None:
            raise RuntimeError("render produced no output")
        job.result = {
            "zip_path": str(batch.zip_path),
            "render_status": batch.status.value,
        }

    _run_job(job_id, work)
