"""Cross-field + conditional assembler rules (T4).

Drives assemble.js in a real browser via Playwright, per
docs/spec/webform.md: same module + logic the shipped page uses, not a
second implementation of the rules.
"""

from __future__ import annotations

import copy
import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page, sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
NOW = "2026-01-01T00:00:00.000Z"

VALID_STATE: dict[str, Any] = {
    "units": "km",
    "goal": {
        "race": "Melbourne Marathon",
        "distance": "marathon",
        "date": "2026-10-11",
        "target_time": "3:45:00",
        "start_date": "2026-06-01",
    },
    "recent_result": {
        "distance": "half",
        "time": "1:45:00",
        "date": "2026-05-01",
    },
    "current_fitness": {"weekly_distance": 40, "longest_run": 18},
    "weekly_schedule": {
        "days_available": 5,
        "long_run_day": "Sunday",
        "rest_days": ["Monday"],
    },
    "preferences": {"calibrate_to": "current"},
    "health_screen": {
        "heart_condition": False,
        "chest_pain_activity": False,
        "chest_pain_rest": False,
        "dizziness_balance": False,
        "bone_joint_problem": False,
        "bp_or_heart_meds": False,
        "pregnancy": False,
        "recent_surgery_illness": False,
    },
    "consent": {"disclaimer_accepted": True},
    "output": {"formats": ["spreadsheet"], "tracking": False},
}


@pytest.fixture(scope="session")
def base_url():
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
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(browser, base_url):
    page = browser.new_page()
    page.goto(f"{base_url}/index.html")
    yield page
    page.close()


def run_assemble(page: Page, form_state: dict[str, Any], now: str = NOW):
    return page.evaluate(
        """async ({ formState, now }) => {
            const { assemble } = await import('./assets/assemble.js');
            return assemble(formState, { now });
        }""",
        {"formState": form_state, "now": now},
    )


def valid_state() -> dict[str, Any]:
    return copy.deepcopy(VALID_STATE)


def test_valid_state_has_no_errors(page: Page) -> None:
    result = run_assemble(page, valid_state())
    assert result["errors"] == []


def test_disclaimer_gate_blocks_without_acceptance(page: Page) -> None:
    state = valid_state()
    state["consent"] = {"disclaimer_accepted": False}
    result = run_assemble(page, state)
    assert any("disclaimer" in e.lower() for e in result["errors"])


def test_disclaimer_gate_blocks_when_missing(page: Page) -> None:
    state = valid_state()
    del state["consent"]
    result = run_assemble(page, state)
    assert any("disclaimer" in e.lower() for e in result["errors"])


def test_health_screen_flag_requires_acknowledgement(page: Page) -> None:
    state = valid_state()
    state["health_screen"]["chest_pain_activity"] = True
    result = run_assemble(page, state)
    assert any("acknowledg" in e.lower() for e in result["errors"])


def test_health_screen_flag_passes_with_acknowledgement(page: Page) -> None:
    state = valid_state()
    state["health_screen"]["chest_pain_activity"] = True
    state["consent"]["health_acknowledged"] = True
    result = run_assemble(page, state)
    assert result["errors"] == []


def test_health_screen_all_false_does_not_require_acknowledgement(
    page: Page,
) -> None:
    result = run_assemble(page, valid_state())
    assert not any("acknowledg" in e.lower() for e in result["errors"])


def test_start_date_after_goal_date_blocks(page: Page) -> None:
    state = valid_state()
    state["goal"]["start_date"] = "2026-11-01"
    result = run_assemble(page, state)
    assert any("start date" in e.lower() for e in result["errors"])


def test_start_date_equal_to_goal_date_passes(page: Page) -> None:
    state = valid_state()
    state["goal"]["start_date"] = state["goal"]["date"]
    result = run_assemble(page, state)
    assert result["errors"] == []


def test_b_race_on_or_after_goal_date_blocks(page: Page) -> None:
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
    state = valid_state()
    state["b_races"] = [
        {"name": "Tune-up 10k", "distance": "10k", "date": "2026-08-01"}
    ]
    result = run_assemble(page, state)
    assert result["errors"] == []


def test_other_event_on_or_after_goal_date_blocks(page: Page) -> None:
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
    state = valid_state()
    state["output"] = {"formats": [], "tracking": False}
    result = run_assemble(page, state)
    assert any("output format" in e.lower() for e in result["errors"])


def test_timestamps_set_at_handoff(page: Page) -> None:
    result = run_assemble(page, valid_state(), now="2026-03-15T09:30:00.000Z")
    assert result["intake"]["meta"]["submitted_at"] == "2026-03-15T09:30:00.000Z"
    assert result["intake"]["consent"]["accepted_at"] == "2026-03-15T09:30:00.000Z"
