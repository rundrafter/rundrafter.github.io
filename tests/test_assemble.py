"""Assembler test suite: cross-field rules (T4), fixtures + smoke test (T5).

Drives assemble.js and the real form in a browser via Playwright, per
rundrafter's docs/webform-architecture.md: same module + logic the shipped
page uses, not a second implementation of the rules.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from playwright.sync_api import Page

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
NOW = "2026-01-01T00:00:00.000Z"
SCHEMA = json.loads((REPO_ROOT / "schema" / "intake-schema.json").read_text())
CONSTRAINTS = json.loads((REPO_ROOT / "schema" / "form-constraints.json").read_text())

DAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def load_fixture(name: str) -> dict[str, Any]:
    """Load a form-state fixture JSON file by name."""
    return json.loads((FIXTURES_DIR / name).read_text())


def valid_state() -> dict[str, Any]:
    """A minimal form-state covering only the required sections."""
    return load_fixture("valid.json")


def cell(state: str = "session", **fields: Any) -> dict[str, Any]:
    """One tri-state availability-grid cell's form-state fragment."""
    return {"state": state, **fields}


def grid(**day_halves: dict[str, Any]) -> dict[str, Any]:
    """Build a weekly_schedule.grid form-state fragment.

    Keys are `<Day>_<half>` (e.g. `Tuesday_evening`); values are `cell(...)`.
    """
    result: dict[str, Any] = {}
    for key, value in day_halves.items():
        day, half = key.rsplit("_", 1)
        result.setdefault(day, {})[half] = value
    return result


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


def normalize_preferred_sessions(intake: dict[str, Any]) -> dict[str, Any]:
    """Normalize an intake's preferred_sessions for order/time_of_day-
    tolerant comparison.

    The tri-state grid always attaches time_of_day (the cell's column) and
    iterates in a fixed day/half order rather than insertion order, so a
    reproduction of a hand-authored fixture (which may omit time_of_day and
    use its own entry order) needs both normalized away before comparing.
    """
    schedule = intake.get("weekly_schedule")
    if not schedule or "preferred_sessions" not in schedule:
        return intake
    sessions = [
        {k: v for k, v in session.items() if k != "time_of_day"}
        for session in schedule["preferred_sessions"]
    ]
    sessions.sort(key=lambda s: (DAY_NAMES.index(s["day"]), json.dumps(s.get("type"))))
    return {**intake, "weekly_schedule": {**schedule, "preferred_sessions": sessions}}


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
            "target_time_mode": "specific",
            "target_time_m": 45,
            "target_time_s": 0,
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
            "target_time_mode": "specific",
            "target_time_m": 45,
            "target_time_s": 0,
        }
    ]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_b_race_finish_mode_omits_projection(page: Page) -> None:
    """A B race with 'Finish' selected assembles target_time: 'finish', with
    no structured time required (B races have no 'suggest' projection)."""
    state = valid_state()
    state["b_races"] = [
        {
            "name": "Tune-up 10k",
            "distance": "10k",
            "date": "2026-08-01",
            "target_time_mode": "finish",
        }
    ]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])
    assert result["intake"]["b_races"][0]["target_time"] == "finish"


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
            "target_time_mode": "specific",
            "target_time_m": 45,
            "target_time_s": 0,
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
            "target_time_mode": "specific",
            "target_time_m": 45,
            "target_time_s": 0,
        }
    ]
    state["other_events"] = [
        {"date": shared_date, "type": "easy", "description": "Bridge to Brisbane"}
    ]
    result = run_assemble(page, state)
    assert any("shares a date" in e.lower() for e in result["errors"])


