"""Playwright UI smoke tests."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("playwright")

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):  # type: ignore[no-untyped-def]
    return {**browser_context_args, "viewport": {"width": 1280, "height": 800}}


def test_dashboard_loads(page) -> None:  # type: ignore[no-untyped-def]
    page.goto(BASE_URL)
    page.wait_for_selector("text=Meridian")
    assert page.locator(".brand").inner_text() == "Meridian"
    page.screenshot(path="docs/screenshots/dashboard-overview.png", full_page=True)


def test_setup_wizard_view(page) -> None:  # type: ignore[no-untyped-def]
    page.goto(BASE_URL)
    page.get_by_role("button", name="Setup").click()
    page.wait_for_selector("text=Setup wizard")
    page.screenshot(path="docs/screenshots/setup-wizard.png", full_page=True)


def test_mobile_width(page) -> None:  # type: ignore[no-untyped-def]
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(BASE_URL)
    page.wait_for_selector("text=Meridian")
    page.screenshot(path="docs/screenshots/dashboard-mobile.png", full_page=True)
