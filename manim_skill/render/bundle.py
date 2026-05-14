from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BundleEntry:
    concept: str
    mp4_path: Path | None
    gif_path: Path | None
    status: str


def _safe_name(name: str) -> str:
    cleaned = "".join(
        c if (c.isalnum() or c in "-_") else "_" for c in name
    )
    return cleaned[:40] or "concept"


def bundle_clips(entries: list[BundleEntry], output_zip) -> Path:
    """Bundle per-concept mp4 + gif into one zip with a manifest.json.

    Each concept gets its own folder (`NN_<safe-name>/`). Missing or
    failed-clip files are simply omitted; the manifest records the
    status and which files made it in.
    """
    output_zip = Path(output_zip).resolve()
    output_zip.parent.mkdir(parents=True, exist_ok=True)

    manifest: dict = {"concepts": []}
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for index, entry in enumerate(entries):
            folder = f"{index:02d}_{_safe_name(entry.concept)}"
            record: dict = {
                "concept": entry.concept,
                "status": entry.status,
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
