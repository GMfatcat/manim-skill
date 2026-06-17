# Contract-Gap Backflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist each unresolved (escalated) beat's detail in the render manifest, then a deterministic `backflow` module + CLI that clusters those failures across runs by shared keyword and emits a "candidate components to add" report.

**Architecture:** `render_batch` records `TIER_UNRESOLVED` beats (index/component/caption/error/code, truncated) into each concept's manifest entry. A new pure module `manim_skill/backflow.py` reads `output.zip` manifests under given paths, flattens the unresolved beats, and groups them by shared keyword (stopword-filtered, frequency-ranked). A `manim-skill backflow` CLI renders the clusters as a markdown report. No LLM, no Docker — lexical + manifest only.

**Tech Stack:** Python 3.13, stdlib `zipfile`/`json`/`re`, dataclasses, pytest (fast suite — render is monkeypatched, manifests are hand-built zips).

---

## Background for the implementer

Final increment of the Contract-Gated Cascade framework (spec: `docs/superpowers/specs/2026-06-17-contract-gap-backflow-design.md`). The tier-metrics layer already detects *that* escalation is high (`escalation_quota`/`over_quota`); this surfaces *what* to add: it clusters the raw beats that kept failing into candidate-component suggestions. The tool surfaces the signal; the agent/human names and builds the component.

Key existing pieces:
- `manim_skill/render/jobs.py`: `BeatJob` has `beat` (a `Beat` with `component`, `code`, `caption`), `status`, `error`, and `tier` (set by the render backend).
- `manim_skill/render/metrics.py`: tier constant `TIER_UNRESOLVED = "unresolved"`.
- `manim_skill/render/backend.py`: `render_batch` builds a `BundleEntry` per clip (already passing `tier_counts=per_clip["tier_counts"]`) and calls `bundle_clips(entries, ..., summary=metrics)`.
- `manim_skill/render/bundle.py`: `BundleEntry(concept, mp4_path, gif_path, status, tier_counts=None)`; `bundle_clips(entries, output_zip, summary=None)` writes a `manifest.json` whose `concepts` list holds per-concept records (`concept`, `status`, `tier_counts`, `files`).
- Test harness `tests/render/test_backend.py`: `_patch_docker_fns(monkeypatch, render_fn=...)`, `_fake_render_raises` (forces a render failure), `_fake_render_spec_to_mp4`. Building manifests/zips in tests uses stdlib `zipfile`.
- CLI `manim_skill/cli.py`: subcommands are added with `sub.add_parser(name, help=...)`, args via `add_argument`, dispatch via `set_defaults(func=...)`; each `_cmd_*` returns an int.

Run the fast suite with: `pytest -m "not docker" -q`

Everything is additive and degrades gracefully: no unresolved beats → empty lists; old manifests without the field → skipped; no recurring keywords → empty report.

---

## File Structure

- **Modify** `manim_skill/render/bundle.py` — `BundleEntry.unresolved_beats` + write it into the manifest record.
- **Modify** `manim_skill/render/backend.py` — collect `TIER_UNRESOLVED` beat records per clip into the `BundleEntry`.
- **Create** `manim_skill/backflow.py` — `Escalation`, `collect_escalations`, `Cluster`, `cluster_escalations`, `render_report` (pure; no Docker/LLM).
- **Modify** `manim_skill/cli.py` — `backflow` subcommand.
- **Test** `tests/render/test_backend.py` (extend), `tests/render/test_bundle.py` (extend), `tests/test_backflow.py` (create).

---

## Task 1: Record unresolved beats in the manifest

**Files:**
- Modify: `manim_skill/render/bundle.py` (`BundleEntry`, `bundle_clips`)
- Test: `tests/render/test_bundle.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/render/test_bundle.py`:

