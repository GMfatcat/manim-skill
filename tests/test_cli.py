import json
from pathlib import Path

from manim_skill import cli as cli_mod
from manim_skill.cli import main

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

    def fake_render_batch(specs, workdir):
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

    def fake_render_batch(specs, workdir):
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


def test_render_command_rejects_bad_spec(tmp_path, capsys):
    spec_path = _write_spec(tmp_path, {"title": "T", "beats": []})
    rc = main(["render", spec_path, "--workdir", str(tmp_path / "wd")])
    assert rc == 1
    assert "INVALID" in capsys.readouterr().err


def test_gen_skill_docs_command(tmp_path, capsys):
    rc = main(["gen-skill-docs", "--skill-dir", str(tmp_path / "skill")])
    assert rc == 0
    assert (tmp_path / "skill" / "reference" / "components.md").exists()
