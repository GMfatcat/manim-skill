# Tier Metrics + Escalation Quota Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Instrument the render pipeline to record, per beat, which cost tier resolved it (L0 deterministic / L1 generated / L1 model-repaired / unresolved-escalation), aggregate that into a batch summary with an escalation rate, gate it against a configurable quota, and surface it in the manifest and CLI/eval output.

**Architecture:** A beat's resolution tier is observable inside `_render_beat_job` (component vs raw, cache hit, repair attempts, failure). We add a `tier` string to `BeatJob`, set it at each resolution point, aggregate with a pure `compute_tier_metrics(batch)` function, store the result on `BatchJob` + embed it in `manifest.json`, and emit a warning when the escalation rate exceeds an optional quota. No new model calls — this is pure measurement over data the pipeline already produces.

**Tech Stack:** Python 3.13, dataclasses, pytest (fast suite — render is monkeypatched, no Docker), existing `manim_skill/render/` modules.

---

## Background for the implementer

This implements the measurement layer of the "Contract-Gated Cascade" framework (`docs/superpowers/specs/2026-06-16-agent-openmodel-cost-cascade-design.md`). The framework's premise: cheap free tiers (L0 deterministic validation/repair, L1 local open models) should resolve most work; the expensive tier (L2 = paid copilot + human) is only for escalations. To manage that you must *measure where each unit of work gets resolved*. That measurement does not yet exist.

The render pipeline (`manim_skill/render/backend.py`) renders each beat independently. A beat resolves one of these ways, all observable in `_render_beat_job`:

- **component beat renders** → deterministic L0 win (model picked a safe component).
- **cache hit** → previously resolved, free this run.
- **raw beat renders on first try** (repair attempts == 1, or no repairer) → L1 generation.
- **raw beat renders after the repair loop** (repair attempts > 1) → L1 repair.
- **beat fails every attempt** → unresolved → escalation candidate (L2).

Tier string values (defined once in `metrics.py`, Task 2): `"deterministic"`, `"cached"`, `"generated"`, `"model_repaired"`, `"unresolved"`.

The escalation rate = unresolved beats ÷ total beats. The "free-tier rate" = everything except unresolved ÷ total. The quota gate compares the escalation rate to an optional threshold and warns (it does NOT abort — the batch has already run; the warning is the "stop hand-fixing, go strengthen the contract" signal described in the spec).

Run the fast suite with: `pytest -m "not docker" -q`

---

## File Structure

- **Modify** `manim_skill/render/jobs.py` — add `tier` to `BeatJob`; add `escalation_rate` + `over_quota` to `BatchJob`.
- **Create** `manim_skill/render/metrics.py` — tier constants + pure `compute_tier_metrics(batch) -> dict`.
- **Modify** `manim_skill/render/backend.py` — set `beat_job.tier` in `_render_beat_job`; compute metrics, set quota flag, embed summary in `render_batch`.
- **Modify** `manim_skill/render/bundle.py` — `BundleEntry.tier_counts` + `summary` param embedded into `manifest.json`.
- **Modify** `manim_skill/cli.py` — print tier distribution in `_cmd_bundle`.
- **Modify** `scripts/eval/bundle_specs.py` — `--escalation-quota` flag + print metrics.
- **Test** `tests/render/test_metrics.py` (create), `tests/render/test_backend.py` (extend), `tests/render/test_bundle.py` (extend).

---

## Task 1: Add `tier` field to `BeatJob`

**Files:**
- Modify: `manim_skill/render/jobs.py:17-22`
- Test: `tests/render/test_metrics.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/render/test_metrics.py`:

```python
from manim_skill.render.jobs import BeatJob
from manim_skill.spec.schema import Beat


def test_beatjob_has_tier_field_defaulting_to_none():
    bj = BeatJob(beat=Beat(component="raw", code="self.wait(1)"))
    assert bj.tier is None
    bj.tier = "generated"
    assert bj.tier == "generated"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/render/test_metrics.py::test_beatjob_has_tier_field_defaulting_to_none -v`
Expected: FAIL with `TypeError` (unexpected keyword) or `AttributeError` — `BeatJob` has no `tier`.

