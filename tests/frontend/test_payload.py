from manim_skill.frontend.payload import (
    ConceptCard,
    build_render_payload,
    cards_from_concepts,
    selected_cards,
    within_quota,
)

_CONCEPTS = [
    {"concept": "A", "why_suitable": "wa", "storyboard": "sa"},
    {"concept": "B", "why_suitable": "wb", "storyboard": "sb"},
]


def test_cards_from_concepts():
    cards = cards_from_concepts(_CONCEPTS)
    assert len(cards) == 2
    assert all(isinstance(c, ConceptCard) for c in cards)
    assert cards[0].concept == "A"
    assert cards[0].selected is True  # selected by default


def test_selected_cards_filters():
    cards = cards_from_concepts(_CONCEPTS)
    cards[1].selected = False
    result = selected_cards(cards)
    assert [c.concept for c in result] == ["A"]


def test_build_render_payload_only_selected_with_edits():
    cards = cards_from_concepts(_CONCEPTS)
    cards[0].storyboard = "edited storyboard"
    cards[1].selected = False
    payload = build_render_payload(cards)
    assert payload == [
        {
            "concept": "A",
            "why_suitable": "wa",
            "storyboard": "edited storyboard",
        }
    ]


def test_within_quota():
    cards = cards_from_concepts(_CONCEPTS)
    assert within_quota(cards, quota=5) is True
    assert within_quota(cards, quota=1) is False


def test_within_quota_counts_only_selected():
    cards = cards_from_concepts(_CONCEPTS)
    cards[0].selected = False
    assert within_quota(cards, quota=1) is True
