# Plan 5: CLI + Agent Skill 封裝 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把整個系統封裝成 agent 可用的 skill——一支 `manim-skill` CLI（`validate` / `catalog` / `render` / `gen-skill-docs`）加上 `skill/` 目錄（手寫的 `SKILL.md` + 從元件 schema 自動生成的 `reference/` 文件）。

**Architecture:** CLI 是渲染後端的薄 client（argparse dispatcher，每個子指令直接呼叫既有模組——`validate_spec`、`build_component_catalog`、`render_batch`、`generate_skill_docs`），不含 LLM：agent 路徑的智慧來自 agent 自己的 LLM，render 失敗時 CLI 回報錯誤、由 agent 重寫 spec 重送。`reference/` 文件由 `skill_docs.py` 從元件的 Pydantic schema 自動生成，一個「committed 文件是否最新」的測試偵測 drift。

**Tech Stack:** Python ≥3.12 stdlib `argparse`、setuptools console_scripts entry point、pytest、Docker（僅端到端測試）。

---

## 背景：Plan 1–4 已完成的部分（`main` 分支，137 測試）

- `manim_skill/spec/` — `parse_spec_text(text) -> dict` + `SpecParseError`；`validate_spec(raw) -> SceneSpec` + `SpecValidationError`；`SceneSpec`/`Beat`（Pydantic v2，有 `.model_json_schema()`）。
- `manim_skill/components/` — 9 個元件自動註冊。
- `manim_skill/render/` — `render_batch(specs, workdir, *, max_workers=3, cache=None, repairer=None) -> BatchJob`；`jobs.py`：`JobStatus`/`BatchJob`（`clip_jobs`、`status`、`zip_path`）/`ClipJob`（`concept`、`spec`、`beat_jobs`、`status`、`mp4_path`、`gif_path`、`error`）/`BeatJob`。
- `manim_skill/llm/` — `catalog.py`：`build_component_catalog() -> str`；以及 client/analyze/codegen/repair/pipeline。
- `pyproject.toml` — `[project]` 有 `dependencies`、`[project.optional-dependencies]`、`[build-system]`、`[tool.setuptools.packages.find]`、`[tool.pytest.ini_options]`。
- 測試：`tests/<subpkg>/` 與 `tests/` 根目錄都有（如 `tests/test_smoke.py`）。`docker` marker 已註冊。

環境：Windows、Docker Desktop、Python 3.13。

## 範圍界定

- **包含：** `skill_docs.py`（reference 文件生成）、`manim_skill/cli.py`（4 個子指令）、`pyproject.toml` 的 console_scripts entry point、`skill/SKILL.md`、自動生成並 commit 的 `skill/reference/*.md`、drift 偵測測試、CLI 端到端 docker 測試。
- **不包含：** CLI 不做 analyze/codegen/repair（那是 Plan 4 的 `run_pipeline`，Web 路徑用）；不做 MCP server（依設計與使用者偏好，agent 整合走 CLI）。

## File Structure

```
pyproject.toml                       修改 — 加 [project.scripts] entry point
.dockerignore                        修改 — 排除 skill/（非套件，不需進 image）
manim_skill/skill_docs.py            新增 — render_components_doc / render_spec_format_doc / generate_skill_docs
manim_skill/cli.py                   新增 — argparse CLI：validate / catalog / render / gen-skill-docs
skill/SKILL.md                       新增 — agent skill 指示（手寫）
skill/reference/components.md        新增 — 自動生成
skill/reference/spec-format.md       新增 — 自動生成
tests/test_skill_docs.py             新增
tests/test_cli.py                    新增
tests/test_skill_reference_current.py 新增 — drift 偵測
tests/test_cli_e2e.py                新增 — docker 端到端
```

---

## Task 1: skill_docs.py — reference 文件生成

從元件的 Pydantic schema 自動生成 agent skill 的 reference 文件。純 Python，無 docker。

**Files:**
- Create: `manim_skill/skill_docs.py`
- Create: `tests/test_skill_docs.py`

- [ ] **Step 1: 寫失敗測試** — `tests/test_skill_docs.py`:

