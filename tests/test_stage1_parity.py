"""Executable parity test against the real upstream stage-1 validator.

Guards against the root cause of docs/spec/pre-deploy-hardening.md's finding
A: run-drafter's `validate.py` cross-field rules drifting silently out of
sync with their client-side re-implementation in assemble.js. Every intake
this suite considers valid is piped through the real
`rundrafter validate` CLI (sibling checkout) and must come back clean.

Skipped when the sibling isn't checked out (e.g. CI, until the PAT from
webform.md's manual step 8 exists) - see H5 in the hardening plan.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
UPSTREAM_DIR = REPO_ROOT.parent / "run-drafter"
NOW = "2026-01-01T00:00:00.000Z"

pytestmark = pytest.mark.skipif(
    not UPSTREAM_DIR.is_dir(),
    reason="../run-drafter sibling checkout not present",
)


def load_fixture(name: str) -> dict[str, Any]:
    """Load a form-state fixture JSON file by name."""
    return json.loads((FIXTURES_DIR / name).read_text())


def run_assemble(page: Page, form_state: dict[str, Any], now: str = NOW):
    """Call the real assemble.js module in-page with the given form-state."""
    return page.evaluate(
        """async ({ formState, now }) => {
            const { assemble } = await import('./assets/assemble.js');
            return assemble(formState, { now });
        }""",
        {"formState": form_state, "now": now},
    )


def assert_passes_stage1(tmp_path: Path, intake: dict[str, Any], name: str) -> None:
    """Run `intake` through the real upstream CLI; fail with its error list."""
    intake_path = tmp_path / f"{name}.json"
    intake_path.write_text(json.dumps(intake))
    canonical_path = tmp_path / f"{name}-canonical.json"
    report_path = tmp_path / f"{name}-report.json"
    subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(UPSTREAM_DIR),
            "rundrafter",
            "validate",
            str(intake_path),
            str(canonical_path),
            str(report_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    report = json.loads(report_path.read_text())
    assert report["errors"] == [], f"{name} failed stage 1: {report['errors']}"


def test_valid_fixture_passes_stage1(tmp_path: Path, page: Page) -> None:
    """The minimal required-only fixture clears the real stage-1 validator."""
    result = run_assemble(page, load_fixture("valid.json"))
    assert result["errors"] == []
    assert_passes_stage1(tmp_path, result["intake"], "valid")


def test_golden_fixture_passes_stage1(tmp_path: Path, page: Page) -> None:
    """The fully filled golden fixture clears the real stage-1 validator."""
    result = run_assemble(page, load_fixture("golden.json"))
    assert result["errors"] == []
    assert_passes_stage1(tmp_path, result["intake"], "golden")


def test_dom_smoke_download_passes_stage1(tmp_path: Path, page: Page) -> None:
    """A real form fill-and-download clears the real stage-1 validator."""
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
    assert_passes_stage1(tmp_path, downloaded, "dom-smoke")
