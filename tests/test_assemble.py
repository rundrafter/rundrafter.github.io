"""Assembler test suite: cross-field rules (T4), fixtures + smoke test (T5).

Drives assemble.js and the real form in a browser via Playwright, per
docs/architecture.md: same module + logic the shipped page uses, not a
second implementation of the rules.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from playwright.sync_api import Page

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
NOW = "2026-01-01T00:00:00.000Z"
SCHEMA = json.loads((REPO_ROOT / "schema" / "intake-schema.json").read_text())


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


def test_start_date_after_goal_date_blocks(page: Page) -> None:
    """A plan start date after the race date blocks handoff."""
    state = valid_state()
    state["goal"]["start_date"] = "2026-11-01"
    result = run_assemble(page, state)
    assert any("start date" in e.lower() for e in result["errors"])


def test_start_date_equal_to_goal_date_blocks(page: Page) -> None:
    """A plan start date equal to the race date blocks handoff (strict <)."""
    state = valid_state()
    state["goal"]["start_date"] = state["goal"]["date"]
    result = run_assemble(page, state)
    assert any("start date" in e.lower() for e in result["errors"])


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


def test_recent_result_after_start_date_blocks(page: Page) -> None:
    """A recent-result date after the plan start date blocks handoff."""
    state = valid_state()
    state["recent_result"]["date"] = "2026-06-02"
    result = run_assemble(page, state)
    assert any("recent result" in e.lower() for e in result["errors"])


def test_recent_result_equal_to_start_date_passes(page: Page) -> None:
    """A recent-result date equal to the plan start date is allowed."""
    state = valid_state()
    state["recent_result"]["date"] = state["goal"]["start_date"]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_b_race_on_start_date_blocks(page: Page) -> None:
    """A B race on the plan start date blocks handoff (strictly-between rule)."""
    state = valid_state()
    state["b_races"] = [
        {
            "name": "Tune-up 10k",
            "distance": "10k",
            "date": state["goal"]["start_date"],
        }
    ]
    result = run_assemble(page, state)
    assert any("b race" in e.lower() for e in result["errors"])


def test_other_event_before_start_date_blocks(page: Page) -> None:
    """An other event before the plan start date blocks handoff."""
    state = valid_state()
    state["other_events"] = [
        {"name": "Charity fun run", "distance": "5k", "date": "2026-01-01"}
    ]
    result = run_assemble(page, state)
    assert any("other event" in e.lower() for e in result["errors"])


def test_other_event_within_window_passes(page: Page) -> None:
    """An other event strictly between start_date and goal.date is allowed."""
    state = valid_state()
    state["other_events"] = [
        {"name": "Bridge to Brisbane", "distance": "10k", "date": "2026-08-16"}
    ]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_duplicate_event_dates_blocks(page: Page) -> None:
    """A B race and an other event sharing a date blocks handoff."""
    state = valid_state()
    shared_date = "2026-08-16"
    state["b_races"] = [
        {"name": "Tune-up 10k", "distance": "10k", "date": shared_date}
    ]
    state["other_events"] = [
        {"name": "Bridge to Brisbane", "distance": "10k", "date": shared_date}
    ]
    result = run_assemble(page, state)
    assert any("shares a date" in e.lower() for e in result["errors"])


def test_long_run_day_on_rest_day_blocks(page: Page) -> None:
    """A long run day that's also a rest day blocks handoff."""
    state = valid_state()
    state["weekly_schedule"]["long_run_day"] = "Monday"
    result = run_assemble(page, state)
    assert any("long run day" in e.lower() for e in result["errors"])


def test_long_run_day_off_rest_day_passes(page: Page) -> None:
    """A long run day that isn't a rest day is allowed."""
    result = run_assemble(page, valid_state())
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_rest_days_empty_lets_rundrafter_decide(page: Page) -> None:
    """An empty rest_days override is pruned entirely rather than emitted as
    `[]` - the resolver picks rest days itself when the runner leaves this
    override blank."""
    state = valid_state()
    state["weekly_schedule"]["rest_days"] = []
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert "rest_days" not in result["intake"]["weekly_schedule"]
    assert_schema_valid(result["intake"])


