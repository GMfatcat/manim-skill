import json
import zipfile

from manim_skill.render.bundle import BundleEntry, bundle_clips


def _make_file(path, content=b"data"):
    path.write_bytes(content)
    return path


def test_bundle_creates_zip_with_manifest(tmp_path):
    mp4 = _make_file(tmp_path / "a.mp4")
    gif = _make_file(tmp_path / "a.gif")
    entries = [
        BundleEntry(concept="Concept A", mp4_path=mp4, gif_path=gif, status="done")
    ]
    zip_path = bundle_clips(entries, tmp_path / "out" / "bundle.zip")

    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert "manifest.json" in names
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["concepts"][0]["concept"] == "Concept A"
    assert manifest["concepts"][0]["status"] == "done"
    assert len(manifest["concepts"][0]["files"]) == 2


def test_bundle_puts_each_concept_in_its_own_folder(tmp_path):
    mp4_a = _make_file(tmp_path / "a.mp4")
    mp4_b = _make_file(tmp_path / "b.mp4")
    entries = [
        BundleEntry(concept="First", mp4_path=mp4_a, gif_path=None, status="done"),
        BundleEntry(concept="Second", mp4_path=mp4_b, gif_path=None, status="done"),
    ]
    zip_path = bundle_clips(entries, tmp_path / "bundle.zip")

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    folders = {n.split("/")[0] for n in names if "/" in n}
    assert len(folders) == 2  # one folder per concept


def test_bundle_handles_failed_clip_with_no_files(tmp_path):
    entries = [
        BundleEntry(concept="Broken", mp4_path=None, gif_path=None, status="failed")
    ]
    zip_path = bundle_clips(entries, tmp_path / "bundle.zip")

    with zipfile.ZipFile(zip_path) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["concepts"][0]["status"] == "failed"
    assert manifest["concepts"][0]["files"] == []


def test_bundle_creates_missing_output_dir(tmp_path):
    mp4 = _make_file(tmp_path / "a.mp4")
    entries = [BundleEntry(concept="A", mp4_path=mp4, gif_path=None, status="done")]
    zip_path = bundle_clips(entries, tmp_path / "deep" / "nested" / "b.zip")
    assert zip_path.exists()