```python
from manim_skill.skill_docs import (
    generate_skill_docs,
    render_components_doc,
    render_spec_format_doc,
)


def test_components_doc_lists_components():
    doc = render_components_doc()
    assert doc.startswith("# Component Reference")
    assert "TextBeat" in doc
    assert "FormulaBreakdown" in doc


def test_spec_format_doc_has_schema_and_example():
    doc = render_spec_format_doc()
    assert doc.startswith("# Scene Spec Format")
    assert "SceneSpec schema" in doc
    assert "Beat schema" in doc
    assert "## Example" in doc


def test_example_spec_is_valid():
    # The example embedded in the spec-format doc must itself validate.
    from manim_skill.skill_docs import _EXAMPLE_SPEC
    from manim_skill.spec.validate import validate_spec

    validate_spec(_EXAMPLE_SPEC)  # must not raise


def test_generate_skill_docs_writes_reference_files(tmp_path):
    written = generate_skill_docs(tmp_path)
    assert len(written) == 2
    components = tmp_path / "reference" / "components.md"
    spec_format = tmp_path / "reference" / "spec-format.md"
    assert components.exists()
    assert spec_format.exists()
    assert "TextBeat" in components.read_text(encoding="utf-8")


def test_generate_skill_docs_creates_missing_dir(tmp_path):
    target = tmp_path / "nested" / "skill"
    generate_skill_docs(target)
    assert (target / "reference" / "components.md").exists()
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/test_skill_docs.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 實作** — `manim_skill/skill_docs.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from manim_skill.llm.catalog import build_component_catalog
from manim_skill.spec.schema import Beat, SceneSpec

_EXAMPLE_SPEC: dict = {
    "title": "Self-Attention",
    "aspect_ratio": "16:9",
    "beats": [
        {
            "component": "TextBeat",
            "params": {"text": "Self-Attention", "style": "title"},
            "caption": "Intro",
            "duration": 2.0,
        },
        {
            "component": "raw",
            "code": "c = Circle()\nself.play(Create(c))",
            "duration": 3.0,
        },
    ],
}


def render_components_doc() -> str:
    """The component reference: every component's params schema.

    Reuses build_component_catalog() so this never drifts from the code.
    """
    return (
        "# Component Reference\n\n"
        "Each component below can be used as a beat's `component` in a "
        "scene spec. A beat's `params` must match the component's "
        "params schema.\n\n"
        + build_component_catalog()
        + "\n"
    )


def render_spec_format_doc() -> str:
    """The scene spec format reference: schema + a worked example."""
    scene_schema = json.dumps(
        SceneSpec.model_json_schema(), ensure_ascii=False, indent=2
    )
    beat_schema = json.dumps(
        Beat.model_json_schema(), ensure_ascii=False, indent=2
    )
    example = json.dumps(_EXAMPLE_SPEC, ensure_ascii=False, indent=2)
    return (
        "# Scene Spec Format\n\n"
        "A scene spec is a JSON object describing one animation clip. "
        "It has a `title`, an optional `aspect_ratio` (default "
        "`16:9`), and a non-empty list of `beats`. Each beat names a "
        "`component` (see the component reference) or `raw` with a "
        "`code` field of manim Python where the scene is `self`.\n\n"
        "## SceneSpec schema\n\n```json\n" + scene_schema + "\n```\n\n"
        "## Beat schema\n\n```json\n" + beat_schema + "\n```\n\n"
        "## Example\n\n```json\n" + example + "\n```\n"
    )


def generate_skill_docs(skill_dir) -> list[Path]:
    """Write the auto-generated reference docs under <skill_dir>/reference/.

    Returns the list of written file paths. SKILL.md itself is
    hand-written and is not touched here.
    """
    reference_dir = Path(skill_dir) / "reference"
    reference_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, content in (
        ("components.md", render_components_doc()),
        ("spec-format.md", render_spec_format_doc()),
    ):
        path = reference_dir / name
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/test_skill_docs.py -v` → expect PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/skill_docs.py tests/test_skill_docs.py
git commit -m "feat: skill docs generation from component schemas"
```

---

## Task 2: manim_skill/cli.py — CLI

argparse CLI，4 個子指令，加 console_scripts entry point。

**Files:**
- Create: `manim_skill/cli.py`
- Modify: `pyproject.toml`
- Create: `tests/test_cli.py`

- [ ] **Step 1: 寫失敗測試** — `tests/test_cli.py`:

