"""Vendored contract self-consistency checks."""

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"


def load_schema() -> dict[str, Any]:
    """The vendored intake schema."""
    return json.loads((SCHEMA_DIR / "intake-schema.json").read_text())


def load_example() -> dict[str, Any]:
    """The vendored golden example intake."""
    return json.loads((SCHEMA_DIR / "intake-example.json").read_text())


def with_preferred_session_type(type_value: Any) -> dict[str, Any]:
    """The vendored example, with one weekly-session row of the given type."""
    intake = load_example()
    intake["weekly_schedule"]["preferred_sessions"] = [
        {"day": "Wednesday", "type": type_value}
    ]
    return intake


def test_vendored_example_validates_against_vendored_schema() -> None:
    """The vendored golden example validates against the vendored schema."""
    jsonschema.validate(instance=load_example(), schema=load_schema())


def test_schema_accepts_both_preferred_session_type_forms() -> None:
    """The vendored schema takes a weekly session's `type` as a single broad
    type or as an array of two or more - the flexible form."""
    for type_value in ("quality", ["easy", "quality"]):
        jsonschema.validate(
            instance=with_preferred_session_type(type_value), schema=load_schema()
        )


def test_schema_rejects_single_element_type_array() -> None:
    """A one-element array is the scalar form spelled differently; the schema
    keeps one spelling per meaning and rejects it."""
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            instance=with_preferred_session_type(["quality"]), schema=load_schema()
        )


def test_schema_rejects_repeated_type_in_array() -> None:
    """A flexible set is a set: the same type twice is rejected."""
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            instance=with_preferred_session_type(["easy", "easy"]),
            schema=load_schema(),
        )
