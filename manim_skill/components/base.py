from __future__ import annotations

from typing import ClassVar

from manim import Mobject, Scene
from pydantic import BaseModel


class Component:
    """Base class for animation components.

    A component turns validated params into manim mobjects (`build`)
    and plays the beat's animation on a scene (`animate`).
    """

    name: ClassVar[str]
    Params: ClassVar[type[BaseModel]]

    def build(self, params: BaseModel) -> Mobject:
        raise NotImplementedError

    def animate(self, scene: Scene, mobject: Mobject, params: BaseModel) -> None:
        raise NotImplementedError


_REGISTRY: dict[str, Component] = {}


def register(component_cls: type[Component]) -> type[Component]:
    _REGISTRY[component_cls.name] = component_cls()
    return component_cls


def get(name: str) -> Component:
    if name not in _REGISTRY:
        raise KeyError(f"unknown component: {name!r}")
    return _REGISTRY[name]


def all_names() -> list[str]:
    return sorted(_REGISTRY)
