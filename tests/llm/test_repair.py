from pathlib import Path

import pytest

from manim_skill.llm import repair as repair_mod
from manim_skill.llm.client import FakeLLMClient
from manim_skill.llm.repair import BeatRepairer, RepairResult
from manim_skill.render.docker_render import RenderError
from manim_skill.spec.schema import Beat


def _fake_mp4(workdir):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    mp4 = workdir / "out.mp4"
    mp4.write_bytes(b"\x00mp4")
    return mp4


def test_repair_succeeds_on_first_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(
        repair_mod, "render_spec_to_mp4",
        lambda spec, workdir, *, quality="medium": _fake_mp4(workdir),
    )
    client = FakeLLMClient(response="should not be called")
    repairer = BeatRepairer(client)
    beat = Beat(component="raw", code="self.wait(1)")
    result = repairer.render_with_repair(beat, tmp_path)
    assert isinstance(result, RepairResult)
    assert result.attempts == 1
    assert result.mp4_path.exists()
    assert client.calls == []  # no repair needed -> no LLM call


def test_repair_fixes_code_then_succeeds(tmp_path, monkeypatch):
    calls = {"n": 0}

    def flaky(spec, workdir, *, quality="medium"):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RenderError("NameError: bad")
        return _fake_mp4(workdir)

    monkeypatch.setattr(repair_mod, "render_spec_to_mp4", flaky)
    client = FakeLLMClient(response="self.wait(2)")
    repairer = BeatRepairer(client)
    beat = Beat(component="raw", code="brokn code")
    result = repairer.render_with_repair(beat, tmp_path)
    assert result.attempts == 2
    assert result.final_beat.code == "self.wait(2)"
    assert len(client.calls) == 1


def test_repair_gives_up_after_max_attempts(tmp_path, monkeypatch):
    def always_fails(spec, workdir, *, quality="medium"):
        raise RenderError("always broken")

    monkeypatch.setattr(repair_mod, "render_spec_to_mp4", always_fails)
    client = FakeLLMClient(response="still broken")
    repairer = BeatRepairer(client, max_attempts=3)
    beat = Beat(component="raw", code="broken")
    with pytest.raises(RenderError):
        repairer.render_with_repair(beat, tmp_path)
    # 3 render attempts -> 2 repair calls
    assert len(client.calls) == 2


def test_repair_does_not_retry_non_raw_beat(tmp_path, monkeypatch):
    def always_fails(spec, workdir, *, quality="medium"):
        raise RenderError("component bug")

    monkeypatch.setattr(repair_mod, "render_spec_to_mp4", always_fails)
    client = FakeLLMClient(response="x")
    repairer = BeatRepairer(client)
    beat = Beat(component="TextBeat", params={"text": "hi"})
    with pytest.raises(RenderError):
        repairer.render_with_repair(beat, tmp_path)
    assert client.calls == []  # non-raw beat: no repair attempted