def test_long_run_entry_with_other_half_unavailable_passes(page: Page) -> None:
    """A `type: "long"` session pinned to one half of a day, with that day's
    *other* half marked unavailable, assembles cleanly. Upstream's
    LONG_RUN_DAY_UNAVAILABLE (a `long` entry on a day whose *both* halves are
    unticked) is not re-implemented here: a session can only live in a cell
    that is itself in the "session" state, which by definition is not
    "unavailable", so a day can never be fully unavailable while also
    carrying a preferred session on it - the tri-state grid makes the
    contradiction structurally unreachable (stays upstream-only, catching
    only a hand-edited intake.json's independent `availability` /
    `preferred_sessions` keys)."""
    state = valid_state()
    state["weekly_schedule"] = {
        "grid": grid(
            Tuesday_morning=cell("unavailable"),
            Tuesday_evening=cell(type=["long"]),
        )
    }
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_multiple_long_entries_blocks(page: Page) -> None:
    """More than one `type: "long"` weekly session blocks handoff - at most
    one is allowed to pin the long-run day (ADR 019)."""
    state = valid_state()
    state["weekly_schedule"] = {
        "grid": grid(
            Sunday_evening=cell(type=["long"]),
            Saturday_morning=cell(type=["long"]),
        )
    }
    result = run_assemble(page, state)
    assert any(
        "more than one" in e and 'type: "long"' in e for e in result["errors"]
    )


def test_flexible_type_assembles_as_array(page: Page) -> None:
    """A cell offering several types keeps the array form through assembly
    and validates against the vendored schema."""
    state = valid_state()
    state["weekly_schedule"] = {
        "grid": grid(
            Wednesday_morning=cell(type=["easy", "quality"], description="club night")
        )
    }
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])
    session = result["intake"]["weekly_schedule"]["preferred_sessions"][0]
    assert session["type"] == ["easy", "quality"]
    assert session["time_of_day"] == "morning"


def test_single_ticked_type_collapses_to_string(page: Page) -> None:
    """The type checkboxes always yield an array, but one ticked type is the
    pinned case - it collapses to a bare string, the only spelling the schema
    accepts for it (`minItems: 2` on the array form)."""
    state = valid_state()
    state["weekly_schedule"] = {
        "grid": grid(Wednesday_morning=cell(type=["quality"]))
    }
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])
    session = result["intake"]["weekly_schedule"]["preferred_sessions"][0]
    assert session["type"] == "quality"


def test_no_ticked_type_omits_the_field(page: Page) -> None:
    """No type ticked emits no `type` at all rather than an empty array, so
    the schema's `required` reports it as a missing field."""
    state = valid_state()
    state["weekly_schedule"] = {"grid": grid(Wednesday_morning=cell(type=[]))}
    result = run_assemble(page, state)
    assert result["errors"] == []
    session = result["intake"]["weekly_schedule"]["preferred_sessions"][0]
    assert "type" not in session


def test_flexible_type_including_long_blocks(page: Page) -> None:
    """A cell offering the long run among several types blocks handoff - the
    long-run pin is resolved once per plan (FLEXIBLE_TYPE_INCLUDES_LONG)."""
    state = valid_state()
    state["weekly_schedule"] = {
        "grid": grid(Saturday_morning=cell(type=["long", "easy"]))
    }
    result = run_assemble(page, state)
    assert any("long run" in e.lower() and "Saturday" in e for e in result["errors"])


def test_flexible_type_mixing_modes_blocks(page: Page) -> None:
    """A cell mixing running and non-running types blocks handoff - rest-day
    placement needs a definite answer (FLEXIBLE_TYPE_MIXES_MODES)."""
    state = valid_state()
    state["weekly_schedule"] = {
        "grid": grid(Wednesday_morning=cell(type=["easy", "strength"]))
    }
    result = run_assemble(page, state)
    assert any("non-running" in e and "Wednesday" in e for e in result["errors"])


