"""VDOT parity test: the form's in-browser Daniels calculation against
rundrafter's real compute_vdot (design.md, "Client-side VDOT parity is an
executable test, not a review item").

Skipped when the sibling isn't checked out, matching test_stage1_parity.py.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from playwright.sync_api import Page

REPO_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_DIR = REPO_ROOT.parent / "rundrafter"

pytestmark = pytest.mark.skipif(
    not UPSTREAM_DIR.is_dir(),
    reason="../rundrafter sibling checkout not present",
)

DISTANCE_METRES = {"5k": 5000, "10k": 10000, "half": 21097, "marathon": 42195}

# A swept time range per accepted distance, fast to conservative, covering
# the input range broadly rather than a single point.
TIME_SWEEP = {
    "5k": ["15:00", "20:00", "25:00", "35:00"],
    "10k": ["32:00", "45:00", "55:00", "1:15:00"],
    "half": ["1:10:00", "1:35:00", "2:00:00", "2:30:00"],
    "marathon": ["2:30:00", "3:30:00", "4:30:00", "5:30:00"],
}

_PYTHON_VDOT_SCRIPT = """
import json, sys
from rundrafter.calibrate.calibrate import compute_vdot, parse_time_to_minutes

cases = json.loads(sys.argv[1])
print(json.dumps([
    compute_vdot(distance_m, parse_time_to_minutes(time_str))
    for distance_m, time_str in cases
]))
"""


def _tolerance() -> float:
    constraints = json.loads(
        (REPO_ROOT / "schema" / "form-constraints.json").read_text()
    )
    return constraints["vdot_match_tolerance"]


def _cases() -> list[tuple[str, str]]:
    return [
        (distance, time_str)
        for distance, times in TIME_SWEEP.items()
        for time_str in times
    ]


def _python_vdots(cases: list[tuple[str, str]]) -> list[float]:
    payload = [[DISTANCE_METRES[distance], time_str] for distance, time_str in cases]
    result = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(UPSTREAM_DIR),
            "python",
            "-c",
            _PYTHON_VDOT_SCRIPT,
            json.dumps(payload),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _browser_vdots(page: Page, cases: list[tuple[str, str]]) -> list[float]:
    return page.evaluate(
        """async (cases) => {
            const { computeVdotFromResult } = await import('./assets/vdot.js');
            return cases.map(([distance, time]) => computeVdotFromResult({ distance, time }));
        }""",
        cases,
    )


def test_vdot_matches_upstream_across_swept_times(page: Page) -> None:
    """The form's in-browser VDOT and rundrafter's compute_vdot agree within
    vdot_match_tolerance across every accepted distance and a swept time
    range - the same tolerance VDOT_MISMATCH uses upstream, so the test and
    the runtime check cannot disagree about what "close enough" means."""
    cases = _cases()
    tolerance = _tolerance()
    browser_vdots = _browser_vdots(page, cases)
    python_vdots = _python_vdots(cases)

    for (distance, time_str), browser_vdot, python_vdot in zip(
        cases, browser_vdots, python_vdots
    ):
        assert abs(browser_vdot - python_vdot) <= tolerance, (
            f"{distance} {time_str}: browser={browser_vdot} python={python_vdot}"
            f" differ by more than {tolerance}"
        )
