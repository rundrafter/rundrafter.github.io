"""Shared Playwright fixtures: a real browser serving the form over HTTP.

See docs/architecture.md - tests drive the shipped index.html + assets in a
real browser rather than reimplementing form logic in Python.
"""

from __future__ import annotations

import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent


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
