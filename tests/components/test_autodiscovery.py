def test_autodiscovery_registers_existing_components():
    # Importing the package triggers auto-discovery of all component modules.
    import importlib

    import manim_skill.components  # noqa: F401
    from manim_skill.components import base

    importlib.reload(manim_skill.components)
    names = base.all_names()
    assert "TextBeat" in names
    assert "CodeWalkthrough" in names


def test_autodiscovery_skips_base_module():
    # `base` is infrastructure, not a component — it must not be treated
    # as a component module (it has no @register call, so this just
    # confirms discovery doesn't choke on it).
    import manim_skill.components  # noqa: F401
    from manim_skill.components import base

    assert isinstance(base.all_names(), list)
