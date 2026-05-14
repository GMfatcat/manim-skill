from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any, Literal

import redis as redis_lib
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from manim_skill.llm.catalog import build_component_catalog
from manim_skill.service.config import ServiceConfig, load_config
from manim_skill.service.job_store import JobStore
from manim_skill.service.jobs import JobStatus, ServiceJob
from manim_skill.service.queue import enqueue_analyze, enqueue_render, get_queue


class RenderRequest(BaseModel):
    mode: Literal["codegen", "spec"]
    payload: Any


def create_app(
    config: ServiceConfig | None = None, redis_conn=None
) -> FastAPI:
    """FastAPI app factory. uvicorn runs it via `--factory`; tests call
    it directly with a fakeredis connection. Nothing connects to Redis
    at import time."""
    config = config or load_config()
    redis_conn = redis_conn or redis_lib.from_url(config.redis_url)
    store = JobStore(redis_conn, config.job_ttl_seconds)
    queue = get_queue(redis_conn)
    app = FastAPI(title="manim-skill")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/catalog")
    def catalog() -> dict:
        return {"catalog": build_component_catalog()}

    @app.post("/analyze")
    async def analyze_endpoint(
        file: UploadFile = File(...),
        kind: str = Form(...),
        guide_prompt: str | None = Form(None),
    ) -> dict:
        if kind not in ("text", "code", "pdf"):
            raise HTTPException(400, f"invalid kind: {kind!r}")
        job_id = uuid.uuid4().hex
        job_dir = config.work_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        input_path = job_dir / "input"
        input_path.write_bytes(await file.read())
        store.save(ServiceJob(job_id=job_id, type="analyze"))
        enqueue_analyze(queue, job_id, str(input_path), kind, guide_prompt)
        return {"job_id": job_id}

    @app.post("/render")
    def render_endpoint(body: RenderRequest) -> dict:
        if body.mode == "codegen":
            if not isinstance(body.payload, list):
                raise HTTPException(
                    400, "codegen payload must be a list of concepts"
                )
            if len(body.payload) > config.web_quota:
                raise HTTPException(
                    400,
                    f"web quota exceeded: {len(body.payload)} > "
                    f"{config.web_quota}",
                )
        job_id = uuid.uuid4().hex
        store.save(ServiceJob(job_id=job_id, type="render"))
        enqueue_render(queue, job_id, body.mode, body.payload)
        return {"job_id": job_id}

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        job = store.get(job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        return job.to_dict()

    @app.get("/jobs/{job_id}/result")
    def get_result(job_id: str) -> FileResponse:
        job = store.get(job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        if job.status != JobStatus.DONE or not job.result:
            raise HTTPException(409, "job result not ready")
        zip_path = job.result.get("zip_path")
        if not zip_path or not Path(zip_path).exists():
            raise HTTPException(404, "result file missing")
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=f"{job_id}.zip",
        )

    @app.delete("/jobs/{job_id}")
    def delete_job(job_id: str) -> dict:
        job = store.get(job_id)
        if job is not None and job.result:
            zip_path = job.result.get("zip_path")
            if zip_path and Path(zip_path).exists():
                Path(zip_path).unlink()
        store.delete(job_id)
        job_dir = config.work_dir / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        return {"deleted": job_id}

    return app
