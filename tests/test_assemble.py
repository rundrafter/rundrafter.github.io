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
            "target_time": "45:00",
        }
    ]
    result = run_assemble(page, state)
    assert any("b race" in e.lower() for e in result["errors"])


def test_b_race_before_goal_date_passes(page: Page) -> None:
    """A B race before the goal race date is allowed."""
    state = valid_state()
    state["b_races"] = [
        {
            "name": "Tune-up 10k",
            "distance": "10k",
            "date": "2026-08-01",
            "target_time": "45:00",
        }
    ]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_other_event_on_or_after_goal_date_blocks(page: Page) -> None:
    """An other event on or after the goal race date blocks handoff."""
    state = valid_state()
    state["other_events"] = [
        {
            "date": state["goal"]["date"],
            "type": "easy",
            "description": "Charity fun run",
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
            "target_time": "45:00",
        }
    ]
    result = run_assemble(page, state)
    assert any("b race" in e.lower() for e in result["errors"])


def test_other_event_before_start_date_blocks(page: Page) -> None:
    """An other event before the plan start date blocks handoff."""
    state = valid_state()
    state["other_events"] = [
        {"date": "2026-01-01", "type": "easy", "description": "Charity fun run"}
    ]
    result = run_assemble(page, state)
    assert any("other event" in e.lower() for e in result["errors"])


def test_other_event_within_window_passes(page: Page) -> None:
    """An other event strictly between start_date and goal.date is allowed."""
    state = valid_state()
    state["other_events"] = [
        {"date": "2026-08-16", "type": "easy", "description": "Bridge to Brisbane"}
    ]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_duplicate_event_dates_blocks(page: Page) -> None:
    """A B race and an other event sharing a date blocks handoff."""
    state = valid_state()
    shared_date = "2026-08-16"
    state["b_races"] = [
        {
            "name": "Tune-up 10k",
            "distance": "10k",
            "date": shared_date,
            "target_time": "45:00",
        }
    ]
    state["other_events"] = [
        {"date": shared_date, "type": "easy", "description": "Bridge to Brisbane"}
    ]
    result = run_assemble(page, state)
    assert any("shares a date" in e.lower() for e in result["errors"])


def test_long_run_entry_on_unavailable_day_blocks(page: Page) -> None:
    """A `type: "long"` weekly session on a fully-unticked day blocks
    handoff (ADR 019 - long_run_day is gone; the template entry is the only
    override)."""
    state = valid_state()
    state["weekly_schedule"]["availability"] = {
        "Tuesday": {"morning": False, "evening": False}
    }
    state["weekly_schedule"]["preferred_sessions"] = [
        {"day": "Tuesday", "type": "long"}
    ]
    result = run_assemble(page, state)
    assert any('type: "long"' in e for e in result["errors"])


def test_multiple_long_entries_blocks(page: Page) -> None:
    """More than one `type: "long"` weekly session blocks handoff - at most
    one is allowed to pin the long-run day (ADR 019)."""
    state = valid_state()
    state["weekly_schedule"]["preferred_sessions"] = [
        {"day": "Sunday", "type": "long"},
        {"day": "Saturday", "type": "long"},
    ]
    result = run_assemble(page, state)
    assert any(
        "more than one" in e and 'type: "long"' in e for e in result["errors"]
    )


def test_preferred_session_on_unavailable_day_blocks(page: Page) -> None:
    """A weekly session on a fully-unticked day blocks handoff."""
    state = valid_state()
    state["weekly_schedule"]["availability"] = {
        "Tuesday": {"morning": False, "evening": False}
    }
    state["weekly_schedule"]["preferred_sessions"] = [
        {"day": "Tuesday", "type": "quality", "description": "tempo"}
    ]
    result = run_assemble(page, state)
    assert any("preferred session" in e.lower() for e in result["errors"])


def test_preferred_session_off_unavailable_day_passes(page: Page) -> None:
    """A weekly session scheduled on an available day is allowed."""
    state = valid_state()
    state["weekly_schedule"]["availability"] = {
        "Tuesday": {"morning": False, "evening": False}
    }
    state["weekly_schedule"]["preferred_sessions"] = [
        {"day": "Wednesday", "type": "quality", "description": "intervals"}
    ]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_preferred_session_distance_max_below_min_blocks(page: Page) -> None:
    """A weekly session with a maximum distance below its minimum blocks
    with a friendly message naming the row (mirrors DISTANCE_RANGE_INVALID)."""
    state = valid_state()
    state["weekly_schedule"]["preferred_sessions"] = [
        {
            "day": "Wednesday",
            "type": "quality",
            "description": "parkrun",
            "distance_min": 10,
            "distance_max": 5,
        }
    ]
    result = run_assemble(page, state)
    assert any("parkrun" in e and "distance" in e.lower() for e in result["errors"])


