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
