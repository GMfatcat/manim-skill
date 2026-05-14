from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConceptCard:
    """A concept in the review stage: the analyze stage's suggestion
    plus the user's edits — the storyboard text and whether to keep it."""

    concept: str
    why_suitable: str
    storyboard: str
    selected: bool = True


def cards_from_concepts(concepts: list[dict]) -> list[ConceptCard]:
    """Turn the analyze stage's concept dicts into editable cards (all
    selected by default)."""
    return [
        ConceptCard(
            concept=c["concept"],
            why_suitable=c["why_suitable"],
            storyboard=c["storyboard"],
        )
        for c in concepts
    ]


def selected_cards(cards: list[ConceptCard]) -> list[ConceptCard]:
    return [card for card in cards if card.selected]


def build_render_payload(cards: list[ConceptCard]) -> list[dict]:
    """The concept dicts to submit as a codegen render job — only the
    selected cards, each carrying the user's (possibly edited)
    storyboard."""
    return [
        {
            "concept": card.concept,
            "why_suitable": card.why_suitable,
            "storyboard": card.storyboard,
        }
        for card in selected_cards(cards)
    ]


def within_quota(cards: list[ConceptCard], quota: int) -> bool:
    """True if the number of selected cards is within the web quota."""
    return len(selected_cards(cards)) <= quota