- [ ] **Step 3: Add the field**

In `manim_skill/render/jobs.py`, change the `BeatJob` dataclass:

```python
@dataclass
class BeatJob:
    beat: Beat
    status: JobStatus = JobStatus.QUEUED
    mp4_path: Path | None = None
    error: str | None = None
    tier: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/render/test_metrics.py::test_beatjob_has_tier_field_defaulting_to_none -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add manim_skill/render/jobs.py tests/render/test_metrics.py
git commit -m "feat(render): add tier field to BeatJob"
```

---

## Task 2: Create `metrics.py` with tier constants + `compute_tier_metrics`

**Files:**
- Create: `manim_skill/render/metrics.py`
- Test: `tests/render/test_metrics.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/render/test_metrics.py`:

```python
from manim_skill.render.jobs import BatchJob, ClipJob, BeatJob
from manim_skill.render.metrics import (
    compute_tier_metrics,
    TIER_DETERMINISTIC,
    TIER_GENERATED,
    TIER_MODEL_REPAIRED,
    TIER_UNRESOLVED,
)
from manim_skill.spec.schema import Beat, SceneSpec


def _beat_with_tier(tier):
    bj = BeatJob(beat=Beat(component="raw", code="x"))
    bj.tier = tier
    return bj


def test_compute_tier_metrics_aggregates_counts_and_rates():
    spec = SceneSpec(title="C", beats=[Beat(component="raw", code="x")])
    clip = ClipJob(
        concept="C",
        spec=spec,
        beat_jobs=[
            _beat_with_tier(TIER_DETERMINISTIC),
            _beat_with_tier(TIER_GENERATED),
            _beat_with_tier(TIER_MODEL_REPAIRED),
            _beat_with_tier(TIER_UNRESOLVED),
        ],
    )
    batch = BatchJob(clip_jobs=[clip])

    m = compute_tier_metrics(batch)

    assert m["total_beats"] == 4
    assert m["tier_counts"][TIER_UNRESOLVED] == 1
    assert m["tier_counts"][TIER_GENERATED] == 1
    assert m["escalation_rate"] == 0.25
    assert m["free_tier_rate"] == 0.75
    assert m["per_clip"][0]["concept"] == "C"
    assert m["per_clip"][0]["unresolved"] == 1


def test_compute_tier_metrics_treats_missing_tier_as_unresolved():
    spec = SceneSpec(title="C", beats=[Beat(component="raw", code="x")])
    bj = BeatJob(beat=Beat(component="raw", code="x"))  # tier left as None
    clip = ClipJob(concept="C", spec=spec, beat_jobs=[bj])
    m = compute_tier_metrics(BatchJob(clip_jobs=[clip]))
    assert m["tier_counts"][TIER_UNRESOLVED] == 1
    assert m["escalation_rate"] == 1.0


def test_compute_tier_metrics_empty_batch_is_zero():
    m = compute_tier_metrics(BatchJob(clip_jobs=[]))
    assert m["total_beats"] == 0
    assert m["escalation_rate"] == 0.0
    assert m["free_tier_rate"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/render/test_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'manim_skill.render.metrics'`

- [ ] **Step 3: Create the module**

Create `manim_skill/render/metrics.py`:

