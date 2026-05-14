"""Shared pytest fixtures."""
import pytest

from manim_skill.components import base as _registry


@pytest.fixture(autouse=True)
def _restore_component_registry():
    """Restore the component registry after each test.

    Prevents tests that register dummy/test components from polluting
    the global registry and affecting other tests (e.g. drift-detection
    tests that call render_components_doc()).
    """
    snapshot = dict(_registry._REGISTRY)
    yield
    _registry._REGISTRY.clear()
    _registry._REGISTRY.update(snapshot)