def test_preferred_session_distance_range_valid_passes(page: Page) -> None:
    """A weekly session whose maximum distance is >= its minimum is allowed."""
    state = valid_state()
    state["weekly_schedule"]["preferred_sessions"] = [
        {
            "day": "Wednesday",
            "type": "quality",
            "description": "parkrun",
            "distance_min": 5,
            "distance_max": 5,
        }
    ]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_other_event_distance_max_below_min_blocks(page: Page) -> None:
    """An other event with a maximum distance below its minimum blocks the
    same way as a weekly session."""
    state = valid_state()
    state["other_events"] = [
        {
            "date": "2026-08-16",
            "type": "easy",
            "description": "long run",
            "distance_min": 10,
            "distance_max": 5,
        }
    ]
    result = run_assemble(page, state)
    assert any("long run" in e and "distance" in e.lower() for e in result["errors"])


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
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert result["warnings"] == []
    assert_schema_valid(result["intake"])


def test_timestamps_set_at_handoff(page: Page) -> None:
    """submitted_at is stamped with the handoff time."""
    result = run_assemble(page, valid_state(), now="2026-03-15T09:30:00.000Z")
    assert result["intake"]["meta"]["submitted_at"] == "2026-03-15T09:30:00.000Z"


def test_blank_optional_sections_are_omitted(page: Page) -> None:
    """Optional sections left blank are omitted, not emitted as empty objects."""
    result = run_assemble(page, valid_state())
    intake = result["intake"]
    for key in ("b_races", "other_events", "notes"):
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


def test_coach_mode_fixture_assembles_and_validates(page: Page) -> None:
    """A coach-mode form-state (skip-tailored sessions with a distance range,
    plus a distance_max: 0 non-running day) assembles cleanly and validates
    (ADR 014)."""
    result = run_assemble(page, load_fixture("coach-mode.json"))
    assert result["errors"] == []
    assert_schema_valid(result["intake"])
    sessions = result["intake"]["weekly_schedule"]["preferred_sessions"]
    assert all(session["tailored"] is False for session in sessions)
    assert any(session.get("distance_max") == 0 for session in sessions)


def test_beginner_fixture_assembles_and_validates(page: Page) -> None:
    """A beginner form-state (no recent_result, target_time: suggest)
    assembles cleanly and validates (ADR 015 / ADR 016)."""
    result = run_assemble(page, load_fixture("beginner.json"))
    assert result["errors"] == []
    assert_schema_valid(result["intake"])
    assert "recent_result" not in result["intake"]
    assert result["intake"]["goal"]["target_time"] == "suggest"


def test_blank_current_fitness_omits_section(page: Page) -> None:
    """A runner with no honest weekly-distance/longest-run figure to give may
    leave the whole Current Fitness group blank; the assembled intake omits
    `current_fitness` entirely rather than emitting a partial object, and
    still validates (ADR 018)."""
    state = valid_state()
    del state["current_fitness"]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])
    assert "current_fitness" not in result["intake"]


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

    with page.expect_download() as download_info:
        page.click('button[type="submit"]')

    downloaded = json.loads(Path(download_info.value.path()).read_text())
    assert_schema_valid(downloaded)


def test_dom_smoke_blank_recent_result_omits_section(page: Page) -> None:
    """Leaving Recent Result entirely untouched in the real form - relying on
    the select's blank default rather than an explicit choice - downloads an
    intake.json with no `recent_result` key, and it still validates."""
    page.fill("#runner-name", "Alex Smith")
    page.select_option("#runner-experience", "experienced")

    page.fill("#goal-race", "Melbourne Marathon")
    page.select_option("#goal-distance", "marathon")
    page.fill("#goal-date", "2026-10-11")
    page.fill("#goal-target-time", "3:45:00")
    page.fill("#goal-start-date", "2026-06-01")

    page.fill("#fitness-weekly-distance", "40")
    page.fill("#fitness-longest-run", "18")

    with page.expect_download() as download_info:
        page.click('button[type="submit"]')

    downloaded = json.loads(Path(download_info.value.path()).read_text())
    assert "recent_result" not in downloaded
    assert_schema_valid(downloaded)


def test_dom_smoke_blank_current_fitness_omits_section(page: Page) -> None:
    """Leaving both Current Fitness fields blank in the real form - now that
    neither is `required` (ADR 018) - downloads an intake.json with no
    `current_fitness` key, and it still validates."""
    page.fill("#runner-name", "Alex Smith")
    page.select_option("#runner-experience", "new")

    page.fill("#goal-race", "Riverside Fun Run")
    page.select_option("#goal-distance", "10k")
    page.fill("#goal-date", "2026-10-11")
    page.check('input[name="goal.target_time_mode"][value="suggest"]')
    page.fill("#goal-start-date", "2026-06-01")

    with page.expect_download() as download_info:
        page.click('button[type="submit"]')

    downloaded = json.loads(Path(download_info.value.path()).read_text())
    assert "current_fitness" not in downloaded
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

    # goal.race is left blank.
    page.click('button[type="submit"]')

    race_field = page.locator('[name="goal.race"]')
    assert race_field.get_attribute("aria-invalid") == "true"
    error_id = race_field.get_attribute("aria-describedby")
    assert page.locator(f"#{error_id}").inner_text() == "goal.race: This field is required."
