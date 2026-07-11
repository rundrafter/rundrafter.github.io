"""Email handoff suite (T6): mailto composition + the success screen.

Drives the real handoff.js and index.html in a browser, per
docs/architecture.md, so the same module the shipped page uses is under test.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from playwright.sync_api import Page

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
RETURN_EMAIL = "eric.parkin@protonmail.com"


def valid_state() -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / "valid.json").read_text())


def build_mailto_url(page: Page, intake: dict[str, Any]) -> str:
    """Call the real buildMailtoUrl in-page."""
    return page.evaluate(
        """async (intake) => {
            const { buildMailtoUrl } = await import('./assets/handoff.js');
            return buildMailtoUrl(intake);
        }""",
        intake,
    )


def parse_mailto(url: str) -> tuple[str, dict[str, str]]:
    """Parse a mailto: URL's query with `unquote` only (not `unquote_plus` /
    `parse_qs`, which would decode `+` as space and mask RFC 6068 violations)."""
    split = urlsplit(url)
    assert split.scheme == "mailto"
    assert "+" not in split.query, "mailto query must be percent-encoded, not form-encoded"
    params = {}
    for pair in split.query.split("&"):
        key, _, value = pair.partition("=")
        params[key] = unquote(value)
    return split.path, params


def test_return_email_constant() -> None:
    """The vendored source module exports the configured return address."""
    text = (REPO_ROOT / "assets" / "handoff.js").read_text()
    assert f'"{RETURN_EMAIL}"' in text


def test_mailto_recipient_and_defaults(page: Page) -> None:
    """A minimal intake (no runner.name) still produces a usable mailto:."""
    result = build_mailto_url(page, {"goal": {"race": "Melbourne Marathon"}})
    recipient, params = parse_mailto(result)
    assert recipient == RETURN_EMAIL
    assert "Melbourne Marathon" in params["subject"]
    assert "intake.json" in params["body"]


def test_mailto_subject_includes_runner_name_and_race(page: Page) -> None:
    """Subject is composed from runner.name + goal.race per ADR 003."""
    result = build_mailto_url(
        page,
        {"runner": {"name": "Alex Smith"}, "goal": {"race": "Melbourne Marathon"}},
    )
    _, params = parse_mailto(result)
    assert params["subject"] == "RunDrafter intake — Alex Smith, Melbourne Marathon"


def test_mailto_subject_falls_back_without_runner_name(page: Page) -> None:
    """No runner section: subject still composes from the race alone."""
    result = build_mailto_url(page, {"goal": {"race": "Melbourne Marathon"}})
    _, params = parse_mailto(result)
    assert params["subject"] == "RunDrafter intake — Melbourne Marathon"


def test_success_screen_after_valid_submission(page: Page) -> None:
    """A valid submission shows the success screen with a prefilled mailto,
    the plain-text return address, and a working download-again link."""
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

    with page.expect_download():
        page.click('button[type="submit"]')

    success = page.locator("#success-screen")
    assert success.is_visible()
    assert not page.locator("#intake-form").is_visible()

    assert page.locator("#return-email").inner_text() == RETURN_EMAIL

    mailto_href = page.locator("#email-it-in").get_attribute("href")
    recipient, params = parse_mailto(mailto_href)
    assert recipient == RETURN_EMAIL
    assert "Melbourne Marathon" in params["subject"]

    with page.expect_download() as download_again_info:
        page.click("#download-again")
    downloaded = json.loads(Path(download_again_info.value.path()).read_text())
    assert downloaded["goal"]["race"] == "Melbourne Marathon"