def test_long_run_day_on_unavailable_day_blocks(page: Page) -> None:
    """A long run day with both halves unticked in the grid blocks handoff."""
    state = valid_state()
    state["weekly_schedule"]["availability"] = {
        "Tuesday": {"morning": False, "evening": False}
    }
    state["weekly_schedule"]["long_run_day"] = "Tuesday"
    result = run_assemble(page, state)
    assert any("long run day" in e.lower() for e in result["errors"])


def test_rest_days_omitting_unavailable_day_blocks(page: Page) -> None:
    """A rest_days override that omits a fully-unticked day blocks handoff."""
    state = valid_state()
    state["weekly_schedule"]["availability"] = {
        "Tuesday": {"morning": False, "evening": False}
    }
    result = run_assemble(page, state)
    assert any("rest day" in e.lower() and "tuesday" in e.lower() for e in result["errors"])


def test_rest_days_covering_unavailable_day_passes(page: Page) -> None:
    """A rest_days override that covers every fully-unticked day is allowed."""
    state = valid_state()
    state["weekly_schedule"]["availability"] = {
        "Tuesday": {"morning": False, "evening": False}
    }
    state["weekly_schedule"]["rest_days"] = ["Monday", "Tuesday"]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_preferred_session_on_unavailable_day_blocks(page: Page) -> None:
    """A preferred session on a fully-unticked day blocks handoff."""
    state = valid_state()
    state["weekly_schedule"]["availability"] = {
        "Tuesday": {"morning": False, "evening": False}
    }
    state["weekly_schedule"]["preferred_sessions"] = [
        {"day": "Tuesday", "description": "tempo"}
    ]
    result = run_assemble(page, state)
    assert any("preferred session" in e.lower() for e in result["errors"])


def test_preferred_session_off_unavailable_day_passes(page: Page) -> None:
    """A preferred session scheduled on an available day is allowed."""
    state = valid_state()
    state["weekly_schedule"]["availability"] = {
        "Tuesday": {"morning": False, "evening": False}
    }
    state["weekly_schedule"]["rest_days"] = ["Monday", "Tuesday"]
    state["weekly_schedule"]["preferred_sessions"] = [
        {"day": "Wednesday", "description": "intervals"}
    ]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_preferred_session_distance_without_effort_blocks(page: Page) -> None:
    """A preferred session with distance but no effort blocks with a friendly
    message naming the row, rather than a raw Ajv dependentRequired error."""
    state = valid_state()
    state["weekly_schedule"]["preferred_sessions"] = [
        {"day": "Wednesday", "description": "parkrun", "distance": 5}
    ]
    result = run_assemble(page, state)
    assert any("parkrun" in e and "anchor session" in e for e in result["errors"])


def test_preferred_session_effort_without_distance_blocks(page: Page) -> None:
    """A preferred session with effort but no distance blocks the same way."""
    state = valid_state()
    state["weekly_schedule"]["preferred_sessions"] = [
        {"day": "Wednesday", "description": "parkrun", "effort": "easy"}
    ]
    result = run_assemble(page, state)
    assert any("parkrun" in e and "anchor session" in e for e in result["errors"])


def test_preferred_session_with_both_distance_and_effort_passes(page: Page) -> None:
    """A preferred session with both distance and effort is a valid anchor
    session and does not block."""
    state = valid_state()
    state["weekly_schedule"]["preferred_sessions"] = [
        {
            "day": "Wednesday",
            "description": "parkrun",
            "distance": 5,
            "effort": "easy",
        }
    ]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_preferred_session_on_rest_day_blocks(page: Page) -> None:
    """A preferred session scheduled on a rest day blocks handoff."""
    state = valid_state()
    state["weekly_schedule"]["preferred_sessions"] = [
        {"day": "Monday", "description": "easy jog"}
    ]
    result = run_assemble(page, state)
    assert any("preferred session" in e.lower() for e in result["errors"])