def test_flexible_all_non_running_type_passes(page: Page) -> None:
    """A cell offering only non-running types is a well-formed flexible set."""
    state = valid_state()
    state["weekly_schedule"] = {
        "grid": grid(Wednesday_morning=cell(type=["strength", "cross_training"]))
    }
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_flexible_type_skipping_tailoring_blocks(page: Page) -> None:
    """Skipping tailoring on a set with a non-skip-tailorable type blocks
    handoff (FLEXIBLE_SKIP_TAILORING_UNSUPPORTED)."""
    state = valid_state()
    state["weekly_schedule"] = {
        "grid": grid(
            Wednesday_morning=cell(
                type=["easy", "quality"], skip_tailoring=True
            )
        )
    }
    result = run_assemble(page, state)
    assert any("skips tailoring" in e and "Wednesday" in e for e in result["errors"])


def test_uniformly_skip_tailorable_flexible_type_passes(page: Page) -> None:
    """Skipping tailoring is allowed when every offered type is one whose
    detail a coach can own."""
    state = valid_state()
    state["weekly_schedule"] = {
        "grid": grid(
            Wednesday_morning=cell(
                type=["strength", "cross_training"], skip_tailoring=True
            )
        )
    }
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])
    session = result["intake"]["weekly_schedule"]["preferred_sessions"][0]
    assert session["tailored"] is False


def test_other_event_flexible_type_including_long_blocks(page: Page) -> None:
    """The flexible-type rules apply to other_events too (task 10.6, ADR
    039): an other event offering the long run among several types blocks
    handoff the same way a weekly session does."""
    state = valid_state()
    state["other_events"] = [
        {"date": "2026-08-16", "type": ["long", "easy"], "description": "Charity fun run"}
    ]
    result = run_assemble(page, state)
    assert any("long run" in e.lower() for e in result["errors"])


def test_other_event_flexible_type_mixing_modes_blocks(page: Page) -> None:
    """An other event mixing running and non-running types blocks handoff
    (task 10.6) - same FLEXIBLE_TYPE_MIXES_MODES rule as weekly sessions."""
    state = valid_state()
    state["other_events"] = [
        {"date": "2026-08-16", "type": ["easy", "strength"], "description": "Charity fun run"}
    ]
    result = run_assemble(page, state)
    assert any("non-running" in e for e in result["errors"])


def test_preferred_session_off_unavailable_day_passes(page: Page) -> None:
    """A weekly session scheduled on an available day is allowed."""
    state = valid_state()
    state["weekly_schedule"] = {
        "grid": grid(
            Tuesday_morning=cell("unavailable"),
            Tuesday_evening=cell("unavailable"),
            Wednesday_morning=cell(type=["quality"], description="intervals"),
        )
    }
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_preferred_session_distance_max_below_min_blocks(page: Page) -> None:
    """A weekly session with a maximum distance below its minimum blocks
    with a friendly message naming the row (mirrors DISTANCE_RANGE_INVALID)."""
    state = valid_state()
    state["weekly_schedule"] = {
        "grid": grid(
            Wednesday_morning=cell(
                type=["quality"],
                description="parkrun",
                distance_min=10,
                distance_max=5,
            )
        )
    }
    result = run_assemble(page, state)
    assert any("parkrun" in e and "distance" in e.lower() for e in result["errors"])


def test_preferred_session_distance_range_valid_passes(page: Page) -> None:
    """A weekly session whose maximum distance is >= its minimum is allowed."""
    state = valid_state()
    state["weekly_schedule"] = {
        "grid": grid(
            Wednesday_morning=cell(
                type=["quality"],
                description="parkrun",
                distance_min=5,
                distance_max=5,
            )
        )
    }
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


def _unavailable_grid(day_count: int) -> dict[str, Any]:
    """A grid with the first `day_count` weekdays fully unticked (both
    halves), leaving `7 - day_count` weekdays with at least one available
    half."""
    return grid(
        **{
            f"{day}_{half}": cell("unavailable")
            for day in DAY_NAMES[:day_count]
            for half in ["morning", "evening"]
        }
    )