```python
def test_bundle_clips_records_unresolved_beats(tmp_path):
    entry = BundleEntry(
        concept="C",
        mp4_path=None,
        gif_path=None,
        status="failed",
        unresolved_beats=[
            {"index": 0, "component": "raw", "caption": "bar chart",
             "error": "boom", "code": "Rectangle()"}
        ],
    )
    out = bundle_clips([entry], tmp_path / "out.zip")
    with zipfile.ZipFile(out) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    rec = manifest["concepts"][0]
    assert rec["unresolved_beats"][0]["caption"] == "bar chart"
    assert rec["unresolved_beats"][0]["index"] == 0


def test_bundle_clips_unresolved_beats_defaults_empty(tmp_path):
    entry = BundleEntry(concept="C", mp4_path=None, gif_path=None, status="done")
    out = bundle_clips([entry], tmp_path / "out.zip")
    with zipfile.ZipFile(out) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["concepts"][0]["unresolved_beats"] == []
```

(`zipfile`, `json`, and `BundleEntry`/`bundle_clips` are already imported at the top of this test file.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/render/test_bundle.py -k unresolved -v`
Expected: FAIL — `BundleEntry` has no `unresolved_beats`.

- [ ] **Step 3: Update `bundle.py`**

In `manim_skill/render/bundle.py`, add the field to `BundleEntry`:

```python
@dataclass
class BundleEntry:
    concept: str
    mp4_path: Path | None
    gif_path: Path | None
    status: str
    tier_counts: dict | None = None
    unresolved_beats: list[dict] | None = None
```

In `bundle_clips`, add `unresolved_beats` to the per-concept `record` dict (alongside the existing `tier_counts` line):

```python
            record: dict = {
                "concept": entry.concept,
                "status": entry.status,
                "tier_counts": entry.tier_counts or {},
                "unresolved_beats": entry.unresolved_beats or [],
                "files": [],
            }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/render/test_bundle.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add manim_skill/render/bundle.py tests/render/test_bundle.py
git commit -m "feat(render): record unresolved beats in the manifest"
```

---

## Task 2: Populate unresolved beats from `render_batch`

**Files:**
- Modify: `manim_skill/render/backend.py`
- Test: `tests/render/test_backend.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/render/test_backend.py`:

```python
def test_render_batch_writes_unresolved_beats_to_manifest(tmp_path, monkeypatch):
    _patch_docker_fns(monkeypatch, render_fn=_fake_render_raises)
    specs = [
        SceneSpec(
            title="C",
            beats=[Beat(component="raw", code="Rectangle()", caption="bar chart compare")],
        )
    ]
    batch = render_batch(specs, tmp_path)
    import json
    import zipfile

    with zipfile.ZipFile(batch.zip_path) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    ubs = manifest["concepts"][0]["unresolved_beats"]
    assert len(ubs) == 1
    assert ubs[0]["index"] == 0
    assert ubs[0]["component"] == "raw"
    assert ubs[0]["caption"] == "bar chart compare"
    assert ubs[0]["code"] == "Rectangle()"
    assert ubs[0]["error"]  # non-empty traceback/message
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/render/test_backend.py::test_render_batch_writes_unresolved_beats_to_manifest -v`
Expected: FAIL — `unresolved_beats` is `[]` (not yet populated).

- [ ] **Step 3: Add the collector and wire it in**

In `manim_skill/render/backend.py`, add this helper above `render_batch` (it uses `TIER_UNRESOLVED`, already imported from `metrics`):

```python
def _unresolved_records(clip: ClipJob) -> list[dict]:
    """Detail of each beat that failed every tier (escalation candidates)."""
    records = []
    for index, bj in enumerate(clip.beat_jobs):
        if bj.tier == TIER_UNRESOLVED:
            records.append(
                {
                    "index": index,
                    "component": bj.beat.component,
                    "caption": bj.beat.caption,
                    "error": (bj.error or "")[:500],
                    "code": (bj.beat.code or "")[:500],
                }
            )
    return records
```

Then in `render_batch`, in the `entries = [...]` comprehension, add the `unresolved_beats` argument:

```python
    entries = [
        BundleEntry(
            concept=clip.concept,
            mp4_path=clip.mp4_path,
            gif_path=clip.gif_path,
            status=clip.status.value,
            tier_counts=per_clip["tier_counts"],
            unresolved_beats=_unresolved_records(clip),
        )
        for clip, per_clip in zip(clip_jobs, metrics["per_clip"])
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/render/test_backend.py::test_render_batch_writes_unresolved_beats_to_manifest -v`
Expected: PASS

- [ ] **Step 5: Run the render suite (no regressions)**

Run: `pytest tests/render/ -m "not docker" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add manim_skill/render/backend.py tests/render/test_backend.py
git commit -m "feat(render): populate manifest unresolved_beats from escalated BeatJobs"
```

---

## Task 3: `backflow.py` — collect + cluster

**Files:**
- Create: `manim_skill/backflow.py`
- Test: `tests/test_backflow.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_backflow.py`:

```python
import json
import zipfile

from manim_skill.backflow import (
    Escalation,
    cluster_escalations,
    collect_escalations,
)


def _write_zip(path, manifest):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))


