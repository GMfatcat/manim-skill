from pathlib import Path

from manim_skill.service.config import ServiceConfig, load_config


def test_load_config_defaults(monkeypatch):
    for var in [
        "MANIM_SKILL_REDIS_URL", "MANIM_SKILL_LLM_BASE_URL",
        "MANIM_SKILL_LLM_MODEL", "MANIM_SKILL_LLM_CONCURRENCY",
        "MANIM_SKILL_RENDER_CONCURRENCY", "MANIM_SKILL_WORK_DIR",
        "MANIM_SKILL_JOB_TTL", "MANIM_SKILL_WEB_QUOTA",
        "MANIM_SKILL_RENDER_QUALITY",
    ]:
        monkeypatch.delenv(var, raising=False)
    config = load_config()
    assert isinstance(config, ServiceConfig)
    assert config.redis_url.startswith("redis://")
    assert config.llm_concurrency == 4
    assert config.render_concurrency == 3
    assert config.job_ttl_seconds == 3600
    assert config.web_quota == 5
    assert config.render_quality == "medium"
    assert isinstance(config.work_dir, Path)


def test_load_config_reads_render_quality(monkeypatch):
    monkeypatch.setenv("MANIM_SKILL_RENDER_QUALITY", "high")
    config = load_config()
    assert config.render_quality == "high"


def test_load_config_reads_env(monkeypatch):
    monkeypatch.setenv("MANIM_SKILL_LLM_CONCURRENCY", "8")
    monkeypatch.setenv("MANIM_SKILL_WEB_QUOTA", "3")
    monkeypatch.setenv("MANIM_SKILL_WORK_DIR", "/tmp/custom")
    config = load_config()
    assert config.llm_concurrency == 8
    assert config.web_quota == 3
    assert config.work_dir == Path("/tmp/custom")