def test_unavailable_days_at_run_day_floor_passes(page: Page) -> None:
    """Exactly `min_run_days_at_peak` weekdays left with an available half
    blocks neither on SCHEDULE_BELOW_RUN_DAY_FLOOR nor the older
    trainable-days warning - the boundary case."""
    floor = CONSTRAINTS["min_run_days_at_peak"]
    state = valid_state()
    state["weekly_schedule"] = {"grid": _unavailable_grid(7 - floor)}
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert result["warnings"] == []
    assert_schema_valid(result["intake"])


def test_unavailable_days_below_run_day_floor_blocks(page: Page) -> None:
    """One weekday short of `min_run_days_at_peak` blocks on
    SCHEDULE_BELOW_RUN_DAY_FLOOR (task 10.2) - no rest-day placement can
    raise this upper bound on trainable days. `MIN_TRAINABLE_DAYS` (3) is
    stricter than most configured floors, so this boundary case trips only
    the blocking error, not the older warning."""
    floor = CONSTRAINTS["min_run_days_at_peak"]
    state = valid_state()
    state["weekly_schedule"] = {"grid": _unavailable_grid(8 - floor)}
    result = run_assemble(page, state)
    assert any("running days" in e.lower() for e in result["errors"])


def test_five_unavailable_days_blocks_and_warns(page: Page) -> None:
    """5+ fully-unavailable days guarantee fewer than 3 trainable days,
    tripping both SCHEDULE_BELOW_RUN_DAY_FLOOR (blocking) and the older,
    non-blocking trainable-days advisory mirroring SCHEDULE_UNDER_CONSTRAINED
    - the two now overlap since `min_run_days_at_peak` (task 10.2) is
    typically >= `MIN_TRAINABLE_DAYS` (3)."""
    state = valid_state()
    state["weekly_schedule"] = {"grid": _unavailable_grid(5)}
    result = run_assemble(page, state)
    assert any("running days" in e.lower() for e in result["errors"])
    assert any("trainable" in w.lower() for w in result["warnings"])


def test_plan_window_too_short_for_goal_distance_blocks(page: Page) -> None:
    """A plan window shorter than base + minimum build + taper for the
    goal's distance blocks handoff (task 10.1) - `valid_state`'s marathon
    goal needs far more than the 4 weeks between start_date and date here."""
    state = valid_state()
    state["goal"]["date"] = "2026-06-29"
    result = run_assemble(page, state)
    assert any(
        "fewer than the" in e and "marathon goal needs" in e for e in result["errors"]
    )


def test_quality_touchpoints_at_ceiling_passes(page: Page) -> None:
    """Exactly `max_quality_touchpoints` pinned touchpoint days, spaced
    apart, does not exceed the ceiling (task 10.3)."""
    state = valid_state()
    state["weekly_schedule"] = {
        "grid": grid(
            Monday_morning=cell(type=["quality"]),
            Wednesday_morning=cell(type=["quality"]),
            Friday_morning=cell(type=["quality"]),
        )
    }
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])


def test_quality_touchpoints_exceeding_ceiling_blocks(page: Page) -> None:
    """More pinned quality/long touchpoint days than the configured ceiling
    blocks handoff (task 10.3) - the long run counts as a touchpoint in its
    own right. Days are spaced apart so this trips only the ceiling, not the
    adjacency rule below."""
    state = valid_state()
    state["weekly_schedule"] = {
        "grid": grid(
            Monday_morning=cell(type=["quality"]),
            Wednesday_morning=cell(type=["quality"]),
            Friday_morning=cell(type=["quality"]),
            Sunday_evening=cell(type=["long"]),
        )
    }
    result = run_assemble(page, state)
    assert any("quality touchpoints" in e.lower() for e in result["errors"])


def test_adjacent_quality_days_blocks(page: Page) -> None:
    """Two pinned quality days on consecutive weekdays blocks handoff (task
    10.3)."""
    state = valid_state()
    state["weekly_schedule"] = {
        "grid": grid(
            Saturday_morning=cell(type=["quality"]),
            Sunday_morning=cell(type=["quality"]),
        )
    }
    result = run_assemble(page, state)
    assert any("adjacent" in e.lower() for e in result["errors"])


