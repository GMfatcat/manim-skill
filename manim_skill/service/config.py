from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ServiceConfig:
    redis_url: str
    llm_base_url: str
    llm_model: str
    llm_concurrency: int
    render_concurrency: int
    work_dir: Path
    job_ttl_seconds: int
    web_quota: int
    render_quality: str = "medium"


def load_config() -> ServiceConfig:
    """Build a ServiceConfig from environment variables (all optional;
    conservative defaults suit a single-box deployment)."""
    env = os.environ
    return ServiceConfig(
        redis_url=env.get("MANIM_SKILL_REDIS_URL", "redis://localhost:6379/0"),
        llm_base_url=env.get(
            "MANIM_SKILL_LLM_BASE_URL", "http://localhost:11434/v1"
        ),
        llm_model=env.get("MANIM_SKILL_LLM_MODEL", "qwen3.5-35b"),
        llm_concurrency=int(env.get("MANIM_SKILL_LLM_CONCURRENCY", "4")),
        render_concurrency=int(
            env.get("MANIM_SKILL_RENDER_CONCURRENCY", "3")
        ),
        work_dir=Path(env.get("MANIM_SKILL_WORK_DIR", "service_work")),
        job_ttl_seconds=int(env.get("MANIM_SKILL_JOB_TTL", "3600")),
        web_quota=int(env.get("MANIM_SKILL_WEB_QUOTA", "5")),
        render_quality=env.get("MANIM_SKILL_RENDER_QUALITY", "medium"),
    )