```python
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
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/test_cli.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 實作** — `manim_skill/cli.py`:

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from manim_skill.llm.catalog import build_component_catalog
from manim_skill.render.backend import render_batch
from manim_skill.render.jobs import JobStatus
from manim_skill.skill_docs import generate_skill_docs
from manim_skill.spec.parse import SpecParseError, parse_spec_text
from manim_skill.spec.validate import SpecValidationError, validate_spec


def _load_spec(spec_path: str):
    text = Path(spec_path).read_text(encoding="utf-8")
    return validate_spec(parse_spec_text(text))


def _cmd_validate(args) -> int:
    try:
        spec = _load_spec(args.spec)
    except (SpecParseError, SpecValidationError, OSError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {len(spec.beats)} beat(s), title={spec.title!r}")
    return 0


def _cmd_catalog(args) -> int:
    print(build_component_catalog())
    return 0


def _cmd_render(args) -> int:
    try:
        spec = _load_spec(args.spec)
    except (SpecParseError, SpecValidationError, OSError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    batch = render_batch([spec], Path(args.workdir))
    clip = batch.clip_jobs[0]
    if clip.status == JobStatus.DONE:
        print(f"mp4: {clip.mp4_path}")
        print(f"gif: {clip.gif_path}")
        print(f"zip: {batch.zip_path}")
        return 0
    print(f"RENDER FAILED: {clip.error}", file=sys.stderr)
    return 1


def _cmd_gen_skill_docs(args) -> int:
    written = generate_skill_docs(args.skill_dir)
    for path in written:
        print(f"wrote {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="manim-skill",
        description="Turn manim scene specs into rendered animations.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="validate a scene spec")
    p_validate.add_argument("spec", help="path to a scene spec JSON file")
    p_validate.set_defaults(func=_cmd_validate)

    p_catalog = sub.add_parser(
        "catalog", help="print the component catalog"
    )
    p_catalog.set_defaults(func=_cmd_catalog)

    p_render = sub.add_parser("render", help="render a scene spec")
    p_render.add_argument("spec", help="path to a scene spec JSON file")
    p_render.add_argument(
        "--workdir",
        default="manim_skill_out",
        help="working/output directory (default: manim_skill_out)",
    )
    p_render.set_defaults(func=_cmd_render)

    p_gen = sub.add_parser(
        "gen-skill-docs",
        help="regenerate the agent skill reference docs",
    )
    p_gen.add_argument(
        "--skill-dir",
        default="skill",
        help="the skill directory (default: skill)",
    )
    p_gen.set_defaults(func=_cmd_gen_skill_docs)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 加 console_scripts entry point 到 `pyproject.toml`** — 在 `[project.optional-dependencies]` 區塊**之後**插入：

```toml
[project.scripts]
manim-skill = "manim_skill.cli:main"
```

- [ ] **Step 5: 重新安裝以註冊 entry point** — Run: `pip install -e ".[dev]"` → expect 成功。

- [ ] **Step 6: 執行測試確認通過** — `pytest tests/test_cli.py -v` → expect PASS (8 passed).

- [ ] **Step 7: 驗證 console script 已註冊** — Run: `manim-skill catalog`
  Expected: 印出元件目錄（含 `TextBeat` 等），exit 0。這證明 `[project.scripts]` entry point 生效。

- [ ] **Step 8: 執行完整非 docker 套件確認無回歸** — `pytest -m "not docker" -q` → expect 全部 PASS.

- [ ] **Step 9: Commit**

```bash
git add manim_skill/cli.py pyproject.toml tests/test_cli.py
git commit -m "feat: manim-skill CLI (validate / catalog / render / gen-skill-docs)"
```

---

## Task 3: skill/ 目錄 — SKILL.md + 生成的 reference 文件

手寫 `SKILL.md`，用 CLI 生成 `reference/*.md`，commit 整個 `skill/`，並加一個 drift 偵測測試。

**Files:**
- Create: `skill/SKILL.md`
- Create: `skill/reference/components.md`（由 CLI 生成）
- Create: `skill/reference/spec-format.md`（由 CLI 生成）
- Modify: `.dockerignore`
- Create: `tests/test_skill_reference_current.py`

- [ ] **Step 1: 寫 `skill/SKILL.md`**（手寫，照以下內容）:

```markdown
---
name: manim-skill
description: Turn a concept into a manim animation. Use when you need an explanatory animation (for slides or a README) of a math concept, an AI/ML paper idea, or a code snippet — you write a "scene spec" JSON and this skill renders it to mp4 + gif.
---

# manim-skill

Produce a short manim animation by writing a **scene spec** (a JSON file) and rendering it with the `manim-skill` CLI. You (the agent) write the spec; this skill validates and renders it. There is no model dependency — the intelligence is you.

## Workflow

1. **Learn the vocabulary.** Run `manim-skill catalog` to see the available components and their parameter schemas. Read `reference/spec-format.md` for the scene spec format and `reference/components.md` for the full component reference.
2. **Write a scene spec** — a JSON file with a `title` and a non-empty list of `beats`. Each beat is either a library component (preferred) or a `raw` beat with manim Python code. Use `raw` only when no component fits.
3. **Validate it.** Run `manim-skill validate path/to/spec.json`. Fix anything it reports.
4. **Render it.** Run `manim-skill render path/to/spec.json --workdir OUTDIR`. On success it prints the mp4, gif, and zip paths. On a render failure it prints the error — fix the spec (most often a `raw` beat's code) and render again.

## Commands

- `manim-skill catalog` — print the component catalog.
- `manim-skill validate <spec.json>` — validate a spec without rendering.
- `manim-skill render <spec.json> [--workdir DIR]` — render a spec to mp4 + gif (also bundled in a zip).
- `manim-skill gen-skill-docs [--skill-dir DIR]` — regenerate `reference/` from the current component code.

## Notes

- A `raw` beat runs arbitrary manim Python inside a sandboxed Docker container; the scene is `self`.
- If a `raw` beat fails to render, `manim-skill render` reports the traceback — that is your repair signal: rewrite the code and render again.
- The `reference/` docs are generated from the component code (`manim-skill gen-skill-docs`), so they never drift.
```

- [ ] **Step 2: 用 CLI 生成 reference 文件** — Run: `manim-skill gen-skill-docs --skill-dir skill`
  Expected: 印出 `wrote skill/reference/components.md` 與 `wrote skill/reference/spec-format.md`；兩個檔案被建立。

- [ ] **Step 3: 把 `skill/` 加入 `.dockerignore`** — `.dockerignore` 目前內容是：

```
.git
.superpowers
docs
tests
**/__pycache__
*.pyc
.pytest_cache
*.egg-info
```

在 `docs` 那行之後加一行 `skill`，使其變成：

```
.git
.superpowers
docs
skill
tests
**/__pycache__
*.pyc
.pytest_cache
*.egg-info
```

（`skill/` 是文件目錄、不是 Python 套件，不需要進渲染 image。）

- [ ] **Step 4: 寫 drift 偵測測試** — `tests/test_skill_reference_current.py`:

```python
from pathlib import Path