def test_sunday_monday_quality_days_count_as_adjacent(page: Page) -> None:
    """Sunday and Monday count as adjacent too, since the weekly template
    repeats (task 10.3)."""
    state = valid_state()
    state["weekly_schedule"] = {
        "grid": grid(
            Sunday_morning=cell(type=["quality"]),
            Monday_morning=cell(type=["quality"]),
        )
    }
    result = run_assemble(page, state)
    assert any("adjacent" in e.lower() for e in result["errors"])


def test_event_on_fully_unavailable_day_warns(page: Page) -> None:
    """A B race landing on a weekday with no available half warns, without
    blocking - the event always wins (task 10.4)."""
    state = valid_state()
    state["weekly_schedule"] = {
        "grid": grid(
            Tuesday_morning=cell("unavailable"), Tuesday_evening=cell("unavailable")
        )
    }
    state["b_races"] = [
        {
            "name": "Tune-up 10k",
            "distance": "10k",
            "date": "2026-08-18",  # a Tuesday within the plan window
            "target_time_mode": "finish",
        }
    ]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert any("takes precedence" in w for w in result["warnings"])
    assert_schema_valid(result["intake"])


def test_event_clashing_with_preferred_session_warns(page: Page) -> None:
    """An other event landing on a weekday carrying a preferred session
    warns that the event displaces it (task 10.4)."""
    state = valid_state()
    state["weekly_schedule"] = {
        "grid": grid(Wednesday_morning=cell(type=["quality"], description="intervals"))
    }
    state["other_events"] = [
        {
            "date": "2026-08-19",  # a Wednesday within the plan window
            "type": "easy",
            "description": "Charity fun run",
        }
    ]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert any("takes precedence" in w for w in result["warnings"])
    assert_schema_valid(result["intake"])


def test_goal_faster_than_fitness_warns(page: Page) -> None:
    """A goal target time implying a VDOT well above current fitness warns,
    without blocking - training paces still follow current fitness, not the
    goal (task 10.5)."""
    state = valid_state()
    state["goal"]["target_time_h"] = 2
    state["goal"]["target_time_m"] = 30
    state["goal"]["target_time_s"] = 0
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert any("above your current vdot" in w.lower() for w in result["warnings"])
    assert_schema_valid(result["intake"])


def test_goal_slower_than_fitness_warns(page: Page) -> None:
    """A goal target time implying a VDOT well below current fitness warns
    too (task 10.5)."""
    state = valid_state()
    state["goal"]["target_time_h"] = 5
    state["goal"]["target_time_m"] = 30
    state["goal"]["target_time_s"] = 0
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert any("below your current vdot" in w.lower() for w in result["warnings"])
    assert_schema_valid(result["intake"])


def test_goal_consistency_skipped_for_suggest_mode(page: Page) -> None:
    """A 'suggest' goal has no specific goal pace to compare and is
    calibrated from current fitness, so it's consistent by construction -
    the goal-consistency check is skipped entirely (task 10.5)."""
    state = valid_state()
    state["goal"]["target_time_mode"] = "suggest"
    for key in ("target_time_h", "target_time_m", "target_time_s"):
        state["goal"].pop(key, None)
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert result["warnings"] == []


def test_timestamps_set_at_handoff(page: Page) -> None:
    """submitted_at is stamped with the handoff time."""
    result = run_assemble(page, valid_state(), now="2026-03-15T09:30:00.000Z")
    assert result["intake"]["meta"]["submitted_at"] == "2026-03-15T09:30:00.000Z"


def test_blank_optional_sections_are_omitted(page: Page) -> None:
    """Optional sections left blank are omitted, not emitted as empty objects."""
    result = run_assemble(page, valid_state())
    intake = result["intake"]
    for key in ("b_races", "other_events", "notes", "output"):
        assert key not in intake