```python
from __future__ import annotations

from manim_skill.render.jobs import BatchJob

# Cost tiers a beat can resolve at (set by the render backend).
TIER_DETERMINISTIC = "deterministic"   # component beat — free L0 win
TIER_CACHED = "cached"                 # served from the beat cache — free
TIER_GENERATED = "generated"           # raw beat rendered first try — L1 generation
TIER_MODEL_REPAIRED = "model_repaired" # raw beat fixed by the repair loop — L1 repair
TIER_UNRESOLVED = "unresolved"         # failed every tier — escalation candidate (L2)

_FREE_TIERS = (
    TIER_DETERMINISTIC,
    TIER_CACHED,
    TIER_GENERATED,
    TIER_MODEL_REPAIRED,
)


def compute_tier_metrics(batch: BatchJob) -> dict:
    """Aggregate per-beat resolution tier into a batch cost summary.

    Returns total beats, the tier histogram, the escalation rate
    (unresolved / total — the share that would need the expensive L2
    copilot), the free-tier rate (everything resolved without L2), and a
    per-clip breakdown. A beat with no tier set counts as unresolved.
    """
    per_clip = []
    overall: dict[str, int] = {}
    total = 0
    unresolved = 0
    for clip in batch.clip_jobs:
        counts: dict[str, int] = {}
        for bj in clip.beat_jobs:
            tier = bj.tier or TIER_UNRESOLVED
            counts[tier] = counts.get(tier, 0) + 1
            overall[tier] = overall.get(tier, 0) + 1
            total += 1
            if tier == TIER_UNRESOLVED:
                unresolved += 1
        per_clip.append(
            {
                "concept": clip.concept,
                "tier_counts": counts,
                "unresolved": counts.get(TIER_UNRESOLVED, 0),
            }
        )

    escalation_rate = (unresolved / total) if total else 0.0
    free = sum(overall.get(t, 0) for t in _FREE_TIERS)
    free_tier_rate = (free / total) if total else 0.0
    return {
        "total_beats": total,
        "tier_counts": overall,
        "escalation_rate": round(escalation_rate, 4),
        "free_tier_rate": round(free_tier_rate, 4),
        "per_clip": per_clip,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/render/test_metrics.py -v`
