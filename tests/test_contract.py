"""Vendored contract self-consistency checks."""

import json
from pathlib import Path

import jsonschema

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"


def test_vendored_example_validates_against_vendored_schema() -> None:
    """The vendored golden example validates against the vendored schema."""
    schema = json.loads((SCHEMA_DIR / "intake-schema.json").read_text())
    example = json.loads((SCHEMA_DIR / "intake-example.json").read_text())
    jsonschema.validate(instance=example, schema=schema)
