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


# --- analyze / codegen-concepts / bundle / demo ---------------------------


_ANALYZE_LLM_RESP = (
    '{"concepts": ['
    '{"concept": "C1", "why_suitable": "w", "storyboard": "s"},'
    '{"concept": "C2", "why_suitable": "w", "storyboard": "s"}'
    ']}'
)
_SPEC_LLM_RESP = (
    '{"title": "C1", "beats": [{"component": "TextBeat", '
    '"params": {"text": "Hello"}}]}'
)


def _stub_llm_factory(monkeypatch, responses):
    """Replace cli._build_llm_client_from_env with a FakeLLMClient."""
    from manim_skill.llm.client import FakeLLMClient

    client = FakeLLMClient(responses=list(responses))
    monkeypatch.setattr(cli_mod, "_build_llm_client_from_env", lambda: client)
    return client


def test_analyze_command_writes_concepts(tmp_path, monkeypatch, capsys):
    _stub_llm_factory(monkeypatch, [_ANALYZE_LLM_RESP])
    input_path = tmp_path / "in.txt"
    input_path.write_text("some content", encoding="utf-8")

    workdir = tmp_path / "wd"
    rc = main([
        "analyze", str(input_path), "--kind", "text", "-o", str(workdir),
    ])
    assert rc == 0
    concepts = json.loads((workdir / "concepts.json").read_text("utf-8"))
    assert len(concepts) == 2
    assert concepts[0]["concept"] == "C1"
    out = capsys.readouterr().out
    assert "2 concept" in out


def test_codegen_concepts_reads_concepts_and_writes_specs(
    tmp_path, monkeypatch, capsys
):
    workdir = tmp_path / "wd"
    workdir.mkdir()
    concepts_path = workdir / "concepts.json"
    concepts_path.write_text(
        json.dumps([
            {"concept": "C1", "why_suitable": "w", "storyboard": "s"},
            {"concept": "C2", "why_suitable": "w", "storyboard": "s"},
        ]),
        encoding="utf-8",
    )
    _stub_llm_factory(monkeypatch, [_SPEC_LLM_RESP, _SPEC_LLM_RESP])

    rc = main(["codegen-concepts", str(workdir)])
    assert rc == 0
    assert (workdir / "spec_00.json").exists()
    assert (workdir / "spec_01.json").exists()
    out = capsys.readouterr().out
    assert "2 spec" in out.lower() or "2 OK" in out


def test_codegen_concepts_indices_subset(tmp_path, monkeypatch):
    workdir = tmp_path / "wd"
    workdir.mkdir()
    (workdir / "concepts.json").write_text(
        json.dumps([
            {"concept": "C0", "why_suitable": "w", "storyboard": "s"},
            {"concept": "C1", "why_suitable": "w", "storyboard": "s"},
            {"concept": "C2", "why_suitable": "w", "storyboard": "s"},
        ]),
        encoding="utf-8",
    )
    _stub_llm_factory(monkeypatch, [_SPEC_LLM_RESP])

    rc = main(["codegen-concepts", str(workdir), "--indices", "1"])
    assert rc == 0
    assert not (workdir / "spec_00.json").exists()
    assert (workdir / "spec_01.json").exists()
    assert not (workdir / "spec_02.json").exists()


def test_bundle_command_renders_all_specs(tmp_path, monkeypatch):
    from manim_skill.render.jobs import BatchJob, ClipJob, JobStatus

    workdir = tmp_path / "wd"
    workdir.mkdir()
    for i, title in enumerate(("A", "B")):
        (workdir / f"spec_{i:02d}.json").write_text(
            json.dumps({
                "title": title,
                "beats": [{"component": "TextBeat", "params": {"text": "x"}}],
            }),
            encoding="utf-8",
        )

    captured = {}

    def fake_render_batch(specs, out_dir, *, quality="medium"):
        captured["count"] = len(specs)
        captured["quality"] = quality
        return BatchJob(
            clip_jobs=[
                ClipJob(concept=s.title, spec=s, status=JobStatus.DONE)
                for s in specs
            ],
            status=JobStatus.DONE,
            zip_path=Path(out_dir) / "output.zip",
        )

    monkeypatch.setattr(cli_mod, "render_batch", fake_render_batch)

    rc = main(["bundle", str(workdir), "--quality", "high"])
    assert rc == 0
    assert captured["count"] == 2
    assert captured["quality"] == "high"


def test_bundle_command_no_specs_fails(tmp_path, capsys):
    workdir = tmp_path / "wd"
    workdir.mkdir()
    rc = main(["bundle", str(workdir)])
    assert rc == 1
    assert "no spec" in capsys.readouterr().err.lower()


def test_demo_command_yes_flag_skips_prompt(tmp_path, monkeypatch, capsys):
    from manim_skill.render.jobs import BatchJob, JobStatus

    _stub_llm_factory(
        monkeypatch,
        [_ANALYZE_LLM_RESP, _SPEC_LLM_RESP, _SPEC_LLM_RESP],
    )

    def fake_render_batch(specs, out_dir, *, quality="medium"):
        return BatchJob(
            clip_jobs=[], status=JobStatus.DONE, zip_path=Path(out_dir) / "z.zip"
        )

    monkeypatch.setattr(cli_mod, "render_batch", fake_render_batch)

    # input() should NOT be called when --yes is passed.
    monkeypatch.setattr(
        "builtins.input",
        lambda *a, **k: pytest.fail("input() called despite --yes"),
    )

    input_path = tmp_path / "in.txt"
    input_path.write_text("x", encoding="utf-8")
    workdir = tmp_path / "wd"

    rc = main([
        "demo", str(input_path),
        "--kind", "text", "-o", str(workdir),
        "--yes",
    ])
    assert rc == 0


def test_demo_command_prompts_when_not_yes(tmp_path, monkeypatch):
    from manim_skill.render.jobs import BatchJob, JobStatus

    _stub_llm_factory(
        monkeypatch,
        [_ANALYZE_LLM_RESP, _SPEC_LLM_RESP, _SPEC_LLM_RESP],
    )

    def fake_render_batch(specs, out_dir, *, quality="medium"):
        return BatchJob(
            clip_jobs=[], status=JobStatus.DONE, zip_path=Path(out_dir) / "z.zip"
        )

    monkeypatch.setattr(cli_mod, "render_batch", fake_render_batch)

    prompts = []
    monkeypatch.setattr(
        "builtins.input", lambda prompt="": prompts.append(prompt) or ""
    )

    input_path = tmp_path / "in.txt"
    input_path.write_text("x", encoding="utf-8")
    workdir = tmp_path / "wd"

    rc = main([
        "demo", str(input_path),
        "--kind", "text", "-o", str(workdir),
    ])
    assert rc == 0
    assert len(prompts) >= 1  # at least one pause for review