def _manifest(*unresolved):
    return {"concepts": [{"concept": "C", "status": "failed",
                          "unresolved_beats": list(unresolved)}]}


def _ub(code, caption="cap"):
    return {"index": 0, "component": "raw", "caption": caption,
            "error": "boom", "code": code}


def test_collect_escalations_reads_zip_in_dir(tmp_path):
    run = tmp_path / "run1"
    run.mkdir()
    _write_zip(run / "output.zip", _manifest(_ub("Rectangle bar chart")))
    escs = collect_escalations([tmp_path])
    assert len(escs) == 1
    assert isinstance(escs[0], Escalation)
    assert escs[0].code == "Rectangle bar chart"
    assert escs[0].concept == "C"


def test_collect_escalations_old_manifest_without_field(tmp_path):
    _write_zip(tmp_path / "output.zip", {"concepts": [{"concept": "C", "status": "done"}]})
    assert collect_escalations([tmp_path]) == []


def test_collect_escalations_skips_bad_zip(tmp_path):
    (tmp_path / "output.zip").write_text("not a zip", encoding="utf-8")
    assert collect_escalations([tmp_path]) == []


def test_cluster_escalations_groups_by_shared_keyword():
    escs = [
        Escalation("z", "C", 0, "raw", "a bar chart", "draw bars", "boom"),
        Escalation("z", "C", 1, "raw", "another bar", "more bars here", "boom"),
        Escalation("z", "C", 2, "raw", "a timeline", "events on a line", "boom"),
    ]
    clusters = cluster_escalations(escs, min_count=2)
    assert clusters[0].keyword == "bar"
    assert clusters[0].count == 2
    # 'timeline' appears once -> below min_count -> not a cluster
    assert all(c.keyword != "timeline" for c in clusters)


def test_cluster_escalations_filters_stopwords():
    escs = [
        Escalation("z", "C", 0, "raw", "self play", "self.play(Create(x))", "boom"),
        Escalation("z", "C", 1, "raw", "self play", "self.play(Create(y))", "boom"),
    ]
    clusters = cluster_escalations(escs, min_count=2)
    kws = {c.keyword for c in clusters}
    assert "self" not in kws and "play" not in kws and "create" not in kws


def test_cluster_escalations_ranked_and_empty():
    assert cluster_escalations([], min_count=2) == []
    escs = [Escalation("z", "C", 0, "raw", "lonely", "unique", "boom")]
    assert cluster_escalations(escs, min_count=2) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_backflow.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'manim_skill.backflow'`

- [ ] **Step 3: Create the module**

Create `manim_skill/backflow.py`:

```python
from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

_WORD = re.compile(r"\w+")

# Common manim / python / english noise (3+ chars; shorter tokens are dropped
# by the length>=3 filter). Keeps domain words (bar, tree, timeline, matrix)
# surfacing instead of the boilerplate every raw beat contains.
_STOPWORDS = frozenset({
    "self", "play", "add", "create", "wait", "scene", "vgroup", "text",
    "color", "animate", "run_time", "import", "numpy", "math", "def",
    "return", "for", "the", "and", "with", "next_to", "shift", "set",
    "fill", "stroke", "mobject", "group", "new", "get", "this", "that",
    "fadein", "fadeout", "transform", "label",
})


