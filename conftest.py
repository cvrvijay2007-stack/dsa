"""Playwright end-to-end fixtures: a real uvicorn server with a throwaway database."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

expect.set_options(timeout=5000)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def server(tmp_path_factory):
    port = _free_port()
    db = tmp_path_factory.mktemp("db") / "e2e.db"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=BACKEND,
        env={**os.environ, "PRIMS_DB": str(db)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(f"{url}/api/health", timeout=0.5).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        if proc.poll() is not None:
            raise RuntimeError(proc.stderr.read().decode())
        time.sleep(0.1)
    else:
        proc.kill()
        raise RuntimeError("server did not start")
    yield url
    proc.terminate()
    proc.wait(5)


@pytest.fixture(scope="session")
def base_url(server):
    return server


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 1400, "height": 1000}}


@pytest.fixture(autouse=True)
def clean_db(server):
    """Each test starts with no saved graphs."""
    for g in httpx.get(f"{server}/api/graphs").json():
        httpx.delete(f"{server}/api/graphs/{g['id']}")


@pytest.fixture
def app(page: Page):
    """The app loaded with the sample graph, failing the test on any console error."""
    errors: list[str] = []
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("/")
    expect(page.locator("#layer [data-n]")).to_have_count(8)
    expect(page.locator("#prog")).to_have_text("Step 0 of 15")  # trace prefetched
    yield page
    # Failed HTTP responses are logged by the browser itself; tests that expect them assert the UI instead.
    assert not [e for e in errors if not e.startswith("Failed to load resource")], errors


# ---------- helpers ----------

def canvas_point(page: Page, x: float, y: float) -> tuple[float, float]:
    """Convert 800x500 graph coordinates to page pixels (scrolling the canvas into view)."""
    page.locator("#svg").scroll_into_view_if_needed()
    box = page.locator("#svg").bounding_box()
    return box["x"] + x * box["width"] / 800, box["y"] + y * box["height"] / 500


def click_canvas(page: Page, x: float, y: float) -> None:
    page.mouse.click(*canvas_point(page, x, y))


def node_center(page: Page, i: int) -> tuple[float, float]:
    c = page.locator(f'[data-n="{i}"] .nc')
    return canvas_point(page, float(c.get_attribute("cx")), float(c.get_attribute("cy")))


def click_node(page: Page, i: int) -> None:
    page.mouse.click(*node_center(page, i))


def step(page: Page, times: int = 1) -> None:
    for _ in range(times):
        page.locator("#step").click()


def build(page: Page, text: str) -> None:
    page.get_by_role("tab", name="Edge list").click()
    page.locator("#el").fill(text)
    page.get_by_role("button", name="Build graph from list").click()
