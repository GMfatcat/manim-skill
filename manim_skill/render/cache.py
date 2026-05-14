from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from manim_skill.spec.schema import Beat


def beat_cache_key(beat: Beat) -> str:
    """A stable content hash of a beat.

    `model_dump(mode="json")` plus `sort_keys=True` makes the hash
    independent of dict key insertion order, so two beats with the
    same content always map to the same key.
    """
    payload = json.dumps(beat.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class BeatCache:
    """Filesystem cache of rendered beat mp4s, keyed by beat content."""

    def __init__(self, cache_dir) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, beat: Beat) -> Path:
        return self.cache_dir / f"{beat_cache_key(beat)}.mp4"

    def get(self, beat: Beat) -> Path | None:
        path = self._path_for(beat)
        return path if path.exists() else None

    def put(self, beat: Beat, mp4_path) -> Path:
        # Not atomic: two identical beats rendering concurrently can both
        # write here (last-write-wins). Acceptable for the Phase 1 local
        # backend — a torn file is rare and self-heals on the next run.
        dest = self._path_for(beat)
        shutil.copy2(mp4_path, dest)
        return dest
