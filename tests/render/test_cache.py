from manim_skill.render.cache import BeatCache, beat_cache_key
from manim_skill.spec.schema import Beat


def test_cache_key_is_stable_for_same_content():
    beat_a = Beat(component="raw", code="self.wait(1)")
    beat_b = Beat(component="raw", code="self.wait(1)")
    assert beat_cache_key(beat_a) == beat_cache_key(beat_b)


def test_cache_key_differs_for_different_content():
    beat_a = Beat(component="raw", code="self.wait(1)")
    beat_b = Beat(component="raw", code="self.wait(2)")
    assert beat_cache_key(beat_a) != beat_cache_key(beat_b)


def test_get_returns_none_when_absent(tmp_path):
    cache = BeatCache(tmp_path / "cache")
    beat = Beat(component="raw", code="pass")
    assert cache.get(beat) is None


def test_put_then_get_roundtrips(tmp_path):
    cache = BeatCache(tmp_path / "cache")
    beat = Beat(component="raw", code="pass")
    source = tmp_path / "source.mp4"
    source.write_bytes(b"\x00\x00video-bytes")

    stored = cache.put(beat, source)
    assert stored.exists()

    retrieved = cache.get(beat)
    assert retrieved is not None
    assert retrieved.read_bytes() == b"\x00\x00video-bytes"


def test_cache_dir_is_created(tmp_path):
    target = tmp_path / "nested" / "cache"
    BeatCache(target)
    assert target.is_dir()