@dataclass
class Escalation:
    source: str
    concept: str
    index: int
    component: str
    caption: str | None
    code: str
    error: str


@dataclass
class Cluster:
    keyword: str
    count: int
    samples: list[Escalation]


def collect_escalations(paths) -> list[Escalation]:
    """Flatten every manifest's `unresolved_beats` under the given paths.

    Each path may be a directory (scanned recursively for `output.zip`) or a
    `.zip` file. Bad zips, missing `manifest.json`, and old manifests without
    the `unresolved_beats` field are skipped silently.
    """
    escalations: list[Escalation] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            zips = sorted(p.rglob("output.zip"))
        elif p.suffix == ".zip" and p.is_file():
            zips = [p]
        else:
            zips = []
        for zp in zips:
            try:
                with zipfile.ZipFile(zp) as zf:
                    manifest = json.loads(zf.read("manifest.json"))
            except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, OSError):
                continue
            for concept in manifest.get("concepts", []):
                name = concept.get("concept", "")
                for ub in concept.get("unresolved_beats") or []:
                    escalations.append(
                        Escalation(
                            source=str(zp),
                            concept=name,
                            index=ub.get("index", -1),
                            component=ub.get("component", ""),
                            caption=ub.get("caption"),
                            code=ub.get("code", ""),
                            error=ub.get("error", ""),
                        )
                    )
    return escalations


def _keywords(text: str) -> set[str]:
    return {
        w
        for w in _WORD.findall((text or "").lower())
        if len(w) >= 3 and w not in _STOPWORDS
    }


def cluster_escalations(
    escalations: list[Escalation], *, min_count: int = 2, max_samples: int = 3
) -> list[Cluster]:
    """Group escalations by shared keyword (from caption + code).

    A keyword that recurs across at least `min_count` escalations becomes a
    cluster — a candidate-component signal. Clusters are sorted by recurrence
    (desc) then keyword (asc). Returns [] when nothing recurs.
    """
    groups: dict[str, list[Escalation]] = {}
    for esc in escalations:
        for kw in _keywords(f"{esc.caption or ''} {esc.code}"):
            groups.setdefault(kw, []).append(esc)
    clusters = [
        Cluster(keyword=kw, count=len(group), samples=group[:max_samples])
        for kw, group in groups.items()
        if len(group) >= min_count
    ]
    clusters.sort(key=lambda c: (-c.count, c.keyword))
    return clusters
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_backflow.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add manim_skill/backflow.py tests/test_backflow.py
git commit -m "feat(backflow): collect + lexically cluster escalated beats"
```

---

## Task 4: Report formatting + `backflow` CLI subcommand

**Files:**
- Modify: `manim_skill/backflow.py` (add `render_report`)
- Modify: `manim_skill/cli.py` (`_cmd_backflow` + subparser)
- Test: `tests/test_backflow.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_backflow.py`:

```python
from manim_skill.backflow import Cluster, render_report


def test_render_report_lists_patterns():
    clusters = [
        Cluster("bar", 3, [Escalation("z", "Perf", 0, "raw", "a bar chart", "bars", "e")])
    ]
    report = render_report(clusters, total=5, runs=2)
    assert "Contract-gap report" in report
    assert "5 unresolved" in report
    assert "**bar** (3" in report
    assert "a bar chart" in report


