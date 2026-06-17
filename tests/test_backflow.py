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
