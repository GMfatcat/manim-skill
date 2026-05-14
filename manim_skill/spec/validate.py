from __future__ import annotations

from pydantic import ValidationError

from manim_skill.components import base as registry
from manim_skill.spec.schema import Beat, SceneSpec


class SpecValidationError(ValueError):
    """Raised when a spec dict fails schema or component validation."""


def validate_spec(raw: dict) -> SceneSpec:
    """Validate a raw dict into a SceneSpec.

    Checks the top-level schema, then for each beat checks that the
    component exists and its params match the component's schema.
    Raw beats are checked for a non-empty `code` field.
    """
    try:
        spec = SceneSpec.model_validate(raw)
    except ValidationError as exc:
        raise SpecValidationError(f"spec schema invalid: {exc}") from exc

    for index, beat in enumerate(spec.beats):
        _validate_beat(index, beat)
    return spec


def _validate_beat(index: int, beat: Beat) -> None:
    if beat.component == "raw":
        if not beat.code:
            raise SpecValidationError(
                f"beat {index}: raw beat requires a non-empty 'code' field"
            )
        return

    try:
        component = registry.get(beat.component)
    except KeyError as exc:
        raise SpecValidationError(f"beat {index}: {exc}") from exc

    try:
        component.Params.model_validate(beat.params)
    except ValidationError as exc:
        raise SpecValidationError(
            f"beat {index}: invalid params for {beat.component}: {exc}"
        ) from exc