def test_preferred_session_off_rest_day_passes(page: Page) -> None:
    """A preferred session scheduled on a non-rest day is allowed."""
    state = valid_state()
    state["weekly_schedule"]["preferred_sessions"] = [
        {"day": "Wednesday", "description": "intervals"}
    ]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_recent_result_stale_warns_without_blocking(page: Page) -> None:
    """A recent result >6 months before start_date warns but still hands off."""
    state = valid_state()
    state["recent_result"]["date"] = "2025-11-01"
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert any("6 months" in w for w in result["warnings"])
    assert_schema_valid(result["intake"])


def test_valid_state_has_no_warnings(page: Page) -> None:
    """A form-state within all thresholds produces no warnings."""
    result = run_assemble(page, valid_state())
    assert result["warnings"] == []


def test_five_unavailable_days_warns_without_blocking(page: Page) -> None:
    """5+ fully-unticked days guarantee fewer than 3 trainable days - a
    non-blocking advisory mirroring SCHEDULE_UNDER_CONSTRAINED."""
    state = valid_state()
    state["weekly_schedule"]["availability"] = {
        day: {"morning": False, "evening": False}
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    }
    state["weekly_schedule"]["rest_days"] = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
    ]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert any("trainable" in w.lower() for w in result["warnings"])
    assert_schema_valid(result["intake"])


def test_four_unavailable_days_does_not_warn(page: Page) -> None:
    """4 fully-unticked days still leaves 3 possibly-trainable days, so no
    advisory fires - the threshold is 5, not 4."""
    state = valid_state()
    state["weekly_schedule"]["availability"] = {
        day: {"morning": False, "evening": False}
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday"]
    }
    state["weekly_schedule"]["rest_days"] = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
    ]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert result["warnings"] == []
    assert_schema_valid(result["intake"])


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
        "strength_cross",
        "preferences",
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
    page.fill("#runner-name", "Alex Smith")
    page.select_option("#runner-experience", "experienced")

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

    page.select_option("#schedule-long-run-day", "Sunday")
    page.check('input[name="weekly_schedule.rest_days"][value="Monday"]')

    page.check('input[name="consent.disclaimer_accepted"]')

    with page.expect_download() as download_info:
        page.click('button[type="submit"]')

    downloaded = json.loads(Path(download_info.value.path()).read_text())
    assert_schema_valid(downloaded)


def test_empty_required_field_shows_inline_error(page: Page) -> None:
    """Submitting with a required field left blank (novalidate lets it reach
    Ajv) shows a `.field-error` right next to that field, not just a
    summary-only Ajv message."""
    page.fill("#runner-name", "Alex Smith")
    page.select_option("#runner-experience", "experienced")

    page.select_option("#goal-distance", "marathon")
    page.fill("#goal-date", "2026-10-11")
    page.fill("#goal-target-time", "3:45:00")
    page.fill("#goal-start-date", "2026-06-01")

    page.select_option("#recent-result-distance", "half")
    page.fill("#recent-result-time", "1:45:00")
    page.fill("#recent-result-date", "2026-05-01")

    page.fill("#fitness-weekly-distance", "40")
    page.fill("#fitness-longest-run", "18")

    page.select_option("#schedule-long-run-day", "Sunday")
    page.check('input[name="weekly_schedule.rest_days"][value="Monday"]')

    page.check('input[name="consent.disclaimer_accepted"]')

    # goal.race is left blank.
    page.click('button[type="submit"]')

    race_field = page.locator('[name="goal.race"]')
    assert race_field.get_attribute("aria-invalid") == "true"
    error_id = race_field.get_attribute("aria-describedby")
    assert page.locator(f"#{error_id}").inner_text() == "goal.race: This field is required."
