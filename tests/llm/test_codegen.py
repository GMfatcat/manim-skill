import pytest

from manim_skill.llm.analyze import ConceptCandidate
from manim_skill.llm.client import FakeLLMClient
from manim_skill.llm.codegen import CodegenError, generate_spec
from manim_skill.spec.schema import SceneSpec

_CONCEPT = ConceptCandidate(
    concept="Demo", why_suitable="y", storyboard="Show a title."
)
_VALID_SPEC = (
    '{"title": "Demo", "beats": [{"component": "TextBeat", '
    '"params": {"text": "Hello"}}]}'
)


def test_generate_spec_valid_first_try():
    client = FakeLLMClient(response=_VALID_SPEC)
    spec = generate_spec(client, _CONCEPT, catalog="(catalog)")
    assert isinstance(spec, SceneSpec)
    assert spec.title == "Demo"
    assert len(client.calls) == 1


def test_generate_spec_reasks_after_unparseable_response():
    client = FakeLLMClient(responses=["not json at all", _VALID_SPEC])
    spec = generate_spec(client, _CONCEPT, catalog="(catalog)")
    assert isinstance(spec, SceneSpec)
    assert len(client.calls) == 2
    # the re-ask prompt mentions the rejection
    assert "rejected" in client.calls[1][1]


def test_generate_spec_reasks_on_invalid_component():
    bad = (
        '{"title": "X", "beats": [{"component": "NopeComponent", '
        '"params": {}}]}'
    )
    client = FakeLLMClient(responses=[bad, _VALID_SPEC])
    spec = generate_spec(client, _CONCEPT, catalog="(catalog)")
    assert isinstance(spec, SceneSpec)
    assert len(client.calls) == 2


def test_generate_spec_raises_after_two_failures():
    client = FakeLLMClient(responses=["garbage one", "garbage two"])
    with pytest.raises(CodegenError):
        generate_spec(client, _CONCEPT, catalog="(catalog)")


def test_generate_spec_passes_catalog_into_system_prompt():
    client = FakeLLMClient(response=_VALID_SPEC)
    generate_spec(client, _CONCEPT, catalog="UNIQUE_CATALOG_MARKER")
    system, _user = client.calls[0]
    assert "UNIQUE_CATALOG_MARKER" in system