from manim_skill.skill_docs import render_components_doc, render_spec_format_doc

_SKILL_REF = Path(__file__).resolve().parent.parent / "skill" / "reference"


def test_committed_components_doc_is_current():
    committed = (_SKILL_REF / "components.md").read_text(encoding="utf-8")
    assert committed == render_components_doc(), (
        "skill/reference/components.md is stale — "
        "run `manim-skill gen-skill-docs`"
    )


def test_committed_spec_format_doc_is_current():
    committed = (_SKILL_REF / "spec-format.md").read_text(encoding="utf-8")
    assert committed == render_spec_format_doc(), (
        "skill/reference/spec-format.md is stale — "
        "run `manim-skill gen-skill-docs`"
    )
```

- [ ] **Step 5: 執行 drift 測試確認通過** — `pytest tests/test_skill_reference_current.py -v`
  Expected: PASS (2 passed)。`read_text` 在讀取時會把 `\r\n` 正規化成 `\n`，與生成函式的 `\n` 輸出一致，所以這個比對對 Windows 的 CRLF 是穩健的。

- [ ] **Step 6: 執行完整非 docker 套件確認無回歸** — `pytest -m "not docker" -q` → expect 全部 PASS.

- [ ] **Step 7: Commit**

```bash
git add skill/ .dockerignore tests/test_skill_reference_current.py
git commit -m "feat: agent skill directory (SKILL.md + generated reference)"
```

---

## Task 4: CLI 端到端 Docker 整合測試

用真實 docker 跑 `manim-skill render`，驗證 CLI 真的能把一份 spec 渲染出來。

**Files:**
- Create: `tests/test_cli_e2e.py`

- [ ] **Step 1: 寫測試** — `tests/test_cli_e2e.py`:

```python
import json
import sys
from pathlib import Path

import pytest


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

    result = subprocess_run(spec_path, workdir)
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