def test_untouched_grid_omits_weekly_schedule(page: Page) -> None:
    """A grid with no cell touched (all default 'available') assembles to no
    `weekly_schedule` key at all - the tri-state grid's "absent = available"
    contract (task 9.11)."""
    state = valid_state()
    del state["weekly_schedule"]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])
    assert "weekly_schedule" not in result["intake"]


def test_generic_quality_detail_included(page: Page) -> None:
    """Picking 'generic' quality detail is carried into `output`."""
    state = valid_state()
    state["output"] = {"quality_detail": "generic"}
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert_schema_valid(result["intake"])
    assert result["intake"]["output"] == {"quality_detail": "generic"}


def test_default_quality_detail_omits_output(page: Page) -> None:
    """The default 'specific' quality detail omits `output` entirely,
    matching every other section's sparse-by-construction contract."""
    state = valid_state()
    state["output"] = {"quality_detail": "specific"}
    result = run_assemble(page, state)
    assert "output" not in result["intake"]


def test_vdot_computed_from_recent_result(page: Page) -> None:
    """current_fitness.vdot is computed client-side from recent_result and
    submitted alongside the runner's own fitness figures. valid.json's half
    marathon in 1:45:00 is VDOT ~42.63 (rundrafter's compute_vdot)."""
    result = run_assemble(page, valid_state())
    assert result["errors"] == []
    assert_schema_valid(result["intake"])
    assert result["intake"]["current_fitness"]["vdot"] == pytest.approx(42.63, abs=0.5)


def test_vdot_omitted_without_weekly_distance_or_longest_run(page: Page) -> None:
    """vdot is only submitted when current_fitness already carries both
    fields the schema requires whenever the section is present at all - a
    partial current_fitness is already schema-invalid regardless of vdot,
    so this only asserts vdot doesn't compound the problem."""
    state = valid_state()
    del state["current_fitness"]["weekly_distance"]
    result = run_assemble(page, state)
    assert result["errors"] == []
    assert "vdot" not in result["intake"]["current_fitness"]


def test_golden_fixture_reproduces_intake_example(page: Page) -> None:
    """A fully filled form-state reproduces the vendored golden example,
    modulo preferred_sessions order and time_of_day (see
    normalize_preferred_sessions)."""
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
    assert normalize_preferred_sessions(result["intake"]) == normalize_preferred_sessions(
        example
    )
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


def test_flexible_fixture_assembles_and_validates(page: Page) -> None:
    """A flexible form-state (a running cell offering easy-or-quality, a
    non-running cell offering strength-or-cross-training, and a
    single-ticked long run) assembles cleanly, validates, and keeps one
    spelling per meaning: array only where the runner offered a real choice."""
    result = run_assemble(page, load_fixture("flexible.json"))
    assert result["errors"] == []
    assert_schema_valid(result["intake"])
    types = {
        session["day"]: session["type"]
        for session in result["intake"]["weekly_schedule"]["preferred_sessions"]
    }
    assert types == {
        "Sunday": "long",
        "Wednesday": ["easy", "quality"],
        "Friday": ["strength", "cross_training"],
    }


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


def fill_required_fields(page: Page) -> None:
    """Fill every field the form needs to reach a download, nothing more."""
    page.fill("#runner-name", "Alex Smith")
    page.select_option("#runner-experience", "experienced")

    page.fill("#goal-race", "Melbourne Marathon")
    page.select_option("#goal-distance", "marathon")
    page.fill("#goal-date", "2026-10-11")
    page.fill("#goal-target-time-h", "3")
    page.fill("#goal-target-time-m", "45")
    page.fill("#goal-target-time-s", "0")
    page.fill("#goal-start-date", "2026-06-01")

    page.select_option("#recent-result-distance", "half")
    page.fill("#recent-result-time-h", "1")
    page.fill("#recent-result-time-m", "45")
    page.fill("#recent-result-time-s", "0")
    page.fill("#recent-result-date", "2026-05-01")

    page.fill("#fitness-weekly-distance", "40")
    page.fill("#fitness-longest-run", "18")


