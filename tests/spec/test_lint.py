from manim_skill.spec.lint import lint_spec
from manim_skill.spec.schema import Beat, SceneSpec


def _spec(beats):
    return SceneSpec(title="t", beats=beats)


def test_clean_spec_has_no_warnings():
    spec = _spec([Beat(component="TextBeat", params={"text": "hi"}, caption="short")])
    assert lint_spec(spec) == []


def test_long_caption_warns():
    spec = _spec([Beat(component="TextBeat", params={"text": "x"}, caption="w " * 40)])
    assert "caption_too_long" in [w.code for w in lint_spec(spec)]


def test_too_many_bullets_warns():
    spec = _spec([Beat(component="TextBeat", params={"text": "x", "bullets": [str(i) for i in range(7)]})])
    assert "beat_text_overload" in [w.code for w in lint_spec(spec)]


def test_raw_background_and_italic_warn():
    spec = _spec([
        Beat(component="raw", code="self.camera.background_color = '#000000'"),
        Beat(component="raw", code="t = Text('x', slant=ITALIC)\nself.add(t)"),
    ])
    codes = [w.code for w in lint_spec(spec)]
    assert "raw_sets_background" in codes
    assert "raw_uses_italic" in codes


def test_lint_never_raises_on_empty_beats():
    # SceneSpec enforces min_length=1, so use model_construct to verify
    # lint_spec is robust even if called with a spec that has no beats.
    assert lint_spec(SceneSpec.model_construct(title="t", beats=[])) == []
