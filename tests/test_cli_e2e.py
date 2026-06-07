import json
import subprocess
import sys
from pathlib import Path

import pytest


def _run_cli_render(spec_path, workdir):
    return subprocess.run(
        [
            sys.executable, "-m", "manim_skill.cli",
            "render", str(spec_path),
            "--workdir", str(workdir),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )


@pytest.mark.docker
def test_cli_render_produces_output(tmp_path):
    spec = {
        "title": "CLI E2E",
        "beats": [
            {
                "component": "TextBeat",
                "params": {"text": "Hello"},
                "duration": 1.0,
            }
        ],
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    workdir = tmp_path / "out"

    result = _run_cli_render(spec_path, workdir)
    assert result.returncode == 0, f"stderr:\n{result.stderr}"
    assert "mp4:" in result.stdout
    assert "gif:" in result.stdout
    assert "zip:" in result.stdout

    # the zip the CLI reported on the "zip:" line actually exists
    zip_line = next(
        line for line in result.stdout.splitlines()
        if line.startswith("zip:")
    )
    zip_path = Path(zip_line.split("zip:", 1)[1].strip())
    assert zip_path.exists()
    assert zip_path.stat().st_size > 0


def test_validate_prints_lint_warnings_but_exits_zero(tmp_path, capsys):
    import json
    from manim_skill.cli import main

    spec = {"title": "t", "aspect_ratio": "16:9", "beats": [{"component": "TextBeat", "params": {"text": "x"}, "caption": "w " * 40}]}
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(spec), encoding="utf-8")

    rc = main(["validate", str(p)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "caption_too_long" in (captured.out + captured.err)