def subprocess_run(spec_path, workdir):
    import subprocess

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
```

- [ ] **Step 2: 執行端到端測試** — `pytest tests/test_cli_e2e.py -v -m docker`
  Expected: PASS (1 passed)。會渲染一支真實影片，較慢，要耐心。

- [ ] **Step 3: 執行完整測試套件** — `pytest -q`
  Expected: 全部 PASS（含所有 docker 測試）。

- [ ] **Step 4: Commit**

```bash
git add tests/test_cli_e2e.py
git commit -m "test: CLI render end-to-end docker integration test"
```

---

## Self-Review

**1. Spec coverage（對照設計文件 §7 Agent Skill 封裝）**

- ① 知識 — `SKILL.md`：指示「寫 scene spec → validate → render」→ Task 3 ✓
- ① 知識 — `reference/components.md`：元件目錄 + 參數 schema，**從元件 schema 自動生成**（單一事實來源、不 drift）→ Task 1（`render_components_doc` 重用 `build_component_catalog`）+ Task 3（生成並 commit）+ drift 測試 ✓
- ① 知識 — `reference/spec-format.md`：spec 格式 + 範例 → Task 1（`render_spec_format_doc`，含 `SceneSpec`/`Beat` schema + 驗證過的範例）✓
- ② 介面 — CLI：`manim-skill render` / `catalog` / `validate`（加上 `gen-skill-docs` 用於再生成 reference）→ Task 2 ✓
- ② 介面 — CLI 是渲染後端的薄 client → Task 2（每個子指令直接呼叫既有模組，無新邏輯）✓
- 採 CLI 而非 MCP → 全程無 MCP（範圍界定已說明，符合設計與使用者偏好）✓
- agent skill 與 Web 路徑共用同一套 scene spec 契約、元件庫、渲染後端 → CLI 重用 `validate_spec`/`render_batch`/`build_component_catalog`，不另立契約 ✓
- raw .py 不另立特例 → CLI 吃的是 scene spec（raw 是其中一種 beat），無特例 ✓
- console_scripts entry point（`manim-skill` 指令可用）→ Task 2 Step 4/5/7 ✓

**不在範圍（已在範圍界定說明）：** CLI 不做 analyze/codegen/repair（Web 路徑用 Plan 4 的 `run_pipeline`）；無 MCP server。

**2. Placeholder scan：** 無 TBD/TODO。每個 step 都有完整程式碼或精確指令。Task 3 是「手寫 SKILL.md + 用 CLI 生成 reference + commit」型任務，每步都有精確內容或指令；`.dockerignore` 的修改給了精確的前後內容。Task 3 Step 5 註明了 drift 比對對 CRLF 的穩健性原因（`read_text` 正規化）。

**3. Type consistency：**
- `render_components_doc()`、`render_spec_format_doc()`、`generate_skill_docs(skill_dir) -> list[Path]`、`_EXAMPLE_SPEC`（Task 1）→ Task 2 `cli.py` import `generate_skill_docs`、Task 3 drift 測試 import `render_components_doc`/`render_spec_format_doc`，名稱一致。
- `cli.py` 的 `main(argv) -> int`、`build_parser`、`_cmd_*`、模組層級的 `render_batch`（Task 2）→ Task 2 測試 monkeypatch `cli_mod.render_batch`、Task 4 e2e 用 `python -m manim_skill.cli`，一致。
- 重用既有：`parse_spec_text`/`SpecParseError`、`validate_spec`/`SpecValidationError`、`build_component_catalog`、`render_batch`、`JobStatus`/`BatchJob`/`ClipJob`（`concept`/`spec`/`status`/`mp4_path`/`gif_path`/`error`/`zip_path` 欄位）—— 名稱與簽名與 Plan 1–4 既有程式一致。Task 2 測試建構 `ClipJob(concept=, spec=, status=, mp4_path=, gif_path=)` 與 `BatchJob(clip_jobs=, status=, zip_path=)` 對應 Plan 3 的 dataclass 欄位。
- `render_batch` 既有簽名是 `render_batch(specs, workdir, *, max_workers=3, cache=None, repairer=None)`；CLI 只用兩個位置參數 `render_batch([spec], Path(args.workdir))`，Task 2 測試的 `fake_render_batch(specs, workdir)` 簽名與此呼叫一致。

無不一致。

---

## Execution Handoff

Plan 完成並存於 `docs/superpowers/plans/2026-05-14-plan-5-cli-and-agent-skill.md`。兩種執行方式：

**1. Subagent-Driven（推薦，與 Plan 1–4 一致）** — 每 task 一個 subagent，task 之間由我審核。Plan 5 的 4 個 task 互相循序相依（Task 2 依賴 1、Task 3 依賴 1+2、Task 4 依賴 2），各自單獨執行，無平行波次。

**2. Inline Execution** — 在本對話 session 內逐 task 執行，分批設檢查點審核。

要用哪一種？
