import json
from pathlib import Path

import pytest

from manim_skill import cli as cli_mod
from manim_skill.cli import main


@pytest.fixture(autouse=True)
def _no_backend_env(monkeypatch):
    """Keep render tests in local mode unless they opt into remote."""
    monkeypatch.delenv("MANIM_SKILL_BACKEND", raising=False)

_VALID_SPEC = {
    "title": "T",
    "beats": [{"component": "TextBeat", "params": {"text": "Hi"}}],
}


def _write_spec(tmp_path, data):
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_validate_command_ok(tmp_path, capsys):
    spec_path = _write_spec(tmp_path, _VALID_SPEC)
    rc = main(["validate", spec_path])
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_validate_command_rejects_bad_spec(tmp_path, capsys):
    spec_path = _write_spec(tmp_path, {"title": "T", "beats": []})
    rc = main(["validate", spec_path])
    assert rc == 1
    assert "INVALID" in capsys.readouterr().err


def test_validate_command_missing_file(capsys):
    rc = main(["validate", "/no/such/file.json"])
    assert rc == 1
    assert "INVALID" in capsys.readouterr().err


def test_catalog_command_prints_components(capsys):
    rc = main(["catalog"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "TextBeat" in out
    assert "FormulaBreakdown" in out


def test_render_command_success(tmp_path, capsys, monkeypatch):
    from manim_skill.render.jobs import BatchJob, ClipJob, JobStatus

    def fake_render_batch(specs, workdir, *, quality="medium"):
        clip = ClipJob(
            concept=specs[0].title,
            spec=specs[0],
            status=JobStatus.DONE,
            mp4_path=Path("out/clip.mp4"),
            gif_path=Path("out/clip.gif"),
        )
        return BatchJob(
            clip_jobs=[clip],
            status=JobStatus.DONE,
            zip_path=Path("out/output.zip"),
        )

    monkeypatch.setattr(cli_mod, "render_batch", fake_render_batch)
    spec_path = _write_spec(tmp_path, _VALID_SPEC)
    rc = main(["render", spec_path, "--workdir", str(tmp_path / "wd")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "mp4:" in out
    assert "gif:" in out
    assert "zip:" in out


def test_render_command_reports_render_failure(tmp_path, capsys, monkeypatch):
    from manim_skill.render.jobs import BatchJob, ClipJob, JobStatus

    def fake_render_batch(specs, workdir, *, quality="medium"):
        clip = ClipJob(
            concept=specs[0].title,
            spec=specs[0],
            status=JobStatus.FAILED,
            error="all beats failed",
        )
        return BatchJob(clip_jobs=[clip], status=JobStatus.FAILED)

    monkeypatch.setattr(cli_mod, "render_batch", fake_render_batch)
    spec_path = _write_spec(tmp_path, _VALID_SPEC)
    rc = main(["render", spec_path, "--workdir", str(tmp_path / "wd")])
    assert rc == 1
    assert "RENDER FAILED" in capsys.readouterr().err


def test_render_command_passes_quality_flag(tmp_path, capsys, monkeypatch):
    from manim_skill.render.jobs import BatchJob, ClipJob, JobStatus

    captured = {}

    def fake_render_batch(specs, workdir, *, quality="medium"):
        captured["quality"] = quality
        clip = ClipJob(
            concept=specs[0].title,
            spec=specs[0],
            status=JobStatus.DONE,
            mp4_path=Path("out/clip.mp4"),
            gif_path=Path("out/clip.gif"),
        )
        return BatchJob(
            clip_jobs=[clip],
            status=JobStatus.DONE,
            zip_path=Path("out/output.zip"),
        )

    monkeypatch.setattr(cli_mod, "render_batch", fake_render_batch)
    spec_path = _write_spec(tmp_path, _VALID_SPEC)
    rc = main([
        "render", spec_path,
        "--quality", "high",
        "--workdir", str(tmp_path / "wd"),
    ])
    assert rc == 0
    assert captured["quality"] == "high"


def test_render_command_quality_defaults_to_medium(
    tmp_path, capsys, monkeypatch
):
    from manim_skill.render.jobs import BatchJob, ClipJob, JobStatus

    captured = {}

    def fake_render_batch(specs, workdir, *, quality="medium"):
        captured["quality"] = quality
        clip = ClipJob(
            concept=specs[0].title,
            spec=specs[0],
            status=JobStatus.DONE,
            mp4_path=Path("out/c.mp4"),
            gif_path=Path("out/c.gif"),
        )
        return BatchJob(
            clip_jobs=[clip],
            status=JobStatus.DONE,
            zip_path=Path("out/o.zip"),
        )

    monkeypatch.setattr(cli_mod, "render_batch", fake_render_batch)
    spec_path = _write_spec(tmp_path, _VALID_SPEC)
    rc = main(["render", spec_path, "--workdir", str(tmp_path / "wd")])
    assert rc == 0
    assert captured["quality"] == "medium"


def test_render_command_rejects_bad_spec(tmp_path, capsys):
    spec_path = _write_spec(tmp_path, {"title": "T", "beats": []})
    rc = main(["render", spec_path, "--workdir", str(tmp_path / "wd")])
    assert rc == 1
    assert "INVALID" in capsys.readouterr().err


def test_gen_skill_docs_command(tmp_path, capsys):
    rc = main(["gen-skill-docs", "--skill-dir", str(tmp_path / "skill")])
    assert rc == 0
    assert (tmp_path / "skill" / "reference" / "components.md").exists()


class _FakeBackendClient:
    """Test double for BackendClient — records the submitted spec and
    returns a scripted job outcome."""

    last_spec = None

    def __init__(self, base_url, **kwargs):
        self.base_url = base_url

    def submit_render_spec(self, spec):
        _FakeBackendClient.last_spec = spec
        return "fake-job-id"

    def wait_for_job(self, job_id):
        return {"status": "done", "result": {}}

    def download_result(self, job_id, dest_path):
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"PK\x03\x04fake-zip")
        return dest

    def delete_job(self, job_id):
        pass


def test_render_remote_via_env(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli_mod, "BackendClient", _FakeBackendClient)
    monkeypatch.setenv("MANIM_SKILL_BACKEND", "http://spark:8000")
    spec_path = _write_spec(tmp_path, _VALID_SPEC)
    rc = main(["render", spec_path, "--workdir", str(tmp_path / "out")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "submitted:" in out
    assert "zip:" in out
    assert _FakeBackendClient.last_spec == _VALID_SPEC


def test_render_remote_via_flag(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli_mod, "BackendClient", _FakeBackendClient)
    spec_path = _write_spec(tmp_path, _VALID_SPEC)
    rc = main([
        "render", spec_path, "--remote", "http://spark:8000",
        "--workdir", str(tmp_path / "out"),
    ])
    assert rc == 0
    assert "zip:" in capsys.readouterr().out


def test_render_remote_reports_job_failure(tmp_path, monkeypatch, capsys):
    class _FailingClient(_FakeBackendClient):
        def wait_for_job(self, job_id):
            return {"status": "failed", "error": "boom"}

    monkeypatch.setattr(cli_mod, "BackendClient", _FailingClient)
    spec_path = _write_spec(tmp_path, _VALID_SPEC)
    rc = main([
        "render", spec_path, "--remote", "http://spark:8000",
        "--workdir", str(tmp_path / "out"),
    ])
    assert rc == 1
    assert "RENDER FAILED" in capsys.readouterr().err


def test_render_remote_reports_backend_error(tmp_path, monkeypatch, capsys):
    from manim_skill.backend_client import BackendClientError

    class _BrokenClient(_FakeBackendClient):
        def submit_render_spec(self, spec):
            raise BackendClientError("connection refused")

    monkeypatch.setattr(cli_mod, "BackendClient", _BrokenClient)
    spec_path = _write_spec(tmp_path, _VALID_SPEC)
    rc = main([
        "render", spec_path, "--remote", "http://spark:8000",
        "--workdir", str(tmp_path / "out"),
    ])
    assert rc == 1
    assert "BACKEND ERROR" in capsys.readouterr().err


def test_render_remote_rejects_unparseable_spec(tmp_path, monkeypatch, capsys):
    # malformed JSON is caught locally before any backend call
    monkeypatch.setattr(cli_mod, "BackendClient", _FakeBackendClient)
    bad = tmp_path / "bad.json"
    bad.write_text("this is not json", encoding="utf-8")
    rc = main([
        "render", str(bad), "--remote", "http://spark:8000",
        "--workdir", str(tmp_path / "out"),
    ])
    assert rc == 1
    assert "INVALID" in capsys.readouterr().err
