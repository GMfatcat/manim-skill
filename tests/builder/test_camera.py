from manim_skill.builder.camera import apply_camera
from manim_skill.spec.schema import CameraDirective


class FakeFrame:
    def __init__(self):
        self.ops = []

    @property
    def animate(self):
        self.ops.append("animate")
        return self

    def scale(self, factor):
        self.ops.append(("scale", factor))
        return self

    def restore(self):
        self.ops.append("restore")
        return self


class FakeCamera:
    def __init__(self):
        self.frame = FakeFrame()


class FakeScene:
    def __init__(self):
        self.camera = FakeCamera()
        self.played = []

    def play(self, *args, **kwargs):
        self.played.append((args, kwargs))


def test_zoom_scales_frame_by_inverse_and_plays():
    scene = FakeScene()
    apply_camera(scene, CameraDirective(action="zoom", scale=2.0))
    assert ("scale", 0.5) in scene.camera.frame.ops
    assert len(scene.played) == 1


def test_reset_restores_frame_and_plays():
    scene = FakeScene()
    apply_camera(scene, CameraDirective(action="reset"))
    assert "restore" in scene.camera.frame.ops
    assert len(scene.played) == 1


def test_focus_is_noop_in_plan_1():
    scene = FakeScene()
    apply_camera(scene, CameraDirective(action="focus", target="x"))
    assert scene.played == []


def test_pan_is_noop_in_plan_1():
    scene = FakeScene()
    apply_camera(scene, CameraDirective(action="pan"))
    assert scene.played == []