Expected: PASS (4 tests including Task 1's)

- [ ] **Step 5: Commit**

```bash
git add manim_skill/render/metrics.py tests/render/test_metrics.py
git commit -m "feat(render): add compute_tier_metrics aggregation"
```

---

## Task 3: Set `beat_job.tier` in `_render_beat_job`

**Files:**
- Modify: `manim_skill/render/backend.py:14-84`
- Test: `tests/render/test_backend.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/render/test_backend.py`:

```python
def test_render_batch_tier_deterministic_for_component_generated_for_raw(
    tmp_path, monkeypatch
):
    _patch_docker_fns(monkeypatch)
    specs = [
        SceneSpec(
            title="C",
            beats=[
                Beat(component="TextBeat", params={"text": "hi"}),
                Beat(component="raw", code="self.wait(1)"),
            ],
        )
    ]
    batch = render_batch(specs, tmp_path, max_workers=1)
    tiers = [bj.tier for bj in batch.clip_jobs[0].beat_jobs]
    assert tiers == ["deterministic", "generated"]


def test_render_batch_tier_unresolved_on_failure(tmp_path, monkeypatch):
    _patch_docker_fns(monkeypatch, render_fn=_fake_render_raises)
    specs = [SceneSpec(title="C", beats=[Beat(component="raw", code="bad")])]
    batch = render_batch(specs, tmp_path)
    assert batch.clip_jobs[0].beat_jobs[0].tier == "unresolved"


def test_render_batch_tier_model_repaired_when_repairer_fixes(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(backend_mod, "render_spec_to_mp4", _fake_render_raises)
    monkeypatch.setattr(backend_mod, "stitch_mp4s", _fake_stitch_mp4s)
    monkeypatch.setattr(backend_mod, "mp4_to_gif", _fake_mp4_to_gif)

    class _FakeRepairer:
        def render_with_repair(
            self, beat, work_dir, *, title, aspect_ratio, quality="medium"
        ):
            from manim_skill.llm.repair import RepairResult

            work_dir = Path(work_dir)
            work_dir.mkdir(parents=True, exist_ok=True)
            mp4 = work_dir / "repaired.mp4"
            mp4.write_bytes(b"\x00repaired")
            return RepairResult(mp4_path=mp4, final_beat=beat, attempts=2)

    specs = [SceneSpec(title="C", beats=[Beat(component="raw", code="broken")])]
    batch = render_batch(specs, tmp_path, repairer=_FakeRepairer())
    assert batch.clip_jobs[0].beat_jobs[0].tier == "model_repaired"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/render/test_backend.py -k tier -v`
Expected: FAIL — `tier` is `None` (not yet set), assertions mismatch.

- [ ] **Step 3: Set tier in `_render_beat_job`**

In `manim_skill/render/backend.py`, add the import near the top imports (after line 15's `from manim_skill.render.jobs import ...`):

```python
from manim_skill.render.metrics import (
    TIER_CACHED,
    TIER_DETERMINISTIC,
    TIER_GENERATED,
    TIER_MODEL_REPAIRED,
    TIER_UNRESOLVED,
)
```

Then update the body of `_render_beat_job` (the `try`/`except` block, lines 45-84) to set `beat_job.tier` at each resolution point:

```python
    try:
        if cache is not None:
            cached = cache.get(original_beat)
            if cached is not None:
                shutil.copy2(cached, dest)
                beat_job.mp4_path = dest
                beat_job.status = JobStatus.DONE
                beat_job.tier = TIER_CACHED
                return beat_job

        beat_work = clip_dir / f"beat_{index:02d}_work"
        if repairer is not None and original_beat.component == "raw":
            result = repairer.render_with_repair(
                original_beat,
                beat_work,
                title=clip.spec.title,
                aspect_ratio=clip.spec.aspect_ratio,
                quality=quality,
            )
            rendered = result.mp4_path
            beat_job.beat = result.final_beat
            beat_job.tier = (
                TIER_MODEL_REPAIRED if result.attempts > 1 else TIER_GENERATED
            )
        else:
            one_beat_spec = SceneSpec(
                title=clip.spec.title,
                aspect_ratio=clip.spec.aspect_ratio,
                beats=[original_beat],
            )
            rendered = render_spec_to_mp4(
                one_beat_spec, beat_work, quality=quality
            )
            beat_job.tier = (
                TIER_GENERATED
                if original_beat.component == "raw"
                else TIER_DETERMINISTIC
            )

        shutil.copy2(rendered, dest)
        beat_job.mp4_path = dest
        beat_job.status = JobStatus.DONE
        if cache is not None:
            cache.put(original_beat, dest)
    except RenderError as exc:
        beat_job.status = JobStatus.FAILED
        beat_job.error = str(exc)
        beat_job.tier = TIER_UNRESOLVED

    return beat_job
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/render/test_backend.py -k tier -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full backend test file (no regressions)**

Run: `pytest tests/render/test_backend.py -v`
Expected: PASS (all existing tests still green)

- [ ] **Step 6: Commit**

```bash
git add manim_skill/render/backend.py tests/render/test_backend.py
git commit -m "feat(render): record resolution tier per beat"
```

---

## Task 4: Embed summary + per-clip tier counts in the manifest

**Files:**
- Modify: `manim_skill/render/bundle.py:9-54`
- Test: `tests/render/test_bundle.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/render/test_bundle.py` (create the file with this import header if it does not exist):

```python
import json
import zipfile
from pathlib import Path

from manim_skill.render.bundle import BundleEntry, bundle_clips


def test_bundle_clips_embeds_summary_and_tier_counts(tmp_path):
    mp4 = tmp_path / "clip.mp4"
    mp4.write_bytes(b"\x00mp4")
    gif = tmp_path / "clip.gif"
    gif.write_bytes(b"\x00gif")

    entry = BundleEntry(
        concept="Concept A",
        mp4_path=mp4,
        gif_path=gif,
        status="done",
        tier_counts={"generated": 2, "deterministic": 1},
    )
    summary = {"total_beats": 3, "escalation_rate": 0.0, "free_tier_rate": 1.0}

    out = bundle_clips([entry], tmp_path / "out.zip", summary=summary)

    with zipfile.ZipFile(out) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["summary"] == summary
    assert manifest["concepts"][0]["tier_counts"] == {
        "generated": 2,
        "deterministic": 1,
    }


def test_bundle_clips_summary_omitted_when_none(tmp_path):
    entry = BundleEntry(concept="C", mp4_path=None, gif_path=None, status="failed")
    out = bundle_clips([entry], tmp_path / "out.zip")
    with zipfile.ZipFile(out) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert "summary" not in manifest
    assert manifest["concepts"][0]["tier_counts"] == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/render/test_bundle.py -k "summary or tier_counts" -v`
Expected: FAIL — `BundleEntry` has no `tier_counts`; `bundle_clips` has no `summary` param.

- [ ] **Step 3: Update `bundle.py`**

Replace the `BundleEntry` dataclass and `bundle_clips` signature/body in `manim_skill/render/bundle.py`:

```python
@dataclass
class BundleEntry:
    concept: str
    mp4_path: Path | None
    gif_path: Path | None
    status: str
    tier_counts: dict | None = None


def _safe_name(name: str) -> str:
    cleaned = "".join(
        c if (c.isalnum() or c in "-_") else "_" for c in name
    )
    return cleaned[:40] or "concept"


def bundle_clips(entries: list[BundleEntry], output_zip, summary: dict | None = None) -> Path:
    """Bundle per-concept mp4 + gif into one zip with a manifest.json.

    Each concept gets its own folder (`NN_<safe-name>/`). Missing or
    failed-clip files are simply omitted; the manifest records the
    status, which files made it in, and the per-concept tier counts. A
    batch `summary` (cost-tier metrics) is embedded at the top level when
    provided.
    """
    output_zip = Path(output_zip).resolve()
    output_zip.parent.mkdir(parents=True, exist_ok=True)

    manifest: dict = {"concepts": []}
    if summary is not None:
        manifest["summary"] = summary
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for index, entry in enumerate(entries):
            folder = f"{index:02d}_{_safe_name(entry.concept)}"
            record: dict = {
                "concept": entry.concept,
                "status": entry.status,
                "tier_counts": entry.tier_counts or {},
                "files": [],
            }
            for path in (entry.mp4_path, entry.gif_path):
                if path is not None and Path(path).exists():
                    arcname = f"{folder}/{Path(path).name}"
                    zf.write(path, arcname)
                    record["files"].append(arcname)
            manifest["concepts"].append(record)
        zf.writestr(
            "manifest.json",
            json.dumps(manifest, indent=2, ensure_ascii=False),
        )

    return output_zip
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/render/test_bundle.py -v`
Expected: PASS (new tests + any existing bundle tests still green)

- [ ] **Step 5: Commit**

```bash
git add manim_skill/render/bundle.py tests/render/test_bundle.py
git commit -m "feat(render): embed tier summary + per-clip tier counts in manifest"
```

---

## Task 5: Wire metrics + quota gate into `render_batch`

**Files:**
- Modify: `manim_skill/render/jobs.py:36-40`
- Modify: `manim_skill/render/backend.py:87-167`
- Test: `tests/render/test_backend.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/render/test_backend.py`:

```python
def test_render_batch_sets_escalation_rate_and_over_quota_flag(
    tmp_path, monkeypatch
):
    calls = {"n": 0}

    def flaky_render(spec, workdir, *, quality="medium"):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RenderError("boom")
        return _fake_render_spec_to_mp4(spec, workdir)

    _patch_docker_fns(monkeypatch, render_fn=flaky_render)
    specs = [
        SceneSpec(
            title="C",
            beats=[
                Beat(component="raw", code="bad"),
                Beat(component="raw", code="ok"),
            ],
        )
    ]
    batch = render_batch(
        specs, tmp_path, max_workers=1, escalation_quota=0.1
    )
    assert batch.escalation_rate == 0.5
    assert batch.over_quota is True


def test_render_batch_over_quota_false_without_quota(tmp_path, monkeypatch):
    _patch_docker_fns(monkeypatch, render_fn=_fake_render_raises)
    specs = [SceneSpec(title="C", beats=[Beat(component="raw", code="bad")])]
    batch = render_batch(specs, tmp_path)  # no quota passed
    assert batch.escalation_rate == 1.0
    assert batch.over_quota is False


def test_render_batch_writes_summary_into_manifest(tmp_path, monkeypatch):
    _patch_docker_fns(monkeypatch)
    specs = [
        SceneSpec(
            title="C",
            beats=[Beat(component="raw", code="self.wait(1)")],
        )
    ]
    batch = render_batch(specs, tmp_path)
    import json
    import zipfile

    with zipfile.ZipFile(batch.zip_path) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["summary"]["total_beats"] == 1
    assert manifest["summary"]["tier_counts"]["generated"] == 1
    assert manifest["concepts"][0]["tier_counts"]["generated"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/render/test_backend.py -k "quota or summary_into" -v`
Expected: FAIL — `BatchJob` has no `escalation_rate`/`over_quota`; `render_batch` has no `escalation_quota` param; manifest has no summary.

- [ ] **Step 3: Add fields to `BatchJob`**

In `manim_skill/render/jobs.py`:

```python
@dataclass
class BatchJob:
    clip_jobs: list[ClipJob]
    status: JobStatus = JobStatus.QUEUED
    zip_path: Path | None = None
    escalation_rate: float = 0.0
    over_quota: bool = False
```

- [ ] **Step 4: Wire metrics into `render_batch`**

In `manim_skill/render/backend.py`, add at the top (after the existing imports):

```python
import logging

logger = logging.getLogger(__name__)
```

Add `compute_tier_metrics` to the metrics import added in Task 3:

```python
from manim_skill.render.metrics import (
    TIER_CACHED,
    TIER_DETERMINISTIC,
    TIER_GENERATED,
    TIER_MODEL_REPAIRED,
    TIER_UNRESOLVED,
    compute_tier_metrics,
)
```

Add the `escalation_quota` parameter to `render_batch` (keyword-only, after `quality`):

```python
def render_batch(
    specs: list[SceneSpec],
    workdir,
    *,
    max_workers: int = 3,
    cache: BeatCache | None = None,
    repairer: "BeatRepairer | None" = None,
    quality: str = "medium",
    escalation_quota: float | None = None,
) -> BatchJob:
```

Then replace the bundling tail of `render_batch` (the `entries = [...]` block through `return batch`, lines 152-167) with:

```python
    metrics = compute_tier_metrics(batch)
    batch.escalation_rate = metrics["escalation_rate"]
    batch.over_quota = (
        escalation_quota is not None
        and metrics["escalation_rate"] > escalation_quota
    )
    if batch.over_quota:
        logger.warning(
            "escalation rate %.0f%% exceeds quota %.0f%% — strengthen the "
            "contract (add components / repair rules) before the next batch",
            metrics["escalation_rate"] * 100,
            escalation_quota * 100,
        )

    entries = [
        BundleEntry(
            concept=clip.concept,
            mp4_path=clip.mp4_path,
            gif_path=clip.gif_path,
            status=clip.status.value,
            tier_counts=per_clip["tier_counts"],
        )
        for clip, per_clip in zip(clip_jobs, metrics["per_clip"])
    ]
    batch.zip_path = bundle_clips(
        entries, workdir / "output.zip", summary=metrics
    )
    batch.status = (
        JobStatus.DONE
        if any(clip.status == JobStatus.DONE for clip in clip_jobs)
        else JobStatus.FAILED
    )
    return batch
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/render/test_backend.py -k "quota or summary_into" -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Run the full render test suite (no regressions)**

Run: `pytest tests/render/ -m "not docker" -v`
Expected: PASS (all render tests green)

- [ ] **Step 7: Commit**

```bash
git add manim_skill/render/jobs.py manim_skill/render/backend.py tests/render/test_backend.py
git commit -m "feat(render): compute escalation rate + quota gate + manifest summary in render_batch"
```

---

## Task 6: Surface tier metrics in the CLI and eval bundler

**Files:**
- Modify: `manim_skill/cli.py:214-225`
- Modify: `scripts/eval/bundle_specs.py`
- Test: `tests/test_cli.py` (extend; create if absent)

- [ ] **Step 1: Write the failing test for the CLI line**

Append to `tests/test_cli.py` (create with this header if it does not exist):

```python
from manim_skill.render import metrics as metrics_mod


def test_format_tier_line_reports_distribution_and_rates():
    line = metrics_mod.format_tier_line(
        {
            "tier_counts": {"generated": 3, "unresolved": 1},
            "free_tier_rate": 0.75,
            "escalation_rate": 0.25,
        }
    )
    assert "generated" in line
    assert "75%" in line
    assert "25%" in line
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_format_tier_line_reports_distribution_and_rates -v`
Expected: FAIL with `AttributeError: module ... has no attribute 'format_tier_line'`

- [ ] **Step 3: Add `format_tier_line` to `metrics.py`**

Append to `manim_skill/render/metrics.py`:

```python
def format_tier_line(metrics: dict) -> str:
    """One-line human summary of a tier-metrics dict for CLI output."""
    counts = ", ".join(
        f"{tier}={n}" for tier, n in sorted(metrics["tier_counts"].items())
    )
    return (
        f"tiers: {counts}  "
        f"free={metrics['free_tier_rate'] * 100:.0f}%  "
        f"escalation={metrics['escalation_rate'] * 100:.0f}%"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py::test_format_tier_line_reports_distribution_and_rates -v`
Expected: PASS

- [ ] **Step 5: Print the line in `_cmd_bundle`**

In `manim_skill/cli.py`, add to the imports at the top:

```python
from manim_skill.render.metrics import compute_tier_metrics, format_tier_line
```

In `_cmd_bundle`, after the per-clip print loop and before `if batch.zip_path:` (around line 222-223), insert:

```python
    print(format_tier_line(compute_tier_metrics(batch)))
```

- [ ] **Step 6: Add `--escalation-quota` + metrics print to the eval bundler**

In `scripts/eval/bundle_specs.py`:

Add the argparse option (after the `--max-attempts` line):

```python
    parser.add_argument(
        "--escalation-quota",
        type=float,
        default=None,
        help="warn if the unresolved (escalation) beat rate exceeds this fraction, e.g. 0.1",
    )
```

Pass it into `render_batch` (extend the existing call):

```python
    batch = render_batch(
        specs,
        out_dir,
        repairer=repairer,
        quality=args.quality,
        max_workers=args.max_workers,
        escalation_quota=args.escalation_quota,
    )
```

After the existing per-clip print loop, before `print(f"\nTOTAL: ...")`, insert:

```python
    from manim_skill.render.metrics import compute_tier_metrics, format_tier_line

    print(format_tier_line(compute_tier_metrics(batch)))
    if batch.over_quota:
        print(
            "WARNING: escalation rate over quota — strengthen the contract "
            "(add components / repair rules) before the next batch"
        )
```

- [ ] **Step 7: Verify the CLI imports and eval script parse**

Run: `python -c "import manim_skill.cli"` then `python scripts/eval/bundle_specs.py --help`
Expected: no import error; `--help` shows `--escalation-quota`.

- [ ] **Step 8: Run the full fast suite (no regressions)**

Run: `pytest -m "not docker" -q`
Expected: PASS (all fast tests green)

- [ ] **Step 9: Commit**

```bash
git add manim_skill/render/metrics.py manim_skill/cli.py scripts/eval/bundle_specs.py tests/test_cli.py
git commit -m "feat(cli,eval): surface tier distribution + escalation-quota warning in bundle output"
```

---

## Self-Review notes (already applied)

- **Spec coverage:** Implements spec §4 metrics (層級解決分布, 升級率, 每關成功率 via tier counts) and §3 升級配額守門 (`escalation_quota` + `over_quota` + warning). NOT in this plan (deferred to follow-up plans, as scoped during brainstorming): 黃金範例機制 (項目 1), 契約缺口回流 (項目 4), `BarChart` 示範 (項目 5). The "省錢比" (savings ratio) is intentionally omitted — it needs a manually-supplied copilot-cost-per-artifact the pipeline cannot observe; the free-tier rate + escalation rate are the honest, automatic proxies.
- **Quota semantics:** `over_quota` is a post-batch signal + warning, not a mid-batch abort (the batch has already rendered in parallel). This matches the spec's intent ("stop hand-fixing, go strengthen the contract") and is stated explicitly so the implementer does not try to abort rendering.
- **Type consistency:** tier string constants are defined once in `metrics.py` and imported by `backend.py`; `compute_tier_metrics` / `format_tier_line` signatures are consistent across Tasks 2, 5, 6; `BundleEntry.tier_counts` and `BatchJob.escalation_rate`/`over_quota` names match between definition and use.
- **No new model calls / no Docker in tests:** every test uses the established `_patch_docker_fns` monkeypatch or constructs dataclasses directly.