def test_dom_smoke_fill_download_validates(page: Page) -> None:
    """Filling the real form and submitting downloads a schema-valid intake.json."""
    fill_required_fields(page)

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
    page.fill("#goal-target-time-h", "3")
    page.fill("#goal-target-time-m", "45")
    page.fill("#goal-target-time-s", "0")
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


def test_dom_smoke_flexible_types_download_as_array(page: Page) -> None:
    """Ticking several types on one grid cell downloads an intake whose
    `type` is the array of exactly those types, tagged with the cell's own
    time_of_day."""
    fill_required_fields(page)

    prefix = "weekly_schedule.grid.Wednesday.morning"
    page.check(f'[name="{prefix}.state"][value="session"]')
    page.check(f'[name="{prefix}.type"][value="easy"]')
    page.check(f'[name="{prefix}.type"][value="quality"]')

    with page.expect_download() as download_info:
        page.click('button[type="submit"]')

    downloaded = json.loads(Path(download_info.value.path()).read_text())
    session = downloaded["weekly_schedule"]["preferred_sessions"][0]
    assert session["type"] == ["easy", "quality"]
    assert session["time_of_day"] == "morning"
    assert_schema_valid(downloaded)


def test_dom_smoke_unavailable_cell_downloads_as_availability_override(page: Page) -> None:
    """Marking a tri-state grid cell 'Unavailable' downloads an intake with
    that half unticked in `weekly_schedule.availability` - the other tri-state
    (available/session) is exercised by the flexible-types test above."""
    fill_required_fields(page)

    prefix = "weekly_schedule.grid.Tuesday.morning"
    page.check(f'[name="{prefix}.state"][value="unavailable"]')

    with page.expect_download() as download_info:
        page.click('button[type="submit"]')

    downloaded = json.loads(Path(download_info.value.path()).read_text())
    assert downloaded["weekly_schedule"]["availability"]["Tuesday"] == {"morning": False}
    assert_schema_valid(downloaded)


def test_dom_smoke_structured_duration_composes_time_strings(page: Page) -> None:
    """The structured h/m/s duration controls compose into the schema's
    `H:MM:SS`/`M:SS` strings for goal.target_time and recent_result.time -
    `fill_required_fields` drives these controls; this asserts the composed
    values rather than just schema validity."""
    fill_required_fields(page)

    with page.expect_download() as download_info:
        page.click('button[type="submit"]')

    downloaded = json.loads(Path(download_info.value.path()).read_text())
    assert downloaded["goal"]["target_time"] == "3:45:00"
    assert downloaded["recent_result"]["time"] == "1:45:00"
    assert_schema_valid(downloaded)


def test_dom_smoke_b_race_structured_duration_composes(page: Page) -> None:
    """A B race's structured h/m/s duration control composes into
    `target_time` the same way the goal's does."""
    fill_required_fields(page)

    page.click("#add-b-race")
    page.fill('[name="b_races.0.name"]', "Tune-up 10k")
    page.select_option('[name="b_races.0.distance"]', "10k")
    page.fill('[name="b_races.0.date"]', "2026-08-16")
    page.check('[name="b_races.0.target_time_mode"][value="specific"]')
    page.fill('[name="b_races.0.target_time_m"]', "45")
    page.fill('[name="b_races.0.target_time_s"]', "0")

    with page.expect_download() as download_info:
        page.click('button[type="submit"]')

    downloaded = json.loads(Path(download_info.value.path()).read_text())
    assert downloaded["b_races"][0]["target_time"] == "45:00"
    assert_schema_valid(downloaded)


