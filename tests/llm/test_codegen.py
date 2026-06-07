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


def test_codegen_system_prompt_includes_latex_backslash_guard():
    """Lock in the LaTeX backslash escape guidance.

    Real-LLM eval surfaced a sibling failure to the raw-beat newline case:
    the model over-applies its JSON escape rule to LaTeX commands too,
    writing \\\\\\\\frac in JSON instead of \\\\frac. The decoded string is
    \\\\frac (two backslashes) which LaTeX rejects and the formula beat
    silently fails to render.
    """
    client = FakeLLMClient(response=_VALID_SPEC)
    generate_spec(client, _CONCEPT, catalog="(catalog)")
    system = client.calls[0][0]

    # Prompt must explicitly discuss LaTeX / formula strings
    s = system.lower()
    assert "latex" in s or "formula" in s
    # And must show \\frac as the correct JSON encoding of \frac
    assert "\\\\frac" in system


def test_codegen_system_prompt_includes_raw_beat_guards():
    """Lock in the raw-beat guidance the prompt must carry.

    Real-LLM eval (Nemotron-3 Super) surfaced five raw-beat failure modes:
    Scene-class wrappers, missing self.play/add, double-escaped \\n in JSON,
    empty code, and cross-beat variable references. The prompt must
    explicitly cover each so the LLM doesn't repeat them.
    """
    client = FakeLLMClient(response=_VALID_SPEC)
    generate_spec(client, _CONCEPT, catalog="(catalog)")
    system = client.calls[0][0]

    # 1. no Scene class wrapper
    assert "class" in system.lower() and "construct" in system.lower()
    # 2. must call self.play or self.add
    assert "self.play" in system or "self.add" in system
    # 3. don't double-escape newlines — the prompt names the failure mode
    assert "\\n" in system  # mentions the JSON-encoded form
    # 4. beats are isolated, no cross-beat variables
    assert (
        "isolated" in system.lower()
        or "other beat" in system.lower()
        or "another beat" in system.lower()
    )


def test_codegen_system_prompt_includes_visual_rules():
    """Lock in the dlm-polish-derived visual guardrails for a weak model."""
    client = FakeLLMClient(response=_VALID_SPEC)
    generate_spec(client, _CONCEPT, catalog="(catalog)")
    system = client.calls[0][0]
    s = system.lower()

    # no italics
    assert "italic" in s
    # keep captions short
    assert "caption" in s and ("short" in s or "few words" in s)
    # use the theme colors / factories in raw beats
    assert "theme" in s
    assert "title_text" in system or "PRIMARY" in system
