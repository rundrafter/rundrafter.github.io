"""Assembler test suite: cross-field rules (T4), fixtures + smoke test (T5).

Drives assemble.js and the real form in a browser via Playwright, per
docs/spec/webform.md: same module + logic the shipped page uses, not a
second implementation of the rules.
"""

from __future__ import annotations

import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from playwright.sync_api import Page, sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
NOW = "2026-01-01T00:00:00.000Z"
SCHEMA = json.loads((REPO_ROOT / "schema" / "intake-schema.json").read_text())


@pytest.fixture(scope="session")
def base_url():
    """Serve the repo over HTTP so `<script type="module">` can load."""
    # Chrome refuses to fetch `<script type="module">` from a `file://`
    # origin (see ADR 001's consequences), so tests serve the repo over HTTP,
    # the same way `just serve` and GitHub Pages do.
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(REPO_ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join()


@pytest.fixture(scope="session")
def browser():
    """A shared Chromium instance for the test session."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(browser, base_url):
    """A fresh page loaded to the intake form for each test."""
    page = browser.new_page()
    page.goto(f"{base_url}/index.html")
    yield page
    page.close()


def load_fixture(name: str) -> dict[str, Any]:
    """Load a form-state fixture JSON file by name."""
    return json.loads((FIXTURES_DIR / name).read_text())


def valid_state() -> dict[str, Any]:
    """A minimal form-state covering only the required sections."""
    return load_fixture("valid.json")


def run_assemble(page: Page, form_state: dict[str, Any], now: str = NOW):
    """Call the real assemble.js module in-page with the given form-state."""
    return page.evaluate(
        """async ({ formState, now }) => {
            const { assemble } = await import('./assets/assemble.js');
            return assemble(formState, { now });
        }""",
        {"formState": form_state, "now": now},
    )


def assert_schema_valid(intake: dict[str, Any]) -> None:
    """Validate an assembled intake object against the vendored schema."""
    jsonschema.validate(instance=intake, schema=SCHEMA)


def test_valid_state_has_no_errors(page: Page) -> None:
    """A fully filled required-only form-state assembles cleanly and validates."""
    result = run_assemble(page, valid_state())
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_disclaimer_gate_blocks_without_acceptance(page: Page) -> None:
    """Declining the disclaimer blocks handoff."""
    state = valid_state()
    state["consent"] = {"disclaimer_accepted": False}
    result = run_assemble(page, state)
    assert any("disclaimer" in e.lower() for e in result["errors"])


def test_disclaimer_gate_blocks_when_missing(page: Page) -> None:
    """A missing consent section blocks handoff."""
    state = valid_state()
    del state["consent"]
    result = run_assemble(page, state)
    assert any("disclaimer" in e.lower() for e in result["errors"])


def test_health_screen_flag_requires_acknowledgement(page: Page) -> None:
    """A raised health-screen flag without acknowledgement blocks handoff."""
    state = valid_state()
    state["health_screen"]["chest_pain_activity"] = True
    result = run_assemble(page, state)
    assert any("acknowledg" in e.lower() for e in result["errors"])


def test_health_screen_flag_passes_with_acknowledgement(page: Page) -> None:
    """A raised health-screen flag with acknowledgement assembles cleanly."""
    state = valid_state()
    state["health_screen"]["chest_pain_activity"] = True
    state["consent"]["health_acknowledged"] = True
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_health_screen_all_false_does_not_require_acknowledgement(
    page: Page,
) -> None:
    """No health-screen flags raised means no acknowledgement is required."""
    result = run_assemble(page, valid_state())
    assert not any("acknowledg" in e.lower() for e in result["errors"])


def test_start_date_after_goal_date_blocks(page: Page) -> None:
    """A plan start date after the race date blocks handoff."""
    state = valid_state()
    state["goal"]["start_date"] = "2026-11-01"
    result = run_assemble(page, state)
    assert any("start date" in e.lower() for e in result["errors"])


def test_start_date_equal_to_goal_date_passes(page: Page) -> None:
    """A plan start date equal to the race date is allowed."""
    state = valid_state()
    state["goal"]["start_date"] = state["goal"]["date"]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_b_race_on_or_after_goal_date_blocks(page: Page) -> None:
    """A B race on or after the goal race date blocks handoff."""
    state = valid_state()
    state["b_races"] = [
        {
            "name": "Tune-up 10k",
            "distance": "10k",
            "date": state["goal"]["date"],
        }
    ]
    result = run_assemble(page, state)
    assert any("b race" in e.lower() for e in result["errors"])


def test_b_race_before_goal_date_passes(page: Page) -> None:
    """A B race before the goal race date is allowed."""
    state = valid_state()
    state["b_races"] = [
        {"name": "Tune-up 10k", "distance": "10k", "date": "2026-08-01"}
    ]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_other_event_on_or_after_goal_date_blocks(page: Page) -> None:
    """An other event on or after the goal race date blocks handoff."""
    state = valid_state()
    state["other_events"] = [
        {
            "name": "Charity fun run",
            "distance": "5k",
            "date": state["goal"]["date"],
        }
    ]
    result = run_assemble(page, state)
    assert any("other event" in e.lower() for e in result["errors"])


def test_output_formats_required(page: Page) -> None:
    """At least one output format must be selected."""
    state = valid_state()
    state["output"] = {"formats": [], "tracking": False}
    result = run_assemble(page, state)
    assert any("output format" in e.lower() for e in result["errors"])


def test_timestamps_set_at_handoff(page: Page) -> None:
    """submitted_at and accepted_at are stamped with the handoff time."""
    result = run_assemble(page, valid_state(), now="2026-03-15T09:30:00.000Z")
    assert result["intake"]["meta"]["submitted_at"] == "2026-03-15T09:30:00.000Z"
    assert result["intake"]["consent"]["accepted_at"] == "2026-03-15T09:30:00.000Z"


def test_blank_optional_sections_are_omitted(page: Page) -> None:
    """Optional sections left blank are omitted, not emitted as empty objects."""
    result = run_assemble(page, valid_state())
    intake = result["intake"]
    for key in (
        "runner",
        "strength_cross",
        "injuries",
        "b_races",
        "other_events",
        "notes",
    ):
        assert key not in intake


def test_golden_fixture_reproduces_intake_example(page: Page) -> None:
    """A fully filled form-state reproduces the vendored golden example."""
    example = json.loads((REPO_ROOT / "schema" / "intake-example.json").read_text())
    # notes.other is blank in the vendored example; our pruning rule omits an
    # empty notes section entirely rather than emitting {"other": ""}, so the
    # fixture leaves `notes` out of the form-state and this is the one field
    # excluded from the comparison below.
    del example["notes"]

    result = run_assemble(
        page, load_fixture("golden.json"), now=example["meta"]["submitted_at"]
    )
    assert result["errors"] == []
    assert result["intake"] == example
    assert_schema_valid(result["intake"])


def test_dom_smoke_fill_download_validates(page: Page) -> None:
    """Filling the real form and submitting downloads a schema-valid intake.json."""
    page.fill("#goal-race", "Melbourne Marathon")
    page.select_option("#goal-distance", "marathon")
    page.fill("#goal-date", "2026-10-11")
    page.fill("#goal-target-time", "3:45:00")
    page.fill("#goal-start-date", "2026-06-01")

    page.select_option("#recent-result-distance", "half")
    page.fill("#recent-result-time", "1:45:00")
    page.fill("#recent-result-date", "2026-05-01")

    page.fill("#fitness-weekly-distance", "40")
    page.fill("#fitness-longest-run", "18")

    page.fill("#schedule-days-available", "5")
    page.select_option("#schedule-long-run-day", "Sunday")
    page.check('input[name="weekly_schedule.rest_days"][value="Monday"]')

    page.check('input[name="consent.disclaimer_accepted"]')
    page.check('input[name="output.formats"][value="spreadsheet"]')

    with page.expect_download() as download_info:
        page.click('button[type="submit"]')

    downloaded = json.loads(Path(download_info.value.path()).read_text())
    assert_schema_valid(downloaded)