def test_dom_smoke_other_event_multi_type_downloads_as_array(page: Page) -> None:
    """Ticking several types on an other-events row downloads an intake
    whose `type` is the array of exactly those types. Uses easy+quality, not
    easy+long: FLEXIBLE_TYPE_INCLUDES_LONG now applies to other_events too
    (task 10.6), so a long-run entry can't be one option among several."""
    fill_required_fields(page)

    page.click("#add-other-event")
    page.fill('[name="other_events.0.date"]', "2026-08-16")
    page.check('[name="other_events.0.type"][value="easy"]')
    page.check('[name="other_events.0.type"][value="quality"]')

    with page.expect_download() as download_info:
        page.click('button[type="submit"]')

    downloaded = json.loads(Path(download_info.value.path()).read_text())
    event = downloaded["other_events"][0]
    assert event["type"] == ["easy", "quality"]
    assert_schema_valid(downloaded)


def test_dom_smoke_generic_quality_detail_downloads(page: Page) -> None:
    """Selecting the generic quality-detail radio downloads an intake
    carrying `output.quality_detail: "generic"`."""
    fill_required_fields(page)
    page.check('input[name="output.quality_detail"][value="generic"]')

    with page.expect_download() as download_info:
        page.click('button[type="submit"]')

    downloaded = json.loads(Path(download_info.value.path()).read_text())
    assert downloaded["output"] == {"quality_detail": "generic"}
    assert_schema_valid(downloaded)


def test_dom_grid_cell_editor_hidden_until_session_selected(page: Page) -> None:
    """A grid cell's session editor is hidden by default (state:
    available) and reveals only once 'Has a session' is selected."""
    prefix = "weekly_schedule.grid.Wednesday.morning"
    editor = page.locator(
        f'.grid-cell:has([name="{prefix}.state"]) .cell-session-editor'
    )
    assert editor.is_hidden()

    page.check(f'[name="{prefix}.state"][value="session"]')
    assert editor.is_visible()

    page.check(f'[name="{prefix}.state"][value="unavailable"]')
    assert editor.is_hidden()


def test_dom_skip_tailoring_hidden_unless_every_type_supports_it(page: Page) -> None:
    """A grid cell's skip-tailoring tickbox appears only while every ticked
    type is one whose detail a coach can own, and clears itself when it
    hides."""
    prefix = "weekly_schedule.grid.Wednesday.morning"
    page.check(f'[name="{prefix}.state"][value="session"]')

    label = page.locator(
        f'label[data-skip-tailoring-for]:has([name="{prefix}.skip_tailoring"])'
    )
    checkbox = page.locator(f'[name="{prefix}.skip_tailoring"]')
    type_box = f'[name="{prefix}.type"]'

    assert label.is_hidden()

    page.check(f'{type_box}[value="strength"]')
    assert label.is_visible()

    page.check(f'{type_box}[value="cross_training"]')
    assert label.is_visible()

    checkbox.check()
    page.check(f'{type_box}[value="easy"]')
    assert label.is_hidden()
    assert checkbox.is_checked() is False


def test_empty_required_field_shows_inline_error(page: Page) -> None:
    """Submitting with a required field left blank (novalidate lets it reach
    Ajv) shows a `.field-error` right next to that field, not just a
    summary-only Ajv message."""
    page.fill("#runner-name", "Alex Smith")
    page.select_option("#runner-experience", "experienced")

    page.select_option("#goal-distance", "marathon")
    page.fill("#goal-date", "2026-10-11")
    page.fill("#goal-target-time-h", "3")
    page.fill("#goal-target-time-m", "45")
    page.fill("#goal-target-time-s", "0")
    page.fill("#goal-start-date", "2026-06-01")

    page.select_option("#recent-result-distance", "half")
    page.fill("#recent-result-time-h", "1")
    page.fill("#recent-result-time-m", "45")
    page.fill("#recent-result-time-s", "0")
    page.fill("#recent-result-date", "2026-05-01")

    page.fill("#fitness-weekly-distance", "40")
    page.fill("#fitness-longest-run", "18")

    # goal.race is left blank.
    page.click('button[type="submit"]')

    race_field = page.locator('[name="goal.race"]')
    assert race_field.get_attribute("aria-invalid") == "true"
    error_id = race_field.get_attribute("aria-describedby")
    assert page.locator(f"#{error_id}").inner_text() == "goal.race: This field is required."
