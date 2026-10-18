"""Playwright UI smoke tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("playwright")

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
SHOTS = Path("docs/screenshots")
SHOTS.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):  # type: ignore[no-untyped-def]
    return {**browser_context_args, "viewport": {"width": 1280, "height": 800}}


def test_dashboard_loads(page) -> None:  # type: ignore[no-untyped-def]
    page.goto(BASE_URL)
    page.wait_for_selector("text=Meridian")
    assert page.locator(".brand").inner_text() == "Meridian"
    page.screenshot(path=str(SHOTS / "dashboard-overview.png"), full_page=True)


def test_setup_wizard_view(page) -> None:  # type: ignore[no-untyped-def]
    page.goto(BASE_URL)
    page.get_by_role("button", name="Setup", exact=True).click()
    page.wait_for_selector("#view-setup.active")
    page.wait_for_selector("#view-setup .setup-step")
    page.screenshot(path=str(SHOTS / "setup-wizard.png"), full_page=True)


def test_validation_and_signals_views(page) -> None:  # type: ignore[no-untyped-def]
    page.goto(BASE_URL)
    page.get_by_role("button", name="Validation", exact=True).click()
    page.wait_for_selector("text=Walk-forward")
    page.get_by_role("button", name="Load latest report").click()
    page.wait_for_timeout(800)
    page.screenshot(path=str(SHOTS / "validation-panel.png"), full_page=True)
    page.get_by_role("button", name="Signals", exact=True).click()
    page.wait_for_selector("#view-signals.active")
    page.screenshot(path=str(SHOTS / "signals-empty.png"), full_page=True)
    page.get_by_role("button", name="Risk", exact=True).click()
    page.wait_for_selector("#view-risk.active")
    page.screenshot(path=str(SHOTS / "risk-panel.png"), full_page=True)


def test_mobile_width(page) -> None:  # type: ignore[no-untyped-def]
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(BASE_URL)
    page.wait_for_selector("text=Meridian")
    page.screenshot(path=str(SHOTS / "dashboard-mobile.png"), full_page=True)
