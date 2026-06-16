from manim_skill.render.jobs import BeatJob
from manim_skill.spec.schema import Beat


def test_beatjob_has_tier_field_defaulting_to_none():
    bj = BeatJob(beat=Beat(component="raw", code="self.wait(1)"))
    assert bj.tier is None
    bj.tier = "generated"
    assert bj.tier == "generated"
