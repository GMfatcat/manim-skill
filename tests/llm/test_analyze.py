import pytest

from manim_skill.llm.analyze import AnalyzeError, ConceptCandidate, analyze
from manim_skill.llm.client import FakeLLMClient


def test_analyze_parses_clean_json():
    response = (
        '{"concepts": [{"concept": "Attention", '
        '"why_suitable": "visual flow", '
        '"storyboard": "Show tokens. Draw weights."}]}'
    )
    client = FakeLLMClient(response=response)
    result = analyze(client, "some paper text")
    assert len(result) == 1
    assert isinstance(result[0], ConceptCandidate)
    assert result[0].concept == "Attention"
    assert result[0].storyboard == "Show tokens. Draw weights."


def test_analyze_tolerates_prose_wrapped_json():
    response = (
        "Sure! Here are the concepts:\n```json\n"
        '{"concepts": [{"concept": "X", "why_suitable": "y", '
        '"storyboard": "z"}]}\n```\nHope that helps.'
    )
    client = FakeLLMClient(response=response)
    result = analyze(client, "text")
    assert result[0].concept == "X"


def test_analyze_includes_guide_prompt_in_user_message():
    response = (
        '{"concepts": [{"concept": "X", "why_suitable": "y", '
        '"storyboard": "z"}]}'
    )
    client = FakeLLMClient(response=response)
    analyze(client, "paper text", guide_prompt="focus on the loss function")
    _system, user = client.calls[0]
    assert "focus on the loss function" in user
    assert "paper text" in user


def test_analyze_raises_on_unparseable_response():
    client = FakeLLMClient(response="no json here at all")
    with pytest.raises(AnalyzeError):
        analyze(client, "text")


def test_analyze_raises_on_missing_concepts_list():
    client = FakeLLMClient(response='{"something_else": 1}')
    with pytest.raises(AnalyzeError):
        analyze(client, "text")