def test_render_report_no_gaps():
    report = render_report([], total=0, runs=0)
    assert "No recurring contract gaps found." in report
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_backflow.py -k report -v`
Expected: FAIL — `cannot import name 'render_report'`

- [ ] **Step 3: Add `render_report` to `backflow.py`**

Append to `manim_skill/backflow.py`:

```python
def render_report(clusters: list[Cluster], *, total: int, runs: int) -> str:
    """Render clusters as a markdown contract-gap report."""
    lines = ["# Contract-gap report", ""]
    lines.append(f"{total} unresolved beat(s) across {runs} run(s).")
    lines.append("")
    if not clusters:
        lines.append("No recurring contract gaps found.")
        return "\n".join(lines) + "\n"
    lines.append("## Recurring patterns (candidate components)")
    lines.append("")
    for cluster in clusters:
        lines.append(f"- **{cluster.keyword}** ({cluster.count}×)")
        for sample in cluster.samples:
            caption = sample.caption or "(no caption)"
            lines.append(f"    - {caption}  — {sample.concept} [{sample.source}]")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_backflow.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Add the CLI subcommand**

In `manim_skill/cli.py`, add the import near the top imports:

```python
from manim_skill.backflow import cluster_escalations, collect_escalations, render_report
```

Add the command handler (near the other `_cmd_*` functions):

```python
def _cmd_backflow(args) -> int:
    """Cluster repeated unresolved beats into candidate-component suggestions."""
    escalations = collect_escalations(args.paths)
    runs = len({e.source for e in escalations})
    clusters = cluster_escalations(escalations, min_count=args.min_count)
    report = render_report(clusters, total=len(escalations), runs=runs)
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"backflow: wrote {args.output} ({len(clusters)} pattern(s))")
    else:
        print(report)
    return 0
```

Register the subparser (with the other `sub.add_parser(...)` blocks, before `args = parser.parse_args()`):

```python
    p_backflow = sub.add_parser(
        "backflow",
        help="cluster repeated unresolved beats into candidate-component suggestions",
    )
    p_backflow.add_argument(
        "paths", nargs="+", help="dirs (scanned for output.zip) or zip files"
    )
    p_backflow.add_argument(
        "--min-count", type=int, default=2,
        help="minimum recurrences for a pattern to be reported (default 2)",
    )
    p_backflow.add_argument(
        "-o", "--output", default=None,
        help="write the markdown report to a file instead of stdout",
    )
    p_backflow.set_defaults(func=_cmd_backflow)
```

- [ ] **Step 6: Verify the CLI wires up**

Run: `python -c "import manim_skill.cli"` then `manim-skill backflow --help`
Expected: no import error; `--help` shows `paths`, `--min-count`, `-o/--output`.

- [ ] **Step 7: Run the full fast suite (no regressions)**

Run: `pytest -m "not docker" -q`
Expected: PASS (all fast tests green)

- [ ] **Step 8: Commit**

```bash
git add manim_skill/backflow.py manim_skill/cli.py tests/test_backflow.py
git commit -m "feat(cli): manim-skill backflow — contract-gap report"
```

---

## Self-Review notes (already applied)

- **Spec coverage:** §1 manifest persistence → Tasks 1 (bundle field) + 2 (backend populates from `TIER_UNRESOLVED`). §2 `backflow.py` collect + cluster → Task 3. §3 CLI + report → Task 4. §4 tests → present in every task (manifest write via fake-render, collect from hand-built zips, cluster math, report formatting, CLI help). Out-of-scope per spec (LLM naming, auto-build, embeddings, service-side aggregation) correctly absent.
- **Backward compatibility:** `unresolved_beats` defaults to `None`/`[]`; `collect_escalations` skips manifests without the field; everything returns `[]` on no data. No existing caller of `BundleEntry`/`bundle_clips`/`render_batch` breaks.
- **Type consistency:** `Escalation(source, concept, index, component, caption, code, error)` and `Cluster(keyword, count, samples)` are used identically in `backflow.py`, its tests, and `render_report`; `collect_escalations`/`cluster_escalations(*, min_count, max_samples)`/`render_report(*, total, runs)` signatures match across Tasks 3–4; the manifest record keys (`index/component/caption/error/code`) written in Task 2 match the keys read in Task 3.
- **Stopwords:** a small fixed 3+-char set (manim/python/english noise); shorter tokens are dropped by the `len>=3` filter, so the set need not list `a/of/to`. Goal is surfacing domain words, not a complete NLP stoplist.
- **No placeholders:** every code/test step has complete content and exact run/expected lines.
